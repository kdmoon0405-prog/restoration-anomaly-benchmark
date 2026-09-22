"""Detection-improvement experiment: calibrated fusion of degraded/restored maps.

Uses Amazon's original PatchCore source (same settings as run_legacy_patchcore.py)
but splits normal training images into disjoint fit/calibration lists, fits
per-variant robust normalization on calibration normals only, and compares four
fixed methods with test labels strictly unseen:

- degraded_only (bicubic x4, normalized)
- restored_only (SwinIR-S x4, normalized)
- mean_0.5_0.5 (fixed equal average, the first method to beat restored-only)
- max (normalized maximum)

F1 thresholds come from fused calibration scores, never test labels. hazelnut is
the development/exploration category; final validation belongs on an unseen
category such as capsule.
"""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

from sr_anomaly.dataset import MVTecADFolder, safe_component
from sr_anomaly.device import device_metadata, elapsed_seconds, resolve_device, start_timer
from sr_anomaly.evaluation import evaluate_predictions
from sr_anomaly.fusion import (
    METHODS,
    fit_fusion_calibration,
    fuse_test_maps,
    fuse_test_scores,
    quantile_threshold,
    robust_params,
    split_train_calibration,
)
from sr_anomaly.metrics import compute_quality_metrics
from sr_anomaly.real_models import SwinIRLightweight


ROOT = Path(__file__).resolve().parents[1]
PATCHCORE_SOURCE = ROOT / "third_party" / "patchcore-inspection" / "src"
EXPECTED_PATCHCORE_COMMIT = "fcaa92f124fb1ad74a7acf56726decd4b27cbcad"
EXPECTED_SWINIR_X4_SHA256 = "09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e"


def _official_imports():
    if not PATCHCORE_SOURCE.is_dir():
        raise RuntimeError("Initialize the patchcore-inspection submodule first: git submodule update --init")
    sys.path.insert(0, str(PATCHCORE_SOURCE))
    import torch
    from torchvision import transforms
    from torchvision.transforms import InterpolationMode
    from patchcore import backbones, common, patchcore, sampler
    from patchcore.datasets import mvtec

    return torch, transforms, InterpolationMode, backbones, common, patchcore, sampler, mvtec


def _balanced_test(samples, limit: int, seed: int):
    if limit < 0:
        raise ValueError("test limit must be nonnegative")
    if not limit or limit >= len(samples):
        return list(samples)
    normal = [sample for sample in samples if sample.metadata["label"] == 0]
    anomalous = [sample for sample in samples if sample.metadata["label"] == 1]
    rng = random.Random(seed)
    normal_count = limit // 2
    anomalous_count = limit - normal_count
    if len(normal) < normal_count or len(anomalous) < anomalous_count:
        raise ValueError("test limit cannot be balanced from available samples")
    return sorted(
        rng.sample(normal, normal_count) + rng.sample(anomalous, anomalous_count),
        key=lambda x: x.relative_path.as_posix(),
    )


def _canonical(image: Image.Image, resize, crop) -> Image.Image:
    return crop(resize(image))


def _checksum(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _delta(new: float | None, baseline: float | None) -> float | None:
    return None if new is None or baseline is None else new - baseline


def _faiss_staging():
    # FAISS Windows wheels use narrow C paths and reject non-ASCII workspace paths.
    parent = Path(os.environ.get("PUBLIC", tempfile.gettempdir()))
    try:
        str(parent).encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError("FAISS requires an ASCII temporary path; set PUBLIC to a writable ASCII directory") from exc
    return tempfile.TemporaryDirectory(prefix="patchcore-", dir=parent)


def _predict(model, tensor, image: Image.Image) -> tuple[float, np.ndarray]:
    scores, maps = model.predict(tensor(image).unsqueeze(0))
    anomaly_map = np.asarray(maps[0], dtype=np.float32)
    if anomaly_map.ndim != 2:
        raise ValueError(f"PatchCore anomaly map must be 2D, got {anomaly_map.shape}")
    if not np.isfinite(scores[0]) or not np.isfinite(anomaly_map).all():
        raise ValueError("PatchCore returned a non-finite score or anomaly map")
    return float(scores[0]), anomaly_map


def _validate_replayed_split(
    split: dict, category: str, train_count_total: int, seed: int, train_ratio: float
) -> tuple[list[int], list[int]]:
    if (split.get("category") != category or split.get("train_count_total") != train_count_total
            or split.get("seed") != seed or split.get("train_ratio") != train_ratio):
        raise ValueError("split JSON category, dataset size, seed, or train ratio does not match this run")
    try:
        selected = [int(index) for index in split["train_indices"]]
        calibration = [int(index) for index in split["calibration_indices"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("split JSON has invalid train/calibration indices") from exc
    combined = selected + calibration
    if (not selected or not calibration or len(set(combined)) != len(combined)
            or any(index < 0 or index >= train_count_total for index in combined)):
        raise ValueError("split JSON indices must be unique, disjoint, nonempty, and in range")
    return selected, calibration


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--category", default="hazelnut")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--train-limit", type=int, default=0, help="0 = all split train images; >0 keeps the first K (cheap plumbing only)")
    parser.add_argument("--calibration-limit", type=int, default=0, help="0 = all split calibration images; >0 keeps the first K (cheap plumbing only)")
    parser.add_argument("--test-limit", type=int, default=20, help="0 = all test images")
    parser.add_argument("--calibration-quantile", type=float, default=0.99)
    parser.add_argument("--split-json", type=Path, help="reuse an exact train/calibration split")
    parser.add_argument("--swinir-checkpoint", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu", help="Torch/SwinIR device; FAISS remains on CPU")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not 0.0 < args.train_ratio < 1.0:
        parser.error("--train-ratio must be in (0, 1)")
    if not 0.0 < args.calibration_quantile < 1.0:
        parser.error("--calibration-quantile must be in (0, 1)")
    if args.split_json and (args.train_limit or args.calibration_limit):
        parser.error("Do not combine --split-json with additional train/calibration limits")
    category = safe_component(args.category, "category")

    torch, transforms, InterpolationMode, backbones, common, patchcore, sampler, mvtec = _official_imports()
    cuda_available = torch.cuda.is_available()
    device = torch.device(resolve_device(args.device, cuda_available))
    execution = device_metadata(
        args.device, str(device), cuda_available,
        torch.cuda.get_device_name(device) if str(device).startswith("cuda") else None,
    )
    checkpoint_sha256 = _checksum(args.swinir_checkpoint)
    if checkpoint_sha256 != EXPECTED_SWINIR_X4_SHA256:
        raise ValueError(
            f"SwinIR x4 checkpoint mismatch: expected {EXPECTED_SWINIR_X4_SHA256}, got {checkpoint_sha256}"
        )
    actual_commit = subprocess.check_output(
        ["git", "-C", str(PATCHCORE_SOURCE.parent), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_commit != EXPECTED_PATCHCORE_COMMIT:
        raise RuntimeError(f"PatchCore source revision changed: expected {EXPECTED_PATCHCORE_COMMIT}, got {actual_commit}")
    torch.set_num_threads(min(4, torch.get_num_threads()))
    data_root = args.data_root.resolve()
    train_set = mvtec.MVTecDataset(
        str(data_root), category, resize=256, imagesize=224, split=mvtec.DatasetSplit.TRAIN
    )
    train_count_total = len(train_set)
    if args.split_json:
        split = json.loads(args.split_json.read_text(encoding="utf-8"))
        selected, calibration_indices = _validate_replayed_split(
            split, category, train_count_total, args.seed, args.train_ratio
        )
        expected_train_paths = [
            Path(train_set.data_to_iterate[index][2]).relative_to(data_root).as_posix() for index in selected
        ]
        expected_calibration_paths = [
            Path(train_set.data_to_iterate[index][2]).relative_to(data_root).as_posix()
            for index in calibration_indices
        ]
        if (split.get("train_paths") != expected_train_paths
                or split.get("calibration_paths") != expected_calibration_paths):
            raise ValueError("split JSON paths do not match the current dataset ordering")
    else:
        selected, calibration_indices = split_train_calibration(train_count_total, args.train_ratio, args.seed)
    if args.train_limit < 0 or args.calibration_limit < 0:
        parser.error("--train-limit and --calibration-limit must be nonnegative")
    if args.train_limit:
        selected = selected[: args.train_limit]
    if args.calibration_limit:
        calibration_indices = calibration_indices[: args.calibration_limit]
    test_samples = _balanced_test(MVTecADFolder(data_root, category).samples(), args.test_limit, args.seed)
    if not selected or not calibration_indices or not test_samples:
        raise ValueError("training, calibration, and test sets must all be nonempty")

    run_name = f"{category}-fusion-seed{args.seed}-train{len(selected)}-cal{len(calibration_indices)}-test{len(test_samples)}"
    model_dir = args.model_dir or ROOT / "checkpoints" / "fusion-patchcore" / f"{category}-seed{args.seed}-train{len(selected)}"
    output_dir = args.output_dir or ROOT / "outputs" / "fusion-patchcore" / run_name
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Experiment output directory is not empty: {output_dir}")
    model_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_paths = [str(Path(train_set.data_to_iterate[index][2]).relative_to(data_root).as_posix()) for index in selected]
    calibration_paths = [
        str(Path(train_set.data_to_iterate[index][2]).relative_to(data_root).as_posix()) for index in calibration_indices
    ]
    split_record = {
        "category": category,
        "seed": args.seed,
        "train_ratio": args.train_ratio,
        "train_limit": args.train_limit,
        "calibration_limit": args.calibration_limit,
        "train_count_total": train_count_total,
        "train_indices": selected,
        "calibration_indices": calibration_indices,
        "train_paths": train_paths,
        "calibration_paths": calibration_paths,
    }
    (output_dir / "split.json").write_text(json.dumps(split_record, ensure_ascii=False, indent=2), encoding="utf-8")

    model_spec = {
        "implementation": "amazon-science/patchcore-inspection",
        "source_commit": actual_commit,
        "category": category,
        "seed": args.seed,
        "train_ratio": args.train_ratio,
        "train_paths": train_paths,
        "calibration_paths": calibration_paths,
        "backbone": "wideresnet50",
        "layers": ["layer2", "layer3"],
        "resize": 256,
        "center_crop": 224,
        "pretrain_embed_dimension": 1024,
        "target_embed_dimension": 1024,
        "patchsize": 3,
        "sampler": "IdentitySampler",
        "nearest_neighbor": "FaissNN(cpu)",
    }
    model_meta_path = model_dir / "metadata.json"
    params_path = model_dir / "patchcore_params.pkl"
    faiss_path = model_dir / "nnscorer_search_index.faiss"
    model = patchcore.PatchCore(device)
    fit_seconds = 0.0
    if model_meta_path.exists():
        saved = json.loads(model_meta_path.read_text(encoding="utf-8"))
        if saved["spec"] != model_spec or any(
            _checksum(model_dir / name) != digest for name, digest in saved["artifact_sha256"].items()
        ):
            raise ValueError("Existing PatchCore artifact does not match this run; choose a different --model-dir")
        with _faiss_staging() as staging:
            for path in (params_path, faiss_path):
                shutil.copy2(path, Path(staging) / path.name)
            model.load_from_path(staging, device, nn_method=common.FaissNN(False, 4))
    else:
        if params_path.exists() or faiss_path.exists():
            raise ValueError("Incomplete existing PatchCore artifact; choose a different --model-dir")
        backbone = backbones.load("wideresnet50")
        backbone.name = "wideresnet50"
        model.load(
            backbone=backbone,
            layers_to_extract_from=["layer2", "layer3"],
            device=device,
            input_shape=(3, 224, 224),
            pretrain_embed_dimension=1024,
            target_embed_dimension=1024,
            patchsize=3,
            featuresampler=sampler.IdentitySampler(),
            nn_method=common.FaissNN(False, 4),
        )
        loader = torch.utils.data.DataLoader(
            torch.utils.data.Subset(train_set, selected), batch_size=8, shuffle=False, num_workers=0
        )
        started = start_timer(torch, device)
        model.fit(loader)
        fit_seconds = elapsed_seconds(torch, device, started)
        with _faiss_staging() as staging:
            model.save_to_path(staging)
            for path in (params_path, faiss_path):
                shutil.copy2(Path(staging) / path.name, path)
        model_meta_path.write_text(
            json.dumps(
                {
                    "spec": model_spec,
                    "fit_seconds": fit_seconds,
                    "artifact_sha256": {path.name: _checksum(path) for path in (params_path, faiss_path)},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    resize_image = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    resize_mask = transforms.Resize(256, interpolation=InterpolationMode.NEAREST)
    crop = transforms.CenterCrop(224)
    tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])
    restorer = SwinIRLightweight(
        ROOT / "third_party" / "SwinIR", args.swinir_checkpoint, device=str(device), scale=4, tile=56, tile_overlap=0
    )

    def _variants(image: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image, float]:
        clean = _canonical(image.convert("RGB"), resize_image, crop)
        low_resolution = clean.resize((56, 56), Image.Resampling.BICUBIC)
        bicubic = low_resolution.resize((224, 224), Image.Resampling.BICUBIC)
        started = start_timer(torch, device)
        restored = restorer.restore(low_resolution)
        restoration_seconds = elapsed_seconds(torch, device, started)
        if restored.size != clean.size:
            raise ValueError(f"SwinIR output size {restored.size} differs from reference {clean.size}")
        return clean, bicubic, restored, restoration_seconds

    # Calibration on held-out normal images only: raw scores for clean plus
    # degraded/restored pairs for robust normalization and fused thresholds.
    calibration_started = start_timer(torch, device)
    clean_scores: list[float] = []
    clean_pixels: list[np.ndarray] = []
    degraded_scores: list[float] = []
    restored_scores: list[float] = []
    degraded_pixels: list[np.ndarray] = []
    restored_pixels: list[np.ndarray] = []
    map_shape: tuple[int, int] | None = None
    for index in calibration_indices:
        with Image.open(train_set.data_to_iterate[index][2]) as source:
            clean, bicubic, restored, _ = _variants(source)
        clean_score, clean_map = _predict(model, tensor, clean)
        degraded_score, degraded_map = _predict(model, tensor, bicubic)
        restored_score, restored_map = _predict(model, tensor, restored)
        if degraded_map.shape != restored_map.shape or clean_map.shape != degraded_map.shape:
            raise ValueError("calibration anomaly maps must share one shape")
        map_shape = degraded_map.shape
        clean_scores.append(clean_score)
        clean_pixels.append(np.asarray(clean_map, dtype=np.float64))
        degraded_scores.append(degraded_score)
        restored_scores.append(restored_score)
        degraded_pixels.append(np.asarray(degraded_map, dtype=np.float64))
        restored_pixels.append(np.asarray(restored_map, dtype=np.float64))
    calibration_seconds = elapsed_seconds(torch, device, calibration_started)
    fusion_calibration = fit_fusion_calibration(
        np.asarray(degraded_scores),
        np.asarray(restored_scores),
        np.concatenate([pixels.ravel() for pixels in degraded_pixels]),
        np.concatenate([pixels.ravel() for pixels in restored_pixels]),
        quantile=args.calibration_quantile,
    )
    clean_calibration = {
        "source": "held-out normal train images (clean)",
        "quantile": args.calibration_quantile,
        "image_threshold": quantile_threshold(np.asarray(clean_scores), args.calibration_quantile),
        "pixel_threshold": quantile_threshold(
            np.concatenate([pixels.ravel() for pixels in clean_pixels]), args.calibration_quantile
        ),
        "image_params": robust_params(np.asarray(clean_scores)),
    }

    # Test evaluation with frozen calibration.
    test_started = start_timer(torch, device)
    labels: list[int] = []
    masks: list[np.ndarray] = []
    clean_test_scores: list[float] = []
    clean_test_maps: list[np.ndarray] = []
    degraded_test_scores: list[float] = []
    restored_test_scores: list[float] = []
    degraded_test_maps: list[np.ndarray] = []
    restored_test_maps: list[np.ndarray] = []
    rows: list[dict] = []
    for sample in test_samples:
        with Image.open(sample.path) as source:
            clean, bicubic, restored, restoration_seconds = _variants(source)
        if sample.mask_path:
            with Image.open(sample.mask_path) as mask_source:
                mask = np.asarray(_canonical(mask_source.convert("L"), resize_mask, crop)) > 0
        else:
            mask = np.zeros((224, 224), dtype=bool)
        started = start_timer(torch, device)
        clean_score, clean_map = _predict(model, tensor, clean)
        degraded_score, degraded_map = _predict(model, tensor, bicubic)
        restored_score, restored_map = _predict(model, tensor, restored)
        detector_seconds = elapsed_seconds(torch, device, started)
        if degraded_map.shape != mask.shape or restored_map.shape != mask.shape or clean_map.shape != mask.shape:
            raise ValueError(f"anomaly map shape {degraded_map.shape} differs from mask shape {mask.shape}")
        labels.append(int(sample.metadata["label"]))
        masks.append(mask)
        clean_test_scores.append(clean_score)
        clean_test_maps.append(np.asarray(clean_map, dtype=np.float32))
        degraded_test_scores.append(degraded_score)
        restored_test_scores.append(restored_score)
        degraded_test_maps.append(np.asarray(degraded_map, dtype=np.float32))
        restored_test_maps.append(np.asarray(restored_map, dtype=np.float32))
        bicubic_quality = compute_quality_metrics(clean, bicubic, ("psnr", "ssim"))
        restored_quality = compute_quality_metrics(clean, restored, ("psnr", "ssim"))
        rows.append(
            {
                "sample": sample.relative_path.as_posix(),
                "label": int(sample.metadata["label"]),
                "clean_score": clean_score,
                "degraded_score_raw": degraded_score,
                "restored_score_raw": restored_score,
                "psnr_bicubic": bicubic_quality["psnr"],
                "ssim_bicubic": bicubic_quality["ssim"],
                "psnr_swinir": restored_quality["psnr"],
                "ssim_swinir": restored_quality["ssim"],
                "restoration_seconds": restoration_seconds,
                "detector_seconds": detector_seconds,
            }
        )
    test_seconds = elapsed_seconds(torch, device, test_started)

    fused_scores = fuse_test_scores(
        np.asarray(degraded_test_scores), np.asarray(restored_test_scores), fusion_calibration
    )
    fused_maps = fuse_test_maps(
        np.asarray(degraded_test_maps), np.asarray(restored_test_maps), fusion_calibration
    )
    labels_array = np.asarray(labels)
    masks_array = np.asarray(masks)
    evaluations: dict[str, dict] = {
        "clean_reference": evaluate_predictions(
            labels_array,
            np.asarray(clean_test_scores),
            masks_array,
            np.asarray(clean_test_maps),
            image_threshold=clean_calibration["image_threshold"],
            pixel_threshold=clean_calibration["pixel_threshold"],
        )
    }
    predictions: dict[str, dict[str, np.ndarray]] = {
        "clean_reference": {
            "labels": labels_array,
            "scores": np.asarray(clean_test_scores),
            "masks": masks_array,
            "maps": np.asarray(clean_test_maps),
        }
    }
    for method in METHODS:
        evaluations[method] = evaluate_predictions(
            labels_array,
            np.asarray(fused_scores[method]),
            masks_array,
            np.asarray(fused_maps[method]),
            image_threshold=fusion_calibration["image_thresholds"][method],
            pixel_threshold=fusion_calibration["pixel_thresholds"][method],
        )
        predictions[method] = {
            "labels": labels_array,
            "scores": np.asarray(fused_scores[method]),
            "masks": masks_array,
            "maps": np.asarray(fused_maps[method]),
        }
        np.savez_compressed(output_dir / f"{method}_predictions.npz", **predictions[method])
    np.savez_compressed(output_dir / "clean_reference_predictions.npz", **predictions["clean_reference"])
    for index, row in enumerate(rows):
        for method in METHODS:
            row[f"score_{method}"] = float(np.asarray(fused_scores[method])[index])

    with (output_dir / "per_image.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    summary_rows = []
    for method, evaluation in evaluations.items():
        if method == "clean_reference":
            mean_psnr = None
            mean_ssim = None
        elif method == "degraded_only":
            mean_psnr = float(np.mean([row["psnr_bicubic"] for row in rows]))
            mean_ssim = float(np.mean([row["ssim_bicubic"] for row in rows]))
        elif method == "restored_only":
            mean_psnr = float(np.mean([row["psnr_swinir"] for row in rows]))
            mean_ssim = float(np.mean([row["ssim_swinir"] for row in rows]))
        else:
            mean_psnr = None  # score-level fusion has no single output image
            mean_ssim = None
        summary_rows.append(
            {
                "method": method,
                "test_count": len(test_samples),
                "train_count": len(selected),
                "calibration_count": len(calibration_indices),
                "mean_psnr": mean_psnr,
                "mean_ssim": mean_ssim,
                "image_threshold": (
                    clean_calibration["image_threshold"]
                    if method == "clean_reference"
                    else fusion_calibration["image_thresholds"][method]
                ),
                "pixel_threshold": (
                    clean_calibration["pixel_threshold"]
                    if method == "clean_reference"
                    else fusion_calibration["pixel_thresholds"][method]
                ),
                **evaluation["classification"],
                **evaluation["localization"],
            }
        )
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    restored = evaluations["restored_only"]
    result = {
        "model_spec": model_spec,
        "model_dir": str(model_dir),
        "fit_seconds_this_run": fit_seconds,
        **execution,
        "calibration_seconds": calibration_seconds,
        "test_seconds": test_seconds,
        "restoration": {"name": restorer.name, "checkpoint_sha256": checkpoint_sha256},
        "fusion_calibration": fusion_calibration,
        "clean_calibration": clean_calibration,
        "test_paths": [sample.relative_path.as_posix() for sample in test_samples],
        "methods": {
            method: {"evaluation": evaluation, "mean_psnr": row["mean_psnr"], "mean_ssim": row["mean_ssim"]}
            for method, evaluation, row in [
                (row["method"], evaluations[row["method"]], row) for row in summary_rows
            ]
        },
        "comparison_mean_vs_restored_only": {
            **{
                f"delta_{key}": _delta(
                    evaluations["mean_0.5_0.5"][section][key], restored[section][key]
                )
                for section, keys in (
                    ("classification", ("image_auroc", "image_f1")),
                    ("localization", ("pixel_auroc", "pixel_f1", "au_pro")),
                )
                for key in keys
            }
        },
        "comparison_max_vs_restored_only": {
            **{
                f"delta_{key}": _delta(
                    evaluations["max"][section][key], restored[section][key]
                )
                for section, keys in (
                    ("classification", ("image_auroc", "image_f1")),
                    ("localization", ("pixel_auroc", "pixel_f1", "au_pro")),
                )
                for key in keys
            }
        },
        "note": (
            "Detection-improvement branch: disjoint fit/calibration split, robust calibration, "
            "fixed fusion. F1 thresholds come from fused calibration normals only. hazelnut is "
            "development/exploration; final validation belongs on an unseen category."
        ),
    }
    (output_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run": run_name, "output": str(output_dir),
                      "comparison_mean_vs_restored_only": result["comparison_mean_vs_restored_only"],
                      "comparison_max_vs_restored_only": result["comparison_max_vs_restored_only"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
