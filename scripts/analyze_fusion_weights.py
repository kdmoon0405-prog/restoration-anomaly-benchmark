"""Five fixed scalar fusion weights on saved Branch B predictions; no model inference."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.evaluation import area_under_per_region_overlap, evaluate_predictions


ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
ANCHORS = {0.0: "restored_only", 0.5: "mean_0.5_0.5", 1.0: "degraded_only"}
METRICS = ("pooled_au_pro", "pixel_auroc", "image_auroc")


def _load_prediction(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        required = {"labels", "scores", "masks", "maps"}
        if required - set(archive.files):
            raise ValueError(f"{path} is missing {sorted(required - set(archive.files))}")
        return {key: archive[key] for key in required}


def _metrics(evaluation: dict) -> dict[str, float]:
    return {
        "pooled_au_pro": float(evaluation["localization"]["au_pro"]),
        "pixel_auroc": float(evaluation["localization"]["pixel_auroc"]),
        "image_auroc": float(evaluation["classification"]["image_auroc"]),
    }


def _per_image_aupro(mask: np.ndarray, anomaly_map: np.ndarray) -> float:
    return area_under_per_region_overlap(mask[None, ...], anomaly_map[None, ...],
                                         max_fpr=0.3, num_thresholds=200)


def _anchor_check(alpha: float, scores: np.ndarray, maps: np.ndarray, metrics: dict[str, float],
                  saved: dict[str, np.ndarray], recorded: dict) -> dict:
    score_diff = float(np.max(np.abs(scores - saved["scores"])))
    map_diff = float(np.max(np.abs(maps - saved["maps"])))
    recorded_metrics = _metrics(recorded)
    metric_diff = max(abs(metrics[key] - recorded_metrics[key]) for key in METRICS)
    if (not np.allclose(scores, saved["scores"], rtol=1e-10, atol=1e-9)
            or not np.allclose(maps, saved["maps"], rtol=1e-10, atol=1e-9)
            or any(not np.isclose(metrics[key], recorded_metrics[key], rtol=1e-10, atol=1e-9) for key in METRICS)):
        raise ValueError(f"alpha={alpha:.2f} anchor mismatch against saved {ANCHORS[alpha]} predictions/evaluation")
    return {"alpha": alpha, "method": ANCHORS[alpha], "passed": True,
            "max_abs_score_diff": score_diff, "max_abs_map_diff": map_diff,
            "max_abs_metric_diff": float(metric_diff)}


def analyze_predictions(predictions: dict[str, dict[str, np.ndarray]], recorded: dict,
                        test_paths: list[str]) -> tuple[list[dict], list[dict], dict[str, dict]]:
    """Evaluate the pre-fixed grid, preserving only small result rows in memory."""
    required = {"degraded_only", "restored_only", "mean_0.5_0.5"}
    if not required <= set(predictions) or not required <= set(recorded):
        raise ValueError("Missing saved Branch B anchor predictions or evaluations")
    degraded, restored = predictions["degraded_only"], predictions["restored_only"]
    labels = np.asarray(degraded["labels"])
    masks = np.asarray(degraded["masks"])
    if labels.ndim != 1 or masks.ndim != 3 or len(labels) != len(test_paths) or masks.shape[0] != len(labels):
        raise ValueError("Test paths, labels, and [N,H,W] masks must align")
    if not np.isin(labels, [0, 1]).all() or not np.any(labels == 0) or not np.any(labels == 1):
        raise ValueError("Both normal and anomalous image labels are required")
    if np.any(masks[labels == 0]):
        raise ValueError("Normal test images must have empty GT masks")
    for name in required:
        item = predictions[name]
        if (not np.array_equal(item["labels"], labels) or not np.array_equal(item["masks"], masks)
                or item["scores"].shape != labels.shape or item["maps"].shape != masks.shape
                or not np.isfinite(item["scores"]).all() or not np.isfinite(item["maps"]).all()):
            raise ValueError(f"{name} predictions are unpaired, misshaped, or non-finite")

    anomalous = np.flatnonzero(labels == 1)
    baseline_aupro = {}
    baseline_gap = {}
    for index in anomalous:
        mask = masks[index].astype(bool)
        if not mask.any() or mask.all():
            raise ValueError(f"Anomalous image has an empty or full mask: {test_paths[index]}")
        anomaly_map = degraded["maps"][index]
        baseline_aupro[index] = _per_image_aupro(mask, anomaly_map)
        baseline_gap[index] = float(anomaly_map[mask].mean() - anomaly_map[~mask].mean())

    summary_rows: list[dict] = []
    per_image_rows: list[dict] = []
    anchor_checks: dict[str, dict] = {}
    restored_metrics = _metrics(recorded["restored_only"])
    for alpha in ALPHAS:
        scores = alpha * degraded["scores"] + (1.0 - alpha) * restored["scores"]
        maps = alpha * degraded["maps"] + (1.0 - alpha) * restored["maps"]
        metrics = _metrics(evaluate_predictions(labels, scores, masks, maps))  # no F1 threshold
        if alpha in ANCHORS:
            name = ANCHORS[alpha]
            anchor_checks[f"{alpha:.2f}"] = _anchor_check(alpha, scores, maps, metrics,
                                                           predictions[name], recorded[name])
        deltas = []
        types = {"suppression": 0, "geometry_candidate": 0}
        for index in anomalous:
            mask = masks[index].astype(bool)
            anomaly_map = maps[index]
            aupro = baseline_aupro[index] if alpha == 1.0 else _per_image_aupro(mask, anomaly_map)
            gap = baseline_gap[index] if alpha == 1.0 else float(anomaly_map[mask].mean() - anomaly_map[~mask].mean())
            delta_aupro = aupro - baseline_aupro[index]
            delta_gap = gap - baseline_gap[index]
            regression_type = ("improvement_or_tie" if delta_aupro >= 0 else
                               "suppression" if delta_gap < 0 else "geometry_candidate")
            if regression_type in types:
                types[regression_type] += 1
            deltas.append(delta_aupro)
            per_image_rows.append({"sample": test_paths[index], "defect_type": Path(test_paths[index]).parts[-2],
                                   "alpha": alpha, "per_image_aupro": float(aupro),
                                   "delta_aupro_vs_bicubic": float(delta_aupro), "roi_bg_gap": gap,
                                   "delta_gap_vs_bicubic": float(delta_gap), "regression_type": regression_type})
        deltas_array = np.asarray(deltas, dtype=np.float64)
        aupro_array = np.asarray([row["per_image_aupro"] for row in per_image_rows[-len(anomalous):]])
        summary_rows.append({
            "alpha": alpha, **metrics,
            "mean_per_image_aupro": float(aupro_array.mean()),
            "median_per_image_aupro": float(np.median(aupro_array)),
            "delta_pooled_au_pro_vs_restored": metrics["pooled_au_pro"] - restored_metrics["pooled_au_pro"],
            "delta_pixel_auroc_vs_restored": metrics["pixel_auroc"] - restored_metrics["pixel_auroc"],
            "localization_regression_count_vs_bicubic": types["suppression"] + types["geometry_candidate"],
            "suppression_type_regression_count_vs_bicubic": types["suppression"],
            "geometry_candidate_regression_count_vs_bicubic": types["geometry_candidate"],
            "mean_delta_per_image_aupro_vs_bicubic": float(deltas_array.mean()),
            "median_delta_per_image_aupro_vs_bicubic": float(np.median(deltas_array)),
            "worst10_mean_delta_per_image_aupro_vs_bicubic": float(np.sort(deltas_array)[:10].mean()),
            "minimum_delta_per_image_aupro_vs_bicubic": float(deltas_array.min()),
        })
    return summary_rows, per_image_rows, anchor_checks


def _write_plots(rows: list[dict], output_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    alphas = [row["alpha"] for row in rows]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(alphas, [row["pooled_au_pro"] for row in rows], marker="o")
    ax.set(xlabel="Bicubic weight alpha", ylabel="Pooled AU-PRO@0.3")
    fig.tight_layout()
    fig.savefig(output_dir / "alpha_vs_pooled_au_pro.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
    axes[0].plot(alphas, [row["worst10_mean_delta_per_image_aupro_vs_bicubic"] for row in rows], marker="o")
    axes[0].set_ylabel("Worst-10 mean ΔAU-PRO vs Bicubic")
    axes[1].plot(alphas, [row["localization_regression_count_vs_bicubic"] for row in rows], marker="o")
    axes[1].set(xlabel="Bicubic weight alpha", ylabel="Regression count vs Bicubic")
    fig.tight_layout()
    fig.savefig(output_dir / "alpha_vs_regression_risk.png", dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "outputs" / "fusion-patchcore" / "hazelnut-313x78-test110")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis" / "hazelnut" / "fusion_weight_search")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve()
    result = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    split = json.loads((run_dir / "split.json").read_text(encoding="utf-8"))
    spec = result["model_spec"]
    if (spec["category"] != "hazelnut" or spec["seed"] != 11 or spec["source_commit"] != "fcaa92f124fb1ad74a7acf56726decd4b27cbcad"
            or len(spec["train_paths"]) != 313 or len(spec["calibration_paths"]) != 78
            or len(result["test_paths"]) != 110 or split["train_paths"] != spec["train_paths"]
            or split["calibration_paths"] != spec["calibration_paths"]
            or result["fusion_calibration"]["normalization"] != "robust_median_iqr_per_variant"):
        raise ValueError("Expected the pinned hazelnut Branch B 313/78/110 seed-11 run")
    predictions = {name: _load_prediction(run_dir / f"{name}_predictions.npz") for name in
                   ("degraded_only", "restored_only", "mean_0.5_0.5")}
    recorded = {name: result["methods"][name]["evaluation"] for name in predictions}
    rows, per_image_rows, anchors = analyze_predictions(predictions, recorded, result["test_paths"])
    best = max(rows, key=lambda row: (row["pooled_au_pro"], -row["alpha"]))
    interior_best = max(rows[1:-1], key=lambda row: (row["pooled_au_pro"], -row["alpha"]))
    endpoint_best = max(rows[0]["pooled_au_pro"], rows[-1]["pooled_au_pro"])
    source_run = run_dir.relative_to(ROOT).as_posix() if run_dir.is_relative_to(ROOT) else str(run_dir)
    output = {
        "source_run": source_run,
        "fixed_alpha_grid": list(ALPHAS),
        "alpha_definition": "alpha * degraded + (1 - alpha) * restored, for scores and maps",
        "primary_metric": "dataset-level pooled AU-PRO@0.3 (200 thresholds)",
        "selection_rule": "maximize primary metric; exact tie chooses smaller alpha",
        "hazelnut_role": "development/feasibility, not untouched validation",
        "best_alpha": best["alpha"],
        "best_pooled_au_pro": best["pooled_au_pro"],
        "best_delta_pooled_au_pro_vs_restored": best["delta_pooled_au_pro_vs_restored"],
        "anchor_validation": anchors,
        "summary": rows,
        "fine_search_decision": {
            "automatic_search_run": False,
            "interior_best_alpha": interior_best["alpha"],
            "interior_best_pooled_au_pro": interior_best["pooled_au_pro"],
            "interior_best_delta_vs_restored": interior_best["delta_pooled_au_pro_vs_restored"],
            "interior_exceeds_both_endpoints": interior_best["pooled_au_pro"] > endpoint_best,
            "note": "Consider a separately specified fine search only if an interior coarse alpha improves primary pooled AU-PRO over both endpoints, with defect-risk magnitudes reviewed; Hazelnut is development data.",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "fusion_weight_search.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "fusion_weight_per_image.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=per_image_rows[0].keys())
        writer.writeheader()
        writer.writerows(per_image_rows)
    (output_dir / "fusion_weight_search.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    table = "\n".join(f"| {row['alpha']:.2f} | {row['pooled_au_pro']:.6f} | {row['delta_pooled_au_pro_vs_restored']:+.6f} | "
                      f"{row['pixel_auroc']:.6f} | {row['localization_regression_count_vs_bicubic']} | "
                      f"{row['worst10_mean_delta_per_image_aupro_vs_bicubic']:+.6f} |" for row in rows)
    summary = ("# Five-point scalar fusion feasibility ablation\n\n"
               f"Source: `{source_run}`. Hazelnut is development data; this is not an unbiased final test.\n\n"
               "Alpha weights Bicubic/degraded. Fixed grid: 0.00, 0.25, 0.50, 0.75, 1.00. "
               "Selection uses pooled AU-PRO@0.3 only; F1 and new thresholds were not computed.\n\n"
               "| Alpha | Pooled AU-PRO | Δ vs restored | Pixel AUROC | Regressions vs Bicubic | Worst-10 mean ΔAU-PRO |\n"
               "| ---: | ---: | ---: | ---: | ---: | ---: |\n" + table + "\n\n"
               f"Best coarse alpha: **{best['alpha']:.2f}**, pooled AU-PRO {best['pooled_au_pro']:.6f} "
               f"(Δ vs restored {best['delta_pooled_au_pro_vs_restored']:+.6f}).\n\n"
               f"Best interior alpha: {interior_best['alpha']:.2f}, pooled AU-PRO {interior_best['pooled_au_pro']:.6f} "
               f"(Δ vs restored {interior_best['delta_pooled_au_pro_vs_restored']:+.6f}); "
               f"exceeds both endpoints: {interior_best['pooled_au_pro'] > endpoint_best}.\n\n"
               "Anchor checks (0/0.5/1): passed against saved predictions and evaluations. "
               "Regression counts are risk descriptors; alpha=1 has zero by definition. "
               "No fine search or adaptive gating was run.\n")
    (output_dir / "fusion_weight_search.md").write_text(summary, encoding="utf-8")
    _write_plots(rows, output_dir)
    print(json.dumps({"output": str(output_dir), "best_alpha": best["alpha"],
                      "best_pooled_au_pro": best["pooled_au_pro"], "anchors": anchors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
