"""Realistic-LR degradation family v1: one extra degradation on the frozen x4 LR, then restoration.

Protocol: docs/REALISTIC_DEGRADATION_PROTOCOL.md (frozen before any test inference).
All degradations act on 56x56 RGB uint8 LR (0..255 units) and return RGB uint8.
"""
from __future__ import annotations

from hashlib import sha256
import io
from importlib.util import module_from_spec, spec_from_file_location
import logging
from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image

FAMILY = "realistic_lr_degradation_v1"
CONDITIONS = ("none", "noise_s5", "noise_s15", "blur_s0.8", "blur_s1.6", "jpeg_q90", "jpeg_q50")
RESTORERS = ("bicubic_x4", "swinir_x4", "realesrnet_x4plus", "realesrgan_x4plus")
CALIBRATION_FRACTION = 0.2
SPLIT_SEED = 11
REALESRGAN_COMMIT = "a4abfb2979a7bbff3f69f58f58ae324608821e27"
# Official xinntao/Real-ESRGAN release assets (size 67,040,989 B each per GitHub API; the publisher gives no digest,
# so these SHA-256 values were computed at download on 2026-10-31 and are pinned from now on).
CHECKPOINTS = {
    "realesrnet_x4plus": ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth",
                          "a820b9bde89a874d7599d545567308ce6c128fc8754a53208eda016d40aa81df"),
    "realesrgan_x4plus": ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
                          "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"),
}


def sample_seed(category: str, sample: str, condition: str) -> int:
    """Deterministic per-sample/condition seed; independent of processing order."""
    digest = sha256(f"{FAMILY}|seed{SPLIT_SEED}|{category}|{sample}|{condition}".encode()).digest()
    return int.from_bytes(digest[:8], "little")


def _check(lr: np.ndarray) -> None:
    if not isinstance(lr, np.ndarray) or lr.dtype != np.uint8 or lr.ndim != 3 or lr.shape[2] != 3:
        raise ValueError("RGB uint8 LR required")


def _to_uint8(values: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)  # rint = round half to even.


def gaussian_kernel(sigma: float) -> np.ndarray:
    radius = int(np.ceil(3 * sigma))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    return kernel / kernel.sum()


def gaussian_blur(lr: np.ndarray, sigma: float) -> np.ndarray:
    """Separable float64 Gaussian, radius ceil(3 sigma), reflect-101 border (numpy 'reflect')."""
    kernel = gaussian_kernel(sigma)
    radius = len(kernel) // 2
    values = lr.astype(np.float64)
    for axis in (0, 1):
        pad = [(0, 0)] * 3
        pad[axis] = (radius, radius)
        padded = np.pad(values, pad, mode="reflect")
        values = sum(kernel[i] * np.take(padded, np.arange(i, i + lr.shape[axis]), axis=axis) for i in range(len(kernel)))
    return _to_uint8(values)


def jpeg(lr: np.ndarray, quality: int) -> np.ndarray:
    """Pillow/libjpeg baseline JPEG, default 4:2:0 chroma subsampling, decoded back to RGB."""
    buffer = io.BytesIO()
    Image.fromarray(lr, "RGB").save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8).copy()


def degrade(lr: np.ndarray, condition: str, seed: int) -> np.ndarray:
    _check(lr)
    if condition == "none":
        return lr.copy()
    kind, value = condition.split("_")
    if kind == "noise":
        rng = np.random.default_rng(seed)
        return _to_uint8(lr.astype(np.float64) + rng.normal(0.0, float(value[1:]), lr.shape))
    if kind == "blur":
        return gaussian_blur(lr, float(value[1:]))
    if kind == "jpeg":
        return jpeg(lr, int(value[1:]))
    raise ValueError(f"Unknown condition: {condition}")


def split_train(paths: list[str]) -> tuple[list[str], list[str]]:
    """Fixed fit/calibration split of train/good: seed 11 permutation, first 20% -> calibration."""
    ordered = sorted(paths)
    if len(set(ordered)) != len(ordered) or not ordered:
        raise ValueError("Unique nonempty train paths required")
    order = np.random.default_rng(SPLIT_SEED).permutation(len(ordered))
    count = int(round(CALIBRATION_FRACTION * len(ordered)))
    calibration = sorted(ordered[i] for i in order[:count])
    fit = sorted(ordered[i] for i in order[count:])
    return fit, calibration


def _official_rrdbnet(basicsr_repository: Path):
    """Exec pinned BasicSR rrdbnet_arch/arch_util source; stub only registry/logger/DCN imports (unused by RRDBNet)."""
    name = "_official_basicsr_rrdbnet"
    if name in sys.modules:
        return sys.modules[name]
    stubs = {}
    if "basicsr" not in sys.modules:
        registry = types.SimpleNamespace(register=lambda *a, **k: (lambda obj: obj))
        stubs = {"basicsr": types.ModuleType("basicsr"), "basicsr.utils": types.ModuleType("basicsr.utils"),
                 "basicsr.utils.registry": types.ModuleType("basicsr.utils.registry"),
                 "basicsr.ops": types.ModuleType("basicsr.ops"), "basicsr.ops.dcn": types.ModuleType("basicsr.ops.dcn")}
        stubs["basicsr.utils.registry"].ARCH_REGISTRY = registry
        stubs["basicsr.utils"].get_root_logger = lambda *a, **k: logging.getLogger("basicsr")
        stubs["basicsr.ops.dcn"].ModulatedDeformConvPack = type("ModulatedDeformConvPack", (), {})
        stubs["basicsr.ops.dcn"].modulated_deform_conv = None
        sys.modules.update(stubs)
    try:
        package = types.ModuleType(name + "_pkg")
        package.__path__ = [str(basicsr_repository / "basicsr" / "archs")]
        sys.modules[package.__name__] = package
        for module_name in ("arch_util", "rrdbnet_arch"):
            spec = spec_from_file_location(f"{package.__name__}.{module_name}",
                                           basicsr_repository / "basicsr" / "archs" / f"{module_name}.py")
            module = module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        sys.modules[name] = module
        return module
    finally:
        for key in stubs:
            sys.modules.pop(key, None)


class RealESRGANX4:
    """Official Real-ESRGAN x4plus inference semantics (RGB float [0,1], clamp, round), fp32, no tiling/pre-pad."""

    scale = 4

    def __init__(self, basicsr_repository, checkpoint, name, device="cpu"):
        import torch
        module = _official_rrdbnet(Path(basicsr_repository))
        model = module.RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        key = "params_ema" if "params_ema" in payload else "params"
        model.load_state_dict(payload[key], strict=True)
        self._torch, self._device, self.name, self.state_key = torch, device, name, key
        self._model = model.eval().to(device)

    def restore(self, image: Image.Image) -> Image.Image:
        source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        tensor = self._torch.from_numpy(source).permute(2, 0, 1).unsqueeze(0).to(self._device)
        with self._torch.inference_mode():
            output = self._model(tensor)
        array = output.squeeze(0).float().clamp(0, 1).permute(1, 2, 0).cpu().numpy()
        if array.shape[:2] != (image.height * 4, image.width * 4):
            raise ValueError("Real-ESRGAN output size differs from x4")
        return Image.fromarray(np.rint(array * 255.0).astype(np.uint8), mode="RGB")
