"""Post-hoc PatchCore NN distances for nine fixed Hazelnut cases; no fitting."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from sr_anomaly.dataset import safe_join
from sr_anomaly.evaluation import area_under_per_region_overlap, binary_roc_auc
from sr_anomaly.real_models import SwinIRLightweight
from run_legacy_patchcore import _canonical, _checksum, _faiss_staging, _official_imports


# Fixed after the Hazelnut map-level analysis; exploratory, not an unbiased sample.
SELECTED = (
    ("geometry_candidate", "hazelnut/test/crack/013.png"),
    ("geometry_candidate", "hazelnut/test/crack/015.png"),
    ("geometry_candidate", "hazelnut/test/print/005.png"),
    ("suppression", "hazelnut/test/crack/001.png"),
    ("suppression", "hazelnut/test/crack/017.png"),
    ("suppression", "hazelnut/test/hole/014.png"),
    ("success_control", "hazelnut/test/crack/006.png"),
    ("success_control", "hazelnut/test/cut/003.png"),
    ("success_control", "hazelnut/test/hole/006.png"),
)
SOURCE_COMMIT = "fcaa92f124fb1ad74a7acf56726decd4b27cbcad"


def mask_occupancy(mask: np.ndarray, grid: tuple[int, int]) -> np.ndarray:
    """Fraction of GT-positive pixels in each nonoverlapping feature-grid cell."""
    mask = np.asarray(mask, dtype=bool)
    rows, cols = grid
    if mask.ndim != 2 or rows < 1 or cols < 1 or mask.shape[0] % rows or mask.shape[1] % cols:
        raise ValueError("GT mask must be 2D and divisible by the actual feature grid")
    return mask.reshape(rows, mask.shape[0] // rows, cols, mask.shape[1] // cols).mean(axis=(1, 3))


def distance_region_stats(distances: np.ndarray, occupancy: np.ndarray) -> dict[str, float]:
    """Continuous-occupancy means of FAISS IndexFlatL2 squared-L2 distances."""
    distances = np.asarray(distances, dtype=np.float64)
    occupancy = np.asarray(occupancy, dtype=np.float64)
    if distances.shape != occupancy.shape or not np.isfinite(distances).all():
        raise ValueError("Distance grid and GT occupancy must have matching finite shapes")
    if np.any((occupancy < 0) | (occupancy > 1)) or not 0 < occupancy.sum() < occupancy.size:
        raise ValueError("GT occupancy needs both defect and background")
    defect = float(np.sum(occupancy * distances) / occupancy.sum())
    background = float(np.sum((1 - occupancy) * distances) / np.sum(1 - occupancy))
    return {"d_defect": defect, "d_background": background, "feature_gap": defect - background}


def _saved_predictions(run_dir: Path, test_paths: list[str]) -> dict[str, dict[str, np.ndarray]]:
    predictions = {}
    for name in ("bicubic_x4", "swinir_x4"):
        with np.load(run_dir / f"{name}_predictions.npz", allow_pickle=False) as data:
            predictions[name] = {key: np.asarray(data[key]) for key in ("labels", "scores", "masks", "maps")}
        if any(len(value) != len(test_paths) for value in predictions[name].values()):
            raise ValueError(f"{name} prediction count differs from test_paths")
    bic, swin = predictions.values()
    if not np.array_equal(bic["labels"], swin["labels"]) or not np.array_equal(bic["masks"], swin["masks"]):
        raise ValueError("Saved Bicubic/SwinIR predictions are not paired")
    return predictions


def _check_sources(run_dir: Path, model_dir: Path, checkpoint: Path) -> tuple[dict, list[str]]:
    result = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
    spec = result["model_spec"]
    if spec != metadata["spec"] or spec["source_commit"] != SOURCE_COMMIT:
        raise ValueError("Branch A result and memory-bank metadata do not match the pinned model")
    if spec["category"] != "hazelnut" or spec["seed"] != 11 or len(spec["train_paths"]) != 391:
        raise ValueError("Expected the Branch A 391-image Hazelnut memory bank, seed 11")
    pinned = {"backbone": "wideresnet50", "layers": ["layer2", "layer3"], "resize": 256,
              "center_crop": 224, "pretrain_embed_dimension": 1024, "target_embed_dimension": 1024,
              "patchsize": 3, "sampler": "IdentitySampler", "nearest_neighbor": "FaissNN(cpu)"}
    if any(spec.get(key) != value for key, value in pinned.items()):
        raise ValueError("Branch A PatchCore architecture or preprocessing differs from the pinned setting")
    expected_settings = {"backbone": "wideresnet50", "layers": ["layer2", "layer3"],
                         "resize": 256, "center_crop": 224, "pretrain_embed_dimension": 1024,
                         "target_embed_dimension": 1024, "patchsize": 3,
                         "sampler": "IdentitySampler", "nearest_neighbor": "FaissNN(cpu)"}
    if any(spec.get(key) != value for key, value in expected_settings.items()):
        raise ValueError("Branch A PatchCore settings differ from the pinned detector")
    if set(metadata["artifact_sha256"]) != {"patchcore_params.pkl", "nnscorer_search_index.faiss"}:
        raise ValueError("Incomplete or unexpected memory-bank artifacts")
    for name, expected in metadata["artifact_sha256"].items():
        if _checksum(model_dir / name) != expected:
            raise ValueError(f"Memory-bank checksum mismatch: {name}")
    if _checksum(checkpoint) != result["restoration"]["checkpoint_sha256"]:
        raise ValueError("SwinIR checkpoint differs from the Branch A run")
    test_paths = list(result["test_paths"])
    if len(test_paths) != 110 or len(set(test_paths)) != 110 or result["nn_stats_enabled"]:
        raise ValueError("Expected the saved 110-test Branch A run without prior NN statistics")
    if not set(path for _, path in SELECTED) <= set(test_paths):
        raise ValueError("A fixed selected case is missing from Branch A test_paths")
    return result, test_paths


def _map_stats(mask: np.ndarray, anomaly_map: np.ndarray) -> dict[str, float]:
    region = mask.astype(bool)
    return {
        "per_image_aupro": float(area_under_per_region_overlap(region[None], anomaly_map[None], max_fpr=0.3, num_thresholds=200)),
        "pixel_auroc": float(binary_roc_auc(region.ravel(), anomaly_map.ravel())),
        "map_roi_bg_gap": float(anomaly_map[region].mean() - anomaly_map[~region].mean()),
    }


def _patch_distances(model, image_tensor, expected_map: np.ndarray, torch) -> tuple[np.ndarray, tuple[int, int], float]:
    with torch.no_grad():
        features, shapes = model._embed(image_tensor, provide_patch_shapes=True)
    grid = tuple(int(value) for value in shapes[0])
    if len(grid) != 2 or np.asarray(features).shape[0] != grid[0] * grid[1]:
        raise ValueError("Patch embedding count does not match actual feature grid")
    patch_scores, distances, _ = model.anomaly_scorer.predict([np.asarray(features)])
    if distances.shape != (grid[0] * grid[1], 1):
        raise ValueError("Expected one exact nearest-neighbor distance per patch")
    reconstructed_map = np.asarray(model.anomaly_segmentor.convert_to_segmentation(patch_scores.reshape(1, *grid))[0])
    max_error = float(np.max(np.abs(reconstructed_map - expected_map)))
    if not np.allclose(reconstructed_map, expected_map, rtol=1e-5, atol=1e-4):
        raise ValueError(f"Recomputed PatchCore map differs from saved Branch A map (max error {max_error:.6g})")
    return distances[:, 0].reshape(grid), grid, max_error


def _summary(rows: list[dict], run_dir: Path, model_dir: Path) -> str:
    def display(path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    lines = [
        "# Selected-case PatchCore NN distances",
        "",
        "Exploratory nine cases selected after Hazelnut results; no causal or population-level claim.",
        f"Source predictions: `{display(run_dir)}`; unchanged 391-image bank: `{display(model_dir)}`.",
        "Distances are official FAISS IndexFlatL2 squared L2 values (not smoothed anomaly-map scores).",
        "GT occupancy is the positive-pixel fraction of each nonoverlapping cell after the original 256-resize/224-center-crop; cells align to the actual PatchCore feature grid. The 3x3 feature patches and backbone receptive fields exceed these cells, so this is an approximate ROI assignment.",
        "GT was used only for post-hoc evaluation. Each recomputed map matched its saved prediction before distances were recorded.",
        "",
        "| Subtype | n | Mean ΔAU-PRO | Mean Δmap gap | Mean ΔD_defect | Mean ΔD_background | Mean Δfeature gap |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for subtype in ("suppression", "geometry_candidate", "success_control"):
        subset = [row for row in rows if row["subtype"] == subtype]
        means = [float(np.mean([row[key] for row in subset])) for key in (
            "delta_per_image_aupro", "delta_map_roi_bg_gap", "delta_d_defect", "delta_d_background", "delta_feature_gap"
        )]
        lines.append(f"| {subtype} | {len(subset)} | " + " | ".join(f"{value:+.6f}" for value in means) + " |")
    lines += ["", "Cases with both ΔD_defect < 0 and Δfeature gap < 0: " + ", ".join(
        f"{kind} {sum(row['delta_d_defect'] < 0 and row['delta_feature_gap'] < 0 for row in rows if row['subtype'] == kind)}/3"
        for kind in ("suppression", "geometry_candidate", "success_control")
    ) + "."]
    lines += ["Descriptive only: n=3 per subtype; feature-distance patterns are not perfectly subtype-specific, and the map-level names are not proven mechanisms."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "outputs/legacy-patchcore/hazelnut-full391-test110-repro")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "checkpoints/legacy-patchcore/hazelnut-seed11-train391")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/external/MVTecAD")
    parser.add_argument("--swinir-checkpoint", type=Path, default=ROOT / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis/hazelnut")
    args = parser.parse_args()
    _, test_paths = _check_sources(args.run_dir, args.model_dir, args.swinir_checkpoint)
    predictions = _saved_predictions(args.run_dir, test_paths)
    index = {path: i for i, path in enumerate(test_paths)}
    actual_commit = subprocess.check_output(["git", "-C", str(ROOT / "third_party/patchcore-inspection"), "rev-parse", "HEAD"], text=True).strip()
    if actual_commit != SOURCE_COMMIT:
        raise ValueError(f"PatchCore source revision changed: {actual_commit}")

    torch, transforms, InterpolationMode, _, common, patchcore, _, mvtec = _official_imports()
    torch.set_num_threads(min(4, torch.get_num_threads()))
    model = patchcore.PatchCore(torch.device("cpu"))
    with _faiss_staging() as staging:
        for name in ("patchcore_params.pkl", "nnscorer_search_index.faiss"):
            shutil.copy2(args.model_dir / name, Path(staging) / name)
        model.load_from_path(staging, torch.device("cpu"), nn_method=common.FaissNN(False, 4))
    restorer = SwinIRLightweight(ROOT / "third_party/SwinIR", args.swinir_checkpoint, scale=4, tile=56, tile_overlap=0)
    resize = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    crop = transforms.CenterCrop(224)
    tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])

    rows: list[dict] = []
    for subtype, sample in SELECTED:
        i = index[sample]
        mask = np.asarray(predictions["bicubic_x4"]["masks"][i], dtype=bool)
        if predictions["bicubic_x4"]["labels"][i] != 1 or not 0 < mask.sum() < mask.size:
            raise ValueError(f"Expected anomalous saved mask for {sample}")
        with Image.open(safe_join(args.data_root, sample)) as source:
            clean = _canonical(source.convert("RGB"), resize, crop)
        low_resolution = clean.resize((56, 56), Image.Resampling.BICUBIC)
        metrics = {}
        for variant in ("bicubic_x4", "swinir_x4"):
            image = (low_resolution.resize((224, 224), Image.Resampling.BICUBIC)
                     if variant == "bicubic_x4" else restorer.restore(low_resolution))
            started = perf_counter()
            saved_map = np.asarray(predictions[variant]["maps"][i], dtype=np.float64)
            distances, grid, map_error = _patch_distances(model, tensor(image).unsqueeze(0), saved_map, torch)
            occupancy = mask_occupancy(mask, grid)
            metrics[variant] = {**_map_stats(mask, saved_map), **distance_region_stats(distances, occupancy),
                                "map_validation_max_abs": map_error, "feature_grid": f"{grid[0]}x{grid[1]}",
                                "defect_occupancy_sum": float(occupancy.sum())}
            print(f"{sample} {variant}: {perf_counter() - started:.1f}s", flush=True)
        bic, swin = metrics["bicubic_x4"], metrics["swinir_x4"]
        row = {"sample": sample, "subtype": subtype, "defect_type": Path(sample).parent.name,
               "nn_distance_unit": "faiss_indexflatl2_squared_l2", "feature_grid": bic["feature_grid"],
               "defect_occupancy_sum": bic["defect_occupancy_sum"]}
        if bic["feature_grid"] != swin["feature_grid"]:
            raise ValueError("Bicubic and SwinIR patch grids differ")
        for key in ("per_image_aupro", "pixel_auroc", "map_roi_bg_gap", "d_defect", "d_background", "feature_gap"):
            row[f"bicubic_{key}"] = bic[key]
            row[f"swinir_{key}"] = swin[key]
            row[f"delta_{key}"] = swin[key] - bic[key]
        row["bicubic_map_validation_max_abs"] = bic["map_validation_max_abs"]
        row["swinir_map_validation_max_abs"] = swin["map_validation_max_abs"]
        rows.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "nn_distance_selected.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir / "nn_distance_selected_summary.md").write_text(_summary(rows, args.run_dir, args.model_dir), encoding="utf-8")
    print(f"Saved {len(rows)} selected cases to {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
