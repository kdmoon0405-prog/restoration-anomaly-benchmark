"""Freeze a deterministic Hazelnut restoration-endpoint test manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.objective_study import (  # noqa: E402
    build_full_manifest, build_pilot_manifest, load_full_manifest, load_pilot_manifest, write_pilot_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--cohort", choices=("pilot25", "full110"), default="pilot25")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true", help="Validate the frozen manifest without rewriting it")
    args = parser.parse_args()
    full = args.cohort == "full110"
    output = args.output or ROOT / "analysis" / ("restoration_objective_full" if full else "restoration_objective_pilot") / ("full_manifest.csv" if full else "pilot_manifest.csv")
    build = build_full_manifest if full else build_pilot_manifest
    load = load_full_manifest if full else load_pilot_manifest
    if args.check:
        rows = load(output, args.data_root.resolve())
        print(f"Validated {len(rows)} frozen images in {output}")
    else:
        if full and output.exists():
            raise FileExistsError(f"Manifest already exists: {output}; use --check")
        rows = build(args.data_root.resolve())
        if full and (len(rows), sum(int(row["label"]) == 0 for row in rows), sum(int(row["label"]) == 1 for row in rows)) != (110, 40, 70):
            raise ValueError("Full Hazelnut cohort must contain 110 images: 40 normal and 70 anomalous")
        write_pilot_manifest(rows, output)
        print(f"Saved {len(rows)} pre-inference images to {output}")


if __name__ == "__main__":
    main()
