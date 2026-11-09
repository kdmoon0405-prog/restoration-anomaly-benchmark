import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest


def fixture(tmp_path, monkeypatch, bad_path=False):
    script = Path(__file__).resolve().parents[1] / "scripts/receive_category_transfer.py"
    spec = importlib.util.spec_from_file_location("category_receiver", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.shutil, "disk_usage", lambda path: SimpleNamespace(free=10 * 1024**3))
    body = b"synthetic license"
    name = "../escape" if bad_path else "license.txt"
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=["path", "bytes", "sha256"])
    writer.writeheader()
    writer.writerow(dict(path=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
    manifest = text.getvalue().encode()
    archive = tmp_path / "transfer.zip"
    with zipfile.ZipFile(archive, "x") as z:
        z.writestr(name, body)
        z.writestr("FILE_MANIFEST.csv", manifest)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(dict(dataset="MVTec AD", categories=["hazelnut", "screw"],
        archive_sha256_role="private_team_category_repack", archive_sha256=module.sha(archive),
        input_inventory_sha256=hashlib.sha256(manifest).hexdigest(), license_file="license.txt",
        license_sha256=hashlib.sha256(body).hexdigest())), encoding="utf-8")
    return module, archive, receipt


def test_transfer_and_no_overwrite(tmp_path, monkeypatch):
    module, archive, receipt = fixture(tmp_path, monkeypatch)
    out = tmp_path / "received"
    assert module.receive(archive, receipt, out)["status"] == "TRANSFER_VERIFIED"
    assert (out / "dataset_provenance.json").is_file()
    with pytest.raises(FileExistsError):
        module.receive(archive, receipt, out)


def test_bad_archive_and_traversal(tmp_path, monkeypatch):
    module, archive, receipt = fixture(tmp_path, monkeypatch, True)
    with pytest.raises(ValueError, match="Unsafe"):
        module.receive(archive, receipt, tmp_path / "received")
    archive.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="receipt/archive"):
        module.receive(archive, receipt, tmp_path / "other")


def test_disk_guard_creates_no_receipt(tmp_path, monkeypatch):
    module, archive, receipt = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(module.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    out = tmp_path / "blocked"
    with pytest.raises(OSError, match="disk"):
        module.receive(archive, receipt, out)
    assert not out.exists()
