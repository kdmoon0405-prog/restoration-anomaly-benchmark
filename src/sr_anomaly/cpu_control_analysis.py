"""Read-only paired analysis of completed CPU controls, preserving seed dependence."""
from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from .analysis_io import csv_rows, digest, new_output, read_json, write_csv, write_json
from .analysis_statistics import paired_bootstrap_mean_delta

VARIANTS = ("clean", "bicubic_x4", "unsharp_x4")


def _number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Expected a finite analysis value")
    return result


def analyze_controls(inputs, output, *, expected_seeds=(11, 23, 37), repeats=2000, bootstrap_seed=11,
                     expected_variants=VARIANTS, candidate="unsharp_x4"):
    runs, identities, template = [], set(), None
    for directory in sorted(Path(p).resolve() for p in inputs):
        state = read_json(directory / "status.json")
        if state.get("status") != "EVALUATED_COMPLETE":
            raise ValueError("Only completed CPU control runs can enter this analysis")
        settings = dict(state["settings"])
        settings.pop("seed")
        settings.pop("variants", None)
        spec = settings, state["source_code_sha256"], state["input_inventory_sha256"]
        if template is not None and spec != template:
            raise ValueError("CPU control protocol/source/input inventory differs")
        template = spec
        for name, expected in state["artifact_sha256"].items():
            if digest(directory / name) != expected:
                raise ValueError("Completed CPU artifact changed")
        summary = csv_rows(directory / "summary.csv")
        per_image = csv_rows(directory / "per_image.csv")
        variants = {r["variant"] for r in summary}
        if len(summary) != len(variants) or not variants or not variants <= set(expected_variants):
            raise ValueError("Missing or duplicate CPU summary condition")
        for variant in variants:
            identity = state["category"], state["seed"], variant
            if identity in identities:
                raise ValueError("Duplicate category/seed/variant run")
            identities.add(identity)
        keys = [(r["sample"], r["variant"]) for r in per_image]
        samples = {r["sample"] for r in per_image}
        if (len(keys) != len(set(keys)) or len(samples) != state["test_count"]
                or set(keys) != {(s, v) for s in samples for v in variants}):
            raise ValueError("Unpaired, duplicate or missing CPU per-image condition")
        for row in per_image:
            if int(row["label"]) == 0 and row["per_image_aupro"] != "":
                raise ValueError("Normal per-image AU-PRO must be N/A")
            if int(row["label"]) == 1 and not 0 <= _number(row["per_image_aupro"]) <= 1:
                raise ValueError("Invalid anomalous per-image AU-PRO")
        runs.append((directory, state, summary, per_image))
    if not runs:
        raise ValueError("No completed CPU inputs")
    restoration_caches = {state["cache_status_sha256"] for _, state, _, _ in runs
                          if "cache_status_sha256" in state}
    if len(restoration_caches) > 1:
        raise ValueError("Restored conditions use different cache bindings")
    categories = template[0]["categories"]
    expected = {(c, s, v) for c in categories for s in expected_seeds for v in expected_variants}
    if identities != expected:
        raise ValueError("Incomplete or unexpected category/seed matrix")

    supplied_runs = runs
    grouped_runs = {}
    for directory, state, summary, per_image in runs:
        key = state["category"], state["seed"]
        if key not in grouped_runs:
            grouped_runs[key] = [directory, state, [], []]
        group = grouped_runs[key]
        if group[1].get("bank_sha256") != state.get("bank_sha256"):
            raise ValueError("Query variants use different bank bytes")
        group[2].extend(dict(row, source_run=str(directory)) for row in summary)
        group[3].extend(per_image)
    runs = list(grouped_runs.values())
    quality, labels, all_summary, seed_effects, paired = {}, {}, [], [], []
    seed_vectors = defaultdict(dict)
    for directory, state, summary, per_image in runs:
        category, seed = state["category"], state["seed"]
        lookup = {(r["sample"], r["variant"]): r for r in per_image}
        samples = sorted({r["sample"] for r in per_image})
        label_set = {s: int(lookup[s, "clean"]["label"]) for s in samples}
        if category in labels and labels[category] != label_set:
            raise ValueError("Test sample/label set differs across seeds")
        labels[category] = label_set
        for row in per_image:
            if int(row["label"]) != label_set[row["sample"]]:
                raise ValueError("Labels differ between query conditions")
            key = category, row["sample"], row["variant"]
            value = dict(category=category, sample=row["sample"], variant=row["variant"],
                         rgb_sha256=row["rgb_sha256"], psnr=row["psnr"], ssim=row["ssim"])
            if key in quality:
                old = quality[key]
                if old["rgb_sha256"] != value["rgb_sha256"]:
                    raise ValueError("Query RGB differs across seeds")
                for metric in ("psnr", "ssim"):
                    if old[metric] != value[metric] and not math.isclose(
                            float(old[metric]), float(value[metric]), rel_tol=0, abs_tol=1e-12):
                        raise ValueError("Same-query quality differs across seeds")
            quality[key] = value
        methods = {r["variant"]: r for r in summary}
        bic, sharp = methods["bicubic_x4"], methods[candidate]
        for row in summary:
            all_summary.append(dict(row, source_run=row.get("source_run", str(directory))))
        own = []
        for sample in samples:
            if not label_set[sample]:
                continue
            a, b = lookup[sample, "bicubic_x4"], lookup[sample, candidate]
            delta = _number(b["per_image_aupro"]) - _number(a["per_image_aupro"])
            gap = _number(b["roi_bg_gap"]) - _number(a["roi_bg_gap"])
            kind = "improvement_or_tie"
            if delta < 0:
                kind = "suppression" if gap < 0 else "geometry_candidate"
            paired.append(dict(category=category, seed=seed, sample=sample,
                defect_type=Path(sample).parent.name, delta_per_image_aupro=delta,
                delta_roi_bg_gap=gap, regression_type=kind))
            own.append(delta)
            seed_vectors[category, sample][seed] = delta
        stats = paired_bootstrap_mean_delta(np.array(own), repeats, np.random.default_rng(bootstrap_seed))
        seed_effects.append(dict(category=category, seed=seed, n_anomalous_images=len(own),
            delta_pooled_aupro=_number(sharp["au_pro"]) - _number(bic["au_pro"]),
            delta_pixel_auroc=_number(sharp["pixel_auroc"]) - _number(bic["pixel_auroc"]),
            delta_psnr=_number(sharp["mean_psnr"]) - _number(bic["mean_psnr"]),
            delta_ssim=_number(sharp["mean_ssim"]) - _number(bic["mean_ssim"]),
            mean_per_image_aupro_delta=stats["estimate"], ci95_low=stats["ci95"][0], ci95_high=stats["ci95"][1],
            regression_count=sum(d < 0 for d in own)))

    image_means, category_effects, associations = [], [], []
    for (category, sample), values in sorted(seed_vectors.items()):
        if set(values) != set(expected_seeds):
            raise ValueError("Anomalous image is missing a seed")
        image_means.append(dict(category=category, sample=sample, n_seeds=len(values),
            mean_delta_per_image_aupro=float(np.mean(list(values.values())))))
    for category in categories:
        own = [r for r in image_means if r["category"] == category]
        stats = paired_bootstrap_mean_delta(np.array([r["mean_delta_per_image_aupro"] for r in own]),
                                            repeats, np.random.default_rng(bootstrap_seed))
        pooled = [r["delta_pooled_aupro"] for r in seed_effects if r["category"] == category]
        category_effects.append(dict(category=category, n_seeds=len(pooled), n_anomalous_images=len(own),
            mean_delta_pooled_aupro=float(np.mean(pooled)), min_delta_pooled_aupro=min(pooled),
            max_delta_pooled_aupro=max(pooled),
            conditional_mean_per_image_aupro_delta=stats["estimate"],
            conditional_ci95_low=stats["ci95"][0], conditional_ci95_high=stats["ci95"][1]))
        for metric in ("psnr", "ssim"):
            x = [float(quality[category, r["sample"], candidate][metric])
                 - float(quality[category, r["sample"], "bicubic_x4"][metric]) for r in own]
            y = [r["mean_delta_per_image_aupro"] for r in own]
            rho = float(spearmanr(x, y).statistic) if len(set(x)) > 1 and len(set(y)) > 1 else None
            associations.append(dict(category=category, quality_metric=metric, n_images=len(own),
                response="mean_across_seed_delta_per_image_aupro", spearman_rho=rho))
    out = new_output(Path(output), [r[0] for r in supplied_runs])
    tables = dict(control_summary=all_summary, seed_effects=seed_effects, paired_effects=paired,
                  image_mean_effects=image_means, category_effects=category_effects,
                  quality_unique=list(quality.values()), quality_association=associations)
    for name, rows in tables.items():
        write_csv(out / (name + ".csv"), rows)
    receipt = dict(kind="completed_cpu_hog_control_analysis", status="COMPLETE",
        expected_seeds=list(expected_seeds), comparison=candidate + " minus bicubic_x4",
        primary_metric="dataset pooled AU-PRO@0.3 point estimate per seed",
        bootstrap_repeats=repeats, bootstrap_seed=bootstrap_seed,
        conditional_ci_scope="image resampling conditional on the fixed bank fits; seeds are not independent images",
        regression_scope="post-hoc normalized-map pattern; no feature-space mechanism inference",
        quality_unique_rows=len(quality), paired_anomaly_seed_rows=len(paired),
        independent_anomaly_image_units=len(image_means),
        source_runs=[dict(path=str(d), status_sha256=digest(d / "status.json")) for d, _, _, _ in supplied_runs],
        code_sha256=digest(Path(__file__)), tables={n + ".csv": digest(out / (n + ".csv")) for n in tables})
    write_json(out / "analysis_manifest.json", receipt)
    return receipt
