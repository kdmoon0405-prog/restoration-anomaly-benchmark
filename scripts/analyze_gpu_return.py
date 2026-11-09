"""Analyze saved PCB/realistic-degradation return rows, without model execution."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.gpu_return_analysis import analyze

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = analyze(args.package, args.output)
    print(json.dumps({k: result[k] for k in ("status", "pcb_boards", "realistic_conditions", "new_master_rows")}))
