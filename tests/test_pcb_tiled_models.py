"""Actual vendored embedding path on fabricated feature tensors, no real backbone/index."""
from pathlib import Path
import sys

import numpy as np
import pytest

from sr_anomaly.pcb_tiled_models import PatchCoreTiles, normalize_tiles


@pytest.fixture
def fake_feature_model():
    torch = pytest.importorskip("torch")
    pytest.importorskip("faiss")
    pytest.importorskip("timm")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"third_party/patchcore-inspection/src"))
    from patchcore import common, patchcore
    class Features(torch.nn.Module):
        def forward(self, images):
            code = images[:, :1, :1, :1]
            grid = torch.arange(784, dtype=torch.float32).reshape(1,1,28,28)
            return {"layer2": grid+code*1000, "layer3": grid[..., ::2, ::2]+code*100}
    model = patchcore.PatchCore(torch.device("cpu"))
    model.layers_to_extract_from = ["layer2", "layer3"]
    model.patch_maker = patchcore.PatchMaker(3, stride=1)
    model.forward_modules = torch.nn.ModuleDict({"feature_aggregator": Features(),
        "preprocessing": common.Preprocessing([1,1], 1024), "preadapt_aggregator": common.Aggregator(1024)})
    return torch, model


def test_actual_embed_patchmaker_alignment_and_batch_order(fake_feature_model):
    torch, model = fake_feature_model
    rgb = np.zeros((2,224,224,3), np.uint8)
    rgb[1] = 255
    adapter = PatchCoreTiles(model, "cpu")
    batch = adapter.extract(rgb)
    assert batch.shape == (2,28,28,1024) and batch.dtype == np.float32
    # Actual Unfold's central values prove patch-y/x order independently of adapter reshape.
    grid = torch.arange(2*784, dtype=torch.float32).reshape(2,1,28,28)
    patches, shape = model.patch_maker.patchify(grid, return_spatial_info=True)
    assert tuple(shape) == (28,28)
    np.testing.assert_array_equal(patches[:, :, 0, 1, 1].numpy(), grid.numpy().reshape(2,784))
    singles = np.concatenate([adapter.extract(rgb[i:i+1]) for i in range(2)])
    np.testing.assert_array_equal(batch, singles)
    assert not np.array_equal(batch[0], batch[1])
    with pytest.raises(ValueError, match="Patch grid"):
        PatchCoreTiles(model, "cpu", patch_shape=(14,14)).extract(rgb)
    with pytest.raises(ValueError, match="dimension"):
        PatchCoreTiles(model, "cpu", dimension=4).extract(rgb)


def test_normalization_matches_existing_transform_no_geometry(fake_feature_model):
    torch, _ = fake_feature_model
    from torchvision.transforms import Normalize, ToTensor
    from PIL import Image
    rgb = np.arange(224*224*3, dtype=np.uint8).reshape(224,224,3)
    expected = Normalize([.485,.456,.406], [.229,.224,.225])(ToTensor()(Image.fromarray(rgb)))
    assert torch.equal(normalize_tiles(rgb[None], "cpu")[0], expected)


def test_bank_bind_and_predict_use_existing_scorer_and_no_geometry(fake_feature_model):
    _, model = fake_feature_model
    class Scorer:
        def fit(self, arrays):
            assert len(arrays) == 1 and not arrays[0].flags.writeable
    model.anomaly_scorer = Scorer()
    def predict(images):
        assert tuple(images.shape) == (1,3,224,224)
        return [123.], [np.ones((224,224), np.float32)]
    model.predict = predict
    adapter = PatchCoreTiles(model, "cpu")
    rgb = np.zeros((224,224,3), np.uint8)
    with pytest.raises(ValueError, match="No bounded bank"):
        adapter.predict(rgb)
    bank = np.zeros((3,1024), np.float32)
    with pytest.raises(ValueError, match="read-only"):
        adapter.bind_bank(bank)
    bank.flags.writeable = False
    adapter.bind_bank(bank)
    values, score = adapter.predict(rgb)
    assert values.shape == (224,224) and score == 123.
    with pytest.raises(ValueError):
        adapter.bind_bank(bank)


def test_actual_upstream_predict_postprocessing_without_faiss_search(fake_feature_model):
    _, model = fake_feature_model
    from patchcore.common import RescaleSegmentor
    class Distances:
        def fit(self, arrays):
            assert not arrays[0].flags.writeable
        def predict(self, arrays):
            values = np.arange(len(arrays[0]), dtype=np.float32)
            return values, values[:, None], np.zeros((len(values),1), dtype=np.int64)
    model.anomaly_scorer = Distances()
    model.anomaly_segmentor = RescaleSegmentor(device="cpu", target_size=(224,224))
    adapter = PatchCoreTiles(model, "cpu")
    bank = np.zeros((2,1024), np.float32)
    bank.flags.writeable = False
    adapter.bind_bank(bank)
    values, score = adapter.predict(np.zeros((224,224,3), np.uint8))
    assert values.dtype == np.float32 and values.shape == (224,224)
    assert np.isfinite(values).all() and score == 783.
    assert values.min() < values.max() < score  # smoothing is not the image score
