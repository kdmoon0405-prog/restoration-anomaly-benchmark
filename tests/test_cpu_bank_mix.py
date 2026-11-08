import numpy as np
import pytest

from sr_anomaly.analysis_io import digest, write_json
from sr_anomaly import cpu_bank_mix as study


def source(root, domain, offset):
    root.mkdir()
    np.save(root / "bank.npy", np.arange(16 * 36, dtype=np.float32).reshape(16, 36) + offset)
    np.save(root / "selected_indices.npy", np.arange(16, dtype=np.int64))
    state = dict(status="BANK_COMPLETE", bank_domain=domain, category="tiny", seed=11,
        stored_vectors=16, descriptor_dimension=36, normal_fit_count=3, split_sha256="1" * 64,
        feature_source_sha256="2" * 64, bank_sha256=digest(root / "bank.npy"),
        selected_indices_sha256=digest(root / "selected_indices.npy"))
    write_json(root / "status.json", state)
    return state


def test_fixed_capacity_exact_rows_and_determinism(tmp_path, monkeypatch):
    monkeypatch.setattr(study, "_guard", lambda *args: {})
    a, b = tmp_path / "a", tmp_path / "b"
    before_a = source(a, "bicubic_matched", 0)
    before_b = source(b, "swinir_restored", 1000)
    first, second = tmp_path / "first", tmp_path / "second"
    state = study.construct_balanced_bank(a, b, first)
    study.construct_balanced_bank(a, b, second)
    assignment = np.load(first / "domain_assignment.npy")
    values = np.load(first / "bank.npy")
    assert state["stored_vectors"] == 16 and state["bicubic_vectors"] == state["swinir_vectors"] == 8
    np.testing.assert_array_equal(values[assignment == 0], np.load(a / "bank.npy")[assignment == 0])
    np.testing.assert_array_equal(values[assignment == 1], np.load(b / "bank.npy")[assignment == 1])
    assert digest(first / "bank.npy") == digest(second / "bank.npy")
    assert digest(a / "bank.npy") == before_a["bank_sha256"] and digest(b / "bank.npy") == before_b["bank_sha256"]


def test_source_change_rejected(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    source(a, "bicubic_matched", 0)
    source(b, "swinir_restored", 1000)
    (b / "bank.npy").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        study.construct_balanced_bank(a, b, tmp_path / "out")
