import numpy as np
import pytest

from sr_anomaly.evaluation import binary_roc_auc, classification_metrics, pixel_metrics


def test_binary_metrics_perfect_and_inverted() -> None:
    labels = np.array([0, 0, 1, 1])
    assert binary_roc_auc(labels, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert binary_roc_auc(labels, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)
    metrics = classification_metrics(labels, np.array([0.1, 0.2, 0.8, 0.9]), threshold=0.5)
    assert metrics["image_f1"] == pytest.approx(1.0)


def test_auc_ties_and_single_class() -> None:
    assert binary_roc_auc(np.array([0, 1]), np.array([0.5, 0.5])) == pytest.approx(0.5)
    with pytest.raises(ValueError, match="both normal and anomalous"):
        binary_roc_auc(np.zeros(3), np.arange(3))


def test_perfect_pixel_metrics() -> None:
    masks = np.zeros((2, 8, 8), dtype=np.uint8)
    masks[1, 2:5, 3:6] = 1
    maps = masks.astype(np.float32)
    result = pixel_metrics(masks, maps, threshold=0.5, num_thresholds=16)
    assert result["pixel_auroc"] == pytest.approx(1.0)
    assert result["au_pro"] == pytest.approx(1.0)
    assert result["pixel_f1"] == pytest.approx(1.0)


def test_pixel_shape_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="same shape"):
        pixel_metrics(np.zeros((1, 8, 8)), np.zeros((1, 7, 8)))

