import hashlib
import json

import numpy as np
import pytest

from sr_anomaly.noise_repeatability import across_noise_seeds, contrast_pair, load_run, public_protocol, source_byte_identity
from sr_anomaly.research_reporting import _normalize


def test_source_checkout_binding():
    body = b'print(1)\n'
    sha = hashlib.sha256(body).hexdigest()
    assert source_byte_identity(body, sha) == 'git_blob'
    crlf_sha = hashlib.sha256(body.replace(b'\n', b'\r\n')).hexdigest()
    assert source_byte_identity(body, crlf_sha) == 'git_CRLF_checkout'
    with pytest.raises(ValueError, match='content differs'):
        source_byte_identity(b'print(2)\n', sha)


@pytest.mark.parametrize('old_path', [r'C:\Users\someone\project\bank', '/home/person/project/bank'])
def test_public_copy_changes_only_path(old_path):
    protocol = dict(category='hazelnut', v1_bank_dir=old_path, metrics={'au_pro': .812345678901}, seed=11)
    output, changes = public_protocol(protocol)
    assert changes == ['v1_bank_dir']
    assert output['v1_bank_dir'] == 'outputs/realistic-degradation/hazelnut-v1/bank'
    assert protocol['v1_bank_dir'] == old_path
    assert output['metrics'] == protocol['metrics']
    assert output['seed'] == protocol['seed']


def test_noise_repeats_resample_unique_images():
    names = ['a', 'b', 'c']
    left = np.array([-.2, 0, .2])
    result = across_noise_seeds([(names, left), (names, left)], repeats=100, seed=11)
    assert result['n_unique_images'] == 3
    assert result['mean_delta'] == pytest.approx(0)
    assert result == across_noise_seeds([(names, left), (names, left)], repeats=100, seed=11)
    with pytest.raises(ValueError, match='ordered image'):
        across_noise_seeds([(names, left), (list(reversed(names)), left)], repeats=100)


def test_pairs_use_only_anomalies_and_same_lr():
    def row(label, value, lr='same'):
        return dict(split='test', label=str(label), per_image_aupro=value, degraded_lr_sha256=lr)
    a = {'normal': row(0, ''), 'defect': row(1, '.8')}
    b = {'normal': row(0, ''), 'defect': row(1, '.7')}
    names, delta = contrast_pair(a, b)
    assert names == ['defect'] and delta[0] == pytest.approx(.1)
    b['defect']['degraded_lr_sha256'] = 'different'
    with pytest.raises(ValueError, match='Paired input'):
        contrast_pair(a, b)


def test_master_keeps_old_entry_identity_and_noise_seed():
    raw = dict(study_family='test', protocol_id='p', dataset='d', category='c', seed='11', variant='v')
    source = dict(study_family_column='study_family', protocol_id_column='protocol_id',
                  category_column='category', evidence_kind='synthetic_fixture')
    result = _normalize(raw, source, 'synthetic.csv', 'abc')
    expected = hashlib.sha256(json.dumps(['test', 'p', 'd', 'c', 11, '', '', 'v'], ensure_ascii=False).encode()).hexdigest()[:16]
    assert result['entry_id'] == expected and result['noise_seed'] == ''
    new = _normalize(dict(raw, noise_seed='23'), source, 'synthetic.csv', 'abc')
    assert new['noise_seed'] == 23 and new['seed'] == 11
    assert new['entry_id'] == result['entry_id']


@pytest.mark.parametrize('source_commit', ['abc', '--output=escape'])
def test_reject_non_commit_source_before_git(tmp_path, source_commit):
    protocol = dict(family='realistic_lr_noise_v2', category='hazelnut', noise_seed=23,
        split_seed=11, bank_refit=False, conditions=['noise_s5', 'noise_s15'],
        restorers=['bicubic_x4', 'swinir_x4', 'realesrnet_x4plus', 'realesrgan_x4plus'], quantile=.99)
    (tmp_path / 'PROTOCOL.json').write_text(json.dumps(protocol), encoding='utf-8')
    (tmp_path / 'sessions').mkdir()
    (tmp_path / 'sessions/000.json').write_text(json.dumps(dict(units_complete=8,
        units_planned=8, source_commit=source_commit)), encoding='utf-8')
    with pytest.raises(ValueError, match='exact producer source commit'):
        load_run(tmp_path, tmp_path, tmp_path)
