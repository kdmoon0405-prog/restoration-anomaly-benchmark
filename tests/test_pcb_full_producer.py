from dataclasses import replace
import gc
import json
from pathlib import Path
import subprocess
import weakref

import numpy as np
import pytest

from scripts import check_pcb_full_producer as checker
from scripts.check_pcb_board_pipeline import FakeAdapter, fixture
from sr_anomaly import bounded_bank as bank
from sr_anomaly import pcb_board_analysis as board
from sr_anomaly import pcb_full_producer as producer
from sr_anomaly import pcb_tiled_runner as runner
from sr_anomaly.pcb_tiled_models import VARIANTS, assemble_rgb
from sr_anomaly.pcb_tiling import tile_boxes, extract_tiles
from sr_anomaly.tiled_cpu_pipeline import TilePrediction, assemble_board, feature_chunks

ROOT = Path(__file__).resolve().parents[1]


def make_raw(output, *, parents=None, batch_tiles=2, fail=False):
    inventory, rgb, transform, _ = fixture()
    counts = {"factory": 0, "bind": 0, "transform": 0, "close": 0}
    refs = []
    class Adapter(FakeAdapter):
        def bind_bank(self, values):
            counts["bind"] += 1
            super().bind_bank(values)
            refs.append(weakref.ref(self.model.anomaly_scorer.detection_features))
        def predict(self, tile):
            if fail:
                raise RuntimeError("injected worker prediction failure")
            return super().predict(tile)
        def close(self):
            counts["close"] += 1
            super().close()
    def factory():
        counts["factory"] += 1
        adapter = Adapter()
        refs.extend((weakref.ref(adapter), weakref.ref(adapter.model),
                     weakref.ref(adapter.model.anomaly_scorer.nn_method.search_index)))
        def apply(tile, variant):
            counts["transform"] += 1
            return transform(tile, variant)
        return adapter, apply
    result = producer.produce(inventory if parents is None else parents, rgb, factory, output,
        provenance={"input_kind": "synthetic"}, patch_shape=(2, 2), dimension=4,
        capacity=7, batch_tiles=batch_tiles)
    gc.collect()
    assert counts["close"] == 1 and all(ref() is None for ref in refs)
    return result, counts


def test_shared_bank_stream_reference_rgb_reuse_and_quality(tmp_path):
    raw = tmp_path / "raw"
    state, counts = make_raw(raw)
    parents, rgb, transform, _ = fixture()
    assert state["scope"] != "full-pilot-raw" and state["actual_pcb_bank"] == "NOT_CREATED"
    assert state["metrics"] is None and state["thresholds"] is None and state["adapter_closed"]
    assert counts["factory"] == counts["bind"] == 1
    assert counts["transform"] == sum(state["transform_calls"].values())
    extractor = FakeAdapter()
    fit = [p for p in parents if p.split == "fit"]
    chunks = feature_chunks(fit, rgb, extractor.extract, patch_shape=(2, 2), dimension=4, batch_tiles=3)
    reference, ids, progress = bank.build_bank(chunks, total_vectors=state["resource_plan"]["fit_vectors"],
                                             dimension=4, capacity=7, seed=11)
    stored, selected, _ = bank.load_complete_bank(raw / "bank")
    np.testing.assert_array_equal(stored, reference)
    np.testing.assert_array_equal(selected, ids)
    assert state["feature_counts"] == dict(progress, max_chunk_vectors_seen=8)
    extractor.close()
    spool = producer.RGBSpool(raw)
    for p in parents:
        if p.split == "test":
            np.testing.assert_array_equal(spool.reference(p), rgb(p))
        if p.split == "fit":
            continue
        for v in VARIANTS:
            predictions = []
            expected_tiles = []
            for i, (tile, box) in enumerate(zip(extract_tiles(rgb(p), tile_boxes(p.size_wh)), tile_boxes(p.size_wh), strict=True)):
                tile = transform(tile, v)  # Independent fake reference, not SR/model inference.
                expected_tiles.append(tile)
                predictions.append(TilePrediction(p.sample, v, i, box, tile[..., 0].astype(np.float32) / 255.,
                                                  float(tile[0, 0, 1]) + 100.))
            expected = assemble_board(p.sample, v, p.size_wh, predictions)
            row = next(r for r in state["rows"] if (r["sample"], r["variant"]) == (p.sample, v))
            np.testing.assert_array_equal(board._map(raw, row), expected.anomaly_map)
            assert row["score"] == expected.score
            if p.split == "test":
                actual = list(spool.tiles(p, v))
                np.testing.assert_array_equal(actual, expected_tiles)
                np.testing.assert_array_equal(assemble_rgb(p.size_wh, actual), assemble_rgb(p.size_wh, expected_tiles))
    before = counts.copy()
    quality = board.quality_report(parents, spool.reference, spool.tiles, tmp_path / "quality",
                                   provenance={"input_kind": "synthetic"})
    assert counts == before  # No transform/model callback reachable from quality.
    assert len(quality["rows"]) == 6 and quality["summary"]["clean"]["mean_psnr"] == "Infinity"
    with pytest.raises(ValueError, match="test inventory"):
        spool.reference(parents[0])


def test_batch_order_labels_and_no_gt_or_calibration_leak(tmp_path, monkeypatch):
    parents = fixture()[0]
    flipped = [replace(p, label=1-p.label) if p.split == "test" else p for p in parents]
    a, _ = make_raw(tmp_path / "a", batch_tiles=1)
    b, _ = make_raw(tmp_path / "b", parents=flipped, batch_tiles=3)
    assert a["selection_indices_sha256"] == b["selection_indices_sha256"]
    assert a["bank_artifact_sha256"]["bank.npy"] == b["bank_artifact_sha256"]["bank.npy"]
    assert [(r["score"], r["sha256"]) for r in a["rows"]] == [(r["score"], r["sha256"]) for r in b["rows"]]
    original = board._map
    def only_calibration(directory, row, **kwargs):
        assert row["split"] == "calibration"
        return original(directory, row, **kwargs)
    monkeypatch.setattr(board, "_map", only_calibration)
    board.fit_calibration(tmp_path / "a", tmp_path / "cal-a")
    board.fit_calibration(tmp_path / "b", tmp_path / "cal-b")
    assert board.load_calibration(tmp_path / "cal-a", tmp_path / "a")[1] == board.load_calibration(tmp_path / "cal-b", tmp_path / "b")[1]


@pytest.mark.parametrize("mutation", ["incomplete", "split", "order", "shape", "checksum", "missing"])
def test_producer_and_spool_artifact_guards(tmp_path, mutation):
    raw = tmp_path / "raw"
    state, _ = make_raw(raw)
    if mutation == "incomplete":
        state["status"] = "BUILDING"
    elif mutation == "split":
        state["rows"][0]["split"] = "test"
    elif mutation == "order":
        state["rgb_rows"][0]["boxes"].reverse()
    elif mutation == "shape":
        state["reference_rows"][0]["shape"][0] += 1
    elif mutation == "checksum":
        (raw / state["rgb_rows"][0]["file"]).write_bytes(b"changed")
    else:
        (raw / state["rgb_rows"][0]["file"]).unlink()
    (raw / "status.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises((ValueError, FileNotFoundError)):
        spool = producer.RGBSpool(raw)
        list(spool.tiles(fixture()[0][-2], VARIANTS[0]))


def test_failure_cleanup_overwrite_and_full_execution_block(tmp_path, monkeypatch):
    closed = []
    class Failing(FakeAdapter):
        def predict(self, _):
            raise RuntimeError("injected failure")
        def close(self):
            super().close()
            closed.append(self.model is None)
    parents, rgb, transform, _ = fixture()
    with pytest.raises(RuntimeError, match="injected"):
        producer.produce(parents, rgb, lambda: (Failing(), transform), tmp_path / "failed",
            provenance={"input_kind": "synthetic"}, patch_shape=(2, 2), dimension=4, capacity=7)
    assert closed == [True]
    assert json.loads((tmp_path / "failed/status.json").read_text(encoding="utf-8"))["status"] == "FAILED"
    with pytest.raises(ValueError, match="Incomplete"):
        board.load_raw_run(tmp_path / "failed")
    with pytest.raises(FileExistsError):
        make_raw(tmp_path / "failed")
    def forbidden(*args):
        pytest.fail("real model construction reached")
    with pytest.raises(RuntimeError, match="before model construction"):
        producer.produce(parents, rgb, forbidden, tmp_path / "full", provenance={"input_kind": "fit_normal_feature_stream"})
    monkeypatch.setattr(runner, "create_models", forbidden)
    with pytest.raises(RuntimeError, match="before model construction"):
        runner.execute_smoke({"status": "PREFLIGHT_PASS", "blockers": [], "scope": "full-pilot"}, ROOT, None, tmp_path / "full")
    assert not (tmp_path / "full").exists()


def test_metadata_only_native_resource_plan_and_resource_guard(tmp_path, monkeypatch):
    native, _, _ = runner.load_inventory(ROOT / runner.GEOMETRY)
    plan = producer.resource_plan(native)
    assert plan["tiles"] == {"fit": 34608, "calibration": 8640, "test": 9600}
    assert plan["fit_vectors"] == 27132672 and plan["bank_bytes"] == 1024**3
    assert plan["rgb_spool_files_bytes"] == 200*1070*1404*3 + 3*9600*224*224*3
    assert plan["disk_payload_before_cleanup_bytes"] - plan["disk_payload_after_rgb_cleanup_bytes"] == plan["rgb_spool_files_bytes"]
    assert not plan["native_peak_validated"] and not plan["full_pilot_approved"]
    monkeypatch.setattr(runner, "available_ram", lambda: 1)
    with pytest.raises(MemoryError, match="BLOCKED_MEMORY"):
        make_raw(tmp_path / "no-ram")
    assert not (tmp_path / "no-ram").exists()


def test_disk_index_and_partial_map_failure_guards(tmp_path, monkeypatch):
    parents, rgb, transform, _ = fixture()
    calls = []
    def factory():
        calls.append("factory")
        return FakeAdapter(), transform
    with pytest.raises(ValueError, match="before factory"):
        producer.produce(parents, rgb, factory, tmp_path / "wrong-id", provenance={"input_kind": "synthetic"},
                         expected_index_sha="wrong", patch_shape=(2, 2), dimension=4, capacity=7)
    assert not calls
    original = board.shutil.disk_usage
    monkeypatch.setattr(board.shutil, "disk_usage", lambda p: original(p)._replace(free=0))
    with pytest.raises(OSError, match="disk"):
        make_raw(tmp_path / "no-disk")
    assert not (tmp_path / "no-disk").exists()
    monkeypatch.undo()
    mappings = []
    original_open = np.lib.format.open_memmap
    def tracked_open(*args, **kwargs):
        values = original_open(*args, **kwargs)
        if kwargs.get("mode") == "w+":
            mappings.append(values._mmap)  # Do not retain/format a NumPy array whose mapping is closed.
        return values
    monkeypatch.setattr(np.lib.format, "open_memmap", tracked_open)
    class BadMap(FakeAdapter):
        calls = 0
        def predict(self, tile):
            self.calls += 1
            values, score = super().predict(tile)
            return (values.astype(np.float64) if self.calls == 13 else values), score
    with pytest.raises(ValueError, match="Tile map"):
        producer.produce(parents, rgb, lambda: (BadMap(), transform), tmp_path / "bad-map",
            provenance={"input_kind": "synthetic"}, patch_shape=(2, 2), dimension=4, capacity=7)
    assert mappings and all(handle.closed for handle in mappings)
    assert json.loads((tmp_path / "bad-map/status.json").read_text(encoding="utf-8"))["status"] == "FAILED"


def test_sequential_process_end_to_end_completion_and_tamper(tmp_path):
    # ROOT contains code/references; unique ignored output, no native RGB/GT read.
    run_id = "pytest-producer-" + tmp_path.parent.name[-12:] + "-" + tmp_path.name
    state, output = checker.run(ROOT, run_id)
    protocol = json.loads((output / "PROTOCOL.json").read_text(encoding="utf-8"))
    assert protocol["phase_ram_cap_bytes"] == 3 * 1024**3
    assert protocol["ram_reserve_bytes"] == 2 * 1024**3
    assert protocol["cap_semantics"] == "total_phase_envelope_plus_reserve"
    assert len(state["workers"]) == 7 and state["rgb_spool_removed"]
    assert state["all_workers_exited_before_next_stage"] and not state["full_pilot_approved"]
    produced = json.loads((output / "stages/produce-all.json").read_text(encoding="utf-8"))
    assert produced["owned_fake_model_index_features_released"]
    assert produced["call_counts"]["factory"] == produced["call_counts"]["bind_bank"] == 1
    assert json.loads((output / "stages/quality-all.json").read_text(encoding="utf-8"))["transform_calls_this_stage"] == 0
    assert checker.load_completed(output)["status"] == "SYNTHETIC_INTEGRATION_PASS_NOT_FULL_APPROVAL"
    with pytest.raises(FileExistsError):
        checker.run(ROOT, run_id)
    (output / state["workers"][0]["file"]).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        checker.load_completed(output)


@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_orchestrator_worker_failure_and_incomplete_guard(tmp_path, monkeypatch, failure):
    run_id = "pytest-failed-" + failure + "-" + tmp_path.parent.name[-12:] + "-" + tmp_path.name
    original_run = subprocess.run
    def fail(command, **kwargs):
        if command[0] == "git":
            return original_run(command, **kwargs)
        if failure == "exit" and command[command.index("--worker") + 1] == "produce":
            return original_run(command, **kwargs)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        return subprocess.CompletedProcess(command, 1, "", "injected worker error")
    monkeypatch.setattr(checker.subprocess, "run", fail)
    with pytest.raises((RuntimeError, subprocess.TimeoutExpired)):
        checker.run(ROOT, run_id)
    output = ROOT / "outputs/pcb-full-producer" / run_id
    assert json.loads((output / "status.json").read_text(encoding="utf-8"))["status"] == "FAILED"
    assert list((output / "logs").glob("*.txt"))
    if failure == "exit":
        assert (output / "raw/rgb").is_dir()  # Completed producer workspace retained on later failure.
    with pytest.raises(ValueError, match="Incomplete"):
        checker.load_completed(output)
