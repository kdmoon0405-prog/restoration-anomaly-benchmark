"""Development probe (not an evaluation): registration success with and without local contrast equalization.

Runs the station's own ORB + RANSAC registration (phone_capture.align, unchanged thresholds) of every photo in a
capture folder three ways: to the recipe anchor on the plain luma (as the station does), to the anchor on
CLAHE-equalized luma (skimage.exposure.equalize_adapthist, fixed clip 0.02, kernel 1/8 of the image), and on the
plain luma to the sheet's reference photo taken under the same light (L1 -> REF L1; L0 and other lights -> REF L0).
Writes one CSV row per photo.
Using this on the session that motivated it makes the result development evidence only; a candidate method change
must be evaluated on a new session.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np
from skimage import exposure

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import phone_capture as pc  # noqa: E402


def equalize(y: np.ndarray) -> np.ndarray:
    return exposure.equalize_adapthist(y / 255.0, kernel_size=max(8, y.shape[1] // 8), clip_limit=0.02) * 255.0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--photos", type=Path, required=True)
    p.add_argument("--recipe", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    if a.output.exists():
        raise SystemExit(f"{a.output} exists")
    recipe = json.loads(a.recipe.read_text(encoding="utf-8"))
    sheet = {r["file"]: r for r in csv.DictReader(open(a.photos / "capture_sheet.csv", encoding="utf-8"))}
    anchor, _ = pc.working(pc.decode(a.photos / recipe["anchor"])[0])
    ay = pc.luma(anchor)
    ay_eq = equalize(ay)
    refs = {s["light"]: name for name, s in sheet.items() if s.get("station_role") == "reference"}
    ref_y = {light: pc.luma(pc.working(pc.decode(a.photos / f)[0])[0]) for light, f in refs.items()}
    rows = []
    for name, s in sheet.items():
        if name == recipe["anchor"]:
            continue
        work, _ = pc.working(pc.decode(a.photos / name)[0])
        y = pc.luma(work)
        plain = pc.align(ay, y)
        eq = pc.align(ay_eq, equalize(y))
        same_light = s["light"] if s["light"] in ref_y else "L0"
        sl = pc.align(ref_y[same_light], y) if name != refs.get(same_light) else dict(success=True, inlier_ratio=1.0)
        rows.append(dict(file=name, recipe_id=s["recipe_id"], light=s["light"], capture_group=s.get("capture_group", ""),
                         plain_success=plain["success"], plain_inlier_ratio=round(plain["inlier_ratio"], 4),
                         clahe_success=eq["success"], clahe_inlier_ratio=round(eq["inlier_ratio"], 4),
                         clahe_rotation_deg=round(eq["rotation_deg"], 3) if eq["matrix"] else "",
                         clahe_scale_deviation=round(eq["scale_deviation"], 4) if eq["matrix"] else "",
                         clahe_reproj_median_px=round(eq["reproj_median_px"], 3) if eq["matrix"] else "",
                         same_light_reference=refs.get(same_light, ""), same_light_success=sl["success"],
                         same_light_inlier_ratio=round(sl["inlier_ratio"], 4)))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with open(a.output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(dict(photos=len(rows), plain=sum(r["plain_success"] for r in rows), clahe=sum(r["clahe_success"] for r in rows),
                          same_light=sum(r["same_light_success"] for r in rows))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
