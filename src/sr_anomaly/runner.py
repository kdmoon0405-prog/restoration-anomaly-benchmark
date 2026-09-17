from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import platform
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image, __version__ as pillow_version

from . import __version__
from .config import load_config, resolve_from
from .dataset import ImageSample, build_dataset_adapter, safe_component, safe_join
from .degradations import apply_degradation
from .metrics import compute_quality_metrics
from .models import build_anomaly_detector, build_restoration


RESULT_FIELDS = [
    "experiment_id",
    "sample_id",
    "label",
    "mask_path",
    "source_path",
    "output_path",
    "degradation",
    "severity",
    "seed",
    "variant",
    "restoration_model",
    "anomaly_detector",
    "degradation_ms",
    "restoration_ms",
    "detector_ms",
    "metrics_ms",
    "total_ms",
    "psnr",
    "ssim",
    "lpips",
    "anomaly_score",
    "anomaly_metrics_status",
    "pixel_map_path",
]


def run_experiment(config_path: str | Path) -> Path:
    config, config_dir = load_config(config_path)
    experiment = config["experiment"]
    base_seed = int(experiment.get("seed", 0))
    experiment_id = safe_component(
        str(experiment.get("id") or f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"),
        "experiment id",
    )
    dataset_root = resolve_from(config_dir, config["dataset"]["root"])
    output_root = resolve_from(config_dir, config.get("output_root", "outputs"))
    run_dir = safe_join(output_root, experiment_id)
    if run_dir.exists():
        raise FileExistsError(f"Experiment output already exists: {run_dir}")
    images_dir = safe_join(run_dir, "images")
    images_dir.mkdir(parents=True)

    samples = build_dataset_adapter(config["dataset"], dataset_root, config_dir).samples()
    limit = config["dataset"].get("limit")
    if limit is not None:
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("dataset.limit must be a positive integer")
        samples = samples[:limit]
    if not samples:
        raise ValueError(f"No supported images found under {dataset_root}")

    restoration = build_restoration(config.get("restoration"))
    detector = build_anomaly_detector(config.get("anomaly_detector"))
    metric_names = config.get("metrics", ["psnr", "ssim"])
    config_bytes = Path(config_path).resolve().read_bytes()
    config_digest = sha256(config_bytes).hexdigest()
    reproducibility = {
        "framework_version": __version__,
        "config_sha256": config_digest,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pillow": pillow_version,
    }
    metadata = {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "base_seed": base_seed,
        "dataset": {
            "adapter": config["dataset"].get("adapter", "folder"),
            "root": config["dataset"]["root"],
            "recursive": bool(config["dataset"].get("recursive", True)),
            "sample_count": len(samples),
            "split": config["dataset"].get("split"),
            "category": config["dataset"].get("category"),
        },
        "model_configs": {
            "restoration": config.get("restoration") or {"name": "none"},
            "anomaly_detector": config.get("anomaly_detector") or {"name": "noop"},
        },
        "preprocessing": config.get("preprocessing", {}),
        "metrics": metric_names,
        "reproducibility": reproducibility,
    }
    _write_json(safe_join(run_dir, "run_metadata.json"), metadata)

    manifest: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for sample in samples:
        with Image.open(sample.path) as opened:
            original = opened.convert("RGB").copy()
        for degradation_index, spec in enumerate(config["degradations"]):
            name = spec["name"]
            severity = int(spec.get("severity", 1))
            seed = int(spec.get("seed", _stable_seed(base_seed, sample.relative_path.as_posix(), name, severity, degradation_index)))
            ground_truth = _ground_truth(sample, dataset_root)
            case_dir = safe_join(images_dir, f"{sample.sample_id}/{name}-s{severity}-seed{seed}")
            case_dir.mkdir(parents=True)

            start = perf_counter()
            degraded = apply_degradation(original, name, severity, seed)
            degradation_ms = _milliseconds(start)
            degraded_path = safe_join(case_dir, "degraded.png")
            degraded.image.save(degraded_path)
            manifest.append(
                _manifest_record(
                    experiment_id,
                    sample.sample_id,
                    sample.relative_path,
                    degraded_path.relative_to(run_dir),
                    "degraded",
                    name,
                    severity,
                    seed,
                    degraded.parameters,
                    "none",
                    reproducibility,
                    ground_truth,
                )
            )

            variants: list[tuple[str, Image.Image, str, float, Path]] = [
                ("no_restoration", degraded.image, "none", 0.0, degraded_path)
            ]
            if restoration:
                start = perf_counter()
                restored_image = restoration.restore(degraded.image)
                restoration_ms = _milliseconds(start)
                restored_path = safe_join(case_dir, f"restored-{safe_component(restoration.name, 'model name')}.png")
                restored_image.save(restored_path)
                manifest.append(
                    _manifest_record(
                        experiment_id,
                        sample.sample_id,
                        sample.relative_path,
                        restored_path.relative_to(run_dir),
                        "restored",
                        name,
                        severity,
                        seed,
                        degraded.parameters,
                        restoration.name,
                        reproducibility,
                        ground_truth,
                    )
                )
                variants.append(("restored", restored_image, restoration.name, restoration_ms, restored_path))

            for variant, final_image, restoration_name, restoration_ms, output_path in variants:
                start = perf_counter()
                prediction = detector.predict(final_image)
                detector_ms = _milliseconds(start)
                pixel_map_path = ""
                if prediction.pixel_map is not None:
                    map_path = safe_join(case_dir, f"{variant}-anomaly-map.npy")
                    np.save(map_path, prediction.pixel_map)
                    pixel_map_path = map_path.relative_to(run_dir).as_posix()
                start = perf_counter()
                quality = compute_quality_metrics(
                    original,
                    final_image,
                    metric_names,
                    str(config.get("lpips", {}).get("net", "alex")),
                    str(config.get("lpips", {}).get("device", "cpu")),
                )
                metrics_ms = _milliseconds(start)
                results.append(
                    {
                        "schema_version": "1.0",
                        "experiment_id": experiment_id,
                        "sample_id": sample.sample_id,
                        "ground_truth": ground_truth,
                        "source_path": sample.relative_path.as_posix(),
                        "output_path": output_path.relative_to(run_dir).as_posix(),
                        "degradation": {"name": name, "severity": severity, "seed": seed, "parameters": degraded.parameters},
                        "variant": variant,
                        "models": {"restoration": restoration_name, "anomaly_detector": detector.name},
                        "runtime_ms": {
                            "degradation": degradation_ms,
                            "restoration": restoration_ms,
                            "detector": detector_ms,
                            "metrics": metrics_ms,
                            "total": round(degradation_ms + restoration_ms + detector_ms + metrics_ms, 3),
                        },
                        "quality_metrics": quality,
                        "detection": {
                            "image_score": prediction.image_score,
                            "pixel_map_path": pixel_map_path or None,
                            "metrics_status": prediction.metadata.get("status", "raw_prediction_only"),
                            "dataset_metrics": None,
                        },
                    }
                )

    _write_jsonl(safe_join(run_dir, "manifest.jsonl"), manifest)
    _write_jsonl(safe_join(run_dir, "results.jsonl"), results)
    _write_results_csv(safe_join(run_dir, "results.csv"), results)
    return run_dir


def _stable_seed(base_seed: int, relative_path: str, name: str, severity: int, index: int) -> int:
    material = f"{base_seed}|{relative_path}|{name}|{severity}|{index}".encode("utf-8")
    return int.from_bytes(sha256(material).digest()[:4], "big")


def _milliseconds(start: float) -> float:
    return round((perf_counter() - start) * 1000.0, 3)


def _manifest_record(
    experiment_id: str,
    sample_id: str,
    source_path: Path,
    output_path: Path,
    stage: str,
    degradation: str,
    severity: int,
    seed: int,
    parameters: dict[str, Any],
    restoration_model: str,
    reproducibility: dict[str, Any],
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "sample_id": sample_id,
        "source_path": source_path.as_posix(),
        "output_path": output_path.as_posix(),
        "stage": stage,
        "degradation": {"name": degradation, "severity": severity, "seed": seed, "parameters": parameters},
        "restoration_model": restoration_model,
        "ground_truth": ground_truth,
        "reproducibility": reproducibility,
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def _ground_truth(sample: ImageSample, dataset_root: Path) -> dict[str, Any]:
    mask_path = sample.mask_path.relative_to(dataset_root).as_posix() if sample.mask_path else None
    return {"label": sample.metadata.get("label"), "mask_path": mask_path, "metadata": sample.metadata}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            degradation = row["degradation"]
            runtime = row["runtime_ms"]
            quality = row["quality_metrics"]
            detection = row["detection"]
            writer.writerow(
                {
                    "experiment_id": row["experiment_id"],
                    "sample_id": row["sample_id"],
                    "label": row["ground_truth"]["label"] if row["ground_truth"]["label"] is not None else "",
                    "mask_path": row["ground_truth"]["mask_path"] or "",
                    "source_path": row["source_path"],
                    "output_path": row["output_path"],
                    "degradation": degradation["name"],
                    "severity": degradation["severity"],
                    "seed": degradation["seed"],
                    "variant": row["variant"],
                    "restoration_model": row["models"]["restoration"],
                    "anomaly_detector": row["models"]["anomaly_detector"],
                    "degradation_ms": runtime["degradation"],
                    "restoration_ms": runtime["restoration"],
                    "detector_ms": runtime["detector"],
                    "metrics_ms": runtime["metrics"],
                    "total_ms": runtime["total"],
                    "psnr": quality.get("psnr", ""),
                    "ssim": quality.get("ssim", ""),
                    "lpips": quality.get("lpips", ""),
                    "anomaly_score": detection["image_score"] if detection["image_score"] is not None else "",
                    "anomaly_metrics_status": detection["metrics_status"],
                    "pixel_map_path": detection["pixel_map_path"] or "",
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a restoration/anomaly experiment")
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    print(run_experiment(args.config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
