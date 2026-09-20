"""Score-range calibration and fixed fusion for degraded/restored anomaly maps.

The detection-improvement experiment keeps test labels strictly unseen:

1. Split normal training images into disjoint fit/calibration lists with a fixed
   seed (default 80/20). The same lists are reused for every compared method.
2. Fit per-variant robust normalization (median/IQR) on calibration normal
   images only, separately for degraded and restored scores/maps.
3. Fuse with fixed rules (mean 0.5:0.5, max) and derive F1 thresholds from the
   fused calibration scores. No test labels are used anywhere.

This module is pure NumPy so the math can be unit-tested without PyTorch,
FAISS, or the MVTec dataset.
"""

from __future__ import annotations

import random
from typing import Literal

import numpy as np

FusionMethod = Literal["degraded_only", "restored_only", "mean_0.5_0.5", "max"]

METHODS: tuple[FusionMethod, ...] = ("degraded_only", "restored_only", "mean_0.5_0.5", "max")


def split_train_calibration(count: int, train_ratio: float, seed: int) -> tuple[list[int], list[int]]:
    """Split ``count`` items into disjoint train/calibration index lists.

    The split is deterministic for a given seed. ``train_ratio`` 0.8 on 391
    images gives 313 train / 78 calibration (rounded).
    """
    if count < 2:
        raise ValueError("split requires at least 2 images")
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be in (0, 1)")
    train_count = int(round(count * train_ratio))
    train_count = min(max(train_count, 1), count - 1)
    order = list(range(count))
    random.Random(seed).shuffle(order)
    train = sorted(order[:train_count])
    calibration = sorted(order[train_count:])
    return train, calibration


def robust_params(values: np.ndarray) -> dict[str, float | str]:
    """Fit median/IQR normalization on calibration normal values.

    Falls back to standard deviation and then to unit scale when the IQR
    (or std) is numerically zero, and records which path was taken.
    """
    flat = np.asarray(values, dtype=np.float64).ravel()
    if flat.size == 0:
        raise ValueError("robust_params requires at least one value")
    if not np.isfinite(flat).all():
        raise ValueError("robust_params requires finite values")
    median = float(np.median(flat))
    q25 = float(np.quantile(flat, 0.25))
    q75 = float(np.quantile(flat, 0.75))
    iqr = q75 - q25
    if iqr > 1e-12:
        return {"median": median, "scale": float(iqr), "q25": q25, "q75": q75, "method": "iqr"}
    std = float(np.std(flat))
    if std > 1e-12:
        return {"median": median, "scale": std, "q25": q25, "q75": q75, "method": "std_fallback"}
    return {"median": median, "scale": 1.0, "q25": q25, "q75": q75, "method": "unit_fallback"}


def normalize(values: np.ndarray, params: dict[str, float | str]) -> np.ndarray:
    """Apply fitted robust normalization: (x - median) / scale."""
    median = float(params["median"])
    scale = float(params["scale"])
    if not np.isfinite(median) or not np.isfinite(scale) or scale <= 0:
        raise ValueError(f"invalid normalization params: {params!r}")
    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError("normalize requires finite values")
    return (array - median) / scale


def fuse_pair(
    degraded: np.ndarray,
    restored: np.ndarray,
    method: FusionMethod,
    weight: float = 0.5,
) -> np.ndarray:
    """Fuse one degraded/restored score or map pair with a fixed rule."""
    deg = np.asarray(degraded, dtype=np.float64)
    res = np.asarray(restored, dtype=np.float64)
    if deg.shape != res.shape:
        raise ValueError(f"fusion inputs must share a shape: {deg.shape} != {res.shape}")
    if method == "degraded_only":
        return deg
    if method == "restored_only":
        return res
    if method == "mean_0.5_0.5":
        if weight != 0.5:
            raise ValueError("mean_0.5_0.5 requires weight 0.5; other weights are a separate experiment")
        return 0.5 * deg + 0.5 * res
    if method == "max":
        return np.maximum(deg, res)
    raise ValueError(f"unknown fusion method: {method}")


def quantile_threshold(values: np.ndarray, quantile: float) -> float:
    """Fixed F1 threshold from calibration values only (never test labels)."""
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must be in (0, 1)")
    flat = np.asarray(values, dtype=np.float64).ravel()
    if flat.size == 0:
        raise ValueError("quantile_threshold requires at least one value")
    if not np.isfinite(flat).all():
        raise ValueError("quantile_threshold requires finite values")
    return float(np.quantile(flat, quantile))


def fit_fusion_calibration(
    degraded_scores: np.ndarray,
    restored_scores: np.ndarray,
    degraded_pixels: np.ndarray,
    restored_pixels: np.ndarray,
    quantile: float = 0.99,
) -> dict:
    """Fit per-variant normalization and per-method thresholds from calibration.

    ``degraded_scores``/``restored_scores`` are [N_cal] image scores and
    ``degraded_pixels``/``restored_pixels`` are pooled calibration pixels.
    Returns JSON-serializable params plus fused-threshold calibration values.
    """
    deg_scores = np.asarray(degraded_scores, dtype=np.float64).ravel()
    res_scores = np.asarray(restored_scores, dtype=np.float64).ravel()
    if deg_scores.shape != res_scores.shape or deg_scores.size == 0:
        raise ValueError("calibration image scores must be nonempty paired vectors")
    deg_pixels = np.asarray(degraded_pixels, dtype=np.float64).ravel()
    res_pixels = np.asarray(restored_pixels, dtype=np.float64).ravel()
    if deg_pixels.size == 0 or res_pixels.size == 0:
        raise ValueError("calibration pixels must be nonempty")

    image_params = {"degraded": robust_params(deg_scores), "restored": robust_params(res_scores)}
    pixel_params = {"degraded": robust_params(deg_pixels), "restored": robust_params(res_pixels)}
    z_deg_scores = normalize(deg_scores, image_params["degraded"])
    z_res_scores = normalize(res_scores, image_params["restored"])
    z_deg_pixels = normalize(deg_pixels, pixel_params["degraded"])
    z_res_pixels = normalize(res_pixels, pixel_params["restored"])

    image_thresholds: dict[str, float] = {}
    pixel_thresholds: dict[str, float] = {}
    for method in METHODS:
        image_thresholds[method] = quantile_threshold(
            fuse_pair(z_deg_scores, z_res_scores, method), quantile
        )
        pixel_thresholds[method] = quantile_threshold(
            fuse_pair(z_deg_pixels, z_res_pixels, method), quantile
        )
    return {
        "quantile": float(quantile),
        "normalization": "robust_median_iqr_per_variant",
        "image": image_params,
        "pixel": pixel_params,
        "image_thresholds": image_thresholds,
        "pixel_thresholds": pixel_thresholds,
    }


def fuse_test_scores(
    degraded_scores: np.ndarray,
    restored_scores: np.ndarray,
    calibration: dict,
) -> dict[str, np.ndarray]:
    """Normalize test image scores with frozen calibration and fuse all methods."""
    z_deg = normalize(degraded_scores, calibration["image"]["degraded"])
    z_res = normalize(restored_scores, calibration["image"]["restored"])
    return {method: fuse_pair(z_deg, z_res, method) for method in METHODS}


def fuse_test_maps(
    degraded_maps: np.ndarray,
    restored_maps: np.ndarray,
    calibration: dict,
) -> dict[str, np.ndarray]:
    """Normalize test anomaly maps with frozen calibration and fuse all methods."""
    z_deg = normalize(degraded_maps, calibration["pixel"]["degraded"])
    z_res = normalize(restored_maps, calibration["pixel"]["restored"])
    return {method: fuse_pair(z_deg, z_res, method) for method in METHODS}
