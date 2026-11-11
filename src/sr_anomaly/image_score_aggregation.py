"""Image-score aggregation rules on stored post-processed maps (docs/IMAGE_SCORE_AGGREGATION_V0.1.md).

Pure functions only: no model, bank, FAISS, GT mask or image access. Calibration and metrics reuse
sr_anomaly.fusion (robust median/IQR, q0.99) and sr_anomaly.evaluation exactly as the realistic runners do.
"""
from __future__ import annotations

from fractions import Fraction
import math

import numpy as np

from .evaluation import classification_metrics
from .fusion import normalize, quantile_threshold, robust_params

QUANTILE = 0.99
RULES = ("original", "map_max", "top0.1pct_mean", "top0.5pct_mean", "top1pct_mean")
TOP_FRACTIONS = {"top0.1pct_mean": "0.001", "top0.5pct_mean": "0.005", "top1pct_mean": "0.01"}
RESTORERS = ("bicubic_x4", "swinir_x4", "realesrnet_x4plus", "realesrgan_x4plus")
CATEGORIES = ("hazelnut", "screw")


def top_k(fraction: str, height: int, width: int) -> int:
    """k = ceil(fraction * H * W) with exact rational arithmetic (fraction given as a decimal string)."""
    k = math.ceil(Fraction(fraction) * height * width)
    if not 1 <= k <= height * width:
        raise ValueError("top-k outside the map")
    return k


def aggregate(rule: str, maps: np.ndarray, stored_scores: np.ndarray) -> np.ndarray:
    """Image scores (float64) for one rule; maps are N x H x W, stored_scores are the original image scores."""
    maps = np.asarray(maps)
    if maps.ndim != 3 or len(maps) != len(stored_scores):
        raise ValueError("maps must be N x H x W aligned with stored scores")
    if rule == "original":
        return np.asarray(stored_scores, dtype=np.float64).copy()
    flat = maps.reshape(len(maps), -1)
    if rule == "map_max":
        return flat.max(axis=1).astype(np.float64)
    if rule in TOP_FRACTIONS:
        k = top_k(TOP_FRACTIONS[rule], maps.shape[1], maps.shape[2])
        out = np.empty(len(flat), dtype=np.float64)
        for i, row in enumerate(flat):  # one image at a time keeps the float64 working copy small
            values = row.astype(np.float64)
            out[i] = np.partition(values, values.size - k)[values.size - k:].mean()
        return out
    raise ValueError(f"unknown rule {rule!r}")


def evaluate_rule(calibration_scores: np.ndarray, test_scores: np.ndarray, test_labels: np.ndarray) -> dict:
    """Calibration-normal robust fit + q0.99, then the existing image metrics (same ops as _unit_metrics)."""
    params = robust_params(np.asarray(calibration_scores))
    threshold = quantile_threshold(normalize(np.asarray(calibration_scores), params), QUANTILE)
    labels = np.asarray(test_labels)
    scores = normalize(np.asarray(test_scores), params)
    metrics = classification_metrics(labels, scores, threshold)
    flagged = scores >= threshold
    return {"params": params, "threshold": threshold, "normalized_test": scores, "flagged": flagged,
            "normalized_calibration": normalize(np.asarray(calibration_scores), params),
            "metrics": {**metrics,
                        "image_false_alarm_rate_test_normal": float(flagged[labels == 0].mean()),
                        "image_miss_rate_test_anomaly": float((~flagged[labels == 1]).mean())}}


def pixel_anchor(calibration_maps: np.ndarray) -> dict:
    """Refit the stored pixel calibration from calibration maps (float64, as the runners did)."""
    cal = np.asarray(calibration_maps, dtype=np.float64)
    params = robust_params(cal)
    return {"params": params, "threshold": quantile_threshold(normalize(cal, params), QUANTILE)}


def unit_plan(root_prefix: str = "outputs") -> list[dict]:
    """Fixed 40-unit list (category x family/run x condition x restorer); paths repository-relative."""
    units = []
    for category in CATEGORIES:
        runs = [("realistic_lr_v1", None, f"{root_prefix}/realistic-degradation/{category}-v1", ("none",))]
        runs += [("realistic_lr_noise_v2", seed, f"{root_prefix}/realistic-noise-v2/{category}-noise{seed}",
                  ("noise_s5", "noise_s15")) for seed in (23, 37)]
        for family, seed, run_dir, conditions in runs:
            for condition in conditions:
                for restorer in RESTORERS:
                    units.append(dict(category=category, family=family, noise_seed=seed, split_seed=11,
                                      condition=condition, restorer=restorer, run_dir=run_dir,
                                      unit=f"{condition}__{restorer}",
                                      unit_id=f"{category}__{family}__{'v1' if seed is None else f'noise{seed}'}__{condition}__{restorer}"))
    return units


def payload_plan_bytes(n_calibration: int, n_test: int, height: int, width: int) -> int:
    """Real per-unit envelope: float32 maps + float64 calibration copy + normalized float64 copy + 64 MiB."""
    pixels = height * width
    return (n_calibration + n_test) * pixels * 4 + 2 * n_calibration * pixels * 8 + 64 * 1024**2
