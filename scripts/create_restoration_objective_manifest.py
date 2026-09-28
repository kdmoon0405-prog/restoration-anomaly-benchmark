"""Freeze the deterministic 25-image Hazelnut restoration-objective pilot."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.objective_study import build_pilot_manifest, load_pilot_manifest, write_pilot_manifest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--output", type=Path, default=ROOT / "analysis" / "restoration_objective_pilot" / "pilot_manifest.csv")
    parser.add_argument("--check", action="store_true", help="Validate the frozen manifest without rewriting it")
    args = parser.parse_args()
    if args.check:
        rows = load_pilot_manifest(args.output, args.data_root.resolve())
        print(f"Validated {len(rows)} frozen selections in {args.output}")
    else:
        rows = build_pilot_manifest(args.data_root.resolve())
        write_pilot_manifest(rows, args.output)
        print(f"Saved {len(rows)} pre-inference selections to {args.output}")


if __name__ == "__main__":
    main()
