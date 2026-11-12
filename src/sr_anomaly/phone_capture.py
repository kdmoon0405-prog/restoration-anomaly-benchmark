"""Phone capture manifest, quality, alignment and policy (docs/PHONE_QUALITY_PROTOCOL_V0.1.md).

NumPy / SciPy / scikit-image / PIL only. No detector, model or bank. Not a detection metric.
"""
from __future__ import annotations

import hashlib
from itertools import combinations
import math
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from scipy import ndimage

PROTOCOL = "docs/PHONE_QUALITY_PROTOCOL_V0.1.md"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".dng"}
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
LABELS = {"normal", "real_defect", "simulated_defect", "unknown"}
WORK_LONG_SIDE = 1024
CLIP_HIGH, CLIP_LOW = 250, 5
T = dict(clip_high_retake=0.01, clip_low_retake=0.01, luma_min=40.0, luma_max=215.0, sharpness_ratio=0.5,
         sharpness_min_set=3, inliers_min=30, inlier_ratio_min=0.25, reproj_median_max=1.5,
         moved_translation=0.02, moved_rotation_deg=1.0, moved_scale=0.02)
ORB = dict(n_keypoints=1000, fast_threshold=0.05)
RANSAC = dict(min_samples=4, residual_threshold=2.0, max_trials=2000)
EXIF_TAGS = {271: "make", 272: "model", 306: "datetime", 274: "orientation"}
EXIF_IFD = {36867: "datetime_original", 33434: "exposure_time", 33437: "f_number", 34855: "iso",
            37386: "focal_length", 37385: "flash", 41987: "white_balance"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------- sheet / manifest
def parse_sheet(rows: list[dict], folder_files: list[str]) -> tuple[list[dict], list[dict]]:
    """Validate rows; return (captures, unlisted). Invalid rows are kept with reason invalid_row."""
    captures, seen_slots = [], {}
    for i, r in enumerate(rows):
        c = {k: (v or "").strip() for k, v in r.items()}
        c["row"] = i + 2  # spreadsheet line
        reasons = []
        for key in ("part_id", "session_id", "recipe_id"):
            if not ID_PATTERN.fullmatch(c.get(key, "")):
                reasons.append(f"invalid_{key}")
        for key, default in (("repeat_id", None), ("attempt", "1")):
            value = c.get(key) or default
            if value is None or not value.isdigit() or int(value) < 1:
                reasons.append(f"invalid_{key}")
            else:
                c[key] = int(value)
        name = c.get("file", "")
        if not name or Path(name).name != name or Path(name).suffix.lower() not in IMAGE_SUFFIXES:
            reasons.append("invalid_file_name")
        c["label_status"] = c.get("label_status") or "unknown"
        if c["label_status"] not in LABELS:
            reasons.append("invalid_label_status")
        if not reasons:
            key = (c["part_id"], c["session_id"], c["recipe_id"], c["repeat_id"], c["attempt"])
            if key in seen_slots:
                reasons.append(f"duplicate_slot_attempt_of_row_{seen_slots[key]}")
            seen_slots.setdefault(key, c["row"])
        c["invalid_reasons"] = reasons
        captures.append(c)
    listed = {c.get("file", "") for c in captures}
    unlisted = [dict(file=f, reasons=["unlisted_file"]) for f in sorted(folder_files) if f not in listed]
    return captures, unlisted


def read_exif(img: Image.Image) -> dict:
    exif = img.getexif()
    out = {name: str(exif.get(tag)) for tag, name in EXIF_TAGS.items() if exif.get(tag) is not None}
    try:
        ifd = exif.get_ifd(0x8769)
        out.update({name: str(ifd.get(tag)) for tag, name in EXIF_IFD.items() if ifd.get(tag) is not None})
    except Exception:  # noqa: BLE001 - EXIF sub-IFD is optional
        pass
    try:
        out["gps_present"] = bool(exif.get_ifd(0x8825))
    except Exception:  # noqa: BLE001
        out["gps_present"] = False
    return out


def decode(path: Path) -> tuple[np.ndarray, dict]:
    """Displayed-orientation RGB uint8 plus EXIF metadata; raises ValueError if unreadable."""
    try:
        with Image.open(path) as img:
            exif = read_exif(img)
            img = ImageOps.exif_transpose(img).convert("RGB")
            rgb = np.asarray(img, dtype=np.uint8).copy()
    except (UnidentifiedImageError, OSError, SyntaxError) as e:
        raise ValueError(f"unreadable: {e}") from e
    return rgb, exif


def working(rgb: np.ndarray) -> tuple[np.ndarray, float]:
    h, w = rgb.shape[:2]
    scale = WORK_LONG_SIDE / max(h, w)
    if scale >= 1:
        return rgb, 1.0
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return np.asarray(Image.fromarray(rgb).resize(size, Image.LANCZOS), dtype=np.uint8), scale


def luma(rgb: np.ndarray) -> np.ndarray:
    x = rgb.astype(np.float64)
    return 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]


# ---------------------------------------------------------------- quality
def quality(rgb: np.ndarray, valid: np.ndarray | None = None) -> dict:
    """Quality metrics on an RGB uint8 ROI; valid masks pixels inside the warped frame."""
    valid = np.ones(rgb.shape[:2], bool) if valid is None else valid
    if valid.sum() < 16:
        raise ValueError("ROI too small after alignment")
    y = luma(rgb)
    yv = y[valid]
    pix = rgb[valid]
    gx, gy = ndimage.sobel(y / 255.0, axis=1), ndimage.sobel(y / 255.0, axis=0)
    inner = valid.copy() if valid.all() else ndimage.binary_erosion(valid, iterations=2)  # drop warp-border gradients
    inner[[0, -1], :] = False
    inner[:, [0, -1]] = False
    ten = (gx ** 2 + gy ** 2)[inner] if inner.any() else (gx ** 2 + gy ** 2)[valid]
    g = pix[:, 1].astype(np.float64).mean()
    return dict(luma_mean=float(yv.mean()), luma_p01=float(np.percentile(yv, 1)), luma_p99=float(np.percentile(yv, 99)),
                clip_high_fraction=float((pix >= CLIP_HIGH).any(axis=1).mean()),
                clip_low_fraction=float((pix <= CLIP_LOW).all(axis=1).mean()),
                sharpness_tenengrad=float(ten.mean()),
                noise_sigma=noise_sigma_immerkaer(y, inner),
                rg_ratio=float(pix[:, 0].mean() / g) if g > 0 else math.nan,
                bg_ratio=float(pix[:, 2].mean() / g) if g > 0 else math.nan)


IMMERKAER = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float64)


def noise_sigma_immerkaer(y: np.ndarray, valid: np.ndarray) -> float:
    """Immerkaer (1996) fast noise estimate, sigma = sqrt(pi/2) / 6 * mean|y * M| over valid interior pixels."""
    response = np.abs(ndimage.convolve(y, IMMERKAER, mode="nearest"))
    inner = ndimage.binary_erosion(valid, iterations=1)
    inner[[0, -1], :] = False
    inner[:, [0, -1]] = False
    if not inner.any():
        return math.nan
    return float(math.sqrt(math.pi / 2) / 6 * response[inner].mean())


def roi_box(shape, fractions) -> tuple[int, int, int, int]:
    h, w = shape[:2]
    x0, y0, x1, y1 = fractions
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("ROI fractions must satisfy 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1")
    return int(math.floor(x0 * w)), int(math.floor(y0 * h)), int(math.ceil(x1 * w)), int(math.ceil(y1 * h))


# ---------------------------------------------------------------- alignment
def align(reference_y: np.ndarray, moving_y: np.ndarray) -> dict:
    """Homography mapping reference coords -> moving coords (ORB + RANSAC), with success test and decomposition."""
    from skimage.feature import ORB as SkORB, match_descriptors
    from skimage.measure import ransac
    from skimage.transform import ProjectiveTransform
    result = dict(success=False, inliers=0, matches=0, inlier_ratio=0.0, reproj_median_px=math.nan, matrix=None,
                  translation_fraction=math.nan, rotation_deg=math.nan, scale_deviation=math.nan, failure=None)
    keypoints = []
    for img in (reference_y, moving_y):
        orb = SkORB(**ORB)
        try:
            orb.detect_and_extract(img / 255.0)
        except (RuntimeError, ValueError, IndexError):
            result["failure"] = "no_features"
            return result
        if len(orb.keypoints) < RANSAC["min_samples"]:
            result["failure"] = "no_features"
            return result
        keypoints.append((orb.keypoints[:, ::-1], orb.descriptors))  # (row, col) -> (x, y)
    (k1, d1), (k2, d2) = keypoints
    matches = match_descriptors(d1, d2, cross_check=True)
    result["matches"] = int(len(matches))
    if len(matches) < RANSAC["min_samples"]:
        result["failure"] = "too_few_matches"
        return result
    src, dst = k1[matches[:, 0]], k2[matches[:, 1]]
    model, inliers = ransac((src, dst), ProjectiveTransform, rng=0, **RANSAC)
    if model is None or inliers is None:
        result["failure"] = "ransac_failed"
        return result
    err = np.linalg.norm(model(src[inliers]) - dst[inliers], axis=1)
    m = model.params / model.params[2, 2]
    h, w = reference_y.shape
    centre = np.array([[w / 2, h / 2]])
    moved = model(centre)[0] - centre[0]
    a = m[:2, :2]
    rotation = math.degrees(math.atan2(a[1, 0] - a[0, 1], a[0, 0] + a[1, 1]))
    scale = math.sqrt(abs(np.linalg.det(a)))
    result.update(inliers=int(inliers.sum()), inlier_ratio=float(inliers.mean()),
                  reproj_median_px=float(np.median(err)) if err.size else math.nan, matrix=m.tolist(),
                  translation_fraction=float(np.hypot(*moved) / w), rotation_deg=float(rotation),
                  scale_deviation=float(abs(scale - 1)))
    ok = (result["inliers"] >= T["inliers_min"] and result["inlier_ratio"] >= T["inlier_ratio_min"]
          and result["reproj_median_px"] <= T["reproj_median_max"])
    result["success"] = bool(ok)
    if not ok:
        result["failure"] = "alignment_below_threshold"
    return result


def warp_to_reference(moving_rgb: np.ndarray, matrix, shape) -> tuple[np.ndarray, np.ndarray]:
    """Resample the moving image into the reference frame; returns (rgb uint8, valid mask)."""
    from skimage.transform import ProjectiveTransform, warp
    t = ProjectiveTransform(np.asarray(matrix))
    out = warp(moving_rgb, t, output_shape=shape[:2], order=1, mode="constant", cval=-1, preserve_range=True)
    valid = (out >= 0).all(axis=-1)
    return np.clip(np.rint(np.where(out < 0, 0, out)), 0, 255).astype(np.uint8), valid


def project_roi_mask(matrix, box, reference_shape, moving_shape) -> np.ndarray:
    """ROI (reference-frame box) as a boolean mask in the unwarped moving frame (nearest neighbour, no pixel resampling)."""
    from skimage.transform import ProjectiveTransform, warp
    x0, y0, x1, y1 = box
    ref_mask = np.zeros(reference_shape[:2], np.float64)
    ref_mask[y0:y1, x0:x1] = 1.0
    inverse = ProjectiveTransform(np.linalg.inv(np.asarray(matrix, dtype=np.float64)))  # moving coords -> reference coords
    return warp(ref_mask, inverse, output_shape=moving_shape[:2], order=0, mode="constant", cval=0) > 0.5


def crop_to_mask(rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = np.flatnonzero(mask.any(1)), np.flatnonzero(mask.any(0))
    if rows.size == 0:
        raise ValueError("ROI falls outside the image")
    return rgb[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1], mask[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


def setup_moved(a: dict) -> bool:
    return bool(a["success"] and (a["translation_fraction"] > T["moved_translation"]
                                  or abs(a["rotation_deg"]) > T["moved_rotation_deg"]
                                  or a["scale_deviation"] > T["moved_scale"]))


# ---------------------------------------------------------------- policy / summaries
def policy(capture: dict, session_sharpness_median: float | None) -> tuple[str, list[str]]:
    retake, review = [], []
    if capture.get("invalid_reasons"):
        return "REVIEW", ["invalid_row", *capture["invalid_reasons"]]
    if capture.get("missing"):
        return "RETAKE", ["missing_file"]
    if capture.get("unreadable"):
        return "RETAKE", ["unreadable"]
    if capture.get("duplicate_of"):
        review.append(f"duplicate_of_row_{capture['duplicate_of']}")
    if capture.get("resolution_mismatch"):
        review.append("resolution_mismatch")
    if not capture.get("alignment_success"):
        retake.append("alignment_failed")
    if capture.get("clip_high_fraction", 0) > T["clip_high_retake"]:
        retake.append("clip_high")
    if capture.get("clip_low_fraction", 0) > T["clip_low_retake"]:
        retake.append("clip_low")
    lm = capture.get("luma_mean")
    if lm is not None and not (T["luma_min"] <= lm <= T["luma_max"]):
        review.append("luma_out_of_range")
    if session_sharpness_median is not None and capture.get("sharpness_tenengrad") is not None \
            and capture["sharpness_tenengrad"] < T["sharpness_ratio"] * session_sharpness_median:
        review.append("low_sharpness")
    if capture.get("setup_moved"):
        review.append("setup_moved")
    if retake:
        return "RETAKE", retake + review
    if review:
        return "REVIEW", review
    return "PASS", []


def pairwise_mae(aligned: list[tuple[np.ndarray, np.ndarray]]) -> list[float]:
    """Mean |ΔY| over pixels valid in both images, for every pair."""
    out = []
    for (a, va), (b, vb) in combinations(aligned, 2):
        both = va & vb
        if both.sum() >= 16:
            out.append(float(np.abs(luma(a)[both] - luma(b)[both]).mean()))
    return out
