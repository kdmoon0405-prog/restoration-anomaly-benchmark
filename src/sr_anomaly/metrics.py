from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import numpy as np
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio, structural_similarity


def psnr(reference: Image.Image, candidate: Image.Image) -> float:
    first, second = _arrays(reference, candidate)
    if np.array_equal(first, second):
        return float("inf")
    return float(peak_signal_noise_ratio(first, second, data_range=255))


def ssim(reference: Image.Image, candidate: Image.Image) -> float:
    first, second = _arrays(reference, candidate)
    shortest = min(first.shape[:2])
    if shortest < 3:
        raise ValueError("SSIM requires image dimensions of at least 3 pixels")
    win_size = None if shortest >= 7 else shortest if shortest % 2 else shortest - 1
    return float(structural_similarity(first, second, data_range=255, channel_axis=-1, win_size=win_size))


def compute_quality_metrics(
    reference: Image.Image,
    candidate: Image.Image,
    names: Iterable[str],
    lpips_net: str = "alex",
    lpips_device: str = "cpu",
) -> dict[str, float]:
    values: dict[str, float] = {}
    for name in names:
        if name == "psnr":
            values[name] = psnr(reference, candidate)
        elif name == "ssim":
            values[name] = ssim(reference, candidate)
        elif name == "lpips":
            values[name] = optional_lpips(reference, candidate, lpips_net, lpips_device)
        else:
            raise ValueError(f"Unknown metric: {name}")
    return values


def optional_lpips(reference: Image.Image, candidate: Image.Image, net: str = "alex", device: str = "cpu") -> float:
    first, second = _arrays(reference, candidate)
    try:
        import torch
        import lpips
    except ImportError as exc:
        raise RuntimeError("LPIPS is optional; install with `pip install -e .[lpips]`") from exc
    model = _lpips_model(net, device, lpips)
    first_tensor = torch.from_numpy(first.astype(np.float32) / 127.5 - 1.0).permute(2, 0, 1).unsqueeze(0).to(device)
    second_tensor = torch.from_numpy(second.astype(np.float32) / 127.5 - 1.0).permute(2, 0, 1).unsqueeze(0).to(device)
    with torch.no_grad():
        return float(model(first_tensor, second_tensor).item())


@lru_cache(maxsize=4)
def _lpips_model(net: str, device: str, lpips_module: object):
    return lpips_module.LPIPS(net=net).to(device).eval()


def _arrays(reference: Image.Image, candidate: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    first = np.asarray(reference.convert("RGB"), dtype=np.uint8)
    second = np.asarray(candidate.convert("RGB"), dtype=np.uint8)
    if first.shape != second.shape:
        raise ValueError(f"Metric images must have the same shape: {first.shape} != {second.shape}")
    return first, second
