from dataclasses import replace
import json

import numpy as np
import pytest

from scripts.check_tiled_cpu_integration import dummy_fixture
from sr_anomaly import bounded_bank, pcb_tiling as geometry
from sr_anomaly.tiled_cpu_pipeline import (TilePrediction, assemble_board, feature_chunks,
    iter_saved_predictions, run_cpu_pipeline, validate_parents)


def records(size=(336, 224)):
    return [TilePrediction("case", "dummy", i, box, np.full((224, 224), 2+4*i, np.float32), -10+7*i)
            for i, box in enumerate(geometry.tile_boxes(size))]


def test_overlap_mean_scores_and_input_order_are_independent_contracts():
    tiles = records()
    result = assemble_board("case", "dummy", (336, 224), tiles)
    assert np.all(result.anomaly_map[:, :112] == 2)
    assert np.all(result.anomaly_map[:, 112:224] == 4)
    assert np.all(result.anomaly_map[:, 224:] == 6)
    assert result.score == -3 and result.score != result.anomaly_map.max()
    assert result.anomaly_map.dtype == np.float32
    assert (result.coverage_min, result.coverage_max) == (1, 2)
    reverse = assemble_board("case", "dummy", (336, 224), reversed(tiles))
    np.testing.assert_array_equal(result.anomaly_map, reverse.anomaly_map)
    assert reverse.score == result.score


def test_nonsquare_corners_and_reused_prediction_buffer_are_snapshotted():
    size = (448, 336)
    buffer = np.empty((224, 224), np.float32)
    def stream():
        for i, box in enumerate(geometry.tile_boxes(size)):
            buffer.fill(i)
            yield TilePrediction("case", "dummy", i, box, buffer, 100+i)
    result = assemble_board("case", "dummy", size, stream())
    assert result.anomaly_map[0, 0] == 0 and result.anomaly_map[-1, -1] == 5
    assert result.score == 105 and result.coverage_max == 4
    expected, count = np.zeros(size[::-1]), np.zeros(size[::-1], np.uint32)
    for i, (x0, y0, x1, y1) in enumerate(geometry.tile_boxes(size)):
        expected[y0:y1, x0:x1] += i
        count[y0:y1, x0:x1] += 1
    np.testing.assert_array_equal(result.anomaly_map, (expected/count).astype(np.float32))


@pytest.mark.parametrize("kind", ["missing", "duplicate", "unknown", "bool_id", "coords", "sample", "variant",
                                  "shape", "dtype", "nan_map", "inf_map", "nan_score", "inf_score", "bool_score"])
def test_prediction_guards(kind):
    items = records()
    if kind == "missing": items.pop()
    elif kind == "duplicate": items.append(items[0])
    else:
        changes = {"unknown": {"tile_id": 99}, "bool_id": {"tile_id": True}, "coords": {"box": items[1].box},
                   "sample": {"sample": "other"}, "variant": {"variant": "other"},
                   "shape": {"anomaly_map": np.zeros((223, 224), np.float32)},
                   "dtype": {"anomaly_map": np.zeros((224, 224), np.float64)},
                   "nan_map": {"anomaly_map": np.full((224, 224), np.nan, np.float32)},
                   "inf_map": {"anomaly_map": np.full((224, 224), np.inf, np.float32)},
                   "nan_score": {"score": np.nan}, "inf_score": {"score": np.inf}, "bool_score": {"score": False}}
        items[0] = replace(items[0], **changes[kind])
    with pytest.raises(ValueError):
        assemble_board("case", "dummy", (336, 224), items)


def test_zero_coverage_layout_is_not_silently_accepted(monkeypatch):
    item = records()[0]
    monkeypatch.setattr(geometry, "tile_boxes", lambda _: (item.box,))
    with pytest.raises(ValueError, match="coverage"):
        assemble_board("case", "dummy", (336, 224), [item])


def test_feature_parent_tile_patch_order_and_batch_independence():
    parents, loader, extractor, _, _ = dummy_fixture()
    fit = tuple(p for p in parents if p.split == "fit")
    expected = np.concatenate([extractor(np.stack([tile])).reshape(-1, 4) for p in fit
                               for tile in geometry.extract_tiles(loader(p), geometry.tile_boxes(p.size_wh))])
    banks = []
    for batch in (1, 3, 8):
        loaded = []
        def traced_loader(p):
            loaded.append(p.sample)
            return loader(p)
        chunks = feature_chunks(iter(fit), traced_loader, extractor, patch_shape=(2, 2), dimension=4, batch_tiles=batch)
        bank, ids, progress = bounded_bank.build_bank(chunks, total_vectors=32, dimension=4, capacity=17)
        np.testing.assert_array_equal(bank, expected[ids])
        assert loaded == [p.sample for p in fit]
        assert progress["observed_vectors"] == 32
        banks.append(bank)
    for bank in banks[1:]: np.testing.assert_array_equal(bank, banks[0])
    with pytest.raises(ValueError, match="Only normal fit"):
        list(feature_chunks(parents, loader, extractor, patch_shape=(2, 2), dimension=4, batch_tiles=1))
    with pytest.raises(ValueError, match="limit"):
        list(feature_chunks(fit, loader, extractor, patch_shape=(2, 2), dimension=4, batch_tiles=3, max_chunk_vectors=8))
    with pytest.raises(ValueError, match="Extractor"):
        list(feature_chunks(fit, loader, lambda batch: np.zeros((len(batch), 4, 4), np.float64),
                            patch_shape=(2, 2), dimension=4, batch_tiles=1))


def run_case(out, *, annotations="original", batch=2, overrides=None):
    parents, loader, extractor, predictors, gt = dummy_fixture()
    if annotations == "changed": gt = {k: ~v for k, v in gt.items()}
    if annotations == "none": gt = None
    if overrides: predictors = overrides
    state = run_cpu_pipeline(parents, loader, extractor, predictors, out,
        patch_shape=(2, 2), dimension=4, capacity=17, batch_tiles=batch,
        annotations=gt, provenance={"input_kind": "synthetic", "test_source": "coordinate toy"})
    return state


def test_end_to_end_gt_nonuse_split_isolation_bank_immutability_and_reload(tmp_path):
    baseline = run_case(tmp_path / "baseline")
    rows = list(iter_saved_predictions(tmp_path / "baseline"))
    assert baseline["bank_unchanged"] and baseline["synthetic_integration"] == "PASS"
    assert baseline["actual_pcb_bank"] == baseline["actual_pcb_calibration"] == "NOT_CREATED"
    assert baseline["pilot"] == "NOT_READY_FOR_PILOT" and len(rows) == 6
    assert all(r[0]["split"] in ("calibration", "test") and not r[1].flags.writeable for r in rows)
    for mode, batch in (("changed", 1), ("none", 3)):
        state = run_case(tmp_path / mode, annotations=mode, batch=batch)
        assert state["selection_indices_sha256"] == baseline["selection_indices_sha256"]
        assert state["bank_artifact_sha256"]["bank.npy"] == baseline["bank_artifact_sha256"]["bank.npy"]
        other = list(iter_saved_predictions(tmp_path / mode))
        for (a, av), (b, bv) in zip(rows, other, strict=True):
            assert (a["sample"], a["variant"], a["score"], a["sha256"]) == (b["sample"], b["variant"], b["score"], b["sha256"])
            np.testing.assert_array_equal(av, bv)


def test_invalid_splits_gt_and_loader_fail_before_prediction(tmp_path):
    parents, loader, extractor, predictors, gt = dummy_fixture()
    for invalid in (parents+[parents[0]], [replace(parents[0], label=1)]+parents[1:]):
        with pytest.raises(ValueError): validate_parents(invalid)
    bad_gt = dict(gt); bad_gt[parents[-1].sample] = np.zeros((224, 224), bool)
    with pytest.raises(ValueError, match="GT coordinate"):
        run_cpu_pipeline(parents, loader, extractor, predictors, tmp_path / "gt", patch_shape=(2, 2),
                         dimension=4, capacity=17, annotations=bad_gt, provenance={"input_kind": "synthetic"})
    with pytest.raises(ValueError, match="Loader"):
        run_cpu_pipeline(parents, lambda p: np.zeros((224, 224, 3), np.uint8), extractor, predictors,
                         tmp_path / "loader", patch_shape=(2, 2), dimension=4, capacity=17,
                         provenance={"input_kind": "synthetic"})


def test_failure_and_overwrite_guards_and_bank_cannot_be_updated(tmp_path):
    out = tmp_path / "failed"
    def illegal_update(tile, bank):
        bank[0, 0] = 1
        return np.zeros((224, 224), np.float32), 0.
    with pytest.raises(ValueError): run_case(out, overrides={"bad": illegal_update})
    assert json.loads((out / "status.json").read_text())["status"] == "FAILED"
    with pytest.raises(ValueError, match="Incomplete"):
        list(iter_saved_predictions(out))
    good = tmp_path / "good"
    run_case(good)
    status_bytes = (good / "status.json").read_bytes()
    with pytest.raises(FileExistsError): run_case(good)
    assert (good / "status.json").read_bytes() == status_bytes
    with (good / "predictions/0000.npy").open("r+b") as handle:
        handle.seek(-1, 2); value = handle.read(1); handle.seek(-1, 2); handle.write(bytes([value[0] ^ 1]))
    with pytest.raises(ValueError, match="checksum"):
        list(iter_saved_predictions(good))
