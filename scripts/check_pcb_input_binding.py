"""Default: frozen metadata only. --execute verifies files sequentially, never models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.pcb_input_binding import audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--hashes-only", action="store_true", help="stream all source hashes without decoding or native arrays; requires --execute")
    args = parser.parse_args(argv)
    if args.hashes_only and not args.execute:
        parser.error("--hashes-only requires --execute")
    try:
        state, output = audit(ROOT, args.run_id, args.data_root, execute=args.execute, hashes_only=args.hashes_only)
    except MemoryError as error:
        print(json.dumps({"status": "BLOCKED_MEMORY", "error": str(error), "full_pilot_approved": False}))
        return 2
    print(json.dumps({"status": state["status"], "output": str(output), "full_pilot_approved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
