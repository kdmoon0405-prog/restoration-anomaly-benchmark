from pathlib import Path

import pytest
import yaml

from sr_anomaly.matrix import generate_experiment_matrix


def write_base(root: Path) -> Path:
    base = {
        "experiment": {"id": "base", "seed": 1},
        "dataset": {"root": "images"},
        "degradations": [{"name": "gaussian_blur", "severity": 1}],
        "restoration": {"name": "identity"},
        "anomaly_detector": {"name": "noop"},
        "metrics": ["psnr", "ssim"],
        "output_root": "outputs",
    }
    path = root / "base.yaml"
    path.write_text(yaml.safe_dump(base), encoding="utf-8")
    return path


def test_matrix_generation_and_limit(tmp_path: Path) -> None:
    write_base(tmp_path)
    matrix = {
        "base_config": "base.yaml",
        "experiment_prefix": "trial",
        "max_runs": 4,
        "axes": {"seeds": [1, 2], "degradations": [[{"name": "gaussian_blur", "severity": 1}]]},
    }
    matrix_path = tmp_path / "matrix.yaml"
    matrix_path.write_text(yaml.safe_dump(matrix), encoding="utf-8")
    generated = generate_experiment_matrix(matrix_path, tmp_path / "generated")
    assert [path.name for path in generated] == ["trial-001.yaml", "trial-002.yaml"]

    matrix["max_runs"] = 1
    matrix_path.write_text(yaml.safe_dump(matrix), encoding="utf-8")
    with pytest.raises(ValueError, match="above max_runs"):
        generate_experiment_matrix(matrix_path, tmp_path / "blocked")

