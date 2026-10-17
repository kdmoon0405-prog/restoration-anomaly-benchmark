"""Single native-224 geometry draft; no model, resize, padding or GT selection."""
from __future__ import annotations

from operator import index

import numpy as np

GEOMETRY_ID = "pcb_native224_maxstride192_halfup_v0_2"
TILE = 224
MAX_STRIDE = 192


def _integer(value):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("Boolean coordinates are invalid")
    try:
        return index(value)
    except TypeError as error:
        raise ValueError("Integer dimensions/coordinates required") from error


def axis_starts(length):
    length = _integer(length)
    if length < TILE:
        raise ValueError("Source dimension below 224; no implicit resize or padding")
    span = length - TILE
    intervals = (span + MAX_STRIDE - 1) // MAX_STRIDE
    if not intervals:
        return (0,)
    # Exact rational round-half-up, independent of float/banker's rounding.
    return tuple((2 * i * span + intervals) // (2 * intervals) for i in range(intervals + 1))


def tile_boxes(size_wh):
    width, height = size_wh
    return tuple((x, y, x + TILE, y + TILE) for y in axis_starts(height) for x in axis_starts(width))


def validate_boxes(size_wh, boxes):
    width, height = map(_integer, size_wh)
    axis_starts(width)
    axis_starts(height)
    boxes = tuple(tuple(_integer(v) for v in box) for box in boxes)
    if not boxes or len(set(boxes)) != len(boxes):
        raise ValueError("Empty/duplicate tile coordinates")
    for box in boxes:
        if len(box) != 4:
            raise ValueError("Expected x0,y0,x1,y1")
        x0, y0, x1, y1 = box
        if x1 - x0 != TILE or y1 - y0 != TILE or not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError("Out-of-bounds or wrong-size tile")
    return boxes


def coverage_map(size_wh, boxes):
    boxes = validate_boxes(size_wh, boxes)
    width, height = size_wh
    coverage = np.zeros((height, width), dtype=np.uint32)
    for x0, y0, x1, y1 in boxes:
        coverage[y0:y1, x0:x1] += 1
    if not coverage.all():
        raise ValueError("Tile layout leaves uncovered source pixels")
    return coverage


def extract_tiles(array, boxes):
    array = np.asarray(array)
    if array.ndim not in (2, 3):
        raise ValueError("Expected HW or HWC array")
    boxes = validate_boxes((array.shape[1], array.shape[0]), boxes)
    for x0, y0, x1, y1 in boxes:
        yield array[y0:y1, x0:x1].copy()


def reassemble_exact(tiles, boxes, source_shape):
    """Audit raw RGB/GT/ID identity only, NOT an anomaly-map merger."""
    if len(source_shape) not in (2, 3):
        raise ValueError("Expected HW or HWC source shape")
    boxes = validate_boxes((source_shape[1], source_shape[0]), boxes)
    coverage_map((source_shape[1], source_shape[0]), boxes)
    seen = np.zeros(source_shape[:2], dtype=bool)
    output = None
    for tile, (x0, y0, x1, y1) in zip(tiles, boxes, strict=True):
        tile = np.asarray(tile)
        if tile.shape != (TILE, TILE, *source_shape[2:]):
            raise ValueError("Tile shape differs from source channels/geometry")
        if output is None:
            output = np.empty(source_shape, dtype=tile.dtype)
        if tile.dtype != output.dtype:
            raise ValueError("Mixed tile dtypes")
        region, overlap = output[y0:y1, x0:x1], seen[y0:y1, x0:x1]
        if not np.array_equal(region[overlap], tile[overlap]):
            raise ValueError("Inconsistent overlapping tile pixels")
        region[:] = tile
        seen[y0:y1, x0:x1] = True
    return output


def estimate_resources(tile_counts, test_pixels, eval_regions, region_mask_pixels, model_spec, bank_memory):
    """Arithmetic planning from saved reference only; never allocate a bank."""
    fit_reference = len(model_spec["train_paths"])
    vectors, dimension = bank_memory["ntotal"], bank_memory["dimensions"]
    if (not fit_reference or vectors % fit_reference or model_spec["sampler"] != "IdentitySampler"
            or model_spec["target_embed_dimension"] != dimension or dimension <= 0):
        raise ValueError("Reference bank is inconsistent with unchanged IdentitySampler model")
    patches = vectors // fit_reference
    embeddings = {name: count * patches for name, count in tile_counts.items()}
    bank_bytes = embeddings["fit"] * dimension * 4
    return {
        "planning_only": True, "measured_runtime_or_peak_memory": False,
        "sampler": "IdentitySampler", "coreset_reduction": "none; unchanged",
        "reference_fit_images": fit_reference, "reference_bank_vectors": vectors,
        "patches_per_224_tile": patches, "embedding_dimension": dimension, "dtype": "float32",
        "tiles": tile_counts, "embedding_vectors": embeddings,
        "embedding_bytes_by_partition": {name: count * dimension * 4 for name, count in embeddings.items()},
        "cpu_exact_index_vector_bytes": bank_bytes,
        "fit_list_plus_concatenation_vector_bytes": 2 * bank_bytes,
        "fit_features_plus_scorer_copy_plus_index_vector_bytes": 3 * bank_bytes,
        "post_fit_scorer_features_plus_index_vector_bytes": 2 * bank_bytes,
        "test_pixels": test_pixels, "test_float32_maps_one_method_bytes": test_pixels * 4,
        "test_float32_maps_three_methods_bytes": test_pixels * 4 * 3,
        "test_bool_masks_bytes": test_pixels,
        "test_float64_score_copy_bytes": test_pixels * 8,
        "one_full_length_int64_sort_or_rank_array_bytes": test_pixels * 8,
        "test_tile_float32_maps_one_method_bytes": tile_counts["test"] * TILE * TILE * 4,
        "evaluation_4connected_regions": eval_regions,
        "aupro_retained_region_bool_masks_bytes": region_mask_pixels,
        "formulas": {
            "vectors": "tiles * (saved ntotal / saved fit image count)",
            "bank": "fit_tiles * patches_per_tile * D * 4; CPU IndexFlatL2, no coreset",
            "fit_buffers": "_fit concatenation, ConcatMerger copy, IndexFlatL2.add copy can coexist; not measured RSS",
            "evaluation": "N*H*W*(4 map / 1 bool / 8 float64 or int64); regions keep one H*W bool each",
        },
        "limits": "No runtime/GPU/VRAM estimate. Includes payloads only, not backbone/activations/allocator/FAISS scratch, sorting/unique temporaries or all evaluator live buffers. Buffer fields are overlapping scenarios, NOT additive totals. Saved bank only supplies shape/config, never reused as PCB bank. New tile boundary effects and native scale are unmeasured.",
    }
