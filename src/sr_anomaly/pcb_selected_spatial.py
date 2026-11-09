"""Exploratory descriptors for fixed selected maps, never a detector or gate."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from skimage.measure import label as connected_components

from .analysis_io import digest, relative_source
from .fusion import normalize
from .pcb_tiling import tile_boxes


VARIANTS = ("clean", "bicubic_x4", "swinir_x4")


def load_map(root, name, expected_sha256, shape):
    path = relative_source(root, name)
    if digest(path) != expected_sha256:
        raise ValueError("Selected map SHA256 mismatch")
    values = np.load(path, mmap_mode="r", allow_pickle=False)
    if values.shape != tuple(shape) or values.dtype != np.float32 or not np.isfinite(values).all():
        raise ValueError("Selected map shape/dtype/finite mismatch")
    return values


def seam_geometry(shape):
    height, width = shape
    boxes = tile_boxes((width, height))
    xs = sorted({x for box in boxes for x in (box[0], box[2]) if 0 < x < width})
    ys = sorted({y for box in boxes for y in (box[1], box[3]) if 0 < y < height})
    seam = np.zeros(shape, dtype=bool)
    for x in xs:
        seam[:, x - 1:x + 1] = True
    for y in ys:
        seam[y - 1:y + 1, :] = True
    return xs, ys, seam


def _centroid(values, background_mean):
    weights = np.maximum(values - background_mean, 0)
    mass = float(weights.sum())
    if mass == 0:
        return None, None
    return (float(weights.sum(axis=0) @ np.arange(values.shape[1]) / mass),
            float(weights.sum(axis=1) @ np.arange(values.shape[0]) / mass))


def _seam_gradient(values, xs, ys):
    total_sum, total_count, seam_sum, seam_count = 0.0, 0, 0.0, 0
    for axis, edges in ((1, xs), (0, ys)):
        gradients = np.abs(np.diff(values, axis=axis))
        chosen = np.take(gradients, np.asarray(edges, dtype=int) - 1, axis=axis)
        total_sum += float(gradients.sum())
        total_count += gradients.size
        seam_sum += float(chosen.sum())
        seam_count += chosen.size
    return dict(seam_gradient_mean=seam_sum / seam_count if seam_count else None,
                nonseam_gradient_mean=(total_sum - seam_sum) / (total_count - seam_count)
                if total_count > seam_count else None)


def describe_maps(maps, mask, calibration):
    if set(maps) != set(VARIANTS) or set(calibration) != set(VARIANTS):
        raise ValueError("Exactly clean/bicubic_x4/swinir_x4 maps and calibration required")
    mask = np.asarray(mask)
    if mask.ndim != 2 or not np.isin(mask, [0, 1]).all():
        raise ValueError("Native binary HW mask required")
    mask = mask.astype(bool)
    if not (~mask).any():
        raise ValueError("Background pixels required")
    xs, ys, seam = seam_geometry(mask.shape)
    normalized, descriptors = {}, {}
    for variant in VARIANTS:
        raw = np.asarray(maps[variant])
        if raw.dtype != np.float32 or raw.shape != mask.shape or not np.isfinite(raw).all():
            raise ValueError("Native finite float32 maps matching GT required")
        values = normalize(raw, calibration[variant]["pixel"])
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite normalized map")
        normalized[variant] = values
        row = {}
        for prefix, array in (("raw", raw), ("normalized", values)):
            bg = float(np.mean(array[~mask], dtype=np.float64))
            roi = float(np.mean(array[mask], dtype=np.float64)) if mask.any() else None
            row.update({f"{prefix}_roi_mean": roi, f"{prefix}_background_mean": bg,
                        f"{prefix}_roi_bg_gap": roi - bg if roi is not None else None})
        row["centroid_x"], row["centroid_y"] = _centroid(values, row["normalized_background_mean"])
        row.update(_seam_gradient(values, xs, ys))
        descriptors[variant] = row

    bic, swin = normalized["bicubic_x4"], normalized["swinir_x4"]
    correlation = None
    if np.std(bic) > 0 and np.std(swin) > 0:
        correlation = float(np.corrcoef(bic.ravel(), swin.ravel())[0, 1])
    delta = {"map_correlation": correlation}
    for key in ("raw_roi_bg_gap", "normalized_roi_bg_gap"):
        a, b = descriptors["bicubic_x4"][key], descriptors["swinir_x4"][key]
        delta[f"delta_{key}"] = b - a if a is not None and b is not None else None
    centroids = [(descriptors[v]["centroid_x"], descriptors[v]["centroid_y"])
                 for v in ("bicubic_x4", "swinir_x4")]
    delta["centroid_displacement_pixels"] = (float(np.hypot(centroids[1][0] - centroids[0][0],
        centroids[1][1] - centroids[0][1])) if all(x is not None for pair in centroids for x in pair) else None)
    components = connected_components(mask, connectivity=1)
    component_rows = []
    for component_id in range(1, int(components.max()) + 1):
        roi = components == component_id
        row = dict(component_id=component_id, area_pixels=int(roi.sum()))
        for variant in VARIANTS:
            values = normalized[variant][roi]
            row[f"{variant}_mean"] = float(values.mean())
            row[f"{variant}_max"] = float(values.max())
        row["delta_mean_swinir_minus_bicubic"] = row["swinir_x4_mean"] - row["bicubic_x4_mean"]
        component_rows.append(row)
    return dict(variants=descriptors, comparison=delta, components=component_rows,
        gt_area_pixels=int(mask.sum()), gt_on_seam_pixels=int((mask & seam).sum()),
        gt_on_seam_ratio=float((mask & seam).sum() / mask.sum()) if mask.any() else None,
        connectivity=4), normalized, seam


def render_case(output, sample, rgb, mask, normalized, seam):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if np.asarray(rgb).shape != (*mask.shape, 3):
        raise ValueError("Native RGB/GT alignment required")
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout="constrained")
    axes[0, 0].imshow(rgb)
    if mask.any():
        axes[0, 0].contour(mask, levels=[.5], colors=["cyan"], linewidths=.6)
    axes[0, 0].set_title("Native RGB + post-hoc GT")
    axes[0, 1].imshow(mask, vmin=0, vmax=1, cmap="gray")
    axes[0, 1].set_title("GT, 4-connected components")
    axes[0, 2].imshow(seam, vmin=0, vmax=1, cmap="gray")
    axes[0, 2].set_title("Fixed tile boundary adjacency")
    low = min(float(values.min()) for values in normalized.values())
    high = max(float(values.max()) for values in normalized.values())
    for ax, variant in zip(axes[1], VARIANTS, strict=True):
        shown = ax.imshow(normalized[variant], vmin=low, vmax=high, cmap="magma")
        ax.set_title(variant)
    fig.colorbar(shown, ax=list(axes[1]), label="Frozen normal-calibrated map value", shrink=.7)
    for ax in axes.flat:
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(sample + " | exploratory selected case", fontsize=11)
    fig.savefig(Path(output), dpi=160)
    plt.close(fig)
