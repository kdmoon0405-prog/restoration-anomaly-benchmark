"""Realistic-LR noise family v2: v1 LR Gaussian noise repeated over explicit noise seeds.

Unchanged from v1 (src/sr_anomaly/realistic_degradation.py): canonical 224 crop, BasicSR MATLAB x0.25 LR,
noise added to the 56x56 RGB uint8 LR in 0..255 units as float64 N(0, sigma^2) i.i.d. per pixel/channel, then
round-half-even and clip to uint8; the same degraded LR bytes go to every restorer; split seed 11; v1 bank bytes.
New: the per-sample RNG seed also depends on a recorded noise seed (23 or 37), so realizations differ from v1 and
from each other. Repeats of the same image over noise seeds are NOT independent samples.
"""
from __future__ import annotations

from hashlib import sha256

import numpy as np

from . import realistic_degradation as v1

FAMILY = "realistic_lr_noise_v2"
SIGMAS = (5, 15)
NOISE_SEEDS = (23, 37)
CATEGORIES = ("hazelnut", "screw")
RESTORERS = v1.RESTORERS
SPLIT_SEED = v1.SPLIT_SEED


def conditions() -> tuple[str, ...]:
    return tuple(f"noise_s{s}" for s in SIGMAS)


def queue() -> list[dict]:
    """Fixed 32-unit queue: category x noise seed (run boundaries) x sigma x restorer."""
    return [dict(category=c, noise_seed=n, condition=k, restorer=r)
            for c in CATEGORIES for n in NOISE_SEEDS for k in conditions() for r in RESTORERS]


def sample_seed(category: str, sample: str, condition: str, noise_seed: int) -> int:
    if noise_seed not in NOISE_SEEDS or condition not in conditions():
        raise ValueError("noise seed/condition outside the fixed v2 queue")
    key = f"{FAMILY}|split_seed{SPLIT_SEED}|noise_seed{noise_seed}|{category}|{sample}|{condition}"
    return int.from_bytes(sha256(key.encode()).digest()[:8], "little")


def degrade(lr: np.ndarray, condition: str, seed: int) -> np.ndarray:
    """Exactly v1's noise operation (delegated), only the seed differs."""
    if condition not in conditions():
        raise ValueError(f"v2 is noise-only: {condition}")
    return v1.degrade(lr, condition, seed)


def lr_sha256(lr: np.ndarray) -> str:
    return sha256(np.ascontiguousarray(lr).tobytes()).hexdigest()
