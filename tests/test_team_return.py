import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def module():
    script = Path(__file__).resolve().parents[1] / 'scripts/prepare_team_return.py'
    spec = importlib.util.spec_from_file_location('team_return', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_text_receipt_and_no_overwrite(module, tmp_path):
    source, repo = tmp_path / 'source', tmp_path / 'repo'
    source.mkdir()
    body = b'sample,score\r\na,0.1\r\n'
    (source / 'summary.csv').write_bytes(body)
    output = module.prepare(source, repo, 'juhyung', 'run-1', ['summary.csv'])
    assert (output / 'summary.csv').read_bytes() == body
    receipt = json.loads((output / 'RECEIPT.json').read_text('utf-8'))
    assert receipt['files'][0]['sha256'] == hashlib.sha256(body).hexdigest()
    assert receipt['review_status'] == 'NOT_REVIEWED'
    assert receipt['array_contents_verified'] is False
    with pytest.raises(FileExistsError):
        module.prepare(source, repo, 'juhyung', 'run-1', ['summary.csv'])


@pytest.mark.parametrize('name', [
    '../escape.csv', '/absolute.csv', 'C:/other.csv', 'sub\\file.csv',
    'map.npy', 'image.png', '.env', 'notes/RESEARCH_EVOLUTION_LOCAL.md',
    'RECEIPT.json', 'missing.csv',
])
def test_reject_unsafe_or_private_files(module, tmp_path, name):
    with pytest.raises(ValueError):
        module.prepare(tmp_path / 'source', tmp_path / 'repo', 'jihyuk', 'run-1', [name])
    assert not (tmp_path / 'repo/handoff/returns/jihyuk/run-1').exists()


def test_duplicate_binary_and_size_guards(module, tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    artifact = source / 'result.csv'
    artifact.write_text('sample,score\na,1\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate'):
        module.prepare(source, tmp_path / 'repo', 'jihyuk', 'run-1', ['result.csv', 'result.csv'])
    artifact.write_bytes(b'\x00binary')
    with pytest.raises(ValueError, match='Binary'):
        module.prepare(source, tmp_path / 'repo', 'jihyuk', 'run-1', ['result.csv'])
    monkeypatch.setattr(module, 'MAX_FILE_BYTES', 2)
    with pytest.raises(ValueError, match='limit'):
        module.prepare(source, tmp_path / 'repo', 'jihyuk', 'run-1', ['result.csv'])


def test_source_output_overlap(module, tmp_path):
    with pytest.raises(ValueError, match='separate'):
        module.prepare(tmp_path, tmp_path, 'jihyuk', 'run-1', ['result.csv'])


def test_failed_write_does_not_publish_partial_return(module, tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'summary.csv').write_text('synthetic', encoding='utf-8')
    def failed_write(*args, **kwargs):
        raise OSError('injected write failure')
    monkeypatch.setattr(Path, 'write_bytes', failed_write)
    with pytest.raises(OSError, match='injected'):
        module.prepare(source, tmp_path / 'repo', 'jihyuk', 'run-1', ['summary.csv'])
    assert not (tmp_path / 'repo/handoff/returns/jihyuk/run-1').exists()
