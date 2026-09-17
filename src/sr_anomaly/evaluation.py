from __future__ import annotations

from typing import Any

import numpy as np
from skimage.measure import label as connected_components


def classification_metrics(
    labels: np.ndarray,
    scores: np.ndarray,
    threshold: float | None = None,
) -> dict[str, float | None]:
    labels, scores = _binary_inputs(labels, scores)
    result: dict[str, float | None] = {
        "image_auroc": binary_roc_auc(labels, scores),
        "image_f1": None,
        "image_threshold": threshold,
    }
    if threshold is not None:
        result["image_f1"] = binary_f1(labels, scores >= threshold)
    return result


def pixel_metrics(
    masks: np.ndarray,
    anomaly_maps: np.ndarray,
    threshold: float | None = None,
    max_fpr: float = 0.3,
    num_thresholds: int = 200,
) -> dict[str, float | None]:
    masks = np.asarray(masks)
    anomaly_maps = np.asarray(anomaly_maps, dtype=np.float64)
    if masks.shape != anomaly_maps.shape:
        raise ValueError(f"Masks and anomaly maps must have the same shape: {masks.shape} != {anomaly_maps.shape}")
    if masks.ndim == 2:
        masks = masks[None, ...]
        anomaly_maps = anomaly_maps[None, ...]
    if masks.ndim != 3:
        raise ValueError("Pixel evaluation expects [N, H, W] or [H, W] arrays")
    if not np.isfinite(anomaly_maps).all():
        raise ValueError("Anomaly maps must contain finite values")
    binary_masks = masks > 0
    result: dict[str, float | None] = {
        "pixel_auroc": binary_roc_auc(binary_masks.ravel(), anomaly_maps.ravel()),
        "au_pro": area_under_per_region_overlap(binary_masks, anomaly_maps, max_fpr, num_thresholds),
        "pixel_f1": None,
        "pixel_threshold": threshold,
    }
    if threshold is not None:
        result["pixel_f1"] = binary_f1(binary_masks.ravel(), (anomaly_maps >= threshold).ravel())
    return result


def evaluate_predictions(
    labels: np.ndarray,
    scores: np.ndarray,
    masks: np.ndarray | None = None,
    anomaly_maps: np.ndarray | None = None,
    image_threshold: float | None = None,
    pixel_threshold: float | None = None,
    max_fpr: float = 0.3,
) -> dict[str, Any]:
    result: dict[str, Any] = {"classification": classification_metrics(labels, scores, image_threshold)}
    if (masks is None) != (anomaly_maps is None):
        raise ValueError("masks and anomaly_maps must be provided together")
    result["localization"] = (
        pixel_metrics(masks, anomaly_maps, pixel_threshold, max_fpr) if masks is not None and anomaly_maps is not None else None
    )
    return result


def binary_roc_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    labels, scores = _binary_inputs(labels, scores)
    positive = labels == 1
    positive_count = int(positive.sum())
    negative_count = labels.size - positive_count
    if positive_count == 0 or negative_count == 0:
        raise ValueError("AUROC requires both normal and anomalous labels")
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    ranks = np.empty(scores.size, dtype=np.float64)
    start = 0
    while start < scores.size:
        end = start + 1
        while end < scores.size and sorted_scores[end] == sorted_scores[start]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end
    rank_sum = float(ranks[positive].sum())
    return (rank_sum - positive_count * (positive_count + 1) / 2.0) / (positive_count * negative_count)


def binary_f1(labels: np.ndarray, predictions: np.ndarray) -> float:
    labels = np.asarray(labels).ravel()
    predictions = np.asarray(predictions).ravel()
    if labels.shape != predictions.shape:
        raise ValueError("Labels and predictions must have the same shape")
    if not np.isin(labels, [0, 1, False, True]).all():
        raise ValueError("Labels must be binary")
    labels = labels.astype(bool)
    predictions = predictions.astype(bool)
    true_positive = int(np.logical_and(labels, predictions).sum())
    false_positive = int(np.logical_and(~labels, predictions).sum())
    false_negative = int(np.logical_and(labels, ~predictions).sum())
    denominator = 2 * true_positive + false_positive + false_negative
    return 0.0 if denominator == 0 else 2 * true_positive / denominator


def area_under_per_region_overlap(
    masks: np.ndarray,
    anomaly_maps: np.ndarray,
    max_fpr: float = 0.3,
    num_thresholds: int = 200,
) -> float:
    if not 0 < max_fpr <= 1:
        raise ValueError("max_fpr must be in (0, 1]")
    if num_thresholds < 3:
        raise ValueError("num_thresholds must be at least 3")
    masks = np.asarray(masks, dtype=bool)
    anomaly_maps = np.asarray(anomaly_maps, dtype=np.float64)
    if masks.shape != anomaly_maps.shape or masks.ndim != 3:
        raise ValueError("AU-PRO expects matching [N, H, W] arrays")
    normal_count = int((~masks).sum())
    if normal_count == 0:
        raise ValueError("AU-PRO requires normal pixels")
    regions: list[tuple[int, np.ndarray]] = []
    for image_index, mask in enumerate(masks):
        components = connected_components(mask, connectivity=1)
        for component_id in range(1, int(components.max()) + 1):
            regions.append((image_index, components == component_id))
    if not regions:
        raise ValueError("AU-PRO requires at least one anomalous region")

    finite_scores = anomaly_maps.ravel()
    unique_scores = np.unique(finite_scores)
    if unique_scores.size > num_thresholds - 2:
        unique_scores = np.unique(np.quantile(unique_scores, np.linspace(0.0, 1.0, num_thresholds - 2)))
    thresholds = np.concatenate(([np.inf], unique_scores[::-1], [-np.inf]))
    points: dict[float, float] = {}
    for threshold in thresholds:
        prediction = anomaly_maps >= threshold
        fpr = float(np.logical_and(prediction, ~masks).sum()) / normal_count
        pro = float(np.mean([prediction[image_index][region].mean() for image_index, region in regions]))
        points[fpr] = max(points.get(fpr, 0.0), pro)

    fprs = np.array(sorted(points), dtype=np.float64)
    pros = np.array([points[fpr] for fpr in fprs], dtype=np.float64)
    below = fprs <= max_fpr
    x = fprs[below]
    y = pros[below]
    if x.size == 0 or x[0] > 0:
        x = np.insert(x, 0, 0.0)
        y = np.insert(y, 0, 0.0)
    if x[-1] < max_fpr:
        above_indices = np.flatnonzero(fprs > max_fpr)
        boundary = np.interp(max_fpr, fprs, pros) if above_indices.size else y[-1]
        x = np.append(x, max_fpr)
        y = np.append(y, boundary)
    area = np.sum((x[1:] - x[:-1]) * (y[1:] + y[:-1]) * 0.5)
    return float(area / max_fpr)


def _binary_inputs(labels: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(labels).ravel()
    scores = np.asarray(scores, dtype=np.float64).ravel()
    if labels.shape != scores.shape:
        raise ValueError("Labels and scores must have the same shape")
    if not np.isin(labels, [0, 1, False, True]).all():
        raise ValueError("Labels must be binary")
    if not np.isfinite(scores).all():
        raise ValueError("Scores must contain finite values")
    return labels.astype(np.uint8), scores
