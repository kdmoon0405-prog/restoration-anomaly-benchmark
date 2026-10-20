"""Read-only resource-smoke consistency review; accepts no inference/full option."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.pcb_resource_review import review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = review(args.run, args.output, args.source_root)
    print(json.dumps({"status": result["status"], "full_pilot_approved": False}))
    return 0 if result["status"] == "CONSISTENCY_VERIFIED_NOT_FULL_APPROVAL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
