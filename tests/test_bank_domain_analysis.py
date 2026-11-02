import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest

from sr_anomaly.analysis_io import csv_rows, digest, read_json, write_csv, write_json
from sr_anomaly.analysis_statistics import paired_bootstrap_mean_delta
from sr_anomaly.bank_domain_analysis import analyze_runs
from _bank_domain_fixtures import make_run, refresh

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def small(tmp_path):
    run = make_run(tmp_path / "run")
    config = tmp_path / "analysis.json"
    write_json(config, dict(bootstrap_repeats=64, bootstrap_seed=11))
    return run, config


def analyze(small, out, **kwargs):
    run, config = small
    return analyze_runs([run], out, config=config, allow_synthetic=True, **kwargs)


def test_complete_2x2_stored_metric_and_paired_estimands(small, tmp_path):
    run, _ = small
    before = {p.name: digest(p) for p in run.iterdir()}
    report = analyze(small, tmp_path / "out")
    effects = csv_rows(tmp_path / "out/bank_effects.csv")
    row = next(r for r in effects if "swinir_x4_minus" in r["contrast"])
    assert float(row["delta_pooled_aupro"]) == pytest.approx(0.03)
    assert float(row["mean_delta_per_image_aupro"]) == pytest.approx(0.035)
    assert row["geometry_candidate_count"] == "1" and row["suppression_count"] == "0"
    assert row["paired_anomaly_images"] == "2"
    assert row["pooled_aupro_ci_computed"] == "False"
    assert len(csv_rows(tmp_path / "out/bank_domain_summary.csv")) == 4
    quality = csv_rows(tmp_path / "out/quality_by_query.csv")
    assert len(quality) == 6 and all("bank_domain" not in r for r in quality)
    assert report["raw_prediction_arrays_opened"] is False
    assert {p.name: digest(p) for p in run.iterdir()} == before
    assert not list((tmp_path / "out").glob("*.png"))


def test_existing_bootstrap_two_point_bounds():
    result = paired_bootstrap_mean_delta(np.array([-0.02, 0.05]), 2000, np.random.default_rng(11))
    assert result["estimate"] == pytest.approx(0.015)
    assert result["ci95"] == [-0.02, 0.05] and result["n"] == 2


def test_identical_copy_deduplicated_but_conflict_rejected(small, tmp_path):
    run, config = small
    copy = tmp_path / "copy"
    shutil.copytree(run, copy)
    report = analyze_runs([run, copy], tmp_path / "out", config=config, allow_synthetic=True)
    assert report["complete_unique_runs"] == 1 and len(report["duplicate_runs"]) == 1
    rows = csv_rows(copy / "summary.csv")
    rows[0]["pooled_aupro"] = "0.1"
    write_csv(copy / "summary.csv", rows)
    refresh(copy)
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        analyze_runs([run, copy], tmp_path / "bad", config=config, allow_synthetic=True)


def test_seed_replicates_are_separate_and_bootstrap_input_order_stable(tmp_path):
    a, b, c = [make_run(tmp_path / str(s), seed=s) for s in (11, 23, 37)]
    report = analyze_runs([c, a, b], tmp_path / "out", allow_synthetic=True)
    assert report["complete_unique_runs"] == 3
    rows = csv_rows(tmp_path / "out/seed_summary.csv")
    assert len(rows) == 4
    assert all(r["seed_count"] == "3" and r["seeds"] == "11;23;37" for r in rows)
    assert all(r["cross_seed_ci_computed"] == "False" for r in rows)
    per_image = csv_rows(tmp_path / "out/bank_effects.csv")
    assert all(r["paired_anomaly_images"] == "2" for r in per_image)
    analyze_runs([b, c, a], tmp_path / "out2", allow_synthetic=True)
    assert (tmp_path / "out/bank_effects.csv").read_bytes() == (tmp_path / "out2/bank_effects.csv").read_bytes()


def test_protocol_families_do_not_merge(tmp_path):
    a = make_run(tmp_path / "a", geometry="geometry_a")
    b = make_run(tmp_path / "b", geometry="geometry_b")
    report = analyze_runs([a, b], tmp_path / "out", allow_synthetic=True)
    assert report["complete_unique_runs"] == 2
    rows = csv_rows(tmp_path / "out/bank_domain_summary.csv")
    assert len({r["protocol_sha256"] for r in rows}) == 2 and len(rows) == 8


@pytest.mark.parametrize("change", ["missing_cell", "normal_aupro", "quality", "identity", "nonfinite", "count"])
def test_invalid_tables_rejected(small, tmp_path, change):
    run, _ = small
    path = run / ("summary.csv" if change in ("missing_cell", "count") else "per_image.csv")
    rows = csv_rows(path)
    if change == "missing_cell":
        rows.pop()
    elif change == "normal_aupro":
        next(r for r in rows if r["label"] == "0")["per_image_aupro"] = "0.8"
    elif change == "quality":
        rows[0]["psnr"] = "22"
    elif change == "identity":
        rows[0]["sample"] = "test/cut/other.png"
    elif change == "nonfinite":
        next(r for r in rows if r["label"] == "1")["per_image_aupro"] = "nan"
    else:
        rows[0]["n_test"] = "4"
    write_csv(path, rows)
    refresh(run)
    with pytest.raises(ValueError):
        analyze(small, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("status", ["PARTIAL", "FAILED", "PREFLIGHT_PASS"])
def test_unfinished_not_in_metrics(small, tmp_path, status):
    run, _ = small
    write_json(run / "bank_domain_manifest.json", dict(schema_version=1,
        kind="bank_domain_study_results", status=status))
    report = analyze(small, tmp_path / "out")
    assert report["status"] == "NO_COMPLETE_INPUTS" and len(report["skipped_runs"]) == 1
    assert csv_rows(tmp_path / "out/bank_domain_summary.csv") == []


def test_opt_in_hash_output_and_path_guards(small, tmp_path):
    run, config = small
    with pytest.raises(ValueError, match="Synthetic"):
        analyze_runs([run], tmp_path / "no", config=config)
    with pytest.raises(ValueError, match="outside"):
        analyze(small, run / "bad")
    analyze(small, tmp_path / "out")
    with pytest.raises(FileExistsError):
        analyze(small, tmp_path / "out")
    with (run / "summary.csv").open("a") as stream:
        stream.write("changed")
    with pytest.raises(ValueError, match="hash"):
        analyze(small, tmp_path / "bad")


def test_source_binding_only_when_explicit(small, tmp_path):
    run, _ = small
    source = tmp_path / "source/src"
    source.mkdir(parents=True)
    (source / "fake.py").write_text("# synthetic source\n")
    provenance = read_json(run / "provenance.json")
    provenance["code_sha256"] = {"src/fake.py": digest(source / "fake.py")}
    write_json(run / "provenance.json", provenance)
    refresh(run)
    report = analyze(small, tmp_path / "out", source_root=source.parent)
    assert report["source_byte_binding_checked"]
    (source / "fake.py").write_text("# changed")
    with pytest.raises(ValueError, match="source mismatch"):
        analyze(small, tmp_path / "bad", source_root=source.parent)


def test_test_cohort_drift_across_seeds_rejected(tmp_path):
    a, b = make_run(tmp_path / "a"), make_run(tmp_path / "b", seed=23)
    provenance = read_json(b / "provenance.json")
    provenance["test_manifest_sha256"] = "9" * 64
    write_json(b / "provenance.json", provenance)
    refresh(b)
    with pytest.raises(ValueError, match="cohort changed"):
        analyze_runs([a, b], tmp_path / "out", allow_synthetic=True)


def test_infinite_psnr_is_preserved_not_nan(small, tmp_path):
    run, _ = small
    for name, field in (("per_image.csv", "psnr"), ("summary.csv", "mean_psnr")):
        rows = csv_rows(run / name)
        for row in rows:
            row[field] = "inf"
        write_csv(run / name, rows)
    refresh(run)
    analyze(small, tmp_path / "out")
    assert all(r["psnr"] == "inf" for r in csv_rows(tmp_path / "out/quality_by_query.csv"))
    assert all(r["delta_mean_psnr"] == "0.0" for r in csv_rows(tmp_path / "out/bank_effects.csv"))


def test_cli_synthetic_end_to_end_and_no_model_runtime(small, tmp_path):
    run, config = small
    command = [sys.executable, "scripts/analyze_bank_domain_study.py", "--run", str(run),
        "--config", str(config), "--output", str(tmp_path / "cli"), "--allow-synthetic"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["evidence_kinds"] == ["synthetic_fixture"]
    code = """import importlib.abc,sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('torch','faiss','torchvision','timm','anomalib'):
   raise RuntimeError('model runtime import forbidden')
sys.meta_path.insert(0,Block())
from sr_anomaly import bank_domain_analysis,artifact_receipts,mvtec_transfer,research_reporting
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("change", ["checkpoint", "vectors", "split", "unsafe_source", "selection_GT"])
def test_scientific_binding_and_protocol_separation(small, tmp_path, change):
    run, config = small
    if change == "checkpoint":
        other = tmp_path / "other"
        shutil.copytree(run, other)
        cfg = read_json(other / "config.json")
        cfg["protocol"]["checkpoints_sha256"]["swinir"] = "9" * 64
        write_json(other / "config.json", cfg)
        refresh(other)
        report = analyze_runs([run, other], tmp_path / "out", config=config, allow_synthetic=True)
        assert report["complete_unique_runs"] == 2
        assert len({r["protocol_sha256"] for r in csv_rows(tmp_path / "out/bank_effects.csv")}) == 2
        return
    provenance = read_json(run / "provenance.json")
    if change == "vectors":
        provenance["bank_vector_counts"]["clean"] += 1
    elif change == "split":
        del provenance["split_manifest_sha256"]
    elif change == "unsafe_source":
        provenance["code_sha256"] = {"../outside.py": "a" * 64}
    else:
        provenance["test_gt_used_for_selection"] = True
    write_json(run / "provenance.json", provenance)
    refresh(run)
    with pytest.raises(ValueError):
        analyze(small, tmp_path / "bad")
