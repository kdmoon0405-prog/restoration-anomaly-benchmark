import numpy as np
import pytest

from scripts.analyze_map_gating_feasibility import analyze, select_candidate, validate_predictions
from sr_anomaly.evaluation import evaluate_predictions
from sr_anomaly.fusion import METHODS, fuse_pair
from sr_anomaly.map_gating import gated_maps


def test_two_fixed_gates_boundaries_and_no_gt_input():
    degraded = np.array([[[1., 2., 3., 4.]]])
    restored = np.array([[[0., 1., 2., 5.]]])
    result = gated_maps(degraded, restored, 1., 1.)
    np.testing.assert_array_equal(result["candidate_1"], [[[0., 2., 3., 5.]]])
    np.testing.assert_array_equal(result["candidate_2"], [[[0., 2., 2., 5.]]])
    for maps in gated_maps(restored, restored, 1., 1.).values():
        np.testing.assert_array_equal(maps, restored)
    for maps in gated_maps(degraded, restored, 10., 1.).values():
        np.testing.assert_array_equal(maps, restored)
    np.testing.assert_array_equal(degraded, [[[1., 2., 3., 4.]]])
    with pytest.raises(ValueError, match="matching"):
        gated_maps(degraded, restored[:, :, :2], 1., 1.)
    with pytest.raises(ValueError, match="finite"):
        gated_maps(degraded * np.nan, restored, 1., 1.)
    with pytest.raises(ValueError, match="finite"):
        gated_maps(degraded, restored, np.inf, 1.)


def test_saved_pair_anchor_and_normal_mask_guards():
    labels = np.array([0, 1])
    masks = np.zeros((2, 3, 3), dtype=bool)
    masks[1, 1, 1] = True
    degraded = np.arange(18.).reshape(2, 3, 3)
    restored = degraded / 2
    predictions = {name: {"labels": labels.copy(), "masks": masks.copy(),
                          "scores": fuse_pair(np.array([1., 2.]), np.array([0., 1.]), name),
                          "maps": fuse_pair(degraded, restored, name)} for name in METHODS}
    paths = ["hazelnut/test/good/000.png", "hazelnut/test/crack/000.png"]
    validate_predictions(predictions, paths)
    evaluations = {name: evaluate_predictions(labels, item["scores"], masks, item["maps"])
                   for name, item in predictions.items()}
    rows, per_image, maps = analyze(predictions, paths, evaluations, 2., 2.)
    assert len(rows) == 6 and len(per_image) == 12
    assert all(row["per_image_aupro"] is None for row in per_image if row["label"] == 0)
    for row in rows[-2:]:
        assert row["candidate_pixel_f1"] is None
        assert row["image_auroc"] == evaluations["restored_only"]["classification"]["image_auroc"]
    np.testing.assert_array_equal(maps["candidate_1"], gated_maps(degraded, restored, 2., 2.)["candidate_1"])
    predictions["max"]["maps"][1, 0, 0] += 1
    with pytest.raises(ValueError, match="anchor parity"):
        validate_predictions(predictions, paths)
    predictions["max"]["maps"][1, 0, 0] -= 1
    predictions["restored_only"]["masks"][0, 0, 0] = True
    with pytest.raises(ValueError, match="Normal test"):
        validate_predictions(predictions, paths)


def test_selection_is_primary_only_with_fixed_tie_rule():
    rows = [{"method": name, "pooled_au_pro": value} for name, value in
            (("restored_only", .8), ("max", .79), ("candidate_1", .8), ("candidate_2", .79))]
    assert select_candidate(rows) is None
    rows[2]["pooled_au_pro"] = rows[3]["pooled_au_pro"] = .81
    assert select_candidate(rows) == "candidate_1"
    rows[3]["pooled_au_pro"] = .82
    assert select_candidate(rows) == "candidate_2"
