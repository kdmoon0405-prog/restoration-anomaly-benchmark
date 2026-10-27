"""Default preflight only; opt-in synthetic full-cap resource fixture, never full pilot."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from sr_anomaly import pcb_fullcap_probe as probe


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run-id", required=True)
    cli.add_argument("--smoke-run", required=True, type=Path)
    cli.add_argument("--backbone-checkpoint", type=Path, default=os.environ.get("PATCHCORE_BACKBONE_CHECKPOINT",
        Path(os.environ.get("TORCH_HOME", Path.home()/".cache/torch"))/"hub/checkpoints/wide_resnet50_2-95faca4d.pth"))
    cli.add_argument("--swinir-checkpoint", type=Path, default=os.environ.get("SWINIR_X4_CHECKPOINT",
        ROOT/"checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth"))
    cli.add_argument("--execute", action="store_true", help="explicit synthetic bank/RGB resource probe; never fits a PCB bank")
    args = cli.parse_args(argv)
    output, state = probe.prepare(ROOT, args.smoke_run, args.backbone_checkpoint,
                                  args.swinir_checkpoint, run_id=args.run_id)
    if args.execute and state["status"] == "PREFLIGHT_PASS":
        state = probe.execute(output, ROOT)
    print(json.dumps(dict(status=state["status"], output=str(output), full_pilot_approved=False,
                         blockers=state.get("blockers", []))))
    return 0 if state["status"] in ("PREFLIGHT_PASS", probe.COMPLETE) else 2


if __name__ == "__main__":
    raise SystemExit(main())
