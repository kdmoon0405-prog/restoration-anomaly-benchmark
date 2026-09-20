import numpy as np

from scripts.analyze_hazelnut_failures import _case_groups, _regression_type, _screening_oracle, _select_whole_maps


def test_regression_taxonomy_and_aupro_case_ranking() -> None:
    assert _regression_type(-0.1, -0.01) == "suppression"
    assert _regression_type(-0.1, 0.0) == "geometry_candidate"
    assert _regression_type(0.0, -1.0) == "improvement_or_tie"
    rows = [
        {"sample": "middle", "delta_per_image_aupro": 0.0},
        {"sample": "worst", "delta_per_image_aupro": -0.3},
        {"sample": "best", "delta_per_image_aupro": 0.2},
    ]
    groups = _case_groups(rows, 1)
    assert groups["worst"][0]["sample"] == "worst"
    assert groups["best"][0]["sample"] == "best"


def test_oracle_screening_and_whole_map_selection_keep_normals() -> None:
    rows = [
        {"index": 1, "bicubic_per_image_aupro": 0.8, "swinir_per_image_aupro": 0.6,
         "bicubic_per_image_pixel_auroc": 0.7, "swinir_per_image_pixel_auroc": 0.9},
        {"index": 2, "bicubic_per_image_aupro": 0.5, "swinir_per_image_aupro": 0.7,
         "bicubic_per_image_pixel_auroc": 0.8, "swinir_per_image_pixel_auroc": 0.8},
    ]
    screening = _screening_oracle(rows, "aupro")
    assert (screening["bicubic_wins"], screening["swinir_wins"], screening["ties"]) == (1, 1, 0)
    assert np.isclose(screening["mean_oracle"], 0.75)
    assert np.isclose(screening["headroom_vs_restored"], 0.1)
    assert _screening_oracle(rows, "pixel_auroc")["ties"] == 1

    bic = {"scores": np.array([10, 20, 30]), "maps": np.array([[[10]], [[20]], [[30]]])}
    swin = {"scores": np.array([1, 2, 3]), "maps": np.array([[[1]], [[2]], [[3]]])}
    scores, maps, bicubic_wins = _select_whole_maps(rows, bic, swin)
    assert bicubic_wins == 1
    np.testing.assert_array_equal(scores, [1, 20, 3])
    np.testing.assert_array_equal(maps[:, 0, 0], [1, 20, 3])
    np.testing.assert_array_equal(swin["scores"], [1, 2, 3])
