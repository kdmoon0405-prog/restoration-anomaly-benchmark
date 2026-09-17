import math

import numpy as np
from PIL import Image
import pytest

from sr_anomaly.metrics import psnr, ssim


def image(value: int, size: tuple[int, int] = (16, 16)) -> Image.Image:
    return Image.fromarray(np.full((*size, 3), value, dtype=np.uint8), "RGB")


def test_identical_images_have_expected_metrics() -> None:
    reference = image(80)
    assert math.isinf(psnr(reference, reference))
    assert ssim(reference, reference) == pytest.approx(1.0)


def test_changed_image_has_finite_metrics() -> None:
    assert math.isfinite(psnr(image(80), image(90)))
    assert 0.0 < ssim(image(80), image(90)) < 1.0


def test_metric_shape_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="same shape"):
        psnr(image(80), image(80, (8, 8)))

