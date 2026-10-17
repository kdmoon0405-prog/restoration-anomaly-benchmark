"""Synthetic tiled plumbing only; callbacks inject features/maps, never GT."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from . import bounded_bank as bounded
from . import pcb_tiling as geometry

IMPLEMENTATION_ID = "native_tiled_stream_meanmap_maxtilescore_cpu_v0_4"
FeatureExtractor = Callable[[np.ndarray], np.ndarray]  # B,Hpatch,Wpatch,D; x fastest.
TilePredictor = Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, float]]


@dataclass(frozen=True)
class Parent:
    sample: str
    split: str
    label: int
    size_wh: tuple[int, int]


@dataclass(frozen=True)
class TilePrediction:
    sample: str
    variant: str
    tile_id: int
    box: tuple[int, int, int, int]
    anomaly_map: np.ndarray
    score: float


@dataclass
class BoardPrediction:
    anomaly_map: np.ndarray
    score: float
    coverage_min: int
    coverage_max: int


def _positive(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError("Positive integer required")
    return int(value)


def validate_parents(parents):
    parents = tuple(parents)
    if not parents or any(not isinstance(p, Parent) for p in parents):
        raise ValueError("Nonempty Parent inventory required")
    normalized = []
    for p in parents:
        if (not isinstance(p.sample, str) or not p.sample.strip() or p.split not in ("fit", "calibration", "test")
                or isinstance(p.label, (bool, np.bool_)) or not isinstance(p.label, (int, np.integer))
                or p.label not in (0, 1) or (p.split != "test" and p.label != 0)):
            raise ValueError("Invalid sample/split/label; fit and calibration must be normal")
        geometry.tile_boxes(p.size_wh)
        normalized.append(Parent(p.sample, p.split, int(p.label), tuple(map(_positive, p.size_wh))))
    parents = tuple(normalized)
    if len({p.sample for p in parents}) != len(parents):
        raise ValueError("Duplicate parent inventory; split overlap forbidden")
    if any(not any(p.split == s for p in parents) for s in ("fit", "calibration", "test")):
        raise ValueError("Disjoint nonempty fit/calibration/test inventories required")
    return parents


def _load_rgb(parent, image_loader):
    rgb = image_loader(parent)
    if (not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8
            or rgb.shape != (parent.size_wh[1], parent.size_wh[0], 3)):
        raise ValueError("Loader must return native uint8 HWC RGB matching parent dimensions")
    return rgb


def feature_chunks(parents, image_loader, extractor: FeatureExtractor, *, patch_shape, dimension,
                   batch_tiles, max_chunk_vectors=8192):
    parents = tuple(parents)  # Descriptors only, never accumulated images/features.
    py, px = map(_positive, patch_shape)
    dimension, batch_tiles = _positive(dimension), _positive(batch_tiles)
    if batch_tiles * py * px > _positive(max_chunk_vectors):
        raise ValueError("Feature batch exceeds chunk-vector limit")
    if any(p.split != "fit" or p.label != 0 for p in parents):
        raise ValueError("Only normal fit parents may produce bank features")
    buffer = []
    def extract():
        features = extractor(np.stack(buffer))
        if (not isinstance(features, np.ndarray) or features.dtype != np.float32
                or features.shape != (len(buffer), py, px, dimension)):
            raise ValueError("Extractor must return float32 [B,patch_y,patch_x,D]")
        return features.reshape(-1, dimension)
    for parent in parents:
        rgb = _load_rgb(parent, image_loader)
        for tile in geometry.extract_tiles(rgb, geometry.tile_boxes(parent.size_wh)):
            buffer.append(tile)
            if len(buffer) == batch_tiles:
                features = extract()
                buffer.clear()
                yield features
                del features
        del rgb
    if buffer:
        features = extract()
        buffer.clear()
        yield features


def assemble_board(sample, variant, size_wh, predictions: Iterable[TilePrediction]):
    boxes = geometry.tile_boxes(size_wh)
    tiles = {}
    for item in predictions:
        if item.sample != sample or item.variant != variant:
            raise ValueError("Mixed sample or variant in board")
        if (isinstance(item.tile_id, (bool, np.bool_)) or not isinstance(item.tile_id, (int, np.integer))
                or not 0 <= item.tile_id < len(boxes)):
            raise ValueError("Unknown tile ID")
        if item.tile_id in tiles:
            raise ValueError("Duplicate tile ID")
        geometry.validate_boxes(size_wh, [item.box])
        if tuple(item.box) != boxes[item.tile_id]:
            raise ValueError("Tile coordinates differ from canonical layout")
        values = item.anomaly_map
        if (not isinstance(values, np.ndarray) or values.shape != (224, 224)
                or values.dtype != np.float32 or not np.isfinite(values).all()):
            raise ValueError("Tile map must be finite float32 [224,224]")
        if isinstance(item.score, (bool, np.bool_)) or np.ndim(item.score) != 0:
            raise ValueError("Tile image score must be a finite scalar")
        score = float(item.score)
        if not np.isfinite(score):
            raise ValueError("Tile image score must be finite")
        tiles[int(item.tile_id)] = (values.copy(), score)  # Snapshot callback buffers before next call.
    if len(tiles) != len(boxes):
        raise ValueError("Missing canonical tiles")
    w, h = size_wh
    accumulator = np.zeros((h, w), dtype=np.float64)
    coverage = np.zeros((h, w), dtype=np.uint32)
    for tile_id, (x0, y0, x1, y1) in enumerate(boxes):
        accumulator[y0:y1, x0:x1] += tiles[tile_id][0]
        coverage[y0:y1, x0:x1] += 1
    if not coverage.all():
        raise ValueError("Zero-coverage pixels in board")
    np.divide(accumulator, coverage, out=accumulator)
    return BoardPrediction(accumulator.astype(np.float32), max(v[1] for v in tiles.values()),
                           int(coverage.min()), int(coverage.max()))


def _status(output, metadata):
    path = output / "status.json.partial"
    with path.open("x", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(path, output / "status.json")


def run_cpu_pipeline(parents, image_loader, extractor, predictors: dict[str, TilePredictor], output, *,
                     patch_shape, dimension, capacity, batch_tiles=2, seed=11, max_chunk_vectors=8192,
                     annotations=None, provenance):
    parents = validate_parents(parents)
    if (provenance.get("input_kind") != "synthetic" or not predictors
            or any(not isinstance(k, str) or not k.strip() for k in predictors)):
        raise ValueError("Explicit synthetic provenance and named predictors required")
    if annotations is not None:
        inventory = {p.sample: p for p in parents}
        for sample, mask in annotations.items():
            if (sample not in inventory or not isinstance(mask, np.ndarray)
                    or mask.shape != inventory[sample].size_wh[::-1] or not np.isin(mask, [0, 1]).all()):
                raise ValueError("Synthetic GT coordinate/binary validation failed")
    py, px = map(_positive, patch_shape)
    fit = tuple(p for p in parents if p.split == "fit")
    dimension, capacity = _positive(dimension), _positive(capacity)
    batch_tiles, max_chunk_vectors = _positive(batch_tiles), _positive(max_chunk_vectors)
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("Nonnegative integer seed required")
    seed = int(seed)
    count = sum(len(geometry.tile_boxes(p.size_wh))*py*px for p in fit)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    state = {"status": "BUILDING", "implementation_id": IMPLEMENTATION_ID, "geometry_id": geometry.GEOMETRY_ID,
             "parents": [asdict(p) for p in parents], "variants": list(predictors), "provenance": provenance,
             "feature_contract": {"patch_shape": [py, px], "dimension": dimension, "capacity": capacity,
                                  "batch_tiles": batch_tiles, "max_chunk_vectors": max_chunk_vectors,
                                  "expected_vectors": count, "seed": seed},
             "rows": [], "actual_pcb_bank": "NOT_CREATED", "actual_pcb_calibration": "NOT_CREATED",
             "pilot": "NOT_READY_FOR_PILOT", "calibration": "PENDING_NO_VALUES_COMPUTED"}
    _status(output, state)
    try:
        chunks = feature_chunks(fit, image_loader, extractor, patch_shape=(py, px), dimension=dimension,
                                batch_tiles=batch_tiles, max_chunk_vectors=max_chunk_vectors)
        bounded.save_bank(chunks, output / "synthetic-bank", provenance=provenance,
                          total_vectors=count, dimension=dimension, capacity=capacity, seed=seed,
                          max_chunk_vectors=max_chunk_vectors)
        bank, indices, bank_state = bounded.load_complete_bank(output / "synthetic-bank")
        before = {n: bounded.file_sha256(output / "synthetic-bank" / n) for n in ("status.json", "bank.npy", "selected_indices.npy")}
        state["bank_artifact_sha256"] = before
        state["selection_indices_sha256"] = bank_state["selection_indices_sha256"]
        state["feature_contract"]["observed_vectors"] = bank_state["progress"]["observed_vectors"]
        (output / "predictions").mkdir()
        for parent in parents:
            if parent.split == "fit":
                continue
            rgb = _load_rgb(parent, image_loader)
            boxes = geometry.tile_boxes(parent.size_wh)
            for variant, predictor in predictors.items():
                def predictions():
                    for tile_id, (tile, box) in enumerate(zip(geometry.extract_tiles(rgb, boxes), boxes, strict=True)):
                        values, score = predictor(tile, bank)
                        yield TilePrediction(parent.sample, variant, tile_id, box, values, score)
                result = assemble_board(parent.sample, variant, parent.size_wh, predictions())
                filename = f"predictions/{len(state['rows']):04d}.npy"
                with (output / filename).open("xb") as handle:
                    np.save(handle, result.anomaly_map, allow_pickle=False)
                state["rows"].append({"sample": parent.sample, "split": parent.split, "label": parent.label,
                    "variant": variant, "size_wh": list(parent.size_wh), "score": result.score,
                    "coverage_min": result.coverage_min, "coverage_max": result.coverage_max,
                    "file": filename, "sha256": bounded.file_sha256(output / filename)})
                del result
            del rgb
        after = {n: bounded.file_sha256(output / "synthetic-bank" / n) for n in before}
        if before != after:
            raise ValueError("Bank changed during calibration/test prediction")
        state.update(status="COMPLETE", synthetic_integration="PASS", bank_unchanged=True)
        _status(output, state)
    except BaseException as error:
        state.update(status="FAILED", synthetic_integration="FAIL", error=f"{type(error).__name__}: {error}")
        _status(output, state)
        raise
    return state


def iter_saved_predictions(output):
    """Read one map at a time; metadata/hash checks are not model validation."""
    output = Path(output)
    state = json.loads((output / "status.json").read_text(encoding="utf-8"))
    if state["status"] != "COMPLETE" or state["implementation_id"] != IMPLEMENTATION_ID:
        raise ValueError("Incomplete or unsupported integration artifact")
    parents = validate_parents(Parent(p["sample"], p["split"], p["label"], tuple(p["size_wh"])) for p in state["parents"])
    expected = {(p.sample, v) for p in parents if p.split != "fit" for v in state["variants"]}
    if len(state["rows"]) != len(expected) or len({(r["sample"], r["variant"]) for r in state["rows"]}) != len(expected):
        raise ValueError("Missing/duplicate saved sample/variant")
    for name, digest in state["bank_artifact_sha256"].items():
        if name not in ("status.json", "bank.npy", "selected_indices.npy") or bounded.file_sha256(output / "synthetic-bank" / name) != digest:
            raise ValueError("Saved bank provenance mismatch")
    bank, ids, bank_state = bounded.load_complete_bank(output / "synthetic-bank")
    if bank_state["selection_indices_sha256"] != state["selection_indices_sha256"] or bank_state["provenance"] != state["provenance"]:
        raise ValueError("Saved selection/source provenance mismatch")
    del bank, ids
    inventory = {p.sample: p for p in parents}
    for i, row in enumerate(state["rows"]):
        if (row["sample"], row["variant"]) not in expected or row["file"] != f"predictions/{i:04d}.npy":
            raise ValueError("Invalid saved sample/variant/path")
        p = inventory[row["sample"]]
        if row["split"] != p.split or row["label"] != p.label or tuple(row["size_wh"]) != p.size_wh:
            raise ValueError("Saved parent metadata mismatch")
        if not np.isfinite(row["score"]) or bounded.file_sha256(output / row["file"]) != row["sha256"]:
            raise ValueError("Saved score/map checksum mismatch")
        values = np.load(output / row["file"], mmap_mode="r", allow_pickle=False)
        if values.shape != p.size_wh[::-1] or values.dtype != np.float32 or not np.isfinite(values).all():
            raise ValueError("Saved map shape/dtype/value mismatch")
        yield row, values
        del values
