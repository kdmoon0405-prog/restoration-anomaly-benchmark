"""Read-only full-cap synthetic-probe review; no model or execution option."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.pcb_fullcap_review import PASS, review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-run", type=Path,
                        help="Explicit local limited-smoke metadata directory; required for a passing review")
    args = parser.parse_args(argv)
    result = review(args.run, args.output, ROOT, args.reference_run)
    print(json.dumps(dict(status=result["status"], full_pilot_approved=False)))
    return 0 if result["status"] == PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
