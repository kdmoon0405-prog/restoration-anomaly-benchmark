"""Inspect VisA PCB files/masks only, without fitting/inference/test metrics."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from scripts.analyze_map_gating_feasibility import digest, relative, write_json
from sr_anomaly.dataset import VisASplitCSV
from sr_anomaly.fusion import split_train_calibration


def inspect_category(root, split_csv, category):
    train = VisASplitCSV(root, split_csv, "train", category).samples()
    test = VisASplitCSV(root, split_csv, "test", category).samples()
    if not train or not test or any(sample.metadata["label"] for sample in train):
        raise ValueError("Normal-only training and nonempty official test split required")
    paths = [sample.relative_path.as_posix() for sample in train + test]
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicated/overlapping split image paths")
    sizes, raw_empty, geometry_empty, misaligned = Counter(), 0, 0, 0
    for sample in train + test:
        with Image.open(sample.path) as image:
            width, height = image.size
            sizes[f"{width}x{height}"] += 1
        if sample.mask_path:
            with Image.open(sample.mask_path) as source:
                if source.size != (width, height):
                    misaligned += 1
                mask = np.asarray(source.convert("L")) > 0
                raw_empty += int(not mask.any() or mask.all())
                size = (256, int(256 * height / width)) if width <= height else (int(256 * width / height), 256)
                resized = source.convert("L").resize(size, Image.Resampling.NEAREST)
                left, top = (int(round((side - 224) / 2.)) for side in size)
                canonical = np.asarray(resized.crop((left, top, left + 224, top + 224))) > 0
                geometry_empty += int(not canonical.any())
    normal = sum(sample.metadata["label"] == 0 for sample in test)
    anomalous = len(test) - normal
    if not normal or not anomalous:
        raise ValueError("Both official normal/anomaly test groups required")
    fit, calibration = split_train_calibration(len(train), .8, 11)
    return {"category": category, "train_normal": len(train), "test_normal": normal, "test_anomaly": anomalous,
            "total_images": len(train) + len(test), "sizes": dict(sizes), "raw_mask_invalid_count": raw_empty,
            "mask_dimension_mismatch_count": misaligned, "canonical_mask_empty_count": geometry_empty,
            "raw_complete": raw_empty == 0 and misaligned == 0, "proposed_fit": len(fit), "proposed_calibration": len(calibration)}


def choose_category(rows):
    eligible = [row for row in rows if row.get("raw_complete") and not row.get("execution_traces")]
    return min(eligible, key=lambda row: (row["total_images"], row["category"])) if eligible else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/external/VisA")
    args = parser.parse_args()
    rule_path = args.output / "PCB_SELECTION_RULE.json"
    if rule_path.exists():
        raise FileExistsError("Readiness audit already exists; do not overwrite")
    args.output.mkdir(parents=True, exist_ok=True)
    split = args.data_root / "split_csv/1cls.csv"
    write_json(rule_path, {"rule": "Before file/mask audit: among complete PCB categories with no observed local result trace, lowest official train+test count; exact tie lexical category",
                           "scope": "Readiness only, no model execution/performance selection; no claim about unobserved machines",
                           "geometry": "Resize shortest edge 256, center crop 224; GT nearest-neighbor; later 224->56 Pillow x4",
                           "source_csv": relative(split), "source_csv_sha256": digest(split) if split.exists() else None})
    if not split.exists():
        write_json(args.output / "PCB_INVENTORY.json", {"blocked": "Missing official VisA split_csv/1cls.csv"})
        return
    traces = {name: [] for name in ("pcb1", "pcb2", "pcb3", "pcb4")}
    for directory in (ROOT / "outputs", ROOT / "checkpoints"):
        for path in directory.rglob("*.json"):
            if path.name not in {"results.json", "metadata.json", "split.json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for category in traces:
                if f'"category": "{category}"' in text:
                    traces[category].append(relative(path))
    rows = []
    for category in traces:
        try:
            row = inspect_category(args.data_root, split, category)
        except (FileNotFoundError, ValueError) as error:
            row = {"category": category, "raw_complete": False, "blocked": str(error).replace(str(ROOT), "repository")}
        row["execution_traces"] = traces[category]
        rows.append(row)
    chosen = choose_category(rows)
    write_json(args.output / "PCB_INVENTORY.json", {"categories": rows, "recommended_category": chosen["category"] if chosen else None,
                                                  "prior_use_scope": "No claim about external teammate machines; obtain usage confirmation before independent-validation label"})
    print(json.dumps({"recommended": chosen["category"] if chosen else None, "inventory": rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
