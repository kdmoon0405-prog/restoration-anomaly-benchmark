"""Recipe, ROI-verified registration, reference-relative quality policy v0.2 and a small golden-reference
inspection (docs/DESIGN_DECISION_PHONE_V0.2.md). NumPy / SciPy / scikit-image only; no learned detector.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import ndimage

from . import phone_capture as pc

DECISION = "docs/DESIGN_DECISION_PHONE_V0.2.md"
POLICY_VERSION = "ref_roi_v0.2"
POLICY_V3 = "ref_roi_same_light_v0.3"  # docs/DESIGN_DECISION_PHONE_V0.3.md
STATION_ROLES = ("reference", "calibration", "first", "alternate")
GR_VERSION = "golden_reference_v0.1"
V2 = dict(roi_inliers_min=20, roi_inlier_bbox_min=0.25, coverage_min=0.98, new_clip_high=0.01, new_clip_low=0.01,
          luma_min=40.0, sharpness_ratio=0.5)
GR = dict(presmooth_sigma=1.5, norm_sigma=12.0, norm_eps=2.0, diff_sigma=2.0, quantile=0.999, tau_factor=2.0,
          min_area=25, roi_erode=4, location_radius=30.0)
RECIPE_KEYS = ("recipe_id", "part_id", "view", "anchor", "roi", "work_long_side", "interpolation", "lighting", "camera",
               "pose_tolerance", "retake_light", "policy_version")


def load_recipe(path: Path) -> dict:
    recipe = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    missing = [k for k in RECIPE_KEYS if k not in recipe]
    if missing:
        raise ValueError(f"recipe missing {missing}")
    roi = recipe["roi"]
    if len(roi) != 4 or not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
        raise ValueError("recipe roi must be [x0, y0, x1, y1] fractions")
    tol = recipe["pose_tolerance"]
    if not (tol.get("rotation_deg", 0) > 0 and tol.get("scale_deviation", 0) > 0):
        raise ValueError("recipe pose_tolerance needs positive rotation_deg and scale_deviation")
    if recipe["work_long_side"] != pc.WORK_LONG_SIDE:
        raise ValueError("recipe work_long_side differs from the tool")
    return recipe


# ---------------------------------------------------------------- registration checks
def projected_coverage(matrix, box, moving_shape, step: int = 4) -> float:
    """Fraction of the reference-frame ROI whose projection lies inside the moving image."""
    x0, y0, x1, y1 = box
    xs, ys = np.meshgrid(np.arange(x0, x1, step, dtype=np.float64), np.arange(y0, y1, step, dtype=np.float64))
    pts = np.stack([xs.ravel(), ys.ravel(), np.ones(xs.size)])
    q = np.asarray(matrix, dtype=np.float64) @ pts
    with np.errstate(divide="ignore", invalid="ignore"):
        u, v = q[0] / q[2], q[1] / q[2]
    h, w = moving_shape[:2]
    inside = np.isfinite(u) & np.isfinite(v) & (u >= 0) & (u <= w - 1) & (v >= 0) & (v <= h - 1)
    return float(inside.mean())


def roi_alignment_check(alignment: dict, box, moving_shape) -> dict:
    """ROI inlier count/spread and projected coverage; guards against background-only registration and lost FOV."""
    out = dict(roi_inliers=0, roi_inlier_bbox_fraction=0.0, projected_coverage=0.0, verified=False, failure=None)
    if not alignment.get("success"):
        out["failure"] = alignment.get("failure") or "alignment_failed"
        return out
    x0, y0, x1, y1 = box
    pts = np.asarray(alignment.get("inlier_reference_xy", np.empty((0, 2))), dtype=np.float64).reshape(-1, 2)
    inside = pts[(pts[:, 0] >= x0) & (pts[:, 0] < x1) & (pts[:, 1] >= y0) & (pts[:, 1] < y1)]
    out["roi_inliers"] = int(len(inside))
    if len(inside) >= 2:
        span = (inside[:, 0].max() - inside[:, 0].min()) * (inside[:, 1].max() - inside[:, 1].min())
        out["roi_inlier_bbox_fraction"] = float(span / ((x1 - x0) * (y1 - y0)))
    out["projected_coverage"] = projected_coverage(alignment["matrix"], box, moving_shape)
    if out["roi_inliers"] < V2["roi_inliers_min"] or out["roi_inlier_bbox_fraction"] < V2["roi_inlier_bbox_min"]:
        out["failure"] = "alignment_unverified_in_roi"
    elif out["projected_coverage"] < V2["coverage_min"]:
        out["failure"] = "roi_outside_frame"
    else:
        out["verified"] = True
    return out


def perspective_term(matrix, shape) -> float:
    """Size of the projective part of a homography: |h31| + |h32| scaled by the image width (0 for an affine map).
    It is the relative change of scale across the frame; reported for information."""
    if matrix is None:
        return math.nan
    m = np.asarray(matrix, dtype=np.float64)
    m = m / m[2, 2]
    return float((abs(m[2, 0]) + abs(m[2, 1])) * shape[1])


def identity_alignment(shape, box) -> dict:
    """Alignment record for the anchor itself (not an inter-image registration result)."""
    x0, y0, x1, y1 = box
    corners = np.array([[x0, y0], [x1 - 1, y0], [x0, y1 - 1], [x1 - 1, y1 - 1]], dtype=np.float64)
    grid = np.array([[x, y] for x in np.linspace(x0, x1 - 1, 6) for y in np.linspace(y0, y1 - 1, 6)])
    return dict(success=True, inliers=None, matches=None, inlier_ratio=None, reproj_median_px=0.0, matrix=np.eye(3).tolist(),
                translation_fraction=0.0, rotation_deg=0.0, scale_deviation=0.0, failure=None, is_anchor=True,
                inlier_reference_xy=np.vstack([corners, grid]))


def warp_mask(mask: np.ndarray, matrix, shape) -> np.ndarray:
    """Nearest-neighbour move of a boolean mask from the moving frame into the reference frame."""
    from skimage.transform import ProjectiveTransform, warp
    out = warp(mask.astype(np.float64), ProjectiveTransform(np.asarray(matrix, dtype=np.float64)), output_shape=shape[:2],
               order=0, mode="constant", cval=0)
    return out > 0.5


# ---------------------------------------------------------------- quality policy v0.2
def clip_masks(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return (rgb >= pc.CLIP_HIGH).any(-1), (rgb <= pc.CLIP_LOW).all(-1)


def sharpness_norm(quality: dict) -> float:
    mean = quality["luma_mean"] / 255.0
    return float(quality["sharpness_tenengrad"] / (mean * mean)) if mean > 0 else math.nan


def new_clip_fractions(moving_rgb, matrix, ref_high, ref_low, box, valid) -> dict:
    """New clipping inside the ROI: clipped in the capture but not in the (dilated) reference masks, which are
    boolean masks in the anchor frame."""
    x0, y0, x1, y1 = box
    high, low = clip_masks(moving_rgb)
    roi = np.zeros(ref_high.shape, bool)
    roi[y0:y1, x0:x1] = True
    roi &= valid
    if int(roi.sum()) < 16:
        raise ValueError("ROI not visible")
    new_high = warp_mask(high, matrix, ref_high.shape) & ~ndimage.binary_dilation(ref_high, structure=np.ones((3, 3), bool))
    new_low = warp_mask(low, matrix, ref_high.shape) & ~ndimage.binary_dilation(ref_low, structure=np.ones((3, 3), bool))
    return dict(new_clip_high=float(new_high[roi].mean()), new_clip_low=float(new_low[roi].mean()),
                reference_clip_high=float(ref_high[roi].mean()), reference_clip_low=float(ref_low[roi].mean()))


def reference_relative_metrics(moving_rgb, matrix, reference_rgb, box, valid) -> dict:
    """v0.2: new clipping against the anchor image (reference_rgb is in the anchor frame, unwarped)."""
    ref_high, ref_low = clip_masks(reference_rgb)
    return new_clip_fractions(moving_rgb, matrix, ref_high, ref_low, box, valid)


def reference_clip_in_anchor(reference_work_rgb, reference_matrix, anchor_shape) -> tuple[np.ndarray, np.ndarray]:
    """Clip masks of a same-light reference photo, taken on its unwarped pixels and moved to the anchor frame."""
    high, low = clip_masks(reference_work_rgb)
    return warp_mask(high, reference_matrix, anchor_shape), warp_mask(low, reference_matrix, anchor_shape)


def policy_v02(capture: dict, recipe: dict) -> tuple[str, list[str]]:
    """capture: missing/unreadable/duplicate_of/resolution_mismatch, roi_check dict, new_clip_*, luma_mean,
    sharpness_ratio, rotation_deg, scale_deviation."""
    if capture.get("missing"):
        return "RETAKE", ["missing_file"]
    if capture.get("unreadable"):
        return "RETAKE", ["unreadable"]
    check = capture.get("roi_check") or {}
    if not check.get("verified"):
        return "RETAKE", [check.get("failure") or "alignment_failed"]
    retake, review = [], []
    if capture["new_clip_high"] > V2["new_clip_high"]:
        retake.append("new_clip_high")
    if capture["new_clip_low"] > V2["new_clip_low"]:
        retake.append("new_clip_low")
    if capture["luma_mean"] < V2["luma_min"]:
        review.append("roi_too_dark")
    if capture["sharpness_ratio"] < V2["sharpness_ratio"]:
        review.append("low_sharpness_vs_reference")
    tol = recipe["pose_tolerance"]
    if abs(capture["rotation_deg"]) > tol["rotation_deg"] or capture["scale_deviation"] > tol["scale_deviation"]:
        review.append("outside_recipe_pose")
    if capture.get("duplicate_of"):
        review.append(f"duplicate_of_row_{capture['duplicate_of']}")
    if capture.get("resolution_mismatch"):
        review.append("resolution_mismatch")
    if retake:
        return "RETAKE", retake + review
    return ("REVIEW", review) if review else ("PASS", [])


def policy_v03(capture: dict, recipe: dict) -> tuple[str, list[str]]:
    """v0.3 = v0.2 rules with same-light reference inputs: capture carries new_clip_*_v03 and sharpness_ratio_v03
    (raw Tenengrad ratio to the reference of the light the capture is expected to have)."""
    if capture.get("missing") or capture.get("unreadable") or not (capture.get("roi_check") or {}).get("verified"):
        return policy_v02(capture, recipe)
    if capture.get("reference_unavailable"):
        return "RETAKE", ["reference_unavailable"]
    state, reasons = policy_v02(dict(capture, new_clip_high=capture["new_clip_high_v03"], new_clip_low=capture["new_clip_low_v03"],
                                     sharpness_ratio=capture["sharpness_ratio_v03"]), recipe)
    return state, ["low_sharpness_vs_same_light_reference" if r == "low_sharpness_vs_reference" else r for r in reasons]


def plan_from_sheet(rows: list[dict], first_light: str = "L0", alternate_light: str = "L1") -> dict:
    """Build the run plan from capture-sheet columns station_role / cycle_id / light (see PHONE_EVAL_SESSION_PLAN_V1)."""
    plan = dict(first_light=first_light, alternate_light=alternate_light, references={}, calibration={}, cycles=[],
                plan_source="capture_sheet.csv station_role/cycle_id/light")
    cycles: dict[str, dict] = {}
    for r in rows:
        role = (r.get("station_role") or "").strip()
        if not role:
            continue
        if role not in STATION_ROLES:
            raise ValueError(f"unknown station_role {role!r} for {r.get('file')!r}")
        if int(r.get("attempt") or 1) != max(int(x.get("attempt") or 1) for x in rows
                                               if (x.get("station_role"), x.get("cycle_id"), x.get("light"), x.get("repeat_id"))
                                               == (r.get("station_role"), r.get("cycle_id"), r.get("light"), r.get("repeat_id"))):
            continue  # an earlier attempt of the same slot; the latest attempt is used
        name, light = (r.get("file") or "").strip(), (r.get("light") or "").strip()
        if role in ("reference", "calibration"):
            group = plan["references" if role == "reference" else "calibration"]
            if light not in (first_light, alternate_light) or light in group:
                raise ValueError(f"need exactly one {role} photo per light; problem at {name!r} ({light!r})")
            group[light] = name
            continue
        cid = (r.get("cycle_id") or "").strip()
        if not cid:
            raise ValueError(f"{role} photo {name!r} has no cycle_id")
        c = cycles.setdefault(cid, dict(cycle_id=cid, kind=(r.get("cycle_kind") or "").strip(), label=None, first=None, alternate=None,
                                        note="", capture_seconds=""))
        if c[role] is not None:
            raise ValueError(f"cycle {cid!r} has two {role} photos")
        if role == "alternate" and light != alternate_light:
            raise ValueError(f"alternate photo of {cid!r} must be taken under {alternate_light}")
        c[role] = name
        if role == "first":
            c["label"] = "simulated_defect" if (r.get("label_status") or "").strip() == "simulated_defect" else "normal"
            c["note"] = (r.get("notes") or "").strip()
            c["capture_seconds"] = (r.get("capture_seconds") or "").strip()
    for cid, c in cycles.items():
        if c["first"] is None:
            raise ValueError(f"cycle {cid!r} has no first photo")
    for group in ("references", "calibration"):
        if set(plan[group]) != {first_light, alternate_light}:
            raise ValueError(f"capture sheet must mark one {group[:-1] if group == 'references' else group} photo for each of "
                             f"{first_light} and {alternate_light}")
    used = list(plan["references"].values()) + list(plan["calibration"].values())
    for c in cycles.values():
        used += [c["first"]] + ([c["alternate"]] if c["alternate"] else [])
    if len(used) != len(set(used)):
        raise ValueError("a photo is used in more than one role; references, calibration and cycle photos must be separate")
    plan["cycles"] = list(cycles.values())
    if not plan["cycles"]:
        raise ValueError("capture sheet marks no cycle (station_role first)")
    return plan


# ---------------------------------------------------------------- golden-reference inspection v0.1
def local_normalize(rgb: np.ndarray) -> np.ndarray:
    x = ndimage.gaussian_filter(rgb.astype(np.float32), sigma=(GR["presmooth_sigma"], GR["presmooth_sigma"], 0))
    mean = ndimage.gaussian_filter(x, sigma=(GR["norm_sigma"], GR["norm_sigma"], 0))
    high = x - mean
    std = np.sqrt(ndimage.gaussian_filter(high * high, sigma=(GR["norm_sigma"], GR["norm_sigma"], 0)))
    return high / (std + GR["norm_eps"])


def difference_map(test_rgb: np.ndarray, reference_rgb: np.ndarray) -> np.ndarray:
    d = np.abs(local_normalize(test_rgb) - local_normalize(reference_rgb)).max(axis=-1)
    return ndimage.gaussian_filter(d, sigma=GR["diff_sigma"])


def inspection_mask(shape, box, *valids) -> np.ndarray:
    x0, y0, x1, y1 = box
    roi = np.zeros(shape[:2], bool)
    roi[y0:y1, x0:x1] = True
    for v in valids:
        roi &= v
    return ndimage.binary_erosion(roi, iterations=GR["roi_erode"])


def largest_blob(diff: np.ndarray, mask: np.ndarray, tau: float) -> dict:
    labels, n = ndimage.label((diff > tau) & mask, structure=np.ones((3, 3), int))
    if n == 0:
        return dict(score=0, centroid_xy=None, bbox=None)
    areas = np.bincount(labels.ravel())[1:]
    k = int(areas.argmax()) + 1
    ys, xs = np.nonzero(labels == k)
    return dict(score=int(areas.max()), centroid_xy=[float(xs.mean()), float(ys.mean())],
                bbox=[int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1])


def gr_calibrate(diff: np.ndarray, mask: np.ndarray) -> dict:
    """Normal-only calibration from one normal capture vs the reference under the same lighting."""
    if mask.sum() < 1000:
        raise ValueError("calibration ROI too small")
    q = float(np.quantile(diff[mask], GR["quantile"]))
    tau = GR["tau_factor"] * q
    return dict(tau=tau, normal_quantile=q, base_score=largest_blob(diff, mask, tau)["score"],
                calibration_pixels=int(mask.sum()))


def gr_inspect(diff: np.ndarray, mask: np.ndarray, calibration: dict) -> dict:
    blob = largest_blob(diff, mask, calibration["tau"])
    limit = GR["min_area"]  # fixed minimum blob area; base_score is recorded for reference only
    return dict(**blob, limit=float(limit), verdict="NG" if blob["score"] >= limit else "OK",
                roi_valid_pixels=int(mask.sum()))


def location_match(centroid_xy, annotation_xy) -> bool | None:
    if centroid_xy is None or annotation_xy is None:
        return None
    return bool(math.hypot(centroid_xy[0] - annotation_xy[0], centroid_xy[1] - annotation_xy[1]) <= GR["location_radius"])


# ---------------------------------------------------------------- x4 round trip (new family phone_x4_roundtrip)
def x4_roundtrip(rgb: np.ndarray, downscale, upscale) -> np.ndarray:
    """rgb (H, W multiples of 4) -> x0.25 -> x4 with the given callables on PIL images; same size out."""
    from PIL import Image
    h, w = rgb.shape[:2]
    if h % 4 or w % 4:
        raise ValueError("x4 round trip needs working dimensions divisible by 4")
    out = upscale(downscale(Image.fromarray(rgb)))
    if out.size != (w, h) or out.mode != "RGB":
        raise ValueError("restorer output must be RGB with the input size")
    return np.asarray(out, dtype=np.uint8)
