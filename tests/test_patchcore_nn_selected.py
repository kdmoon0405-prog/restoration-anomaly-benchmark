from __future__ import annotations

from hashlib import sha256
import json

import numpy as np
import pytest

from scripts.analyze_patchcore_nn_selected import SOURCE_COMMIT, SELECTED, _check_sources, distance_region_stats, mask_occupancy


def test_fixed_nine_cases_and_continuous_occupancy() -> None:
    assert len(SELECTED) == len({sample for _, sample in SELECTED}) == 9
    assert [sum(subtype == kind for subtype, _ in SELECTED) for kind in
            ("geometry_candidate", "suppression", "success_control")] == [3, 3, 3]

    mask = np.array([[1, 0, 0, 0], [1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]], dtype=bool)
    weights = mask_occupancy(mask, (2, 2))
    np.testing.assert_array_equal(weights, [[0.75, 0], [0, 0]])
    values = distance_region_stats(np.array([[8, 2], [2, 2]]), weights)
    assert values["d_defect"] == 8
    assert values["d_background"] == pytest.approx((0.25 * 8 + 3 * 2) / 3.25)
    assert values["feature_gap"] == pytest.approx(values["d_defect"] - values["d_background"])

    with pytest.raises(ValueError, match="divisible"):
        mask_occupancy(mask, (3, 2))
    with pytest.raises(ValueError, match="both defect and background"):
        distance_region_stats(np.ones((2, 2)), np.zeros((2, 2)))


def test_bank_and_checkpoint_checksums_guard_selected_run(tmp_path) -> None:
    run_dir, model_dir = tmp_path / "run", tmp_path / "model"
    run_dir.mkdir()
    model_dir.mkdir()
    bank = model_dir / "nnscorer_search_index.faiss"
    params = model_dir / "patchcore_params.pkl"
    checkpoint = tmp_path / "swinir.pth"
    for path in (bank, params, checkpoint):
        path.write_bytes(path.name.encode())
    digest = lambda path: sha256(path.read_bytes()).hexdigest()
    spec = {"source_commit": SOURCE_COMMIT, "category": "hazelnut", "seed": 11,
            "train_paths": [f"train/{i}.png" for i in range(391)], "backbone": "wideresnet50",
            "layers": ["layer2", "layer3"], "resize": 256, "center_crop": 224,
            "pretrain_embed_dimension": 1024, "target_embed_dimension": 1024,
            "patchsize": 3, "sampler": "IdentitySampler", "nearest_neighbor": "FaissNN(cpu)"}
    test_paths = [path for _, path in SELECTED] + [f"hazelnut/test/good/{i:03}.png" for i in range(101)]
    (model_dir / "metadata.json").write_text(json.dumps({"spec": spec, "artifact_sha256": {
        bank.name: digest(bank), params.name: digest(params)}}), encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps({"model_spec": spec, "restoration": {
        "checkpoint_sha256": digest(checkpoint)}, "test_paths": test_paths, "nn_stats_enabled": False}), encoding="utf-8")
    assert _check_sources(run_dir, model_dir, checkpoint)[1] == test_paths
    wrong_spec = {**spec, "patchsize": 5}
    (model_dir / "metadata.json").write_text(json.dumps({"spec": wrong_spec, "artifact_sha256": {
        bank.name: digest(bank), params.name: digest(params)}}), encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps({"model_spec": wrong_spec, "restoration": {
        "checkpoint_sha256": digest(checkpoint)}, "test_paths": test_paths, "nn_stats_enabled": False}), encoding="utf-8")
    with pytest.raises(ValueError, match="pinned setting"):
        _check_sources(run_dir, model_dir, checkpoint)
    (model_dir / "metadata.json").write_text(json.dumps({"spec": spec, "artifact_sha256": {
        bank.name: digest(bank), params.name: digest(params)}}), encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps({"model_spec": spec, "restoration": {
        "checkpoint_sha256": digest(checkpoint)}, "test_paths": test_paths, "nn_stats_enabled": False}), encoding="utf-8")
    bank.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        _check_sources(run_dir, model_dir, checkpoint)
