"""Measure which synthetic pose changes the fixed registration accepts (docs/PHONE_REGISTRATION_RANGE.md).

SYNTHETIC only: a board-like texture is rotated, scaled, shifted or perspective-tilted and registered back to the
untransformed reference with the same ORB + RANSAC homography, ROI checks and recipe pose tolerance the station uses.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
from skimage.transform import ProjectiveTransform, warp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import phone_capture as pc  # noqa: E402
from sr_anomaly import phone_station as ps  # noqa: E402

ROI = (0.2, 0.2, 0.8, 0.8)
TOLERANCE = dict(rotation_deg=5.0, scale_deviation=0.10)
GRID = dict(rotation_deg=(0, 2, 5, 10, 20, 45, 90, 180), scale=(0.7, 0.8, 0.9, 1.1, 1.25, 1.5, 2.0),
            shift_fraction=(0.05, 0.1, 0.2, 0.3, 0.4), tilt_deg=(5, 10, 15, 20, 30),
            tilt_recentred_deg=(5, 10, 15, 20, 30, 40, 50))


def _synth():
    spec = importlib.util.spec_from_file_location("phone_synth_reg", ROOT / "scripts/make_phone_synthetic_set.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def homography(kind: str, value: float, w: int, h: int) -> np.ndarray:
    """Reference -> moving homography about the image centre."""
    c = np.array([[1, 0, w / 2], [0, 1, h / 2], [0, 0, 1.0]])
    ci = np.linalg.inv(c)
    if kind == "rotation_deg":
        a = math.radians(value)
        m = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1.0]])
    elif kind == "scale":
        m = np.diag([value, value, 1.0])
    elif kind == "shift_fraction":
        m = np.array([[1, 0, value * w], [0, 1, 0], [0, 0, 1.0]])
    elif kind in ("tilt_deg", "tilt_recentred_deg"):
        # Camera rotated about the horizontal image axis, focal length 1.2 x width. "tilt_deg" keeps the camera
        # position, so the view also shifts; "tilt_recentred_deg" re-aims so the image centre stays put (pure perspective).
        f, a = 1.2 * w, math.radians(value)
        k = np.diag([f, f, 1.0])
        r = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
        m = k @ r @ np.linalg.inv(k)
        if kind == "tilt_recentred_deg":
            m = np.array([[1, 0, 0], [0, 1, -m[1, 2] / m[2, 2]], [0, 0, 1.0]]) @ (m / m[2, 2])
    else:
        raise ValueError(kind)
    return c @ m @ ci


def apply(img: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    out = warp(img, ProjectiveTransform(matrix).inverse, order=1, mode="edge", preserve_range=True)
    return np.clip(out, 0, 255).astype(np.uint8)


def classify(reference: np.ndarray, moving: np.ndarray, box) -> dict:
    a = pc.align(pc.luma(reference), pc.luma(moving))
    check = ps.roi_alignment_check(a, box, moving.shape)
    row = dict(alignment_success=a["success"], alignment_failure=a["failure"], inliers=a["inliers"],
               inlier_ratio=a["inlier_ratio"], reproj_median_px=a["reproj_median_px"], rotation_deg_measured=a["rotation_deg"],
               scale_deviation_measured=a["scale_deviation"], perspective_term=ps.perspective_term(a.get("matrix"), reference.shape),
               roi_inliers=check["roi_inliers"], projected_coverage=check["projected_coverage"], roi_verified=check["verified"])
    if not check["verified"]:
        row.update(outcome="RETAKE", reason=check["failure"])
    elif abs(a["rotation_deg"]) > TOLERANCE["rotation_deg"] or a["scale_deviation"] > TOLERANCE["scale_deviation"]:
        row.update(outcome="REVIEW", reason="outside_recipe_pose")
    else:
        row.update(outcome="ACCEPT", reason="")
    return row


def run(output: Path, size=(800, 600)) -> list[dict]:
    synth = _synth()
    synth.W, synth.H = size
    base = synth.board(11)
    reference = synth.lit(base, "front", noise_seed=1)
    box = pc.roi_box(reference.shape, ROI)
    rows = []
    for kind, values in GRID.items():
        for i, value in enumerate(values):
            moving = apply(synth.lit(base, "left", noise_seed=10 + i), homography(kind, value, *size))
            rows.append(dict(transform=kind, value=value, **classify(reference, moving, box)))
    output.mkdir(parents=True, exist_ok=False)
    with open(output / "registration_range.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (output / "manifest.json").write_text(json.dumps(dict(kind="synthetic", size=list(size), roi=list(ROI), tolerance=TOLERANCE,
                                                           grid={k: list(v) for k, v in GRID.items()},
                                                           note="synthetic board texture, side-light shading; not real photos"), indent=1),
                                          encoding="utf-8")
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    for r in run(p.parse_args(argv).output):
        print(r["transform"], r["value"], r["outcome"], r["reason"])


if __name__ == "__main__":
    main()
