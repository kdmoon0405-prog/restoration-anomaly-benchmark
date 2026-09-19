from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .models import AnomalyPrediction


class PatchCoreTorchAdapter:
    name = "patchcore"

    def __init__(
        self,
        artifact: str | Path,
        device: str = "cpu",
        align_to_input: bool = True,
        trusted_local_artifact: bool = False,
    ) -> None:
        try:
            from anomalib.deploy import TorchInferencer
        except ImportError as exc:
            raise RuntimeError('PatchCore requires `anomalib[cpu]`') from exc
        artifact = Path(artifact)
        if not artifact.is_file():
            raise FileNotFoundError(f"PatchCore artifact not found: {artifact}")
        if trusted_local_artifact:
            previous = os.environ.get("TRUST_REMOTE_CODE")
            os.environ["TRUST_REMOTE_CODE"] = "1"
            try:
                self._inferencer = TorchInferencer(path=artifact, device=device)
            finally:
                if previous is None:
                    os.environ.pop("TRUST_REMOTE_CODE", None)
                else:
                    os.environ["TRUST_REMOTE_CODE"] = previous
        else:
            self._inferencer = TorchInferencer(path=artifact, device=device)
        self._align_to_input = align_to_input

    def predict(self, image: Image.Image) -> AnomalyPrediction:
        prediction = self._inferencer.predict(image.convert("RGB"))
        score = float(_numpy(prediction.pred_score).reshape(-1)[0])
        anomaly_map = np.squeeze(_numpy(prediction.anomaly_map)).astype(np.float32, copy=False)
        if anomaly_map.ndim != 2:
            raise ValueError(f"PatchCore anomaly map must be 2D after squeeze, got {anomaly_map.shape}")
        if not np.isfinite(score) or not np.isfinite(anomaly_map).all():
            raise ValueError("PatchCore returned a non-finite score or anomaly map")
        raw_size = [int(anomaly_map.shape[1]), int(anomaly_map.shape[0])]
        align_to_input = getattr(self, "_align_to_input", True)
        if align_to_input and raw_size != list(image.size):
            anomaly_map = np.asarray(
                Image.fromarray(anomaly_map, mode="F").resize(image.size, Image.Resampling.BILINEAR),
                dtype=np.float32,
            )
        return AnomalyPrediction(
            score,
            anomaly_map,
            {"raw_map_size": raw_size, "aligned_size": list(image.size) if align_to_input else raw_size},
        )


class SwinIRLightweight:
    window_size = 8

    def __init__(
        self,
        repository: str | Path,
        checkpoint: str | Path,
        device: str = "cpu",
        tile: int = 512,
        tile_overlap: int = 32,
        scale: int = 2,
    ) -> None:
        if scale not in (2, 3, 4):
            raise ValueError("Lightweight SwinIR supports x2, x3, or x4 checkpoints")
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("SwinIR requires PyTorch") from exc
        network_file = Path(repository) / "models" / "network_swinir.py"
        checkpoint = Path(checkpoint)
        if not network_file.is_file():
            raise FileNotFoundError(f"SwinIR implementation not found: {network_file}")
        if not checkpoint.is_file():
            raise FileNotFoundError(f"SwinIR checkpoint not found: {checkpoint}")
        spec = spec_from_file_location("_official_swinir_network", network_file)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load SwinIR implementation: {network_file}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        model = module.SwinIR(
            upscale=scale,
            in_chans=3,
            img_size=64,
            window_size=8,
            img_range=1.0,
            depths=[6, 6, 6, 6],
            embed_dim=60,
            num_heads=[6, 6, 6, 6],
            mlp_ratio=2,
            upsampler="pixelshuffledirect",
            resi_connection="1conv",
        )
        payload = torch.load(checkpoint, map_location=device, weights_only=True)
        model.load_state_dict(payload["params"] if "params" in payload else payload, strict=True)
        self._torch = torch
        self._model = model.eval().to(device)
        self._device = device
        self.scale = scale
        self.name = f"swinir_lightweight_x{scale}"
        self._tile = tile
        self._tile_overlap = tile_overlap

    def restore(self, image: Image.Image) -> Image.Image:
        torch = self._torch
        source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        tensor = torch.from_numpy(source).permute(2, 0, 1).unsqueeze(0).to(self._device)
        old_height, old_width = tensor.shape[-2:]
        pad_height = (-old_height) % self.window_size
        pad_width = (-old_width) % self.window_size
        if pad_height or pad_width:
            tensor = torch.nn.functional.pad(tensor, (0, pad_width, 0, pad_height), mode="reflect")
        with torch.inference_mode():
            output = self._tiled_forward(tensor)
        output = output[..., : old_height * self.scale, : old_width * self.scale]
        array = output.squeeze(0).clamp(0, 1).permute(1, 2, 0).cpu().numpy()
        return Image.fromarray(np.rint(array * 255.0).astype(np.uint8), mode="RGB")

    def _tiled_forward(self, image: Any) -> Any:
        torch = self._torch
        _, _, height, width = image.shape
        tile = min(self._tile, height, width)
        tile -= tile % self.window_size
        if tile < self.window_size or self._tile_overlap >= tile:
            raise ValueError("SwinIR tile must be a window-size multiple larger than tile overlap")
        stride = tile - self._tile_overlap
        height_starts = list(range(0, max(height - tile, 0), stride)) + [max(height - tile, 0)]
        width_starts = list(range(0, max(width - tile, 0), stride)) + [max(width - tile, 0)]
        output = torch.zeros((1, 3, height * self.scale, width * self.scale), dtype=image.dtype, device=image.device)
        weights = torch.zeros_like(output)
        for top in height_starts:
            for left in width_starts:
                patch = image[..., top : top + tile, left : left + tile]
                restored = self._model(patch)
                rows = slice(top * self.scale, (top + tile) * self.scale)
                columns = slice(left * self.scale, (left + tile) * self.scale)
                output[..., rows, columns] += restored
                weights[..., rows, columns] += 1
        return output / weights


SwinIRLightweightX2 = SwinIRLightweight


def _numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)
