from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.aggregate_category_results import extract_category, write_report
from scripts.compare_cpu_cuda_runs import compare_runs, write_outputs as write_parity_outputs


METRIC_FIELDS = (
    "mean_psnr", "mean_ssim", "image_threshold", "pixel_threshold",
    "image_auroc", "image_f1", "pixel_auroc", "au_pro", "pixel_f1",
)


def _fusion_run(path: Path, device: str, offset: float = 0.0) -> None:
    path.mkdir()
    methods = ("clean_reference", "degraded_only", "restored_only")
    spec = {
        "implementation": "patchcore", "source_commit": "abc", "category": "hazelnut", "seed": 11,
        "train_paths": ["train/a.png"], "calibration_paths": ["train/b.png"],
    }
    method_result = {}
    summary_rows = []
    labels = np.array([0, 1], dtype=np.uint8)
    masks = np.array([[[0, 0], [0, 0]], [[1, 0], [0, 0]]], dtype=np.uint8)
    for method in methods:
        values = {
            "mean_psnr": None if method == "clean_reference" else 30.0 + offset,
            "mean_ssim": None if method == "clean_reference" else 0.9 + offset,
            "image_threshold": 0.4 + offset, "pixel_threshold": 0.5 + offset,
            "image_auroc": 0.9 + offset, "image_f1": 0.8 + offset,
            "pixel_auroc": 0.85 + offset, "au_pro": 0.75 + offset, "pixel_f1": 0.7 + offset,
        }
        method_result[method] = {
            "evaluation": {
                "classification": {key: values[key] for key in ("image_auroc", "image_f1", "image_threshold")},
                "localization": {key: values[key] for key in ("pixel_auroc", "au_pro", "pixel_f1", "pixel_threshold")},
            },
            "mean_psnr": values["mean_psnr"], "mean_ssim": values["mean_ssim"],
        }
        summary_rows.append({"method": method, **values})
        maps = np.arange(8, dtype=np.float32).reshape(2, 2, 2) + offset
        np.savez_compressed(path / f"{method}_predictions.npz", labels=labels,
                            scores=np.array([0.1, 0.9]) + offset, masks=masks, maps=maps)
    result = {
        "model_spec": spec, "requested_device": device, "actual_device": device,
        "cuda_available": device == "cuda", "gpu_name": "Synthetic GPU" if device == "cuda" else None,
        "fit_seconds_this_run": 8.0 if device == "cpu" else 2.0,
        "calibration_seconds": 4.0 if device == "cpu" else 2.0,
        "test_seconds": 6.0 if device == "cpu" else 3.0,
        "restoration": {"name": "swinir", "checkpoint_sha256": "sha"},
        "test_paths": ["test/good.png", "test/bad.png"], "methods": method_result,
    }
    (path / "results.json").write_text(json.dumps(result), encoding="utf-8")
    (path / "split.json").write_text(json.dumps({"seed": 11, "train": [0], "calibration": [1]}), encoding="utf-8")
    with (path / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("method", *METRIC_FIELDS))
        writer.writeheader()
        writer.writerows(summary_rows)


def test_parity_allows_device_fields_and_reports_tolerance_and_speedup(tmp_path: Path) -> None:
    cpu, cuda = tmp_path / "cpu", tmp_path / "cuda"
    _fusion_run(cpu, "cpu")
    _fusion_run(cuda, "cuda", offset=5e-6)
    report, rows = compare_runs(cpu, cuda)
    assert report["overall_pass"]
    assert report["device_metadata"]["cpu"]["actual_device"] == "cpu"
    assert report["device_metadata"]["cuda"]["actual_device"] == "cuda"
    assert report["prediction_differences"]["degraded_only"]["maps"]["max_abs_diff"] == pytest.approx(5e-6, abs=1e-8)
    assert report["runtime_comparison"]["fit_seconds_this_run"]["speedup_cpu_over_cuda"] == 4.0
    output = tmp_path / "parity"
    write_parity_outputs(report, rows, output)
    assert {path.name for path in output.iterdir()} == {
        "cpu_cuda_parity.json", "cpu_cuda_parity.csv", "CPU_CUDA_NOTE.md",
    }


def test_parity_rejects_exact_metadata_mismatch(tmp_path: Path) -> None:
    cpu, cuda = tmp_path / "cpu", tmp_path / "cuda"
    _fusion_run(cpu, "cpu")
    _fusion_run(cuda, "cuda")
    result_path = cuda / "results.json"
    result = json.loads(result_path.read_text())
    result["model_spec"]["seed"] = 12
    result_path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="model_spec.*seed"):
        compare_runs(cpu, cuda)


@pytest.mark.parametrize("array_name", ["labels", "masks"])
def test_parity_rejects_label_and_mask_mismatches(tmp_path: Path, array_name: str) -> None:
    cpu, cuda = tmp_path / "cpu", tmp_path / "cuda"
    _fusion_run(cpu, "cpu")
    _fusion_run(cuda, "cuda")
    prediction_path = cuda / "degraded_only_predictions.npz"
    with np.load(prediction_path) as data:
        arrays = {key: data[key] for key in data.files}
    arrays[array_name] = arrays[array_name].copy()
    arrays[array_name].flat[0] = 1
    np.savez_compressed(prediction_path, **arrays)
    with pytest.raises(ValueError, match=f"{array_name} mismatch"):
        compare_runs(cpu, cuda)


def test_parity_marks_out_of_tolerance_numeric_difference(tmp_path: Path) -> None:
    cpu, cuda = tmp_path / "cpu", tmp_path / "cuda"
    _fusion_run(cpu, "cpu")
    _fusion_run(cuda, "cuda", offset=1e-3)
    report, _ = compare_runs(cpu, cuda)
    assert not report["numeric_tolerance_pass"]
    assert not report["prediction_tolerance_pass"]
    assert not report["overall_pass"]


def test_reporting_uses_stored_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "legacy"
    run.mkdir()
    result = {
        "model_spec": {"category": "hazelnut"},
        "comparison_vs_bicubic_x4": {
            "delta_psnr": 2.0, "delta_ssim": 0.02, "delta_image_auroc": 0.01,
            "delta_pixel_auroc": 0.03, "delta_au_pro": 0.04,
        },
    }
    (run / "results.json").write_text(json.dumps(result))
    fields = ("variant", "train_count", "test_count", "mean_psnr", "mean_ssim",
              "image_auroc", "pixel_auroc", "au_pro")
    with (run / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"variant": "bicubic_x4", "train_count": 10, "test_count": 5, "mean_psnr": 30,
             "mean_ssim": 0.9, "image_auroc": 0.8, "pixel_auroc": 0.7, "au_pro": 0.6},
            {"variant": "swinir_x4", "train_count": 10, "test_count": 5, "mean_psnr": 32,
             "mean_ssim": 0.92, "image_auroc": 0.81, "pixel_auroc": 0.73, "au_pro": 0.64},
        ])
    cross_path = tmp_path / "cross.json"
    cross_path.write_text(json.dumps({
        "category": "hazelnut", "localization_regression_count": 3, "localization_regression_rate": 0.3,
        "suppression_count": 1, "suppression_rate": 0.1,
        "geometry_candidate_count": 2, "geometry_candidate_rate": 0.2,
    }))
    row = extract_category(run, cross_path)
    assert row["delta_au_pro"] == 0.04
    assert row["suppression_count"] == 1
    output = tmp_path / "report"
    write_report([row], output)
    assert "hazelnut" in (output / "category_summary.md").read_text()
    assert list(csv.DictReader((output / "category_summary.csv").open()))[0]["swinir_psnr"] == "32.0"
