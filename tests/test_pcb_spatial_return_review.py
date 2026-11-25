import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[1] / 'scripts/review_pcb_spatial_return.py'
    spec = importlib.util.spec_from_file_location('pcb_spatial_return', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    common = dict(sample='synthetic', selection_group='success_control', regression_type='improvement_or_tie')
    selected = [dict(common, delta_roi_bg_gap='2', delta_per_image_aupro='0.1')]
    calibration = {v: dict(pixel=dict(scale=2. if v == 'bicubic_x4' else 1., median=0.))
                   for v in ('clean', 'bicubic_x4', 'swinir_x4')}
    rows = []
    for v, roi, x, y in [('clean', 5., 1., 1.), ('bicubic_x4', 3., 0., 0.), ('swinir_x4', 4., 3., 4.)]:
        scale = calibration[v]['pixel']['scale']
        rows.append(dict(common, variant=v, raw_roi_mean=roi, raw_background_mean=1., raw_roi_bg_gap=roi-1,
            normalized_roi_mean=roi/scale, normalized_background_mean=1/scale,
            normalized_roi_bg_gap=(roi-1)/scale, gt_area_pixels=3, gt_on_seam_pixels=1, gt_on_seam_ratio=1/3,
            centroid_x=x, centroid_y=y, delta_raw_roi_bg_gap=1., delta_normalized_roi_bg_gap=2.,
            centroid_displacement_pixels=5., map_correlation=.9, seam_gradient_mean=2., nonseam_gradient_mean=1.))
    components = [dict(common, component_id=i, area_pixels=i, clean_mean=5., bicubic_x4_mean=1.5,
                       swinir_x4_mean=4.) for i in (1, 2)]
    return rows, components, selected, calibration


def test_units_and_component_arithmetic(module):
    cases, gradients = module.summarize(*fixture())
    assert cases[0]['centroid_displacement_pixels'] == 5
    assert cases[0]['delta_raw_roi_bg_gap'] == 1
    bicubic = next(r for r in gradients if r['variant'] == 'bicubic_x4')
    assert bicubic['raw_seam_gradient'] == 4 and bicubic['seam_nonseam_ratio'] == 2


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'component', 'delta', 'nan'])
def test_reject_inconsistent_csv(module, mutation):
    rows, components, selected, calibration = fixture()
    if mutation == 'duplicate':
        rows.append(rows[0].copy())
    elif mutation == 'missing':
        rows.pop()
    elif mutation == 'component':
        components[0]['clean_mean'] = 100
    elif mutation == 'delta':
        rows[0]['delta_normalized_roi_bg_gap'] = 100
    else:
        rows[0]['seam_gradient_mean'] = float('nan')
    with pytest.raises(ValueError):
        module.summarize(rows, components, selected, calibration)


def test_receipt_and_tamper_guard(module, tmp_path):
    body = b'synthetic text\n'
    path = tmp_path / 'report.md'
    path.write_bytes(body)
    receipt = dict(schema='team-public-text-return-v1', owner='juhyung', files=[
        dict(path='report.md', bytes=len(body), sha256=hashlib.sha256(body).hexdigest())])
    (tmp_path / 'RECEIPT.json').write_text(json.dumps(receipt), encoding='utf-8')
    module.verify_receipt(tmp_path)
    path.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash/size'):
        module.verify_receipt(tmp_path)
