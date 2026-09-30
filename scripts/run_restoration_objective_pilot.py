"""Run a frozen Hazelnut restoration-endpoint cohort without fitting PatchCore."""

from __future__ import annotations

import argparse
import csv
import json
from importlib import metadata as package_metadata
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from time import perf_counter

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_legacy_patchcore import (  # noqa: E402
    EXPECTED_PATCHCORE_COMMIT,
    EXPECTED_SWINIR_X4_SHA256,
    FROZEN_PATCHCORE_SETTINGS,
    _canonical,
    _checksum,
    _faiss_staging,
    _official_imports,
)
from sr_anomaly.dataset import safe_join  # noqa: E402
from sr_anomaly.device import device_metadata, elapsed_seconds, resolve_device, start_timer  # noqa: E402
from sr_anomaly.evaluation import area_under_per_region_overlap, binary_roc_auc, evaluate_predictions  # noqa: E402
from sr_anomaly.metrics import compute_quality_metrics  # noqa: E402
from sr_anomaly.objective_study import load_full_manifest, load_pilot_manifest, regression_type  # noqa: E402
from sr_anomaly.real_models import ESRGANRRDBX4, SwinIRLightweight, matlab_bicubic_resize  # noqa: E402


EXPECTED_ESRGAN_COMMIT = "73e9b634cf987f5996ac2dd33f4050922398a921"
EXPECTED_BASICSR_COMMIT = "8d56e3a045f9fb3e1d8872f92ee4a4f07f886b0a"
EXPECTED_SWINIR_COMMIT = "6545850fbf8df298df73d81f3e8cba638787c8bd"
EXPECTED_RRDB_PSNR_SHA256 = "f372b59f22929e1bc83fa58d78215c96f976de3b2eaeee736da1b348913da6cc"
EXPECTED_RRDB_ESRGAN_SHA256 = "65fece06e1ccb48853242aa972bdf00ad07a7dd8938d2dcbdf4221b59f6372ce"
EXPECTED_MANIFEST_SHA256 = "4d3b23548b5add0f067bec44330062870cde00a1521b9680198744f32bbf3603"
EXPECTED_FULL_MANIFEST_SHA256 = "2ddb62748c750b3e4fae2b4b0b0cb4f3c354fd02faac74c95117afe1b3e116cc"
EXPECTED_BANK_SHA256 = {
    "patchcore_params.pkl": "7c2728899e9e4aeca619d5c6f24ad47456c1603cc16e4c846a80f002c6ddc8b4",
    "nnscorer_search_index.faiss": "e665e08ac3d108ae095566df7baf7e966561333fdf50a6d85c6f5d77bfc3f9b4",
}
VARIANTS = ("bicubic_x4", "swinir_x4", "rrdb_psnr_x4", "rrdb_esrgan_x4")
COHORTS = {
    "pilot25": {
        "manifest": ROOT / "analysis" / "restoration_objective_pilot" / "pilot_manifest.csv",
        "sha256": EXPECTED_MANIFEST_SHA256,
        "counts": (25, 5, 20),
        "output": ROOT / "outputs" / "restoration-objective" / "hazelnut-pilot25",
        "load": load_pilot_manifest,
    },
    "full110": {
        "manifest": ROOT / "analysis" / "restoration_objective_full" / "full_manifest.csv",
        "sha256": EXPECTED_FULL_MANIFEST_SHA256,
        "counts": (110, 40, 70),
        "output": ROOT / "outputs" / "restoration-objective" / "hazelnut-full110",
        "load": load_full_manifest,
    },
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=tuple(COHORTS), default="pilot25")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--manifest", type=Path, help="Alternate location of the selected cohort's checksum-bound manifest")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "checkpoints" / "legacy-patchcore" / "hazelnut-seed11-train391")
    parser.add_argument("--swinir-checkpoint", type=Path, default=ROOT / "checkpoints" / "swinir" / "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth")
    parser.add_argument("--rrdb-psnr-checkpoint", type=Path, default=ROOT / "checkpoints" / "esrgan" / "RRDB_PSNR_x4.pth")
    parser.add_argument("--rrdb-esrgan-checkpoint", type=Path, default=ROOT / "checkpoints" / "esrgan" / "RRDB_ESRGAN_x4.pth")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu", help="Models use this device; FAISS stays on CPU")
    parser.add_argument("--with-lpips", action="store_true", help="Add the single frozen perceptual metric (AlexNet LPIPS)")
    parser.add_argument("--lpips-device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args(argv)
    args.manifest = args.manifest or COHORTS[args.cohort]["manifest"]
    args.output_dir = args.output_dir or COHORTS[args.cohort]["output"]
    return args


def _git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def _require_revision(path: Path, expected: str, name: str) -> str:
    actual = _git_head(path)
    if actual != expected:
        raise RuntimeError(f"{name} source revision changed: expected {expected}, got {actual}")
    return actual


def _require_file_hash(path: Path, expected: str, name: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"{name} file not found: {path}")
    actual = _checksum(path)
    if actual != expected:
        raise ValueError(f"{name} SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def _load_frozen_detector(model_dir: Path, device, common, patchcore) -> tuple[object, dict, dict]:
    metadata_path = model_dir / "metadata.json"
    params_path = model_dir / "patchcore_params.pkl"
    faiss_path = model_dir / "nnscorer_search_index.faiss"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Frozen PatchCore metadata not found: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    spec = metadata.get("spec", {})
    if (
        spec.get("source_commit") != EXPECTED_PATCHCORE_COMMIT
        or spec.get("category") != "hazelnut"
        or spec.get("seed") != 11
        or len(spec.get("train_paths", ())) != 391
        or len(set(spec.get("train_paths", ()))) != 391
        or any(not path.startswith("hazelnut/train/good/") for path in spec.get("train_paths", ()))
        or any(spec.get(key) != value for key, value in FROZEN_PATCHCORE_SETTINGS.items())
    ):
        raise ValueError("PatchCore bank is not the frozen Hazelnut Branch A 391-normal bank")
    expected_artifacts = metadata.get("artifact_sha256", {})
    for path in (params_path, faiss_path):
        if (not path.is_file() or expected_artifacts.get(path.name) != EXPECTED_BANK_SHA256[path.name]
                or _checksum(path) != EXPECTED_BANK_SHA256[path.name]):
            raise ValueError(f"PatchCore bank artifact is missing or changed: {path}")
    model = patchcore.PatchCore(device)
    with _faiss_staging() as staging:
        for path in (params_path, faiss_path):
            shutil.copy2(path, Path(staging) / path.name)
        model.load_from_path(staging, device, nn_method=common.FaissNN(False, 4))
    return model, spec, metadata


def _per_image_metrics(mask: np.ndarray, anomaly_map: np.ndarray) -> dict[str, float]:
    region = np.asarray(mask, dtype=bool)
    values = np.asarray(anomaly_map, dtype=np.float64)
    return {
        "per_image_pixel_auroc": float(binary_roc_auc(region.ravel(), values.ravel())),
        "per_image_aupro": float(area_under_per_region_overlap(region[None], values[None], max_fpr=0.3, num_thresholds=200)),
        "roi_mean": float(values[region].mean()),
        "background_mean": float(values[~region].mean()),
        "roi_bg_gap": float(values[region].mean() - values[~region].mean()),
    }


def _delta(new: float | None, baseline: float | None) -> float | None:
    return None if new is None or baseline is None else new - baseline


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _load_frozen_manifest(args: argparse.Namespace, data_root: Path) -> tuple[str, list[dict[str, str]]]:
    cohort = COHORTS[args.cohort]
    manifest_sha = _require_file_hash(args.manifest.resolve(), cohort["sha256"], f"frozen {args.cohort} manifest")
    rows = cohort["load"](args.manifest.resolve(), data_root)
    counts = (len(rows), sum(int(row["label"]) == 0 for row in rows), sum(int(row["label"]) == 1 for row in rows))
    if counts != cohort["counts"]:
        raise ValueError(f"{args.cohort} cohort counts changed: expected {cohort['counts']}, got {counts}")
    return manifest_sha, rows


def _execution_provenance(torch, args: argparse.Namespace, argv: list[str]) -> dict:
    lpips_version = None
    if args.with_lpips:
        try:
            lpips_version = package_metadata.version("lpips")
        except package_metadata.PackageNotFoundError:
            pass
    return {
        "python_version": platform.python_version(),
        "pytorch_version": str(torch.__version__),
        "torch_cuda_build_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "lpips_package_version": lpips_version,
        "invocation_argv": list(argv),
        "interpreter_argv": list(sys.orig_argv),
        "resolved_arguments": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
    }


def _output_artifact_hashes(output_dir: Path) -> dict[str, str]:
    names = ("summary.csv", "per_image.csv", "regression_taxonomy.csv", "objective_pair_per_image.csv")
    names += tuple(f"{variant}_predictions.npz" for variant in VARIANTS)
    return {name: _checksum(output_dir / name) for name in names}


def main() -> None:
    wall_started = perf_counter()
    args = _parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Experiment output directory is not empty: {output_dir}")
    data_root = args.data_root.resolve()
    manifest_sha, manifest_rows = _load_frozen_manifest(args, data_root)
    if args.cohort == "full110" and not args.with_lpips:
        raise ValueError("full110 requires --with-lpips to preserve the frozen quality metrics")

    torch, transforms, InterpolationMode, _, common, patchcore, _, mvtec = _official_imports()
    cuda_available = torch.cuda.is_available()
    device = torch.device(resolve_device(args.device, cuda_available))
    if args.with_lpips and args.lpips_device == "cuda" and not cuda_available:
        raise RuntimeError("--lpips-device cuda requested, but PyTorch CUDA is unavailable")
    execution = device_metadata(
        args.device,
        str(device),
        cuda_available,
        torch.cuda.get_device_name(device) if str(device).startswith("cuda") else None,
    )
    torch.set_num_threads(min(4, torch.get_num_threads()))

    patchcore_commit = _require_revision(ROOT / "third_party" / "patchcore-inspection", EXPECTED_PATCHCORE_COMMIT, "PatchCore")
    swinir_commit = _require_revision(ROOT / "third_party" / "SwinIR", EXPECTED_SWINIR_COMMIT, "SwinIR")
    esrgan_commit = _require_revision(ROOT / "third_party" / "ESRGAN", EXPECTED_ESRGAN_COMMIT, "ESRGAN")
    basicsr_commit = _require_revision(ROOT / "third_party" / "BasicSR", EXPECTED_BASICSR_COMMIT, "BasicSR")
    checkpoint_hashes = {
        "swinir_x4": _require_file_hash(args.swinir_checkpoint, EXPECTED_SWINIR_X4_SHA256, "SwinIR x4"),
        "rrdb_psnr_x4": _require_file_hash(args.rrdb_psnr_checkpoint, EXPECTED_RRDB_PSNR_SHA256, "RRDB PSNR x4"),
        "rrdb_esrgan_x4": _require_file_hash(args.rrdb_esrgan_checkpoint, EXPECTED_RRDB_ESRGAN_SHA256, "RRDB ESRGAN x4"),
    }
    detector, detector_spec, bank_metadata = _load_frozen_detector(args.model_dir.resolve(), device, common, patchcore)

    resize_image = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    resize_mask = transforms.Resize(256, interpolation=InterpolationMode.NEAREST)
    crop = transforms.CenterCrop(224)
    to_tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])
    restorers = {
        "swinir_x4": SwinIRLightweight(ROOT / "third_party" / "SwinIR", args.swinir_checkpoint, device=str(device), scale=4, tile=56, tile_overlap=0),
        "rrdb_psnr_x4": ESRGANRRDBX4(ROOT / "third_party" / "ESRGAN", args.rrdb_psnr_checkpoint, "rrdb_psnr_x4", str(device)),
        "rrdb_esrgan_x4": ESRGANRRDBX4(ROOT / "third_party" / "ESRGAN", args.rrdb_esrgan_checkpoint, "rrdb_esrgan_x4", str(device)),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    predictions = {name: {"labels": [], "scores": [], "masks": [], "maps": []} for name in VARIANTS}
    rows: list[dict] = []
    anomaly_rows: list[dict] = []
    objective_pair_rows: list[dict] = []
    quality_names = ("psnr", "ssim", "lpips") if args.with_lpips else ("psnr", "ssim")

    for manifest_row in manifest_rows:
        sample_path = safe_join(data_root, manifest_row["sample"])
        with Image.open(sample_path) as source:
            clean = _canonical(source.convert("RGB"), resize_image, crop)
        low_resolution = matlab_bicubic_resize(clean, 0.25, ROOT / "third_party" / "BasicSR")
        variant_images = {"bicubic_x4": matlab_bicubic_resize(low_resolution, 4.0, ROOT / "third_party" / "BasicSR")}
        restoration_seconds = {"bicubic_x4": 0.0}
        for name, restorer in restorers.items():
            started = start_timer(torch, device)
            restored = restorer.restore(low_resolution)
            restoration_seconds[name] = elapsed_seconds(torch, device, started)
            if restored.size != clean.size:
                raise ValueError(f"{name} output size {restored.size} differs from reference {clean.size}")
            variant_images[name] = restored

        if manifest_row["mask"]:
            with Image.open(safe_join(data_root, manifest_row["mask"])) as source:
                mask = np.asarray(_canonical(source.convert("L"), resize_mask, crop)) > 0
        else:
            mask = np.zeros((224, 224), dtype=bool)
        label = int(manifest_row["label"])
        sample_output = images_dir / manifest_row["stratum"] / Path(manifest_row["sample"]).stem
        sample_output.mkdir(parents=True, exist_ok=True)
        clean.save(sample_output / "clean.png")
        low_resolution.save(sample_output / "lr_x4.png")
        if label:
            Image.fromarray(mask.astype(np.uint8) * 255, mode="L").save(sample_output / "gt_mask.png")

        sample_variant_metrics: dict[str, dict[str, float]] = {}
        for name in VARIANTS:
            image = variant_images[name]
            image.save(sample_output / f"{name}.png")
            quality = compute_quality_metrics(clean, image, quality_names, lpips_device=args.lpips_device)
            started = start_timer(torch, device)
            scores, maps = detector.predict(to_tensor(image).unsqueeze(0))
            detector_seconds = elapsed_seconds(torch, device, started)
            score = float(scores[0])
            anomaly_map = np.asarray(maps[0], dtype=np.float32)
            predictions[name]["labels"].append(label)
            predictions[name]["scores"].append(score)
            predictions[name]["masks"].append(mask)
            predictions[name]["maps"].append(anomaly_map)
            local = _per_image_metrics(mask, anomaly_map) if label else {}
            sample_variant_metrics[name] = local
            rows.append({
                "sample": manifest_row["sample"],
                "label": label,
                "defect_type": manifest_row["defect_type"],
                "variant": name,
                "image_score": score,
                "psnr": quality["psnr"],
                "ssim": quality["ssim"],
                "lpips": quality.get("lpips"),
                **{key: local.get(key) for key in ("per_image_pixel_auroc", "per_image_aupro", "roi_mean", "background_mean", "roi_bg_gap")},
                "restoration_seconds": restoration_seconds[name],
                "detector_seconds": detector_seconds,
                "device": str(device),
                "output_image": (sample_output / f"{name}.png").relative_to(output_dir).as_posix(),
            })
        if label:
            baseline = sample_variant_metrics["bicubic_x4"]
            for name in VARIANTS[1:]:
                current = sample_variant_metrics[name]
                delta_aupro = current["per_image_aupro"] - baseline["per_image_aupro"]
                delta_gap = current["roi_bg_gap"] - baseline["roi_bg_gap"]
                anomaly_rows.append({
                    "sample": manifest_row["sample"],
                    "defect_type": manifest_row["defect_type"],
                    "variant": name,
                    "baseline_variant": "bicubic_x4",
                    "regression_type": regression_type(delta_aupro, delta_gap),
                    "per_image_aupro": current["per_image_aupro"],
                    "delta_per_image_aupro": delta_aupro,
                    "per_image_pixel_auroc": current["per_image_pixel_auroc"],
                    "delta_per_image_pixel_auroc": current["per_image_pixel_auroc"] - baseline["per_image_pixel_auroc"],
                    "roi_mean": current["roi_mean"],
                    "delta_roi_mean": current["roi_mean"] - baseline["roi_mean"],
                    "roi_bg_gap": current["roi_bg_gap"],
                    "delta_roi_bg_gap": delta_gap,
                    "defect_area_ratio": float(mask.mean()),
                })
        pair = {row["variant"]: row for row in rows[-len(VARIANTS):]}
        psnr, gan = pair["rrdb_psnr_x4"], pair["rrdb_esrgan_x4"]
        objective_pair_rows.append({
            "sample": manifest_row["sample"],
            "defect_type": manifest_row["defect_type"],
            "label": label,
            **{f"delta_{key}_esrgan_minus_psnr": _delta(gan[key], psnr[key])
               for key in ("psnr", "ssim", "lpips", "image_score", "per_image_pixel_auroc", "per_image_aupro", "roi_bg_gap")
               + (("roi_mean",) if args.cohort == "full110" else ())},
        })

    evaluations = {}
    summary_rows = []
    for name, values in predictions.items():
        arrays = {key: np.asarray(value) for key, value in values.items()}
        evaluation = evaluate_predictions(arrays["labels"], arrays["scores"], arrays["masks"], arrays["maps"])
        evaluations[name] = evaluation
        np.savez_compressed(output_dir / f"{name}_predictions.npz", **arrays)
        variant_rows = [row for row in rows if row["variant"] == name]
        summary_rows.append({
            "variant": name,
            "test_count": len(manifest_rows),
            "normal_count": sum(int(row["label"]) == 0 for row in manifest_rows),
            "anomaly_count": sum(int(row["label"]) == 1 for row in manifest_rows),
            "mean_psnr": float(np.mean([row["psnr"] for row in variant_rows])),
            "mean_ssim": float(np.mean([row["ssim"] for row in variant_rows])),
            "mean_lpips": float(np.mean([row["lpips"] for row in variant_rows])) if args.with_lpips else None,
            **evaluation["classification"],
            **evaluation["localization"],
            "mean_restoration_seconds": float(np.mean([row["restoration_seconds"] for row in variant_rows])),
            "mean_detector_seconds": float(np.mean([row["detector_seconds"] for row in variant_rows])),
        })

    _write_csv(output_dir / "per_image.csv", rows)
    _write_csv(output_dir / "regression_taxonomy.csv", anomaly_rows)
    _write_csv(output_dir / "objective_pair_per_image.csv", objective_pair_rows)
    _write_csv(output_dir / "summary.csv", summary_rows)
    by_name = {row["variant"]: row for row in summary_rows}
    objective_pair = {
        key: _delta(by_name["rrdb_esrgan_x4"][key], by_name["rrdb_psnr_x4"][key])
        for key in ("mean_psnr", "mean_ssim", "mean_lpips", "image_auroc", "pixel_auroc", "au_pro")
    }
    result = {
        "study": "restoration_objective_full" if args.cohort == "full110" else "restoration_objective_pilot",
        "category_role": "Hazelnut development/exploration; not untouched validation",
        "manifest": str(args.manifest),
        "manifest_sha256": manifest_sha,
        "selection_rule": ("all 110 Hazelnut test images in lexical path order; fixed before inference"
                           if args.cohort == "full110" else "lexical first 5 in normal/crack/cut/hole/print; fixed before inference"),
        "sample_count": len(manifest_rows),
        "source_commit": _git_head(ROOT),
        "device": str(device),
        **execution,
        "detector": {
            "spec": detector_spec,
            "model_dir": str(args.model_dir),
            "fit_performed": False,
            "bank_artifact_sha256": bank_metadata["artifact_sha256"],
            "source_commit": patchcore_commit,
            "faiss": "CPU IndexFlatL2 exact search",
        },
        "degradation": {
            "clean_transform": "Resize(256, bilinear) then CenterCrop(224)",
            "lr": "BasicSR MATLAB-compatible bicubic 224x224 to 56x56, antialiasing=True, rounded to uint8",
            "bicubic_baseline": "same BasicSR implementation 56x56 to 224x224",
            "source_commit": basicsr_commit,
        },
        "restoration": {
            "swinir_source_commit": swinir_commit,
            "esrgan_source_commit": esrgan_commit,
            "checkpoint_sha256": checkpoint_hashes,
            "input": "same 56x56 RGB uint8 LR image for every learned restorer",
            "output": "224x224 RGB uint8",
        },
        "metrics": {
            "quality": list(quality_names),
            "detection": ["image_auroc", "pixel_auroc", "pooled_au_pro_at_0.3"],
            "f1": None,
            "au_pro_thresholds": 200,
        },
        "variants": {row["variant"]: row for row in summary_rows},
        "objective_pair_delta_rrdb_esrgan_minus_rrdb_psnr": objective_pair,
        "note": "No model selection, threshold fitting, fusion, or PatchCore fitting is performed by this pilot.",
    }
    result["execution_provenance"] = _execution_provenance(torch, args, sys.argv)
    result["artifact_sha256"] = _output_artifact_hashes(output_dir)
    result["wall_clock_seconds"] = elapsed_seconds(torch, device, wall_started)
    result["wall_clock_scope"] = "main entry through setup, inference, evaluation, file writes and artifact hashing; excludes final results.json serialization"
    (output_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_dir), "objective_pair_delta": objective_pair}, ensure_ascii=False))


if __name__ == "__main__":
    main()
