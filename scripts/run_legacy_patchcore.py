"""Small, reproducible CPU pilot using Amazon's original PatchCore implementation."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter

import numpy as np
from PIL import Image

from sr_anomaly.dataset import MVTecADFolder, safe_component
from sr_anomaly.evaluation import evaluate_predictions
from sr_anomaly.metrics import compute_quality_metrics
from sr_anomaly.real_models import SwinIRLightweight


ROOT = Path(__file__).resolve().parents[1]
PATCHCORE_SOURCE = ROOT / "third_party" / "patchcore-inspection" / "src"


def _official_imports():
    if not PATCHCORE_SOURCE.is_dir():
        raise RuntimeError("Initialize the patchcore-inspection submodule first: git submodule update --init")
    sys.path.insert(0, str(PATCHCORE_SOURCE))
    import torch
    from torchvision import transforms
    from torchvision.transforms import InterpolationMode
    from patchcore import backbones, common, patchcore, sampler
    from patchcore.datasets import mvtec

    return torch, transforms, InterpolationMode, backbones, common, patchcore, sampler, mvtec


def _select_indices(count: int, limit: int, seed: int) -> list[int]:
    if limit < 0:
        raise ValueError("limit must be nonnegative")
    if limit == 0 or limit >= count:
        return list(range(count))
    return sorted(random.Random(seed).sample(range(count), limit))


def _balanced_test(samples, limit: int, seed: int):
    if limit < 0:
        raise ValueError("test limit must be nonnegative")
    if not limit or limit >= len(samples):
        return samples
    normal = [sample for sample in samples if sample.metadata["label"] == 0]
    anomalous = [sample for sample in samples if sample.metadata["label"] == 1]
    rng = random.Random(seed)
    normal_count = limit // 2
    anomalous_count = limit - normal_count
    if len(normal) < normal_count or len(anomalous) < anomalous_count:
        raise ValueError("test limit cannot be balanced from available samples")
    return sorted(rng.sample(normal, normal_count) + rng.sample(anomalous, anomalous_count), key=lambda x: x.relative_path.as_posix())


def _canonical(image: Image.Image, resize, crop) -> Image.Image:
    return crop(resize(image))


def _checksum(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _delta(new: float | None, baseline: float | None) -> float | None:
    return None if new is None or baseline is None else new - baseline


def _faiss_staging():
    # FAISS Windows wheels use narrow C paths and reject this workspace's Korean path.
    parent = Path(os.environ.get("PUBLIC", tempfile.gettempdir()))
    try:
        str(parent).encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError("FAISS requires an ASCII temporary path; set PUBLIC to a writable ASCII directory") from exc
    return tempfile.TemporaryDirectory(prefix="patchcore-", dir=parent)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--category", default="hazelnut")
    parser.add_argument("--train-limit", type=int, default=16, help="0 = all training images; default is a CPU pilot")
    parser.add_argument("--test-limit", type=int, default=4, help="0 = all test images")
    parser.add_argument("--calibration-limit", type=int, default=4, help="held-out normal train images; 0 disables F1")
    parser.add_argument("--swinir-checkpoint", type=Path, help="optional official lightweight SwinIR-S x4 weights")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    category = safe_component(args.category, "category")
    torch, transforms, InterpolationMode, backbones, common, patchcore, sampler, mvtec = _official_imports()
    actual_commit = subprocess.check_output(["git", "-C", str(PATCHCORE_SOURCE.parent), "rev-parse", "HEAD"], text=True).strip()
    expected_commit = "fcaa92f124fb1ad74a7acf56726decd4b27cbcad"
    if actual_commit != expected_commit:
        raise RuntimeError(f"PatchCore source revision changed: expected {expected_commit}, got {actual_commit}")
    torch.set_num_threads(min(4, torch.get_num_threads()))
    data_root = args.data_root.resolve()
    train_set = mvtec.MVTecDataset(str(data_root), category, resize=256, imagesize=224, split=mvtec.DatasetSplit.TRAIN)
    selected = _select_indices(len(train_set), args.train_limit, args.seed)
    test_samples = _balanced_test(MVTecADFolder(data_root, category).samples(), args.test_limit, args.seed)
    if not selected or not test_samples:
        raise ValueError("training and test sets must both be nonempty")
    run_name = f"{category}-seed{args.seed}-train{len(selected)}-test{len(test_samples)}"
    model_dir = args.model_dir or ROOT / "checkpoints" / "legacy-patchcore" / f"{category}-seed{args.seed}-train{len(selected)}"
    output_dir = args.output_dir or ROOT / "outputs" / "legacy-patchcore" / run_name
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Experiment output directory is not empty: {output_dir}")
    model_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_meta_path = model_dir / "metadata.json"
    params_path = model_dir / "patchcore_params.pkl"
    faiss_path = model_dir / "nnscorer_search_index.faiss"
    train_paths = [str(Path(train_set.data_to_iterate[index][2]).relative_to(data_root).as_posix()) for index in selected]
    model_spec = {
        "implementation": "amazon-science/patchcore-inspection",
        "source_commit": actual_commit,
        "category": category,
        "seed": args.seed,
        "train_paths": train_paths,
        "backbone": "wideresnet50",
        "layers": ["layer2", "layer3"],
        "resize": 256,
        "center_crop": 224,
        "pretrain_embed_dimension": 1024,
        "target_embed_dimension": 1024,
        "patchsize": 3,
        "sampler": "IdentitySampler",
        "nearest_neighbor": "FaissNN(cpu)",
    }
    model = patchcore.PatchCore(torch.device("cpu"))
    fit_seconds = 0.0
    if model_meta_path.exists():
        saved = json.loads(model_meta_path.read_text(encoding="utf-8"))
        if saved["spec"] != model_spec or any(_checksum(model_dir / name) != digest for name, digest in saved["artifact_sha256"].items()):
            raise ValueError("Existing PatchCore artifact does not match this run; choose a different --model-dir")
        # The upstream loader unpickles local params; checksums above bind them to this run.
        with _faiss_staging() as staging:
            for path in (params_path, faiss_path):
                shutil.copy2(path, Path(staging) / path.name)
            model.load_from_path(staging, torch.device("cpu"), nn_method=common.FaissNN(False, 4))
    else:
        if params_path.exists() or faiss_path.exists():
            raise ValueError("Incomplete existing PatchCore artifact; choose a different --model-dir")
        backbone = backbones.load("wideresnet50")
        backbone.name = "wideresnet50"
        model.load(
            backbone=backbone,
            layers_to_extract_from=["layer2", "layer3"],
            device=torch.device("cpu"),
            input_shape=(3, 224, 224),
            pretrain_embed_dimension=1024,
            target_embed_dimension=1024,
            patchsize=3,
            featuresampler=sampler.IdentitySampler(),
            nn_method=common.FaissNN(False, 4),
        )
        loader = torch.utils.data.DataLoader(torch.utils.data.Subset(train_set, selected), batch_size=8, shuffle=False, num_workers=0)
        started = perf_counter()
        model.fit(loader)
        fit_seconds = perf_counter() - started
        with _faiss_staging() as staging:
            model.save_to_path(staging)
            for path in (params_path, faiss_path):
                shutil.copy2(Path(staging) / path.name, path)
        model_meta_path.write_text(
            json.dumps({"spec": model_spec, "fit_seconds": fit_seconds, "artifact_sha256": {path.name: _checksum(path) for path in (params_path, faiss_path)}}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    resize_image = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    resize_mask = transforms.Resize(256, interpolation=InterpolationMode.NEAREST)
    crop = transforms.CenterCrop(224)
    tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])
    remaining = sorted(set(range(len(train_set))) - set(selected))
    calibration_indices = [remaining[index] for index in _select_indices(len(remaining), args.calibration_limit, args.seed + 1)] if args.calibration_limit else []
    calibration = {"source": "held-out normal train images", "quantile": 0.99,
                   "paths": [str(Path(train_set.data_to_iterate[index][2]).relative_to(data_root).as_posix()) for index in calibration_indices],
                   "image_threshold": None, "pixel_threshold": None}
    if calibration_indices:
        calibration_scores = []
        calibration_maps = []
        for index in calibration_indices:
            with Image.open(train_set.data_to_iterate[index][2]) as source:
                image = _canonical(source.convert("RGB"), resize_image, crop)
            scores, maps = model.predict(tensor(image).unsqueeze(0))
            calibration_scores.append(float(scores[0]))
            calibration_maps.append(np.asarray(maps[0]))
        calibration["image_threshold"] = float(np.quantile(calibration_scores, 0.99))
        calibration["pixel_threshold"] = float(np.quantile(np.stack(calibration_maps), 0.99))
    restorer = (
        SwinIRLightweight(ROOT / "third_party" / "SwinIR", args.swinir_checkpoint, scale=4, tile=56, tile_overlap=0)
        if args.swinir_checkpoint else None
    )
    variant_names = ["clean", "bicubic_x4"] + (["swinir_x4"] if restorer else [])
    rows = []
    predictions = {variant: {"labels": [], "scores": [], "masks": [], "maps": []} for variant in variant_names}
    for sample in test_samples:
        with Image.open(sample.path) as source:
            clean = _canonical(source.convert("RGB"), resize_image, crop)
        low_resolution = clean.resize((56, 56), Image.Resampling.BICUBIC)
        bicubic = low_resolution.resize((224, 224), Image.Resampling.BICUBIC)
        restored_seconds = 0.0
        variants = [("clean", clean), ("bicubic_x4", bicubic)]
        if restorer:
            started = perf_counter()
            restored = restorer.restore(low_resolution)
            restored_seconds = perf_counter() - started
            if restored.size != clean.size:
                raise ValueError(f"SwinIR output size {restored.size} differs from reference {clean.size}")
            variants.append(("swinir_x4", restored))
        if sample.mask_path:
            with Image.open(sample.mask_path) as mask_source:
                mask = np.asarray(_canonical(mask_source.convert("L"), resize_mask, crop)) > 0
        else:
            mask = np.zeros((224, 224), dtype=bool)
        for variant, image in variants:
            start = perf_counter()
            input_tensor = tensor(image).unsqueeze(0)
            image_scores, maps = model.predict(input_tensor)
            detector_seconds = perf_counter() - start
            # Upstream FAISS IndexFlatL2 reports squared L2 distance per patch.
            start = perf_counter()
            with torch.no_grad():
                features = np.asarray(model.embed(input_tensor))
            _, nn_distances, _ = model.anomaly_scorer.predict([features])
            nn_stats_seconds = perf_counter() - start
            score = float(image_scores[0])
            anomaly_map = np.asarray(maps[0], dtype=np.float32)
            predictions[variant]["labels"].append(int(sample.metadata["label"]))
            predictions[variant]["scores"].append(score)
            predictions[variant]["masks"].append(mask)
            predictions[variant]["maps"].append(anomaly_map)
            quality = compute_quality_metrics(clean, image, ("psnr", "ssim")) if variant != "clean" else {"psnr": None, "ssim": None}
            rows.append({
                "sample": sample.relative_path.as_posix(), "label": sample.metadata["label"], "variant": variant,
                "image_score": score, "nn_squared_l2_mean": float(np.mean(nn_distances)),
                "nn_squared_l2_max": float(np.max(nn_distances)), "nn_squared_l2_min": float(np.min(nn_distances)),
                "psnr": quality["psnr"], "ssim": quality["ssim"], "restoration_seconds": restored_seconds if variant == "swinir_x4" else 0.0,
                "detector_seconds": detector_seconds, "nn_stats_seconds": nn_stats_seconds,
            })
    evaluations = {}
    for variant, values in predictions.items():
        evaluations[variant] = evaluate_predictions(
            labels=np.asarray(values["labels"]), scores=np.asarray(values["scores"]),
            masks=np.asarray(values["masks"]), anomaly_maps=np.asarray(values["maps"]),
            image_threshold=calibration["image_threshold"], pixel_threshold=calibration["pixel_threshold"],
        )
        np.savez_compressed(output_dir / f"{variant}_predictions.npz", **{key: np.asarray(value) for key, value in values.items()})
    with (output_dir / "per_image.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    result = {"model_spec": model_spec, "model_dir": str(model_dir), "fit_seconds_this_run": fit_seconds,
              "restoration": {"name": restorer.name, "checkpoint_sha256": _checksum(args.swinir_checkpoint)} if restorer else None,
              "calibration": calibration,
              "test_paths": [sample.relative_path.as_posix() for sample in test_samples],
              "variants": {variant: {"evaluation": evaluation,
                                     "mean_psnr": float(np.mean([row["psnr"] for row in rows if row["variant"] == variant and row["psnr"] is not None])) if variant != "clean" else None,
                                     "mean_ssim": float(np.mean([row["ssim"] for row in rows if row["variant"] == variant and row["ssim"] is not None])) if variant != "clean" else None}
                           for variant, evaluation in evaluations.items()},
              "note": "CPU subset pilot; F1 is null when no held-out normal calibration images are available."}
    summary_rows = []
    for variant, item in result["variants"].items():
        summary_rows.append({"variant": variant, "test_count": len(test_samples), "train_count": len(selected),
                             "mean_psnr": item["mean_psnr"], "mean_ssim": item["mean_ssim"],
                             **{f"mean_{name}": float(np.mean([row[name] for row in rows if row["variant"] == variant]))
                                for name in ("restoration_seconds", "detector_seconds", "nn_stats_seconds")},
                             **item["evaluation"]["classification"], **item["evaluation"]["localization"]})
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)
    if restorer:
        baseline = result["variants"]["bicubic_x4"]
        restored = result["variants"]["swinir_x4"]
        result["comparison_vs_bicubic_x4"] = {
            "delta_psnr": _delta(restored["mean_psnr"], baseline["mean_psnr"]),
            "delta_ssim": _delta(restored["mean_ssim"], baseline["mean_ssim"]),
            **{f"delta_{key}": _delta(restored["evaluation"][section][key], baseline["evaluation"][section][key])
               for section, keys in (("classification", ("image_auroc", "image_f1")),
                                     ("localization", ("pixel_auroc", "pixel_f1", "au_pro"))) for key in keys},
        }
    (output_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run": run_name, "results": result["variants"], "output": str(output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
