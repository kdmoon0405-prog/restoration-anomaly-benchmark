"""Verify supplied aggregation scalars and bootstrap the fixed rule contrasts."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sr_anomaly.analysis_io import csv_rows, new_output, write_csv, write_json
from sr_anomaly.image_score_return import load_category, paired_auc_intervals
from sr_anomaly.noise_repeatability import close


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--returns', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = new_output(args.output, [args.returns])
    plan = dict(kind='posthoc_uncertainty_for_frozen_aggregation_rules', repeats=2000, seed=11,
                sampling='paired stratified image IDs;fixed class counts;identical indices for every rule',
                estimand='per-unit image-AUROC difference vs original;conditional on observed bank/noise draw',
                multiple_comparison='exploratory pointwise intervals;no test-based rule selection',
                repeated_conditions='shared image cohorts;no independent200-condition count',
                pixel_metrics='stored reference only;no new AU-PRO or pooled CI')
    write_json(output / 'analysis_plan.json', plan)
    all_cells, intervals, checks, identities = [], [], {}, {}
    source_summary = {}
    for category in ('hazelnut', 'screw'):
        directory = args.returns / ('image-score-aggregation-20261111-' + category)
        for row in csv_rows(directory / 'summary.csv'):
            key = row['unit_id'], row['rule']
            if key in source_summary and source_summary[key] != row:
                raise ValueError('Conflicting duplicate summary cell')
            source_summary[key] = row
        units, checks[category] = load_category(directory, ROOT)
        for unit, samples, labels, scores, summary in units:
            identity = list(zip(samples, labels.tolist()))
            if category in identities and identities[category] != identity:
                raise ValueError('Category test identities differ between units')
            identities[category] = identity
            for row in summary:
                expected = source_summary[(row['unit_id'], row['rule'])]
                for key in ('image_auroc', 'image_f1', 'image_false_alarm_rate_test_normal', 'image_miss_rate_test_anomaly'):
                    close(row[key], expected[key])
                all_cells.append(row)
            for result in paired_auc_intervals(labels, scores, plan['repeats'], plan['seed']):
                intervals.append(dict(unit_id=unit['unit_id'], category=category,
                                      family=unit['family'], noise_seed=unit['noise_seed'],
                                      condition=unit['condition'], restorer=unit['restorer'], **result))
            print('VERIFIED', unit['unit_id'], flush=True)
    if len(source_summary) != 200 or len(all_cells) != 200:
        raise ValueError('Expected 200 unique cells')
    write_csv(output / 'verified_cells.csv', all_cells)
    write_csv(output / 'paired_auc_intervals.csv', intervals)
    write_json(output / 'verification.json', dict(source_checks=checks, units=40, cells=200,
               original_anchor_scalar_recomputed=40, raw_npz_received=False,
               calibration_map_anchor='reported by GPU;not recomputed from absent maps locally'))
    print(json.dumps(dict(units=40, cells=200, intervals=len(intervals))))


if __name__ == '__main__':
    main()
