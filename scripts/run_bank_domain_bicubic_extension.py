"""Bank-domain extension: a bicubic-restored normal bank, seed 11, queried with bicubic_x4 and swinir_x4.

The extension adds 4 conditions (2 categories x 1 bank x 2 queries) as a separate family. The bank is fitted on the
same fit images as the base run, after the same PIL bicubic 224 -> 56 -> 224 round trip used for the bicubic_x4
query. The clean-bank reference cells are reused from the completed base run of the same category and seed; this
script checks that split paths and query RGB hashes are identical to that run. Functions are imported from
scripts/run_bank_domain_study.py unchanged; this file does not modify the base runner.
"""
from __future__ import annotations

import argparse
import csv
import gc
import importlib.util
import json
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
_spec = importlib.util.spec_from_file_location("bank_runner", ROOT / "scripts" / "run_bank_domain_study.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)
study, branch_b = runner.study, runner.branch_b
BANK = "bicubic_restored"
SEED = 11


class _BicubicBankDataset(runner._BankDomainDataset):
    def __getitem__(self, local_index):
        source_index = self.indices[local_index]
        classname, anomaly, image_path, _ = self.base.data_to_iterate[source_index]
        with Image.open(image_path) as source:
            clean = branch_b._canonical(source.convert("RGB"), self.resize, self.crop)
        image = clean.resize((56, 56), Image.Resampling.BICUBIC).resize((runner.IMAGE_SIZE, runner.IMAGE_SIZE), Image.Resampling.BICUBIC)
        return {"image": self.transforms(image), "mask": self.torch.zeros((1, runner.IMAGE_SIZE, runner.IMAGE_SIZE)),
                "classname": classname, "anomaly": anomaly, "is_anomaly": 0, "image_name": Path(image_path).as_posix(),
                "image_path": str(image_path)}


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def run(args) -> Path:
    category = args.category
    base_dir = args.base_run.resolve()
    base = json.loads((base_dir / "status.json").read_text(encoding="utf-8"))
    if base.get("status") != "COMPLETE" or base["category"] != category or int(base["seed"]) != SEED:
        raise ValueError("base run must be the COMPLETE seed-11 run of the same category")
    data_root = args.data_root.resolve()
    runner._load_dataset_provenance(args.data_root / "dataset_provenance.json", data_root, category)
    torch, transforms, InterpolationMode, backbones, common, patchcore, sampler, mvtec = branch_b._official_imports()
    device = torch.device("cuda")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    checkpoint, backbone_checkpoint = args.swinir_checkpoint.resolve(), args.backbone_checkpoint.resolve()
    if branch_b._checksum(checkpoint) != runner.EXPECTED_SWINIR_SHA256 or branch_b._checksum(backbone_checkpoint) != runner.EXPECTED_WIDERESNET_SHA256:
        raise ValueError("checkpoint SHA mismatch")
    torch.set_num_threads(min(4, torch.get_num_threads()))
    torch.manual_seed(SEED)
    resize = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    crop = transforms.CenterCrop(runner.IMAGE_SIZE)
    tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])
    train_set = mvtec.MVTecDataset(str(data_root), category, resize=256, imagesize=runner.IMAGE_SIZE, split=mvtec.DatasetSplit.TRAIN)
    fit_indices, calibration_indices = runner.split_train_calibration(len(train_set), 0.8, SEED)
    fit_paths = [Path(train_set.data_to_iterate[i][2]).relative_to(data_root).as_posix() for i in fit_indices]
    cal_paths = [Path(train_set.data_to_iterate[i][2]).relative_to(data_root).as_posix() for i in calibration_indices]
    if fit_paths != base["fit_paths"] or cal_paths != base["calibration_paths"]:
        raise ValueError("fit/calibration split differs from the base run")
    test_samples = runner.MVTecADFolder(data_root, category, split="test", require_masks=True).samples()
    if [s.relative_path.as_posix() for s in test_samples] != base["test_samples"]:
        raise ValueError("test order differs from the base run")
    calibration_samples = [runner.ImageSample(sample_id=p, path=data_root / p, relative_path=Path(p), mask_path=None,
                                              metadata={"category": category, "split": "train", "label": 0, "defect_type": "good"})
                           for p in cal_paths]
    plan = study.bank_fit_plan(len(fit_indices), batch_size=8)
    study.check_fit_ram(plan)
    run_dir = args.output_root.resolve() / args.run_id / category / f"seed{SEED}_{BANK}"
    if run_dir.exists():
        raise FileExistsError(run_dir)
    run_dir.mkdir(parents=True)
    state = dict(schema_version=1, status="BUILDING", scope="bank-domain-bicubic-bank-extension", family="patchcore_bank_domain_bicubic_extension_v1",
                 run_id=args.run_id, category=category, seed=SEED, bank_domain=BANK, query_domains=list(study.QUERY_DOMAINS),
                 base_run=dict(run_id=base["run_id"], status_sha256=study.sha256_file(base_dir / "status.json"), source_commit=base.get("source_commit")),
                 fit_paths=fit_paths, calibration_paths=cal_paths, test_samples=base["test_samples"], resource_plan=plan,
                 source_commit=branch_b.subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                 git_dirty=bool(branch_b.subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
                 command=[sys.executable, *sys.argv],
                 model_configuration=dict(base.get("model_configuration", {}), swinir_checkpoint_sha256=runner.EXPECTED_SWINIR_SHA256,
                                          backbone_checkpoint_sha256=runner.EXPECTED_WIDERESNET_SHA256),
                 bank_fit_rule="PIL bicubic 224->56->224 of each canonical clean fit image")
    study.write_status(run_dir, state)
    try:
        restorer = runner.SwinIRLightweight(ROOT / "third_party" / "SwinIR", checkpoint, device="cuda", scale=4, tile=56, tile_overlap=0)
        cache, query_hashes = {}, {}
        for sample in calibration_samples + test_samples:
            sid = sample.relative_path.as_posix()
            _, bicubic, restored, _ = runner._query_variants(sample.path, restorer, resize, crop)
            cache[sid] = {"bicubic_x4": bicubic, "swinir_x4": restored}
            query_hashes[sid] = {"bicubic_x4": runner._rgb_sha(bicubic), "swinir_x4": runner._rgb_sha(restored)}
        if set(query_hashes) != set(base["query_rgb_sha256"]):
            raise ValueError("query image set differs from the base run")
        mismatch = [s for s in query_hashes if query_hashes[s] != base["query_rgb_sha256"][s]]
        if mismatch:
            raise ValueError(f"query RGB differs from the base run for {len(mismatch)} images")
        del restorer
        gc.collect()
        torch.cuda.empty_cache()
        torch.manual_seed(SEED)  # same re-seed as the base runner before each bank
        torch.cuda.manual_seed_all(SEED)
        torch.cuda.reset_peak_memory_stats(device)
        model = runner._new_patchcore(torch, backbones, common, patchcore, sampler, device, backbone_checkpoint)
        loader = torch.utils.data.DataLoader(_BicubicBankDataset(train_set, fit_indices, BANK, None, resize, crop, tensor, torch),
                                             batch_size=8, shuffle=False, num_workers=0, pin_memory=False)
        t0 = time.perf_counter()
        model.fit(loader)
        torch.cuda.synchronize(device)
        fit_seconds = time.perf_counter() - t0
        bank = np.asarray(model.anomaly_scorer.detection_features)
        if bank.shape != (plan["fit_vectors"], 1024) or bank.dtype != np.float32 or not np.isfinite(bank).all():
            raise ValueError(f"unexpected bank {bank.shape} {bank.dtype}")
        bank_sha = study.sha256_array(bank)
        data = {}
        t0 = time.perf_counter()
        for q in study.QUERY_DOMAINS:
            data[q] = dict(zip(("cal_scores", "cal_maps", "cal_t"), runner._predict_all(model, tensor, cache, calibration_samples, q)))
            data[q].update(zip(("test_scores", "test_maps", "test_t"), runner._predict_all(model, tensor, cache, test_samples, q)))
        infer_seconds = time.perf_counter() - t0
        masks_npz = np.load(base_dir / "test_masks_for_local_analysis.npz")
        if [str(s) for s in masks_npz["samples"]] != base["test_samples"]:
            raise ValueError("mask order differs")
        masks = masks_npz["masks"].astype(bool)
        labels = np.asarray([s.metadata["label"] for s in test_samples], dtype=np.uint8)
        summary, per_image, calib = [], [], {}
        for q in study.QUERY_DOMAINS:
            cal = study.fit_cell_calibration(np.zeros(len(calibration_samples), np.uint8), data[q]["cal_scores"], data[q]["cal_maps"])
            metrics, rows = study.evaluate_cell(labels, data[q]["test_scores"], masks, data[q]["test_maps"], cal, base["test_samples"])
            calib[f"{BANK}/{q}"] = cal
            summary.append(dict(category=category, seed=SEED, bank_domain=BANK, query_domain=q, fit_count=len(fit_indices),
                                calibration_count=len(calibration_samples), test_count=len(test_samples),
                                image_auroc=metrics["classification"]["image_auroc"], image_f1=metrics["classification"]["image_f1"],
                                pixel_auroc=metrics["localization"]["pixel_auroc"], pooled_aupro_at_0_3=metrics["localization"]["au_pro"],
                                pixel_f1=metrics["localization"]["pixel_f1"], image_threshold=cal["image_threshold"], pixel_threshold=cal["pixel_threshold"]))
            defect = {s.relative_path.as_posix(): s.metadata.get("defect_type") for s in test_samples}
            per_image += [dict(r, category=category, seed=SEED, bank_domain=BANK, query_domain=q, defect_type=defect[r["sample"]]) for r in rows]
        np.savez_compressed(run_dir / f"raw_{BANK}.npz", test_samples=np.asarray(base["test_samples"]), query_domains=np.asarray(study.QUERY_DOMAINS),
                            bank_sha256=np.asarray(bank_sha),
                            calibration_scores=np.stack([data[q]["cal_scores"] for q in study.QUERY_DOMAINS], 1),
                            calibration_maps=np.stack([data[q]["cal_maps"] for q in study.QUERY_DOMAINS], 1),
                            test_scores=np.stack([data[q]["test_scores"] for q in study.QUERY_DOMAINS], 1),
                            test_maps=np.stack([data[q]["test_maps"] for q in study.QUERY_DOMAINS], 1))
        write_csv(run_dir / "summary.csv", summary)
        write_csv(run_dir / "per_image.csv", per_image)
        state.update(status="COMPLETE", bank_sha256=bank_sha, bank_vectors=int(bank.shape[0]), calibration_by_cell=calib,
                     runtime=dict(fit_seconds=fit_seconds, inference_seconds=infer_seconds,
                                  cuda_peak_allocated_bytes=int(torch.cuda.max_memory_allocated(device))),
                     query_rgb_matches_base=True,
                     artifacts={n: study.sha256_file(run_dir / n) for n in (f"raw_{BANK}.npz", "summary.csv", "per_image.csv")})
        study.write_status(run_dir, state)
        return run_dir
    except BaseException as error:
        state.update(status="FAILED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        study.write_status(run_dir, state)
        raise


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--category", choices=("hazelnut", "screw"), required=True)
    p.add_argument("--base-run", type=Path, required=True, help="completed base run directory <run-id>/<category>/seed11")
    p.add_argument("--swinir-checkpoint", type=Path, required=True)
    p.add_argument("--backbone-checkpoint", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    a = p.parse_args(argv)
    try:
        out = run(a)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"status": "FAILED", "error": f"{type(e).__name__}: {e}"}))
        return 1
    print(json.dumps({"status": "COMPLETE", "run_dir": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
