"""Existing Hazelnut paired-bootstrap implementation, shared without changing it."""
from __future__ import annotations

import numpy as np


def percentile_ci(values: np.ndarray, alpha: float = 0.05) -> list[float]:
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return [float("nan"), float("nan")]
    lo, hi = np.quantile(values, [alpha / 2.0, 1.0 - alpha / 2.0])
    return [float(lo), float(hi)]


def paired_bootstrap_mean_delta(deltas: np.ndarray, repeats: int,
                               rng: np.random.Generator) -> dict:
    deltas = np.asarray(deltas, dtype=np.float64)
    deltas = deltas[np.isfinite(deltas)]
    if deltas.size == 0:
        return {"estimate": None, "ci95": [None, None], "n": 0}
    draws = np.empty(repeats, dtype=np.float64)
    n = deltas.size
    for i in range(repeats):
        idx = rng.integers(0, n, n)
        draws[i] = deltas[idx].mean()
    return {"estimate": float(deltas.mean()), "ci95": percentile_ci(draws), "n": int(n)}
