"""Write a SYNTHETIC phone capture folder (board-like texture, 3 light positions x repeats) with injected faults.

For software tests and demo screens only; not a real capture and not research data. expected.json lists the
intended state and reason per sheet row.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageFilter

W, H = 1600, 1200  # blur levels below are absolute px chosen for this default size (margins checked)


def board(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.empty((H, W, 3), np.float64)
    img[:] = (52, 112, 66)
    img += rng.normal(0, 4, img.shape)
    for _ in range(70):  # chips
        x, y = rng.integers(0, W - 160), rng.integers(0, H - 120)
        w, h = rng.integers(40, 160), rng.integers(30, 120)
        img[y:y + h, x:x + w] = rng.integers(55, 80)
    for _ in range(600):  # pads
        x, y = rng.integers(0, W - 14), rng.integers(0, H - 14)
        s = rng.integers(5, 14)
        img[y:y + s, x:x + s] = (185, 182, 170)
    for _ in range(140):  # traces
        x, y = rng.integers(0, W - 300), rng.integers(0, H - 4)
        img[y:y + 3, x:x + rng.integers(60, 300)] = (70, 140, 85)
    return np.clip(img, 45, 200)


def lit(base: np.ndarray, position: str, gain=1.0, noise_seed=0) -> np.ndarray:
    x = np.linspace(0, 1, W)[None, :, None]
    shade = {"left": 1.12 - 0.24 * x, "front": np.ones_like(x), "right": 0.88 + 0.24 * x}[position]
    rng = np.random.default_rng(noise_seed)
    return np.clip(base * shade * gain + rng.normal(0, 2.0, base.shape), 0, 255).astype(np.uint8)


def shift(img: np.ndarray, dx: int) -> np.ndarray:
    out = np.roll(img, dx, axis=1)
    out[:, :dx] = img[:, :1]
    return out


def make(folder: Path) -> dict:
    folder = Path(folder)
    if folder.exists():
        raise FileExistsError(folder)
    folder.mkdir(parents=True)
    base = board(11)
    rows, expected = [], {}

    def add(name, arr, part="P1", session="S1", recipe="front", repeat=1, attempt=1, expect=("PASS", None), **extra):
        if arr is not None:
            Image.fromarray(arr).save(folder / name, quality=92)
        rows.append(dict(file=name, part_id=part, session_id=session, recipe_id=recipe, repeat_id=repeat, attempt=attempt,
                         label_status="unknown", light_position=recipe, **extra))
        expected[len(rows) + 1] = dict(file=name, state=expect[0], reason=expect[1])

    k = 0
    for position in ("front", "left", "right"):
        for repeat in (1, 2, 3):
            k += 1
            name = f"{position}_r{repeat}.jpg"
            if position == "front" and repeat == 3:
                # Heavy blur: alignment itself fails under the fixed rule -> RETAKE (low_sharpness also recorded).
                arr = np.asarray(Image.fromarray(lit(base, position, noise_seed=k)).filter(ImageFilter.GaussianBlur(8)))
                add(name, arr, recipe=position, repeat=repeat, expect=("RETAKE", "alignment_failed"))
            elif position == "left" and repeat == 3:
                add(name, shift(lit(base, position, noise_seed=k), int(0.06 * W)), recipe=position, repeat=repeat,
                    expect=("REVIEW", "setup_moved"))
            elif position == "right" and repeat == 2:
                add(name, lit(base, position, gain=1.9, noise_seed=k), recipe=position, repeat=repeat,
                    expect=("RETAKE", "clip_high"))
                add("right_r2_retake.jpg", lit(base, position, noise_seed=k + 100), recipe=position, repeat=repeat, attempt=2)
            else:
                add(name, lit(base, position, noise_seed=k), recipe=position, repeat=repeat,
                    **({"reference": "1", "roi_x0": "0.1", "roi_y0": "0.1", "roi_x1": "0.9", "roi_y1": "0.9"}
                       if (position, repeat) == ("front", 1) else {}))
    # Mild blur: still aligns, sharpness below 0.5 x session median -> REVIEW only.
    mild = np.asarray(Image.fromarray(lit(base, "front", noise_seed=54)).filter(ImageFilter.GaussianBlur(1.5)))
    add("front_r6_mildblur.jpg", mild, recipe="front", repeat=6, expect=("REVIEW", "low_sharpness"))
    add("dim_r1.jpg", lit(base, "front", gain=0.25, noise_seed=50), recipe="dim", expect=("REVIEW", "luma_out_of_range"))
    add("flash_r1.jpg", lit(board(99), "front", noise_seed=51), recipe="flash", expect=("RETAKE", "alignment_failed"))
    add("front_r4.jpg", None, recipe="front", repeat=4, expect=("RETAKE", "missing_file"))
    shutil.copyfile(folder / "front_r1.jpg", folder / "front_r5.jpg")
    add("front_r5.jpg", None, recipe="front", repeat=5, expect=("REVIEW", "duplicate_of_row_2"))
    add("bad_id.jpg", lit(base, "front", noise_seed=52), part="bad id!", expect=("REVIEW", "invalid_row"))
    Image.fromarray(lit(base, "front", noise_seed=53)).save(folder / "extra_unlisted.jpg", quality=92)
    with open(folder / "capture_sheet.csv", "w", encoding="utf-8", newline="") as f:
        fields = ["file", "part_id", "session_id", "recipe_id", "repeat_id", "attempt", "label_status", "light_position",
                  "reference", "roi_x0", "roi_y0", "roi_x1", "roi_y1"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    spec = dict(kind="synthetic", generator="scripts/make_phone_synthetic_set.py", seed=11, size=[W, H],
                rows=expected, unlisted=["extra_unlisted.jpg"],
                note="Synthetic board-like texture; lighting is a multiplicative gradient, not a physical light model.")
    (folder / "expected.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    return spec


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    make(p.parse_args(argv).output)


if __name__ == "__main__":
    main()
