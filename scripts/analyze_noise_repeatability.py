"""Review the four fixed realistic-noise v2 return folders on CPU."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sr_anomaly.analysis_io import digest, new_output, read_json, write_json
from sr_anomaly.noise_repeatability import analyze, load_run, public_protocol
from review_pcb_spatial_return import verify_receipt


def plot_summary(output, contrasts, repeatability):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = [(c, s) for c in ('hazelnut', 'screw') for s in ('noise_s5', 'noise_s15')]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), layout='constrained')
    for seed, offset, marker, color in [(23, -.07, 'o', '#0072B2'), (37, .07, '^', '#D55E00')]:
        rows = {(r['category'],r['condition']):r for r in contrasts if r['primary'] and r['noise_seed']==seed}
        axes[0].scatter([i+offset for i in range(4)], [rows[g]['pooled_aupro_delta'] for g in groups],
                        marker=marker,color=color,label=f'noise seed {seed}')
    rows={(r['category'],r['condition']):r for r in repeatability
          if r['contrast']=='swinir_x4_minus_bicubic_x4'}
    for i,g in enumerate(groups):
        r=rows[g];mean=r['mean_delta']
        axes[1].errorbar(i,mean,yerr=[[mean-r['ci95_low']],[r['ci95_high']-mean]],
                         fmt='o',color='#0072B2',capsize=4)
        axes[1].annotate(f"n={r['n_unique_images']}",(i,mean),xytext=(6,5),textcoords='offset points',fontsize=8)
    labels=[c.title()+'\n'+s.replace('noise_s','sigma ') for c,s in groups]
    for ax in axes:
        ax.axhline(0,color='gray',linewidth=.8)
        ax.set_xticks(range(4),labels)
        ax.set_xlim(-.4,3.5)
    axes[0].set(title='Stored pooled AU-PRO deltas',ylabel='SwinIR - Bicubic')
    axes[0].legend(fontsize=9)
    axes[1].set(title='Two-draw mean per-image deltas',ylabel='Mean delta with 95% image-bootstrap CI')
    fig.savefig(output/'noise_repeatability.png',dpi=170)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs',type=Path,required=True)
    parser.add_argument('--references',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    plan=read_json(ROOT/'configs/noise_repeatability_analysis.json')
    runs=[];source_receipts={}
    for category in plan['categories']:
        for seed in plan['noise_seeds']:
            directory=args.runs/f'realistic-noise-v2-{category}-noise{seed}'
            verify_receipt(directory)
            runs.append(load_run(directory,ROOT,args.references))
            source_receipts[directory.name]=digest(directory/'RECEIPT.json')
    output=new_output(args.output,inputs=(args.runs,args.references))
    write_json(output/'analysis_plan.json',plan)
    state=dict(status='BUILDING',source_receipts=source_receipts,arrays_supplied=0,
        raw_array_values_verified=False,detection_metrics_recomputed=False,
        ci_unit='unique anomalous image,noise-draw mean computed before resampling',
        bootstrap_repeats=plan['bootstrap_repeats'],bootstrap_seed=plan['bootstrap_seed'],
        script_sha256=digest(Path(__file__)),module_sha256=digest(ROOT/'src/sr_anomaly/noise_repeatability.py'))
    write_json(output/'analysis_manifest.json',state)
    try:
        conditions,contrasts,repeated=analyze(runs,output,plan)
        views=output/'public_protocols';views.mkdir();exports=[]
        for run in runs:
            name=f"{run['category']}-noise{run['noise_seed']}.json"
            protocol,changes=public_protocol(run['protocol'])
            write_json(views/name,protocol)
            exports.append(dict(file=name,changed_fields=changes,
                supplied_protocol_sha256=run['supplied_protocol_sha256'],
                execution_protocol_sha256=run['execution_protocol_sha256'],
                original_execution_protocol_bytes_supplied=run['original_protocol_bytes_supplied'],
                public_copy_sha256=digest(views/name)))
        write_json(output/'protocol_exports.json',exports)
        plot_summary(output,contrasts,repeated)
        state.update(status='COMPLETE_SCALAR_REVIEW',runs=4,conditions=len(conditions),
            per_seed_contrasts=len(contrasts),source_commit=runs[0]['source_commit'],
            source_worktree_dirty=[r['source_worktree_dirty'] for r in runs],
            tracked_worktree_dirty=[r['tracked_worktree_dirty'] for r in runs],
            public_files={p.relative_to(output).as_posix():digest(p) for p in output.rglob('*')
                          if p.is_file() and p.name!='analysis_manifest.json'})
    except Exception as error:
        state.update(status='FAILED',error=f'{type(error).__name__}: {error}')
        write_json(output/'analysis_manifest.json',state)
        raise
    write_json(output/'analysis_manifest.json',state)
    print(json.dumps({k:state[k] for k in ['status','runs','conditions','per_seed_contrasts']}))


if __name__=='__main__':
    main()
