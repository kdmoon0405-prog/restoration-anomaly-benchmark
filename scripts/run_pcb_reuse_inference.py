"""Fixed real-bank integration preflight; opt-in CUDA execution, never full cohort."""
from pathlib import Path
import argparse
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sr_anomaly import pcb_reuse_inference as reuse


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--bank-run',type=Path,required=True)
    parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--device',choices=('cuda',),default='cuda')
    torch_home=Path(os.environ.get('TORCH_HOME',Path.home()/'.cache/torch'))
    parser.add_argument('--backbone-checkpoint',type=Path,default=os.environ.get('PATCHCORE_BACKBONE_CHECKPOINT',torch_home/'hub/checkpoints/wide_resnet50_2-95faca4d.pth'))
    parser.add_argument('--swinir-checkpoint',type=Path,default=os.environ.get('SWINIR_X4_CHECKPOINT',ROOT/'checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth'))
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args(argv)
    try:
        output,state=reuse.prepare(ROOT,args.bank_run,args.data_root,args.backbone_checkpoint,args.swinir_checkpoint,run_id=args.run_id)
        print(json.dumps(dict(output=str(output),**state)))
        if state['status']!='PREFLIGHT_PASS':return 2
        if args.execute:
            print(json.dumps(reuse.execute(output,ROOT,args.bank_run,args.data_root)))
        return 0
    except (ValueError,OSError,RuntimeError) as error:
        print(json.dumps(dict(error=f'{type(error).__name__}: {error}',full_pilot_approved=False)))
        return 2


if __name__=='__main__':raise SystemExit(main())
