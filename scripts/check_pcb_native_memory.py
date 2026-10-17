"""Model-free postprocessing memory rehearsal; default is preflight ONLY."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import pcb_native_memory as memory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--scope", choices=("small", "native"), default="small")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ram-budget-gib", type=float, help="optional downward RAM cap; never removes fixed 2 GiB reserve")
    parser.add_argument("--timeout-seconds", type=float, default=3600, help="per-worker limit, default 3600 seconds")
    parser.add_argument("--worker", choices=memory.STAGES, help=argparse.SUPPRESS)
    parser.add_argument("--variant", choices=memory.VARIANTS, help=argparse.SUPPRESS)
    parser.add_argument("--payload", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        if not args.execute or not args.payload or not args.variant:
            parser.error("Internal worker requires --execute, owned payload and variant")
        memory.worker(ROOT, args.payload, args.worker, args.variant)
        return 0
    if not args.run_id:
        parser.error("--run-id is required")
    cap = args.ram_budget_gib
    if cap is not None and (not math.isfinite(cap) or cap <= 0):
        parser.error("--ram-budget-gib must be positive and finite")
    result, output = memory.run(ROOT, args.run_id, args.scope, args.data_root, execute=args.execute,
        ram_cap=int(cap*1024**3) if cap is not None else None, timeout=args.timeout_seconds)
    print(json.dumps({"status": result["status"], "output": str(output), "full_pilot_approved": False}))
    return 0 if result["status"] in ("PREFLIGHT_PASS", "MEMORY_REHEARSAL_COMPLETE_NOT_FULL_APPROVAL") else 2


if __name__ == "__main__":
    raise SystemExit(main())
