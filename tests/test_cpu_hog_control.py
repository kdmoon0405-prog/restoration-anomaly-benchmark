from pathlib import Path
import json

import numpy as np
from PIL import Image
import pytest

pytest.importorskip("sklearn")

from sr_anomaly.analysis_io import read_json
from sr_anomaly.cpu_hog_control import canonical, query_image, hog_descriptors, HOGMemoryDetector
from sr_anomaly import cpu_hog_control as study
from sr_anomaly.models import AnomalyDetector

ROOT = Path(__file__).resolve().parents[1]


def settings():
    return read_json(ROOT / "configs/cpu_hog_control.json")


def test_canonical_and_fixed_queries_deterministic():
    rng = np.random.default_rng(11)
    source = Image.fromarray(rng.integers(0, 256, (90, 120, 3), dtype=np.uint8))
    clean = canonical(source)
    assert clean.size == (224, 224)
    np.testing.assert_array_equal(clean, canonical(source))
    for variant in settings()["variants"]:
        result = query_image(clean, variant, settings())
        assert result.size == clean.size
        np.testing.assert_array_equal(result, query_image(clean, variant, settings()))
    mask = canonical(Image.new("L", source.size, 255), mask=True)
    assert np.asarray(mask).all()


def test_trusted_hog_and_exact_zero_distance_interface():
    image = Image.new("RGB", (224, 224), "gray")
    features = hog_descriptors(image, settings())
    assert features.shape == (729, 36) and np.isfinite(features).all()
    model = HOGMemoryDetector(features[:4], settings())
    assert isinstance(model, AnomalyDetector)
    result = model.predict(image)
    assert result.image_score == 0 and result.pixel_map.shape == (224, 224)
    assert not result.pixel_map.any()


def test_hog_shape_and_bank_guards():
    with pytest.raises(ValueError):
        hog_descriptors(Image.new("RGB", (32, 32)), settings())
    with pytest.raises(ValueError):
        HOGMemoryDetector(np.zeros((4, 3)), settings())


def test_tiny_cpu_end_to_end(tmp_path, monkeypatch):
    root = tmp_path / "data"
    for split, defect, count in (("train", "good", 4), ("test", "good", 1), ("test", "crack", 1)):
        folder = root / "tiny" / split / defect
        folder.mkdir(parents=True)
        for i in range(count):
            a = np.tile(np.arange(64, dtype=np.uint8), (64, 1))
            rgb = np.stack([a + i, a, a], axis=-1)
            if defect == "crack":
                rgb[25:35, 25:35] = 255
            Image.fromarray(rgb).save(folder / f"{i:03d}.png")
    gt = root / "tiny/ground_truth/crack"
    gt.mkdir(parents=True)
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[25:35, 25:35] = 255
    Image.fromarray(mask).save(gt / "000_mask.png")
    config = settings()
    config.update(bank_capacity=32, categories=["tiny"])
    monkeypatch.setattr(study, "_guard", lambda required, phase: dict(phase=phase, required=required))
    predictions = []
    original_predict = HOGMemoryDetector.predict
    original_read = Path.read_bytes

    def predict(self, image):
        predictions.append(1)
        return original_predict(self, image)

    def read(path):
        if "ground_truth" in path.parts:
            assert len(predictions) == 9  # one calibration + two test, three variants
        return original_read(path)

    monkeypatch.setattr(HOGMemoryDetector, "predict", predict)
    monkeypatch.setattr(Path, "read_bytes", read)
    out = tmp_path / "run"
    state = study.infer_category(root, out, config, "tiny")
    assert state["bank_vectors"] == 32 and state["test_count"] == 2
    assert state["normal_fit_count"] == 3 and state["normal_calibration_count"] == 1
    final = study.evaluate_category(out)
    assert final["status"] == "EVALUATED_COMPLETE"
    assert (out / "summary.csv").is_file() and (out / "per_image.csv").is_file()
    assert len(read_json(out / "results.json")["variants"]) == 3
