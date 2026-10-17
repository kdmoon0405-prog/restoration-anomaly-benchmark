"""Explain frozen GT-ID sampling with a figure only; no alternative geometry."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
from PIL import Image
from skimage.measure import label


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=root / "data/external/VisA")
    args = parser.parse_args()
    out = args.audit / "figures/component_sampling_details.png"
    if out.exists():
        raise FileExistsError("Do not overwrite an inspected figure")
    manifest = json.loads((args.audit / "MANIFEST.json").read_text())
    protocol = json.loads((args.audit / "PROTOCOL.json").read_text())
    assert hashlib.sha256((args.audit / "PROTOCOL.json").read_bytes()).hexdigest() == manifest["protocol_sha256"]
    assert protocol["target_wh"] == [224, 224] and protocol["crop"] is None and protocol["padding"] is None
    with (args.audit / "INPUTS.csv").open(newline="", encoding="utf-8") as handle:
        inputs = {r["sample"]: r for r in csv.DictReader(handle)}
    with (args.audit / "components.csv").open(newline="", encoding="utf-8") as handle:
        components = {(r["sample"], int(r["component_id"])): r for r in csv.DictReader(handle)}
    cases = json.loads((args.audit / "selected_examples.json").read_text())
    fig, axes = plt.subplots(len(cases), 3, figsize=(12, 3.7 * len(cases)), squeeze=False)
    colors = ListedColormap(["#171b20", "#999999", "#36e04b"])
    for row, case in enumerate(cases):
        sample, identity = case["sample"], case["illustrated_source_component_id"]
        record, component = inputs[sample], components[sample, identity]
        image_path, mask_path = args.data_root / sample, args.data_root / record["mask"]
        assert hashlib.sha256(image_path.read_bytes()).hexdigest() == record["image_sha256"]
        assert hashlib.sha256(mask_path.read_bytes()).hexdigest() == record["mask_sha256"]
        with Image.open(mask_path) as mask:
            ids = label(np.asarray(mask) > 0, connectivity=2, background=0)
        height, width = ids.shape
        target = np.asarray(Image.fromarray(ids.astype(np.int32)).resize((224, 224), Image.Resampling.NEAREST))
        assert int((ids == identity).sum()) == int(component["source_area_pixels"])
        assert int((target == identity).sum()) == int(component["target_positive_samples"])
        x0, y0, x1, y1 = json.loads(component["source_bbox_xyxy"])
        left, top, right, bottom = max(0, x0-12), max(0, y0-12), min(width, x1+12), min(height, y1+12)
        with Image.open(image_path) as image:
            axes[row, 0].imshow(image.convert("RGB").crop((left, top, right, bottom)), interpolation="nearest")
        axes[row, 0].contour(ids[top:bottom, left:right] == identity, levels=[.5], colors=["lime"], linewidths=.8)
        axes[row, 0].set_title(f"{Path(sample).name}, source ID {identity}\nRGB zoom ONLY; selected GT contour")
        source_view = ids[top:bottom, left:right]
        coded = (source_view > 0).astype(int) + (source_view == identity)
        axes[row, 1].imshow(coded, cmap=colors, vmin=0, vmax=2, interpolation="nearest")
        # Obtain the actual nearest-selected source indices, not a reimplemented sampler.
        xs = np.asarray(Image.fromarray(np.arange(width, dtype=np.int32)[None]).resize((224, 1), Image.Resampling.NEAREST)).ravel()
        ys = np.asarray(Image.fromarray(np.arange(height, dtype=np.int32)[:, None]).resize((1, 224), Image.Resampling.NEAREST)).ravel()
        gx, gy = np.meshgrid(xs[(xs >= left) & (xs < right)]-left, ys[(ys >= top) & (ys < bottom)]-top)
        axes[row, 1].scatter(gx.ravel(), gy.ravel(), marker="x", color="cyan", s=25, linewidths=.8)
        axes[row, 1].set_title(f"Original GT: {component['source_area_pixels']} source pixels\nGreen=selected ID; cyan=GT sample centers")
        lx, ty = max(0, int(left*224/width)-1), max(0, int(top*224/height)-1)
        rx, by = min(224, int(np.ceil(right*224/width))+1), min(224, int(np.ceil(bottom*224/height))+1)
        target_view = target[ty:by, lx:rx]
        coded = (target_view > 0).astype(int) + (target_view == identity)
        axes[row, 2].imshow(coded, cmap=colors, vmin=0, vmax=2, interpolation="nearest")
        axes[row, 2].set_title(f"224 target: {component['target_positive_samples']} samples of this ID\nGray=other GT; not a pixel-retention ratio")
        for axis in axes[row]:
            axis.axis("off")
    fig.suptitle("Fixed nearest GT sampler: selected original ID, not physical defect count. Zooms never enter model inputs.")
    fig.tight_layout()
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print("Rendered frozen-ID sampling detail; input hashes and source/target sample counts matched")


if __name__ == "__main__":
    main()
