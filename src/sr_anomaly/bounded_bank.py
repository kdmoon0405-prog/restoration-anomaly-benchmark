"""Preselected uniform patch bank; CPU NumPy only, no model or FAISS dependency."""
from __future__ import annotations

import hashlib
import json
from operator import index
import os
from pathlib import Path
import platform
import random
import sys

import numpy as np

IMPLEMENTATION_ID = "uniform_global_patch_preselection_stream_v0_3"
DEFAULT_CAPACITY = 262_144
DEFAULT_CHUNK_LIMIT = 8_192


def _integer(value, name, minimum=1):
    try:
        if isinstance(value, (bool, np.bool_)):
            raise TypeError
        value = index(value)
    except TypeError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not minimum <= value <= min(sys.maxsize, np.iinfo(np.int64).max):
        raise ValueError(f"{name} is outside supported bounds")
    return value


def validate_indices(indices, total_vectors, selected_count):
    if (not isinstance(indices, np.ndarray) or indices.dtype != np.dtype('<i8')
            or indices.ndim != 1 or len(indices) != selected_count):
        raise ValueError("Expected selected_count sorted int64 indices")
    if (len(indices) == 0 or indices[0] < 0 or indices[-1] >= total_vectors
            or np.any(indices[1:] <= indices[:-1])):
        raise ValueError("Selection indices duplicated, unsorted or out of bounds")


def _plan(total_vectors, dimension=1024, capacity=DEFAULT_CAPACITY, seed=11, max_chunk_vectors=DEFAULT_CHUNK_LIMIT):
    cfg = {name: _integer(value, name, 0 if name == "seed" else 1) for name, value in {
        "total_vectors": total_vectors, "dimension": dimension, "capacity": capacity,
        "seed": seed, "max_chunk_vectors": max_chunk_vectors}.items()}
    selected = min(cfg["total_vectors"], cfg["capacity"])
    # CPython random.sample(range(N), k) avoids a population-sized list for N >> k.
    # Its near-population pool branch is also O(k), since N is then bounded by O(k).
    indices = np.asarray(sorted(random.Random(cfg["seed"]).sample(range(cfg["total_vectors"]), selected)), dtype='<i8')
    validate_indices(indices, cfg["total_vectors"], selected)
    indices.flags.writeable = False
    return cfg, indices


def selection_plan(**settings):
    """Return configuration and sorted global IDs without allocating features."""
    return _plan(**settings)


def _consume(chunks, cfg, indices, progress):
    validate_indices(indices, cfg["total_vectors"], min(cfg["total_vectors"], cfg["capacity"]))
    bank = np.empty((len(indices), cfg["dimension"]), dtype=np.float32)
    offset = stored = 0
    for chunk in chunks:
        if not isinstance(chunk, np.ndarray) or chunk.ndim != 2 or chunk.shape[1] != cfg["dimension"]:
            raise ValueError("Chunk must be a NumPy [rows, D] array")
        rows = len(chunk)
        progress["observed_vectors"] += rows
        progress["max_chunk_vectors_seen"] = max(progress["max_chunk_vectors_seen"], rows)
        if not 0 < rows <= cfg["max_chunk_vectors"]:
            raise ValueError("Empty or oversized feature chunk")
        if chunk.dtype != np.dtype(np.float32):
            raise ValueError("Feature dtype must be native float32; implicit casts forbidden")
        if offset + rows > cfg["total_vectors"]:
            raise ValueError("Feature stream exceeds expected total_vectors")
        if not np.isfinite(chunk).all():
            raise ValueError("Non-finite feature values")
        right = int(np.searchsorted(indices, offset + rows, side="left"))
        bank[stored:right] = chunk[indices[stored:right] - offset]
        offset += rows
        stored = right
        progress.update(validated_vectors=offset, stored_vectors=stored)
        del chunk  # Release before requesting the next chunk; producer buffering is outside this API.
    if offset != cfg["total_vectors"] or stored != len(indices):
        raise ValueError("Feature stream is shorter than expected total_vectors")
    return bank


def _progress():
    return {"observed_vectors": 0, "validated_vectors": 0, "stored_vectors": 0, "max_chunk_vectors_seen": 0}


def build_bank(chunks, **settings):
    cfg, indices = _plan(**settings)
    progress = _progress()
    bank = _consume(chunks, cfg, indices, progress)
    return bank, indices, progress


def file_sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def index_sha256(indices):
    return hashlib.sha256(memoryview(indices).cast('B')).hexdigest()


def _status(directory, value):
    temporary = directory / "status.json.partial"
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, directory / "status.json")


def save_bank(chunks, output, *, provenance, **settings):
    """New directory only; COMPLETE is atomic and published after payload hashes."""
    if provenance.get("input_kind") not in ("synthetic", "fit_normal_feature_stream"):
        raise ValueError("Explicit synthetic or fit_normal_feature_stream provenance required")
    cfg, indices = _plan(**settings)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    progress = _progress()
    metadata = {"status": "BUILDING", "implementation_id": IMPLEMENTATION_ID, **cfg,
                "dtype": "float32", "selected_count": len(indices), "selection_indices_sha256": index_sha256(indices),
                "algorithm": "sorted(random.Random(seed).sample(range(N), min(N,K))); CPython MT19937",
                "index_hash_encoding": "contiguous little-endian int64 bytes, no NPY header",
                "python": platform.python_version(), "numpy": np.__version__,
                "provenance": provenance, "progress": progress}
    _status(output, metadata)
    try:
        bank = _consume(chunks, cfg, indices, progress)
        for name, value in (("bank.npy", bank), ("selected_indices.npy", indices)):
            path = output / (name + ".partial")
            with path.open("xb") as handle:
                np.save(handle, value, allow_pickle=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(path, output / name)
        metadata["artifact_sha256"] = {name: file_sha256(output / name) for name in ("bank.npy", "selected_indices.npy")}
        metadata["status"] = "COMPLETE"
        _status(output, metadata)
    except BaseException as error:
        metadata.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        _status(output, metadata)
        raise
    return metadata


def load_complete_bank(directory):
    """Reject interrupted/failed/tampered artifacts; return read-only mmap arrays."""
    directory = Path(directory)
    metadata = json.loads((directory / "status.json").read_text(encoding="utf-8"))
    if metadata["status"] != "COMPLETE" or metadata["implementation_id"] != IMPLEMENTATION_ID:
        raise ValueError("Not a complete supported bank")
    for name in ("bank.npy", "selected_indices.npy"):
        if file_sha256(directory / name) != metadata["artifact_sha256"][name]:
            raise ValueError("Bank artifact checksum mismatch")
    bank = np.load(directory / "bank.npy", mmap_mode="r", allow_pickle=False)
    indices = np.load(directory / "selected_indices.npy", mmap_mode="r", allow_pickle=False)
    validate_indices(indices, metadata["total_vectors"], metadata["selected_count"])
    if (bank.dtype != np.dtype(np.float32) or bank.shape != (len(indices), metadata["dimension"])
            or metadata["selected_count"] != min(metadata["total_vectors"], metadata["capacity"])
            or metadata["progress"]["validated_vectors"] != metadata["total_vectors"]
            or metadata["progress"]["stored_vectors"] != len(indices)
            or index_sha256(indices) != metadata["selection_indices_sha256"]):
        raise ValueError("Completed bank shape/count/provenance mismatch")
    return bank, indices, metadata
