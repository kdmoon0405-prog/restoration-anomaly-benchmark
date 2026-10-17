"""Draft full-frame PCB geometry, independent of legacy model preprocessing."""
from __future__ import annotations

import numpy as np
from PIL import Image
from skimage.measure import label, regionprops

GEOMETRY_ID = "pcb_full_frame_224_bilinear_nearest_v0_1"
TARGET_SIZE = (224, 224)


def geometry_metadata(source_size: tuple[int, int]) -> dict:
    width, height = source_size
    if width <= 0 or height <= 0:
        raise ValueError("Positive source dimensions required")
    sx, sy = TARGET_SIZE[0] / width, TARGET_SIZE[1] / height
    return {"geometry_id": GEOMETRY_ID, "source_size_wh": [width, height],
            "target_size_wh": list(TARGET_SIZE), "image_interpolation": "Pillow BILINEAR",
            "mask_interpolation": "Pillow NEAREST on binary foreground (>0)",
            "crop": None, "padding": None, "fov_edge_coverage": "entire [0,width] x [0,height] domain",
            "coordinate_convention": "x=column,y=row; edge coordinates; pixel centers use integer source/target indices",
            "source_to_target_edge_affine": [[sx, 0., 0.], [0., sy, 0.], [0., 0., 1.]],
            "source_to_target_center_affine": [[sx, 0., (sx - 1) / 2], [0., sy, (sy - 1) / 2], [0., 0., 1.]],
            "target_to_source_center_affine": [[1/sx, 0., (1/sx - 1)/2], [0., 1/sy, (1/sy - 1)/2], [0., 0., 1.]],
            "target_pixel_center_to_source": "((x+0.5)*width/224-0.5, (y+0.5)*height/224-0.5)",
            "aspect_ratio_preserved": width == height,
            "axis_scale_x_over_y": sx / sy,
            "limits": "Full FOV does not guarantee foreground/component/shape preservation after point sampling; non-square inputs are anisotropically resized."}


def _binary_mask(mask: Image.Image) -> np.ndarray:
    values = np.asarray(mask)
    if values.ndim != 2 or values.dtype.kind not in "biu":
        raise ValueError("Single-channel integer/bool GT mask required")
    if values.dtype.kind == "i" and np.any(values < 0):
        raise ValueError("GT values must be nonnegative")
    return values > 0


def resize_full_frame(image: Image.Image, mask: Image.Image | None = None):
    """Return RGB/optional binary GT/coordinate metadata; no crop or model work."""
    metadata = geometry_metadata(image.size)
    if mask is not None and mask.size != image.size:
        raise ValueError("Image and GT source dimensions must match")
    rgb = image.convert("RGB").resize(TARGET_SIZE, Image.Resampling.BILINEAR)
    gt = None
    if mask is not None:
        binary = _binary_mask(mask)
        gt = Image.fromarray(binary.astype(np.uint8) * 255).resize(TARGET_SIZE, Image.Resampling.NEAREST)
    return rgb, gt, metadata


def component_sampling_audit(mask: Image.Image, target_mask: Image.Image | None = None):
    """Track original 8-connected foreground IDs through the exact NN sampler.

    Counts are source components, not physical defects. Source areas and target
    sample counts have different units; their ratio is not a retention measure.
    """
    geometry_metadata(mask.size)
    binary = _binary_mask(mask)
    source_ids = label(binary, connectivity=2, background=0)
    sampled = np.asarray(Image.fromarray(source_ids.astype(np.int32)).resize(TARGET_SIZE, Image.Resampling.NEAREST))
    target = sampled > 0
    if target_mask is not None:
        if target_mask.size != TARGET_SIZE or not np.array_equal(target, _binary_mask(target_mask)):
            raise ValueError("Target GT does not match nearest sampling of source component IDs")
    counts = np.bincount(sampled.ravel(), minlength=int(source_ids.max()) + 1)
    components = []
    for region in regionprops(source_ids):
        y0, x0, y1, x1 = region.bbox
        components.append({"component_id": int(region.label), "source_area_pixels": int(region.area),
                           "source_bbox_xyxy": [int(x0), int(y0), int(x1), int(y1)],
                           "target_positive_samples": int(counts[region.label]),
                           "represented": bool(counts[region.label])})
    lost = [row for row in components if not row["represented"]]
    summary = {"source_foreground_pixels": int(binary.sum()), "target_foreground_pixels": int(target.sum()),
               "source_component_count": len(components), "represented_source_components": len(components) - len(lost),
               "lost_source_components": len(lost), "lost_source_component_area_pixels": sum(row["source_area_pixels"] for row in lost),
               "target_connected_components": int(label(target, connectivity=2, background=0).max()),
               "source_empty": not bool(binary.any()), "target_empty": not bool(target.any()),
               "source_all_foreground": bool(binary.all()), "target_all_foreground": bool(target.all()),
               "component_reference": "original-resolution binary GT, 8-connected; IDs tracked by Pillow NEAREST; not physical defect count",
               "pixel_count_units": "source raster pixels and target raster samples reported separately; no cross-resolution pixel retention ratio"}
    return summary, components


def readiness_status(anomaly_summaries, *, dimension_errors=0, normal_foreground_errors=0):
    """Presence/alignment guard only, not proof of preserved shapes or accuracy."""
    if (not anomaly_summaries or dimension_errors or normal_foreground_errors or any(
            row["source_empty"] or row["target_empty"] or row["source_all_foreground"]
            or row["target_all_foreground"] or row["lost_source_components"] for row in anomaly_summaries)):
        return "BLOCKED_GEOMETRY"
    return "READY_FOR_SEPARATE_PILOT"
