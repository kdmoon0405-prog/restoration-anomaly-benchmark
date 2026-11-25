"""Realistic-LR degradation family v1 for ONE category; resumable per (condition, restorer) unit.

Protocol: docs/REALISTIC_DEGRADATION_PROTOCOL.md. Clean-normal bank fit once on the fixed fit split, reused for all
units; per-unit normal calibration on the held-out calibration normals; GT masks enter only after a unit's
predictions are saved, for evaluation.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
from PIL import Image, features
import PIL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from run_legacy_patchcore import EXPECTED_PATCHCORE_COMMIT, EXPECTED_SWINIR_X4_SHA256, _canonical, _checksum, _faiss_staging, _official_imports  # noqa: E402
from run_restoration_objective_pilot import EXPECTED_BASICSR_COMMIT, EXPECTED_SWINIR_COMMIT, _per_image_metrics, _require_file_hash, _require_revision  # noqa: E402
from sr_anomaly import realistic_degradation as rd  # noqa: E402
from sr_anomaly.dataset import MVTecADFolder  # noqa: E402
from sr_anomaly.evaluation import evaluate_predictions  # noqa: E402
from sr_anomaly.fusion import normalize, quantile_threshold, robust_params  # noqa: E402
from sr_anomaly.metrics import compute_quality_metrics  # noqa: E402
from sr_anomaly.real_models import SwinIRLightweight, matlab_bicubic_resize  # noqa: E402

CODE = ("scripts/run_realistic_degradation.py", "src/sr_anomaly/realistic_degradation.py", "src/sr_anomaly/evaluation.py",
        "src/sr_anomaly/fusion.py", "src/sr_anomaly/metrics.py", "src/sr_anomaly/real_models.py",
        "scripts/run_legacy_patchcore.py", "scripts/run_restoration_objective_pilot.py")
COUNTS = {"hazelnut": (391, 110, 40, 70), "screw": (320, 160, 41, 119)}
QUANTILE = 0.99


def _protocol(args, train, test, fit, calibration) -> dict:
    data = args.data_root.resolve()
    return {"family": rd.FAMILY, "category": args.category, "conditions": list(rd.CONDITIONS), "restorers": list(rd.RESTORERS),
            "split_seed": rd.SPLIT_SEED, "calibration_fraction": rd.CALIBRATION_FRACTION, "quantile": QUANTILE,
            "fit_paths": fit, "calibration_paths": calibration,
            "test": [{"sample": s.relative_path.as_posix(), "label": int(s.metadata["label"]), "defect_type": str(s.metadata["defect_type"]),
                      "image_sha256": _checksum(s.path), "mask_sha256": _checksum(s.mask_path) if s.mask_path else ""} for s in test],
            "train_sha256": {p: _checksum(data / p) for p in train},
            "code_sha256": {name: _checksum(ROOT / name) for name in CODE},
            "checkpoints": {"swinir_x4": EXPECTED_SWINIR_X4_SHA256, **{k: v[1] for k, v in rd.CHECKPOINTS.items()}},
            "revisions": {"patchcore": EXPECTED_PATCHCORE_COMMIT, "swinir": EXPECTED_SWINIR_COMMIT, "basicsr": EXPECTED_BASICSR_COMMIT,
                          "realesrgan_inference_semantics": rd.REALESRGAN_COMMIT},
            "versions": {"python": sys.version, "numpy": np.__version__, "pillow": PIL.__version__,
                         "libjpeg": features.version("jpg"), "torch": __import__("torch").__version__},
            "realesrgan_precision": "fp32 (official default fp16)", "lpips": args.with_lpips}


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _bank(output, device, torch, common, patchcore, sampler, backbones, fit_images, to_tensor):
    bank_dir = output / "bank"
    names = ("patchcore_params.pkl", "nnscorer_search_index.faiss")
    model = patchcore.PatchCore(device)
    if (bank_dir / "metadata.json").is_file():
        meta = json.loads((bank_dir / "metadata.json").read_text(encoding="utf-8"))
        if any(_checksum(bank_dir / n) != meta["artifact_sha256"][n] for n in names):
            raise ValueError("Family bank changed")
        with _faiss_staging() as staging:
            for n in names:
                shutil.copy2(bank_dir / n, Path(staging) / n)
            model.load_from_path(staging, device, nn_method=common.FaissNN(False, 4))
        return model, meta
    bank_dir.mkdir()
    torch.manual_seed(11)
    backbone = backbones.load("wideresnet50")
    backbone.name = "wideresnet50"
    model.load(backbone=backbone, layers_to_extract_from=["layer2", "layer3"], device=device, input_shape=(3, 224, 224),
               pretrain_embed_dimension=1024, target_embed_dimension=1024, patchsize=3,
               featuresampler=sampler.IdentitySampler(), nn_method=common.FaissNN(False, 4))
    loader = torch.utils.data.DataLoader([to_tensor(image) for image in fit_images], batch_size=8, shuffle=False)
    started = time.perf_counter()
    model.fit(loader)
    fit_seconds = time.perf_counter() - started
    with _faiss_staging() as staging:
        model.save_to_path(staging)
        for n in names:
            shutil.copy2(Path(staging) / n, bank_dir / n)
    meta = {"fit_images": len(fit_images), "fit_seconds": fit_seconds, "clean_normal_only": True,
            "artifact_sha256": {n: _checksum(bank_dir / n) for n in names}}
    (bank_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return model, meta


def _unit_metrics(rows_cal, rows_test, cal_maps, test_maps, masks) -> tuple[dict, dict]:
    image = robust_params(np.asarray([r["image_score"] for r in rows_cal]))
    pixel = robust_params(cal_maps)
    image_threshold = quantile_threshold(normalize(np.asarray([r["image_score"] for r in rows_cal]), image), QUANTILE)
    pixel_threshold = quantile_threshold(normalize(cal_maps, pixel), QUANTILE)
    labels = np.asarray([r["label"] for r in rows_test])
    scores = normalize(np.asarray([r["image_score"] for r in rows_test]), image)
    metrics = evaluate_predictions(labels, scores, masks=masks, anomaly_maps=normalize(test_maps, pixel),
                                   image_threshold=image_threshold, pixel_threshold=pixel_threshold, max_fpr=0.3)
    flagged = scores >= image_threshold
    risk = {"image_false_alarm_rate_test_normal": float(flagged[labels == 0].mean()),
            "image_miss_rate_test_anomaly": float((~flagged[labels == 1]).mean()),
            "calibration_image_score_median_raw": image["median"], "calibration_pixel_median_raw": pixel["median"]}
    return {**metrics["classification"], **metrics["localization"], **risk}, {"image": image, "pixel": pixel,
            "image_threshold": image_threshold, "pixel_threshold": pixel_threshold, "calibration_normals": len(rows_cal)}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=tuple(COUNTS), required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--with-lpips", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-units", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    wall = time.perf_counter()
    output = (args.output_dir or ROOT / "outputs" / "realistic-degradation" / f"{args.category}-v1").resolve()
    if not args.resume and output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output exists; use --resume: {output}")
    data = args.data_root.resolve()
    folder = MVTecADFolder(data, args.category)
    test = sorted(folder.samples(), key=lambda s: s.relative_path.as_posix())
    train = sorted(p.relative_to(data).as_posix() for p in (data / args.category / "train" / "good").glob("*.png"))
    if (len(train), len(test), sum(int(s.metadata["label"]) == 0 for s in test), sum(int(s.metadata["label"]) == 1 for s in test)) != COUNTS[args.category]:
        raise ValueError("Category cohort counts changed")
    fit, calibration = rd.split_train(train)
    for name, path in (("SwinIR x4", ROOT / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth"),
                       ("RealESRNet", ROOT / "checkpoints/realesrgan/RealESRNet_x4plus.pth"),
                       ("RealESRGAN", ROOT / "checkpoints/realesrgan/RealESRGAN_x4plus.pth")):
        _require_file_hash(path, {"SwinIR x4": EXPECTED_SWINIR_X4_SHA256, "RealESRNet": rd.CHECKPOINTS["realesrnet_x4plus"][1],
                                  "RealESRGAN": rd.CHECKPOINTS["realesrgan_x4plus"][1]}[name], name)
    for path, expected, name in ((ROOT / "third_party/patchcore-inspection", EXPECTED_PATCHCORE_COMMIT, "PatchCore"),
                                 (ROOT / "third_party/SwinIR", EXPECTED_SWINIR_COMMIT, "SwinIR"),
                                 (ROOT / "third_party/BasicSR", EXPECTED_BASICSR_COMMIT, "BasicSR")):
        _require_revision(path, expected, name)
    protocol = _protocol(args, train, test, fit, calibration)
    if args.resume:
        saved = json.loads((output / "PROTOCOL.json").read_text(encoding="utf-8"))
        if json.dumps(saved, sort_keys=True) != json.dumps(protocol, sort_keys=True):
            raise ValueError("Code/input/config differs from saved protocol; resume refused")
    else:
        output.mkdir(parents=True, exist_ok=True)
        (output / "PROTOCOL.json").write_text(json.dumps(protocol, indent=1), encoding="utf-8")
    protocol_sha = _checksum(output / "PROTOCOL.json")
    torch, transforms, InterpolationMode, backbones, common, patchcore, sampler, mvtec = _official_imports()
    torch.set_num_threads(min(4, torch.get_num_threads()))
    device = torch.device(args.device)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    resize_image = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    resize_mask = transforms.Resize(256, interpolation=InterpolationMode.NEAREST)
    crop = transforms.CenterCrop(224)
    to_tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])

    def clean(path):
        with Image.open(path) as source:
            return _canonical(source.convert("RGB"), resize_image, crop)

    calibration_clean = {p: clean(data / p) for p in calibration}
    test_clean = {s.relative_path.as_posix(): clean(s.path) for s in test}
    started = time.perf_counter()
    model, bank_meta = _bank(output, device, torch, common, patchcore, sampler, backbones, [clean(data / p) for p in fit], to_tensor)
    bank_seconds = time.perf_counter() - started
    basicsr = ROOT / "third_party" / "BasicSR"
    lr = {k: np.asarray(matlab_bicubic_resize(v, 0.25, basicsr)) for k, v in (calibration_clean | test_clean).items()}
    restorers = {"bicubic_x4": lambda image: matlab_bicubic_resize(image, 4.0, basicsr),
                 "swinir_x4": SwinIRLightweight(ROOT / "third_party/SwinIR", ROOT / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth",
                                                device=str(device), scale=4, tile=56, tile_overlap=0).restore,
                 "realesrnet_x4plus": rd.RealESRGANX4(basicsr, ROOT / "checkpoints/realesrgan/RealESRNet_x4plus.pth", "realesrnet_x4plus", str(device)).restore,
                 "realesrgan_x4plus": rd.RealESRGANX4(basicsr, ROOT / "checkpoints/realesrgan/RealESRGAN_x4plus.pth", "realesrgan_x4plus", str(device)).restore}
    quality_names = ("psnr", "ssim", "lpips") if args.with_lpips else ("psnr", "ssim")
    (output / "units").mkdir(exist_ok=True)
    session = {"start": time.strftime("%Y-%m-%dT%H:%M:%S"), "bank_load_or_fit_seconds": bank_seconds, "units_run": [], "units_skipped": []}
    done = 0
    for condition in rd.CONDITIONS:
        for restorer_name in rd.RESTORERS:
            unit = f"{condition}__{restorer_name}"
            receipt_path = output / "units" / f"{unit}.json"
            if receipt_path.is_file():
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if receipt["protocol_sha256"] != protocol_sha or any(_checksum(output / f) != h for f, h in receipt["files"].items()):
                    raise ValueError(f"Unit {unit} receipt/payload differs; resume refused")
                session["units_skipped"].append(unit)
                continue
            if args.max_units is not None and done >= args.max_units:
                continue
            unit_started = time.perf_counter()
            restore = restorers[restorer_name]
            image_dir = output / "images" / condition / restorer_name
            image_dir.mkdir(parents=True, exist_ok=True)
            results = {"calibration": [], "test": []}
            maps = {"calibration": [], "test": []}
            timing = {"restore": 0.0, "predict": 0.0, "quality": 0.0}
            for split, references in (("calibration", calibration_clean), ("test", test_clean)):
                for sample, reference in references.items():
                    degraded = Image.fromarray(rd.degrade(lr[sample], condition, rd.sample_seed(args.category, sample, condition)), "RGB")
                    t = time.perf_counter(); restored = restore(degraded); timing["restore"] += time.perf_counter() - t
                    if restored.size != (224, 224) or restored.mode != "RGB":
                        raise ValueError("Restorer output must be RGB 224x224")
                    restored.save(image_dir / (sample.replace("/", "__") + ".png"))
                    t = time.perf_counter()
                    quality = compute_quality_metrics(reference, restored, quality_names, lpips_device="cpu")
                    timing["quality"] += time.perf_counter() - t
                    t = time.perf_counter()
                    scores, anomaly_maps = model.predict(to_tensor(restored).unsqueeze(0))
                    if args.device == "cuda":
                        torch.cuda.synchronize()
                    timing["predict"] += time.perf_counter() - t
                    maps[split].append(np.asarray(anomaly_maps[0], dtype=np.float32))
                    results[split].append({"sample": sample, "split": split, "condition": condition, "restorer": restorer_name,
                                           "label": 0 if split == "calibration" else int(next(s for s in test if s.relative_path.as_posix() == sample).metadata["label"]),
                                           "image_score": float(scores[0]), **{k: quality.get(k) for k in quality_names}})
            payload = output / "units" / f"{unit}.npz"
            np.savez(payload, calibration_maps=np.stack(maps["calibration"]), test_maps=np.stack(maps["test"]),
                     calibration_scores=np.asarray([r["image_score"] for r in results["calibration"]]),
                     test_scores=np.asarray([r["image_score"] for r in results["test"]]))
            # Evaluation only from here: GT masks are loaded after predictions are saved.
            masks = []
            for s in test:
                if s.mask_path:
                    with Image.open(s.mask_path) as source:
                        masks.append(np.asarray(_canonical(source.convert("L"), resize_mask, crop)) > 0)
                else:
                    masks.append(np.zeros((224, 224), bool))
            masks = np.stack(masks)
            cal_maps = np.stack(maps["calibration"]).astype(np.float64)
            test_maps = np.stack(maps["test"]).astype(np.float64)
            metrics, calibration_params = _unit_metrics(results["calibration"], results["test"], cal_maps, test_maps, masks)
            for i, row in enumerate(results["test"]):
                row["defect_type"] = str(test[i].metadata["defect_type"])
                if row["label"]:
                    row.update(_per_image_metrics(masks[i], test_maps[i]), defect_area_ratio=float(masks[i].mean()))
            per_image = output / "units" / f"{unit}.csv"
            _write_csv(per_image, results["calibration"] + results["test"])
            files = {p.relative_to(output).as_posix(): _checksum(p) for p in (payload, per_image)}
            receipt = {"unit": unit, "condition": condition, "restorer": restorer_name, "protocol_sha256": protocol_sha,
                       "files": files, "metrics": metrics, "calibration": calibration_params,
                       "means": {k: float(np.mean([r[k] for r in results["test"]])) for k in quality_names},
                       "timing_seconds": {**timing, "unit_inclusive": time.perf_counter() - unit_started},
                       "images": {"calibration": len(results["calibration"]), "test": len(results["test"])}}
            receipt_path.write_text(json.dumps(receipt, indent=1), encoding="utf-8")  # Written last.
            session["units_run"].append(unit)
            done += 1
            print(json.dumps({"unit": unit, "au_pro": metrics["au_pro"], "seconds": receipt["timing_seconds"]["unit_inclusive"]}), flush=True)
    receipts = [json.loads((output / "units" / f"{c}__{r}.json").read_text(encoding="utf-8"))
                for c in rd.CONDITIONS for r in rd.RESTORERS if (output / "units" / f"{c}__{r}.json").is_file()]
    _write_csv(output / "summary.csv", [{"category": args.category, "condition": r["condition"], "restorer": r["restorer"],
                                          **{f"mean_{k}": v for k, v in r["means"].items()}, **r["metrics"],
                                          "unit_seconds": r["timing_seconds"]["unit_inclusive"]} for r in receipts])
    session.update(end=time.strftime("%Y-%m-%dT%H:%M:%S"), wall_seconds=time.perf_counter() - wall, units_complete=len(receipts),
                   units_planned=len(rd.CONDITIONS) * len(rd.RESTORERS), bank=bank_meta, device=str(device),
                   gpu=torch.cuda.get_device_name(0) if args.device == "cuda" else None, argv=sys.argv)
    sessions = output / "sessions"
    sessions.mkdir(exist_ok=True)
    (sessions / f"{len(list(sessions.glob('*.json'))):03d}.json").write_text(json.dumps(session, indent=1), encoding="utf-8")
    print(json.dumps({"category": args.category, "units_complete": len(receipts), "planned": session["units_planned"]}))


if __name__ == "__main__":
    main()
