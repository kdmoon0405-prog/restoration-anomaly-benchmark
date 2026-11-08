"""Aggregate completed CPU controls without inflating the number of independent images."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.cpu_control_analysis import analyze_controls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-swinir", action="store_true")
    args = parser.parse_args()
    kwargs = dict(expected_variants=("clean", "bicubic_x4", "unsharp_x4", "swinir_x4"),
                  candidate="swinir_x4") if args.include_swinir else {}
    result = analyze_controls(args.run, args.output, **kwargs)
    print(json.dumps({k: result[k] for k in ("status", "quality_unique_rows", "independent_anomaly_image_units")}))
