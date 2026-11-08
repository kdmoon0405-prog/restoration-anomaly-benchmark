"""Read completed CPU bank-domain tables, including the matched-Bicubic control."""
from collections import defaultdict
from pathlib import Path
import argparse
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import csv_rows, digest, new_output, read_json, write_csv, write_json
from sr_anomaly.analysis_statistics import paired_bootstrap_mean_delta
from sr_anomaly.bank_domain_analysis import analyze_runs, load_run, load_settings, _effect, METRICS


def analyze(execution, output, *, mixed_execution=None, allow_synthetic=False, source_root=ROOT):
    execution = Path(execution)
    state = read_json(execution / "status.json")
    if state["status"] != "CPU_BANK_DOMAIN_COMPLETE":
        raise ValueError("CPU bank-domain execution is incomplete")
    banks = ("clean", "bicubic_matched", "swinir_restored")
    if mixed_execution is not None:
        mixed_execution = Path(mixed_execution)
        if read_json(mixed_execution / "status.json")["status"] != "CPU_MIXED_BANK_COMPLETE":
            raise ValueError("Mixed-bank execution is incomplete")
        protocol = read_json(mixed_execution / "PROTOCOL.json")
        if protocol["ratio"] != 0.5 or protocol["source_execution_sha256"] != digest(execution / "status.json"):
            raise ValueError("Mixed-bank source/ratio mismatch")
        banks += ("balanced_mixed",)
    sources = sorted((execution / "core-results").iterdir())
    plan = read_json(execution / "PROTOCOL.json")["config"]
    expected = {(category, seed) for category in plan["categories"] for seed in plan["seeds"]}
    identities = [(read_json(p / "config.json")["category"], read_json(p / "config.json")["seed"]) for p in sources]
    if set(identities) != expected or len(identities) != len(expected):
        raise ValueError("Missing or duplicate category/seed result")
    out = new_output(Path(output), [execution] + ([mixed_execution] if mixed_execution else []))
    core = analyze_runs(sources, out / "core", allow_synthetic=allow_synthetic, source_root=source_root)
    settings = load_settings()
    matrix, effects, paired, receipts = [], [], [], []
    quality = {}
    for source in sources:
        run, skip = load_run(source, settings=settings, allow_synthetic=allow_synthetic, source_root=source_root)
        if skip:
            raise ValueError("A core run is incomplete")
        for bank, query in [(bank, query) for bank in banks if bank not in ("clean", "swinir_restored")
                            for query in ("bicubic_x4", "swinir_x4")]:
            parent = mixed_execution if bank == "balanced_mixed" else execution
            extra = parent / "runs" / source.name / bank / query
            status = read_json(extra / "status.json")
            if status["status"] != "EVALUATED_COMPLETE":
                raise ValueError("Matched-Bicubic condition is incomplete")
            for name, sha in status["artifact_sha256"].items():
                if digest(extra / name) != sha:
                    raise ValueError("Matched-Bicubic artifact changed")
            raw = csv_rows(extra / "summary.csv")
            if len(raw) != 1 or raw[0]["bank_domain"] != bank or raw[0]["query_domain"] != query:
                raise ValueError("Wrong matched-Bicubic summary")
            row = raw[0]
            cell = bank, query
            run["summary"][cell] = {k: float(row[k]) if row[k] != "" else None for k in METRICS}
            run["summary"][cell].update(n_test=int(row["n_test"]), n_anomaly=int(row["n_anomaly"]))
            image_rows = csv_rows(extra / "per_image.csv")
            images = {}
            for row in image_rows:
                if row["sample"] in images:
                    raise ValueError("Duplicate matched-Bicubic image")
                label = int(row["label"])
                if not label and row["per_image_aupro"] != "":
                    raise ValueError("Normal per-image AU-PRO must be N/A")
                images[row["sample"]] = dict(sample=row["sample"], label=label, defect_type=row["defect_type"],
                    per_image_aupro=float(row["per_image_aupro"]) if label else None,
                    roi_bg_gap=float(row["roi_bg_gap"]) if label else None,
                    psnr=float(row["psnr"]), ssim=float(row["ssim"]))
            if {s: (r["label"], r["defect_type"]) for s, r in images.items()} != run["identity"]:
                raise ValueError("Matched-Bicubic sample/label identities differ")
            if (run["summary"][cell]["n_test"] != len(images)
                    or run["summary"][cell]["n_anomaly"] != sum(r["label"] for r in images.values())):
                raise ValueError("Matched-Bicubic counts differ from image rows")
            run["images"][cell] = images
            for sample, row in images.items():
                reference = run["images"]["clean", query][sample]
                if any(not np.isclose(row[k], reference[k], rtol=1e-9, atol=1e-9) for k in ("psnr", "ssim")):
                    raise ValueError("Same-query quality changed with bank domain")
            receipts.append(dict(path=str(extra), status_sha256=digest(extra / "status.json")))
        for cell in sorted(run["summary"]):
            matrix.append(dict(run["common"], bank_domain=cell[0], query_domain=cell[1], **run["summary"][cell]))
        comparisons = []
        for query in ("bicubic_x4", "swinir_x4"):
            comparisons += [(("clean", query), (bank, query), "bank") for bank in banks if bank != "clean"]
        comparisons += [((bank, "bicubic_x4"), (bank, "swinir_x4"), "query")
                        for bank in banks]
        comparisons.append((("bicubic_matched", "bicubic_x4"), ("swinir_restored", "swinir_x4"), "pipeline"))
        if mixed_execution:
            comparisons.extend([((bank, query), ("balanced_mixed", query), "bank_capacity")
                                for bank, query in (("bicubic_matched", "bicubic_x4"),
                                                    ("swinir_restored", "swinir_x4"))])
        for reference, candidate, axis in comparisons:
            row, images = _effect(run, reference, candidate, axis, settings)
            effects.append(row)
            paired.extend(images)
        for query in ("bicubic_x4", "swinir_x4"):
            for sample, row in run["images"]["clean", query].items():
                key = run["common"]["category"], sample, query
                value = (row["psnr"], row["ssim"])
                if key in quality and not np.allclose(quality[key], value, atol=1e-9, rtol=1e-9):
                    raise ValueError("Query quality differs across seeds")
                quality[key] = value
    seed_groups, image_groups = defaultdict(list), defaultdict(list)
    for row in effects:
        seed_groups[row["category"], row["axis"], row["contrast"]].append(row)
    for row in paired:
        image_groups[row["category"], row["axis"], row["contrast"], row["sample"]].append(row)
    image_means = []
    for (category, axis, contrast, sample), rows in sorted(image_groups.items()):
        image_means.append(dict(category=category, axis=axis, contrast=contrast, sample=sample,
            n_seeds=len(rows), mean_delta_per_image_aupro=float(np.mean([r["delta_per_image_aupro"] for r in rows]))))
    seed_summary = []
    for (category, axis, contrast), rows in sorted(seed_groups.items()):
        values = [r["delta_pooled_aupro"] for r in rows]
        images = [r["mean_delta_per_image_aupro"] for r in image_means
                  if (r["category"], r["axis"], r["contrast"]) == (category, axis, contrast)]
        boot = paired_bootstrap_mean_delta(np.array(images), settings["bootstrap_repeats"],
                                          np.random.default_rng(settings["bootstrap_seed"]))
        seed_summary.append(dict(category=category, axis=axis, contrast=contrast, n_seeds=len(rows),
            mean_delta_pooled_aupro=float(np.mean(values)), min_delta_pooled_aupro=min(values), max_delta_pooled_aupro=max(values),
            unique_anomaly_images=boot["n"], conditional_mean_per_image_delta=boot["estimate"],
            conditional_ci95_low=boot["ci95"][0], conditional_ci95_high=boot["ci95"][1]))
    tables = dict(matrix_summary=matrix, paired_effects=effects, per_image_deltas=paired,
                  image_seed_mean_deltas=image_means, seed_summary=seed_summary)
    for name, rows in tables.items():
        write_csv(out / (name + ".csv"), rows)
    manifest = dict(kind="read_only_cpu_bank_two_query_analysis", status="COMPLETE", bank_domains=list(banks),
        matrix_rows=len(matrix), newly_computed_condition_rows=sum(r["bank_domain"] != "clean" for r in matrix),
        reused_clean_condition_rows=sum(r["bank_domain"] == "clean" for r in matrix),
        unique_query_quality_rows=len(quality),
        core_analysis_sha256=digest(out / "core/analysis_manifest.json"), source_receipts=receipts,
        analysis_code_sha256=digest(Path(__file__)),
        mixed_protocol=read_json(mixed_execution / "PROTOCOL.json") if mixed_execution else None,
        mixed_status_sha256=digest(mixed_execution / "status.json") if mixed_execution else None,
        ci_scope="image resampling conditional on fixed seed fits; pooled effects are point estimates",
        raw_prediction_arrays_opened=False, detection_metrics_recomputed=False,
        tables={name + ".csv": digest(out / (name + ".csv")) for name in tables})
    write_json(out / "analysis_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mixed-execution", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.execution, args.output, mixed_execution=args.mixed_execution)))
