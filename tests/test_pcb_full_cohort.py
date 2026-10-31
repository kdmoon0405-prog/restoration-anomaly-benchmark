"""Tiny fake full-cohort raw producer: receipts, resume, refusal, existing v0.6 consumers."""
import os
from types import SimpleNamespace

import numpy as np
import pytest

from sr_anomaly import pcb_full_cohort as full
from sr_anomaly import pcb_board_analysis as board
from sr_anomaly import bounded_bank as bank
from tests.test_pcb_reuse_inference import prepared, read  # noqa: F401  (fixture reuse)

m = full.reuse


@pytest.fixture
def cohort(prepared, monkeypatch):
    x = prepared
    monkeypatch.setattr(full.fit.runner, 'load_inventory', lambda *a: (x.parents, [], {}))
    monkeypatch.setattr(full, '_sources', m._sources)
    monkeypatch.setattr(full, '_runtime', lambda: dict(torch_version='fake', cuda_runtime=None, gpu_name=None))
    out, state = full.prepare(x.root, x.bank, x.data, x.tmp/'backbone.pth', x.tmp/'swinir.pth', run_id='full')
    assert state['status'] == 'PREFLIGHT_PASS' and (out/'bank/bank.npy').is_file()
    x.full = out
    return x


def run(x, **kw):
    return full.execute(x.full, x.root, x.bank, x.data, factory=x.factory, **kw)


def test_end_to_end_existing_reader_calibration_and_evaluation(cohort, tmp_path):
    x = cohort
    before = m._hashes(x.bank)
    state = run(x)
    assert state['status'] == 'COMPLETE' and state['units_complete'] == 9
    assert x.stats['bind'] == 1 and x.stats['predict'] == 9 and x.stats['closed'] == 1
    assert m._hashes(x.bank) == before
    raw, parents = board.load_raw_run(x.full)  # Existing v0.6 reader, unchanged.
    assert raw['provenance'] == read(x.bank/'bank/status.json')['provenance']
    assert raw['inference_provenance']['execution_family'] == full.EXECUTION_FAMILY
    spool = full.FullRGBSpool(x.full)
    for p in parents:
        if p.split == 'test':
            np.testing.assert_array_equal(full.fit.models.assemble_rgb(p.size_wh, spool.tiles(p, 'clean')), spool.reference(p))
    board.fit_calibration(x.full, tmp_path/'cal')
    board.apply_calibration(x.full, tmp_path/'cal', tmp_path/'norm')
    def mask(p):
        value = np.zeros(p.size_wh[::-1], np.uint8)
        if p.label: value[10:20, 10:20] = 1
        return value
    for variant in full.fit.models.VARIANTS:
        result = board.evaluate_variant(x.full, tmp_path/'cal', tmp_path/'norm', variant, mask, tmp_path/('ev-'+variant))
        assert result['status'] == 'COMPLETE'


def test_resume_skips_verified_units_and_discards_unreceipted_partial(cohort):
    x = cohort
    state = run(x, max_units=4)
    assert state['status'] == full.RESUMABLE and state['units_complete'] == 4
    first = {i: bank.file_sha256(full._receipt_path(x.full, i)) for i in range(4)}
    (x.full/'predictions/0004.npy').write_bytes(b'crash leftover')
    (x.full/'predictions/0005.npy.partial').write_bytes(b'crash leftover')
    state = run(x)
    assert state['status'] == 'COMPLETE' and x.stats['predict'] == 9 and x.stats['bind'] == 2
    assert first == {i: bank.file_sha256(full._receipt_path(x.full, i)) for i in range(4)}
    session = read(x.full/'sessions/001.json')
    assert session['skipped_verified_units'] == 4 and 'predictions/0004.npy' in session['discarded_unreceipted']
    board.load_raw_run(x.full)
    with pytest.raises(ValueError, match='COMPLETE'):
        run(x)


@pytest.mark.parametrize('change', ['source', 'payload', 'protocol', 'bank_copy', 'rgb'])
def test_resume_refused_on_identity_change(cohort, change):
    x = cohort
    run(x, max_units=2)
    if change == 'source': x.source.write_bytes(b'changed')
    elif change == 'payload': (x.full/'predictions/0000.npy').write_bytes(b'tampered')
    elif change == 'protocol':
        p = read(x.full/'PROTOCOL.json'); p['execution_family'] = 'other'; m.fit.memory.write_json(x.full/'PROTOCOL.json', p)
    elif change == 'bank_copy': (x.full/'bank/bank.npy').write_bytes(b'changed')
    else: (x.data/'cal').write_bytes(b'changed')
    with pytest.raises(ValueError):
        run(x)
    assert x.stats['predict'] == 2


def test_live_lock_refused_and_stop_request_is_resumable(cohort):
    x = cohort
    (x.full/'RUN.lock').write_text(str(os.getpid()))
    with pytest.raises(RuntimeError, match='locked'):
        run(x)
    (x.full/'RUN.lock').unlink()
    (x.full/full.STOP_FILE).write_text('pause')
    state = run(x)
    assert state['status'] == full.RESUMABLE and state['units_complete'] == 0
    (x.full/full.STOP_FILE).unlink()
    assert run(x)['status'] == 'COMPLETE'


def test_failure_mid_cohort_keeps_receipts_and_never_completes(cohort):
    x = cohort
    calls = dict(n=0)
    class Broken(x.Adapter):
        def predict(self, rgb):
            calls['n'] += 1
            if calls['n'] == 5: raise RuntimeError('injected')
            return super().predict(rgb)
    with pytest.raises(RuntimeError):
        full.execute(x.full, x.root, x.bank, x.data, factory=lambda *a: (Broken(), x.transform))
    state = read(x.full/'status.json')
    assert state['status'] == full.RESUMABLE and state['units_complete'] == 4 and x.stats['closed'] == 1
    with pytest.raises(ValueError):
        board.load_raw_run(x.full)
    assert run(x)['status'] == 'COMPLETE'


def test_preflight_never_reuses_run_id_and_requires_owned_directory(cohort):
    x = cohort
    with pytest.raises(FileExistsError):
        full.prepare(x.root, x.bank, x.data, x.tmp/'backbone.pth', x.tmp/'swinir.pth', run_id='full')
    with pytest.raises(ValueError):
        full.execute(x.out, x.root, x.bank, x.data, factory=x.factory)


def test_postprocess_per_board_uses_gt_only_in_evaluation(cohort, tmp_path):
    from scripts import run_pcb_full_postprocess as post
    import csv
    x = cohort
    run(x)
    board.fit_calibration(x.full, tmp_path/'cal')
    board.apply_calibration(x.full, tmp_path/'cal', tmp_path/'norm')
    class GT:
        gt_receipts = {}
        def evaluation_mask(self, p):
            assert p.split == 'test'
            value = np.zeros(p.size_wh[::-1], bool)
            if p.label: value[5:15, 5:15] = True
            self.gt_receipts[p.sample] = 'read'
            return value
    meta = post.per_board(x.full, tmp_path/'cal', tmp_path/'norm', 'swinir_x4', GT(), tmp_path/'pb')
    rows = list(csv.DictReader((tmp_path/'pb/per_board.csv').open(encoding='utf-8')))
    assert meta['rows'] == 2 and set(meta['gt_receipts']) == {'good', 'bad'}
    bad = next(r for r in rows if r['sample'] == 'bad')
    assert bad['defect_area_pixels'] == '100' and bad['region_count'] == '1' and bad['per_image_aupro'] != ''
    assert next(r for r in rows if r['sample'] == 'good')['per_image_aupro'] == ''
    with pytest.raises(FileExistsError):
        post.per_board(x.full, tmp_path/'cal', tmp_path/'norm', 'swinir_x4', GT(), tmp_path/'pb')
