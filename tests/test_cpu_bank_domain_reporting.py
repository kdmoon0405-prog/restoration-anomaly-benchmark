from pathlib import Path
import importlib.util
import shutil

import pytest

from sr_anomaly.analysis_io import csv_rows, digest, read_json, write_csv, write_json
from _bank_domain_fixtures import make_run

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cpu_domain_reporting", ROOT / "scripts/analyze_cpu_bank_domain_study.py")
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)


def fixture(root):
    core = make_run(root / "core-results/synthetic_category-seed11")
    write_json(root / "status.json", dict(status="CPU_BANK_DOMAIN_COMPLETE"))
    write_json(root / "PROTOCOL.json", dict(config=dict(categories=["synthetic_category"], seeds=[11])))
    for query in ("bicubic_x4", "swinir_x4"):
        out = root / "runs" / core.name / "bicubic_matched" / query
        out.mkdir(parents=True)
        summary = [dict(row, bank_domain="bicubic_matched") for row in csv_rows(core / "summary.csv")
                   if row["bank_domain"] == "clean" and row["query_domain"] == query]
        images = [dict(row, bank_domain="bicubic_matched") for row in csv_rows(core / "per_image.csv")
                  if row["bank_domain"] == "clean" and row["query_domain"] == query]
        write_csv(out / "summary.csv", summary)
        write_csv(out / "per_image.csv", images)
        write_json(out / "status.json", dict(status="EVALUATED_COMPLETE",
            artifact_sha256={name: digest(out / name) for name in ("summary.csv", "per_image.csv")}))
    return root


def test_complete_three_bank_matrix_and_image_units(tmp_path):
    source = fixture(tmp_path / "source")
    result = reporting.analyze(source, tmp_path / "analysis", allow_synthetic=True, source_root=None)
    assert result["matrix_rows"] == 6 and result["newly_computed_condition_rows"] == 4
    assert result["reused_clean_condition_rows"] == 2 and result["unique_query_quality_rows"] == 6
    rows = csv_rows(tmp_path / "analysis/seed_summary.csv")
    assert all(int(row["unique_anomaly_images"]) == 2 for row in rows)


def test_missing_case_rejected(tmp_path):
    source = fixture(tmp_path / "source")
    write_json(source / "PROTOCOL.json", dict(config=dict(categories=["synthetic_category"], seeds=[11, 23])))
    with pytest.raises(ValueError, match="Missing"):
        reporting.analyze(source, tmp_path / "analysis", allow_synthetic=True, source_root=None)


def test_extra_control_normal_aupro_rejected(tmp_path):
    source = fixture(tmp_path / "source")
    out = source / "runs/synthetic_category-seed11/bicubic_matched/bicubic_x4"
    rows = csv_rows(out / "per_image.csv")
    next(row for row in rows if row["label"] == "0")["per_image_aupro"] = "0.25"
    write_csv(out / "per_image.csv", rows)
    state = read_json(out / "status.json")
    state["artifact_sha256"]["per_image.csv"] = digest(out / "per_image.csv")
    write_json(out / "status.json", state)
    with pytest.raises(ValueError, match="Normal"):
        reporting.analyze(source, tmp_path / "analysis", allow_synthetic=True, source_root=None)


def mixed_fixture(source, root):
    root.mkdir(parents=True)
    write_json(root / "status.json", dict(status="CPU_MIXED_BANK_COMPLETE"))
    write_json(root / "PROTOCOL.json", dict(ratio=0.5, source_execution_sha256=digest(source / "status.json")))
    for query in ("bicubic_x4", "swinir_x4"):
        old = source / "runs/synthetic_category-seed11/bicubic_matched" / query
        out = root / "runs/synthetic_category-seed11/balanced_mixed" / query
        shutil.copytree(old, out)
        for name in ("summary.csv", "per_image.csv"):
            rows = [dict(row, bank_domain="balanced_mixed") for row in csv_rows(out / name)]
            write_csv(out / name, rows)
        write_json(out / "status.json", dict(status="EVALUATED_COMPLETE",
            artifact_sha256={name: digest(out / name) for name in ("summary.csv", "per_image.csv")}))
    return root


def test_fixed_mixed_candidate_matrix_and_matched_comparisons(tmp_path):
    source = fixture(tmp_path / "source")
    mixed = mixed_fixture(source, tmp_path / "mixed")
    result = reporting.analyze(source, tmp_path / "analysis", mixed_execution=mixed,
                               allow_synthetic=True, source_root=None)
    assert result["matrix_rows"] == 8 and result["newly_computed_condition_rows"] == 6
    comparisons = csv_rows(tmp_path / "analysis/seed_summary.csv")
    capacity = [r for r in comparisons if r["axis"] == "bank_capacity"]
    assert len(capacity) == 2 and all(int(r["unique_anomaly_images"]) == 2 for r in capacity)


def test_mixed_source_binding_rejected(tmp_path):
    source = fixture(tmp_path / "source")
    mixed = mixed_fixture(source, tmp_path / "mixed")
    write_json(mixed / "PROTOCOL.json", dict(ratio=0.75, source_execution_sha256=digest(source / "status.json")))
    with pytest.raises(ValueError, match="source/ratio"):
        reporting.analyze(source, tmp_path / "analysis", mixed_execution=mixed,
                          allow_synthetic=True, source_root=None)


def test_public_numeric_export_has_no_duplicate_anchors_or_absolute_paths(tmp_path):
    source = fixture(tmp_path / "source")
    analysis = tmp_path / "analysis"
    reporting.analyze(source, analysis, allow_synthetic=True, source_root=None)
    bank = source / "runs/synthetic_category-seed11/bicubic_matched/bank"
    bank.mkdir()
    write_json(bank / "status.json", dict(status="BANK_COMPLETE", category="synthetic_category",
        seed=11, normal_fit_count=3))
    spec = importlib.util.spec_from_file_location("cpu_domain_export", ROOT / "scripts/export_cpu_bank_domain_results.py")
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    result = exporter.export(analysis, source, tmp_path / "public")
    assert result["matrix_rows"] == 6 and result["new_conditions"] == 4
    rows = csv_rows(tmp_path / "public/new_conditions_for_master.csv")
    assert all(r["bank_domain"] != "clean" and r["train_count"] == "3" for r in rows)
    assert all("/" not in r["source_run"] and "\\" not in r["source_run"] for r in rows)
    for name, sha in result["tables"].items():
        assert digest(tmp_path / "public" / name) == sha
        assert b"\r\n" not in (tmp_path / "public" / name).read_bytes()
