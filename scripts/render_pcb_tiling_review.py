"""Readable figure revision only; preserve the frozen audit and original PNGs."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from skimage.measure import label
from scripts.prepare_pcb_tiling import PRIOR, check_equal, geometry, read_csv, render_figures, sha, write_json


def render_review(audit_dir, data_root, prior_dir=PRIOR):
    manifest = json.loads((audit_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    protocol = json.loads((audit_dir / "PROTOCOL.json").read_text(encoding="utf-8"))
    if sha(audit_dir / "PROTOCOL.json") != manifest["protocol_sha256"] or sha(audit_dir / "INPUTS.csv") != manifest["inputs_csv_sha256"]:
        raise ValueError("Audit protocol/input inventory hash mismatch")
    for name in ("scripts/prepare_pcb_tiling.py", "src/sr_anomaly/pcb_tiling.py"):
        if sha(ROOT / name) != protocol["code_sha256"][name]:
            raise ValueError("Frozen audit code changed")
    if sha(prior_dir / "selected_examples.json") != protocol["prior_artifact_sha256"]["selected_examples.json"]:
        raise ValueError("Historical selection changed")
    selection = json.loads((prior_dir / "selected_examples.json").read_text(encoding="utf-8"))
    inputs = read_csv(audit_dir / "INPUTS.csv")
    wanted = {r["sample"] for r in selection}
    wanted.add(min(r["sample"] for r in inputs if r["partition"] == "test" and r["label"] == "0"))
    payloads = {}
    for row in inputs:
        if row["sample"] not in wanted:
            continue
        path = data_root / row["sample"]
        if sha(path) != row["image_sha256"]:
            raise ValueError("RGB source changed")
        with Image.open(BytesIO(path.read_bytes())) as im:
            rgb = np.asarray(im.convert("RGB"))
        ids = np.zeros(rgb.shape[:2], dtype=np.int32)
        if row["mask"]:
            path = data_root / row["mask"]
            if sha(path) != row["mask_sha256"]:
                raise ValueError("GT source changed")
            with Image.open(BytesIO(path.read_bytes())) as im:
                ids = label(np.asarray(im) > 0, connectivity=2, background=0)
        boxes = geometry.tile_boxes((rgb.shape[1], rgb.shape[0]))
        rebuilt = [geometry.reassemble_exact(geometry.extract_tiles(a, boxes), boxes, a.shape) for a in (rgb, ids)]
        for actual, expected in zip(rebuilt, (rgb, ids), strict=True):
            check_equal(actual, expected, "Selected figure reconstruction differs")
        payloads[row["sample"]] = {"sample": row["sample"], "label": int(row["label"]), "rgb": rgb,
                                   "ids": ids, "rebuilt_rgb": rebuilt[0], "rebuilt_ids": rebuilt[1], "boxes": boxes,
                                   "coverage": geometry.coverage_map((rgb.shape[1], rgb.shape[0]), boxes)}
    out = audit_dir / "figure_review"
    out.mkdir(exist_ok=False)
    with plt.rc_context({"axes.titlesize": 8, "figure.titlesize": 12}):
        hashes = render_figures(out, payloads, selection)
    write_json(out / "FIGURE_MANIFEST.json", {"reason": "Shorter title typography only; original PNGs and frozen audit unchanged",
               "renderer_sha256": sha(Path(__file__)), "audit_protocol_sha256": manifest["protocol_sha256"],
               "rgb_local_only": True, "sha256": hashes})
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/external/VisA")
    args = parser.parse_args()
    print(render_review(args.audit, args.data_root))
