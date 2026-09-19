import numpy as np
from PIL import Image
import pytest

from sr_anomaly.real_models import PatchCoreTorchAdapter, SwinIRLightweight


class FakeInferencer:
    def __init__(self, anomaly_map: np.ndarray) -> None:
        self.anomaly_map = anomaly_map

    def predict(self, _image: Image.Image):
        return type("Prediction", (), {"pred_score": np.array([0.25]), "anomaly_map": self.anomaly_map})()


def test_patchcore_adapter_aligns_map_to_input() -> None:
    adapter = PatchCoreTorchAdapter.__new__(PatchCoreTorchAdapter)
    adapter._inferencer = FakeInferencer(np.ones((1, 4, 4), dtype=np.float32))

    prediction = adapter.predict(Image.new("RGB", (8, 6)))

    assert prediction.image_score == 0.25
    assert prediction.pixel_map.shape == (6, 8)
    assert prediction.metadata["raw_map_size"] == [4, 4]


def test_patchcore_adapter_rejects_nonfinite_output() -> None:
    adapter = PatchCoreTorchAdapter.__new__(PatchCoreTorchAdapter)
    adapter._inferencer = FakeInferencer(np.full((1, 4, 4), np.nan, dtype=np.float32))

    with pytest.raises(ValueError, match="non-finite"):
        adapter.predict(Image.new("RGB", (8, 6)))


def test_swinir_rejects_unsupported_scale() -> None:
    with pytest.raises(ValueError, match="x2, x3, or x4"):
        SwinIRLightweight("missing", "missing", scale=5)
