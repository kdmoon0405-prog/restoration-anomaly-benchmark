"""Review returned nine-case scalar descriptors without loading maps or GT."""
from pathlib import Path
import argparse
import hashlib
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sr_anomaly.analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json

VARIANTS = ('clean', 'bicubic_x4', 'swinir_x4')


def verify_receipt(directory):
    receipt = read_json(directory / 'RECEIPT.json')
    if receipt['schema'] != 'team-public-text-return-v1' or receipt['owner'] != 'juhyung':
        raise ValueError('Unexpected return receipt')
    seen = set()
    for row in receipt['files']:
        name = row['path']
        path = relative_source(directory, name)
        if name.casefold() in seen or path.is_symlink():
            raise ValueError('Duplicate path or symlink')
        seen.add(name.casefold())
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Return receipt hash/size mismatch')
    return receipt


def close(actual, expected):
    if not math.isfinite(actual) or not math.isfinite(expected) or not math.isclose(
            actual, expected, abs_tol=1e-6, rel_tol=1e-7):
        raise ValueError(f'Inconsistent scalar arithmetic: {actual}, {expected}')


def summarize(rows, components, selected, calibration):
    fixed = {r['sample']: r for r in selected}
    index = {(r['sample'], r['variant']): r for r in rows}
    if (len(index) != len(rows) or set(index) != {(s, v) for s in fixed for v in VARIANTS}):
        raise ValueError('Missing or duplicate board/variant')
    component_keys = {(r['sample'], int(r['component_id'])) for r in components}
    if len(component_keys) != len(components) or {s for s, _ in component_keys} != set(fixed):
        raise ValueError('Missing or duplicate GT component')
    variant_rows, cases = [], []
    for sample, case in fixed.items():
        group = [r for r in components if r['sample'] == sample]
        if any(int(r['area_pixels']) <= 0 for r in group):
            raise ValueError('Nonpositive component area')
        area = sum(int(r['area_pixels']) for r in group)
        for v in VARIANTS:
            r = index[sample, v]
            if r['selection_group'] != case['selection_group'] or r['regression_type'] != case['regression_type']:
                raise ValueError('Fixed case taxonomy changed')
            if area != int(r['gt_area_pixels']):
                raise ValueError('Component/board GT area mismatch')
            if not 0 <= int(r['gt_on_seam_pixels']) <= area:
                raise ValueError('Invalid seam/GT count')
            close(float(r['gt_on_seam_ratio']), int(r['gt_on_seam_pixels']) / area)
            scale, median = calibration[v]['pixel']['scale'], calibration[v]['pixel']['median']
            if not math.isfinite(scale) or scale <= 0:
                raise ValueError('Invalid calibration scale')
            for prefix in ('raw', 'normalized'):
                close(float(r[prefix + '_roi_bg_gap']),
                      float(r[prefix + '_roi_mean']) - float(r[prefix + '_background_mean']))
            close(float(r['normalized_roi_bg_gap']), float(r['raw_roi_bg_gap']) / scale)
            close(float(r['normalized_roi_mean']), (float(r['raw_roi_mean']) - median) / scale)
            close(float(r['normalized_roi_mean']),
                  sum(int(c['area_pixels']) * float(c[v + '_mean']) for c in group) / area)
            seam, other = float(r['seam_gradient_mean']), float(r['nonseam_gradient_mean'])
            if not math.isfinite(seam) or not math.isfinite(other) or seam < 0 or other <= 0:
                raise ValueError('Invalid gradient descriptor')
            variant_rows.append(dict(sample=sample, selection_group=case['selection_group'], variant=v,
                normalized_seam_gradient=seam, normalized_nonseam_gradient=other,
                raw_seam_gradient=seam * scale, raw_nonseam_gradient=other * scale,
                seam_nonseam_ratio=seam / other))
        b, s = index[sample, 'bicubic_x4'], index[sample, 'swinir_x4']
        raw_delta = float(s['raw_roi_bg_gap']) - float(b['raw_roi_bg_gap'])
        normalized_delta = float(s['normalized_roi_bg_gap']) - float(b['normalized_roi_bg_gap'])
        displacement = math.hypot(float(s['centroid_x']) - float(b['centroid_x']),
                                  float(s['centroid_y']) - float(b['centroid_y']))
        for v in VARIANTS:
            r = index[sample, v]
            close(float(r['delta_raw_roi_bg_gap']), raw_delta)
            close(float(r['delta_normalized_roi_bg_gap']), normalized_delta)
            close(float(r['centroid_displacement_pixels']), displacement)
        close(normalized_delta, float(case['delta_roi_bg_gap']))
        if not math.isfinite(float(s['map_correlation'])) or not -1 <= float(s['map_correlation']) <= 1:
            raise ValueError('Invalid map correlation')
        cases.append(dict(sample=sample, selection_group=case['selection_group'],
            regression_type=case['regression_type'], delta_per_image_aupro=float(case['delta_per_image_aupro']),
            delta_raw_roi_bg_gap=raw_delta, delta_normalized_roi_bg_gap=normalized_delta,
            centroid_displacement_pixels=displacement, map_correlation=float(s['map_correlation']),
            components=len(group), gt_area_pixels=area))
    return cases, variant_rows


def run(spatial, addendum, metadata, output, analysis_commit):
    for directory in (spatial, addendum):
        verify_receipt(directory)
    manifest = read_json(spatial / 'manifest.json')
    if (manifest['status'] != 'COMPLETE' or manifest['boards_analyzed'] != 9
            or manifest['maps_analyzed'] != 27 or manifest['connectivity'] != 4
            or manifest['population_estimate'] or manifest['research_metrics_recomputed']):
        raise ValueError('Incomplete or different analysis contract')
    selected_path = ROOT / 'analysis/gpu_return_20261109/selected_native_map_cases.csv'
    if digest(selected_path) != manifest['selection_sha256']:
        raise ValueError('Fixed case selection changed')
    if len(analysis_commit) != 40 or any(c not in '0123456789abcdef' for c in analysis_commit):
        raise ValueError('Use the exact analysis source commit')
    for name in ('scripts/analyze_pcb_selected_maps.py', 'src/sr_anomaly/pcb_selected_spatial.py'):
        body = subprocess.check_output(['git', '-C', str(ROOT), 'show', analysis_commit + ':' + name])
        if hashlib.sha256(body).hexdigest() != manifest['source_sha256'][name]:
            raise ValueError('Analysis source hash mismatch')
    for name, sha in manifest['files'].items():
        if name.endswith('.png'):
            continue
        if digest(relative_source(spatial, name)) != sha:
            raise ValueError('Manifest file hash mismatch')
    selected = csv_rows(selected_path)
    inputs = read_json(spatial / 'input_receipts.json')
    maps = {(r['sample'], r['variant']): r for r in inputs['maps']}
    if len(maps) != 27 or len(inputs['maps']) != 27:
        raise ValueError('Map receipt count/identity mismatch')
    inventory = {r['sample']: r for r in csv_rows(
        ROOT / 'analysis/pcb_geometry/pcb2-native224-tiling-20261016/INPUTS.csv')}
    for case in selected:
        sample = case['sample']
        for v in VARIANTS:
            item = maps[sample, v]
            if item['file'] != case[v + '_file'] or item['sha256'] != case[v + '_sha256']:
                raise ValueError('Map receipt does not match fixed selection')
        gt, rgb, frozen = inputs['gt'][sample], inputs['rgb'][sample], inventory[sample]
        if (gt['file_sha256'] != frozen['mask_sha256'] or gt['mask_path'] != frozen['mask']
                or rgb['file_sha256'] != frozen['image_sha256']
                or gt['shape'] != [int(frozen['source_height']), int(frozen['source_width'])]):
            raise ValueError('Native RGB/GT file receipt mismatch')
    calibration = {v: read_json(metadata / f'pcb/postprocess/calibration/{v}.json') for v in VARIANTS}
    binding = read_json(ROOT / 'analysis/gpu_return_20261109/analysis_manifest.json')['sources']
    for v in VARIANTS:
        name = f'pcb/postprocess/calibration/{v}.json'
        if digest(metadata / name) != binding[name]:
            raise ValueError('Calibration metadata changed')
    protocol = read_json(metadata / 'pcb/raw-run/PROTOCOL.json')
    if digest(metadata / 'pcb/raw-run/PROTOCOL.json') != binding['pcb/raw-run/PROTOCOL.json']:
        raise ValueError('Raw prediction protocol changed')
    if (manifest['runtime_source_commit'] != protocol['source_commit']
            or manifest['runtime_source_worktree_dirty'] != protocol['source_worktree_dirty']):
        raise ValueError('Legacy runtime field differs from raw prediction provenance')
    cases, gradients = summarize(csv_rows(spatial / 'spatial_descriptors.csv'),
        csv_rows(spatial / 'component_descriptors.csv'), selected, calibration)
    output = new_output(output, inputs=(spatial, addendum, metadata))
    write_csv(output / 'per_case_review.csv', cases)
    write_csv(output / 'gradient_units.csv', gradients)
    state = dict(status='SUPPLIED_SCALAR_CONSISTENCY_VERIFIED', selected_boards=9,
        components=sum(r['components'] for r in cases), source_commit_file_hashes_match=analysis_commit,
        actual_analysis_git_head_independently_observed=False,
        raw_prediction_source_commit=protocol['source_commit'],
        raw_prediction_source_worktree_dirty=protocol['source_worktree_dirty'],
        legacy_runtime_field_role='raw prediction provenance, not the analysis checkout',
        maps_matching_previously_verified_receipts=27, raw_arrays_recomputed_locally=False,
        gt_decoded_locally=False, remote_pngs_supplied=0, remote_pngs_viewed_locally=0,
        population_estimate=False, dataset_metrics_recomputed=False,
        source_sha256={'spatial_receipt': digest(spatial / 'RECEIPT.json'),
                       'addendum_receipt': digest(addendum / 'RECEIPT.json')})
    write_json(output / 'review.json', state)
    return cases, gradients


def render_summary(output, cases, gradients):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    styles = {'clean': ('#0072B2', 'o'), 'bicubic_x4': ('#D55E00', 's'),
              'swinir_x4': ('#009E73', '^')}
    for variant, (color, marker) in styles.items():
        values = {(r['sample'], r['variant']): r for r in gradients}
        axes[0].plot(range(len(cases)), [values[c['sample'], variant]['seam_nonseam_ratio']
                     for c in cases], linestyle='none', marker=marker, color=color, label=variant)
    names = [Path(c['sample']).stem for c in cases]
    axes[0].set(xticks=range(len(cases)), xticklabels=names, xlabel='Selected board ID',
                ylabel='Seam / non-seam mean gradient (ratio)', title='Fixed tile-boundary association',
                ylim=(0, 26))
    axes[0].axhline(1, color='gray', linewidth=0.7, linestyle='--')
    axes[0].legend(fontsize=8)
    group_styles = {'suppression': ('#D55E00', 's'),
        'geometry_candidate': ('#0072B2', '^'), 'success_control': ('#009E73', 'o')}
    for group, (color, marker) in group_styles.items():
        subset = [c for c in cases if c['selection_group'] == group]
        axes[1].scatter([c['centroid_displacement_pixels'] for c in subset],
            [c['delta_per_image_aupro'] for c in subset], marker=marker, color=color, label=group)
        for c in subset:
            axes[1].annotate(Path(c['sample']).stem,
                (c['centroid_displacement_pixels'], c['delta_per_image_aupro']),
                xytext=(4, 4), textcoords='offset points', fontsize=8)
    axes[1].axhline(0, color='gray', linewidth=0.7)
    axes[1].set(xlabel='Positive-excess centroid displacement (native pixels)',
        ylabel='Per-image AU-PRO delta (SwinIR - Bicubic)', title='Selected cases, n = 9 boards',
        xlim=(0, 20))
    axes[1].legend(fontsize=7)
    fig.savefig(output / 'selected_descriptors.png', dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spatial-run', type=Path, required=True)
    parser.add_argument('--addendum-run', type=Path, required=True)
    parser.add_argument('--metadata-root', type=Path, required=True)
    parser.add_argument('--analysis-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases, gradients = run(args.spatial_run, args.addendum_run, args.metadata_root,
                           args.output, args.analysis_source_commit)
    render_summary(args.output, cases, gradients)
    print('Supplied scalar consistency verified; native arrays/figures remain a separate coverage item')


if __name__ == '__main__':
    main()
