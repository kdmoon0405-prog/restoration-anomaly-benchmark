"""Realistic-LR noise family v2 for ONE category and ONE noise seed (8 units: sigma {5,15} x 4 restorers).

Reuses the v1 run's clean-normal bank BYTES (hash-verified, never refit) and v1's fixed fit/calibration/test paths,
224->56->224 geometry, checkpoints, robust/q0.99 normal calibration per unit and CPU IndexFlatL2 exact search
(FaissNN(False, 4)). GT masks are loaded only after a unit's predictions are saved (evaluation only).
Resumable per unit (receipt written last, verified on resume). v1 code and results are not modified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image, features
import PIL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from sr_anomaly import realistic_degradation as rd  # noqa: E402
from sr_anomaly import realistic_noise_v2 as v2  # noqa: E402

CODE = ("scripts/run_realistic_noise_v2.py", "src/sr_anomaly/realistic_noise_v2.py", "scripts/run_realistic_degradation.py",
        "src/sr_anomaly/realistic_degradation.py", "src/sr_anomaly/evaluation.py", "src/sr_anomaly/fusion.py",
        "src/sr_anomaly/metrics.py", "src/sr_anomaly/real_models.py", "scripts/run_legacy_patchcore.py",
        "scripts/run_restoration_objective_pilot.py")


def source_state(root=ROOT) -> dict:
    def git(*a):
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()
    status = git("status", "--porcelain", "--untracked-files=no")
    untracked = git("status", "--porcelain", "--untracked-files=normal").splitlines()
    untracked = [line for line in untracked if line.startswith("??")]
    return dict(source_commit=git("rev-parse", "HEAD"), source_branch=git("rev-parse", "--abbrev-ref", "HEAD"),
                tracked_worktree_dirty=bool(status), tracked_dirty_paths=status.splitlines(),
                source_worktree_dirty=bool(status) or bool(untracked), untracked_paths=untracked)


def run_units(*, output: Path, category: str, noise_seed: int, protocol_sha: str, calibration_clean: dict, test_clean: dict,
              test_meta: list[dict], lr: dict, restorers: dict, predict, quality, load_masks, unit_metrics, per_image_metrics,
              checksum, write_csv, max_units=None, log=print) -> dict:
    """Unit loop. test_meta: [{sample,label,defect_type}] in test order. predict(PIL)->(score, map[224,224])."""
    (output / "units").mkdir(exist_ok=True)
    session = {"units_run": [], "units_skipped": []}
    shared_lr: dict[tuple[str, str], str] = {}  # (condition, sample) -> degraded LR sha, must match across restorers
    done = 0
    for condition in v2.conditions():
        for restorer_name in v2.RESTORERS:
            unit = f"{condition}__{restorer_name}"
            receipt_path = output / "units" / f"{unit}.json"
            if receipt_path.is_file():
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if receipt["protocol_sha256"] != protocol_sha or any(checksum(output / f) != h for f, h in receipt["files"].items()):
                    raise ValueError(f"Unit {unit} receipt/payload differs; resume refused")
                for key, h in receipt["degraded_lr_sha256"].items():
                    if shared_lr.setdefault((condition, key), h) != h:
                        raise ValueError("Degraded LR bytes differ across restorers")
                session["units_skipped"].append(unit)
                continue
            if max_units is not None and done >= max_units:
                continue
            started = time.perf_counter()
            restore = restorers[restorer_name]
            results = {"calibration": [], "test": []}
            maps = {"calibration": [], "test": []}
            timing = {"restore": 0.0, "predict": 0.0, "quality": 0.0}
            lr_hashes = {}
            labels = {m["sample"]: m for m in test_meta}
            for split, references in (("calibration", calibration_clean), ("test", test_clean)):
                for sample, reference in references.items():
                    degraded_array = v2.degrade(lr[sample], condition, v2.sample_seed(category, sample, condition, noise_seed))
                    h = v2.lr_sha256(degraded_array)
                    if shared_lr.setdefault((condition, sample), h) != h:
                        raise ValueError("Degraded LR bytes differ across restorers")
                    lr_hashes[sample] = h
                    degraded = Image.fromarray(degraded_array, "RGB")
                    t = time.perf_counter(); restored = restore(degraded); timing["restore"] += time.perf_counter() - t
                    if restored.size != (224, 224) or restored.mode != "RGB":
                        raise ValueError("Restorer output must be RGB 224x224")
                    t = time.perf_counter(); q = quality(reference, restored); timing["quality"] += time.perf_counter() - t
                    t = time.perf_counter(); score, amap = predict(restored); timing["predict"] += time.perf_counter() - t
                    maps[split].append(np.asarray(amap, dtype=np.float32))
                    row = {"sample": sample, "split": split, "condition": condition, "noise_seed": noise_seed,
                           "restorer": restorer_name, "label": 0 if split == "calibration" else int(labels[sample]["label"]),
                           "image_score": float(score), "degraded_lr_sha256": h, **q}
                    results[split].append(row)
            payload = output / "units" / f"{unit}.npz"
            np.savez(payload, calibration_maps=np.stack(maps["calibration"]), test_maps=np.stack(maps["test"]),
                     calibration_scores=np.asarray([r["image_score"] for r in results["calibration"]]),
                     test_scores=np.asarray([r["image_score"] for r in results["test"]]))
            masks = load_masks()  # evaluation only, after predictions are saved
            cal_maps = np.stack(maps["calibration"]).astype(np.float64)
            test_maps = np.stack(maps["test"]).astype(np.float64)
            metrics, calibration_params = unit_metrics(results["calibration"], results["test"], cal_maps, test_maps, masks)
            for i, row in enumerate(results["test"]):
                row["defect_type"] = test_meta[i]["defect_type"]
                if row["label"]:
                    row.update(per_image_metrics(masks[i], test_maps[i]), defect_area_ratio=float(masks[i].mean()))
            per_image = output / "units" / f"{unit}.csv"
            write_csv(per_image, results["calibration"] + results["test"])
            quality_keys = [k for k in results["test"][0] if k in ("psnr", "ssim", "lpips")]
            receipt = {"unit": unit, "category": category, "condition": condition, "noise_seed": noise_seed, "split_seed": v2.SPLIT_SEED,
                       "restorer": restorer_name, "protocol_sha256": protocol_sha,
                       "files": {p.relative_to(output).as_posix(): checksum(p) for p in (payload, per_image)},
                       "degraded_lr_sha256": lr_hashes, "metrics": metrics, "calibration": calibration_params,
                       "means": {k: float(np.mean([r[k] for r in results["test"]])) for k in quality_keys},
                       "timing_seconds": {**timing, "unit_inclusive": time.perf_counter() - started},
                       "images": {"calibration": len(results["calibration"]), "test": len(results["test"])}}
            receipt_path.write_text(json.dumps(receipt, indent=1), encoding="utf-8")  # written last
            session["units_run"].append(unit)
            done += 1
            log(json.dumps({"unit": unit, "noise_seed": noise_seed, "au_pro": metrics["au_pro"],
                            "seconds": receipt["timing_seconds"]["unit_inclusive"]}))
    return session


def main(argv=None) -> int:
    from run_realistic_degradation import COUNTS, _bank, _unit_metrics, _write_csv
    from run_legacy_patchcore import EXPECTED_SWINIR_X4_SHA256, _canonical, _checksum, _official_imports
    from run_restoration_objective_pilot import _per_image_metrics, _require_file_hash
    from sr_anomaly.dataset import MVTecADFolder
    from sr_anomaly.metrics import compute_quality_metrics
    from sr_anomaly.real_models import SwinIRLightweight, matlab_bicubic_resize
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=v2.CATEGORIES, required=True)
    parser.add_argument("--noise-seed", type=int, choices=v2.NOISE_SEEDS, required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--v1-dir", type=Path, help="v1 run whose bank bytes and paths are reused (default outputs/realistic-degradation/<cat>-v1)")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--with-lpips", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-units", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    wall = time.perf_counter()
    start_time = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    v1_dir = (args.v1_dir or ROOT / "outputs/realistic-degradation" / f"{args.category}-v1").resolve()
    output = (args.output_dir or ROOT / "outputs/realistic-noise-v2" / f"{args.category}-noise{args.noise_seed}").resolve()
    if not args.resume and output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output exists; use --resume: {output}")
    v1_protocol = json.loads((v1_dir / "PROTOCOL.json").read_text(encoding="utf-8"))
    bank_meta_path = v1_dir / "bank" / "metadata.json"
    if not bank_meta_path.is_file():
        raise ValueError("v1 bank metadata missing; v2 never fits a bank")
    bank_meta = json.loads(bank_meta_path.read_text(encoding="utf-8"))
    data = args.data_root.resolve()
    folder = MVTecADFolder(data, args.category)
    test = sorted(folder.samples(), key=lambda s: s.relative_path.as_posix())
    train = sorted(p.relative_to(data).as_posix() for p in (data / args.category / "train" / "good").glob("*.png"))
    if (len(train), len(test), sum(int(s.metadata["label"]) == 0 for s in test), sum(int(s.metadata["label"]) == 1 for s in test)) != COUNTS[args.category]:
        raise ValueError("Category cohort counts changed")
    fit, calibration = rd.split_train(train)
    test_rows = [{"sample": s.relative_path.as_posix(), "label": int(s.metadata["label"]), "defect_type": str(s.metadata["defect_type"]),
                  "image_sha256": _checksum(s.path), "mask_sha256": _checksum(s.mask_path) if s.mask_path else ""} for s in test]
    if fit != v1_protocol["fit_paths"] or calibration != v1_protocol["calibration_paths"] or test_rows != v1_protocol["test"]:
        raise ValueError("Fit/calibration/test paths differ from v1")
    train_sha = {p: _checksum(data / p) for p in train}
    if train_sha != v1_protocol["train_sha256"]:
        raise ValueError("Train bytes differ from v1")
    for name, path in (("SwinIR x4", ROOT / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth"),
                       ("RealESRNet", ROOT / "checkpoints/realesrgan/RealESRNet_x4plus.pth"),
                       ("RealESRGAN", ROOT / "checkpoints/realesrgan/RealESRGAN_x4plus.pth")):
        _require_file_hash(path, {"SwinIR x4": EXPECTED_SWINIR_X4_SHA256, "RealESRNet": rd.CHECKPOINTS["realesrnet_x4plus"][1],
                                  "RealESRGAN": rd.CHECKPOINTS["realesrgan_x4plus"][1]}[name], name)
    if v1_protocol["checkpoints"] != {"swinir_x4": EXPECTED_SWINIR_X4_SHA256, **{k: v[1] for k, v in rd.CHECKPOINTS.items()}}:
        raise ValueError("Checkpoint identities differ from v1")
    src = source_state()
    protocol = {"family": v2.FAMILY, "category": args.category, "noise_seed": args.noise_seed, "split_seed": v2.SPLIT_SEED,
                "conditions": list(v2.conditions()), "restorers": list(v2.RESTORERS), "quantile": 0.99,
                "noise_definition": "v1: LR uint8 + float64 N(0,sigma^2) iid per pixel/channel, rint, clip; seed=sha256(family|split_seed|noise_seed|category|sample|condition)[:8] LE",
                "geometry": "Resize(256,bilinear)+CenterCrop(224) -> BasicSR MATLAB bicubic x0.25 (56) -> restorer x4 (224)",
                "fit_paths": fit, "calibration_paths": calibration, "test": test_rows, "train_sha256": train_sha,
                "v1_protocol_sha256": _checksum(v1_dir / "PROTOCOL.json"), "v1_bank_dir": str(v1_dir / "bank"),
                "bank_artifact_sha256": bank_meta["artifact_sha256"], "bank_fit_images": bank_meta["fit_images"], "bank_refit": False,
                "search": "PatchCore FaissNN(on_gpu=False, num_workers=4): CPU IndexFlatL2 exact, k=1",
                "code_sha256": {n: _checksum(ROOT / n) for n in CODE}, "checkpoints": v1_protocol["checkpoints"],
                "revisions": v1_protocol["revisions"],
                "versions": {"python": sys.version, "numpy": np.__version__, "pillow": PIL.__version__, "libjpeg": features.version("jpg"),
                             "torch": __import__("torch").__version__},
                "realesrgan_precision": v1_protocol["realesrgan_precision"], "lpips": args.with_lpips,
                "gt_use": "evaluation only, loaded after unit predictions are saved"}
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
    t0 = time.perf_counter()
    model, loaded_meta = _bank(v1_dir, device, torch, common, patchcore, sampler, backbones, [], to_tensor)  # load-only path
    if loaded_meta["artifact_sha256"] != bank_meta["artifact_sha256"]:
        raise ValueError("Loaded bank differs from v1 metadata")
    bank_seconds = time.perf_counter() - t0
    basicsr = ROOT / "third_party" / "BasicSR"
    lr = {k: np.asarray(matlab_bicubic_resize(v, 0.25, basicsr)) for k, v in (calibration_clean | test_clean).items()}
    restorers = {"bicubic_x4": lambda image: matlab_bicubic_resize(image, 4.0, basicsr),
                 "swinir_x4": SwinIRLightweight(ROOT / "third_party/SwinIR", ROOT / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth",
                                                device=str(device), scale=4, tile=56, tile_overlap=0).restore,
                 "realesrnet_x4plus": rd.RealESRGANX4(basicsr, ROOT / "checkpoints/realesrgan/RealESRNet_x4plus.pth", "realesrnet_x4plus", str(device)).restore,
                 "realesrgan_x4plus": rd.RealESRGANX4(basicsr, ROOT / "checkpoints/realesrgan/RealESRGAN_x4plus.pth", "realesrgan_x4plus", str(device)).restore}
    quality_names = ("psnr", "ssim", "lpips") if args.with_lpips else ("psnr", "ssim")

    def predict(restored):
        scores, anomaly_maps = model.predict(to_tensor(restored).unsqueeze(0))
        if args.device == "cuda":
            torch.cuda.synchronize()
        return float(scores[0]), anomaly_maps[0]

    def quality(reference, restored):
        q = compute_quality_metrics(reference, restored, quality_names, lpips_device="cpu")
        return {k: q.get(k) for k in quality_names}

    def load_masks():
        masks = []
        for s in test:
            if s.mask_path:
                with Image.open(s.mask_path) as source:
                    masks.append(np.asarray(_canonical(source.convert("L"), resize_mask, crop)) > 0)
            else:
                masks.append(np.zeros((224, 224), bool))
        return np.stack(masks)

    session = run_units(output=output, category=args.category, noise_seed=args.noise_seed, protocol_sha=protocol_sha,
                        calibration_clean=calibration_clean, test_clean=test_clean, test_meta=test_rows, lr=lr, restorers=restorers,
                        predict=predict, quality=quality, load_masks=load_masks, unit_metrics=_unit_metrics,
                        per_image_metrics=_per_image_metrics, checksum=_checksum, write_csv=_write_csv, max_units=args.max_units,
                        log=lambda s: print(s, flush=True))
    receipts = [json.loads((output / "units" / f"{c}__{r}.json").read_text(encoding="utf-8"))
                for c in v2.conditions() for r in v2.RESTORERS if (output / "units" / f"{c}__{r}.json").is_file()]
    _write_csv(output / "summary.csv", [{"category": args.category, "noise_seed": r["noise_seed"], "split_seed": r["split_seed"],
                                         "condition": r["condition"], "restorer": r["restorer"],
                                         **{f"mean_{k}": v for k, v in r["means"].items()}, **r["metrics"],
                                         "unit_seconds": r["timing_seconds"]["unit_inclusive"]} for r in receipts])
    session.update(start=start_time, wall_seconds=time.perf_counter() - wall, end=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   bank_load_seconds=bank_seconds, units_complete=len(receipts), units_planned=len(v2.conditions()) * len(v2.RESTORERS),
                   device=str(device), gpu=torch.cuda.get_device_name(0) if args.device == "cuda" else None, argv=sys.argv, **src)
    sessions = output / "sessions"
    sessions.mkdir(exist_ok=True)
    (sessions / f"{len(list(sessions.glob('*.json'))):03d}.json").write_text(json.dumps(session, indent=1), encoding="utf-8")
    print(json.dumps({"category": args.category, "noise_seed": args.noise_seed, "units_complete": len(receipts),
                      "planned": session["units_planned"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
