"""Read-only scalar checks and paired image-AUROC uncertainty for frozen rules."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess

import numpy as np

from .analysis_io import csv_rows, digest, read_json, relative_source
from .evaluation import binary_roc_auc, classification_metrics
from .fusion import normalize, quantile_threshold, robust_params
from .noise_repeatability import close, source_byte_identity

RULES = ('original', 'map_max', 'top0.1pct_mean', 'top0.5pct_mean', 'top1pct_mean')


def paired_auc_intervals(labels, scores, repeats=2000, seed=11):
    labels = np.asarray(labels)
    scores = np.asarray(scores, dtype=np.float64)
    if (labels.ndim != 1 or scores.shape != (len(labels), len(RULES))
            or not np.isin(labels, [0, 1]).all() or not np.isfinite(scores).all()
            or not isinstance(repeats, int) or repeats < 2):
        raise ValueError('Invalid paired labels, scores or bootstrap repetitions')
    groups = [np.flatnonzero(labels == value) for value in (0, 1)]
    if any(len(group) == 0 for group in groups):
        raise ValueError('Both label classes are required')
    point = np.asarray([binary_roc_auc(labels, scores[:, j]) for j in range(len(RULES))])
    rng = np.random.default_rng(seed)
    deltas = np.empty((repeats, len(RULES) - 1))
    for repeat in range(repeats):
        indices = np.concatenate([rng.choice(group, len(group), replace=True) for group in groups])
        aucs = np.asarray([binary_roc_auc(labels[indices], scores[indices, j])
                           for j in range(len(RULES))])
        deltas[repeat] = aucs[1:] - aucs[0]
    return [{'rule': rule, 'image_auroc': float(point[j]),
             'delta_vs_original': float(point[j] - point[0]),
             'ci_low': float(np.quantile(deltas[:, j - 1], .025)),
             'ci_high': float(np.quantile(deltas[:, j - 1], .975))}
            for j, rule in enumerate(RULES[1:], 1)]


def verify_scalar_unit(unit, rows):
    expected_counts = unit['counts']
    if (unit['anchor_a_original'] != 'EXACT' or set(unit['anchor_b_map_payload']) != {'pixel_params_equal', 'pixel_threshold_equal', 'npz_sha256_equal'}
            or any(value is not True for value in unit['anchor_b_map_payload'].values())
            or unit['k'] != {'top0.1pct_mean': 51, 'top0.5pct_mean': 251, 'top1pct_mean': 502}
            or set(unit['rules']) != set(RULES)):
        raise ValueError('Missing anchors or different frozen rules')
    grouped = {rule: {} for rule in RULES}
    for row in rows:
        rule = row['rule']
        if (rule not in grouped or row['sample'] in grouped[rule]
                or row['unit_id'] != unit['unit_id'] or row['category'] != unit['category']
                or row['split'] not in ('calibration', 'test') or row['label'] not in ('0', '1')
                or row['source_npz_sha256'] != unit['source_sha256']['npz']):
            raise ValueError('Duplicate or inconsistent sample/rule/source')
        grouped[rule][row['sample']] = row
    identities = {sample: (row['split'], row['label']) for sample, row in grouped['original'].items()}
    calibration = sorted(sample for sample, identity in identities.items() if identity[0] == 'calibration')
    test = sorted(sample for sample, identity in identities.items() if identity[0] == 'test')
    if (set(calibration) & set(test) or len(calibration) != expected_counts['calibration']
            or any(identities[sample][1] != '0' for sample in calibration)):
        raise ValueError('Invalid normal-only calibration or split count')
    labels = np.asarray([int(identities[sample][1]) for sample in test])
    if ((labels == 0).sum() != expected_counts['test_normal']
            or (labels == 1).sum() != expected_counts['test_anomaly']):
        raise ValueError('Test label counts differ')
    output_scores = []
    summaries = []
    for rule in RULES:
        table = grouped[rule]
        if {sample: (row['split'], row['label']) for sample, row in table.items()} != identities:
            raise ValueError('Paired sample alignment differs')
        params = robust_params(np.asarray([float(table[s]['raw_score']) for s in calibration]))
        expected = unit['rules'][rule]
        for key in ('median', 'scale', 'q25', 'q75'):
            close(params[key], expected['calibration'][key])
        if params['method'] != expected['calibration']['method']:
            raise ValueError('Calibration fallback differs')
        threshold = quantile_threshold(normalize([float(table[s]['raw_score']) for s in calibration], params), .99)
        close(threshold, expected['threshold'])
        all_samples = calibration + test
        normalized = normalize([float(table[s]['raw_score']) for s in all_samples], params)
        for sample, value in zip(all_samples, normalized):
            close(value, table[sample]['normalized_score'])
            close(threshold, table[sample]['threshold'])
            if int(table[sample]['flagged']) != int(value >= threshold):
                raise ValueError('Stored decision differs')
        scores = normalized[len(calibration):]
        metrics = classification_metrics(labels, scores, threshold)
        metrics.update(image_false_alarm_rate_test_normal=float((scores[labels == 0] >= threshold).mean()),
                       image_miss_rate_test_anomaly=float((scores[labels == 1] < threshold).mean()))
        for key, value in metrics.items():
            close(value, expected['metrics'][key])
        output_scores.append(scores)
        summaries.append(dict(unit_id=unit['unit_id'], category=unit['category'], rule=rule, **metrics))
    return test, labels, np.column_stack(output_scores), summaries


def load_category(directory, repo):
    directory = Path(directory)
    receipt = read_json(directory / 'RECEIPT.json')
    for item in receipt['files']:
        path = relative_source(directory, item['path'])
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('Return file hash differs')
    protocol = read_json(directory / 'PROTOCOL.json')
    if protocol['rules'] != list(RULES) or protocol['quantile'] != .99 or protocol['units_planned'] != 40:
        raise ValueError('Different aggregation protocol')
    sessions = list((directory / 'sessions').glob('*.json'))
    if len(sessions) != 1:
        raise ValueError('Expected one supplied category session')
    session = read_json(sessions[0])
    commit = session['source_commit']
    if not re.fullmatch('[0-9a-f]{40}', commit) or session['units_complete'] != 20:
        raise ValueError('Invalid execution source or incomplete category')
    source_forms = {}
    for name, expected in protocol['code_sha256'].items():
        relative_source(directory, name)
        body = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=repo)
        source_forms[name] = source_byte_identity(body, expected)
    units = []
    for path in sorted((directory / 'units').glob('*.json')):
        unit = read_json(path)
        csv_path = path.with_suffix('.csv')
        if (unit['protocol_sha256'] != digest(directory / 'PROTOCOL.json')
                or unit['per_image_csv_sha256'] != digest(csv_path)
                or session['units'].get(unit['unit_id']) != 'COMPLETE'):
            raise ValueError('Unit source/protocol linkage differs')
        samples, labels, scores, summary = verify_scalar_unit(unit, csv_rows(csv_path))
        units.append((unit, samples, labels, scores, summary))
    if len(units) != 20 or len({u[0]['unit_id'] for u in units}) != 20:
        raise ValueError('Expected 20 distinct supplied units')
    return units, {'execution_commit': commit, 'source_byte_forms': source_forms,
                   'supplied_files_verified': len(receipt['files']),
                   'remote_payload_validation_observed': False}
