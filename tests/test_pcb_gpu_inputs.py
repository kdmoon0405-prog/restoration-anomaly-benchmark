import hashlib
from pathlib import Path
import zipfile

import pytest

from scripts import setup_pcb_gpu_inputs as inputs


def fixture_bundle(tmp_path, *, bad_payload=False, extra=None):
    archive = tmp_path / "input.zip"
    payload = b"unchanged synthetic RGB placeholder"
    expected = {"pcb2/Data/Images/Normal/0001.JPG": hashlib.sha256(payload).hexdigest()}
    with zipfile.ZipFile(archive, "w") as bundle:
        for name in inputs.LEGAL:
            bundle.writestr(name, "synthetic legal fixture")
        bundle.writestr(next(iter(expected)), b"bad" if bad_payload else payload)
        if extra:
            bundle.writestr(extra, b"bad")
    return archive, expected, inputs.sha256(archive)


def test_frozen_inventory():
    expected = inputs.expected_files()
    assert len(expected) == 1202
    assert sum("/Images/" in name for name in expected) == 1101
    assert sum("/Masks/" in name for name in expected) == 100


def test_config_uses_frozen_checkpoints():
    import json
    from sr_anomaly.pcb_tiled_models import BACKBONE_SHA256, SWINIR_SHA256
    config = json.loads(inputs.CONFIG.read_text(encoding="utf-8"))
    assert config["backbone"]["sha256"] == BACKBONE_SHA256
    assert config["swinir"]["sha256"] == SWINIR_SHA256
    assert config["bundle"]["entries"] == len(inputs.expected_files()) + len(inputs.LEGAL)


def test_exact_install_and_safe_resume(tmp_path):
    archive, expected, digest = fixture_bundle(tmp_path)
    destination = tmp_path / "data"
    inputs.install_bundle(archive, destination, expected, digest)
    assert inputs.verify_existing(destination, expected, require_all=True) == []
    inputs.install_bundle(archive, destination, expected, digest)
    assert len(list(destination.rglob("*.JPG"))) == 1


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/drive", "a\\b", "a/../b", "./a", "a//b", "."])
def test_path_guards(tmp_path, name):
    with pytest.raises(ValueError):
        inputs.target_path(tmp_path, name)


@pytest.mark.parametrize("bad_payload,extra", [(True, None), (False, "../escape")])
def test_invalid_bundle_does_not_create_dataset(tmp_path, bad_payload, extra):
    archive, expected, digest = fixture_bundle(tmp_path, bad_payload=bad_payload, extra=extra)
    with pytest.raises(ValueError):
        inputs.install_bundle(archive, tmp_path / "data", expected, digest)
    assert not (tmp_path / "data").exists()


def test_existing_data_not_overwritten(tmp_path):
    archive, expected, digest = fixture_bundle(tmp_path)
    destination = tmp_path / "data"
    target = destination / next(iter(expected))
    target.parent.mkdir(parents=True)
    target.write_bytes(b"user data")
    with pytest.raises(ValueError, match="refusing overwrite"):
        inputs.install_bundle(archive, destination, expected, digest)
    assert target.read_bytes() == b"user data"


def test_archive_and_download_hash_guards(tmp_path):
    archive, expected, digest = fixture_bundle(tmp_path)
    with pytest.raises(ValueError, match="Bundle SHA256"):
        inputs.install_bundle(archive, tmp_path / "data", expected, "0" * 64)
    assert inputs.download("https://unused.invalid", archive, digest) == archive
    with pytest.raises(ValueError, match="refusing overwrite"):
        inputs.download("https://unused.invalid", archive, "0" * 64)


def test_download_is_verified_and_failed_payload_is_not_published(tmp_path, monkeypatch):
    import io
    monkeypatch.setattr(inputs.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"test"))
    target = tmp_path / "weights.pth"
    with pytest.raises(ValueError, match="Downloaded SHA256"):
        inputs.download("https://fixture.invalid", target, "0" * 64)
    assert not target.exists()
    inputs.download("https://fixture.invalid", target, hashlib.sha256(b"test").hexdigest())
    assert target.read_bytes() == b"test"
