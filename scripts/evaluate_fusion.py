"""Evaluate fixed equal-weight PatchCore map fusion using held-out normal calibration."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from sr_anomaly.evaluation import evaluate_predictions


BRANCHES = ("bicubic_x4", "swinir_x4")


def _load(path: Path, keys: tuple[str, ...]) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        missing = set(keys) - set(archive.files)
        if missing:
            raise ValueError(f"{path} is missing {sorted(missing)}")
        return {key: archive[key] for key in keys}


def _scale(values: np.ndarray, normal: np.ndarray) -> tuple[np.ndarray, float]:
    values = np.asarray(values, dtype=np.float64)
    normal = np.asarray(normal, dtype=np.float64)
    if not values.size or not normal.size or not np.isfinite(values).all() or not np.isfinite(normal).all():
        raise ValueError("Scores and normal calibration values must be nonempty and finite")
    reference = float(np.quantile(normal, 0.99))
    if reference <= 0:
        raise ValueError("Normal 99th-percentile reference must be positive")
    return values / reference, reference


def fuse_predictions(
    test: dict[str, dict[str, np.ndarray]],
    calibration: dict[str, dict[str, np.ndarray]],
) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, dict[str, float]]]:
    """Scale branches on normal-only data, then compute prespecified mean/max ablations."""
    if set(test) != set(BRANCHES) or set(calibration) != set(BRANCHES):
        raise ValueError(f"Both inputs require branches {BRANCHES}")
    scaled: dict[str, dict[str, np.ndarray]] = {}
    references: dict[str, dict[str, float]] = {}
    for name in BRANCHES:
        branch = test[name]
        normal = calibration[name]
        if branch["scores"].ndim != 1 or normal["scores"].ndim != 1:
            raise ValueError("Image scores must be one-dimensional")
        if branch["maps"].ndim != 3 or normal["maps"].ndim != 3 or branch["maps"].shape[1:] != normal["maps"].shape[1:]:
            raise ValueError("Anomaly maps must have matching [N, H, W] dimensions")
        if len(branch["scores"]) != len(branch["maps"]) or len(normal["scores"]) != len(normal["maps"]):
            raise ValueError("Image scores and anomaly maps must have equal sample counts")
        scores, score_ref = _scale(branch["scores"], normal["scores"])
        maps, map_ref = _scale(branch["maps"], normal["maps"])
        normal_scores = normal["scores"] / score_ref
        normal_maps = normal["maps"] / map_ref
        scaled[name] = {"scores": scores, "maps": maps, "normal_scores": normal_scores, "normal_maps": normal_maps}
        references[name] = {"image_q99": score_ref, "pixel_q99": map_ref}
    left, right = (scaled[name] for name in BRANCHES)
    if left["scores"].shape != right["scores"].shape or left["maps"].shape != right["maps"].shape:
        raise ValueError("Paired test predictions must have matching shapes")
    if left["normal_scores"].shape != right["normal_scores"].shape or left["normal_maps"].shape != right["normal_maps"].shape:
        raise ValueError("Paired calibration predictions must have matching shapes")
    for method, combine in (("mean_equal", lambda a, b: (a + b) / 2), ("max", np.maximum)):
        scaled[method] = {key: combine(left[key], right[key]) for key in ("scores", "maps", "normal_scores", "normal_maps")}
    return scaled, references


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="legacy PatchCore run with paired test and calibration NPZ files")
    parser.add_argument("--output-dir", type=Path, help="defaults to RUN_DIR/fusion_equal")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = (args.output_dir or run_dir / "fusion_equal").resolve()
    source = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    train_paths = set(source["model_spec"]["train_paths"])
    normal_paths = set(source["calibration"]["paths"])
    test_paths = set(source["test_paths"])
    if not normal_paths or len(normal_paths) != len(source["calibration"]["paths"]):
        raise ValueError("Independent normal calibration paths are required")
    if train_paths & normal_paths or train_paths & test_paths or normal_paths & test_paths:
        raise ValueError("Train, calibration, and test paths must be disjoint")
    test = {name: _load(run_dir / f"{name}_predictions.npz", ("labels", "scores", "masks", "maps")) for name in BRANCHES}
    calibration = {name: _load(run_dir / f"{name}_calibration.npz", ("scores", "maps", "paths")) for name in BRANCHES}
    first, second = (test[name] for name in BRANCHES)
    if not np.array_equal(first["labels"], second["labels"]) or not np.array_equal(first["masks"], second["masks"]):
        raise ValueError("Paired branches have different labels or masks")
    if len(first["labels"]) != len(source["test_paths"]):
        raise ValueError("Test prediction count does not match recorded paths")
    for name in BRANCHES:
        if calibration[name]["paths"].tolist() != source["calibration"]["paths"]:
            raise ValueError(f"{name} calibration paths do not match the run manifest")
    scaled, references = fuse_predictions(test, calibration)
    methods = {}
    for name, values in scaled.items():
        image_threshold = float(np.quantile(values["normal_scores"], 0.99))
        pixel_threshold = float(np.quantile(values["normal_maps"], 0.99))
        methods[name] = evaluate_predictions(first["labels"], values["scores"], first["masks"], values["maps"],
                                             image_threshold=image_threshold, pixel_threshold=pixel_threshold)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Fusion output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {"source_run": str(run_dir), "method": "normal_q99_scale; fixed 0.5:0.5 mean and max ablation",
              "calibration_count": len(normal_paths), "test_count": len(test_paths),
              "normalization_references": references, "methods": methods,
              "note": "Exploratory subset only; the test category was previously inspected, so this is not an untouched confirmation set."}
    (output_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        rows = [{"method": name, "calibration_count": len(normal_paths), "test_count": len(test_paths),
                 **item["classification"], **item["localization"]} for name, item in methods.items()]
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"output": str(output_dir), "methods": methods}, ensure_ascii=False))


if __name__ == "__main__":
    main()
