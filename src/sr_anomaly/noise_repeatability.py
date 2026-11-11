"""Analyze saved realistic-noise v2 text artifacts with paired image resampling."""
from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess

import numpy as np

from .analysis_io import csv_rows, digest, read_json, relative_source, write_csv, write_json
from .analysis_statistics import paired_bootstrap_mean_delta
from .fusion import normalize, quantile_threshold, robust_params

RESTORERS = ('bicubic_x4', 'swinir_x4', 'realesrnet_x4plus', 'realesrgan_x4plus')
CONDITIONS = ('noise_s5', 'noise_s15')


def close(actual, expected):
    if not math.isfinite(float(actual)) or not math.isclose(float(actual), float(expected), abs_tol=1e-6, rel_tol=1e-8):
        raise ValueError('Stored scalar arithmetic mismatch')


def public_protocol(protocol):
    result = copy.deepcopy(protocol)
    value = result['v1_bank_dir']
    changed = bool(PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute())
    if changed:
        result['v1_bank_dir'] = f"outputs/realistic-degradation/{protocol['category']}-v1/bank"
    return result, ['v1_bank_dir'] if changed else []


def source_byte_identity(body, expected):
    if hashlib.sha256(body).hexdigest() == expected:
        return 'git_blob'
    crlf = body.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    if hashlib.sha256(crlf).hexdigest() == expected:
        return 'git_CRLF_checkout'
    raise ValueError('Producer source content differs from both recorded Git checkout forms')


def load_run(directory, repo, references):
    protocols = list(directory.glob('PROTOCOL*.json'))
    if len(protocols) != 1:
        raise ValueError('Expected one supplied protocol')
    protocol = read_json(protocols[0])
    category, seed = protocol['category'], protocol['noise_seed']
    if (protocol['family'] != 'realistic_lr_noise_v2' or category not in ('hazelnut', 'screw')
            or seed not in (23, 37) or protocol['split_seed'] != 11 or protocol['bank_refit']
            or protocol['conditions'] != list(CONDITIONS) or protocol['restorers'] != list(RESTORERS)
            or protocol['quantile'] != .99):
        raise ValueError('Different fixed noise queue')
    session = read_json(directory / 'sessions/000.json')
    if session['units_complete'] != 8 or session['units_planned'] != 8:
        raise ValueError('Incomplete run')
    source_commit = session['source_commit']
    if len(source_commit) != 40 or any(c not in '0123456789abcdef' for c in source_commit):
        raise ValueError('Expected an exact producer source commit')
    source_bindings = {}
    for name, sha in protocol['code_sha256'].items():
        relative_source(repo, name)
        body = subprocess.check_output(['git', '-C', str(repo), 'show', source_commit + ':' + name])
        source_bindings[name] = source_byte_identity(body, sha)
    reference = references / 'realistic' / f'{category}-v1' / 'PROTOCOL.json'
    if digest(reference) != protocol['v1_protocol_sha256']:
        raise ValueError('Historical v1 protocol binding mismatch')
    previous = read_json(reference)
    for key in ('fit_paths', 'calibration_paths', 'test', 'train_sha256', 'checkpoints', 'revisions', 'split_seed'):
        if protocol[key] != previous[key]:
            raise ValueError('Fixed v1 split/input/checkpoint changed: ' + key)
    fit, cal = set(protocol['fit_paths']), set(protocol['calibration_paths'])
    test = {r['sample']: int(r['label']) for r in protocol['test']}
    if (len(fit) != len(protocol['fit_paths']) or len(cal) != len(protocol['calibration_paths'])
            or len(test) != len(protocol['test']) or fit & cal or fit & set(test) or cal & set(test)
            or protocol['bank_fit_images'] != len(fit)):
        raise ValueError('Split duplication or fit count mismatch')
    summary = csv_rows(directory / 'summary.csv')
    indexed = {(r['condition'], r['restorer']): r for r in summary}
    if len(indexed) != 8 or len(summary) != 8:
        raise ValueError('Missing or duplicate summary condition')
    units, protocol_hashes, shared_hashes = {}, set(), {}
    for condition in CONDITIONS:
        for restorer in RESTORERS:
            key = condition, restorer
            unit_name = condition + '__' + restorer
            unit = read_json(directory / 'units' / (unit_name + '.json'))
            table_name = 'units/' + unit_name + '.csv'
            table = relative_source(directory, table_name)
            if digest(table) != unit['files'][table_name]:
                raise ValueError('Per-image table hash mismatch')
            if (unit['unit'] != unit_name or unit['category'] != category or unit['condition'] != condition
                    or unit['restorer'] != restorer or unit['noise_seed'] != seed or unit['split_seed'] != 11):
                raise ValueError('Unit identity mismatch')
            protocol_hashes.add(unit['protocol_sha256'])
            rows = csv_rows(table)
            by_sample = {r['sample']: r for r in rows}
            if len(by_sample) != len(rows) or set(by_sample) != cal | set(test):
                raise ValueError('Per-image sample alignment mismatch')
            if set(unit['degraded_lr_sha256']) != set(by_sample):
                raise ValueError('LR receipt sample set mismatch')
            for sample, row in by_sample.items():
                expected_label = test[sample] if sample in test else 0
                expected_split = 'test' if sample in test else 'calibration'
                if (int(row['label']) != expected_label or row['split'] != expected_split
                        or row['restorer'] != restorer or row['condition'] != condition
                        or int(row['noise_seed']) != seed
                        or row['degraded_lr_sha256'] != unit['degraded_lr_sha256'][sample]):
                    raise ValueError('Per-image identity or LR hash mismatch')
                shared = condition, sample
                if shared in shared_hashes and shared_hashes[shared] != row['degraded_lr_sha256']:
                    raise ValueError('Restorers received different LR bytes')
                shared_hashes[shared] = row['degraded_lr_sha256']
                if expected_label:
                    value = float(row['per_image_aupro'])
                    if not math.isfinite(value) or not 0 <= value <= 1:
                        raise ValueError('Invalid per-image AU-PRO')
                elif row['per_image_aupro'] != '':
                    raise ValueError('Normal per-image AU-PRO must be NA')
            if unit['images'] != {'calibration': len(cal), 'test': len(test)}:
                raise ValueError('Unit image count mismatch')
            expected_params = robust_params(np.array([float(by_sample[s]['image_score']) for s in sorted(cal)]))
            for field in ('median', 'scale', 'q25', 'q75'):
                close(expected_params[field], unit['calibration']['image'][field])
            expected_threshold = quantile_threshold(normalize(
                np.array([float(by_sample[s]['image_score']) for s in sorted(cal)]), expected_params), .99)
            close(expected_threshold, unit['metrics']['image_threshold'])
            saved = indexed[key]
            for name, value in unit['metrics'].items():
                close(saved[name], value)
            for name, value in unit['means'].items():
                close(saved['mean_' + name], value)
                close(value, np.mean([float(by_sample[s][name]) for s in test]))
            units[key] = dict(receipt=unit, rows=by_sample)
    if len(protocol_hashes) != 1:
        raise ValueError('Units refer to different execution protocols')
    execution_sha = next(iter(protocol_hashes))
    original_supplied = protocols[0].name == 'PROTOCOL.json'
    if original_supplied and digest(protocols[0]) != execution_sha:
        raise ValueError('Original execution protocol hash mismatch')
    return dict(category=category, noise_seed=seed, protocol=protocol, units=units, summary=summary,
        source_commit=source_commit, source_byte_bindings=source_bindings, execution_protocol_sha256=execution_sha,
        original_protocol_bytes_supplied=original_supplied, supplied_protocol_sha256=digest(protocols[0]),
        protocol_filename=protocols[0].name, shared_lr_hashes=shared_hashes,
        source_worktree_dirty=session['source_worktree_dirty'],
        tracked_worktree_dirty=session['tracked_worktree_dirty'])


def contrast_pair(left, right):
    if set(left) != set(right):
        raise ValueError('Paired sample identities differ')
    names = sorted(s for s in left if left[s]['split'] == 'test' and int(left[s]['label']) == 1)
    for name in left:
        if (left[name]['label'] != right[name]['label'] or left[name]['split'] != right[name]['split']
                or left[name]['degraded_lr_sha256'] != right[name]['degraded_lr_sha256']):
            raise ValueError('Paired input/label differs')
    return names, np.array([float(left[s]['per_image_aupro']) - float(right[s]['per_image_aupro']) for s in names])


def across_noise_seeds(seed_rows, repeats=2000, seed=11):
    if len(seed_rows) != 2 or seed_rows[0][0] != seed_rows[1][0]:
        raise ValueError('Two noise draws must use the same ordered image identities')
    values = np.mean(np.stack([r[1] for r in seed_rows]), axis=0)
    result = paired_bootstrap_mean_delta(values, repeats, np.random.default_rng(seed))
    return dict(n_unique_images=result['n'], mean_delta=result['estimate'],
                ci95_low=result['ci95'][0], ci95_high=result['ci95'][1])


def analyze(runs, output, plan):
    lookup = {(r['category'], r['noise_seed']): r for r in runs}
    if len(lookup) != 4 or len(runs) != 4:
        raise ValueError('Expected four unique complete runs')
    condition_rows, contrasts, per_image, repeatability, protocol_receipts = [], [], [], [], []
    pairs = [plan['primary_contrast'], *plan['secondary_contrasts']]
    for category in plan['categories']:
        first, second = [lookup[category, s] for s in plan['noise_seeds']]
        for field in ('bank_artifact_sha256', 'fit_paths', 'calibration_paths', 'test', 'code_sha256', 'checkpoints'):
            if first['protocol'][field] != second['protocol'][field]:
                raise ValueError('Controls differ across noise draws: ' + field)
        changed = sum(first['shared_lr_hashes'][k] != second['shared_lr_hashes'][k]
                      for k in first['shared_lr_hashes'])
        protocol_receipts.append(dict(category=category, changed_lr_hashes=changed,
            compared_lr_samples=len(first['shared_lr_hashes']), bank_hashes_match=True))
        for noise_seed in plan['noise_seeds']:
            run = lookup[category, noise_seed]
            for row in run['summary']:
                condition_rows.append(dict(row, study_family='realistic_lr_noise_v2',
                    protocol_id=run['execution_protocol_sha256'], seed=11, train_count=len(run['protocol']['fit_paths']),
                    test_count=len(run['protocol']['test']), n_anomaly=sum(int(t['label']) for t in run['protocol']['test']),
                    variant=row['condition'] + '__' + row['restorer'], dataset='MVTecAD',
                    source_run=f'realistic-noise-v2-{category}-noise{noise_seed}',
                    source_artifact='unit receipts and saved per-image CSVs'))
        for condition in plan['conditions']:
            for left, right in pairs:
                seed_values, pooled = [], []
                for noise_seed in plan['noise_seeds']:
                    run = lookup[category, noise_seed]
                    a, b = [run['units'][condition, r] for r in (left, right)]
                    names, delta = contrast_pair(a['rows'], b['rows'])
                    stats = paired_bootstrap_mean_delta(delta, plan['bootstrap_repeats'],
                                                          np.random.default_rng(plan['bootstrap_seed']))
                    pooled_delta = a['receipt']['metrics']['au_pro'] - b['receipt']['metrics']['au_pro']
                    row = dict(category=category, condition=condition, noise_seed=noise_seed,
                        contrast=left + '_minus_' + right, primary=left==plan['primary_contrast'][0] and right==plan['primary_contrast'][1],
                        pooled_aupro_delta=pooled_delta, mean_per_image_delta=stats['estimate'],
                        median_per_image_delta=float(np.median(delta)), ci95_mean_low=stats['ci95'][0],
                        ci95_mean_high=stats['ci95'][1], negative_images=int((delta < 0).sum()),
                        n_unique_images=len(names))
                    contrasts.append(row);seed_values.append((names, delta));pooled.append(pooled_delta)
                    per_image.extend(dict(category=category, condition=condition, noise_seed=noise_seed,
                        contrast=row['contrast'], sample=s, per_image_aupro_delta=float(d))
                        for s,d in zip(names,delta,strict=True))
                repeatability.append(dict(category=category, condition=condition, contrast=left+'_minus_'+right,
                    pooled_delta_seed23=pooled[0], pooled_delta_seed37=pooled[1],
                    pooled_delta_range=max(pooled)-min(pooled), signs_agree=bool(np.sign(pooled[0])==np.sign(pooled[1])),
                    **across_noise_seeds(seed_values,plan['bootstrap_repeats'],plan['bootstrap_seed'])))
    write_csv(output/'conditions.csv', condition_rows)
    write_csv(output/'contrasts.csv', contrasts)
    write_csv(output/'per_image_deltas.csv', per_image)
    write_csv(output/'repeatability.csv', repeatability)
    write_json(output/'cross_seed_controls.json',protocol_receipts)
    return condition_rows, contrasts, repeatability
