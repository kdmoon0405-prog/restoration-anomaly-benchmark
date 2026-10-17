"""Thin native-tile adapters. Importing this module never imports a model runtime."""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from PIL import Image

VARIANTS = ("clean", "bicubic_x4", "swinir_x4")
PATCHCORE_COMMIT = "fcaa92f124fb1ad74a7acf56726decd4b27cbcad"
SWINIR_COMMIT = "6545850fbf8df298df73d81f3e8cba638787c8bd"
SWINIR_SHA256 = "09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e"
# Local cache verified against torchvision's legacy pretrained=True / IMAGENET1K_V1 file.
BACKBONE_SHA256 = "95faca4d11227dddf8633dbb5ff6c8a9003c1aa5b8945c73834b8007b10950b8"
MEAN = (.485, .456, .406)
STD = (.229, .224, .225)


def check_rgb(rgb, *, batch=False):
    shape = (224, 224, 3)
    valid_shape = (isinstance(rgb, np.ndarray) and
                   (rgb.ndim == 4 and rgb.shape[1:] == shape and len(rgb) > 0 if batch else rgb.shape == shape))
    if not valid_shape or rgb.dtype != np.uint8:
        raise ValueError("Native uint8 RGB 224x224 tiles required; no resize/crop/padding")


def normalize_tiles(rgb, device):
    """ToTensor + ImageNet Normalize, no spatial transform."""
    check_rgb(rgb, batch=True)
    import torch
    values = torch.from_numpy(np.ascontiguousarray(rgb)).permute(0, 3, 1, 2).to(device=device, dtype=torch.float32)
    values = values / 255.
    mean = values.new_tensor(MEAN)[None, :, None, None]
    std = values.new_tensor(STD)[None, :, None, None]
    return (values - mean) / std


class PatchCoreTiles:
    def __init__(self, model, device, *, patch_shape=(28, 28), dimension=1024):
        self.model, self.device = model, device
        self.patch_shape, self.dimension = tuple(patch_shape), dimension
        self.bound = False

    def extract(self, rgb):
        import torch
        images = normalize_tiles(rgb, self.device)
        self.model.forward_modules.eval()
        with torch.inference_mode():
            flat, shapes = self.model._embed(images, detach=False, provide_patch_shapes=True)
        if tuple(shapes[0]) != self.patch_shape:
            raise ValueError(f"Patch grid differs from frozen contract: {shapes[0]}")
        values = flat.detach().cpu().numpy()
        expected = (len(rgb) * np.prod(self.patch_shape), self.dimension)
        if values.shape != expected or values.dtype != np.float32 or not np.isfinite(values).all():
            raise ValueError("Unexpected _embed count/dimension/dtype/finite values")
        return values.reshape(len(rgb), *self.patch_shape, self.dimension)

    def bind_bank(self, bank):
        if (self.bound or bank.ndim != 2 or not len(bank) or bank.shape[1] != self.dimension
                or bank.dtype != np.float32 or bank.flags.writeable):
            raise ValueError("Bind one complete read-only bounded bank exactly once")
        # Keep upstream scorer merge + CPU IndexFlatL2 semantics, including their copies.
        self.model.anomaly_scorer.fit([bank])
        self.bound = True

    def predict(self, rgb):
        if not self.bound:
            raise ValueError("No bounded bank bound")
        check_rgb(rgb)
        scores, maps = self.model.predict(normalize_tiles(rgb[None], self.device))
        values = np.asarray(maps[0])
        if values.shape != (224, 224) or values.dtype != np.float32:
            raise ValueError("Upstream tile map shape/dtype changed")
        return values, float(scores[0])

    def close(self):
        """Release owned index/scorer/model references; no claim about allocator RSS/cache."""
        model, self.model = self.model, None
        self.bound = False
        if model is not None:
            scorer = getattr(model, "anomaly_scorer", None)
            nn = getattr(scorer, "nn_method", None)
            if nn is not None:
                nn.reset_index()
            if scorer is not None and hasattr(scorer, "detection_features"):
                del scorer.detection_features


def tile_variant(rgb, variant, restorer=None):
    check_rgb(rgb)
    if variant == "clean":
        return rgb
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant: {variant}")
    low = Image.fromarray(rgb).resize((56, 56), Image.Resampling.BICUBIC)
    result = (low.resize((224, 224), Image.Resampling.BICUBIC) if variant == "bicubic_x4"
              else restorer.restore(low) if restorer is not None else None)
    if result is None or result.mode != "RGB" or result.size != (224, 224):
        raise ValueError("SwinIR restorer required; output must be RGB 224x224")
    return np.asarray(result)


def assemble_rgb(size_wh, tiles):
    """Native overlap mean once, round-to-nearest-even/clip uint8 for existing RGB metrics."""
    from .pcb_tiling import tile_boxes
    w, h = size_wh
    total = np.zeros((h, w, 3), np.float64)
    coverage = np.zeros((h, w, 1), np.uint32)
    count = 0
    for rgb, (x0, y0, x1, y1) in zip(tiles, tile_boxes(size_wh), strict=True):
        check_rgb(rgb)
        total[y0:y1, x0:x1] += rgb
        coverage[y0:y1, x0:x1] += 1
        count += 1
    if not count or not coverage.all():
        raise ValueError("RGB reconstruction has missing tiles/coverage")
    np.divide(total, coverage, out=total)
    np.rint(total, out=total)
    np.clip(total, 0, 255, out=total)
    return total.astype(np.uint8)


def create_models(root, device, backbone_checkpoint, swinir_checkpoint):
    """Explicit execution only. No pretrained loader/network download is used."""
    import torch
    from torchvision.models import wide_resnet50_2
    from .bounded_bank import file_sha256
    from .real_models import SwinIRLightweight
    root = Path(root)
    if file_sha256(backbone_checkpoint) != BACKBONE_SHA256 or file_sha256(swinir_checkpoint) != SWINIR_SHA256:
        raise ValueError("Checkpoint identity changed before model construction")
    sys.path.insert(0, str(root / "third_party/patchcore-inspection/src"))
    from patchcore import common, patchcore, sampler
    torch.manual_seed(11)
    backbone = wide_resnet50_2(weights=None)
    backbone.load_state_dict(torch.load(backbone_checkpoint, map_location="cpu", weights_only=True), strict=True)
    backbone.name = "wideresnet50"
    model = patchcore.PatchCore(torch.device(device))
    model.load(backbone=backbone, layers_to_extract_from=["layer2", "layer3"], device=torch.device(device),
               input_shape=(3, 224, 224), pretrain_embed_dimension=1024, target_embed_dimension=1024,
               patchsize=3, featuresampler=sampler.IdentitySampler(), nn_method=common.FaissNN(False, 4))
    restorer = SwinIRLightweight(root / "third_party/SwinIR", swinir_checkpoint,
                                 device=device, scale=4, tile=56, tile_overlap=0)
    return PatchCoreTiles(model, device), lambda tile, variant: tile_variant(tile, variant, restorer)
