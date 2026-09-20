import numpy as np
import pytest

from scripts.analyze_fusion_weights import ALPHAS, analyze_predictions
from sr_anomaly.evaluation import evaluate_predictions


def _synthetic_branch_b():
    labels = np.array([0, 0, 1, 1])
    masks = np.zeros((4, 4, 4), dtype=bool)
    masks[2, 1:3, 1:3] = True
    masks[3, :2, :2] = True
    background = np.arange(16, dtype=float).reshape(4, 4) / 100
    degraded_maps = np.stack([background.copy() for _ in labels])
    restored_maps = degraded_maps.copy()
    degraded_maps[2][masks[2]] += 0.7
    degraded_maps[3][masks[3]] += 0.5
    restored_maps[2][masks[2]] += 0.8
    restored_maps[3][masks[3]] += 0.3
    degraded_scores = np.array([0.1, 0.2, 0.7, 0.9])
    restored_scores = np.array([0.2, 0.1, 0.8, 0.7])

    def prediction(scores, maps):
        return {"labels": labels.copy(), "scores": scores, "masks": masks.copy(), "maps": maps}

    predictions = {
        "degraded_only": prediction(degraded_scores, degraded_maps),
        "restored_only": prediction(restored_scores, restored_maps),
        "mean_0.5_0.5": prediction(0.5 * degraded_scores + 0.5 * restored_scores,
                                  0.5 * degraded_maps + 0.5 * restored_maps),
    }
    recorded = {name: evaluate_predictions(item["labels"], item["scores"], item["masks"], item["maps"])
                for name, item in predictions.items()}
    paths = ["hazelnut/test/good/000.png", "hazelnut/test/good/001.png",
             "hazelnut/test/crack/002.png", "hazelnut/test/cut/003.png"]
    return predictions, recorded, paths


def test_coarse_fusion_anchors_and_risk():
    predictions, recorded, paths = _synthetic_branch_b()
    rows, per_image, anchors = analyze_predictions(predictions, recorded, paths)
    assert [row["alpha"] for row in rows] == list(ALPHAS)
    assert len(per_image) == 2 * len(ALPHAS)
    assert set(anchors) == {"0.00", "0.50", "1.00"}
    assert all(check["passed"] for check in anchors.values())
    assert all(check["max_abs_map_diff"] < 1e-9 for check in anchors.values())
    assert rows[-1]["localization_regression_count_vs_bicubic"] == 0
    assert rows[-1]["minimum_delta_per_image_aupro_vs_bicubic"] == 0
    assert all("f1" not in row for row in rows)


def test_anchor_mismatch_is_rejected():
    predictions, recorded, paths = _synthetic_branch_b()
    predictions["mean_0.5_0.5"]["maps"][2, 1, 1] += 0.01
    with pytest.raises(ValueError, match="alpha=0.50 anchor mismatch"):
        analyze_predictions(predictions, recorded, paths)
