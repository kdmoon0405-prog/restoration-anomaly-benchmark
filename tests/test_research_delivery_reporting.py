import hashlib
from pathlib import Path
import shutil
import zipfile

import pytest
from PIL import Image

from sr_anomaly.analysis_io import csv_rows, digest, read_json, write_csv, write_json
from sr_anomaly.artifact_receipts import review_archive
from sr_anomaly.bank_domain_analysis import analyze_runs
from sr_anomaly.fusion import split_train_calibration
from sr_anomaly.mvtec_transfer import prepare_transfer, verify_transfer
from sr_anomaly.research_reporting import build_master
from _bank_domain_fixtures import make_run


def tiny_data(root, category):
    for split, defect, count in (("train", "good", 5), ("test", "good", 1), ("test", "crack", 2)):
        folder = root / category / split / defect
        folder.mkdir(parents=True)
        for i in range(count):
            Image.new("RGB", (8, 6), (i, 30, 80)).save(folder / f"{i:03d}.png")
            if defect != "good":
                masks = root / category / "ground_truth" / defect
                masks.mkdir(parents=True, exist_ok=True)
                Image.new("L", (8, 6), 255).save(masks / f"{i:03d}_mask.png")
    (root / "license.txt").write_text("Attribution-NonCommercial-ShareAlike 4.0 International")
    (root / "readme.txt").write_text("Synthetic input notices for tests only")
    return root


def test_category_manifest_pack_verify_and_existing_split(tmp_path):
    root = tiny_data(tmp_path / "data", "tiny")
    report = prepare_transfer(root, tmp_path / "out", categories=["tiny"], seeds=[11, 23], pack=True)
    assert report["categories"][0]["test_anomaly"] == 2
    split = read_json(tmp_path / "out/splits/tiny-seed11.json")
    fit, calibration = split_train_calibration(5, 0.8, 11)
    assert split["train_indices"] == fit and split["calibration_indices"] == calibration
    assert not set(split["train_paths"]) & set(split["calibration_paths"])
    assert verify_transfer(tmp_path / "out/input_manifest.json", root)["files"] == 12
    with zipfile.ZipFile(tmp_path / "out/tiny-inputs.zip") as z:
        assert z.read("MVTecAD/tiny/train/good/000.png") == (root / "tiny/train/good/000.png").read_bytes()
        assert "MVTecAD/license.txt" in z.namelist()
    assert report["image_decode_performed"] is False
    (root / "tiny/train/good/000.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="modified"):
        verify_transfer(tmp_path / "out/input_manifest.json", root)


def test_partial_category_delivery_and_overwrite(tmp_path):
    root = tiny_data(tmp_path / "data", "first")
    tiny_data(root, "second")
    prepare_transfer(root, tmp_path / "out", categories=["first", "second"], seeds=[11])
    owned_fixture = (root / "second").resolve()
    assert owned_fixture.is_relative_to(tmp_path.resolve())
    shutil.rmtree(owned_fixture)  # This test owns this explicit tiny fixture.
    assert verify_transfer(tmp_path / "out/input_manifest.json", root, categories=["first"])["categories"] == ["first"]
    with pytest.raises(ValueError):
        verify_transfer(tmp_path / "out/input_manifest.json", root)
    with pytest.raises(FileExistsError):
        prepare_transfer(root, tmp_path / "out", categories=["first"], seeds=[11])


def make_zip(path, content=b"metadata", *, wrong=False, member="review.json"):
    sha = ("0" * 64) if wrong else hashlib.sha256(content).hexdigest()
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(member, content)
        z.writestr("SHA256SUMS", sha + "  " + member + "\n")
    return path


def test_receipt_cache_skips_zip_reinspection(tmp_path, monkeypatch):
    archive = make_zip(tmp_path / "return.zip")
    first = review_archive(archive, tmp_path / "cache")
    assert first["manifest_entries_verified"] == 1 and not first["cache_hit"]
    monkeypatch.setattr(zipfile, "ZipFile", lambda *a, **k: pytest.fail("ZIP reopened on cache hit"))
    second = review_archive(archive, tmp_path / "cache")
    assert second["cache_hit"] and second["raw_array_content_checked"] is False
    assert second["remote_execution_independently_observed"] is False


@pytest.mark.parametrize("mode", ["hash", "path", "budget"])
def test_bad_archive_rejected(tmp_path, mode):
    archive = make_zip(tmp_path / "return.zip", wrong=mode == "hash",
                       member="../escape.json" if mode == "path" else "review.json")
    with pytest.raises(ValueError):
        review_archive(archive, tmp_path / "cache", max_uncompressed_bytes=1 if mode == "budget" else 10000)
    assert not list((tmp_path / "cache").glob("*.json"))


def test_receipt_reports_arrays_as_supplied_not_decoded(tmp_path):
    archive = make_zip(tmp_path / "return.zip", content=b"not-an-array", member="bank.npy")
    result = review_archive(archive, tmp_path / "cache")
    assert result["supplied_array_files"] == ["bank.npy"]
    assert not result["raw_array_content_checked"]


def catalog(tmp_path, *, sources=None):
    table = tmp_path / "stored.csv"
    rows = [dict(family="historical_pil", protocol="pillow_x4", category="synthetic",
                 variant="swinir", pooled="0.812345678901", psnr="31.123456789012"),
            dict(family="endpoint_matlab", protocol="matlab_x4", category="synthetic",
                 variant="swinir", pooled="0.834567890123", psnr="31.987654321098")]
    write_csv(table, rows)
    source = dict(table="stored.csv", status="COMPLETE", study_family_column="family",
                  protocol_id_column="protocol", category_column="category",
                  evidence_kind="synthetic_fixture", column_map=dict(pooled_aupro="pooled"))
    config = tmp_path / "catalog.json"
    write_json(config, dict(schema_version=1, sources=sources if sources is not None else [source]))
    return config, source


def test_master_keeps_families_and_source_precision(tmp_path):
    config, source = catalog(tmp_path)
    report = build_master(config, tmp_path, tmp_path / "out", allow_synthetic=True)
    rows = csv_rows(tmp_path / "out/master_results.csv")
    assert report["protocol_groups"] == 2 and report["rows"] == 2
    assert {r["study_family"] for r in rows} == {"historical_pil", "endpoint_matlab"}
    assert float(rows[0]["pooled_aupro"]) == 0.834567890123
    assert all(r["source_sha256"] == digest(tmp_path / "stored.csv") for r in rows)
    assert "screw" not in {r["category"] for r in rows}
    claims = csv_rows(tmp_path / "out/claim_evidence_index.csv")
    assert all(r["raw_prediction_arrays_checked"] == "False" for r in claims)


def test_master_duplicate_partial_synthetic_and_output_guards(tmp_path):
    config, source = catalog(tmp_path)
    write_json(config, dict(schema_version=1, sources=[source, source,
        dict(table="absent.csv", status="FAILED")]))
    with pytest.raises(ValueError, match="Synthetic"):
        build_master(config, tmp_path, tmp_path / "bad")
    report = build_master(config, tmp_path, tmp_path / "out", allow_synthetic=True)
    assert report["rows"] == 2 and len(report["duplicates_removed"]) == 2 and len(report["skipped"]) == 1
    with pytest.raises(FileExistsError):
        build_master(config, tmp_path, tmp_path / "out", allow_synthetic=True)


def test_master_consumes_bound_bank_analysis(tmp_path):
    run = make_run(tmp_path / "run")
    analyzed = tmp_path / "analyzed"
    analyze_runs([run], analyzed, allow_synthetic=True)
    config = tmp_path / "catalog.json"
    write_json(config, dict(schema_version=1, sources=[]))
    report = build_master(config, tmp_path, tmp_path / "out",
        bank_analyses=[analyzed], allow_synthetic=True)
    assert report["rows"] == 4
    with (analyzed / "bank_domain_summary.csv").open("a") as f:
        f.write("changed")
    with pytest.raises(ValueError, match="changed"):
        build_master(config, tmp_path, tmp_path / "bad", bank_analyses=[analyzed], allow_synthetic=True)


def test_catalog_identity_and_partial_rows_do_not_create_fake_conditions(tmp_path):
    table = tmp_path / "stored.csv"
    write_csv(table, [dict(variant="bicubic", value=0.7, status="COMPLETE"),
                      dict(variant="swinir", value="", status="FAILED")])
    config = tmp_path / "catalog.json"
    write_json(config, dict(schema_version=1, sources=[dict(table="stored.csv", status="COMPLETE",
        identity=dict(study_family="pcb_native", protocol_id="native224", category="synthetic", dataset="synthetic"),
        evidence_kind="synthetic_fixture", column_map=dict(pooled_aupro="value"))]))
    report = build_master(config, tmp_path, tmp_path / "out", allow_synthetic=True)
    assert report["rows"] == 1 and len(report["skipped"]) == 1
    assert csv_rows(tmp_path / "out/master_results.csv")[0]["study_family"] == "pcb_native"
