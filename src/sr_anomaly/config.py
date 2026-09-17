from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ALLOWED_METRICS = {"psnr", "ssim", "lpips"}


def load_config(path: str | Path) -> tuple[dict[str, Any], Path]:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("Config root must be a mapping")
    validate_config(config)
    return config, config_path.parent


def validate_config(config: dict[str, Any]) -> None:
    experiment = _mapping(config, "experiment")
    if not isinstance(experiment.get("seed", 0), int):
        raise ValueError("experiment.seed must be an integer")

    dataset = _mapping(config, "dataset")
    if not isinstance(dataset.get("root"), str) or not dataset["root"].strip():
        raise ValueError("dataset.root must be a non-empty path string")

    degradations = config.get("degradations")
    if not isinstance(degradations, list) or not degradations:
        raise ValueError("degradations must be a non-empty list")
    for item in degradations:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("Each degradation needs a name")
        severity = item.get("severity", 1)
        if not isinstance(severity, int) or not 1 <= severity <= 5:
            raise ValueError("Degradation severity must be an integer from 1 to 5")

    metrics = config.get("metrics", ["psnr", "ssim"])
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("metrics must be a non-empty list")
    unknown = set(metrics) - ALLOWED_METRICS
    if unknown:
        raise ValueError(f"Unsupported metrics: {sorted(unknown)}")

    output_root = config.get("output_root", "outputs")
    if not isinstance(output_root, str) or not output_root.strip():
        raise ValueError("output_root must be a non-empty path string")

    for key in ("restoration", "anomaly_detector"):
        value = config.get(key)
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"{key} must be a mapping when provided")


def resolve_from(base_dir: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def _mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value

