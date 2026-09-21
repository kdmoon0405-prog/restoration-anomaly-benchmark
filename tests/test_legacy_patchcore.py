from pathlib import Path
from types import SimpleNamespace

import pytest

import sr_anomaly.device as device_helpers
from scripts.run_legacy_patchcore import _balanced_test, _delta, _parse_args, _select_indices
from sr_anomaly.dataset import ImageSample
from sr_anomaly.device import device_metadata, elapsed_seconds, resolve_device, start_timer


def test_legacy_subset_is_deterministic_and_balanced() -> None:
    assert _select_indices(20, 5, 11) == _select_indices(20, 5, 11)
    assert len(_select_indices(20, 5, 11)) == 5
    assert _select_indices(3, 0, 11) == [0, 1, 2]
    with pytest.raises(ValueError):
        _select_indices(3, -1, 11)
    samples = [ImageSample(str(index), Path(str(index)), Path(str(index)), metadata={"label": index % 2}) for index in range(10)]
    chosen = _balanced_test(samples, 4, 11)
    assert sum(sample.metadata["label"] for sample in chosen) == 2
    assert len(chosen) == 4
    assert _delta(2.0, 1.0) == 1.0
    assert _delta(None, 1.0) is None


def test_device_resolution_metadata_and_cuda_timing(monkeypatch) -> None:
    assert _parse_args([]).device == "cpu"
    assert _parse_args(["--device", "auto"]).device == "auto"
    assert resolve_device("cpu", True) == "cpu"
    assert resolve_device("auto", False) == "cpu"
    assert resolve_device("auto", True) == "cuda"
    assert resolve_device("cuda", True) == "cuda"
    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        resolve_device("cuda", False)
    assert device_metadata("auto", "cpu", False) == {
        "requested_device": "auto", "actual_device": "cpu", "cuda_available": False,
    }
    assert device_metadata("cuda", "cuda:0", True, "Test GPU")["gpu_name"] == "Test GPU"

    synchronized = []
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda device: synchronized.append(str(device))))
    ticks = iter((10.0, 12.5))
    monkeypatch.setattr(device_helpers, "perf_counter", lambda: next(ticks))
    started = start_timer(fake_torch, "cuda:0")
    assert elapsed_seconds(fake_torch, "cuda:0", started) == 2.5
    assert synchronized == ["cuda:0", "cuda:0"]
    synchronized.clear()
    ticks = iter((20.0, 21.0))
    monkeypatch.setattr(device_helpers, "perf_counter", lambda: next(ticks))
    assert elapsed_seconds(fake_torch, "cpu", start_timer(fake_torch, "cpu")) == 1.0
    assert synchronized == []
