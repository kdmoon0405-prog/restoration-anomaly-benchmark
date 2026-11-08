from pathlib import Path

import numpy as np
from PIL import Image
import pytest

pytest.importorskip("sklearn")
from sr_anomaly.analysis_io import digest, read_json, write_json
from sr_anomaly import cpu_restoration_control as study
from sr_anomaly.cpu_hog_control import evaluate_category, HOGMemoryDetector


def fixture(tmp_path, monkeypatch):
    reference = tmp_path / "reference"
    reference.mkdir()
    paths = ["tiny/train/good/0.png", "tiny/test/good/0.png", "tiny/test/crack/0.png"]
    receipts = {}
    for i, name in enumerate(paths):
        image = np.tile(np.arange(224, dtype=np.uint8), (224, 1))
        rgb = np.stack((image, image, image), axis=-1)
        rgb[30:40, 50:60] = i * 70
        destination = reference / "canonical" / name
        destination.parent.mkdir(parents=True)
        Image.fromarray(rgb).save(destination)
        receipts[name] = dict(canonical_file_sha256=digest(destination))
    write_json(reference / "rgb_receipts.json", receipts)
    write_json(reference / "split.json", dict(calibration_paths=paths[:1], test_paths=paths[1:], fit_paths=["other"]))
    config = read_json(Path(__file__).resolve().parents[1] / "configs/cpu_hog_control.json")
    np.save(reference / "bank.npy", np.ones((8, 36), dtype=np.float32) / 6)
    masks = np.zeros((2, 224, 224), dtype=bool)
    masks[1, 30:40, 50:60] = True
    np.savez(reference / "bicubic_x4_predictions.npz", labels=[0, 1], masks=masks)
    write_json(reference / "status.json", dict(status="EVALUATED_COMPLETE", category="tiny", seed=11,
        study_family=config["study_family"], settings=config, source_code_sha256=digest(study.__file__.replace(
            "cpu_restoration_control.py", "cpu_hog_control.py")), input_inventory_sha256="b" * 64,
        normal_fit_count=1, normal_calibration_count=1, test_count=2,
        bank_sha256=digest(reference / "bank.npy"),
        prediction_sha256=dict(bicubic_x4=digest(reference / "bicubic_x4_predictions.npz"))))
    repository = tmp_path / "repository"
    (repository / "models").mkdir(parents=True)
    (repository / "models/network_swinir.py").write_text("# fake, never imported\n")
    checkpoint = tmp_path / "checkpoint"
    checkpoint.write_bytes(b"fake, never loaded")
    monkeypatch.setattr(study, "CHECKPOINT_SHA256", digest(checkpoint))
    monkeypatch.setattr(study, "available_ram", lambda: 2**40)
    monkeypatch.setattr(study, "_guard", lambda *args: {})
    return reference, repository, checkpoint


class FakeRestorer:
    def restore(self, low):
        return low.resize((224, 224), Image.Resampling.BICUBIC)


def test_cache_resume_and_change_guard(tmp_path, monkeypatch):
    reference, repository, checkpoint = fixture(tmp_path, monkeypatch)
    out = tmp_path / "cache"
    state = study.cache_restoration([reference], out, repository, checkpoint, model_factory=FakeRestorer)
    assert state["status"] == "CPU_RESTORATION_CACHE_COMPLETE" and len(state["completed"]) == 3
    same = study.cache_restoration([reference], out, repository, checkpoint, resume=True,
                                  model_factory=lambda: pytest.fail("Do not run completed model queries twice"))
    assert same == state
    with pytest.raises(FileExistsError):
        study.cache_restoration([reference], out, repository, checkpoint, model_factory=FakeRestorer)
    first = next(iter(state["completed"]))
    (out / "images" / first).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        study.cache_restoration([reference], out, repository, checkpoint, resume=True, model_factory=FakeRestorer)


def test_fixed_checkpoint_and_resource_guard(tmp_path, monkeypatch):
    reference, repository, checkpoint = fixture(tmp_path, monkeypatch)
    checkpoint.write_bytes(b"different")
    with pytest.raises(ValueError, match="checkpoint"):
        study.cache_restoration([reference], tmp_path / "bad", repository, checkpoint, model_factory=FakeRestorer)
    monkeypatch.setattr(study, "CHECKPOINT_SHA256", digest(checkpoint))
    monkeypatch.setattr(study, "available_ram", lambda: 0)
    with pytest.raises(MemoryError):
        study.cache_restoration([reference], tmp_path / "blocked", repository, checkpoint, model_factory=FakeRestorer)
    assert read_json(tmp_path / "blocked/status.json")["status"] == "BLOCKED_RESOURCES"


def test_bank_reuse_gt_after_predictions(tmp_path, monkeypatch):
    reference, repository, checkpoint = fixture(tmp_path, monkeypatch)
    cache = tmp_path / "cache"
    study.cache_restoration([reference], cache, repository, checkpoint, model_factory=FakeRestorer)
    predict = HOGMemoryDetector.predict
    load = np.load
    calls = []

    def predicted(self, image):
        calls.append(1)
        return predict(self, image)

    def loaded(path, *args, **kwargs):
        if Path(path).name == "bicubic_x4_predictions.npz":
            assert len(calls) == 3
        return load(path, *args, **kwargs)

    monkeypatch.setattr(HOGMemoryDetector, "predict", predicted)
    monkeypatch.setattr(np, "load", loaded)
    original_bank = digest(reference / "bank.npy")
    out = tmp_path / "query"
    result = study.infer_restored_control(reference, cache, out)
    assert result["bank_created_this_run"] is False and result["status"] == "INFERENCE_COMPLETE"
    assert digest(reference / "bank.npy") == original_bank
    final = evaluate_category(out)
    assert final["status"] == "EVALUATED_COMPLETE"
