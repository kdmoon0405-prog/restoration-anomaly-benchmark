"""Compare saved CPU and CUDA fusion smoke runs without rerunning inference."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np


DEVICE_FIELDS = ("requested_device", "actual_device", "cuda_available", "gpu_name")
METRICS = (
    "mean_psnr", "mean_ssim", "image_auroc", "pixel_auroc", "au_pro",
    "image_f1", "pixel_f1", "image_threshold", "pixel_threshold",
)
RUNTIMES = ("fit_seconds_this_run", "calibration_seconds", "test_seconds")
CSV_FIELDS = (
    "section", "source", "method", "metric", "cpu_value", "cuda_value",
    "absolute_difference", "relative_difference", "max_absolute_difference",
    "mean_absolute_difference", "tolerance_pass", "speedup_cpu_over_cuda",
)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Required artifact not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_summary(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required artifact not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "method" not in rows[0]:
        raise ValueError(f"Invalid summary.csv: {path}")
    if len({row["method"] for row in rows}) != len(rows):
        raise ValueError(f"Duplicate methods in summary.csv: {path}")
    return {row["method"]: row for row in rows}


def _number(value) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite numeric value: {value}")
    return number


def _numeric_row(source: str, method: str, metric: str, cpu, cuda, atol: float, rtol: float) -> dict:
    cpu_value, cuda_value = _number(cpu), _number(cuda)
    if cpu_value is None or cuda_value is None:
        passed = cpu_value is None and cuda_value is None
        absolute = relative = None
    else:
        absolute = abs(cpu_value - cuda_value)
        relative = 0.0 if absolute == 0 else (absolute / abs(cpu_value) if cpu_value != 0 else None)
        passed = math.isclose(cpu_value, cuda_value, abs_tol=atol, rel_tol=rtol)
    return {
        "section": "numeric", "source": source, "method": method, "metric": metric,
        "cpu_value": cpu_value, "cuda_value": cuda_value,
        "absolute_difference": absolute, "relative_difference": relative,
        "max_absolute_difference": None, "mean_absolute_difference": None,
        "tolerance_pass": passed, "speedup_cpu_over_cuda": None,
    }


def _result_metrics(result: dict, method: str) -> dict:
    item = result["methods"][method]
    classification = item["evaluation"]["classification"]
    localization = item["evaluation"]["localization"]
    return {
        "mean_psnr": item.get("mean_psnr"),
        "mean_ssim": item.get("mean_ssim"),
        "image_auroc": classification.get("image_auroc"),
        "pixel_auroc": localization.get("pixel_auroc"),
        "au_pro": localization.get("au_pro"),
        "image_f1": classification.get("image_f1"),
        "pixel_f1": localization.get("pixel_f1"),
        "image_threshold": classification.get("image_threshold"),
        "pixel_threshold": localization.get("pixel_threshold"),
    }


def _load_prediction(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(f"Required prediction not found: {path}")
    with np.load(path, allow_pickle=False) as data:
        required = {"labels", "scores", "masks", "maps"}
        if not required <= set(data.files):
            raise ValueError(f"{path.name} missing arrays: {sorted(required - set(data.files))}")
        return {key: np.asarray(data[key]) for key in required}


def compare_runs(cpu_run: Path, cuda_run: Path, atol: float = 1e-5, rtol: float = 1e-5) -> tuple[dict, list[dict]]:
    if atol < 0 or rtol < 0:
        raise ValueError("atol and rtol must be non-negative")
    cpu_run, cuda_run = Path(cpu_run), Path(cuda_run)
    cpu_result = _read_json(cpu_run / "results.json")
    cuda_result = _read_json(cuda_run / "results.json")
    cpu_spec, cuda_spec = cpu_result.get("model_spec", {}), cuda_result.get("model_spec", {})
    cpu_methods = sorted(cpu_result.get("methods", {}))
    cuda_methods = sorted(cuda_result.get("methods", {}))
    if not cpu_methods:
        raise ValueError("results.json contains no methods")
    checks = {
        "model_spec": cpu_spec == cuda_spec,
        "source_commit": cpu_spec.get("source_commit") == cuda_spec.get("source_commit"),
        "category": cpu_spec.get("category") == cuda_spec.get("category"),
        "seed": cpu_spec.get("seed") == cuda_spec.get("seed"),
        "train_paths": cpu_spec.get("train_paths") == cuda_spec.get("train_paths"),
        "calibration_paths": cpu_spec.get("calibration_paths") == cuda_spec.get("calibration_paths"),
        "test_paths": cpu_result.get("test_paths") == cuda_result.get("test_paths"),
        "swinir_checkpoint_sha256": (
            cpu_result.get("restoration", {}).get("checkpoint_sha256")
            == cuda_result.get("restoration", {}).get("checkpoint_sha256")
        ),
        "restoration_name": (
            cpu_result.get("restoration", {}).get("name") == cuda_result.get("restoration", {}).get("name")
        ),
        "method_names": cpu_methods == cuda_methods,
        "split": _read_json(cpu_run / "split.json") == _read_json(cuda_run / "split.json"),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"Exact parity mismatch: {', '.join(failed)}")

    rows: list[dict] = []
    cpu_summary, cuda_summary = _read_summary(cpu_run / "summary.csv"), _read_summary(cuda_run / "summary.csv")
    if sorted(cpu_summary) != cpu_methods or sorted(cuda_summary) != cpu_methods:
        raise ValueError("summary.csv method names do not match results.json")
    for method in cpu_methods:
        cpu_json_metrics = _result_metrics(cpu_result, method)
        cuda_json_metrics = _result_metrics(cuda_result, method)
        for metric in METRICS:
            rows.append(_numeric_row("summary.csv", method, metric,
                                     cpu_summary[method].get(metric), cuda_summary[method].get(metric), atol, rtol))
            rows.append(_numeric_row("results.json", method, metric,
                                     cpu_json_metrics[metric], cuda_json_metrics[metric], atol, rtol))

    prediction_differences = {}
    for method in cpu_methods:
        cpu_prediction = _load_prediction(cpu_run / f"{method}_predictions.npz")
        cuda_prediction = _load_prediction(cuda_run / f"{method}_predictions.npz")
        for key in ("labels", "scores", "masks", "maps"):
            checks[f"{method}.{key}.shape"] = cpu_prediction[key].shape == cuda_prediction[key].shape
        if not all(checks[name] for name in checks if name.startswith(f"{method}.")):
            raise ValueError(f"Prediction array shape mismatch: {method}")
        if not np.array_equal(cpu_prediction["labels"], cuda_prediction["labels"]):
            raise ValueError(f"Prediction labels mismatch: {method}")
        if not np.array_equal(cpu_prediction["masks"], cuda_prediction["masks"]):
            raise ValueError(f"Prediction masks mismatch: {method}")
        checks[f"{method}.labels"] = checks[f"{method}.masks"] = True
        prediction_differences[method] = {}
        for key in ("scores", "maps"):
            cpu_array = np.asarray(cpu_prediction[key], dtype=np.float64)
            cuda_array = np.asarray(cuda_prediction[key], dtype=np.float64)
            if not np.isfinite(cpu_array).all() or not np.isfinite(cuda_array).all():
                raise ValueError(f"Non-finite prediction values: {method}.{key}")
            difference = np.abs(cpu_array - cuda_array)
            item = {
                "max_abs_diff": float(difference.max(initial=0.0)),
                "mean_abs_diff": float(difference.mean()) if difference.size else 0.0,
                "tolerance_pass": bool(np.allclose(cpu_array, cuda_array, atol=atol, rtol=rtol)),
            }
            prediction_differences[method][key] = item
            rows.append({
                "section": "prediction", "source": "npz", "method": method, "metric": key,
                "cpu_value": None, "cuda_value": None, "absolute_difference": None,
                "relative_difference": None, "max_absolute_difference": item["max_abs_diff"],
                "mean_absolute_difference": item["mean_abs_diff"],
                "tolerance_pass": item["tolerance_pass"], "speedup_cpu_over_cuda": None,
            })

    runtimes = {}
    for metric in RUNTIMES:
        cpu_value, cuda_value = _number(cpu_result.get(metric)), _number(cuda_result.get(metric))
        speedup = cpu_value / cuda_value if cpu_value is not None and cuda_value and cuda_value > 0 else None
        runtimes[metric] = {"cpu_seconds": cpu_value, "cuda_seconds": cuda_value, "speedup_cpu_over_cuda": speedup}
        rows.append({
            "section": "runtime", "source": "results.json", "method": "", "metric": metric,
            "cpu_value": cpu_value, "cuda_value": cuda_value,
            "absolute_difference": abs(cpu_value - cuda_value) if cpu_value is not None and cuda_value is not None else None,
            "relative_difference": None, "max_absolute_difference": None, "mean_absolute_difference": None,
            "tolerance_pass": None, "speedup_cpu_over_cuda": speedup,
        })

    numeric_pass = all(row["tolerance_pass"] for row in rows if row["section"] == "numeric")
    prediction_pass = all(item["tolerance_pass"] for method in prediction_differences.values() for item in method.values())
    report = {
        "cpu_run": str(cpu_run), "cuda_run": str(cuda_run), "atol": atol, "rtol": rtol,
        "exact_checks": checks,
        "device_metadata": {
            "cpu": {key: cpu_result.get(key) for key in DEVICE_FIELDS},
            "cuda": {key: cuda_result.get(key) for key in DEVICE_FIELDS},
        },
        "numeric_tolerance_pass": numeric_pass,
        "prediction_tolerance_pass": prediction_pass,
        "overall_pass": numeric_pass and prediction_pass,
        "numeric_comparisons": [row for row in rows if row["section"] == "numeric"],
        "prediction_differences": prediction_differences,
        "runtime_comparison": runtimes,
    }
    return report, rows


def write_outputs(report: dict, rows: list[dict], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "cpu_cuda_parity.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "cpu_cuda_parity.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    note = f"""# CPU/CUDA parity note

- CPU run: `{report['cpu_run']}`
- CUDA run: `{report['cuda_run']}`
- Tolerance: `atol={report['atol']}`, `rtol={report['rtol']}`
- Exact metadata/shape/label/mask checks: pass
- Numeric metrics within tolerance: {report['numeric_tolerance_pass']}
- Raw scores/maps within tolerance: {report['prediction_tolerance_pass']}
- Overall parity: {report['overall_pass']}

Runtime and speedup are reported separately and do not affect research metrics or parity tolerances. The tolerances are execution-parity settings, not thresholds for research conclusions.
"""
    (output / "CPU_CUDA_NOTE.md").write_text(note, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu-run", type=Path, required=True)
    parser.add_argument("--cuda-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--rtol", type=float, default=1e-5)
    args = parser.parse_args()
    report, rows = compare_runs(args.cpu_run, args.cuda_run, args.atol, args.rtol)
    write_outputs(report, rows, args.output)
    print(json.dumps({"overall_pass": report["overall_pass"], "output": str(args.output)}, ensure_ascii=False))
    if not report["overall_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
