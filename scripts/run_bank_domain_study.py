"""Run the fixed 2x2 PatchCore normal-bank-domain study on one full MVTec category."""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import platform
from pathlib import Path
import shutil
import sys
import time
import traceback

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.dataset import ImageSample, MVTecADFolder, safe_component
from sr_anomaly.fusion import split_train_calibration
from sr_anomaly.metrics import compute_quality_metrics
from sr_anomaly.real_models import SwinIRLightweight
from sr_anomaly import bank_domain_study as study
from scripts import run_fusion_patchcore as branch_b

EXPECTED_PATCHCORE_COMMIT = branch_b.EXPECTED_PATCHCORE_COMMIT
EXPECTED_SWINIR_SHA256 = branch_b.EXPECTED_SWINIR_X4_SHA256
EXPECTED_WIDERESNET_SHA256 = "95faca4d11227dddf8633dbb5ff6c8a9003c1aa5b8945c73834b8007b10950b8"
OFFICIAL_MVTEC_AD_URL = "https://www.mvtec.com/research-teaching/datasets/mvtec-ad"
IMAGE_SIZE = 224
PATCHES_PER_IMAGE = 28 * 28


def _checksum_images(samples, category_root: Path) -> list[dict]:
    records = []
    for sample in samples:
        record = {
            "sample": sample.relative_path.as_posix(),
            "image_sha256": study.sha256_file(sample.path),
            "label": int(sample.metadata["label"]),
            "defect_type": sample.metadata.get("defect_type"),
            "mask_sha256": study.sha256_file(sample.mask_path) if sample.mask_path else None,
        }
        records.append(record)
    return records


def _rgb_sha(image: Image.Image) -> str:
    return study.sha256_array(np.asarray(image.convert("RGB"), dtype=np.uint8))


def _query_variants(image_path: Path, restorer, resize, crop):
    with Image.open(image_path) as source:
        clean = branch_b._canonical(source.convert("RGB"), resize, crop)
    low = clean.resize((56, 56), Image.Resampling.BICUBIC)
    bicubic = low.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BICUBIC)
    started = time.perf_counter()
    restored = restorer.restore(low)
    seconds = time.perf_counter() - started
    if restored.mode != "RGB" or restored.size != clean.size:
        raise ValueError(f"SwinIR output must be RGB {clean.size}, got {restored.mode} {restored.size}")
    return clean.copy(), bicubic.copy(), restored.copy(), seconds


class _BankDomainDataset:
    """PatchCore fit wrapper; transforms clean RGB before tensor normalization."""

    def __init__(self, base, indices, domain, restorer, resize, crop, transforms, torch):
        self.base = base
        self.indices = tuple(indices)
        self.domain = domain
        self.restorer = restorer
        self.resize = resize
        self.crop = crop
        self.transforms = transforms
        self.torch = torch

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, local_index):
        source_index = self.indices[local_index]
        classname, anomaly, image_path, _ = self.base.data_to_iterate[source_index]
        with Image.open(image_path) as source:
            clean = branch_b._canonical(source.convert("RGB"), self.resize, self.crop)
        if self.domain == "swinir_restored":
            low = clean.resize((56, 56), Image.Resampling.BICUBIC)
            image = self.restorer.restore(low)
            if image.mode != "RGB" or image.size != clean.size:
                raise ValueError("Restored fit RGB differs from canonical native size")
        elif self.domain == "clean":
            image = clean
        else:
            raise ValueError(f"Unknown bank domain: {self.domain}")
        tensor = self.transforms(image)
        return {
            "image": tensor,
            "mask": self.torch.zeros((1, IMAGE_SIZE, IMAGE_SIZE)),
            "classname": classname,
            "anomaly": anomaly,
            "is_anomaly": 0,
            "image_name": Path(image_path).as_posix(),
            # Default DataLoader collation cannot handle pathlib.Path objects.
            "image_path": str(image_path),
        }


def _new_patchcore(torch, backbones, common, patchcore, sampler, device, backbone_checkpoint: Path):
    model = patchcore.PatchCore(device)
    # Use the checked-in local torchvision ImageNet V1 checkpoint instead of
    # triggering an implicit torchvision network download on a fresh PC.
    import torchvision.models as torchvision_models

    backbone = torchvision_models.wide_resnet50_2(weights=None)
    backbone.load_state_dict(
        torch.load(backbone_checkpoint, map_location="cpu", weights_only=True), strict=True
    )
    backbone.name = "wideresnet50"
    model.load(
        backbone=backbone,
        layers_to_extract_from=["layer2", "layer3"],
        device=device,
        input_shape=(3, IMAGE_SIZE, IMAGE_SIZE),
        pretrain_embed_dimension=1024,
        target_embed_dimension=1024,
        patchsize=3,
        featuresampler=sampler.IdentitySampler(),
        nn_method=common.FaissNN(False, 4),
    )
    return model


def _predict_all(model, tensor, cache, ordered_samples, query_domain):
    scores = np.empty(len(ordered_samples), dtype=np.float64)
    maps = np.empty((len(ordered_samples), IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32)
    seconds = np.empty(len(ordered_samples), dtype=np.float64)
    for index, sample in enumerate(ordered_samples):
        image = cache[sample.relative_path.as_posix()][query_domain]
        started = time.perf_counter()
        scores[index], maps[index] = branch_b._predict(model, tensor, image)
        seconds[index] = time.perf_counter() - started
    if not np.isfinite(scores).all() or not np.isfinite(maps).all():
        raise ValueError("Non-finite query prediction")
    return scores, maps, seconds


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty table: {path.name}")
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_npz(path: Path, **arrays) -> dict:
    temporary = path.with_name(path.name + ".partial")
    if path.exists() or temporary.exists():
        raise FileExistsError(path)
    with temporary.open("xb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        import os
        os.fsync(handle.fileno())
    temporary.replace(path)
    with np.load(path, allow_pickle=False) as artifact:
        shapes = {name: list(artifact[name].shape) for name in artifact.files}
        for name in artifact.files:
            values = artifact[name]
            if values.dtype.kind in "fiu" and not np.isfinite(values).all():
                raise ValueError(f"Non-finite artifact array: {name}")
    return {"file": path.name, "sha256": study.sha256_file(path), "arrays": shapes}


def _identity_from_raw(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as artifact:
        return {
            "samples": artifact["test_samples"].astype(str).tolist(),
            "query_input_sha256": artifact["query_input_sha256"].astype(str).tolist(),
            "query_domains": artifact["query_domains"].astype(str).tolist(),
            "query_domain_sha256": {
                "bicubic_x4": artifact["query_bicubic_sha256"].astype(str).tolist(),
                "swinir_x4": artifact["query_swinir_sha256"].astype(str).tolist(),
            },
        }


def _load_dataset_provenance(path: Path, data_root: Path, category: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(
            f"Dataset provenance receipt is required: {path}. Record the official source, archive SHA-256, "
            "license file/hash, and delivered categories before running inference."
        )
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("dataset") != "MVTec AD" or receipt.get("source_url") != OFFICIAL_MVTEC_AD_URL:
        raise ValueError("Dataset receipt must identify the official MVTec AD source URL")
    categories = receipt.get("categories")
    if not isinstance(categories, list) or category not in categories:
        raise ValueError(f"Dataset receipt does not include category {category}")
    archive_sha = str(receipt.get("archive_sha256", "")).lower()
    if len(archive_sha) != 64 or any(char not in "0123456789abcdef" for char in archive_sha):
        raise ValueError("Dataset receipt must contain a 64-character archive_sha256")
    license_relative = receipt.get("license_file")
    if not isinstance(license_relative, str) or not license_relative:
        raise ValueError("Dataset receipt must name the delivered license_file")
    license_path = study.safe_artifact_path(data_root, license_relative)
    if not license_path.is_file():
        raise FileNotFoundError(f"Dataset license file is missing: {license_path}")
    license_sha = study.sha256_file(license_path)
    expected_license_sha = str(receipt.get("license_sha256", "")).lower()
    if expected_license_sha != license_sha:
        raise ValueError("Dataset license SHA-256 does not match the provenance receipt")
    archive_relative = receipt.get("archive_file")
    if archive_relative is not None:
        archive_path = study.safe_artifact_path(data_root, str(archive_relative))
        if not archive_path.is_file() or study.sha256_file(archive_path) != archive_sha:
            raise ValueError("Retained dataset archive is missing or its SHA-256 differs from the receipt")
    return {
        "dataset": "MVTec AD",
        "source_url": OFFICIAL_MVTEC_AD_URL,
        "receipt_path": str(path.resolve()),
        "receipt_sha256": study.sha256_file(path),
        "archive_sha256": archive_sha,
        "categories": categories,
        "license_file": license_relative,
        "license_sha256": license_sha,
        "license_text": "CC BY-NC-SA 4.0; verify the delivered official license text",
    }


def run(args: argparse.Namespace) -> Path:
    category = safe_component(args.category, "category").lower()
    run_id = safe_component(args.run_id, "run id")
    if category not in {"hazelnut", "screw", "capsule"}:
        raise ValueError("Only the preselected MVTec categories are supported")
    if args.seed not in study.SEEDS:
        raise ValueError(f"Study seeds are frozen to {study.SEEDS}")
    if category == "capsule":
        receipt_path = args.capsule_history_receipt
        if receipt_path is None or not receipt_path.is_file():
            raise RuntimeError("Capsule is gated until an explicit team-use history receipt is supplied")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("all_team_members_confirmed_no_test_use") is not True:
            raise RuntimeError("Capsule history receipt does not confirm untouched test use")
        if receipt.get("patchcore_hazelnut_screw_seed11_reviewed") is not True:
            raise RuntimeError("Capsule is gated until Hazelnut/Screw seed-11 PatchCore results are reviewed")
        if receipt.get("efficientad_seed11_complete_or_protocol_frozen") is not True:
            raise RuntimeError("Capsule is gated until EfficientAD seed-11 work is complete or its protocol is frozen")
    data_root = args.data_root.resolve()
    category_root = data_root / category
    if not category_root.is_dir():
        raise FileNotFoundError(
            f"Required MVTec category is missing: {category_root}. "
            "This run will not download the full 15-category archive."
        )
    dataset_provenance = _load_dataset_provenance(
        args.dataset_provenance.resolve(), data_root, category
    )

    torch, transforms, InterpolationMode, backbones, common, patchcore, sampler, mvtec = branch_b._official_imports()
    cuda_available = torch.cuda.is_available()
    device = torch.device(branch_b.resolve_device(args.device, cuda_available))
    if device.type != "cuda":
        raise RuntimeError("This execution queue requires the existing CUDA device; CPU is for tests only")
    checkpoint = args.swinir_checkpoint.resolve()
    checkpoint_sha = branch_b._checksum(checkpoint)
    if checkpoint_sha != EXPECTED_SWINIR_SHA256:
        raise ValueError(f"SwinIR checkpoint SHA mismatch: {checkpoint_sha}")
    backbone_checkpoint = args.backbone_checkpoint.resolve()
    backbone_sha = branch_b._checksum(backbone_checkpoint)
    if backbone_sha != EXPECTED_WIDERESNET_SHA256:
        raise ValueError(f"WideResNet50-2 ImageNet V1 SHA mismatch: {backbone_sha}")
    patchcore_source = branch_b.PATCHCORE_SOURCE
    actual_patchcore_commit = branch_b.subprocess.check_output(
        ["git", "-C", str(patchcore_source.parent), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_patchcore_commit != EXPECTED_PATCHCORE_COMMIT:
        raise RuntimeError(
            f"PatchCore revision mismatch: expected {EXPECTED_PATCHCORE_COMMIT}, got {actual_patchcore_commit}"
        )

    torch.set_num_threads(min(4, torch.get_num_threads()))
    torch.manual_seed(args.seed)
    resize = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    crop = transforms.CenterCrop(IMAGE_SIZE)
    tensor = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD),
    ])
    train_set = mvtec.MVTecDataset(
        str(data_root), category, resize=256, imagesize=IMAGE_SIZE, split=mvtec.DatasetSplit.TRAIN
    )
    train_total = len(train_set)
    fit_indices, calibration_indices = split_train_calibration(train_total, 0.8, args.seed)
    if not fit_indices or not calibration_indices:
        raise ValueError("Fit and normal calibration splits must both be nonempty")
    test_samples = MVTecADFolder(data_root, category, split="test", require_masks=True).samples()
    if not test_samples or any(sample.mask_path and not sample.mask_path.is_file() for sample in test_samples):
        raise ValueError("Full-category test images and anomaly masks must be present")
    if any(row[1] != "good" for row in train_set.data_to_iterate):
        raise ValueError("PatchCore bank and calibration inputs must contain normal train/good images only")
    train_paths = [Path(train_set.data_to_iterate[i][2]).relative_to(data_root).as_posix()
                   for i in fit_indices]
    calibration_paths = [Path(train_set.data_to_iterate[i][2]).relative_to(data_root).as_posix()
                         for i in calibration_indices]
    calibration_samples = []
    for index in calibration_indices:
        image_path = Path(train_set.data_to_iterate[index][2])
        relative_path = image_path.relative_to(data_root)
        calibration_samples.append(ImageSample(
            sample_id=relative_path.as_posix(),
            path=image_path,
            relative_path=relative_path,
            mask_path=None,
            metadata={"category": category, "split": "train", "label": 0, "defect_type": "good"},
        ))
    test_ids = {sample.relative_path.as_posix() for sample in test_samples}
    test_mask_paths = {
        sample.relative_path.as_posix(): (
            sample.mask_path.relative_to(data_root).as_posix() if sample.mask_path else None
        )
        for sample in test_samples
    }
    test_mask_hashes = {
        sample.relative_path.as_posix(): (study.sha256_file(sample.mask_path) if sample.mask_path else None)
        for sample in test_samples
    }

    plan = study.bank_fit_plan(len(fit_indices), batch_size=8)
    available_ram_before_run = study.available_ram_bytes()
    study.check_fit_ram(plan, available_bytes=available_ram_before_run)

    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    disk_plan = study.output_disk_plan(len(calibration_indices), len(test_samples), image_size=IMAGE_SIZE)
    disk_free_before_run = shutil.disk_usage(output_root).free
    study.check_output_disk(disk_plan, free_bytes=disk_free_before_run)
    run_dir = output_root / run_id / category / f"seed{args.seed}"
    if run_dir.exists():
        raise FileExistsError(f"Run directory exists; failed/old outputs are never overwritten: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    state = {
        "schema_version": study.SCHEMA_VERSION,
        "status": "BUILDING",
        "scope": "full-category-bank-domain-study",
        "run_id": run_id,
        "category": category,
        "seed": args.seed,
        "seeds_frozen": list(study.SEEDS),
        "bank_domains": list(study.BANK_DOMAINS),
        "query_domains": list(study.QUERY_DOMAINS),
        "fit_paths": train_paths,
        "calibration_paths": calibration_paths,
        "test_samples": [sample.relative_path.as_posix() for sample in test_samples],
        "test_mask_paths": test_mask_paths,
        "test_mask_sha256": test_mask_hashes,
        "fit_count": len(fit_indices),
        "calibration_count": len(calibration_indices),
        "test_count": len(test_samples),
        "dataset_provenance": dataset_provenance,
        "resource_plan": {
            "fit_ram": plan,
            "available_ram_before_run_bytes": available_ram_before_run,
            "prediction_disk": disk_plan,
            "free_disk_before_run_bytes": disk_free_before_run,
        },
        "artifacts": [],
        "prediction_rows": [],
    }
    study.write_status(run_dir, state)
    restorer = None
    completed = False
    try:
        restorer = SwinIRLightweight(
            ROOT / "third_party" / "SwinIR", checkpoint,
            device=str(device), scale=4, tile=56, tile_overlap=0
        )
        cache: dict[str, dict[str, Image.Image]] = {}
        input_hashes: dict[str, str] = {}
        query_hashes: dict[str, dict[str, str]] = {}
        quality_rows: list[dict] = []
        for sample in calibration_samples + test_samples:
            sample_id = sample.relative_path.as_posix()
            clean, bicubic, restored, restoration_seconds = _query_variants(
                sample.path, restorer, resize, crop
            )
            cache[sample_id] = {"bicubic_x4": bicubic, "swinir_x4": restored}
            input_hashes[sample_id] = branch_b._checksum(sample.path)
            query_hashes[sample_id] = {
                "bicubic_x4": _rgb_sha(bicubic),
                "swinir_x4": _rgb_sha(restored),
            }
            if sample_id in test_ids:
                bicubic_quality = compute_quality_metrics(clean, bicubic, ("psnr", "ssim"))
                restored_quality = compute_quality_metrics(clean, restored, ("psnr", "ssim"))
                quality_rows.append({
                    "sample": sample_id,
                    "psnr_bicubic": bicubic_quality["psnr"],
                    "ssim_bicubic": bicubic_quality["ssim"],
                    "psnr_swinir": restored_quality["psnr"],
                    "ssim_swinir": restored_quality["ssim"],
                    "swinir_seconds": restoration_seconds,
                })
            del clean
        if len(quality_rows) != len(test_samples):
            raise RuntimeError("Query quality was not computed exactly once per test image")

        available_ram = study.available_ram_bytes()
        study.check_fit_ram(plan, available_bytes=available_ram)
        state["resource_snapshot_before_fit"] = {
            "available_ram_bytes": available_ram,
            "plan": plan,
            "disk_free_bytes": shutil.disk_usage(run_dir).free,
            "gpu_name": torch.cuda.get_device_name(device),
            "gpu_free_bytes_before_fit": int(torch.cuda.mem_get_info(device)[0]),
        }
        train_input_hashes = {
            path: branch_b._checksum(data_root / path) for path in train_paths + calibration_paths
        }
        state["train_input_sha256"] = train_input_hashes
        state["test_input_sha256"] = {
            sample.relative_path.as_posix(): input_hashes[sample.relative_path.as_posix()]
            for sample in test_samples
        }
        inventory_hashes = {
            **train_input_hashes,
            **state["test_input_sha256"],
            **{f"mask:{sample_id}": digest for sample_id, digest in test_mask_hashes.items() if digest},
        }
        state["input_inventory_sha256"] = hashlib.sha256(
            json.dumps(inventory_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        state["query_rgb_sha256"] = query_hashes
        state["patchcore_source_commit"] = actual_patchcore_commit
        state["swinir_checkpoint_sha256"] = checkpoint_sha
        state["backbone_checkpoint_sha256"] = backbone_sha
        state["backbone_checkpoint"] = str(backbone_checkpoint)
        state["source_commit"] = branch_b.subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        state["torch_version"] = torch.__version__
        torchvision = __import__("torchvision")
        import faiss
        import timm
        state["torchvision_version"] = torchvision.__version__
        state["faiss_version"] = faiss.__version__
        state["timm_version"] = timm.__version__
        state["python_version"] = sys.version
        state["platform"] = platform.platform()
        state["torch_cuda_build"] = torch.version.cuda
        state["device"] = str(device)
        state["gpu_name"] = torch.cuda.get_device_name(device)
        state["normalization_rule"] = "existing robust_params/normalize; per cell; normal calibration only"
        state["threshold_rule"] = "existing quantile_threshold at fixed q=0.99; normal calibration only"
        state["metric_rule"] = "existing evaluate_predictions; pooled AU-PRO@0.3 primary"
        state["model_configuration"] = {
            "patchcore_source_commit": actual_patchcore_commit,
            "backbone": "WideResNet50-2 ImageNet V1",
            "backbone_checkpoint_sha256": backbone_sha,
            "layers": ["layer2", "layer3"],
            "resize_short_side": 256,
            "center_crop": IMAGE_SIZE,
            "pretrain_embed_dimension": 1024,
            "target_embed_dimension": 1024,
            "patch_size": 3,
            "sampler": "IdentitySampler",
            "patches_per_fit_image": PATCHES_PER_IMAGE,
            "faiss": "CPU IndexFlatL2; FaissNN(False, 4); 1-nearest-neighbor score",
            "fit_batch_size": 8,
            "train_fit_fraction": 0.8,
            "normal_calibration_fraction": 0.2,
            "seed": args.seed,
            "swinir_checkpoint": str(checkpoint),
            "swinir_checkpoint_sha256": checkpoint_sha,
            "swinir_scale": 4,
            "swinir_tile": 56,
            "swinir_tile_overlap": 0,
            "bicubic_downsample_size": 56,
            "query_domains": list(study.QUERY_DOMAINS),
        }
        state["command"] = [sys.executable, *sys.argv]
        state["git_branch"] = branch_b.subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip()
        state["git_dirty"] = bool(branch_b.subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip())
        state["submodule_revisions"] = {
            name: branch_b.subprocess.check_output(
                ["git", "-C", str(ROOT / "third_party" / name), "rev-parse", "HEAD"],
                text=True,
            ).strip()
            for name in ("SwinIR", "patchcore-inspection")
        }
        try:
            state["nvidia_smi"] = branch_b.subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                text=True,
            ).strip()
        except Exception as exc:
            state["nvidia_smi_query_error"] = f"{type(exc).__name__}: {exc}"
        study.write_status(run_dir, state)

        raw_results: dict[str, dict[str, np.ndarray]] = {}
        bank_hashes: dict[str, str] = {}
        runtime_rows: list[dict] = []
        for bank_domain in study.BANK_DOMAINS:
            available_ram_for_bank = study.available_ram_bytes()
            study.check_fit_ram(plan, available_bytes=available_ram_for_bank)
            state.setdefault("available_ram_before_each_bank_bytes", {})[bank_domain] = available_ram_for_bank
            study.write_status(run_dir, state)
            # Re-seed construction so randomly initialized PatchCore projection modules
            # are identical within this paired bank-domain comparison.
            torch.manual_seed(args.seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(args.seed)
                torch.cuda.reset_peak_memory_stats(device)
            model = _new_patchcore(
                torch, backbones, common, patchcore, sampler, device, backbone_checkpoint
            )
            fit_dataset = _BankDomainDataset(
                train_set, fit_indices, bank_domain, restorer, resize, crop, tensor, torch
            )
            fit_loader = torch.utils.data.DataLoader(
                fit_dataset, batch_size=8, shuffle=False, num_workers=0, pin_memory=False
            )
            fit_started = time.perf_counter()
            model.fit(fit_loader)
            torch.cuda.synchronize(device)
            fit_seconds = time.perf_counter() - fit_started
            bank_values = np.asarray(model.anomaly_scorer.detection_features)
            if (bank_values.ndim != 2 or bank_values.shape[0] != plan["fit_vectors"]
                    or bank_values.shape[1] != 1024 or bank_values.dtype != np.float32
                    or not np.isfinite(bank_values).all()):
                raise ValueError(f"Unexpected feature bank from {bank_domain}: {bank_values.shape} {bank_values.dtype}")
            bank_hashes[bank_domain] = study.sha256_array(bank_values)
            cell_data = {
                "calibration_scores": np.empty((len(calibration_indices), len(study.QUERY_DOMAINS)), np.float64),
                "calibration_maps": np.empty((len(calibration_indices), len(study.QUERY_DOMAINS), IMAGE_SIZE, IMAGE_SIZE), np.float32),
                "test_scores": np.empty((len(test_samples), len(study.QUERY_DOMAINS)), np.float64),
                "test_maps": np.empty((len(test_samples), len(study.QUERY_DOMAINS), IMAGE_SIZE, IMAGE_SIZE), np.float32),
            }
            infer_seconds = 0.0
            for query_index, query_domain in enumerate(study.QUERY_DOMAINS):
                cal_scores, cal_maps, cal_times = _predict_all(
                    model, tensor, cache, calibration_samples, query_domain
                )
                test_scores, test_maps, test_times = _predict_all(
                    model, tensor, cache, test_samples, query_domain
                )
                cell_data["calibration_scores"][:, query_index] = cal_scores
                cell_data["calibration_maps"][:, query_index] = cal_maps
                cell_data["test_scores"][:, query_index] = test_scores
                cell_data["test_maps"][:, query_index] = test_maps
                infer_seconds += float(cal_times.sum() + test_times.sum())
            raw_results[bank_domain] = cell_data
            raw_path = run_dir / f"raw_{bank_domain}.npz"
            artifact = _write_npz(
                raw_path,
                calibration_samples=np.asarray([s.relative_path.as_posix() for s in calibration_samples]),
                test_samples=np.asarray([s.relative_path.as_posix() for s in test_samples]),
                query_domains=np.asarray(study.QUERY_DOMAINS),
                bank_sha256=np.asarray(bank_hashes[bank_domain]),
                query_input_sha256=np.asarray([
                    input_hashes[sample.relative_path.as_posix()] for sample in test_samples
                ]),
                query_bicubic_sha256=np.asarray([
                    query_hashes[sample.relative_path.as_posix()]["bicubic_x4"] for sample in test_samples
                ]),
                query_swinir_sha256=np.asarray([
                    query_hashes[sample.relative_path.as_posix()]["swinir_x4"] for sample in test_samples
                ]),
                **cell_data,
            )
            state["artifacts"].append(artifact)
            runtime_rows.append({
                "bank_domain": bank_domain,
                "fit_seconds": fit_seconds,
                "query_inference_seconds": infer_seconds,
                "torch_cuda_peak_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
                "torch_cuda_peak_reserved_bytes": int(torch.cuda.max_memory_reserved(device)),
                "bank_bytes": int(bank_values.nbytes),
                "bank_sha256": bank_hashes[bank_domain],
            })
            nn_method = getattr(model.anomaly_scorer, "nn_method", None)
            if nn_method is not None:
                nn_method.reset_index()
            del fit_loader, fit_dataset, bank_values, model
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.synchronize(device)

        # Confirm the shared query source and transform bytes did not change across banks.
        if len(bank_hashes) != len(study.BANK_DOMAINS) or not all(bank_hashes.values()):
            raise RuntimeError("Both paired banks must complete")
        study.validate_pair_identity(
            _identity_from_raw(run_dir / "raw_clean.npz"),
            _identity_from_raw(run_dir / "raw_swinir_restored.npz"),
        )
        test_labels = np.asarray([sample.metadata["label"] for sample in test_samples], dtype=np.uint8)
        test_masks = []
        resize_mask = transforms.Resize(256, interpolation=InterpolationMode.NEAREST)
        for sample in test_samples:
            if sample.mask_path is None:
                test_masks.append(np.zeros((IMAGE_SIZE, IMAGE_SIZE), dtype=bool))
            else:
                with Image.open(sample.mask_path) as mask_source:
                    mask = np.asarray(branch_b._canonical(mask_source.convert("L"), resize_mask, crop)) > 0
                test_masks.append(mask)
        test_masks_array = np.stack(test_masks)
        if not np.array_equal(test_masks_array.reshape(len(test_masks_array), -1).any(axis=1), test_labels.astype(bool)):
            raise ValueError("Native test mask occupancy disagrees with official image labels")

        summary_rows: list[dict] = []
        per_image_rows: list[dict] = []
        calibration_records: dict[str, dict] = {}
        for bank_domain in study.BANK_DOMAINS:
            values = raw_results[bank_domain]
            for query_index, query_domain in enumerate(study.QUERY_DOMAINS):
                calibration = study.fit_cell_calibration(
                    np.zeros(len(calibration_indices), dtype=np.uint8),
                    values["calibration_scores"][:, query_index],
                    values["calibration_maps"][:, query_index],
                )
                metrics, per_images = study.evaluate_cell(
                    test_labels,
                    values["test_scores"][:, query_index],
                    test_masks_array,
                    values["test_maps"][:, query_index],
                    calibration,
                    [sample.relative_path.as_posix() for sample in test_samples],
                )
                calibration_records[f"{bank_domain}/{query_domain}"] = calibration
                summary_rows.append({
                    "category": category,
                    "seed": args.seed,
                    "bank_domain": bank_domain,
                    "query_domain": query_domain,
                    "fit_count": len(fit_indices),
                    "calibration_count": len(calibration_indices),
                    "test_count": len(test_samples),
                    "image_auroc": metrics["classification"]["image_auroc"],
                    "image_f1": metrics["classification"]["image_f1"],
                    "pixel_auroc": metrics["localization"]["pixel_auroc"],
                    "pooled_aupro_at_0_3": metrics["localization"]["au_pro"],
                    "pixel_f1": metrics["localization"]["pixel_f1"],
                    "image_threshold": calibration["image_threshold"],
                    "pixel_threshold": calibration["pixel_threshold"],
                })
                for row in per_images:
                    per_image_rows.append({
                        **row,
                        "category": category,
                        "seed": args.seed,
                        "bank_domain": bank_domain,
                        "query_domain": query_domain,
                        "defect_type": next(s.metadata.get("defect_type") for s in test_samples
                                            if s.relative_path.as_posix() == row["sample"]),
                    })
                    state["prediction_rows"].append({
                        "bank_domain": bank_domain,
                        "query_domain": query_domain,
                        "sample": row["sample"],
                    })
        state["artifacts"].append(_write_npz(
            run_dir / "test_masks_for_local_analysis.npz",
            samples=np.asarray([sample.relative_path.as_posix() for sample in test_samples]),
            masks=test_masks_array,
        ))
        _write_csv(run_dir / "summary.csv", summary_rows)
        _write_csv(run_dir / "per_image.csv", per_image_rows)
        _write_csv(run_dir / "query_quality.csv", quality_rows)
        state["artifacts"].extend([
            {"file": name, "sha256": study.sha256_file(run_dir / name)}
            for name in ("summary.csv", "per_image.csv", "query_quality.csv")
        ])
        state["calibration_by_cell"] = calibration_records
        state["bank_hashes"] = bank_hashes
        state["runtime"] = runtime_rows
        state["resource_snapshot_after"] = {
            "available_ram_bytes": study.available_ram_bytes(),
            "disk_free_bytes": shutil.disk_usage(run_dir).free,
        }
        state["status"] = "COMPLETE"
        study.write_status(run_dir, state)
        study.verify_complete_run(
            run_dir,
            study.expected_condition_order([sample.relative_path.as_posix() for sample in test_samples]),
        )
        completed = True
        return run_dir
    except BaseException as error:
        state["status"] = "FAILED"
        state["error"] = f"{type(error).__name__}: {error}"
        state["traceback"] = traceback.format_exc()
        study.write_status(run_dir, state)
        raise
    finally:
        if restorer is not None:
            del restorer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if not completed:
            print(f"Partial/failed run preserved at {run_dir}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--dataset-provenance", type=Path,
                        help="receipt JSON; defaults to <data-root>/dataset_provenance.json")
    parser.add_argument("--category", choices=("hazelnut", "screw", "capsule"), required=True)
    parser.add_argument("--seed", type=int, choices=study.SEEDS, required=True)
    parser.add_argument("--swinir-checkpoint", type=Path,
                        default=ROOT / "checkpoints" / "swinir" / "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth")
    parser.add_argument("--backbone-checkpoint", type=Path,
                        default=ROOT / "checkpoints" / "wide_resnet50_2-95faca4d.pth")
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs" / "bank-domain-study")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--capsule-history-receipt", type=Path)
    args = parser.parse_args()
    if args.dataset_provenance is None:
        args.dataset_provenance = args.data_root / "dataset_provenance.json"
    try:
        run_dir = run(args)
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED_OR_FAILED", "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 1
    print(json.dumps({"status": "COMPLETE", "run_dir": str(run_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
