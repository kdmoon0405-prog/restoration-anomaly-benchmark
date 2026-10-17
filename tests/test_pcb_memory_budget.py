"""Boundary-only probes use byte counts, never native-size allocations."""
import json

import numpy as np
import pytest

from sr_anomaly import pcb_board_analysis as board
from sr_anomaly import pcb_native_memory as memory
from sr_anomaly import pcb_tiled_runner as runner


@pytest.mark.parametrize("entry", ["board", "rehearsal"])
@pytest.mark.parametrize("live", [0, 40, 100])
def test_free_ram_and_total_cap_have_distinct_boundaries(monkeypatch, entry, live):
    required = 100
    reserve = board.RAM_RESERVE
    assert reserve == memory.RAM_RESERVE == 2 * 1024**3
    probe = runner if entry == "board" else memory
    check = board._budget if entry == "board" else memory.guard_memory
    available = required - live + reserve
    monkeypatch.setattr(probe, "available_ram", lambda: available)
    check(required, required + reserve, live_bytes=live)  # Equality passes.
    with pytest.raises(MemoryError, match="RAM cap"):
        check(required, required + reserve - 1, live_bytes=live)
    available -= 1
    with pytest.raises(MemoryError, match="available RAM"):
        check(required, None, live_bytes=live)


@pytest.mark.parametrize("entry", ["board", "rehearsal"])
@pytest.mark.parametrize("required,cap,live", [
    (-1, None, 0), (True, None, 0), (1.5, None, 0),
    (100, 0, 0), (100, True, 0), (100, 3.5, 0),
    (100, None, -1), (100, None, True), (100, None, 1.5), (100, None, 101),
])
def test_invalid_budget_inputs_rejected(monkeypatch, entry, required, cap, live):
    probe = runner if entry == "board" else memory
    monkeypatch.setattr(probe, "available_ram", lambda: 64 * 1024**3)
    check = board._budget if entry == "board" else memory.guard_memory
    with pytest.raises(ValueError):
        check(required, cap, live_bytes=live)


@pytest.mark.parametrize("available", [-1, True, 1.5])
def test_invalid_available_probe_is_not_an_authorization(available):
    with pytest.raises(ValueError):
        board._budget(100, None, available_bytes=available)


def test_numpy_byte_counts_and_native_boundary_without_allocations():
    required = 19776013920
    live = 200 * 1404 * 1070 * 9  # Existing float64 maps plus bool masks, ONE variant.
    reserve = board.RAM_RESERVE
    board._budget(np.int64(required), np.int64(required + reserve),
                  live_bytes=np.int64(live), available_bytes=required - live + reserve)
    with pytest.raises(MemoryError):
        board._budget(required, required + reserve - 1,
                      live_bytes=live, available_bytes=required + reserve)
    # Arithmetic promotes int64 before adding the reserve, rather than wrapping.
    limit = np.iinfo(np.int64).max
    with pytest.raises(MemoryError):
        board._budget(np.int64(limit), None, available_bytes=limit)


@pytest.mark.parametrize("shortfall", [0, 1])
def test_board_evaluation_counts_live_arrays_once(tmp_path, monkeypatch, shortfall):
    from scripts.check_pcb_board_pipeline import fixture, produce
    from sr_anomaly import evaluation

    monkeypatch.setattr(runner, "available_ram", lambda: 64 * 1024**3)
    produce(tmp_path)
    raw, cal, norm = tmp_path / "raw", tmp_path / "cal", tmp_path / "norm"
    board.fit_calibration(raw, cal)
    board.apply_calibration(raw, cal, norm)
    parents, _, _, gt = fixture()
    pixels = sum(p.size_wh[0] * p.size_wh[1] for p in parents if p.split == "test")
    initial = board.memory_plan(parents)["evaluation_planning_envelope_bytes"]
    total = board.memory_plan(parents, region_mask_bytes=2 * 224 * 336)["evaluation_planning_envelope_bytes"]
    live = pixels * 9
    snapshots = iter([initial + board.RAM_RESERVE, total - live + board.RAM_RESERVE - shortfall])
    monkeypatch.setattr(runner, "available_ram", lambda: next(snapshots))
    calls = []
    budget = board._budget
    def tracked(required, cap, **kwargs):
        calls.append((required, cap, kwargs.get("live_bytes", 0)))
        return budget(required, cap, **kwargs)
    monkeypatch.setattr(board, "_budget", tracked)
    metric_calls = []
    evaluator = evaluation.evaluate_predictions
    def evaluate(*args, **kwargs):
        metric_calls.append(True)
        return evaluator(*args, **kwargs)
    monkeypatch.setattr(evaluation, "evaluate_predictions", evaluate)
    output = tmp_path / "eval"
    if shortfall:
        with pytest.raises(MemoryError, match="available RAM"):
            board.evaluate_variant(raw, cal, norm, "clean", gt, output,
                                   ram_budget=total + board.RAM_RESERVE)
    else:
        board.evaluate_variant(raw, cal, norm, "clean", gt, output,
                               ram_budget=total + board.RAM_RESERVE)
    assert calls == [(initial, total + board.RAM_RESERVE, 0),
                     (total, total + board.RAM_RESERVE, live)]
    assert len(metric_calls) == (0 if shortfall else 1)
    assert json.loads((output / "status.json").read_text(encoding="utf-8"))["status"] == (
        "FAILED" if shortfall else "COMPLETE")
