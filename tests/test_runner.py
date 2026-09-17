import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest
import yaml

from sr_anomaly.reporting import aggregate_results
from sr_anomaly.runner import run_experiment


def write_config(root: Path, experiment_id: str = "e2e") -> Path:
    images = root / "images"
    images.mkdir()
    y, x = np.mgrid[:20, :20]
    array = np.stack(((x * 9) % 256, (y * 11) % 256, ((x + y) * 6) % 256), axis=-1).astype(np.uint8)
    Image.fromarray(array, "RGB").save(images / "sample.png")
    config = {
        "experiment": {"id": experiment_id, "seed": 42},
        "dataset": {"root": "images", "recursive": True},
        "degradations": [
            {"name": "gaussian_noise", "severity": 1},
            {"name": "low_resolution", "severity": 2},
        ],
        "restoration": {"name": "identity"},
        "anomaly_detector": {"name": "noop"},
        "metrics": ["psnr", "ssim"],
        "output_root": "outputs",
    }
    path = root / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def test_end_to_end_manifest_results_and_aggregation(tmp_path: Path) -> None:
    run_dir = run_experiment(write_config(tmp_path))
    manifest = [json.loads(line) for line in (run_dir / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    results = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(manifest) == 4
    assert len(results) == 4
    assert {row["variant"] for row in results} == {"no_restoration", "restored"}
    assert all(not Path(row["source_path"]).is_absolute() for row in manifest)
    assert all(not Path(row["output_path"]).is_absolute() for row in manifest)
    assert all(row["detection"]["dataset_metrics"] is None for row in results)
    assert all(row["detection"]["metrics_status"] == "not_computed" for row in results)

    combined, comparison = aggregate_results([run_dir / "results.csv"], tmp_path / "reports")
    with combined.open("r", encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 4
    with comparison.open("r", encoding="utf-8", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    assert len(summaries) == 4
    assert all(row["anomaly_score_mean"] == "" for row in summaries)


def test_unsafe_experiment_id_is_rejected(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, "../escape")
    with pytest.raises(ValueError, match="experiment id"):
        run_experiment(config_path)


def test_existing_run_is_not_overwritten(tmp_path: Path) -> None:
    config_path = write_config(tmp_path)
    run_experiment(config_path)
    with pytest.raises(FileExistsError):
        run_experiment(config_path)

