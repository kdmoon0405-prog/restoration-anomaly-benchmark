"""Analyze stored 2x2 bank/query results. Never load images, models or prediction arrays."""
from __future__ import annotations

from collections import defaultdict
from itertools import product
import hashlib
import json
import math
from pathlib import Path
import statistics

import numpy as np

from .analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json
from .analysis_statistics import paired_bootstrap_mean_delta

BANKS = ("clean", "swinir_restored")
QUERIES = ("bicubic_x4", "swinir_x4")
CELLS = tuple(product(BANKS, QUERIES))
METRICS = ("pooled_aupro", "pixel_auroc", "image_auroc", "mean_psnr", "mean_ssim")
SUMMARY_FIELDS = ("bank_domain", "query_domain", "n_test", "n_anomaly", *METRICS)
IMAGE_FIELDS = ("sample", "defect_type", "label", "bank_domain", "query_domain",
                "per_image_aupro", "roi_bg_gap", "psnr", "ssim")
DEFAULTS = dict(schema_version=1, bootstrap_repeats=2000, bootstrap_seed=11,
                quality_atol=1e-9, quality_rtol=1e-9)


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _json_safe(value):
    if isinstance(value, float) and math.isinf(value):
        return "inf" if value > 0 else "-inf"
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(v) for v in value]
    return value


def _sha(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _number(value, name, *, missing=False, infinity=False):
    if value in (None, "", "NA", "N/A", "null", "None", "nan", "NaN") and missing:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid numeric {name}: {value}") from exc
    if math.isnan(result) or (not math.isfinite(result) and not infinity):
        raise ValueError(f"Nonfinite {name}")
    if name in ("pooled_aupro", "pixel_auroc", "image_auroc", "per_image_aupro"):
        if not 0 <= result <= 1:
            raise ValueError(f"{name} must be in [0,1]")
    if name in ("ssim", "mean_ssim") and not -1 <= result <= 1:
        raise ValueError(f"{name} must be in [-1,1]")
    return result


def _integer(value, name):
    number = _number(value, name)
    if int(number) != number or number < 0:
        raise ValueError(f"Expected nonnegative integer {name}")
    return int(number)


def _same_quality(a, b, settings):
    return a == b or math.isclose(a, b, abs_tol=settings["quality_atol"],
                                 rel_tol=settings["quality_rtol"])


def load_settings(path=None) -> dict:
    settings = dict(DEFAULTS)
    if path:
        provided = read_json(Path(path))
        if set(provided) - set(settings):
            raise ValueError("Unknown analysis config fields")
        settings.update(provided)
    if (settings["schema_version"] != 1 or isinstance(settings["bootstrap_repeats"], bool)
            or not isinstance(settings["bootstrap_repeats"], int) or settings["bootstrap_repeats"] < 1
            or not isinstance(settings["bootstrap_seed"], int) or settings["bootstrap_seed"] < 0
            or any(not isinstance(settings[k], (int, float)) or not math.isfinite(settings[k])
                   or settings[k] < 0 for k in ("quality_atol", "quality_rtol"))):
        raise ValueError("Invalid analysis settings")
    return settings


def load_run(directory, *, settings, allow_synthetic=False, source_root=None):
    directory = Path(directory).resolve()
    manifest_path = directory / "bank_domain_manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "bank_domain_study_results":
        raise ValueError("Not a bank-domain result manifest v1")
    if manifest.get("status") in ("PARTIAL", "FAILED", "PREFLIGHT_PASS"):
        return None, dict(run=str(directory), status=manifest["status"], reason="not complete")
    if manifest.get("status") != "COMPLETE":
        raise ValueError("Unknown run status")
    if manifest.get("evidence_kind") not in ("model_predictions", "synthetic_fixture"):
        raise ValueError("Unknown evidence kind")
    if manifest["evidence_kind"] == "synthetic_fixture" and not allow_synthetic:
        raise ValueError("Synthetic fixture requires explicit --allow-synthetic")
    files = manifest.get("files", {})
    required = ("summary.csv", "per_image.csv", "config.json", "provenance.json")
    if set(files) != set(required) or any(not _sha(files[n]) for n in required):
        raise ValueError("Manifest must bind the four result files by SHA256")
    for name in required:
        if digest(relative_source(directory, name)) != files[name]:
            raise ValueError(f"Artifact hash mismatch: {name}")
    config = read_json(directory / "config.json")
    provenance = read_json(directory / "provenance.json")
    family, category, seed = config["study_family"], config["category"], config["seed"]
    if not isinstance(family, str) or not family or not isinstance(category, str) or not category:
        raise ValueError("Missing study family/category")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("Invalid experiment seed")
    protocol = config["protocol"]
    required_protocol = ("dataset", "geometry_id", "degradation_id", "detector_id",
                         "restorer_id", "calibration_source", "metric_definition",
                         "bank_spec", "checkpoints_sha256")
    if not isinstance(protocol, dict) or any(not protocol.get(k) for k in required_protocol):
        raise ValueError("Protocol lacks family-defining fields")
    if protocol["calibration_source"] != "normal_calibration_only":
        raise ValueError("Calibration must use separate normal calibration")
    if (not isinstance(protocol["bank_spec"], dict)
            or not isinstance(protocol["checkpoints_sha256"], dict)
            or not protocol["checkpoints_sha256"]
            or any(not _sha(v) for v in protocol["checkpoints_sha256"].values())):
        raise ValueError("Bank specification and checkpoint identities must define the protocol")
    if protocol["metric_definition"] != dict(primary="pooled_aupro", max_fpr=0.3,
                                              num_thresholds=200, connectivity=4):
        raise ValueError("Metric definition differs from the frozen bank-domain study")
    if (provenance.get("normal_fit_calibration_disjoint") is not True
            or provenance.get("test_gt_used_for_selection") is not False):
        raise ValueError("Split/GT provenance is incomplete or violates the protocol")
    for field in ("input_manifest_sha256", "split_manifest_sha256",
                  "test_manifest_sha256", "query_manifest_sha256"):
        if not _sha(provenance.get(field)):
            raise ValueError(f"Missing provenance digest: {field}")
    banks = provenance.get("bank_manifest_sha256", {})
    code = provenance.get("code_sha256", {})
    if set(banks) != set(BANKS) or any(not _sha(v) for v in banks.values()):
        raise ValueError("Both bank manifests must be bound")
    if not code or any(not _sha(v) for v in code.values()):
        raise ValueError("Execution source digests are required")
    vector_counts = provenance.get("bank_vector_counts", {})
    if (set(vector_counts) != set(BANKS)
            or any(type(v) is not int or v < 1 for v in vector_counts.values())
            or len(set(vector_counts.values())) != 1):
        raise ValueError("The two banks must have equal positive vector counts")
    for name, expected in code.items():
        path = relative_source(Path(source_root or directory), name)
        if source_root is not None and digest(path) != expected:
            raise ValueError(f"Execution source mismatch: {name}")
    commit = provenance.get("source_commit", "")
    if (not isinstance(commit, str) or len(commit) != 40
            or any(c not in "0123456789abcdef" for c in commit)
            or not isinstance(provenance.get("source_worktree_dirty"), bool)):
        raise ValueError("Missing execution commit/dirty provenance")
    summaries = {}
    for raw in csv_rows(directory / "summary.csv", SUMMARY_FIELDS):
        key = raw["bank_domain"], raw["query_domain"]
        if key not in CELLS or key in summaries:
            raise ValueError("Unknown or duplicate summary cell")
        row = {k: _number(raw[k], k, missing=k == "image_auroc", infinity=k == "mean_psnr")
               for k in METRICS}
        row.update(n_test=_integer(raw["n_test"], "n_test"),
                   n_anomaly=_integer(raw["n_anomaly"], "n_anomaly"))
        if not 0 < row["n_anomaly"] <= row["n_test"]:
            raise ValueError("Result must contain anomalous test images")
        summaries[key] = row
    if set(summaries) != set(CELLS):
        raise ValueError("COMPLETE run is missing a 2x2 condition")
    images = {cell: {} for cell in CELLS}
    for raw in csv_rows(directory / "per_image.csv", IMAGE_FIELDS):
        cell = raw["bank_domain"], raw["query_domain"]
        sample = raw["sample"]
        relative_source(directory, sample)  # Validate spelling only; never open image/GT.
        if cell not in images or sample in images[cell]:
            raise ValueError("Unknown or duplicate per-image cell/sample")
        label = _integer(raw["label"], "label")
        if label not in (0, 1) or not raw["defect_type"]:
            raise ValueError("Invalid label/defect")
        aupro = _number(raw["per_image_aupro"], "per_image_aupro", missing=not label)
        gap = _number(raw["roi_bg_gap"], "roi_bg_gap", missing=not label)
        if not label and aupro is not None:
            raise ValueError("Normal per-image AU-PRO must be not applicable")
        images[cell][sample] = dict(sample=sample, label=label, defect_type=raw["defect_type"],
            per_image_aupro=aupro, roi_bg_gap=gap, psnr=_number(raw["psnr"], "psnr", infinity=True),
            ssim=_number(raw["ssim"], "ssim"))
    first = images[CELLS[0]]
    identity = {s: (r["label"], r["defect_type"]) for s, r in first.items()}
    for cell in CELLS:
        rows = images[cell]
        if {s: (r["label"], r["defect_type"]) for s, r in rows.items()} != identity:
            raise ValueError("Paired sample/label/defect identities differ between cells")
        if (len(rows) != summaries[cell]["n_test"]
                or sum(r["label"] for r in rows.values()) != summaries[cell]["n_anomaly"]):
            raise ValueError("Summary and per-image cohort counts disagree")
    for query in QUERIES:
        for sample in first:
            a, b = (images[(bank, query)][sample] for bank in BANKS)
            if any(not _same_quality(a[k], b[k], settings) for k in ("psnr", "ssim")):
                raise ValueError("Same-query RGB quality differs between banks")
        a, b = (summaries[(bank, query)] for bank in BANKS)
        if any(not _same_quality(a[k], b[k], settings) for k in ("mean_psnr", "mean_ssim")):
            raise ValueError("Same-query summary quality differs between banks")
    protocol_id = hashlib.sha256(_canonical(dict(protocol=protocol, code_sha256=code)).encode()).hexdigest()
    common = dict(study_family=family, protocol_sha256=protocol_id, dataset=protocol["dataset"], category=category, seed=seed,
                  evidence_kind=manifest["evidence_kind"], source_run=str(directory),
                  source_commit=commit, source_worktree_dirty=provenance["source_worktree_dirty"])
    signature = dict(config=config, summary=[(c, summaries[c]) for c in CELLS],
        images=[(c, sorted(images[c].items())) for c in CELLS],
        evidence={k: provenance[k] for k in ("input_manifest_sha256", "split_manifest_sha256",
            "test_manifest_sha256", "query_manifest_sha256", "bank_manifest_sha256",
            "bank_vector_counts", "code_sha256")},
        evidence_kind=manifest["evidence_kind"])
    run = dict(common=common, summary=summaries, images=images, provenance=provenance,
               signature=_canonical(_json_safe(signature)), identity=identity,
               source_files={**files, "bank_domain_manifest.json": digest(manifest_path)},
               source_byte_binding_checked=source_root is not None)
    return run, None


def _difference(candidate, reference):
    if candidate is None or reference is None or (math.isinf(candidate) and candidate == reference):
        return None
    return candidate - reference


def _effect(run, reference, candidate, axis, settings):
    common = run["common"]
    title = f"{candidate[0]}:{candidate[1]}_minus_{reference[0]}:{reference[1]}"
    row = dict(common, axis=axis, contrast=title)
    a, b = run["summary"][reference], run["summary"][candidate]
    row.update(n_test=a["n_test"], n_anomaly=a["n_anomaly"])
    for name in METRICS:
        row["delta_" + name] = _difference(b[name], a[name])
    if axis == "bank":
        row.update(delta_mean_psnr=0.0, delta_mean_ssim=0.0)
    paired = []
    for sample in sorted(run["identity"]):
        a, b = (run["images"][c][sample] for c in (reference, candidate))
        if not a["label"]:
            continue
        delta = b["per_image_aupro"] - a["per_image_aupro"]
        gap = b["roi_bg_gap"] - a["roi_bg_gap"]
        regression = "improvement_or_tie" if delta >= 0 else ("suppression" if gap < 0 else "geometry_candidate")
        paired.append(dict(common, axis=axis, contrast=title, sample=sample, defect_type=a["defect_type"],
            reference_aupro=a["per_image_aupro"], candidate_aupro=b["per_image_aupro"],
            delta_per_image_aupro=delta, delta_roi_bg_gap=gap, regression_type=regression,
            delta_psnr=0.0 if axis == "bank" else _difference(b["psnr"], a["psnr"]),
            delta_ssim=0.0 if axis == "bank" else b["ssim"] - a["ssim"]))
    deltas = np.asarray([r["delta_per_image_aupro"] for r in paired])
    # One deterministic stream per paired contrast, independent of input ordering.
    salt = int(hashlib.sha256(_canonical([common["study_family"], common["protocol_sha256"],
        common["category"], common["seed"], axis, title]).encode()).hexdigest()[:16], 16)
    boot = paired_bootstrap_mean_delta(deltas, settings["bootstrap_repeats"],
                                      np.random.default_rng(np.random.SeedSequence([settings["bootstrap_seed"], salt])))
    row.update(mean_delta_per_image_aupro=boot["estimate"], median_delta_per_image_aupro=float(np.median(deltas)),
        worst_10_mean_delta=float(np.sort(deltas)[:10].mean()), min_delta=float(deltas.min()),
        per_image_mean_ci95_low=boot["ci95"][0], per_image_mean_ci95_high=boot["ci95"][1],
        paired_anomaly_images=boot["n"], ci_estimand="mean_paired_per_anomalous_image_aupro_delta",
        pooled_aupro_ci_computed=False)
    for kind in ("suppression", "geometry_candidate", "improvement_or_tie"):
        count = sum(r["regression_type"] == kind for r in paired)
        row[kind + "_count"], row[kind + "_rate"] = count, count / len(paired)
    row["localization_regression_count"] = sum(r["delta_per_image_aupro"] < 0 for r in paired)
    row["localization_regression_rate"] = row["localization_regression_count"] / len(paired)
    return row, paired


def analyze_runs(inputs, output, *, config=None, allow_synthetic=False, source_root=None):
    settings = load_settings(config)
    inputs = [Path(p).resolve() for p in inputs]
    if not inputs:
        raise ValueError("At least one --run is required")
    runs, skipped, duplicates = {}, [], []
    cohorts = {}
    for path in inputs:
        run, skip = load_run(path, settings=settings, allow_synthetic=allow_synthetic, source_root=source_root)
        if skip:
            skipped.append(skip)
            continue
        c = run["common"]
        key = c["study_family"], c["protocol_sha256"], c["category"], c["seed"]
        if key in runs:
            if runs[key]["signature"] != run["signature"]:
                raise ValueError("Conflicting duplicate scientific condition; select input explicitly")
            duplicates.append(dict(duplicate=str(path), retained=runs[key]["common"]["source_run"]))
            continue
        cohort_key = key[:3]
        identity = (run["identity"], run["provenance"]["test_manifest_sha256"])
        if cohort_key in cohorts and cohorts[cohort_key] != identity:
            raise ValueError("Official test cohort changed between seeds")
        cohorts[cohort_key] = identity
        runs[key] = run
    if len({r["common"]["evidence_kind"] for r in runs.values()}) > 1:
        raise ValueError("Do not combine synthetic and actual evidence in one analysis")
    summaries, bank_effects, query_effects, paired_rows, quality = [], [], [], [], []
    for key, run in sorted(runs.items()):
        c = run["common"]
        for cell in CELLS:
            summaries.append(dict(c, bank_domain=cell[0], query_domain=cell[1], **run["summary"][cell]))
        for query in QUERIES:
            row, paired = _effect(run, (BANKS[0], query), (BANKS[1], query), "bank", settings)
            bank_effects.append(row)
            paired_rows.extend(paired)
            for sample, r in sorted(run["images"][(BANKS[0], query)].items()):
                quality.append(dict(c, query_domain=query, sample=sample, label=r["label"],
                                    psnr=r["psnr"], ssim=r["ssim"], bank_copies_removed=1))
        for bank in BANKS:
            row, paired = _effect(run, (bank, QUERIES[0]), (bank, QUERIES[1]), "query", settings)
            query_effects.append(row)
            paired_rows.extend(paired)
    grouped = defaultdict(list)
    for row in bank_effects + query_effects:
        grouped[tuple(row[k] for k in ("study_family", "protocol_sha256", "category", "axis", "contrast"))].append(row)
    seed_rows = []
    for key, rows in sorted(grouped.items()):
        values = [r["delta_pooled_aupro"] for r in rows]
        seed_rows.append(dict(zip(("study_family", "protocol_sha256", "category", "axis", "contrast"), key),
            evidence_kind=rows[0]["evidence_kind"],
            seed_count=len(rows), seeds=";".join(str(r["seed"]) for r in rows),
            mean_delta_pooled_aupro=statistics.fmean(values),
            min_delta_pooled_aupro=min(values), max_delta_pooled_aupro=max(values),
            between_seed_sd=statistics.stdev(values) if len(values) > 1 else None,
            repeated_images_are_not_independent=True, cross_seed_ci_computed=False))
    out = new_output(Path(output), inputs)
    tables = dict(bank_domain_summary=summaries, bank_effects=bank_effects, query_effects=query_effects,
                  per_image_deltas=paired_rows, quality_by_query=quality, seed_summary=seed_rows)
    for name, rows in tables.items():
        write_csv(out / (name + ".csv"), rows, fields=None if rows else ["study_family", "category", "seed"])
    report = dict(kind="read_only_bank_domain_analysis", schema_version=1,
        status="COMPLETE" if runs else "NO_COMPLETE_INPUTS", settings=settings,
        complete_unique_runs=len(runs), skipped_runs=skipped, duplicate_runs=duplicates,
        evidence_kinds=sorted({r["common"]["evidence_kind"] for r in runs.values()}),
        raw_prediction_arrays_opened=False, detection_metrics_recomputed=False,
        source_byte_binding_checked=source_root is not None, plots_generated=False,
        ci_scope="Per-contrast and per-seed anomalous-image paired mean; not pooled AU-PRO or cross-seed CI",
        sources=[dict(run=r["common"]["source_run"], files=r["source_files"],
                      provenance=r["provenance"]) for r in runs.values()],
        analysis_code_sha256={p.name: digest(p) for p in
            (Path(__file__), Path(__file__).with_name("analysis_io.py"),
             Path(__file__).with_name("analysis_statistics.py"))},
        tables={name + ".csv": digest(out / (name + ".csv")) for name in tables})
    write_json(out / "analysis_manifest.json", _json_safe(report))
    lines = ["# Bank-domain stored-result analysis", "",
        f"Complete unique category/seed runs: {len(runs)}. Duplicate copies removed: {len(duplicates)}.",
        f"Evidence kinds: {', '.join(report['evidence_kinds']) or 'none'}.",
        "Primary: stored dataset pooled AU-PRO@0.3. No detector evaluation was rerun.", "",
        "| family/category/seed | paired contrast | delta pooled AU-PRO | mean per-image delta |",
        "|---|---|---:|---:|"]
    for r in bank_effects:
        lines.append(f"| {r['study_family']}/{r['category']}/{r['seed']} | {r['contrast']} | "
                     f"{r['delta_pooled_aupro']:.6f} | {r['mean_delta_per_image_aupro']:.6f} |")
    lines += ["", "Per-image CIs are supplementary and computed within each seed; repeated seeds do not multiply independent images.",
              "Same-query quality is counted once across banks. Protocol hashes keep geometry/kernel/model families separate.",
              "Source digests are recorded; raw arrays and remote execution were not independently observed.",
              "Synthetic fixtures require explicit opt-in and are labelled in every data table.",
              "Plots are deferred until actual result artifacts are supplied.", ""]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    return report
