from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import platform
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from sr_anomaly.dataset import ImageSample, MVTecADFolder
from sr_anomaly.degradations import apply_degradation
from sr_anomaly.evaluation import evaluate_predictions
from sr_anomaly.metrics import compute_quality_metrics
from sr_anomaly.real_models import PatchCoreTorchAdapter, SwinIRLightweightX2


VARIANTS = ("clean_reference", "no_restoration", "swinir_lightweight_x2")
SWINIR_CHECKPOINT_SHA256 = "193b229909ca89cd8b55de9c9e7fce146ae759d59dfcd78d8feb9dd1d6fa0fd7"
SWINIR_COMMIT = "6545850fbf8df298df73d81f3e8cba638787c8bd"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the paired MVTec bottle PatchCore/SwinIR CPU pilot")
    parser.add_argument("--data-root", type=Path, default=Path("data/external/MVTecAD"))
    parser.add_argument(
        "--patchcore-artifact",
        type=Path,
        default=Path("checkpoints/patchcore/bottle-seed11/weights/torch/patchcore_bottle.pt"),
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path("checkpoints/patchcore/bottle-seed11/calibration.json"),
    )
    parser.add_argument("--swinir-repository", type=Path, default=Path("third_party/SwinIR"))
    parser.add_argument(
        "--swinir-checkpoint",
        type=Path,
        default=Path("checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/cpu-pilot-bottle-x2-seed11"))
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--evaluation-size", type=int, default=256)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--tile", type=int, default=512)
    args = parser.parse_args()

    if args.evaluation_size < 16:
        parser.error("--evaluation-size must be at least 16")
    if args.limit is not None and args.limit < 2:
        parser.error("--limit must be at least 2 so both labels can be retained")
    import anomalib
    import torch

    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite experiment directory: {output_dir}")
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    detector_metadata = json.loads((args.patchcore_artifact.resolve().parents[2] / "metadata.json").read_text(encoding="utf-8"))
    detector_sha256 = _sha256(args.patchcore_artifact)
    if detector_sha256 != detector_metadata["artifact_sha256"]:
        raise ValueError("PatchCore artifact SHA-256 does not match its fit metadata")
    checkpoint_sha256 = _sha256(args.swinir_checkpoint)
    if checkpoint_sha256 != SWINIR_CHECKPOINT_SHA256:
        raise ValueError(f"Unexpected SwinIR checkpoint SHA-256: {checkpoint_sha256}")
    detector = PatchCoreTorchAdapter(args.patchcore_artifact.resolve(), align_to_input=False, trusted_local_artifact=True)
    restorer = SwinIRLightweightX2(
        args.swinir_repository.resolve(),
        args.swinir_checkpoint.resolve(),
        tile=args.tile,
    )
    samples = MVTecADFolder(args.data_root.resolve(), "bottle", "test").samples()
    if args.limit is not None:
        samples = _balanced_limit(samples, args.limit)
    (output_dir / "images").mkdir(parents=True)
    (output_dir / "predictions").mkdir()
    (output_dir / "evaluations").mkdir()

    collected = {variant: {"labels": [], "scores": [], "masks": [], "maps": []} for variant in VARIANTS}
    rows: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    total_start = perf_counter()
    for index, sample in enumerate(samples, 1):
        with Image.open(sample.path) as opened:
            original = opened.convert("RGB")
        if original.width % 2 or original.height % 2:
            raise ValueError(f"SwinIR x2 pilot requires even image dimensions: {sample.path} is {original.size}")
        degradation = apply_degradation(original, "low_resolution", severity=1, seed=args.seed)
        native_lr = degradation.restoration_input
        if native_lr is None:
            raise RuntimeError("low_resolution did not preserve its native LR image")
        restoration_start = perf_counter()
        restored = restorer.restore(native_lr)
        restoration_ms = (perf_counter() - restoration_start) * 1000.0
        if restored.size != original.size:
            raise ValueError(f"SwinIR output size mismatch for {sample.path}: {restored.size} != {original.size}")

        sample_dir = output_dir / "images" / sample.sample_id
        sample_dir.mkdir()
        native_path = sample_dir / "native_lr.png"
        degraded_path = sample_dir / "bicubic_x2.png"
        restored_path = sample_dir / "swinir_x2.png"
        native_lr.save(native_path)
        degradation.image.save(degraded_path)
        restored.save(restored_path)
        label = int(sample.metadata["label"])
        mask = _load_mask(sample, original.size)
        evaluation_mask = _resize_mask(mask, args.evaluation_size)
        quality = {
            "clean_reference": {"psnr": None, "ssim": None},
            "no_restoration": compute_quality_metrics(original, degradation.image, ("psnr", "ssim")),
            "swinir_lightweight_x2": compute_quality_metrics(original, restored, ("psnr", "ssim")),
        }
        images = {
            "clean_reference": original,
            "no_restoration": degradation.image,
            "swinir_lightweight_x2": restored,
        }
        for variant, image in images.items():
            inference_start = perf_counter()
            prediction = detector.predict(image)
            inference_ms = (perf_counter() - inference_start) * 1000.0
            if prediction.image_score is None or prediction.pixel_map is None:
                raise RuntimeError(f"PatchCore returned an empty prediction for {sample.path}")
            evaluation_map = _resize_map(prediction.pixel_map, args.evaluation_size)
            group = collected[variant]
            group["labels"].append(label)
            group["scores"].append(prediction.image_score)
            group["masks"].append(evaluation_mask)
            group["maps"].append(evaluation_map)
            rows.append(
                {
                    "sample_id": sample.sample_id,
                    "source_path": sample.relative_path.as_posix(),
                    "defect_type": sample.metadata["defect_type"],
                    "label": label,
                    "variant": variant,
                    "degradation": "none" if variant == "clean_reference" else "low_resolution",
                    "severity": None if variant == "clean_reference" else 1,
                    "scale_factor": None if variant == "clean_reference" else 2,
                    "seed": args.seed,
                    "restoration_model": "swinir_lightweight_x2" if variant == "swinir_lightweight_x2" else None,
                    "psnr": quality[variant]["psnr"],
                    "ssim": quality[variant]["ssim"],
                    "anomaly_score": prediction.image_score,
                    "restoration_ms": restoration_ms if variant == "swinir_lightweight_x2" else 0.0,
                    "inference_ms": inference_ms,
                }
            )
        manifests.append(
            {
                "sample_id": sample.sample_id,
                "source_path": sample.relative_path.as_posix(),
                "mask_path": sample.mask_path.relative_to(args.data_root.resolve()).as_posix() if sample.mask_path else None,
                "label": label,
                "degradation": "low_resolution",
                "severity": 1,
                "seed": args.seed,
                "parameters": degradation.parameters,
                "native_lr_path": native_path.relative_to(output_dir).as_posix(),
                "degraded_path": degraded_path.relative_to(output_dir).as_posix(),
                "restored_path": restored_path.relative_to(output_dir).as_posix(),
            }
        )
        print(f"[{index}/{len(samples)}] {sample.relative_path.as_posix()}", flush=True)

    evaluations: dict[str, dict[str, Any]] = {}
    for variant, group in collected.items():
        arrays = {key: np.asarray(value) for key, value in group.items()}
        np.savez_compressed(
            output_dir / "predictions" / f"{variant}.npz",
            labels=arrays["labels"],
            scores=arrays["scores"],
            masks=arrays["masks"],
            anomaly_maps=arrays["maps"],
        )
        evaluation = evaluate_predictions(
            arrays["labels"],
            arrays["scores"],
            arrays["masks"],
            arrays["maps"],
            image_threshold=float(calibration["image_threshold"]),
            pixel_threshold=float(calibration["pixel_threshold"]),
        )
        evaluations[variant] = evaluation
        (output_dir / "evaluations" / f"{variant}.json").write_text(
            json.dumps(evaluation, indent=2), encoding="utf-8"
        )

    _write_csv(output_dir / "results.csv", rows)
    summary = _summary(rows, evaluations)
    _write_csv(output_dir / "summary.csv", summary)
    _write_csv(output_dir / "comparison.csv", [_comparison(summary)])
    with (output_dir / "manifest.jsonl").open("w", encoding="utf-8") as handle:
        for record in manifests:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    metadata = {
        "experiment_id": output_dir.name,
        "dataset": "MVTec AD",
        "dataset_source": "https://www.mvtec.com/research-teaching/datasets/mvtec-ad",
        "dataset_license": "CC BY-NC-SA 4.0",
        "category": "bottle",
        "sample_count": len(samples),
        "seed": args.seed,
        "degradation": {"name": "low_resolution", "severity": 1, "scale_factor": 2},
        "detector": "PatchCore",
        "detector_artifact": args.patchcore_artifact.as_posix(),
        "detector_artifact_sha256": detector_sha256,
        "restoration": "SwinIR-S x2 lightweight",
        "restoration_source": "https://github.com/JingyunLiang/SwinIR",
        "restoration_commit": SWINIR_COMMIT,
        "restoration_checkpoint": args.swinir_checkpoint.as_posix(),
        "restoration_checkpoint_sha256": checkpoint_sha256,
        "expected_restoration_checkpoint_sha256": SWINIR_CHECKPOINT_SHA256,
        "evaluation_size": [args.evaluation_size, args.evaluation_size],
        "map_alignment": "raw anomaly map bilinear resize; original mask nearest-neighbor resize",
        "threshold_source": calibration["source"],
        "threshold_quantile": calibration["quantile"],
        "runtime_seconds": perf_counter() - total_start,
        "python": platform.python_version(),
        "anomalib": anomalib.__version__,
        "torch": torch.__version__,
    }
    (output_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(output_dir)


def _balanced_limit(samples: list[ImageSample], limit: int) -> list[ImageSample]:
    normal = [sample for sample in samples if sample.metadata["label"] == 0]
    anomalous = [sample for sample in samples if sample.metadata["label"] == 1]
    normal_count = min(len(normal), max(1, limit // 2))
    anomalous_count = min(len(anomalous), limit - normal_count)
    if not normal_count or not anomalous_count:
        raise ValueError("Limited pilot requires at least one normal and one anomalous sample")
    return sorted(normal[:normal_count] + anomalous[:anomalous_count], key=lambda sample: sample.relative_path.as_posix())


def _load_mask(sample: ImageSample, size: tuple[int, int]) -> Image.Image:
    if sample.mask_path is None:
        return Image.new("L", size, 0)
    with Image.open(sample.mask_path) as opened:
        mask = opened.convert("L")
    if mask.size != size:
        raise ValueError(f"Ground-truth mask size mismatch: {sample.mask_path} is {mask.size}, image is {size}")
    return mask


def _resize_mask(mask: Image.Image, size: int) -> np.ndarray:
    return np.asarray(mask.resize((size, size), Image.Resampling.NEAREST), dtype=np.uint8) > 0


def _resize_map(anomaly_map: np.ndarray, size: int) -> np.ndarray:
    return np.asarray(
        Image.fromarray(anomaly_map.astype(np.float32), mode="F").resize((size, size), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )


def _summary(rows: list[dict[str, Any]], evaluations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for variant in VARIANTS:
        selected = [row for row in rows if row["variant"] == variant]
        quality_rows = [row for row in selected if row["psnr"] is not None]
        classification = evaluations[variant]["classification"]
        localization = evaluations[variant]["localization"]
        summary.append(
            {
                "variant": variant,
                "samples": len(selected),
                "mean_psnr": float(np.mean([row["psnr"] for row in quality_rows])) if quality_rows else None,
                "mean_ssim": float(np.mean([row["ssim"] for row in quality_rows])) if quality_rows else None,
                "image_auroc": classification["image_auroc"],
                "image_f1": classification["image_f1"],
                "pixel_auroc": localization["pixel_auroc"],
                "pixel_f1": localization["pixel_f1"],
                "au_pro": localization["au_pro"],
                "mean_inference_ms": float(np.mean([row["inference_ms"] for row in selected])),
                "mean_restoration_ms": float(np.mean([row["restoration_ms"] for row in selected])),
            }
        )
    return summary


def _comparison(summary: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = next(row for row in summary if row["variant"] == "no_restoration")
    restored = next(row for row in summary if row["variant"] == "swinir_lightweight_x2")
    return {
        "baseline": baseline["variant"],
        "candidate": restored["variant"],
        "delta_psnr": restored["mean_psnr"] - baseline["mean_psnr"],
        "delta_ssim": restored["mean_ssim"] - baseline["mean_ssim"],
        "delta_image_auroc": restored["image_auroc"] - baseline["image_auroc"],
        "delta_pixel_auroc": restored["pixel_auroc"] - baseline["pixel_auroc"],
        "delta_au_pro": restored["au_pro"] - baseline["au_pro"],
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
