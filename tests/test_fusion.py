import numpy as np
import pytest

from sr_anomaly.evaluation import binary_roc_auc
from sr_anomaly.fusion import (
    METHODS,
    fit_fusion_calibration,
    fuse_pair,
    fuse_test_maps,
    fuse_test_scores,
    normalize,
    quantile_threshold,
    robust_params,
    split_train_calibration,
)


def test_split_matches_hazelnut_80_20_and_is_reusable() -> None:
    train, calibration = split_train_calibration(391, 0.8, 11)
    assert len(train) == 313
    assert len(calibration) == 78
    assert set(train).isdisjoint(calibration)
    assert sorted(train + calibration) == list(range(391))
    # Same seed replays the exact same lists for every compared method.
    assert split_train_calibration(391, 0.8, 11) == (train, calibration)


def test_split_validation() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        split_train_calibration(1, 0.8, 11)
    with pytest.raises(ValueError, match="train_ratio"):
        split_train_calibration(10, 1.0, 11)
    train, calibration = split_train_calibration(10, 0.8, 11)
    assert len(train) == 8 and len(calibration) == 2


def test_robust_params_known_values() -> None:
    params = robust_params(np.array([1.0, 2.0, 3.0, 4.0]))
    assert params["median"] == pytest.approx(2.5)
    assert params["scale"] == pytest.approx(1.5)
    assert params["method"] == "iqr"
    normalized = normalize(np.array([1.0, 4.0]), params)
    assert normalized.tolist() == pytest.approx([(-1.5) / 1.5, 1.5 / 1.5])


def test_robust_params_zero_iqr_falls_back_without_nan() -> None:
    params = robust_params(np.zeros(8))
    assert params["scale"] == pytest.approx(1.0)
    assert params["method"] == "unit_fallback"
    assert normalize(np.zeros(3), params).tolist() == [0.0, 0.0, 0.0]


def test_fuse_pair_methods() -> None:
    degraded = np.array([0.0, 2.0])
    restored = np.array([1.0, 1.0])
    assert fuse_pair(degraded, restored, "degraded_only").tolist() == [0.0, 2.0]
    assert fuse_pair(degraded, restored, "restored_only").tolist() == [1.0, 1.0]
    assert fuse_pair(degraded, restored, "mean_0.5_0.5").tolist() == [0.5, 1.5]
    assert fuse_pair(degraded, restored, "max").tolist() == [1.0, 2.0]
    with pytest.raises(ValueError, match="shape"):
        fuse_pair(np.zeros(2), np.zeros(3), "max")
    with pytest.raises(ValueError, match="weight 0.5"):
        fuse_pair(degraded, restored, "mean_0.5_0.5", weight=0.7)


def test_quantile_threshold_validation() -> None:
    assert quantile_threshold(np.array([0.0, 1.0]), 0.5) == pytest.approx(0.5)
    with pytest.raises(ValueError, match="quantile"):
        quantile_threshold(np.array([0.0]), 1.0)


def test_single_variant_auroc_is_invariant_under_frozen_normalization() -> None:
    labels = np.array([0, 0, 0, 1, 1, 1])
    raw = np.array([0.1, 0.2, 0.3, 0.8, 0.9, 1.0])
    params = robust_params(np.array([0.05, 0.15, 0.25, 0.35]))
    assert binary_roc_auc(labels, normalize(raw, params)) == pytest.approx(binary_roc_auc(labels, raw))


def test_fit_and_fuse_roundtrip_preserves_method_set() -> None:
    rng = np.random.default_rng(11)
    calibration_scores_deg = rng.normal(0.0, 1.0, 40)
    calibration_scores_res = rng.normal(5.0, 2.0, 40)
    calibration_pixels_deg = rng.normal(0.0, 1.0, 400)
    calibration_pixels_res = rng.normal(5.0, 2.0, 400)
    calibration = fit_fusion_calibration(
        calibration_scores_deg, calibration_scores_res, calibration_pixels_deg, calibration_pixels_res
    )
    assert set(calibration["image_thresholds"]) == set(METHODS)
    assert set(calibration["pixel_thresholds"]) == set(METHODS)

    test_deg = np.array([0.0, 3.0])
    test_res = np.array([5.0, 11.0])
    fused = fuse_test_scores(test_deg, test_res, calibration)
    assert set(fused) == set(METHODS)
    assert fused["mean_0.5_0.5"].tolist() == pytest.approx(
        (0.5 * fused["degraded_only"] + 0.5 * fused["restored_only"]).tolist()
    )

    maps_deg = np.zeros((2, 4, 4))
    maps_res = np.ones((2, 4, 4))
    fused_maps = fuse_test_maps(maps_deg, maps_res, calibration)
    assert set(fused_maps) == set(METHODS)
    assert fused_maps["max"].shape == (2, 4, 4)
