"""Default: model-free preflight. Real limited smoke requires explicit --execute."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.dataset import safe_component
from sr_anomaly.pcb_tiled_runner import execute_smoke, preflight, write_json


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run-id", required=True, help="new unique output/report identifier")
    cli.add_argument("--scope", choices=("full-pilot", "model-smoke"), default="full-pilot")
    cli.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    cli.add_argument("--data-root", type=Path, default=os.environ.get("VISA_ROOT"))
    torch_home = Path(os.environ.get("TORCH_HOME", Path.home()/".cache/torch"))
    cli.add_argument("--backbone-checkpoint", type=Path, default=os.environ.get("PATCHCORE_BACKBONE_CHECKPOINT",
        torch_home/"hub/checkpoints/wide_resnet50_2-95faca4d.pth"))
    cli.add_argument("--swinir-checkpoint", type=Path, default=os.environ.get("SWINIR_X4_CHECKPOINT",
        ROOT/"checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth"))
    cli.add_argument("--ram-budget-gib", type=float, help="optional positive cap on currently available RAM, not total host RAM")
    cli.add_argument("--execute", action="store_true", help="execute limited model-smoke only after passing preflight; full-pilot remains blocked")
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.ram_budget_gib is not None and (not 0 < args.ram_budget_gib < float("inf")):
        cli.error("--ram-budget-gib must be finite and positive")
    run_id = safe_component(args.run_id, "run-id")
    report_dir = ROOT/"analysis/pcb_tiled_preflight"/run_id
    output = ROOT/"outputs/pcb-tiled-smoke"/run_id
    if report_dir.exists() or output.exists():
        raise FileExistsError("Existing report/payload is never overwritten; choose a new --run-id")
    report = preflight(ROOT, args.data_root, args.backbone_checkpoint, args.swinir_checkpoint,
        scope=args.scope, device=args.device,
        ram_budget=int(args.ram_budget_gib*1024**3) if args.ram_budget_gib is not None else None)
    report_dir.mkdir(parents=True, exist_ok=False)
    write_json(report_dir/"preflight.json", report)
    print(json.dumps({"status": report["status"], "scope": args.scope, "blockers": report["blockers"],
                      "report": str(report_dir.relative_to(ROOT))}, ensure_ascii=False))
    if args.execute:
        state = execute_smoke(report, ROOT, args.data_root, output)
        print(json.dumps({"raw_smoke_status": state["status"], "payload": str(output.relative_to(ROOT)),
                          "full_pilot": "NOT_READY_FOR_FULL_PILOT", "metrics": None}))
    return 0 if report["status"] == "PREFLIGHT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
