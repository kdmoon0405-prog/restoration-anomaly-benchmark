"""Degradation family v1 contracts: determinism, units, split, calibration-only thresholds."""
import numpy as np
import pytest

from sr_anomaly import realistic_degradation as rd
from scripts import run_realistic_degradation as runner


def lr(value=None):
    rng = np.random.default_rng(3)
    return np.full((56, 56, 3), value, np.uint8) if value is not None else rng.integers(0, 256, (56, 56, 3), dtype=np.uint8)


def test_conditions_and_restorers_are_frozen():
    assert rd.CONDITIONS == ("none", "noise_s5", "noise_s15", "blur_s0.8", "blur_s1.6", "jpeg_q90", "jpeg_q50")
    assert rd.RESTORERS == ("bicubic_x4", "swinir_x4", "realesrnet_x4plus", "realesrgan_x4plus")
    assert len(rd.CONDITIONS) * len(rd.RESTORERS) * 2 == 56


@pytest.mark.parametrize("condition", rd.CONDITIONS)
def test_degradations_are_uint8_rgb_deterministic_and_do_not_mutate(condition):
    image = lr(); before = image.copy()
    seed = rd.sample_seed("screw", "screw/test/good/000.png", condition)
    first, second = rd.degrade(image, condition, seed), rd.degrade(image, condition, seed)
    assert first.dtype == np.uint8 and first.shape == (56, 56, 3)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(image, before)
    assert (condition == "none") == np.array_equal(first, image)


def test_seed_depends_on_sample_and_condition_not_order():
    seeds = {rd.sample_seed(c, s, k) for c in ("hazelnut", "screw") for s in ("a", "b") for k in rd.CONDITIONS}
    assert len(seeds) == 2 * 2 * 7
    assert rd.sample_seed("screw", "a", "noise_s5") == rd.sample_seed("screw", "a", "noise_s5")


def test_noise_sigma_is_in_8bit_units():
    out = rd.degrade(lr(128), "noise_s15", 7).astype(float) - 128
    assert abs(out.std() - 15) < 0.6 and abs(out.mean()) < 0.6


def test_blur_preserves_constant_and_kernel_is_normalized():
    for sigma in (0.8, 1.6):
        kernel = rd.gaussian_kernel(sigma)
        assert kernel.sum() == pytest.approx(1) and len(kernel) == 2 * int(np.ceil(3 * sigma)) + 1
    np.testing.assert_array_equal(rd.degrade(lr(77), "blur_s1.6", 0), lr(77))
    image = lr()
    assert rd.degrade(image, "blur_s1.6", 0).std() < rd.degrade(image, "blur_s0.8", 0).std() < image.std()


def test_jpeg_lower_quality_is_further_from_source():
    image = lr()
    err = {q: np.abs(rd.degrade(image, f"jpeg_q{q}", 0).astype(int) - image).mean() for q in (90, 50)}
    assert 0 < err[90] < err[50]


@pytest.mark.parametrize("n,calibration", [(391, 78), (320, 64)])
def test_split_is_fixed_disjoint_and_complete(n, calibration):
    paths = [f"c/train/good/{i:03d}.png" for i in range(n)]
    fit, cal = rd.split_train(list(reversed(paths)))
    assert (len(cal), len(fit)) == (calibration, n - calibration) and not set(fit) & set(cal) and set(fit) | set(cal) == set(paths)
    assert (fit, cal) == rd.split_train(paths)


def test_unit_thresholds_come_from_calibration_normals_only():
    rng = np.random.default_rng(0)
    cal = [{"image_score": float(v), "label": 0} for v in rng.normal(1, .1, 20)]
    test = [{"image_score": float(v), "label": int(i >= 4)} for i, v in enumerate([1, 1.1, .9, 1, 3, 4, 5, 2.5])]
    cal_maps = rng.normal(1, .1, (20, 8, 8))
    test_maps = rng.normal(1, .1, (8, 8, 8)); masks = np.zeros((8, 8, 8), bool); masks[4:, 2:4, 2:4] = True
    test_maps[masks] += 5
    metrics, params = runner._unit_metrics(cal, test, cal_maps, test_maps, masks)
    shifted, _ = runner._unit_metrics(cal, test, cal_maps, test_maps * 1, masks)
    assert params["calibration_normals"] == 20 and metrics["image_auroc"] == 1.0 and metrics["au_pro"] > .9
    assert metrics == shifted and 0 <= metrics["image_false_alarm_rate_test_normal"] <= 1
    moved = [dict(r, label=1 - r["label"]) for r in test]  # Labels never move thresholds.
    assert runner._unit_metrics(cal, moved, cal_maps, test_maps, masks)[1] == params
