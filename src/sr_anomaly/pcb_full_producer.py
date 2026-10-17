"""Streaming producer candidate; only injected synthetic execution is authorized."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path

import numpy as np

from . import bounded_bank as bank
from . import pcb_board_analysis as board
from . import pcb_tiling as geometry
from .pcb_tiled_models import VARIANTS, check_rgb
from .pcb_tiled_runner import safe_source
from .tiled_cpu_pipeline import TilePrediction, assemble_board, feature_chunks, validate_parents

KIND = "synthetic_streaming_producer_not_full_pilot"


def resource_plan(parents, *, patch_shape=(28, 28), dimension=1024,
                  capacity=bank.DEFAULT_CAPACITY, batch_tiles=2):
    """Array/file payload scenarios, NOT runtime/RSS or execution approval."""
    parents = validate_parents(parents)
    py, px = (bank._integer(n, "patch dimension") for n in patch_shape)
    dimension = bank._integer(dimension, "dimension")
    capacity = bank._integer(capacity, "capacity")
    batch_tiles = bank._integer(batch_tiles, "batch_tiles")
    if batch_tiles * py * px > bank.DEFAULT_CHUNK_LIMIT:
        raise ValueError("Feature batch exceeds frozen chunk limit")
    tiles = {s: sum(len(geometry.tile_boxes(p.size_wh)) for p in parents if p.split == s)
             for s in ("fit", "calibration", "test")}
    pixels = {s: sum(int(np.prod(p.size_wh)) for p in parents if p.split == s) for s in tiles}
    largest = max(int(np.prod(p.size_wh)) for p in parents)
    max_tiles = max(len(geometry.tile_boxes(p.size_wh)) for p in parents)
    n = tiles["fit"] * py * px
    k = min(n, capacity)
    bank_bytes, indices = k * dimension * 4, k * 8
    chunk = batch_tiles * py * px * dimension * 4
    rgb_spool = 3 * pixels["test"] + 3 * tiles["test"] * 224 * 224 * 3
    raw_maps = 3 * (pixels["calibration"] + pixels["test"]) * 4
    normalized = 3 * pixels["test"] * 8
    # assemble_board snapshots every map for ONE board, then allocates its mean/coverage.
    predict = largest * (3 + 8 + 4 + 4) + max_tiles * 224 * 224 * 4 + 2 * 224 * 224 * 3
    return {"estimated_not_measured": True, "tiles": tiles, "pixels": pixels,
            "fit_vectors": n, "bank_bytes": bank_bytes, "selected_indices_bytes": indices,
            "feature_chunk_bytes": chunk, "raw_map_files_bytes": raw_maps,
            "test_reference_rgb_files_bytes": 3 * pixels["test"],
            "test_variant_tile_rgb_files_bytes": rgb_spool - 3 * pixels["test"],
            "rgb_spool_files_bytes": rgb_spool, "normalized_test_files_bytes": normalized,
            "disk_payload_before_cleanup_bytes": bank_bytes + indices + raw_maps + normalized + rgb_spool,
            "disk_payload_after_rgb_cleanup_bytes": bank_bytes + indices + raw_maps + normalized,
            "producer_bank_build_visible_bytes": 2 * bank_bytes + indices + chunk + 3 * largest,
            "producer_prediction_visible_bytes": 3 * bank_bytes + indices + predict,
            "quality_tile_load_extra_bytes": max_tiles * 224 * 224 * 3,
            "postprocessing": board.memory_plan(parents),
            "native_peak_validated": False, "full_pilot_approved": False,
            "excluded": ["model/activations/VRAM", "FAISS scratch", "Python/selection overhead",
                         "NPY headers/JSON/logs", "page cache", "OS/runtime reserve",
                         "library sort/quantile workspaces beyond existing envelopes",
                         "actual GT region masks: add frozen region payload before native evaluation"],
            "lifecycle": "producer exits before calibration/normalization/quality/evaluation; variants evaluated separately"}


def _save(directory, name, values):
    path = safe_source(directory, name)
    with path.open("xb") as stream:
        np.save(stream, values, allow_pickle=False)
    return {"file": name, "sha256": bank.file_sha256(path),
            "shape": list(values.shape), "dtype": str(values.dtype)}


def _rgb(parent, loader, state):
    values = loader(parent)
    if (not isinstance(values, np.ndarray) or values.dtype != np.uint8
            or values.shape != (*parent.size_wh[::-1], 3)):
        raise ValueError("Native uint8 RGB and parent shape required")
    digest = hashlib.sha256(np.ascontiguousarray(values)).hexdigest()
    state["input_rgb"][parent.sample] = {"decoded_rgb_sha256": digest,
        "shape": list(values.shape), "dtype": "uint8"}
    return values


def produce(parents, loader, factory, output, *, provenance, patch_shape=(28, 28),
            dimension=1024, capacity=bank.DEFAULT_CAPACITY, batch_tiles=2, expected_index_sha=None):
    """Inject adapter/transform with the existing real adapter interface; fake inputs ONLY.

    There is deliberately no real-model factory/default or full-execution option here.
    RGB spool is ephemeral, lossless uint8, and used without another transform call.
    """
    if provenance.get("input_kind") != "synthetic":
        raise RuntimeError("Full production execution blocked before model construction; synthetic only")
    parents = validate_parents(parents)
    plan = resource_plan(parents, patch_shape=patch_shape, dimension=dimension,
                         capacity=capacity, batch_tiles=batch_tiles)
    board._budget(max(plan["producer_bank_build_visible_bytes"], plan["producer_prediction_visible_bytes"]), None)
    state = {"kind": KIND, "scope": "synthetic-producer-not-full-pilot", "provenance": provenance,
             "parents": [asdict(p) for p in parents], "geometry_id": geometry.GEOMETRY_ID,
             "variants": list(VARIANTS), "rows": [], "rgb_rows": [], "reference_rows": [], "input_rgb": {},
             "calibration": "NOT_CREATED_RAW_MAPS_ONLY", "thresholds": None, "metrics": None,
             "actual_pcb_bank": "NOT_CREATED", "actual_pcb_calibration": "NOT_CREATED",
             "full_pilot_approved": False, "checkpoints": None, "model_kind": "injected_synthetic_adapter",
             "transform_calls": {v: 0 for v in VARIANTS}, "adapter_closed": False,
             "feature_contract": {"patch_shape": list(patch_shape), "dimension": dimension,
                                  "capacity": capacity, "batch_tiles": batch_tiles,
                                  "max_chunk_vectors": bank.DEFAULT_CHUNK_LIMIT, "seed": 11},
             "resource_plan": plan}
    output = board._new_output(output, state, disk_bytes=plan["disk_payload_before_cleanup_bytes"])
    adapter = transform = values = indices = None
    try:
        try:
            # Check frozen IDs before invoking even the injected factory.
            _, selected = bank.selection_plan(total_vectors=plan["fit_vectors"], dimension=dimension,
                                             capacity=capacity, seed=11)
            index_sha = bank.index_sha256(selected)
            del selected
            if expected_index_sha is not None and expected_index_sha != index_sha:
                raise ValueError("Selection-index SHA mismatch before factory/extraction")
            adapter, transform = factory()
            fit = tuple(p for p in parents if p.split == "fit")
            chunks = feature_chunks(fit, lambda p: _rgb(p, loader, state), adapter.extract,
                                    patch_shape=patch_shape, dimension=dimension, batch_tiles=batch_tiles)
            bank.save_bank(chunks, output / "bank", provenance=provenance,
                total_vectors=plan["fit_vectors"], dimension=dimension, capacity=capacity, seed=11,
                max_chunk_vectors=bank.DEFAULT_CHUNK_LIMIT)
            del chunks
            values, indices, metadata = bank.load_complete_bank(output / "bank")
            hashes = {n: bank.file_sha256(output / "bank" / n)
                      for n in ("status.json", "bank.npy", "selected_indices.npy")}
            adapter.bind_bank(values)
            (output / "predictions").mkdir()
            (output / "rgb").mkdir()
            for parent in parents:
                if parent.split == "fit":
                    continue
                rgb = _rgb(parent, loader, state)
                boxes = geometry.tile_boxes(parent.size_wh)
                if parent.split == "test":
                    name = f"rgb/reference-{len(state['reference_rows']):04d}.npy"
                    state["reference_rows"].append(dict(_save(output, name, rgb), sample=parent.sample))
                for variant in VARIANTS:
                    def predictions():
                        spool = None
                        try:
                            if parent.split == "test":
                                name = f"rgb/tiles-{len(state['rgb_rows']):04d}.npy"
                                spool = np.lib.format.open_memmap(output / name, mode="w+", dtype=np.uint8,
                                                                 shape=(len(boxes), 224, 224, 3))
                            for i, (tile, box) in enumerate(zip(geometry.extract_tiles(rgb, boxes), boxes, strict=True)):
                                prepared = np.array(transform(tile, variant), copy=True)
                                state["transform_calls"][variant] += 1
                                check_rgb(prepared)
                                if variant == "clean" and not np.array_equal(prepared, tile):
                                    raise ValueError("Clean variant must preserve original tile RGB")
                                if spool is not None:
                                    spool[i] = prepared
                                anomaly_map, score = adapter.predict(prepared)
                                if spool is not None and not np.array_equal(prepared, spool[i]):
                                    raise ValueError("Predictor mutated the shared produced RGB")
                                yield TilePrediction(parent.sample, variant, i, box, anomaly_map, score)
                            if spool is not None:
                                spool.flush()
                                state["rgb_rows"].append({"sample": parent.sample, "variant": variant,
                                    "file": name, "sha256": bank.file_sha256(output / name),
                                    "shape": list(spool.shape), "dtype": "uint8",
                                    "boxes": [list(b) for b in boxes]})
                        finally:
                            if spool is not None:
                                spool._mmap.close()
                    stream = predictions()
                    try:
                        result = assemble_board(parent.sample, variant, parent.size_wh, stream)
                    finally:
                        stream.close()  # Close a partial RGB mmap even if map validation fails.
                        del stream
                    name = f"predictions/{len(state['rows']):04d}.npy"
                    state["rows"].append(dict(_save(output, name, result.anomaly_map),
                        sample=parent.sample, split=parent.split, label=parent.label, variant=variant,
                        size_wh=list(parent.size_wh), score=result.score))
                    del result
                del rgb
            if hashes != {n: bank.file_sha256(output / "bank" / n) for n in hashes}:
                raise ValueError("Shared clean-fit bank changed during prediction")
            state.update(bank_unchanged=True, bank_artifact_sha256=hashes,
                         feature_counts=metadata["progress"], selection_indices_sha256=index_sha)
        finally:
            if adapter is not None:
                adapter.close()
                state["adapter_closed"] = True
            adapter = transform = values = indices = None
        state["status"] = "COMPLETE"
        bank._status(output, state)
    except BaseException as error:
        board._fail(output, state, error)
        raise
    return state


class RGBSpool:
    """Checksummed native reference and canonical produced tiles, never a restorer."""
    def __init__(self, raw):
        self.raw = Path(raw)
        self.state, parents = board.load_raw_run(raw)
        if (self.state.get("kind") != KIND or self.state["provenance"].get("input_kind") != "synthetic"
                or self.state.get("geometry_id") != geometry.GEOMETRY_ID):
            raise ValueError("Wrong synthetic producer/geometry")
        test = [p for p in parents if p.split == "test"]
        expected_ref = [p.sample for p in test]
        if [r["sample"] for r in self.state["reference_rows"]] != expected_ref:
            raise ValueError("RGB reference inventory mismatch")
        expected_tiles = [(p.sample, v) for p in test for v in VARIANTS]
        if [(r["sample"], r["variant"]) for r in self.state["rgb_rows"]] != expected_tiles:
            raise ValueError("RGB tile inventory mismatch")
        self.parents = {p.sample: p for p in test}
        self.references, self.variants = {}, {}
        for i, row in enumerate(self.state["reference_rows"]):
            p = self.parents[row["sample"]]
            if (row["file"] != f"rgb/reference-{i:04d}.npy" or row["shape"] != [*p.size_wh[::-1], 3]
                    or row["dtype"] != "uint8"):
                raise ValueError("RGB reference shape/dtype/path mismatch")
            self.references[p.sample] = row
        for i, row in enumerate(self.state["rgb_rows"]):
            p = self.parents[row["sample"]]
            boxes = [list(b) for b in geometry.tile_boxes(p.size_wh)]
            if (row["file"] != f"rgb/tiles-{i:04d}.npy" or row["boxes"] != boxes
                    or row["shape"] != [len(boxes), 224, 224, 3] or row["dtype"] != "uint8"):
                raise ValueError("RGB tile order/shape/dtype/path mismatch")
            self.variants[p.sample, row["variant"]] = row

    def _array(self, row):
        path = safe_source(self.raw, row["file"])
        if bank.file_sha256(path) != row["sha256"]:
            raise ValueError("RGB checksum mismatch")
        # Only ONE board/variant's tile tensor lives here; its payload is in resource_plan.
        values = np.load(path, allow_pickle=False)
        if list(values.shape) != row["shape"] or values.dtype != np.uint8:
            raise ValueError("RGB payload shape/dtype mismatch")
        return values

    def reference(self, parent):
        if self.parents.get(parent.sample) != parent:
            raise ValueError("RGB requested outside exact test inventory")
        return self._array(self.references[parent.sample])

    def tiles(self, parent, variant):
        if self.parents.get(parent.sample) != parent or variant not in VARIANTS:
            raise ValueError("RGB requested outside exact test/variant inventory")
        yield from self._array(self.variants[parent.sample, variant])
