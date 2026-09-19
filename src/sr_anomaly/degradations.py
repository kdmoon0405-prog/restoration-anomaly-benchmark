from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass(frozen=True)
class DegradationResult:
    image: Image.Image
    parameters: dict[str, Any]
    restoration_input: Image.Image | None = None


_GAUSSIAN_RADII = (0.7, 1.2, 1.8, 2.6, 3.5)
_MOTION_SIZES = (3, 5, 7, 9, 11)
_NOISE_SIGMAS = (5.0, 10.0, 18.0, 28.0, 40.0)
_JPEG_QUALITIES = (90, 75, 60, 40, 20)
_BRIGHTNESS_FACTORS = (0.9, 0.8, 0.7, 0.6, 0.5)
_CONTRAST_FACTORS = (0.9, 0.75, 0.6, 0.45, 0.3)
_DOWNSAMPLE_FACTORS = (2, 3, 4, 5, 6)


def gaussian_blur(image: Image.Image, severity: int, seed: int = 0) -> DegradationResult:
    radius = _at_severity(_GAUSSIAN_RADII, severity)
    return DegradationResult(_rgb(image).filter(ImageFilter.GaussianBlur(radius)), {"radius": radius})


def motion_blur(image: Image.Image, severity: int, seed: int = 0) -> DegradationResult:
    size = _at_severity(_MOTION_SIZES, severity)
    array = np.asarray(_rgb(image), dtype=np.float32)
    pad = size // 2
    padded = np.pad(array, ((0, 0), (pad, pad), (0, 0)), mode="edge")
    cumulative = np.concatenate(
        (np.zeros((array.shape[0], 1, array.shape[2]), dtype=np.float32), np.cumsum(padded, axis=1)),
        axis=1,
    )
    blurred = (cumulative[:, size:] - cumulative[:, :-size]) / size
    output = Image.fromarray(np.clip(blurred, 0, 255).astype(np.uint8), "RGB")
    return DegradationResult(output, {"kernel_size": size, "angle_degrees": 0})


def gaussian_noise(image: Image.Image, severity: int, seed: int = 0) -> DegradationResult:
    sigma = _at_severity(_NOISE_SIGMAS, severity)
    array = np.asarray(_rgb(image), dtype=np.float32)
    noise = np.random.default_rng(seed).normal(0.0, sigma, array.shape)
    noisy = Image.fromarray(np.clip(array + noise, 0, 255).astype(np.uint8), "RGB")
    return DegradationResult(noisy, {"sigma": sigma})


def jpeg_compression(image: Image.Image, severity: int, seed: int = 0) -> DegradationResult:
    quality = _at_severity(_JPEG_QUALITIES, severity)
    buffer = BytesIO()
    _rgb(image).save(buffer, format="JPEG", quality=quality, optimize=False, progressive=False)
    buffer.seek(0)
    with Image.open(buffer) as decoded:
        output = decoded.convert("RGB").copy()
    return DegradationResult(output, {"quality": quality})


def brightness(image: Image.Image, severity: int, seed: int = 0) -> DegradationResult:
    factor = _at_severity(_BRIGHTNESS_FACTORS, severity)
    return DegradationResult(ImageEnhance.Brightness(_rgb(image)).enhance(factor), {"factor": factor})


def contrast(image: Image.Image, severity: int, seed: int = 0) -> DegradationResult:
    factor = _at_severity(_CONTRAST_FACTORS, severity)
    return DegradationResult(ImageEnhance.Contrast(_rgb(image)).enhance(factor), {"factor": factor})


def low_resolution(image: Image.Image, severity: int, seed: int = 0) -> DegradationResult:
    factor = _at_severity(_DOWNSAMPLE_FACTORS, severity)
    source = _rgb(image)
    reduced = (max(1, source.width // factor), max(1, source.height // factor))
    output = source.resize(reduced, Image.Resampling.BICUBIC).resize(source.size, Image.Resampling.BICUBIC)
    return DegradationResult(
        output,
        {"scale_factor": factor, "reduced_size": list(reduced)},
        source.resize(reduced, Image.Resampling.BICUBIC),
    )


DEGRADATIONS: dict[str, Callable[[Image.Image, int, int], DegradationResult]] = {
    "gaussian_blur": gaussian_blur,
    "motion_blur": motion_blur,
    "gaussian_noise": gaussian_noise,
    "jpeg_compression": jpeg_compression,
    "brightness": brightness,
    "contrast": contrast,
    "low_resolution": low_resolution,
    "downsampling": low_resolution,
}


def apply_degradation(image: Image.Image, name: str, severity: int, seed: int) -> DegradationResult:
    try:
        degradation = DEGRADATIONS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown degradation: {name}") from exc
    return degradation(image, severity, seed)


def _at_severity(values: tuple[Any, ...], severity: int) -> Any:
    if not isinstance(severity, int) or not 1 <= severity <= len(values):
        raise ValueError(f"severity must be an integer from 1 to {len(values)}")
    return values[severity - 1]


def _rgb(image: Image.Image) -> Image.Image:
    return image.convert("RGB")
