"""Normal-bank domain study primitives; no torch/model imports at module import time."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
from typing import Any, Iterable

import numpy as np

from .evaluation import area_under_per_region_overlap, evaluate_predictions
from .fusion import normalize, quantile_threshold, robust_params

BANK_DOMAINS = ("clean", "swinir_restored")
QUERY_DOMAINS = ("bicubic_x4", "swinir_x4")
SEEDS = (11, 23, 37)
CALIBRATION_QUANTILE = 0.99
MAX_FPR = 0.3
SCHEMA_VERSION = 1


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_array(values: np.ndarray) -> str:
    array = np.ascontiguousarray(values)
    if array.dtype.hasobject:
        raise ValueError("Object arrays cannot be hashed as study artifacts")
    return hashlib.sha256(memoryview(array).cast("B")).hexdigest()


def expected_condition_order(samples: Iterable[str]) -> list[tuple[str, str, str]]:
    sample_ids = tuple(samples)
    if (not sample_ids or any(not isinstance(sample, str) or not sample for sample in sample_ids)
            or len(set(sample_ids)) != len(sample_ids)):
        raise ValueError("A nonempty, unique ordered sample inventory is required")
    return [
        (bank_domain, query_domain, sample)
        for bank_domain in BANK_DOMAINS
        for query_domain in QUERY_DOMAINS
        for sample in sample_ids
    ]


def validate_pair_identity(left: dict[str, Any], right: dict[str, Any]) -> None:
    """Require both bank domains to use the same ordered query identity and inputs."""
    for key in ("samples", "query_input_sha256", "query_domain_sha256"):
        if left.get(key) != right.get(key):
            raise ValueError(f"Bank-domain pair has different query identity: {key}")
    if left.get("query_domains") != list(QUERY_DOMAINS) or right.get("query_domains") != list(QUERY_DOMAINS):
        raise ValueError("Unexpected query domain order")


def fit_cell_calibration(
    labels: np.ndarray,
    scores: np.ndarray,
    maps: np.ndarray,
    *,
    quantile: float = CALIBRATION_QUANTILE,
) -> dict[str, Any]:
    """Fit existing robust normalization and quantile threshold on normal cal only."""
    labels = np.asarray(labels).ravel()
    scores = np.asarray(scores, dtype=np.float64).ravel()
    maps = np.asarray(maps, dtype=np.float32)
    if labels.size == 0 or not np.isin(labels, [0, False]).all():
        raise ValueError("Bank-domain calibration accepts normal calibration samples only")
    if scores.shape != labels.shape or maps.ndim != 3 or maps.shape[0] != labels.size:
        raise ValueError("Calibration score/map inventory mismatch")
    if maps.shape[1] < 1 or maps.shape[2] < 1:
        raise ValueError("Calibration maps must have positive spatial dimensions")
    if not np.isfinite(scores).all() or not np.isfinite(maps).all():
        raise ValueError("Calibration scores/maps must be finite")
    image = robust_params(scores)
    pixel = robust_params(maps)
    normalized_scores = normalize(scores, image)
    normalized_maps = normalize(maps, pixel)
    return {
        "quantile": float(quantile),
        "normalization": "existing_median_iqr_std_then_unit",
        "image": image,
        "pixel": pixel,
        "image_threshold": quantile_threshold(normalized_scores, quantile),
        "pixel_threshold": quantile_threshold(normalized_maps, quantile),
        "calibration_count": int(labels.size),
        "calibration_pixel_count": int(maps.size),
        "map_shape": list(maps.shape[1:]),
    }


def evaluate_cell(
    labels: np.ndarray,
    scores: np.ndarray,
    masks: np.ndarray,
    maps: np.ndarray,
    calibration: dict[str, Any],
    samples: Iterable[str],
    *,
    max_fpr: float = MAX_FPR,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    labels = np.asarray(labels).ravel()
    scores = np.asarray(scores, dtype=np.float64).ravel()
    masks = np.asarray(masks, dtype=bool)
    maps = np.asarray(maps, dtype=np.float32)
    sample_ids = tuple(samples)
    if labels.size == 0 or labels.shape != scores.shape or len(sample_ids) != labels.size:
        raise ValueError("Test sample/label/score inventory mismatch")
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("Test sample IDs must be unique")
    if masks.shape != maps.shape or masks.ndim != 3 or masks.shape[0] != labels.size:
        raise ValueError("Test mask/map inventory mismatch")
    if tuple(maps.shape[1:]) != tuple(calibration["map_shape"]):
        raise ValueError("Test map shape differs from calibration")
    if not np.isin(labels, [0, 1]).all() or not np.isfinite(scores).all() or not np.isfinite(maps).all():
        raise ValueError("Test labels must be binary and scores/maps finite")
    if not np.array_equal(masks.reshape(len(masks), -1).any(axis=1), labels.astype(bool)):
        raise ValueError("Test mask occupancy differs from image labels")

    normalized_scores = normalize(scores, calibration["image"])
    normalized_maps = normalize(maps, calibration["pixel"])
    metrics = evaluate_predictions(
        labels,
        normalized_scores,
        masks,
        normalized_maps,
        image_threshold=float(calibration["image_threshold"]),
        pixel_threshold=float(calibration["pixel_threshold"]),
        max_fpr=max_fpr,
    )
    rows: list[dict[str, Any]] = []
    for index, sample in enumerate(sample_ids):
        per_image = None
        if labels[index] == 1:
            per_image = area_under_per_region_overlap(
                masks[index:index + 1], normalized_maps[index:index + 1], max_fpr=max_fpr
            )
        rows.append({
            "sample": sample,
            "label": int(labels[index]),
            "normalized_score": float(normalized_scores[index]),
            "per_image_aupro": per_image,
        })
    return metrics, rows


def available_ram_bytes() -> int:
    if os.name == "nt":
        import ctypes

        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong)
                for name in ("total", "available", "page_total", "page_available",
                             "virtual", "virtual_available", "extended")
            ]

        value = Memory()
        value.length = ctypes.sizeof(value)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            raise OSError("Cannot read available system RAM")
        return int(value.available)
    return int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))


def output_disk_plan(
    calibration_count: int,
    test_count: int,
    *,
    image_size: int = 224,
    reserve_bytes: int = 2 * 1024**3,
) -> dict[str, int | bool]:
    if min(calibration_count, test_count, image_size, reserve_bytes) < 1:
        raise ValueError("Positive output and reserve dimensions are required")
    prediction_count = calibration_count + test_count
    # Two bank domains × two query domains, each with one float32 native map.
    raw_maps = len(BANK_DOMAINS) * len(QUERY_DOMAINS) * prediction_count * image_size * image_size * 4
    scores = len(BANK_DOMAINS) * len(QUERY_DOMAINS) * prediction_count * 8
    masks = test_count * image_size * image_size
    payload = raw_maps + scores + masks
    return {
        "raw_prediction_payload_scenario_bytes": payload,
        "reserve_bytes": reserve_bytes,
        "required_free_bytes": payload + reserve_bytes,
        "estimated_not_measured": True,
    }


def check_output_disk(plan: dict[str, int | bool], *, free_bytes: int) -> None:
    if free_bytes < int(plan["required_free_bytes"]):
        raise OSError(
            "BANK_STUDY_BLOCKED_DISK: raw predictions plus reserve "
            f"requires {plan['required_free_bytes']} bytes free; observed {free_bytes}"
        )


def bank_fit_plan(
    fit_count: int,
    *,
    patches_per_image: int = 784,
    dimension: int = 1024,
    batch_size: int = 8,
    reserve_bytes: int = 2 * 1024**3,
) -> dict[str, int | bool]:
    if min(fit_count, patches_per_image, dimension, batch_size, reserve_bytes) < 1:
        raise ValueError("Positive fit and memory-plan dimensions are required")
    vectors = fit_count * patches_per_image
    bank_bytes = vectors * dimension * np.dtype(np.float32).itemsize
    query_chunk_bytes = batch_size * patches_per_image * dimension * np.dtype(np.float32).itemsize
    # PatchCore fit retains per-image embeddings while concatenating and building
    # the CPU IndexFlatL2. This is a conservative payload scenario, not a peak.
    visible_fit_payload = 3 * bank_bytes + query_chunk_bytes
    return {
        "fit_vectors": vectors,
        "bank_bytes": bank_bytes,
        "query_chunk_bytes": query_chunk_bytes,
        "visible_fit_payload_scenario_bytes": visible_fit_payload,
        "reserve_bytes": reserve_bytes,
        "required_available_ram_bytes": visible_fit_payload + reserve_bytes,
        "estimated_not_measured": True,
    }


def check_fit_ram(plan: dict[str, int | bool], *, available_bytes: int | None = None) -> None:
    available = available_ram_bytes() if available_bytes is None else int(available_bytes)
    if available < int(plan["required_available_ram_bytes"]):
        raise MemoryError(
            "BANK_FIT_BLOCKED_MEMORY: PatchCore fit payload scenario plus reserve "
            f"requires {plan['required_available_ram_bytes']} bytes available; observed {available}"
        )


def safe_artifact_path(root: str | Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    windows_relative = PureWindowsPath(relative)
    if (not relative or "\0" in relative or rel.is_absolute() or windows_relative.is_absolute()
            or windows_relative.drive or chr(92) in relative or ":" in relative
            or any(part in ("", ".", "..") for part in rel.parts)):
        raise ValueError("Unsafe relative artifact path")
    root_path = Path(root).resolve()
    candidate = root_path.joinpath(*rel.parts).resolve()
    if not candidate.is_relative_to(root_path):
        raise ValueError("Artifact escapes run directory")
    return candidate


def write_json_atomic(path: str | Path, value: dict[str, Any]) -> None:
    path = Path(path)
    temporary = path.with_name(path.name + ".partial")
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + chr(10)
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_status(run_dir: str | Path, state: dict[str, Any]) -> None:
    write_json_atomic(Path(run_dir) / "status.json", state)


def verify_complete_run(run_dir: str | Path, expected_order: Iterable[tuple[str, str, str]]) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    state = json.loads((root / "status.json").read_text(encoding="utf-8"))
    if state.get("status") != "COMPLETE" or state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Study run is not a complete supported artifact")
    observed = [
        (row.get("bank_domain"), row.get("query_domain"), row.get("sample"))
        for row in state.get("prediction_rows", [])
    ]
    if observed != list(expected_order):
        raise ValueError("Prediction sample/bank/query order differs from frozen inventory")
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("Complete run has no payload artifact manifest")
    seen: set[str] = set()
    for item in artifacts:
        relative = item.get("file")
        if relative in seen:
            raise ValueError("Duplicate artifact path in manifest")
        seen.add(relative)
        path = safe_artifact_path(root, relative)
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Missing or changed study payload: {relative}")
    return state
