"""Apply the frozen Hazelnut regression taxonomy to a saved full category run."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_hazelnut_failures import (
    _bootstrap_mean_delta,
    _defect_type,
    _load_npz,
    _per_image_pixel_metrics,
    _regression_type,
)


VARIANTS = ("clean", "bicubic_x4", "swinir_x4")
CASES_PER_GROUP = 3
CASE_FIELDS = (
    "sample", "defect_type", "regression_type", "delta_per_image_aupro",
    "delta_per_image_pixel_auroc", "delta_roi_mean", "delta_roi_bg_gap", "defect_area_ratio",
)


def validate_predictions(predictions: dict[str, dict[str, np.ndarray]], test_paths: list[str]) -> None:
    if set(predictions) != set(VARIANTS):
        raise ValueError(f"Required predictions are {VARIANTS}")
    n = len(test_paths)
    if n == 0 or len(set(test_paths)) != n:
        raise ValueError("results.json test_paths must be nonempty and unique")
    reference = predictions["clean"]
    labels = np.asarray(reference["labels"])
    masks = np.asarray(reference["masks"])
    if labels.shape != (n,) or masks.ndim != 3 or masks.shape[0] != n:
        raise ValueError("Prediction labels/masks do not align with test_paths")
    if not np.isin(labels, [0, 1]).all() or not np.any(labels == 1):
        raise ValueError("Predictions require binary labels and anomalous images")
    if np.any(masks[labels == 0]):
        raise ValueError("Normal test images must have empty masks")
    for name, item in predictions.items():
        scores = np.asarray(item["scores"])
        maps = np.asarray(item["maps"])
        if (not np.array_equal(item["labels"], labels) or not np.array_equal(item["masks"], masks)
                or scores.shape != (n,) or maps.shape != masks.shape
                or not np.isfinite(scores).all() or not np.isfinite(maps).all()):
            raise ValueError(f"{name} predictions are unpaired, misshaped, or non-finite")


def analyze_predictions(predictions: dict[str, dict[str, np.ndarray]], test_paths: list[str]) -> list[dict]:
    validate_predictions(predictions, test_paths)
    bic = predictions["bicubic_x4"]
    swin = predictions["swinir_x4"]
    rows = []
    for index, (sample, label) in enumerate(zip(test_paths, bic["labels"])):
        if int(label) != 1:
            continue
        mask = np.asarray(bic["masks"][index], dtype=bool)
        if not mask.any() or mask.all():
            raise ValueError(f"Anomalous image requires both ROI and background pixels: {sample}")
        bic_map = np.asarray(bic["maps"][index], dtype=np.float64)
        swin_map = np.asarray(swin["maps"][index], dtype=np.float64)
        background = ~mask
        bic_roi = float(bic_map[mask].mean())
        swin_roi = float(swin_map[mask].mean())
        bic_bg = float(bic_map[background].mean())
        swin_bg = float(swin_map[background].mean())
        bic_auc, swin_auc, bic_aupro, swin_aupro = _per_image_pixel_metrics(mask, bic_map, swin_map)
        delta_gap = (swin_roi - swin_bg) - (bic_roi - bic_bg)
        delta_aupro = swin_aupro - bic_aupro
        correlation = (float(np.corrcoef(bic_map.ravel(), swin_map.ravel())[0, 1])
                       if np.std(bic_map) > 0 and np.std(swin_map) > 0 else None)
        area = int(mask.sum())
        rows.append({
            "index": index,
            "sample": sample,
            "defect_type": _defect_type(sample),
            "defect_area_pixels": area,
            "defect_area_ratio": float(area / mask.size),
            "bicubic_roi_mean": bic_roi,
            "swinir_roi_mean": swin_roi,
            "delta_roi_mean": swin_roi - bic_roi,
            "bicubic_background_mean": bic_bg,
            "swinir_background_mean": swin_bg,
            "bicubic_roi_bg_gap": bic_roi - bic_bg,
            "swinir_roi_bg_gap": swin_roi - swin_bg,
            "delta_roi_bg_gap": delta_gap,
            "bicubic_per_image_pixel_auroc": bic_auc,
            "swinir_per_image_pixel_auroc": swin_auc,
            "delta_per_image_pixel_auroc": swin_auc - bic_auc,
            "bicubic_per_image_aupro": bic_aupro,
            "swinir_per_image_aupro": swin_aupro,
            "delta_per_image_aupro": delta_aupro,
            "map_pearson_corr": correlation,
            "regression_type": _regression_type(delta_aupro, delta_gap),
        })
    if not rows:
        raise ValueError("No anomalous images were available for analysis")
    return rows


def select_cases(rows: list[dict]) -> dict[str, list[dict]]:
    worst_key = lambda row: (row["delta_per_image_aupro"], row["sample"])
    success_key = lambda row: (-row["delta_per_image_aupro"], row["sample"])
    regressions = [row for row in rows if row["delta_per_image_aupro"] < 0]
    return {
        "worst_localization_regression": sorted(regressions, key=worst_key)[:CASES_PER_GROUP],
        "suppression_examples": sorted(
            (row for row in rows if row["regression_type"] == "suppression"), key=worst_key
        )[:CASES_PER_GROUP],
        "geometry_examples": sorted(
            (row for row in rows if row["regression_type"] == "geometry_candidate"), key=worst_key
        )[:CASES_PER_GROUP],
        "success_controls": sorted(rows, key=success_key)[:CASES_PER_GROUP],
    }


def summarize(rows: list[dict], category: str, source_run: str, repeats: int, seed: int) -> dict:
    n = len(rows)
    counts = {name: sum(row["regression_type"] == name for row in rows)
              for name in ("suppression", "geometry_candidate", "improvement_or_tie")}
    regression_count = counts["suppression"] + counts["geometry_candidate"]
    delta_keys = (
        "delta_roi_mean", "delta_roi_bg_gap", "delta_per_image_pixel_auroc", "delta_per_image_aupro",
    )
    rng = np.random.default_rng(seed)
    return {
        "category": category,
        "source_run": source_run,
        "comparison": "SwinIR minus Bicubic",
        "taxonomy_source": "Hazelnut-frozen rules in docs/EXPERIMENT_PROTOCOL_V0.2.md",
        "total_anomalous_images": n,
        "localization_regression_count": regression_count,
        "localization_regression_rate": regression_count / n,
        "suppression_count": counts["suppression"],
        "suppression_rate": counts["suppression"] / n,
        "geometry_candidate_count": counts["geometry_candidate"],
        "geometry_candidate_rate": counts["geometry_candidate"] / n,
        "improvement_or_tie_count": counts["improvement_or_tie"],
        "improvement_or_tie_rate": counts["improvement_or_tie"] / n,
        **{f"mean_{key}": float(np.mean([row[key] for row in rows])) for key in delta_keys},
        "paired_bootstrap": {
            "method": "Paired anomalous-image resampling of mean deltas",
            "repeats": repeats,
            "seed": seed,
            **{key: _bootstrap_mean_delta(np.asarray([row[key] for row in rows]), repeats, rng)
               for key in delta_keys},
        },
        "selection_rule": {
            "maximum_per_group": CASES_PER_GROUP,
            "worst_and_subtypes": "ascending delta_per_image_aupro, then lexical sample path",
            "success_controls": "descending delta_per_image_aupro, then lexical sample path",
            "purpose": "post-hoc qualitative/NN follow-up, not a population estimate",
        },
    }


def _validate_per_image_csv(path: Path, test_paths: list[str]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required run artifact not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"sample", "variant"} <= set(rows[0]):
        raise ValueError("per_image.csv must contain sample and variant columns")
    actual = [(row["sample"], row["variant"]) for row in rows]
    expected = [(sample, variant) for sample in test_paths for variant in VARIANTS]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError("per_image.csv does not contain exactly one row per test sample and required variant")


def load_run(run_dir: Path) -> tuple[str, list[str], dict[str, dict[str, np.ndarray]]]:
    result_path = run_dir / "results.json"
    if not result_path.is_file():
        raise FileNotFoundError(f"Required run artifact not found: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    category = str(result.get("model_spec", {}).get("category", ""))
    if not category or category in {".", ".."} or "/" in category or "\\" in category:
        raise ValueError("results.json must contain a safe model_spec.category")
    test_paths = list(result.get("test_paths", []))
    predictions = {name: _load_npz(run_dir / f"{name}_predictions.npz") for name in VARIANTS}
    _validate_per_image_csv(run_dir / "per_image.csv", test_paths)
    validate_predictions(predictions, test_paths)
    return category, test_paths, predictions


def write_outputs(rows: list[dict], summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "per_anomaly.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "regression_taxonomy.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_FIELDS)
        writer.writeheader()
        writer.writerows({key: row[key] for key in CASE_FIELDS} for row in rows)
    selected = select_cases(rows)
    with (output_dir / "selected_cases.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("selection_group", "rank", *CASE_FIELDS))
        writer.writeheader()
        for group, group_rows in selected.items():
            writer.writerows({"selection_group": group, "rank": rank,
                              **{key: row[key] for key in CASE_FIELDS}}
                             for rank, row in enumerate(group_rows, 1))
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    note = f"""# Cross-category analysis note: {summary['category']}

- Source run: `{summary['source_run']}`
- Comparison: SwinIR minus Bicubic, using saved predictions only.
- Anomalous images: {summary['total_anomalous_images']}
- Localization regressions: {summary['localization_regression_count']} ({summary['localization_regression_rate']:.3%})
- Suppression patterns: {summary['suppression_count']} ({summary['suppression_rate']:.3%})
- Geometry candidates: {summary['geometry_candidate_count']} ({summary['geometry_candidate_rate']:.3%})
- Improvement/tie: {summary['improvement_or_tie_count']} ({summary['improvement_or_tie_rate']:.3%})

The taxonomy and zero cutoff were frozen on Hazelnut before viewing this category. Selected cases follow the pre-fixed AU-PRO/path ranking and are only candidates for qualitative or NN-distance follow-up, not population estimates. No inference, fusion, threshold selection, or model tuning is performed by this script.
"""
    (output_dir / "CROSS_CATEGORY_NOTE.md").write_text(note, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if args.bootstrap < 1:
        raise ValueError("--bootstrap must be positive")
    run_dir = args.run_dir.resolve()
    category, test_paths, predictions = load_run(run_dir)
    rows = analyze_predictions(predictions, test_paths)
    source_run = run_dir.relative_to(ROOT).as_posix() if run_dir.is_relative_to(ROOT) else str(run_dir)
    summary = summarize(rows, category, source_run, args.bootstrap, args.seed)
    output_dir = args.output_dir.resolve() if args.output_dir else ROOT / "analysis" / category
    write_outputs(rows, summary, output_dir)
    print(json.dumps({"category": category, "output": str(output_dir),
                      "anomalous_images": len(rows),
                      "localization_regressions": summary["localization_regression_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
