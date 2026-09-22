"""Read-only preflight for the frozen full Branch A cross-category run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from sr_anomaly.dataset import MVTecADFolder, safe_component
from sr_anomaly.device import resolve_device

from run_legacy_patchcore import (
    EXPECTED_PATCHCORE_COMMIT,
    EXPECTED_SWINIR_X4_SHA256,
    FROZEN_PATCHCORE_SETTINGS,
    _checksum,
)


def dataset_summary(data_root: Path, category: str) -> dict:
    train = MVTecADFolder(data_root, category, split="train", require_masks=False).samples()
    test = MVTecADFolder(data_root, category, split="test", require_masks=True).samples()
    if not train or any(sample.metadata["label"] != 0 for sample in train):
        raise ValueError("Training split must contain nonempty normal-only images")
    normal = sum(sample.metadata["label"] == 0 for sample in test)
    anomalous = len(test) - normal
    if not normal or not anomalous or any(sample.mask_path is None for sample in test if sample.metadata["label"] == 1):
        raise ValueError("Test split requires normal images and masked anomalous images")
    return {
        "train_normal_count": len(train),
        "test_count": len(test),
        "test_normal_count": normal,
        "test_anomalous_count": anomalous,
        "defect_types": sorted({sample.metadata["defect_type"] for sample in test if sample.metadata["label"] == 1}),
    }


def validate_output_dir(path: Path) -> str:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"Full-run output directory must not exist or must be empty: {path}")
    return "empty" if path.exists() else "absent"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/external/MVTecAD")
    parser.add_argument("--category", default="screw")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--train-limit", type=int, default=0)
    parser.add_argument("--test-limit", type=int, default=0)
    parser.add_argument("--calibration-limit", type=int, default=0)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cuda")
    parser.add_argument("--swinir-checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    category = safe_component(args.category, "category")
    if args.seed != 11 or any((args.train_limit, args.test_limit, args.calibration_limit)):
        raise ValueError("Frozen full Branch A requires seed 11 and train/test/calibration limits all equal to 0")
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if status.strip():
        raise ValueError("Git working tree must be clean before the full run")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    patchcore_commit = subprocess.check_output(
        ["git", "-C", str(ROOT / "third_party/patchcore-inspection"), "rev-parse", "HEAD"], text=True
    ).strip()
    if patchcore_commit != EXPECTED_PATCHCORE_COMMIT:
        raise ValueError(f"PatchCore commit mismatch: {patchcore_commit}")
    checkpoint_sha256 = _checksum(args.swinir_checkpoint)
    if checkpoint_sha256 != EXPECTED_SWINIR_X4_SHA256:
        raise ValueError(f"SwinIR checkpoint mismatch: {checkpoint_sha256}")
    if not (ROOT / "third_party/SwinIR/models/network_swinir.py").is_file():
        raise FileNotFoundError("Pinned SwinIR source is missing; initialize submodules")
    import torch
    actual_device = resolve_device(args.device, torch.cuda.is_available())
    report = {
        "ready": True,
        "repository": {"branch": branch, "commit": commit, "working_tree_clean": True},
        "dataset": {"category": category, **dataset_summary(args.data_root.resolve(), category)},
        "execution": {
            "requested_device": args.device,
            "actual_device": actual_device,
            "cuda_available": bool(torch.cuda.is_available()),
            "gpu_name": torch.cuda.get_device_name(0) if actual_device == "cuda" else None,
        },
        "patchcore": {"source_commit": patchcore_commit, **FROZEN_PATCHCORE_SETTINGS},
        "restoration": {"name": "swinir_lightweight_x4", "checkpoint_sha256": checkpoint_sha256},
        "run": {
            "seed": args.seed,
            "train_limit": args.train_limit,
            "test_limit": args.test_limit,
            "calibration_limit": args.calibration_limit,
            "f1_policy": "disabled: no independent normal calibration split",
            "output_dir": str(args.output_dir.resolve()),
            "output_dir_state": validate_output_dir(args.output_dir.resolve()),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
