"""Default: existing limited model-smoke preflight. --execute is explicitly opt-in."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import pcb_model_resources as resources


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run-id", required=True)
    cli.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    cli.add_argument("--data-root", type=Path, default=os.environ.get("VISA_ROOT"))
    torch_home = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache/torch"))
    cli.add_argument("--backbone-checkpoint", type=Path, default=os.environ.get(
        "PATCHCORE_BACKBONE_CHECKPOINT", torch_home / "hub/checkpoints/wide_resnet50_2-95faca4d.pth"))
    cli.add_argument("--swinir-checkpoint", type=Path, default=os.environ.get(
        "SWINIR_X4_CHECKPOINT", ROOT / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth"))
    cli.add_argument("--ram-budget-gib", type=float)
    cli.add_argument("--execute", action="store_true", help="limited model-smoke only; never enables full pilot")
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.ram_budget_gib is not None and not 0 < args.ram_budget_gib < float("inf"):
        cli.error("--ram-budget-gib must be finite and positive")
    output, report = resources.prepare(ROOT, args.data_root, args.backbone_checkpoint, args.swinir_checkpoint,
        run_id=args.run_id, device=args.device,
        ram_budget=int(args.ram_budget_gib * 1024**3) if args.ram_budget_gib is not None else None)
    print(json.dumps({"status": report["status"], "blockers": report["blockers"],
                      "output": str(output.relative_to(ROOT)), "full_pilot": "BLOCKED"}))
    if report["status"] != "PREFLIGHT_PASS":
        return 2
    if args.execute:
        result = resources.execute(output, ROOT)
        print(json.dumps({"status": result["status"], "full_pilot_approved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
