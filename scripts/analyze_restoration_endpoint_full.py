"""Analyze saved Hazelnut restoration-endpoint artifacts; never run model inference."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
from math import sqrt

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PILOT_RESULTS = ROOT / "analysis" / "restoration_objective_pilot" / "results"
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_hazelnut_failures import _bootstrap_mean_delta, _spearman  # noqa: E402
from sr_anomaly.evaluation import evaluate_predictions  # noqa: E402

VARIANTS = ("bicubic_x4", "swinir_x4", "rrdb_psnr_x4", "rrdb_esrgan_x4")
LEARNED = VARIANTS[1:]
TAUS = (0.0, 0.005, 0.01, 0.02, 0.05)
MANIFESTS = {
    "restoration_objective_pilot": ("analysis/restoration_objective_pilot/pilot_manifest.csv", "4d3b23548b5add0f067bec44330062870cde00a1521b9680198744f32bbf3603", 25, 5, 20),
    "restoration_objective_full": ("analysis/restoration_objective_full/full_manifest.csv", "2ddb62748c750b3e4fae2b4b0b0cb4f3c354fd02faac74c95117afe1b3e116cc", 110, 40, 70),
}
COMPARE_FIELDS = ("image_score", "psnr", "ssim", "lpips", "per_image_pixel_auroc", "per_image_aupro", "roi_mean", "background_mean", "roi_bg_gap")


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(fields).issubset(reader.fieldnames or ()):
            raise ValueError(f"{path.name} missing required columns: {sorted(set(fields) - set(reader.fieldnames or ()))}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path.name} is empty")
    return rows


def _number(row: dict[str, str], key: str) -> float:
    value = float(row[key])
    if not np.isfinite(value):
        raise ValueError(f"Non-finite {key}: {row.get('sample', row.get('variant', 'unknown'))}")
    return value


def _unique(rows: list[dict[str, str]], fields: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, str]]:
    result = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in result:
            raise ValueError(f"Duplicate {fields}: {key}")
        result[key] = row
    return result


def _manifest(study: str) -> list[dict[str, str]]:
    relative, expected_hash, total, normal, anomalous = MANIFESTS[study]
    path = ROOT / relative
    if sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError(f"Frozen manifest hash changed: {path}")
    rows = _read_csv(path, ("sample", "label", "defect_type", "image_sha256", "mask_sha256"))
    counts = (len(rows), sum(row["label"] == "0" for row in rows), sum(row["label"] == "1" for row in rows))
    if counts != (total, normal, anomalous) or len({row["sample"] for row in rows}) != total:
        raise ValueError(f"Frozen manifest cohort mismatch: {counts}")
    return rows


def bootstrap(deltas: np.ndarray) -> dict:
    if deltas.size == 0 or not np.isfinite(deltas).all():
        raise ValueError("Paired AU-PRO deltas must be nonempty and finite")
    return {**_bootstrap_mean_delta(deltas, 5000, np.random.default_rng(2026)), "repeats": 5000, "seed": 2026, "estimand": "mean paired anomalous-image AU-PRO delta, ESRGAN minus PSNR"}


def wilson(count: int, total: int) -> tuple[float, float]:
    if not 0 <= count <= total or total == 0:
        raise ValueError("Wilson interval requires 0 <= count <= positive total")
    z = 1.959963984540054
    p = count / total
    divisor = 1 + z * z / total
    center = (p + z * z / (2 * total)) / divisor
    half = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / divisor
    return center - half, center + half


def magnitude(deltas: np.ndarray, tau: float) -> tuple[int, float]:
    if deltas.size == 0 or not np.isfinite(deltas).all():
        raise ValueError("Magnitude sensitivity requires finite deltas")
    count = int(np.sum(deltas < -tau))
    return count, count / int(deltas.size)


def sign_summary(deltas: np.ndarray) -> dict:
    if deltas.size == 0 or not np.isfinite(deltas).all():
        raise ValueError("Endpoint summary requires finite deltas")
    return {
        "count": int(deltas.size), "mean": float(deltas.mean()), "median": float(np.median(deltas)),
        "min": float(deltas.min()), "max": float(deltas.max()),
        "esrgan_wins": int(np.sum(deltas > 0)), "psnr_wins": int(np.sum(deltas < 0)), "ties": int(np.sum(deltas == 0)),
    }


def delta_distribution(deltas: np.ndarray) -> dict:
    if deltas.size == 0 or not np.isfinite(deltas).all():
        raise ValueError("Delta distribution requires finite nonempty values")
    quantiles = np.quantile(deltas, [0, 0.25, 0.5, 0.75, 1])
    near_zero = int(np.sum(np.abs(deltas) <= 0.01))
    return {**dict(zip(("minimum", "q25", "median", "q75", "maximum"), map(float, quantiles))),
            "anomaly_count": int(deltas.size), "absolute_delta_le_0_01_count": near_zero,
            "absolute_delta_le_0_01_rate": near_zero / int(deltas.size)}


def classify_case(pooled_delta: float, mean_delta: float, ci: tuple[float, float], unseen_mean: float) -> str:
    if pooled_delta > 0 and mean_delta > 0 and ci[0] > 0 and unseen_mean > 0:
        return "A"
    if pooled_delta < 0 and mean_delta < 0 and ci[1] < 0 and unseen_mean < 0:
        return "C"
    return "B"


def b_description(ci: tuple[float, float]) -> str:
    return "B-small" if ci[0] >= -0.01 and ci[1] <= 0.01 else "B-uncertain"


def partition_test_images(full: set[str], pilot: set[str]) -> set[str]:
    unseen = full - pilot
    if not pilot <= full or (len(full), len(pilot), len(unseen)) != (110, 25, 85):
        raise ValueError("Full/pilot test-image split is not 110/25/85")
    return unseen


def baseline_terciles(baseline: dict[str, float]) -> list[tuple[str, list[str]]]:
    ordered = sorted(baseline, key=lambda sample: (baseline[sample], sample))
    size = len(ordered) // 3
    return [("low", ordered[:size]), ("middle", ordered[size:2 * size]), ("high", ordered[2 * size:])]


def taxonomy_contingency(base_rates: list[dict]) -> dict:
    regression, non_regression = base_rates
    return {"variant": regression["variant"],
            "regression_gap_negative": regression["negative_gap_count"],
            "regression_gap_nonnegative": regression["count"] - regression["negative_gap_count"],
            "non_regression_gap_negative": non_regression["negative_gap_count"],
            "non_regression_gap_nonnegative": non_regression["count"] - non_regression["negative_gap_count"]}


def evaluate_unseen_predictions(run_dir: Path, manifest: list[dict], unseen: set[str], per_image: dict) -> list[dict]:
    """Reuse stored maps in manifest order, with paired-array and score-order guards."""
    indices = [i for i, row in enumerate(manifest) if row["sample"] in unseen]
    expected_labels = np.asarray([int(row["label"]) for row in manifest])
    reference_masks = None
    rows = []
    for variant in VARIANTS:
        with np.load(run_dir / f"{variant}_predictions.npz", allow_pickle=False) as data:
            labels, scores, masks, maps = (data[key] for key in ("labels", "scores", "masks", "maps"))
            if (not np.array_equal(labels, expected_labels) or scores.shape != labels.shape
                    or masks.ndim != 3 or maps.shape != masks.shape or maps.shape[0] != len(manifest)
                    or not np.isfinite(scores).all() or not np.isfinite(maps).all()
                    or not np.isin(masks, [0, 1]).all()):
                raise ValueError(f"Invalid saved prediction arrays: {variant}")
            if reference_masks is not None and not np.array_equal(masks, reference_masks):
                raise ValueError(f"Unpaired saved masks: {variant}")
            reference_masks = masks.copy()
            expected_scores = [_number(per_image[(row["sample"], variant)], "image_score") for row in manifest]
            if not np.allclose(scores, expected_scores, atol=1e-5, rtol=1e-5):
                raise ValueError(f"NPZ scores do not match manifest-ordered per_image.csv: {variant}")
            evaluation = evaluate_predictions(labels[indices], scores[indices], masks[indices], maps[indices])
        rows.append({"subset": "pilot-unseen85 within-category subset", "variant": variant,
                     "test_count": len(indices), "normal_count": int(np.sum(expected_labels[indices] == 0)),
                     "anomaly_count": int(np.sum(expected_labels[indices] == 1)),
                     "pooled_au_pro": evaluation["localization"]["au_pro"],
                     "pixel_auroc": evaluation["localization"]["pixel_auroc"],
                     "image_auroc": evaluation["classification"]["image_auroc"]})
    return rows


def partition_anomalies(full: set[str], pilot: set[str], *, expected: bool = False) -> tuple[set[str], set[str]]:
    overlap, unseen = full & pilot, full - pilot
    if expected and (len(full), len(overlap), len(unseen)) != (70, 20, 50):
        raise ValueError("Full/pilot anomalous-image split is not 70/20/50")
    return overlap, unseen


def taxonomy_base_rates(rows: list[dict[str, str]], variant: str) -> list[dict]:
    subset = [row for row in rows if row["variant"] == variant]
    result = []
    for regression in (True, False):
        group = [row for row in subset if (_number(row, "delta_per_image_aupro") < 0) == regression]
        negative = sum(_number(row, "delta_roi_bg_gap") < 0 for row in group)
        result.append({"variant": variant, "group": "regression" if regression else "non_regression", "count": len(group),
                       "negative_gap_count": negative, "negative_gap_rate": negative / len(group) if group else None})
    return result


def overlap_check(current: dict[tuple[str, str], dict[str, str]], reference: dict[tuple[str, str], dict[str, str]], samples: set[str]) -> dict:
    mismatches = []
    max_abs = 0.0
    compared = 0
    for sample in sorted(samples):
        for variant in VARIANTS:
            for field in COMPARE_FIELDS:
                left, right = _number(current[(sample, variant)], field), _number(reference[(sample, variant)], field)
                difference = abs(left - right)
                max_abs = max(max_abs, difference)
                compared += 1
                if not np.isclose(left, right, atol=1e-5, rtol=1e-5):
                    mismatches.append({"sample": sample, "variant": variant, "field": field, "absolute_difference": difference})
    return {"samples": len(samples), "compared_values": compared, "atol": 1e-5, "rtol": 1e-5,
            "max_absolute_difference": max_abs, "mismatch_count": len(mismatches), "passed": not mismatches,
            "mismatch_examples": mismatches[:10]}


def analyze(run_dir: Path) -> tuple[dict, dict, dict[str, list[dict]], dict]:
    result = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    study = result.get("study")
    if study not in MANIFESTS:
        raise ValueError("Input is not a frozen Hazelnut restoration-endpoint run")
    manifest = _manifest(study)
    expected_hash = MANIFESTS[study][1]
    if result.get("manifest_sha256") != expected_hash or result.get("sample_count") != len(manifest):
        raise ValueError("Run manifest hash or sample count differs from frozen cohort")
    samples = {row["sample"]: row for row in manifest}
    summary = _unique(_read_csv(run_dir / "summary.csv", ("variant", "test_count", "normal_count", "anomaly_count", "mean_psnr", "mean_lpips", "au_pro")), ("variant",))
    per_image = _unique(_read_csv(run_dir / "per_image.csv", ("sample", "variant", "label", "defect_type", *COMPARE_FIELDS)), ("sample", "variant"))
    taxonomy_rows = _read_csv(run_dir / "regression_taxonomy.csv", ("sample", "variant", "regression_type", "delta_per_image_aupro", "delta_roi_bg_gap"))
    taxonomy = _unique(taxonomy_rows, ("sample", "variant"))
    pair = _unique(_read_csv(run_dir / "objective_pair_per_image.csv", ("sample", "label", "delta_per_image_aupro_esrgan_minus_psnr")), ("sample",))
    anomalous = [row["sample"] for row in manifest if row["label"] == "1"]
    expected_per = {(sample, variant) for sample in samples for variant in VARIANTS}
    expected_tax = {(sample, variant) for sample in anomalous for variant in LEARNED}
    if set(summary) != {(name,) for name in VARIANTS} or set(per_image) != expected_per or set(taxonomy) != expected_tax or set(pair) != {(sample,) for sample in samples}:
        raise ValueError("Saved CSV rows are missing, duplicated, or outside the frozen cohort")
    for (sample, variant), row in per_image.items():
        original = samples[sample]
        if row["label"] != original["label"] or row["defect_type"] != original["defect_type"]:
            raise ValueError(f"Per-image label/defect mismatch: {sample}")
    for sample in anomalous:
        gan = per_image[(sample, "rrdb_esrgan_x4")]
        psnr = per_image[(sample, "rrdb_psnr_x4")]
        direct = _number(gan, "per_image_aupro") - _number(psnr, "per_image_aupro")
        if not np.isclose(direct, _number(pair[(sample,)], "delta_per_image_aupro_esrgan_minus_psnr"), atol=1e-10, rtol=1e-10):
            raise ValueError(f"Direct endpoint CSV disagrees with per_image.csv: {sample}")
        for variant in LEARNED:
            item = taxonomy[(sample, variant)]
            delta = _number(per_image[(sample, variant)], "per_image_aupro") - _number(per_image[(sample, "bicubic_x4")], "per_image_aupro")
            gap = _number(per_image[(sample, variant)], "roi_bg_gap") - _number(per_image[(sample, "bicubic_x4")], "roi_bg_gap")
            expected_type = "improvement_or_tie" if delta >= 0 else "suppression" if gap < 0 else "geometry_candidate"
            if item["regression_type"] != expected_type or not np.isclose(delta, _number(item, "delta_per_image_aupro"), atol=1e-10) or not np.isclose(gap, _number(item, "delta_roi_bg_gap"), atol=1e-10):
                raise ValueError(f"Taxonomy CSV disagrees with per_image.csv: {sample} {variant}")
    for variant in VARIANTS:
        row = summary[(variant,)]
        if (int(row["test_count"]), int(row["normal_count"]), int(row["anomaly_count"])) != MANIFESTS[study][2:]:
            raise ValueError(f"Summary cohort counts changed: {variant}")
        for metric in ("au_pro", "mean_psnr", "mean_lpips"):
            if not np.isclose(_number(row, metric), result["variants"][variant][metric], atol=1e-10):
                raise ValueError(f"Summary/results {metric} mismatch: {variant}")

    direct = np.asarray([_number(pair[(sample,)], "delta_per_image_aupro_esrgan_minus_psnr") for sample in anomalous])
    boot = bootstrap(direct)
    psnr_delta = _number(summary[("rrdb_esrgan_x4",)], "mean_psnr") - _number(summary[("rrdb_psnr_x4",)], "mean_psnr")
    lpips_delta = _number(summary[("rrdb_esrgan_x4",)], "mean_lpips") - _number(summary[("rrdb_psnr_x4",)], "mean_lpips")
    pooled_delta = _number(summary[("rrdb_esrgan_x4",)], "au_pro") - _number(summary[("rrdb_psnr_x4",)], "au_pro")
    full = study == "restoration_objective_full"
    pilot_manifest = _manifest("restoration_objective_pilot")
    pilot_anomalies = {row["sample"] for row in pilot_manifest if row["label"] == "1"}
    overlap, unseen = partition_anomalies(set(anomalous), pilot_anomalies, expected=full) if full else (set(anomalous), set())
    overlap_result = None
    unseen_summary = None
    unseen_confirmation = []
    if full:
        pilot_rows = _unique(_read_csv(PILOT_RESULTS / "per_image.csv", ("sample", "variant", *COMPARE_FIELDS)), ("sample", "variant"))
        overlap_result = overlap_check(per_image, pilot_rows, overlap)
        unseen_summary = sign_summary(np.asarray([_number(pair[(sample,)], "delta_per_image_aupro_esrgan_minus_psnr") for sample in sorted(unseen)]))
        unseen_all = partition_test_images(set(samples), {row["sample"] for row in pilot_manifest})
        if (sum(samples[path]["label"] == "0" for path in unseen_all), sum(samples[path]["label"] == "1" for path in unseen_all)) != (35, 50):
            raise ValueError("Pilot-unseen85 must contain 35 normal and 50 anomalous images")
        unseen_confirmation = evaluate_unseen_predictions(run_dir, manifest, unseen_all, per_image)

    tables: dict[str, list[dict]] = {name: [] for name in ("regression_intervals", "magnitude_sensitivity", "endpoint_pair_sensitivity", "taxonomy_base_rates", "taxonomy_contingency", "localization_delta_distribution", "baseline_tercile_regression", "quality_localization")}
    if full:
        tables["pilot_unseen_confirmation"] = unseen_confirmation
    spearman = {}
    baseline_association = {}
    baseline_values = {sample: _number(per_image[(sample, "bicubic_x4")], "per_image_aupro") for sample in anomalous}
    for variant in LEARNED:
        variant_tax = [taxonomy[(sample, variant)] for sample in anomalous]
        deltas = np.asarray([_number(row, "delta_per_image_aupro") for row in variant_tax])
        regressions = int(np.sum(deltas < 0))
        lower, upper = wilson(regressions, len(anomalous))
        tables["regression_intervals"].append({"variant": variant, "regression_count": regressions, "anomaly_count": len(anomalous), "rate": regressions / len(anomalous), "wilson95_lower": lower, "wilson95_upper": upper})
        for tau in TAUS:
            count, rate = magnitude(deltas, tau)
            tables["magnitude_sensitivity"].append({"variant": variant, "tau": tau, "count_delta_lt_minus_tau": count, "rate_delta_lt_minus_tau": rate, "anomaly_count": len(anomalous)})
        base_rates = taxonomy_base_rates(variant_tax, variant)
        tables["taxonomy_base_rates"].extend(base_rates)
        tables["taxonomy_contingency"].append(taxonomy_contingency(base_rates))
        tables["localization_delta_distribution"].append({"variant": variant, **delta_distribution(deltas)})
        delta_by_sample = {sample: _number(taxonomy[(sample, variant)], "delta_per_image_aupro") for sample in anomalous}
        baseline_association[variant] = _spearman(np.asarray([baseline_values[sample] for sample in anomalous]), deltas)
        for group, paths in baseline_terciles(baseline_values):
            group_deltas = np.asarray([delta_by_sample[sample] for sample in paths])
            strict_count, strict_rate = magnitude(group_deltas, 0)
            loss_count, loss_rate = magnitude(group_deltas, 0.01)
            tables["baseline_tercile_regression"].append({"variant": variant, "baseline_group": group, "image_count": len(paths),
                "mean_bicubic_per_image_aupro": float(np.mean([baseline_values[sample] for sample in paths])),
                "mean_delta_per_image_aupro": float(group_deltas.mean()), "strict_regression_count": strict_count,
                "strict_regression_rate": strict_rate, "delta_lt_minus_0_01_count": loss_count, "delta_lt_minus_0_01_rate": loss_rate})
        quality = []
        for sample in anomalous:
            baseline, restored = per_image[(sample, "bicubic_x4")], per_image[(sample, variant)]
            quality.append({"sample": sample, "defect_type": samples[sample]["defect_type"], "variant": variant,
                            "pilot_overlap": sample in overlap,
                            "psnr_gain_vs_bicubic": _number(restored, "psnr") - _number(baseline, "psnr"),
                            "lpips_improvement_vs_bicubic": _number(baseline, "lpips") - _number(restored, "lpips"),
                            "delta_per_image_aupro_vs_bicubic": _number(restored, "per_image_aupro") - _number(baseline, "per_image_aupro")})
        tables["quality_localization"].extend(quality)
        y = np.asarray([row["delta_per_image_aupro_vs_bicubic"] for row in quality])
        spearman[variant] = {axis: _spearman(np.asarray([row[axis] for row in quality]), y) for axis in ("psnr_gain_vs_bicubic", "lpips_improvement_vs_bicubic")}
    for name, selected in (("all_anomalies", anomalous), ("pilot_unseen_within_category", sorted(unseen))):
        if not selected:
            continue
        values = np.asarray([_number(pair[(sample,)], "delta_per_image_aupro_esrgan_minus_psnr") for sample in selected])
        for tau in TAUS:
            tables["endpoint_pair_sensitivity"].append({"subset": name, "tau": tau, "esrgan_delta_gt_tau": int(np.sum(values > tau)),
                                                        "psnr_delta_lt_minus_tau": int(np.sum(values < -tau)), "within_band": int(np.sum(np.abs(values) <= tau)), "anomaly_count": len(values)})
    localization_case = classify_case(pooled_delta, float(direct.mean()), tuple(boot["ci95"]), unseen_summary["mean"]) if full else None
    analysis = {"study": study, "source_run": str(run_dir), "manifest_sha256": expected_hash, "anomalous_images": len(anomalous),
                "primary_metric": "pooled AU-PRO@0.3", "pooled_delta_aupro_esrgan_minus_psnr": pooled_delta,
                "mean_delta_psnr_esrgan_minus_psnr": psnr_delta, "mean_delta_lpips_esrgan_minus_psnr": lpips_delta,
                "quality_tradeoff_reproduced": psnr_delta < 0 and lpips_delta < 0,
                "direct_per_image_aupro": sign_summary(direct),
                "localization_case": localization_case,
                "localization_b_description": b_description(tuple(boot["ci95"])) if localization_case == "B" else None,
                "pilot_overlap_reproducibility": overlap_result, "pilot_unseen_within_category": unseen_summary,
                "pilot_unseen85": {"variants": unseen_confirmation,
                    "pooled_delta_aupro_esrgan_minus_psnr": unseen_confirmation[3]["pooled_au_pro"] - unseen_confirmation[2]["pooled_au_pro"]} if full else None,
                "aggregate_methods": [summary[(variant,)] for variant in VARIANTS],
                "localization_delta_distribution": tables["localization_delta_distribution"],
                "baseline_aupro_vs_delta_spearman_descriptive": baseline_association,
                "reporting_order": ["aggregate quality/detection", "per-image delta distribution", "magnitude sensitivity", "baseline diagnostic", "quality/localization association", "supporting taxonomy"],
                "pooled_uncertainty_note": "Pooled AU-PRO is a point estimate; paired bootstrap covers the mean anomalous-image AU-PRO difference, not pooled AU-PRO.",
                "spearman_descriptive": spearman,
                "sensitivity_status": "pre-registered before full110 inference" if full else "pilot validation; post-hoc sensitivity, not a revised pilot decision"}
    plot_data = {"pair": [(sample, samples[sample]["defect_type"], _number(pair[(sample,)], "delta_per_image_aupro_esrgan_minus_psnr")) for sample in anomalous]}
    return analysis, boot, tables, plot_data


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _figures(output: Path, tables: dict[str, list[dict]], plot_data: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    defects = sorted({item[1] for item in plot_data["pair"]})
    colors = {name: plt.get_cmap("tab10")(i) for i, name in enumerate(defects)}
    sorted_pair = sorted(plot_data["pair"], key=lambda item: (item[2], item[0]))
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.bar(range(len(sorted_pair)), [item[2] for item in sorted_pair], color=[colors[item[1]] for item in sorted_pair], width=0.9)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(xlabel="Anomalous images, sorted by direct endpoint delta", ylabel="ESRGAN - PSNR per-image AU-PRO@0.3")
    for defect in defects:
        ax.bar([], [], color=colors[defect], label=defect)
    ax.legend(ncol=len(defects), fontsize=8)
    fig.tight_layout()
    fig.savefig(output / "per_image_aupro_waterfall.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for variant in LEARNED:
        rows = [row for row in tables["magnitude_sensitivity"] if row["variant"] == variant]
        ax.plot([row["tau"] for row in rows], [row["count_delta_lt_minus_tau"] for row in rows], marker="o", label=variant)
    ax.set(xlabel="tau", ylabel="Count: AU-PRO delta vs Bicubic < -tau", xticks=TAUS)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output / "regression_sensitivity.png", dpi=160)
    plt.close(fig)

    for field, name, xlabel in (("psnr_gain_vs_bicubic", "quality_localization_psnr.png", "PSNR gain vs Bicubic (dB)"),
                               ("lpips_improvement_vs_bicubic", "quality_localization_lpips.png", "LPIPS improvement vs Bicubic")):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
        for ax, variant in zip(axes, LEARNED):
            for defect in defects:
                rows = [row for row in tables["quality_localization"] if row["variant"] == variant and row["defect_type"] == defect]
                ax.scatter([row[field] for row in rows], [row["delta_per_image_aupro_vs_bicubic"] for row in rows], s=16, color=colors[defect], label=defect)
            ax.axhline(0, color="black", linewidth=0.8)
            ax.set(title=variant, xlabel=xlabel)
        axes[0].set_ylabel("Per-image AU-PRO delta vs Bicubic")
        axes[-1].legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(output / name, dpi=160)
        plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="Completed frozen pilot25 or full110 runner output")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Analysis output directory is not empty: {output}")
    analysis, boot, tables, plot_data = analyze(args.run_dir.resolve())
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis_summary.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "endpoint_bootstrap.json").write_text(json.dumps(boot, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, rows in tables.items():
        _write_csv(output / f"{name}.csv", rows)
    _figures(output, tables, plot_data)
    print(json.dumps({"study": analysis["study"], "output": str(output), "direct_per_image_aupro": analysis["direct_per_image_aupro"],
                      "localization_case": analysis["localization_case"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
