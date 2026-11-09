"""CPU-only mock tests for scripts/profile_pcb_exact_batch.py pure helpers (no model, bank or dataset)."""
from collections import namedtuple
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("profile_batch", Path(__file__).resolve().parents[1] / "scripts/profile_pcb_exact_batch.py")
pb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pb)
P = namedtuple("P", "sample split label size_wh")


def brute(bank):
    def search(q):
        d = ((q[:, None, :] - bank[None]) ** 2).sum(-1)
        i = d.argmin(1)
        return d[np.arange(len(q)), i][:, None].astype(np.float32), i[:, None].astype(np.int64)
    return search


def test_fixed_plan_uses_inventory_order_and_tile_ordinals_only():
    parents = [P("fit/a", "fit", 0, (1, 1)), P("cal/b", "calibration", 0, (1, 1)), P("cal/c", "calibration", 0, (1, 1)),
               P("test/z", "test", 1, (1, 1)), P("test/y", "test", 0, (1, 1))]
    plan = pb.fixed_query_plan(parents)
    assert [(q["sample"], q["tile_id"]) for q in plan] == [("cal/b", 0), ("cal/b", 1), ("cal/b", 2), ("test/z", 0), ("test/z", 1), ("test/z", 2)]


def test_batches_and_rotation():
    assert pb.batches(6, 4) == [[0, 1, 2, 3], [4, 5]]
    assert pb.batches(6, 2) == [[0, 1], [2, 3], [4, 5]]
    assert [pb.condition_order(r) for r in range(3)] == [[1, 2, 4], [2, 4, 1], [4, 1, 2]]


def test_preflight_blocks_instead_of_forcing():
    _, ok = pb.ram_preflight(2**30, 6, 784, 1024, 262144, available=64 * 2**30)
    assert {r["status"] for r in ok} == {"PASS"}
    _, low = pb.ram_preflight(2**30, 6, 784, 1024, 262144, available=6 * 2**30)
    assert {r["status"] for r in low} == {"BLOCKED_MEMORY"}
    assert low[2]["required_bytes"] > low[0]["required_bytes"]  # scratch grows with batch


def test_schedule_is_batch_invariant_for_exact_search_and_counts_calls():
    rng = np.random.default_rng(0)
    bank = rng.normal(size=(50, 8)).astype(np.float32)
    queries = rng.normal(size=(6, 5, 8)).astype(np.float32)
    ticks = iter(range(10**6))
    outputs, calls, passes = pb.run_schedule(brute(bank), queries, clock=lambda: next(ticks))
    measured = [c for c in calls if c["phase"] == "measured"]
    assert sum(c["batch_tiles"] == 4 for c in measured) == 2 * 3 and sum(c["batch_tiles"] == 1 for c in measured) == 6 * 3
    assert [p["batch_tiles"] for p in passes if p["phase"] == "warmup"] == [1, 2, 4]
    assert [p["batch_tiles"] for p in passes if p["round"] == 1] == [2, 4, 1]

    def downstream(d):
        return float(d.max()), np.repeat(d[:, 0], 2).astype(np.float32)
    for b in (2, 4):
        assert len(outputs[b]) == 2  # deterministic repeats
        cmp = pb.compare(outputs[1], outputs[b], downstream)
        assert cmp["distance_bitwise_equal"] and cmp["nn_index_differences"] == 0 and cmp["map_max_abs_diff"] == 0


def test_compare_separates_tied_index_change_from_distance_change():
    d = np.ones((1, 3, 1), np.float32); i = np.zeros((1, 3, 1), np.int64)
    i2 = i.copy(); i2[0, 1, 0] = 7  # different neighbour at equal distance
    def downstream(x):
        return float(x.max()), x[:, 0].astype(np.float32)
    tie = pb.compare((d, i), (d, i2), downstream)
    assert tie["nn_index_differences"] == 1 and tie["nn_index_differences_distance_tied"] and tie["distance_allclose"]
    moved = pb.compare((d, i), (d + 1e-3, i2), downstream)
    assert not moved["distance_allclose"] and not moved["nn_index_differences_distance_tied"]
    assert moved["score_max_abs_diff"] == pytest.approx(1e-3, rel=1e-3)
