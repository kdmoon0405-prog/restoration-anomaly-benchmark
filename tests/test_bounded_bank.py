import gc
import hashlib
import json
import random
import weakref

import numpy as np
import pytest

from sr_anomaly import bounded_bank as b
from scripts.check_pcb_bank_budget import synthetic_stream


@pytest.mark.parametrize("n,k", [(1, 5), (5, 5), (97, 11)])
def test_preselection_streaming_matches_small_full_reference_and_chunk_sizes(n, k):
    data = np.arange(n*4, dtype=np.float32).reshape(n, 4)
    rng_state = random.getstate()
    expected_ids = np.array(sorted(random.Random(11).sample(range(n), min(n, k))), dtype='<i8')
    first = None
    for size in (1, 3, 17, 8192):
        chunks = (data[start:start+size] for start in range(0, n, size))
        bank, ids, progress = b.build_bank(chunks, total_vectors=n, dimension=4, capacity=k)
        np.testing.assert_array_equal(ids, expected_ids)
        np.testing.assert_array_equal(bank, data[expected_ids])
        assert len(ids) == min(n, k) and len(np.unique(ids)) == len(ids)
        assert progress["observed_vectors"] == progress["validated_vectors"] == n
        assert progress["stored_vectors"] == min(n, k)
        assert not ids.flags.writeable
        if first is None:
            first = bank.tobytes()
        assert bank.tobytes() == first
    assert random.getstate() == rng_state
    if n <= k:
        assert expected_ids[0] == 0 and expected_ids[-1] == n-1


@pytest.mark.parametrize("field,value", [("total_vectors", 0), ("total_vectors", True), ("total_vectors", 1.5),
                                         ("capacity", 0), ("dimension", -1), ("seed", -1),
                                         ("max_chunk_vectors", 0), ("capacity", np.bool_(True))])
def test_invalid_configuration(field, value):
    settings = {"total_vectors": 10, "dimension": 4, "capacity": 3}
    settings[field] = value
    with pytest.raises(ValueError):
        b.build_bank(iter(()), **settings)


@pytest.mark.parametrize("ids", [np.array([0, 0], dtype='<i8'), np.array([-1, 2], dtype='<i8'),
                                  np.array([0, 10], dtype='<i8'), np.array([2, 1], dtype='<i8'),
                                  np.array([0., 1.]), np.array([[0, 1]], dtype='<i8')])
def test_invalid_selection_indices(ids):
    with pytest.raises(ValueError):
        b.validate_indices(ids, 10, 2)


@pytest.mark.parametrize("kind", ["shape", "dimension", "list", "dtype", "nan", "inf", "empty", "oversized", "short", "long"])
def test_stream_failure_never_publishes_complete_bank(tmp_path, kind):
    valid = np.zeros((2, 2), dtype=np.float32)
    bad = {"shape": np.zeros(2, dtype=np.float32), "dimension": np.zeros((2, 3), dtype=np.float32),
           "list": [[0., 0.], [0., 0.]], "dtype": np.zeros((2, 2), dtype=np.float64),
           "nan": np.full((2, 2), np.nan, dtype=np.float32), "inf": np.full((2, 2), np.inf, dtype=np.float32),
           "empty": np.zeros((0, 2), dtype=np.float32), "oversized": np.zeros((3, 2), dtype=np.float32)}
    stream = [valid] if kind == "short" else [valid, valid, valid[:1]] if kind == "long" else [valid, bad[kind]]
    out = tmp_path / kind
    with pytest.raises(ValueError):
        b.save_bank(iter(stream), out, total_vectors=4, dimension=2, capacity=1, max_chunk_vectors=2,
                    provenance={"input_kind": "synthetic"})
    state = json.loads((out / "status.json").read_text())
    assert state["status"] == "FAILED"
    with pytest.raises(ValueError, match="complete"):
        b.load_complete_bank(out)


def test_nonfinite_unselected_rows_are_still_rejected():
    _, ids = b.selection_plan(total_vectors=9, capacity=1, dimension=2)
    unselected = next(i for i in range(9) if i != ids[0])
    data = np.zeros((9, 2), dtype=np.float32)
    data[unselected, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        b.build_bank(iter([data]), total_vectors=9, capacity=1, dimension=2)


def test_saved_artifact_mmap_hashes_and_overwrite_guard(tmp_path):
    out = tmp_path / "bank"
    state = b.save_bank(synthetic_stream(97, 4, 13), out, total_vectors=97, dimension=4, capacity=11,
                        provenance={"input_kind": "synthetic", "geometry_id": "NOT_APPLICABLE"})
    bank, ids, loaded = b.load_complete_bank(out)
    assert state == loaded and loaded["status"] == "COMPLETE"
    assert isinstance(bank, np.memmap) and not bank.flags.writeable
    assert b.index_sha256(ids) == hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest()
    frozen = {p.name: p.read_bytes() for p in out.iterdir()}
    with pytest.raises(FileExistsError):
        b.save_bank(iter(()), out, total_vectors=1, dimension=1, provenance={"input_kind": "synthetic"})
    assert frozen == {p.name: p.read_bytes() for p in out.iterdir()}
    del bank, ids
    with (out / "bank.npy").open("r+b") as handle:
        handle.seek(-1, 2)
        value = handle.read(1)
        handle.seek(-1, 2)
        handle.write(bytes([value[0] ^ 1]))
    with pytest.raises(ValueError, match="checksum"):
        b.load_complete_bank(out)


def test_generator_failure_and_payload_write_failure_are_not_complete(tmp_path, monkeypatch):
    def broken():
        yield np.zeros((1, 2), dtype=np.float32)
        raise RuntimeError("producer failed")
    out = tmp_path / "producer"
    with pytest.raises(RuntimeError):
        b.save_bank(broken(), out, total_vectors=2, dimension=2, provenance={"input_kind": "synthetic"})
    assert json.loads((out / "status.json").read_text())["status"] == "FAILED"
    save = np.save
    calls = 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic disk failure")
        return save(*args, **kwargs)
    monkeypatch.setattr(np, "save", fail_second)
    with pytest.raises(OSError):
        b.save_bank(synthetic_stream(2, 2, 2), tmp_path / "disk", total_vectors=2, dimension=2,
                    provenance={"input_kind": "synthetic"})
    with pytest.raises(ValueError, match="complete"):
        b.load_complete_bank(tmp_path / "disk")


def test_lazy_large_stream_releases_chunks_and_allocates_only_bounded_bank(monkeypatch):
    n, d, k = 100_003, 8, 31
    allocate = np.empty
    allocations = []
    def bounded_empty(shape, **kwargs):
        allocations.append(shape)
        assert shape == (k, d), "Dataset-sized or growing bank allocation"
        return allocate(shape, **kwargs)
    monkeypatch.setattr(np, "empty", bounded_empty)
    previous = []
    def create(start, count):
        chunk = np.arange(start, start+count, dtype=np.float32)[:, None] + np.arange(d, dtype=np.float32)[None, :]*.25
        previous[:] = [weakref.ref(chunk)]
        return chunk
    def stream():
        for start in range(0, n, 113):
            if start % (113*64) == 0:
                gc.collect()
            assert not previous or previous[0]() is None, "Previous chunk retained"
            yield create(start, min(113, n-start))
    bank, ids, progress = b.build_bank(stream(), total_vectors=n, dimension=d, capacity=k)
    np.testing.assert_array_equal(bank, ids[:, None].astype(np.float32) + np.arange(d, dtype=np.float32)[None, :]*.25)
    assert allocations == [(k, d)]
    assert progress["max_chunk_vectors_seen"] == 113


def test_building_state_is_not_loadable_before_stream_finishes(tmp_path):
    out = tmp_path / "in-progress"
    def stream():
        assert json.loads((out / "status.json").read_text())["status"] == "BUILDING"
        with pytest.raises(ValueError, match="complete"):
            b.load_complete_bank(out)
        yield np.zeros((1, 2), dtype=np.float32)
    state = b.save_bank(stream(), out, total_vectors=1, dimension=2, provenance={"input_kind": "synthetic"})
    assert state["status"] == "COMPLETE"


def test_default_production_payload_arithmetic_without_allocating_features():
    cfg, ids = b.selection_plan(total_vectors=27_132_672)
    assert len(ids) == 262_144
    assert len(ids)*cfg["dimension"]*4 == 2**30
    assert ids.nbytes == 2*2**20
    assert cfg["max_chunk_vectors"]*cfg["dimension"]*4 == 32*2**20
