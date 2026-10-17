"""Two fixed gates on already-normalized anomaly maps; no GT or calibration."""

import numpy as np


def gated_maps(degraded: np.ndarray, restored: np.ndarray,
               tau_deg: float, tau_rest: float) -> dict[str, np.ndarray]:
    degraded = np.asarray(degraded, dtype=np.float64)
    restored = np.asarray(restored, dtype=np.float64)
    if degraded.shape != restored.shape or degraded.ndim != 3 or degraded.size == 0:
        raise ValueError("Gating requires matching nonempty [N,H,W] maps")
    if not (np.isfinite(degraded).all() and np.isfinite(restored).all()
            and np.isfinite(tau_deg) and np.isfinite(tau_rest)):
        raise ValueError("Gating maps and thresholds must be finite")
    difference = np.maximum(degraded - restored, 0)
    gate = degraded > tau_deg
    return {
        "candidate_1": restored + gate * difference,
        "candidate_2": restored + (gate & (restored <= tau_rest)) * difference,
    }
