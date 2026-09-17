from __future__ import annotations

from copy import deepcopy
from itertools import product
import os
from pathlib import Path
from typing import Any

import yaml

from .config import load_config, validate_config
from .dataset import safe_component


MAX_MATRIX_RUNS = 256


def generate_experiment_matrix(matrix_path: str | Path, output_dir: str | Path) -> list[Path]:
    matrix_file = Path(matrix_path).resolve()
    with matrix_file.open("r", encoding="utf-8") as handle:
        matrix = yaml.safe_load(handle)
    if not isinstance(matrix, dict):
        raise ValueError("Matrix root must be a mapping")
    base_value = matrix.get("base_config")
    if not isinstance(base_value, str):
        raise ValueError("matrix.base_config must be a path string")
    base_path = (matrix_file.parent / base_value).resolve()
    base, base_dir = load_config(base_path)
    axes = matrix.get("axes", {})
    if not isinstance(axes, dict):
        raise ValueError("matrix.axes must be a mapping")

    values = {
        "degradations": _axis(axes, "degradations", [base["degradations"]]),
        "seeds": _axis(axes, "seeds", [base["experiment"].get("seed", 0)]),
        "restorations": _axis(axes, "restorations", [base.get("restoration")]),
        "detectors": _axis(axes, "detectors", [base.get("anomaly_detector")]),
    }
    projected = 1
    for axis in values.values():
        projected *= len(axis)
    max_runs = matrix.get("max_runs", 64)
    if not isinstance(max_runs, int) or not 1 <= max_runs <= MAX_MATRIX_RUNS:
        raise ValueError(f"max_runs must be between 1 and {MAX_MATRIX_RUNS}")
    if projected > max_runs:
        raise ValueError(f"Matrix expands to {projected} runs, above max_runs={max_runs}")

    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    prefix = safe_component(str(matrix.get("experiment_prefix", "matrix")), "experiment prefix")
    portable_base = _portable_paths(base, base_dir, destination)
    generated: list[Path] = []
    combinations = product(values["degradations"], values["seeds"], values["restorations"], values["detectors"])
    for index, (degradations, seed, restoration, detector) in enumerate(combinations, 1):
        config = deepcopy(portable_base)
        config["experiment"]["id"] = f"{prefix}-{index:03d}"
        config["experiment"]["seed"] = seed
        config["degradations"] = degradations
        config["restoration"] = restoration
        config["anomaly_detector"] = detector
        validate_config(config)
        target = destination / f"{prefix}-{index:03d}.yaml"
        if target.exists():
            raise FileExistsError(f"Generated config already exists: {target}")
        target.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
        generated.append(target)
    return generated


def _axis(axes: dict[str, Any], name: str, default: list[Any]) -> list[Any]:
    value = axes.get(name, default)
    if not isinstance(value, list) or not value:
        raise ValueError(f"matrix.axes.{name} must be a non-empty list")
    return value


def _portable_paths(config: dict[str, Any], base_dir: Path, destination: Path) -> dict[str, Any]:
    copied = deepcopy(config)
    for container, key in ((copied["dataset"], "root"), (copied, "output_root")):
        value = Path(container[key])
        resolved = value.resolve() if value.is_absolute() else (base_dir / value).resolve()
        container[key] = Path(os.path.relpath(resolved, destination)).as_posix()
    return copied

