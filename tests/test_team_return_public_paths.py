"""Public-path view in prepare_team_return.py: relative copy + original SHA, refusal elsewhere."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def module():
    script = Path(__file__).resolve().parents[1] / 'scripts/prepare_team_return.py'
    spec = importlib.util.spec_from_file_location('team_return_paths', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _protocol(root, ensure_ascii):
    bank = str(root / 'outputs' / '연구' / 'bank')  # non-ASCII like the real Hazelnut path
    return json.dumps({'a': 1, 'v1_bank_dir': bank, 'nested': [{'x': 'outputs/rel.csv'}], 'b': 0.1},
                      indent=1, ensure_ascii=ensure_ascii).encode('utf-8'), bank


@pytest.mark.parametrize('ensure_ascii', [True, False])
def test_json_absolute_path_becomes_relative_with_original_sha(module, tmp_path, ensure_ascii):
    source, repo, local = tmp_path / 'source', tmp_path / 'repo', tmp_path / 'local'
    source.mkdir()
    body, bank = _protocol(local, ensure_ascii)
    (source / 'PROTOCOL.json').write_bytes(body)
    out = module.prepare(source, repo, 'juhyung', 'run-1', ['PROTOCOL.json'], [local])
    public = (out / 'PROTOCOL.json').read_bytes()
    assert (source / 'PROTOCOL.json').read_bytes() == body  # original untouched
    parsed = json.loads(public)
    assert parsed['v1_bank_dir'] == 'outputs/연구/bank'
    assert {k: v for k, v in parsed.items() if k != 'v1_bank_dir'} == {
        k: v for k, v in json.loads(body).items() if k != 'v1_bank_dir'}
    # Only the path literal changed: everything before it is byte-identical.
    prefix = body.split(b'"v1_bank_dir"')[0]
    assert public.startswith(prefix)
    entry = json.loads((out / 'RECEIPT.json').read_text('utf-8'))['files'][0]
    assert entry['sha256'] == hashlib.sha256(public).hexdigest()
    assert entry['original_sha256'] == hashlib.sha256(body).hexdigest()
    assert entry['public_path_view'] is True
    assert entry['changed_fields'] == [{'field': '/v1_bank_dir', 'public_value': 'outputs/연구/bank'}]
    assert bank not in public.decode('utf-8')


def test_argv_list_paths_including_the_root_itself(module, tmp_path):
    source, local = tmp_path / 'source', tmp_path / 'local'
    source.mkdir()
    body = json.dumps({'argv': ['--data-root', str(local), '--output', str(local / 'outputs' / 'run-a')]}).encode()
    (source / 's.json').write_bytes(body)
    out = module.prepare(source, tmp_path / 'repo', 'juhyung', 'run-1', ['s.json'], [local])
    assert json.loads((out / 's.json').read_bytes())['argv'] == ['--data-root', '.', '--output', 'outputs/run-a']
    fields = json.loads((out / 'RECEIPT.json').read_text('utf-8'))['files'][0]['changed_fields']
    assert [f['field'] for f in fields] == ['/argv/1', '/argv/3']


def test_json_without_paths_is_copied_unchanged_without_extra_fields(module, tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    body = b'{"x": "outputs/a.csv", "url": "https://example.org/a"}\n'
    (source / 'a.json').write_bytes(body)
    out = module.prepare(source, tmp_path / 'repo', 'juhyung', 'run-1', ['a.json'], [tmp_path])
    assert (out / 'a.json').read_bytes() == body
    assert 'original_sha256' not in json.loads((out / 'RECEIPT.json').read_text('utf-8'))['files'][0]


@pytest.mark.parametrize('roots', [[], ['elsewhere']])
def test_json_absolute_path_outside_local_root_is_refused(module, tmp_path, roots):
    source = tmp_path / 'source'
    source.mkdir()
    body, _ = _protocol(tmp_path / 'local', True)
    (source / 'PROTOCOL.json').write_bytes(body)
    with pytest.raises(ValueError, match='Absolute local path'):
        module.prepare(source, tmp_path / 'repo', 'juhyung', 'run-1', ['PROTOCOL.json'],
                       [tmp_path / r for r in roots])
    assert not (tmp_path / 'repo/handoff/returns/juhyung/run-1').exists()


@pytest.mark.parametrize('text', ['see C:\\Users\\x\\out.csv\n', 'path,C:/data/a.png\n', 'at /home/u/run\n',
                                  'x /Users/u/run\n'])
def test_text_with_absolute_path_is_refused(module, tmp_path, text):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'RUN_RECORD.md').write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match='Absolute local path'):
        module.prepare(source, tmp_path / 'repo', 'juhyung', 'run-1', ['RUN_RECORD.md'], [tmp_path])


def test_relative_and_url_text_is_accepted(module, tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    body = 'outputs/realistic-noise-v2/screw-noise23 https://github.com/x/y ratio 1:2 home/user\n'
    (source / 'RUN_RECORD.md').write_text(body, encoding='utf-8')
    out = module.prepare(source, tmp_path / 'repo', 'juhyung', 'run-1', ['RUN_RECORD.md'], [])
    assert (out / 'RUN_RECORD.md').read_text('utf-8') == body
