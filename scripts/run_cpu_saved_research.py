"""Run exploratory CPU spatial-budget and calibrated operating-point analyses."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.cpu_saved_research import run_saved_research


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/cpu_saved_research.json")
    parser.add_argument("--campaign-status", type=Path)
    args = parser.parse_args(argv)
    result = run_saved_research(args.artifact_root, args.output, args.config,
                               campaign_status=args.campaign_status)
    print(json.dumps({k: result[k] for k in ("status", "total_images", "budget_rows", "elapsed_seconds")}))


if __name__ == "__main__":
    main()
