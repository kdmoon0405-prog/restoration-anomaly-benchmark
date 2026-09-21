"""Mock integration test for scripts/run_fusion_patchcore.py.

Stubs the heavy PatchCore/SwinIR/MVTec upstream pieces with deterministic fakes
so the full experiment wiring (split -> fit -> calibration pairs -> frozen
fusion -> per-method thresholds -> artifacts) is verified without PyTorch,
FAISS, or the real dataset.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

import scripts.run_fusion_patchcore as fusion_script


def _paint(path: Path, size: tuple[int, int] = (64, 64), value: int = 128) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.full((*size[::-1], 3), value, dtype=np.uint8), "RGB").save(path)


def _mask(path: Path, size: tuple[int, int] = (64, 64)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    array = np.zeros(size[::-1], dtype=np.uint8)
    array[8:16, 8:16] = 255
    Image.fromarray(array, "L").save(path)


def _layout(data_root: Path) -> None:
    for index in range(8):
        _paint(data_root / "hazelnut" / "train" / "good" / f"{index:03d}.png", value=100 + index)
    for index in range(3):
        _paint(data_root / "hazelnut" / "test" / "good" / f"{index:03d}.png", value=110 + index)
    for index in range(3):
        _paint(data_root / "hazelnut" / "test" / "crack" / f"{index:03d}.png", value=150 + index)
        _mask(data_root / "hazelnut" / "ground_truth" / "crack" / f"{index:03d}_mask.png")


class _FakeTensor:
    def unsqueeze(self, _dim: int) -> "_FakeTensor":
        return self


class _FakeResize:
    def __init__(self, size: int, interpolation=None) -> None:
        self.size = size

    def __call__(self, image: Image.Image) -> Image.Image:
        return image.resize((self.size, self.size), Image.Resampling.BILINEAR)


class _FakeCenterCrop:
    def __init__(self, size: int) -> None:
        self.size = size

    def __call__(self, image: Image.Image) -> Image.Image:
        left = max((image.width - self.size) // 2, 0)
        top = max((image.height - self.size) // 2, 0)
        return image.crop((left, top, left + self.size, top + self.size))


class _FakeCompose:
    def __init__(self, steps) -> None:
        self.steps = steps

    def __call__(self, image):
        value = image
        for step in self.steps:
            value = step(value)
        return value


class _FakePatchCore:
    def __init__(self, _device) -> None:
        self.rng = np.random.default_rng(7)

    def load(self, **_kwargs) -> None:
        return None

    def fit(self, _loader) -> None:
        return None

    def predict(self, _tensor):
        scores = self.rng.normal(0.0, 1.0, size=(1,))
        maps = self.rng.normal(0.0, 1.0, size=(1, 224, 224)).astype(np.float32)
        return scores, maps

    def save_to_path(self, staging) -> None:
        Path(staging, "patchcore_params.pkl").write_bytes(b"params")
        Path(staging, "nnscorer_search_index.faiss").write_bytes(b"faiss")

    def load_from_path(self, *_args, **_kwargs) -> None:
        return None


class _FakeMVTecDataset:
    def __init__(self, root: str, category: str, **_kwargs) -> None:
        train_dir = Path(root) / category / "train" / "good"
        paths = sorted(train_dir.glob("*.png"))
        self.data_to_iterate = [(None, None, str(path)) for path in paths]

    def __len__(self) -> int:
        return len(self.data_to_iterate)


class _FakeRestorer:
    name = "fake_swinir_x4"

    def __init__(self, *_args, **_kwargs) -> None:
        return None

    def restore(self, image: Image.Image) -> Image.Image:
        return image.resize((224, 224), Image.Resampling.BICUBIC)


def _install_fakes(monkeypatch, data_root: Path) -> None:
    torch = SimpleNamespace(
        device=lambda _name: "cpu",
        cuda=SimpleNamespace(is_available=lambda: False),
        set_num_threads=lambda _count: None,
        get_num_threads=lambda: 8,
        utils=SimpleNamespace(
            data=SimpleNamespace(
                Subset=lambda dataset, indices: (dataset, list(indices)),
                DataLoader=lambda subset, **_kwargs: subset,
            )
        ),
    )
    transforms = SimpleNamespace(
        Resize=_FakeResize,
        CenterCrop=_FakeCenterCrop,
        Compose=_FakeCompose,
        ToTensor=lambda: (lambda _image: _FakeTensor()),
        Normalize=lambda _mean, _std: (lambda value: value),
    )
    interpolation = SimpleNamespace(BILINEAR="bilinear", NEAREST="nearest")
    backbones = SimpleNamespace(load=lambda _name: SimpleNamespace(name="wideresnet50"))
    common = SimpleNamespace(FaissNN=lambda *_args: object())
    patchcore = SimpleNamespace(PatchCore=_FakePatchCore)
    sampler = SimpleNamespace(IdentitySampler=lambda: object())
    mvtec = SimpleNamespace(
        MVTecDataset=_FakeMVTecDataset,
        DatasetSplit=SimpleNamespace(TRAIN="train"),
        IMAGENET_MEAN=(0.485, 0.456, 0.406),
        IMAGENET_STD=(0.229, 0.224, 0.225),
    )
    monkeypatch.setattr(fusion_script, "_official_imports", lambda: (torch, transforms, interpolation, backbones, common, patchcore, sampler, mvtec))
    monkeypatch.setattr(fusion_script, "SwinIRLightweight", _FakeRestorer)
    monkeypatch.setattr(
        fusion_script.subprocess, "check_output", lambda *_args, **_kwargs: fusion_script.EXPECTED_PATCHCORE_COMMIT
    )


def test_fusion_script_end_to_end_with_fakes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _layout(data_root)
    _install_fakes(monkeypatch, data_root)
    checkpoint = tmp_path / "swinirFake.pth"
    checkpoint.write_bytes(b"checkpoint")
    model_dir = tmp_path / "model"
    output_dir = tmp_path / "outputs" / "fusion-test"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_fusion_patchcore.py",
            "--data-root", str(data_root),
            "--category", "hazelnut",
            "--seed", "11",
            "--train-ratio", "0.5",
            "--test-limit", "6",
            "--swinir-checkpoint", str(checkpoint),
            "--model-dir", str(model_dir),
            "--output-dir", str(output_dir),
        ],
    )
    fusion_script.main()

    split = json.loads((output_dir / "split.json").read_text(encoding="utf-8"))
    assert len(split["train_indices"]) == 4
    assert len(split["calibration_indices"]) == 4
    assert set(split["train_indices"]).isdisjoint(split["calibration_indices"])

    with (output_dir / "summary.csv").open(encoding="utf-8") as handle:
        methods = [row["method"] for row in csv.DictReader(handle)]
    assert methods == ["clean_reference", "degraded_only", "restored_only", "mean_0.5_0.5", "max"]
    with (output_dir / "per_image.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert sum(int(row["label"]) for row in rows) == 3

    result = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert result["requested_device"] == "cpu"
    assert result["actual_device"] == "cpu"
    assert result["cuda_available"] is False
    assert "gpu_name" not in result
    assert set(result["fusion_calibration"]["image_thresholds"]) == {
        "degraded_only", "restored_only", "mean_0.5_0.5", "max",
    }
    assert "delta_pixel_auroc" in result["comparison_mean_vs_restored_only"]
    for name in ("clean_reference", "degraded_only", "restored_only", "mean_0.5_0.5", "max"):
        assert (output_dir / f"{name}_predictions.npz").is_file()

    # Reusing the frozen split replays the exact same image lists.
    output_dir2 = tmp_path / "outputs" / "fusion-test-reuse"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_fusion_patchcore.py",
            "--data-root", str(data_root),
            "--category", "hazelnut",
            "--seed", "11",
            "--train-ratio", "0.5",
            "--test-limit", "6",
            "--split-json", str(output_dir / "split.json"),
            "--swinir-checkpoint", str(checkpoint),
            "--model-dir", str(tmp_path / "model2"),
            "--output-dir", str(output_dir2),
        ],
    )
    fusion_script.main()
    split2 = json.loads((output_dir2 / "split.json").read_text(encoding="utf-8"))
    assert split2["train_indices"] == split["train_indices"]
    assert split2["calibration_indices"] == split["calibration_indices"]


def test_fusion_script_rejects_unavailable_cuda(monkeypatch, tmp_path: Path) -> None:
    _install_fakes(monkeypatch, tmp_path / "data")
    monkeypatch.setattr(sys, "argv", [
        "run_fusion_patchcore.py", "--device", "cuda", "--swinir-checkpoint", str(tmp_path / "swinir.pth"),
    ])
    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        fusion_script.main()
