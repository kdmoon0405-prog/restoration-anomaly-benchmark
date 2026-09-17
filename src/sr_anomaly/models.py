from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np
from PIL import Image


@runtime_checkable
class RestorationModel(Protocol):
    name: str

    def restore(self, image: Image.Image) -> Image.Image: ...


@dataclass(frozen=True)
class AnomalyPrediction:
    image_score: float | None = None
    pixel_map: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AnomalyDetector(Protocol):
    name: str

    def predict(self, image: Image.Image) -> AnomalyPrediction: ...


class IdentityRestoration:
    name = "identity"

    def restore(self, image: Image.Image) -> Image.Image:
        return image.copy()


class NoOpAnomalyDetector:
    name = "noop"

    def predict(self, image: Image.Image) -> AnomalyPrediction:
        return AnomalyPrediction(metadata={"status": "not_computed"})


def build_restoration(config: dict[str, Any] | None) -> RestorationModel | None:
    if not config or config.get("name", "none") in {"none", None}:
        return None
    if config.get("name") == "identity":
        return IdentityRestoration()
    raise ValueError(f"Unknown restoration adapter: {config.get('name')}")


def build_anomaly_detector(config: dict[str, Any] | None) -> AnomalyDetector:
    if not config or config.get("name", "noop") == "noop":
        return NoOpAnomalyDetector()
    raise ValueError(f"Unknown anomaly detector adapter: {config.get('name')}")

