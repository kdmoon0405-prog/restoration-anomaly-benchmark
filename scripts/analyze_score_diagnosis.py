"""Describe empirical FPR plateaus; never select a deployment threshold."""
from pathlib import Path
import argparse
import math
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sr_anomaly.analysis_io import csv_rows, digest, new_output, write_csv, write_json


def plateau(normals, anomalies, false_positives):
    normals = np.sort(np.asarray(normals, dtype=float))[::-1]
    anomalies = np.asarray(anomalies, dtype=float)
    if (normals.ndim != 1 or anomalies.ndim != 1 or not anomalies.size
            or not np.isfinite(normals).all() or not np.isfinite(anomalies).all()
            or not 0 < false_positives < len(normals)):
        raise ValueError('Finite vectors and an interior positive FP count required')
    high = float(normals[false_positives - 1])
    low = math.nextafter(float(normals[false_positives]), math.inf)
    if high < low:
        return dict(attainable=False, tpr_low=None, tpr_high=None)
    assert int((normals >= high).sum()) == false_positives
    assert int((normals >= low).sum()) == false_positives
    return dict(attainable=True, tpr_low=float((anomalies >= high).mean()),
                tpr_high=float((anomalies >= low).mean()))


def analyze(diagnosis, output):
    source = diagnosis / 'analysis/image_score_diagnosis/pcb/pcb_per_board_decisions.csv'
    boards = csv_rows(source)
    if (len(boards) != 200 or len({r['sample'] for r in boards}) != 200
            or sum(r['label'] == '0' for r in boards) != 100
            or sum(r['label'] == '1' for r in boards) != 100):
        raise ValueError('Expected the reviewed 100 normal/100 anomalous boards')
    rows = []
    for variant in ('clean', 'bicubic_x4', 'swinir_x4'):
        normal = [float(r[variant + '_norm_score']) for r in boards if r['label'] == '0']
        anomaly = [float(r[variant + '_norm_score']) for r in boards if r['label'] == '1']
        for k in (1, 3, 5, 10):
            rows.append(dict(variant=variant, false_positives=k, fpr=k / 100,
                             **plateau(normal, anomaly, k)))
    output = new_output(output, inputs=(diagnosis,))
    write_csv(output / 'empirical_fpr_plateaus.csv', rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), layout='constrained')
    variants = ('clean', 'bicubic_x4', 'swinir_x4')
    for ax, k in zip(axes.flat, (1, 3, 5, 10), strict=True):
        for i, variant in enumerate(variants):
            row = next(r for r in rows if r['variant'] == variant and r['false_positives'] == k)
            if row['attainable']:
                ax.plot([row['tpr_low'], row['tpr_high']], [i, i], linewidth=5,
                        marker='|', markersize=12, markeredgewidth=2, color=f'C{i}')
                ax.text(row['tpr_high'] + .02, i, f"{row['tpr_low']:.2f}-{row['tpr_high']:.2f}", va='center', fontsize=8)
        ax.set(yticks=range(3), yticklabels=variants, xlim=(0, 1.16), ylim=(-.6, 2.6),
               xlabel='Attainable TPR within the same empirical-FP plateau', title=f'{k}/100 normal false positives')
        ax.grid(axis='x', alpha=.2)
    fig.suptitle('Post-hoc threshold plateaus, 100 normal + 100 anomalous PCB boards')
    fig.savefig(output / 'empirical_fpr_plateaus.png', dpi=160)
    plt.close(fig)
    write_json(output / 'manifest.json', dict(status='COMPLETE', kind='posthoc_empirical_fpr_description',
        threshold_selected=False, research_method_changed=False, source_sha256=digest(source),
        analysis_code_sha256=digest(Path(__file__)), files={p.name: digest(p) for p in output.iterdir()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnosis', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    analyze(args.diagnosis, args.output)
