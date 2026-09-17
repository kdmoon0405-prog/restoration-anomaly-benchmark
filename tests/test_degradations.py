import numpy as np
from PIL import Image
import pytest

from sr_anomaly.degradations import apply_degradation


NAMES = [
    "gaussian_blur",
    "motion_blur",
    "gaussian_noise",
    "jpeg_compression",
    "brightness",
    "contrast",
    "low_resolution",
]


def synthetic_image() -> Image.Image:
    y, x = np.mgrid[:32, :32]
    array = np.stack(((x * 9) % 256, (y * 7) % 256, ((x + y) * 5) % 256), axis=-1).astype(np.uint8)
    return Image.fromarray(array, "RGB")


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("severity", range(1, 6))
def test_degradation_is_deterministic(name: str, severity: int) -> None:
    first = apply_degradation(synthetic_image(), name, severity=severity, seed=123)
    second = apply_degradation(synthetic_image(), name, severity=severity, seed=123)
    assert first.image.size == (32, 32)
    assert first.image.tobytes() == second.image.tobytes()
    assert first.parameters == second.parameters


def test_gaussian_noise_seed_changes_output() -> None:
    first = apply_degradation(synthetic_image(), "gaussian_noise", 2, 1)
    second = apply_degradation(synthetic_image(), "gaussian_noise", 2, 2)
    assert first.image.tobytes() != second.image.tobytes()


def test_invalid_severity_and_name() -> None:
    with pytest.raises(ValueError, match="severity"):
        apply_degradation(synthetic_image(), "gaussian_blur", 0, 1)
    with pytest.raises(ValueError, match="Unknown degradation"):
        apply_degradation(synthetic_image(), "unknown", 1, 1)
