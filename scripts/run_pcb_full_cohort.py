"""Real PCB 180/200 raw cohort: preflight (bank byte-copy), opt-in CUDA execution, verified resume."""
from pathlib import Path
import argparse
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sr_anomaly import pcb_full_cohort as full


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--bank-run',type=Path,required=True)
    parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--device',choices=('cuda',),default='cuda')
    torch_home=Path(os.environ.get('TORCH_HOME',Path.home()/'.cache/torch'))
    parser.add_argument('--backbone-checkpoint',type=Path,default=os.environ.get('PATCHCORE_BACKBONE_CHECKPOINT',torch_home/'hub/checkpoints/wide_resnet50_2-95faca4d.pth'))
    parser.add_argument('--swinir-checkpoint',type=Path,default=os.environ.get('SWINIR_X4_CHECKPOINT',ROOT/'checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth'))
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--execute',action='store_true',help='preflight a NEW run-id, then run')
    mode.add_argument('--resume',action='store_true',help='continue an existing run-id; verified units are skipped')
    parser.add_argument('--max-units',type=int,default=None,help='stop after N new units (connection check)')
    parser.add_argument('--note',default='')
    args=parser.parse_args(argv)
    try:
        if args.resume:
            output=(ROOT/full.OUTPUT_BASE/args.run_id).resolve()
        else:
            output,state=full.prepare(ROOT,args.bank_run,args.data_root,args.backbone_checkpoint,args.swinir_checkpoint,run_id=args.run_id)
            print(json.dumps(dict(output=str(output),status=state['status'])))
            if not args.execute:return 0
        state=full.execute(output,ROOT,args.bank_run,args.data_root,max_units=args.max_units,note=args.note)
        print(json.dumps({k:state.get(k) for k in ('status','units_complete','units_total','error')}))
        return 0
    except (ValueError,OSError,RuntimeError,MemoryError) as error:
        print(json.dumps(dict(error=f'{type(error).__name__}: {error}')))
        return 2


if __name__=='__main__':raise SystemExit(main())
