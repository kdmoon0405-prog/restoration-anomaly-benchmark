import json

import numpy as np
from PIL import Image
import pytest

from sr_anomaly.pcb_tiling import (axis_starts, coverage_map, estimate_resources, extract_tiles,
                                   reassemble_exact, tile_boxes, validate_boxes)
from scripts.prepare_pcb_geometry import audit as resize_audit
from scripts.prepare_pcb_tiling import audit
from scripts.render_pcb_tiling_review import render_review
from test_prepare_pcb_geometry import make_official_fixture


@pytest.mark.parametrize("length", [224, 225, 416, 417, 511, 1070, 1404])
def test_axis_rounding_coverage_and_determinism(length):
    starts = axis_starts(length)
    assert starts == axis_starts(length)
    assert len(starts) == (length-224+191)//192+1
    assert starts[0] == 0 and starts[-1] == length-224
    assert len(set(starts)) == len(starts)
    assert all(0 < b-a <= 192 for a, b in zip(starts, starts[1:]))
    assert coverage_map((length, 224), tile_boxes((length, 224))).min() >= 1
    assert axis_starts(511) == (0, 144, 287)  # 143.5 rounds upward, not to even.


def test_nonsquare_rgb_gt_ids_exact_including_tile_boundaries_and_one_pixel():
    y, x = np.indices((337, 511))
    rgb = np.stack((x % 256, y % 256, (x+y) % 256), axis=-1).astype(np.uint8)
    mask = np.zeros((337, 511), dtype=np.uint8)
    mask[0, 0] = mask[-1, -1] = 1
    mask[223:226, 223:226] = 2
    mask[100, 100] = 3
    boxes = tile_boxes((511, 337))
    assert len(boxes) == 6
    for source in (rgb, mask, np.zeros_like(mask)):
        first, second = list(extract_tiles(source, boxes)), list(extract_tiles(source, boxes))
        for a, b, (x0, y0, x1, y1) in zip(first, second, boxes, strict=True):
            np.testing.assert_array_equal(a, source[y0:y1, x0:x1])
            np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(reassemble_exact(first, boxes, source.shape), source)


def test_invalid_coordinates_missing_tiles_overlap_and_small_input_guards():
    for length in (223, 0, -1, 224.5, True):
        with pytest.raises(ValueError):
            axis_starts(length)
    b = tile_boxes((225, 224))
    with pytest.raises(ValueError, match="duplicate"):
        validate_boxes((225, 224), [b[0], b[0]])
    for invalid in [(-1, 0, 223, 224), (0, 0, 225, 224), (0, 0, 224), (False, 0, 224, 224)]:
        with pytest.raises(ValueError):
            validate_boxes((225, 224), [invalid])
    with pytest.raises(ValueError, match="uncovered"):
        coverage_map((225, 224), [b[0]])
    source = np.zeros((224, 225), dtype=np.uint8)
    tiles = list(extract_tiles(source, b))
    tiles[1][0, 0] = 1
    with pytest.raises(ValueError, match="overlapping"):
        reassemble_exact(tiles, b, source.shape)
    with pytest.raises(ValueError):
        reassemble_exact([], b, source.shape)
    with pytest.raises(ValueError, match="shape"):
        reassemble_exact([np.zeros((224, 224, 3))]*2, b, source.shape)


def test_resource_payload_arithmetic_is_not_model_execution():
    assert len(tile_boxes((1404, 1070))) == 48
    counts = {"fit": 721*48, "calibration": 180*48, "test": 200*48}
    spec = {"train_paths": ["normal"]*313, "sampler": "IdentitySampler", "target_embed_dimension": 1024}
    result = estimate_resources(counts, 200*1404*1070, 324, 324*1404*1070,
                                spec, {"ntotal": 313*784, "dimensions": 1024})
    assert result["embedding_vectors"]["fit"] == 27_132_672
    assert result["cpu_exact_index_vector_bytes"] == 27_132_672*1024*4
    assert result["fit_features_plus_scorer_copy_plus_index_vector_bytes"] == 3*27_132_672*1024*4
    assert result["test_float32_maps_one_method_bytes"] == 200*1404*1070*4
    assert result["aupro_retained_region_bool_masks_bytes"] == 324*1404*1070
    assert result["planning_only"] and not result["measured_runtime_or_peak_memory"]
    with pytest.raises(ValueError, match="inconsistent"):
        estimate_resources(counts, 1, 1, 1, {**spec, "sampler": "Other"}, {"ntotal": 313*784, "dimensions": 1024})


def test_complete_synthetic_audit_reuses_frozen_inputs_and_rejects_overwrite(tmp_path):
    data, reference, _ = make_official_fixture(tmp_path)
    prior = tmp_path / "resize"
    resize_audit(data, prior, reference)
    frozen = {p: p.read_bytes() for p in prior.rglob("*") if p.is_file()}
    profile = tmp_path / "profile"
    profile.mkdir()
    spec = {"train_paths": ["normal"]*4, "sampler": "IdentitySampler", "target_embed_dimension": 1024}
    (profile / "PROTOCOL.json").write_text(json.dumps({"model_spec": spec}))
    (profile / "summary.json").write_text(json.dumps({"bank_memory": {"ntotal": 4*784, "dimensions": 1024}}))
    out = tmp_path / "tiling"
    result = audit(data, out, prior, reference, profile)
    assert result["geometry_status"] == "GEOMETRY_IDENTITY_PASS"
    assert result["pilot_status"] == "NOT_READY_FOR_PILOT"
    assert result["rgb_exact_images"] == result["gt_exact_images"] == 8
    assert result["source_components_8connected"] == 3 and result["lost_components"] == 0
    assert result["historical_lost_ids_recovered_exactly"] == result["historical_lost_components"] == 1
    manifest = json.loads((out / "MANIFEST.json").read_text())
    assert manifest["all_input_hashes_match_previous"] and not manifest["partition_overlap"]
    assert (out / "figures/tiling_overview.png").is_file()
    assert (out / "figures/component_reassembly.png").is_file()
    reviewed = render_review(out, data, prior)
    assert (reviewed / "figures/tiling_overview.png").is_file()
    with pytest.raises(FileExistsError):
        render_review(out, data, prior)
    assert all(p.read_bytes() == content for p, content in frozen.items())
    with pytest.raises(FileExistsError):
        audit(data, out, prior, reference, profile)
    image = next(data.glob("pcb2/000.png"))
    Image.new("RGB", (448, 224), "red").save(image)
    with pytest.raises(ValueError, match="Source inputs changed"):
        audit(data, tmp_path / "changed", prior, reference, profile)
