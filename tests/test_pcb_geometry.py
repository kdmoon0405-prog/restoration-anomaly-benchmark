import numpy as np
from PIL import Image
import pytest

from sr_anomaly.pcb_geometry import component_sampling_audit, geometry_metadata, readiness_status, resize_full_frame


def test_full_frame_nonsquare_quadrants_and_coordinate_roundtrip():
    rgb = np.zeros((160, 320, 3), dtype=np.uint8)
    rgb[:80, :160] = (255, 0, 0)
    rgb[:80, 160:] = (0, 255, 0)
    rgb[80:, :160] = (0, 0, 255)
    rgb[80:, 160:] = 255
    mask = np.zeros((160, 320), dtype=np.uint8)
    mask[:80, :160] = 1
    first, gt, meta = resize_full_frame(Image.fromarray(rgb), Image.fromarray(mask))
    second, second_gt, second_meta = resize_full_frame(Image.fromarray(rgb), Image.fromarray(mask))
    assert first.size == gt.size == (224, 224)
    assert first.tobytes() == second.tobytes() and gt.tobytes() == second_gt.tobytes() and meta == second_meta
    assert np.asarray(first)[30, 30].tolist() == [255, 0, 0] and np.asarray(gt)[30, 30] == 255
    assert np.asarray(first)[190, 190].tolist() == [255, 255, 255] and np.asarray(gt)[190, 190] == 0
    transform = np.array(meta["source_to_target_center_affine"])
    inverse = np.array(meta["target_to_source_center_affine"])
    np.testing.assert_allclose(inverse @ transform, np.eye(3), atol=1e-12)
    edge = np.array(meta["source_to_target_edge_affine"])
    np.testing.assert_allclose(edge @ [320, 160, 1], [224, 224, 1])
    assert meta["crop"] is None and meta["padding"] is None and not meta["aspect_ratio_preserved"]


def test_boundary_components_survive_but_tiny_unsampled_source_id_does_not():
    mask = np.zeros((448, 448), dtype=np.uint8)
    for y, x in ((0, 0), (0, 440), (440, 0), (440, 440)):
        mask[y:y+8, x:x+8] = 255
    mask[100, 100] = 255  # 2x NN downsampling selects odd source indices, not this point.
    _, target, _ = resize_full_frame(Image.new("RGB", (448, 448)), Image.fromarray(mask))
    summary, components = component_sampling_audit(Image.fromarray(mask), target)
    assert summary["source_component_count"] == 5 and summary["lost_source_components"] == 1
    assert not summary["target_empty"]
    lost = [row for row in components if not row["represented"]]
    assert lost[0]["source_area_pixels"] == 1 and lost[0]["source_bbox_xyxy"] == [100, 100, 101, 101]
    assert readiness_status([summary]) == "BLOCKED_GEOMETRY"
    assert all(np.asarray(target)[y, x] for y, x in ((0, 0), (0, 223), (223, 0), (223, 223)))


def test_original_component_identity_does_not_depend_on_output_connectivity():
    mask = np.zeros((448, 448), dtype=np.uint8)
    mask[20:22, 20:22] = 1
    mask[20:22, 24:26] = 2
    summary, rows = component_sampling_audit(Image.fromarray(mask))
    assert summary["source_component_count"] == 2
    assert [row["component_id"] for row in rows] == [1, 2]
    assert summary["lost_source_components"] == 0
    assert readiness_status([summary]) == "READY_FOR_SEPARATE_PILOT"


def test_normal_empty_mask_and_dimension_type_guards():
    rgb, gt, meta = resize_full_frame(Image.new("RGB", (301, 107)), Image.new("L", (301, 107)))
    summary, components = component_sampling_audit(Image.new("L", (301, 107)), gt)
    assert not np.asarray(gt).any() and components == [] and summary["target_empty"]
    assert resize_full_frame(Image.new("RGB", (32, 64)))[1] is None
    with pytest.raises(ValueError, match="dimensions"):
        resize_full_frame(Image.new("RGB", (32, 64)), Image.new("L", (64, 32)))
    with pytest.raises(ValueError, match="Single-channel"):
        component_sampling_audit(Image.new("RGB", (32, 32)))
    with pytest.raises(ValueError, match="Positive"):
        geometry_metadata((0, 10))
    with pytest.raises(ValueError, match="does not match"):
        component_sampling_audit(Image.new("L", (32, 32)), Image.new("L", (224, 224), 255))
    assert readiness_status([]) == "BLOCKED_GEOMETRY"
