from pathlib import Path

import pytest

from sr_anomaly.analysis_io import read_json, write_json
from sr_anomaly.cpu_restoration_control import _checkpoint
from sr_anomaly import cpu_restoration_control as control
from sr_anomaly.cpu_checkpoint_recovery import pixel_code_sha


def test_transient_lock_retries(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    write_json(path, dict(old=True))
    original = Path.replace
    calls = []

    def replace(source, target):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("simulated short Windows sharing lock")
        return original(source, target)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(control.time, "sleep", lambda value: None)
    _checkpoint(path, dict(complete=True))
    assert len(calls) == 3 and read_json(path) == dict(complete=True)


def test_persistent_lock_preserves_previous_state(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    write_json(path, dict(old=True))
    def locked(*args):
        raise PermissionError("persistent lock")
    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr(control.time, "sleep", lambda value: None)
    with pytest.raises(PermissionError):
        _checkpoint(path, dict(complete=True))
    assert read_json(path) == dict(old=True)


def test_pixel_ast_excludes_writer_only(tmp_path):
    original = tmp_path / "old.py"
    updated = tmp_path / "new.py"
    original.write_text("def _checkpoint():\n    return 0\n\ndef image():\n    return 4\n")
    updated.write_text("def _checkpoint():\n    return 1\n\ndef image():\n    return 4\n")
    assert pixel_code_sha(original) == pixel_code_sha(updated)
    updated.write_text("def _checkpoint():\n    return 1\n\ndef image():\n    return 5\n")
    assert pixel_code_sha(original) != pixel_code_sha(updated)


def test_explicit_failed_cache_migration(tmp_path):
    import ast
    from sr_anomaly.analysis_io import digest
    from sr_anomaly.cpu_checkpoint_recovery import migrate_writer
    tree = ast.parse(Path(control.__file__).read_text(encoding="utf-8"))
    writer = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_checkpoint")
    writer.body = [ast.Pass()]
    previous = tmp_path / "previous.py"
    previous.write_text(ast.unparse(tree), encoding="utf-8")
    cache = tmp_path / "cache"
    image = cache / "images/tiny/0.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"fixture RGB bytes, hash-only check")
    write_json(cache / "status.json", dict(status="FAILED", error="old lock",
        binding=dict(code_sha256=digest(previous)), completed={"tiny/0.png": dict(output_sha256=digest(image))}))
    proof = migrate_writer(cache, previous)
    state = read_json(cache / "status.json")
    assert proof["completed_rgb_verified"] == 1 and proof["prior_error"] == "old lock"
    assert state["binding"]["code_sha256"] == digest(Path(control.__file__))
    assert "error" not in state and (cache / "status-before-writer-migration.json").exists()
