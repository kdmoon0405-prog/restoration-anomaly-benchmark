import numpy as np
import pytest

from sr_anomaly.cpu_saved_research import operating_point, spatial_profile, paired_budget_effects


def test_known_top_pixel_and_full_budget_overlap():
    scores = np.arange(16, dtype=np.float32).reshape(4, 4)
    mask = np.zeros((4, 4), dtype=bool)
    mask[3, 3] = True
    before = scores.copy()
    first, all_pixels = spatial_profile(scores, mask, [1 / 16, 1])
    assert first["gt_pixel_recall"] == 1 and first["selected_pixel_precision"] == 1
    assert first["mean_gt_region_overlap"] == 1 and first["peak_gt_distance_pixels"] == 0
    assert all_pixels["top_k"] == 16 and all_pixels["selected_pixel_precision"] == 1 / 16
    assert all_pixels["alert_component_count"] == 1
    np.testing.assert_array_equal(scores, before)


def test_four_connected_regions_and_stable_boundary_ties():
    mask = np.eye(4, dtype=bool)
    result = spatial_profile(np.ones((4, 4)), mask, [1 / 16])[0]
    assert result["gt_region_count"] == 4
    assert result["gt_region_any_hit_rate"] == 0.25
    assert result["gt_pixel_recall"] == 0.25
    assert result["boundary_tie_count"] == 16 and result["boundary_tie_crosses_budget"]
    assert result == spatial_profile(np.ones((4, 4)), mask, [1 / 16])[0]


def test_normal_gt_fields_and_distance_units():
    normal = spatial_profile(np.arange(16).reshape(4, 4), np.zeros((4, 4)), [0.1])[0]
    assert normal["gt_pixel_recall"] is None and normal["peak_gt_distance_pixels"] is None
    assert normal["top_k"] == 2 and normal["selected_pixel_precision"] == 0
    mask = np.zeros((4, 4), dtype=bool)
    mask[0, 0] = True
    result = spatial_profile(np.arange(16).reshape(4, 4), mask, [1 / 16])[0]
    assert result["peak_gt_distance_pixels"] == pytest.approx(np.sqrt(18))
    assert result["peak_gt_distance_diagonal"] == pytest.approx(0.75)


@pytest.mark.parametrize("bad", ["shape", "nan", "budget"])
def test_invalid_profile_inputs(bad):
    scores = np.ones((4, 4))
    mask = np.zeros((4, 4))
    fractions = [0.1]
    if bad == "shape":
        mask = np.zeros((3, 3))
    elif bad == "nan":
        scores[0, 0] = np.nan
    else:
        fractions = [0]
    with pytest.raises(ValueError):
        spatial_profile(scores, mask, fractions)


def test_stored_threshold_comparison_and_exact_binomial_ci():
    result = operating_point(np.array([0, 0, 1, 1]), np.array([0.5, 0.1, 0.5, 0.2]), 0.5)
    assert [result[k] for k in ("fp", "tn", "tp", "fn")] == [1, 1, 1, 1]
    assert result["normal_image_fpr"] == 0.5 and result["anomaly_image_sensitivity"] == 0.5
    assert result["normal_image_fpr_ci95_low"] < 0.5 < result["normal_image_fpr_ci95_high"]
    zero = operating_point(np.zeros(40), np.zeros(40), 1)
    assert zero["fp"] == 0 and zero["normal_image_fpr_ci95_high"] > 0.08
    assert zero["anomaly_image_sensitivity"] is None


def test_paired_effect_is_by_image_and_deterministic():
    rows = []
    for sample, shift in (("a", 0), ("b", 1)):
        mask = np.zeros((4, 4), dtype=bool)
        mask[3, 3] = True
        bicubic = np.arange(16).reshape(4, 4)
        swinir = bicubic.copy()
        if shift:
            swinir[3, 3] = -1
        for variant, values in (("bicubic_x4", bicubic), ("swinir_x4", swinir)):
            row = spatial_profile(values, mask, [1 / 16])[0]
            rows.append(dict(row, category="synthetic", sample=sample, label=1,
                             defect_type="test", variant=variant))
    settings = dict(bootstrap_seed=11, bootstrap_repeats=100)
    summary, paired = paired_budget_effects(rows, settings)
    row = next(r for r in summary if r["metric"] == "gt_pixel_recall")
    assert row["mean_delta"] == -0.5 and row["n_anomaly_images"] == 2
    assert len(paired) == 2
    assert (summary, paired) == paired_budget_effects(list(reversed(rows)), settings)
