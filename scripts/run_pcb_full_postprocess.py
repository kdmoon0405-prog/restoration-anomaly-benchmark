"""PCB full-cohort postprocessing: ONE existing v0.6 stage (and variant) per process; no model, no SR rerun.

calibration -> normalize -> quality -> evaluate --variant V / perboard --variant V
GT (native frozen evaluation_mask, no resize/pad/dilation) enters only evaluate/perboard.
Outputs are never overwritten; a finished stage is skipped by refusing its existing directory.
"""
from pathlib import Path
import argparse
import csv
import json
import shutil
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sr_anomaly import pcb_board_analysis as board
from sr_anomaly import pcb_full_cohort as full
from sr_anomaly.bounded_bank import file_sha256
from sr_anomaly.pcb_native_memory import process_memory, Monitor
from sr_anomaly.pcb_tiled_runner import available_ram
from sr_anomaly.tiled_cpu_pipeline import Parent

BASE=ROOT/'outputs/pcb-full-postprocess'


def _parents(raw):
    state,parents=board.load_raw_run(raw)
    return state,parents


def per_board(raw,calibration,normalized,variant,inputs,output):
    """Per test board on the existing normalized maps; per-image AU-PRO only where a GT region exists."""
    from sr_anomaly.evaluation import area_under_per_region_overlap, binary_roc_auc, connected_components
    state=board.load_normalized(normalized,raw,calibration)
    _,parents=board.load_raw_run(raw)
    inventory={p.sample:p for p in parents}
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for row in (r for r in state['rows'] if r['variant']==variant):
        values=np.asarray(board._map(normalized,row,dtype=np.float64))
        mask=inputs.evaluation_mask(inventory[row['sample']])
        if mask.shape!=values.shape or bool(mask.any())!=bool(row['label']):
            raise ValueError('GT native shape/label mismatch')
        region=mask.astype(bool)
        item=dict(sample=row['sample'],label=row['label'],variant=variant,normalized_image_score=row['score'],
                  map_max=float(values.max()),map_mean=float(values.mean()))
        if row['label']:
            item.update(defect_area_pixels=int(region.sum()),defect_area_ratio=float(region.mean()),
                region_count=int(connected_components(region,connectivity=1).max()),
                per_image_aupro=area_under_per_region_overlap(region[None],values[None],max_fpr=.3,num_thresholds=200),
                per_image_pixel_auroc=binary_roc_auc(region.ravel(),values.ravel()),
                roi_mean=float(values[region].mean()),background_mean=float(values[~region].mean()))
            item['roi_bg_gap']=item['roi_mean']-item['background_mean']
        rows.append(item);del values,mask,region
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (output/'per_board.csv').open('x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    meta=dict(kind='board_per_image',variant=variant,status='COMPLETE',rows=len(rows),
              normalized_status_sha256=file_sha256(Path(normalized)/'status.json'),per_board_sha256=file_sha256(output/'per_board.csv'),
              gt_receipts=inputs.gt_receipts)
    (output/'status.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('calibration','normalize','quality','evaluate','perboard'))
    parser.add_argument('--raw-run-id',required=True)
    parser.add_argument('--data-root',type=Path,help='needed by evaluate/perboard (GT) only')
    parser.add_argument('--variant',choices=full.fit.models.VARIANTS)
    args=parser.parse_args(argv)
    raw=(ROOT/full.OUTPUT_BASE/args.raw_run_id).resolve()
    base=BASE/args.raw_run_id;base.mkdir(parents=True,exist_ok=True)
    cal,norm=base/'calibration',base/'normalized'
    if args.stage in ('evaluate','perboard') and (args.variant is None or args.data_root is None):
        parser.error('evaluate/perboard need --variant and --data-root')
    name=args.stage+(f'-{args.variant}' if args.variant else '')
    record=dict(stage=args.stage,variant=args.variant,raw_run=str(raw),raw_status_sha256=file_sha256(raw/'status.json'),
                argv=sys.argv,python=sys.executable,available_ram_at_start_bytes=available_ram(),
                free_disk_at_start_bytes=shutil.disk_usage(base).free,start_time=time.strftime('%Y-%m-%dT%H:%M:%S'))
    monitor=Monitor(base/'.monitor');(base/'.monitor').mkdir(exist_ok=True);monitor.start()
    start=time.perf_counter()
    try:
        if args.stage=='calibration':result=board.fit_calibration(raw,cal)
        elif args.stage=='normalize':result=board.apply_calibration(raw,cal,norm)
        elif args.stage=='quality':
            spool=full.FullRGBSpool(raw);_,parents=_parents(raw)
            result=board.quality_report(parents,spool.reference,spool.tiles,base/'quality',
                provenance=dict(raw_status_sha256=record['raw_status_sha256'],source='stored prepared RGB spool; no SR rerun'))
        else:
            inputs=full.fit.binding.FrozenPCBInputs(ROOT,args.data_root)
            if args.stage=='evaluate':
                result=board.evaluate_variant(raw,cal,norm,args.variant,inputs.evaluation_mask,base/name)
                (base/name/'gt_receipts.json').write_text(json.dumps(inputs.gt_receipts,indent=1),encoding='utf-8')
            else:result=per_board(raw,cal,norm,args.variant,inputs,base/name)
        record.update(status='COMPLETE',result_status=result.get('status'))
    except BaseException as error:
        record.update(status='BLOCKED_MEMORY' if isinstance(error,MemoryError) else 'FAILED',error=f'{type(error).__name__}: {error}',
                      resume_command=' '.join(['.venv/Scripts/python.exe','scripts/run_pcb_full_postprocess.py',*sys.argv[1:]]))
        raise
    finally:
        record.update(elapsed_seconds=time.perf_counter()-start,process_memory=monitor.finish(),end=process_memory(),
                      end_time=time.strftime('%Y-%m-%dT%H:%M:%S'))
        attempt=0
        while (base/f'{name}.record{"" if not attempt else f"-{attempt}"}.json').exists():attempt+=1
        (base/f'{name}.record{"" if not attempt else f"-{attempt}"}.json').write_text(json.dumps(record,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:record[k] for k in ('stage','variant','status','elapsed_seconds')}))
    return 0


if __name__=='__main__':raise SystemExit(main())
