"""Small shared helpers for CPU/CUDA experiment execution and timing."""

from __future__ import annotations

from time import perf_counter


def resolve_device(requested: str, cuda_available: bool) -> str:
    if requested == "auto":
        return "cuda" if cuda_available else "cpu"
    if requested == "cuda" and not cuda_available:
        raise RuntimeError("--device cuda requested, but PyTorch CUDA is unavailable")
    if requested not in {"cpu", "cuda"}:
        raise ValueError(f"Unsupported device: {requested}")
    return requested


def device_metadata(requested: str, actual: str, cuda_available: bool, gpu_name: str | None = None) -> dict:
    metadata = {
        "requested_device": requested,
        "actual_device": actual,
        "cuda_available": bool(cuda_available),
    }
    if actual.startswith("cuda"):
        metadata["gpu_name"] = gpu_name
    return metadata


def start_timer(torch, device) -> float:
    if str(device).startswith("cuda"):
        torch.cuda.synchronize(device)
    return perf_counter()


def elapsed_seconds(torch, device, started: float) -> float:
    if str(device).startswith("cuda"):
        torch.cuda.synchronize(device)
    return perf_counter() - started
