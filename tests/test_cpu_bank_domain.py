from pathlib import Path

import numpy as np
from PIL import Image
import pytest

pytest.importorskip("sklearn")
from sr_anomaly.analysis_io import digest, read_json, write_json
from sr_anomaly import cpu_hog_control as hog
from sr_anomaly import cpu_restoration_control as restoration
from sr_anomaly import cpu_bank_domain as study
from sr_anomaly.bank_domain_analysis import load_run, load_settings


class FakeRestorer:
    def restore(self, low):
        return low.resize((224, 224), Image.Resampling.BICUBIC)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    root = tmp_path / "data"
    for split, defect, count in (("train", "good", 4), ("test", "good", 1), ("test", "crack", 1)):
        folder = root / "tiny" / split / defect
        folder.mkdir(parents=True)
        for i in range(count):
            y, x = np.mgrid[:64, :64]
            value = ((x * 3 + y * 2 + i * 7) % 256).astype(np.uint8)
            rgb = np.stack((value, value, value), axis=-1)
            if defect == "crack":
                rgb[25:35, 25:35] = 255
            Image.fromarray(rgb).save(folder / f"{i:03d}.png")
    gt = root / "tiny/ground_truth/crack"
    gt.mkdir(parents=True)
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[25:35, 25:35] = 255
    Image.fromarray(mask).save(gt / "000_mask.png")
    config = read_json(Path(__file__).resolve().parents[1] / "configs/cpu_hog_control.json")
    config.update(bank_capacity=32, categories=["tiny"])
    for module in (hog, restoration, study):
        monkeypatch.setattr(module, "_guard", lambda *args: {})
    monkeypatch.setattr(restoration, "available_ram", lambda: 2**40)
    reference = tmp_path / "reference"
    hog.infer_category(root, reference, config, "tiny")
    hog.evaluate_category(reference)
    repo = tmp_path / "repo/models"
    repo.mkdir(parents=True)
    (repo / "network_swinir.py").write_text("# fixture only, never imported\n")
    checkpoint = tmp_path / "checkpoint"
    checkpoint.write_bytes(b"fixture only, never loaded")
    for module in (restoration, study):
        monkeypatch.setattr(module, "CHECKPOINT_SHA256", digest(checkpoint))
    cache = tmp_path / "cache"
    restoration.cache_restoration([reference], cache, repo.parent, checkpoint,
                                  include_fit=True, model_factory=FakeRestorer)
    restored_reference = tmp_path / "restored-reference"
    restoration.infer_restored_control(reference, cache, restored_reference)
    hog.evaluate_category(restored_reference)
    return study.DomainInputs(reference, restored_reference, cache)


def test_fixed_ordinals_query_invariance_and_contract(inputs, tmp_path, monkeypatch):
    root = tmp_path / "study"
    original_bank = digest(inputs.reference / "bank.npy")
    calls = []
    predict, load = hog.HOGMemoryDetector.predict, np.load

    def predicted(self, image):
        calls.append(1)
        return predict(self, image)

    def loaded(path, *args, **kwargs):
        if Path(path).name == "bicubic_x4_predictions.npz":
            assert len(calls) == 12
        return load(path, *args, **kwargs)

    monkeypatch.setattr(hog.HOGMemoryDetector, "predict", predicted)
    monkeypatch.setattr(np, "load", loaded)
    for bank in study.NEW_BANKS:
        directory = root / bank / "bank"
        status = study.fit_domain_bank(inputs, bank, directory)
        assert status["stored_vectors"] == 32 and status["normal_fit_count"] == 3
        assert status["selected_indices_sha256"] == digest(inputs.reference / "selected_indices.npy")
        assert set(read_json(directory / "fit_rgb_receipts.json")) <= set(inputs.split["fit_paths"])
        for query in study.QUERIES:
            study.infer_domain_query(inputs, directory, query, root / bank / query)
    for bank in study.NEW_BANKS:
        for query in study.QUERIES:
            status = study.evaluate_domain_query(inputs, root / bank / query)
            assert status["status"] == "EVALUATED_COMPLETE"
    assert digest(inputs.reference / "bank.npy") == original_bank
    for query in study.QUERIES:
        with np.load(root / "bicubic_matched" / query / "query_predictions.npz") as a:
            with np.load(root / "swinir_restored" / query / "query_predictions.npz") as b:
                np.testing.assert_array_equal(a["maps"], b["maps"])
    out = tmp_path / "export"
    study.export_core_matrix(inputs, root, out, evidence_kind="synthetic_fixture")
    parsed, skipped = load_run(out, settings=load_settings(), allow_synthetic=True,
                               source_root=Path(__file__).resolve().parents[1])
    assert skipped is None and len(parsed["summary"]) == 4
    with pytest.raises(ValueError, match="Synthetic"):
        load_run(out, settings=load_settings())


def test_split_and_selection_guards(inputs):
    split = read_json(inputs.reference / "split.json")
    split["calibration_paths"].append(split["fit_paths"][0])
    write_json(inputs.reference / "split.json", split)
    with pytest.raises(ValueError, match="overlap"):
        study.DomainInputs(inputs.reference, inputs.restored_reference, inputs.cache)


def test_calibration_change_rejected(inputs, tmp_path):
    bank = tmp_path / "bank"
    study.fit_domain_bank(inputs, "bicubic_matched", bank)
    query = tmp_path / "query"
    study.infer_domain_query(inputs, bank, "bicubic_x4", query)
    (query / "calibration.json").write_text("{}")
    with pytest.raises(ValueError, match="calibration changed"):
        study.evaluate_domain_query(inputs, query)


def test_patch_ordinal_change_rejected(inputs):
    path = inputs.reference / "selected_indices.npy"
    values = np.load(path)
    np.save(path, values[::-1], allow_pickle=False)
    with pytest.raises(ValueError, match="patch ordinals"):
        study.DomainInputs(inputs.reference, inputs.restored_reference, inputs.cache)
