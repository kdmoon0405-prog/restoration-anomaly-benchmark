from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from scripts.run_fusion_patchcore import _validate_replayed_split
from scripts.validate_experiment_ready import dataset_summary, validate_output_dir


def test_replayed_split_rejects_provenance_and_index_drift() -> None:
    split = {
        "category": "hazelnut", "train_count_total": 4, "seed": 11, "train_ratio": 0.5,
        "train_indices": [0, 2], "calibration_indices": [1, 3],
    }
    assert _validate_replayed_split(split, "hazelnut", 4, 11, 0.5) == ([0, 2], [1, 3])
    with pytest.raises(ValueError, match="seed"):
        _validate_replayed_split(split, "hazelnut", 4, 29, 0.5)
    split["calibration_indices"] = [2, 3]
    with pytest.raises(ValueError, match="unique"):
        _validate_replayed_split(split, "hazelnut", 4, 11, 0.5)


def test_preflight_reads_counts_masks_and_output_state(tmp_path: Path) -> None:
    root = tmp_path / "MVTecAD"
    for relative in (
        "screw/train/good/000.png", "screw/test/good/000.png",
        "screw/test/scratch/001.png", "screw/ground_truth/scratch/001_mask.png",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("L" if "ground_truth" in relative else "RGB", (8, 8), 255).save(path)
    assert dataset_summary(root, "screw") == {
        "train_normal_count": 1, "test_count": 2, "test_normal_count": 1,
        "test_anomalous_count": 1, "defect_types": ["scratch"],
    }
    output = tmp_path / "output"
    assert validate_output_dir(output) == "absent"
    output.mkdir()
    assert validate_output_dir(output) == "empty"
    (output / "partial.txt").write_text("partial")
    with pytest.raises(ValueError, match="must not exist or must be empty"):
        validate_output_dir(output)
