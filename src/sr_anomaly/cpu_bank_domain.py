"""CPU normal-bank domain controls using the existing HOG and exact evaluator."""
from __future__ import annotations

from pathlib import Path
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import time

import numpy as np
from PIL import Image

from .analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json
from .cpu_hog_control import HOGMemoryDetector, hog_descriptors, query_image, _guard
from .cpu_restoration_control import CHECKPOINT_SHA256
from .evaluation import evaluate_predictions, area_under_per_region_overlap, binary_roc_auc
from .fusion import robust_params, normalize, quantile_threshold
from .pcb_native_memory import process_memory

ROOT = Path(__file__).resolve().parents[2]
QUERIES = ("bicubic_x4", "swinir_x4")
NEW_BANKS = ("bicubic_matched", "swinir_restored")


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_hashes():
    paths = ("src/sr_anomaly/cpu_bank_domain.py", "src/sr_anomaly/cpu_hog_control.py",
             "src/sr_anomaly/cpu_restoration_control.py", "src/sr_anomaly/fusion.py",
             "src/sr_anomaly/evaluation.py", "src/sr_anomaly/metrics.py",
             "src/sr_anomaly/dataset.py", "src/sr_anomaly/analysis_io.py",
             "scripts/run_cpu_bank_domain_study.py", "configs/cpu_bank_domain_study.json")
    return {p: digest(ROOT / p) for p in paths}


class DomainInputs:
    def __init__(self, reference, restored_reference, cache):
        self.reference, self.restored_reference, self.cache = map(Path, (reference, restored_reference, cache))
        self.base = read_json(self.reference / "status.json")
        restored = read_json(self.restored_reference / "status.json")
        self.cached = read_json(self.cache / "status.json")
        if (self.base["status"] != "EVALUATED_COMPLETE" or restored["status"] != "EVALUATED_COMPLETE"
                or self.cached["status"] != "CPU_RESTORATION_CACHE_COMPLETE"):
            raise ValueError("Bank domain inputs are incomplete")
        if (self.base["source_code_sha256"] != digest(Path(__file__).with_name("cpu_hog_control.py"))
                or restored["bank_sha256"] != self.base["bank_sha256"]
                or digest(self.reference / "bank.npy") != self.base["bank_sha256"]):
            raise ValueError("Reference feature code/bank mismatch")
        self.settings = self.base["settings"]
        self.split = read_json(self.reference / "split.json")
        if (restored["category"], restored["seed"]) != (self.base["category"], self.base["seed"]):
            raise ValueError("Reference category/seed pairing differs")
        if (self.cached["binding"]["checkpoint_sha256"] != CHECKPOINT_SHA256
                or not self.cached["binding"].get("include_fit")):
            raise ValueError("Need the fixed checkpoint and full normal-fit restoration cache")
        groups = [set(self.split[name]) for name in ("fit_paths", "calibration_paths", "test_paths")]
        if any(groups[i] & groups[j] for i in range(3) for j in range(i + 1, 3)):
            raise ValueError("Fit, calibration and test overlap")
        if any("/train/good/" not in p for p in self.split["fit_paths"] + self.split["calibration_paths"]):
            raise ValueError("Only normal train RGB can fit bank/calibration")
        self.receipts = read_json(self.reference / "rgb_receipts.json")
        self.quality = {}
        for directory in (self.reference, self.restored_reference):
            for row in csv_rows(directory / "per_image_inference.csv"):
                if row["variant"] in QUERIES:
                    self.quality[row["sample"], row["variant"]] = {
                        k: row[k] for k in ("rgb_sha256", "psnr", "ssim")}
        self.indices = np.load(self.reference / "selected_indices.npy", allow_pickle=False)
        total = len(self.split["fit_paths"]) * 729
        expected = np.sort(np.random.default_rng(self.base["seed"]).choice(
            total, min(self.settings["bank_capacity"], total), replace=False))
        if not np.array_equal(self.indices, expected):
            raise ValueError("Selected patch ordinals differ from the fixed reference policy")
        bank = np.load(self.reference / "bank.npy", mmap_mode="r", allow_pickle=False)
        if bank.shape != (len(self.indices), 36) or bank.dtype != np.float32:
            raise ValueError("Reference bank shape/dtype differs from selected ordinals")
        bank._mmap.close()

    def image(self, sample, domain):
        if domain == "swinir_x4":
            receipt = self.cached["completed"][sample]
            path = relative_source(self.cache / "images", sample)
            if (receipt["input_sha256"] != self.receipts[sample]["canonical_file_sha256"]
                    or digest(path) != receipt["output_sha256"]):
                raise ValueError("Restored RGB/source mismatch")
            with Image.open(path) as image:
                return image.convert("RGB")
        path = relative_source(self.reference / "canonical", sample)
        if digest(path) != self.receipts[sample]["canonical_file_sha256"]:
            raise ValueError("Canonical RGB changed")
        with Image.open(path) as image:
            return query_image(image.convert("RGB"), domain, self.settings)


def fit_domain_bank(inputs, domain, output):
    from threadpoolctl import threadpool_limits
    if domain not in NEW_BANKS:
        raise ValueError("Only the two new normal-bank domains are fitted")
    _guard(inputs.settings["reserve_ram_bytes"] + inputs.settings["runtime_allowance_bytes"], "CPU domain bank fit")
    out = new_output(Path(output), [inputs.reference, inputs.cache])
    tick = time.perf_counter()
    values = np.empty((len(inputs.indices), 36), dtype=np.float32)
    cursor, observed, rgb = 0, 0, {}
    query = "bicubic_x4" if domain == "bicubic_matched" else "swinir_x4"
    with threadpool_limits(limits=inputs.settings["cpu_threads"]):
        for i, sample in enumerate(inputs.split["fit_paths"]):
            local = inputs.indices[(inputs.indices >= i * 729) & (inputs.indices < (i + 1) * 729)] - i * 729
            if not len(local):
                continue
            image = inputs.image(sample, query)
            features = hog_descriptors(image, inputs.settings)
            values[cursor:cursor + len(local)] = features[local]
            cursor += len(local)
            observed += len(features)
            rgb[sample] = hashlib.sha256(np.asarray(image).tobytes()).hexdigest()
    if cursor != len(values) or not np.isfinite(values).all():
        raise ValueError("Invalid fitted HOG bank")
    np.save(out / "bank.npy", values, allow_pickle=False)
    shutil.copyfile(inputs.reference / "selected_indices.npy", out / "selected_indices.npy")
    write_json(out / "fit_rgb_receipts.json", rgb)
    state = dict(kind="cpu_hog_domain_bank", status="BANK_COMPLETE", bank_domain=domain, device="cpu",
        category=inputs.base["category"], seed=inputs.base["seed"], stored_vectors=len(values),
        eligible_vectors=len(inputs.split["fit_paths"]) * 729, observed_descriptors=observed,
        descriptor_dimension=36, normal_fit_count=len(inputs.split["fit_paths"]),
        selected_indices_sha256=digest(out / "selected_indices.npy"), bank_sha256=digest(out / "bank.npy"),
        split_sha256=digest(inputs.reference / "split.json"), feature_source_sha256=inputs.base["source_code_sha256"],
        code_sha256=source_hashes(), elapsed_seconds=time.perf_counter() - tick, process_memory=process_memory())
    write_json(out / "status.json", state)
    return state


def infer_domain_query(inputs, bank_directory, query, output):
    from threadpoolctl import threadpool_limits
    bank_directory = Path(bank_directory)
    bank_state = read_json(bank_directory / "status.json")
    if query not in QUERIES or bank_state["status"] != "BANK_COMPLETE":
        raise ValueError("Invalid query or incomplete domain bank")
    if (bank_state["split_sha256"] != digest(inputs.reference / "split.json")
            or bank_state["selected_indices_sha256"] != digest(inputs.reference / "selected_indices.npy")
            or digest(bank_directory / "bank.npy") != bank_state["bank_sha256"]):
        raise ValueError("Bank/split/ordinal binding changed")
    cal, test = inputs.split["calibration_paths"], inputs.split["test_paths"]
    required = inputs.settings["reserve_ram_bytes"] + inputs.settings["runtime_allowance_bytes"] + (len(cal) * 3 + len(test)) * 224 * 224 * 4
    guard = _guard(required, "CPU domain query")
    out = new_output(Path(output), [inputs.reference, inputs.cache, bank_directory])
    tick = time.perf_counter()
    with threadpool_limits(limits=inputs.settings["cpu_threads"]):
        bank = np.load(bank_directory / "bank.npy", mmap_mode="r", allow_pickle=False)
        model = HOGMemoryDetector(bank, inputs.settings)
        cal_maps, cal_scores = np.empty((len(cal), 224, 224), dtype=np.float32), np.empty(len(cal))
        for i, sample in enumerate(cal):
            prediction = model.predict(inputs.image(sample, query))
            cal_maps[i], cal_scores[i] = prediction.pixel_map, prediction.image_score
        image_params, pixel_params = robust_params(cal_scores), robust_params(cal_maps)
        params = dict(image_params=image_params, pixel_params=pixel_params,
            image_threshold=quantile_threshold(normalize(cal_scores, image_params), inputs.settings["normal_quantile"]),
            pixel_threshold=quantile_threshold(normalize(cal_maps, pixel_params), inputs.settings["normal_quantile"]),
            normal_calibration_count=len(cal))
        del cal_maps, cal_scores
        maps, scores, rows = np.empty((len(test), 224, 224), dtype=np.float32), np.empty(len(test)), []
        for i, sample in enumerate(test):
            image = inputs.image(sample, query)
            quality = inputs.quality[sample, query]
            rgb_sha = hashlib.sha256(np.asarray(image).tobytes()).hexdigest()
            if rgb_sha != quality["rgb_sha256"]:
                raise ValueError("Same-query RGB differs from the clean-bank reference")
            prediction = model.predict(image)
            maps[i], scores[i] = normalize(prediction.pixel_map, pixel_params), float(normalize(np.asarray(prediction.image_score), image_params))
            rows.append(dict(sample=sample, bank_domain=bank_state["bank_domain"], query_domain=query,
                image_score=float(scores[i]), rgb_sha256=rgb_sha, psnr=quality["psnr"], ssim=quality["ssim"]))
        del model, bank
    np.savez_compressed(out / "query_predictions.npz", maps=maps, scores=scores)
    write_json(out / "calibration.json", params)
    write_csv(out / "query_rows.csv", rows)
    if digest(bank_directory / "bank.npy") != bank_state["bank_sha256"]:
        raise ValueError("Bank changed during query")
    state = dict(status="QUERY_COMPLETE", device="cpu", category=inputs.base["category"], seed=inputs.base["seed"],
        bank_domain=bank_state["bank_domain"], query_domain=query, n_test=len(test),
        bank_sha256=bank_state["bank_sha256"], prediction_sha256=digest(out / "query_predictions.npz"),
        query_rows_sha256=digest(out / "query_rows.csv"), calibration_sha256=digest(out / "calibration.json"), guard=guard,
        code_sha256=source_hashes(), elapsed_seconds=time.perf_counter() - tick, process_memory=process_memory())
    write_json(out / "status.json", state)
    return state


def evaluate_domain_query(inputs, directory):
    directory = Path(directory)
    state = read_json(directory / "status.json")
    if state["status"] != "QUERY_COMPLETE" or digest(directory / "query_predictions.npz") != state["prediction_sha256"]:
        raise ValueError("Query predictions are incomplete or changed")
    if (digest(directory / "query_rows.csv") != state["query_rows_sha256"]
            or digest(directory / "calibration.json") != state["calibration_sha256"]):
        raise ValueError("Query metadata/calibration changed")
    _guard(inputs.settings["reserve_ram_bytes"] + state["n_test"] * 224 * 224 * 45, "CPU domain exact evaluation")
    source = inputs.reference / "bicubic_x4_predictions.npz"
    if digest(source) != inputs.base["prediction_sha256"]["bicubic_x4"]:
        raise ValueError("GT-bearing reference prediction changed")
    with np.load(source, allow_pickle=False) as archive:
        labels, masks = archive["labels"], archive["masks"]
    with np.load(directory / "query_predictions.npz", allow_pickle=False) as archive:
        maps, scores = archive["maps"], archive["scores"]
    params = read_json(directory / "calibration.json")
    tick = time.perf_counter()
    metrics = evaluate_predictions(labels, scores, masks, maps, image_threshold=params["image_threshold"],
        pixel_threshold=params["pixel_threshold"], max_fpr=0.3)
    rows = csv_rows(directory / "query_rows.csv")
    for i, row in enumerate(rows):
        mask = masks[i].astype(bool)
        row.update(label=int(labels[i]), defect_type=Path(row["sample"]).parent.name,
            per_image_aupro=area_under_per_region_overlap(mask[None], maps[i:i + 1], max_fpr=0.3, num_thresholds=200) if mask.any() else None,
            per_image_pixel_auroc=binary_roc_auc(mask.ravel(), maps[i].ravel()) if mask.any() and (~mask).any() else None,
            roi_bg_gap=float(maps[i][mask].mean() - maps[i][~mask].mean()) if mask.any() and (~mask).any() else None)
    summary = dict(bank_domain=state["bank_domain"], query_domain=state["query_domain"],
        n_test=len(labels), n_anomaly=int(labels.sum()), pooled_aupro=metrics["localization"]["au_pro"],
        pixel_auroc=metrics["localization"]["pixel_auroc"], image_auroc=metrics["classification"]["image_auroc"],
        image_f1=metrics["classification"]["image_f1"], pixel_f1=metrics["localization"]["pixel_f1"],
        mean_psnr=float(np.mean([float(r["psnr"]) for r in rows])),
        mean_ssim=float(np.mean([float(r["ssim"]) for r in rows])))
    write_csv(directory / "summary.csv", [summary])
    write_csv(directory / "per_image.csv", rows)
    write_json(directory / "evaluation.json", metrics)
    state.update(status="EVALUATED_COMPLETE", evaluation_seconds=time.perf_counter() - tick,
        evaluation_process_memory=process_memory(), artifact_sha256={name: digest(directory / name)
            for name in ("summary.csv", "per_image.csv", "evaluation.json")})
    write_json(directory / "status.json", state)
    return state


def export_core_matrix(inputs, domain_root, output, *, evidence_kind="model_predictions"):
    domain_root = Path(domain_root)
    out = new_output(Path(output), [inputs.reference, inputs.restored_reference, domain_root])
    summary, images = [], []
    for query, reference in (("bicubic_x4", inputs.reference), ("swinir_x4", inputs.restored_reference)):
        state = read_json(reference / "status.json")
        for name, sha in state["artifact_sha256"].items():
            if digest(reference / name) != sha:
                raise ValueError("Reference evaluation changed")
        row = next(r for r in csv_rows(reference / "summary.csv") if r["variant"] == query)
        own = [r for r in csv_rows(reference / "per_image.csv") if r["variant"] == query]
        summary.append(dict(bank_domain="clean", query_domain=query, n_test=row["test_count"],
            n_anomaly=sum(int(r["label"]) for r in own), pooled_aupro=row["au_pro"],
            pixel_auroc=row["pixel_auroc"], image_auroc=row["image_auroc"],
            mean_psnr=row["mean_psnr"], mean_ssim=row["mean_ssim"]))
        images.extend(dict(r, bank_domain="clean", query_domain=query,
                           defect_type=Path(r["sample"]).parent.name) for r in own)
        directory = domain_root / "swinir_restored" / query
        state = read_json(directory / "status.json")
        if state["status"] != "EVALUATED_COMPLETE":
            raise ValueError("New restored-bank condition is incomplete")
        for name, sha in state["artifact_sha256"].items():
            if digest(directory / name) != sha:
                raise ValueError("Domain evaluation changed")
        summary.extend(csv_rows(directory / "summary.csv"))
        images.extend(csv_rows(directory / "per_image.csv"))
    packages = {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-image", "scikit-learn", "Pillow")}
    config = dict(study_family="cpu_hog_bank_domain_v1", category=inputs.base["category"], seed=inputs.base["seed"],
        protocol=dict(dataset="MVTecAD" if evidence_kind == "model_predictions" else "synthetic",
            geometry_id="pillow_short256_bilinear_center224_mask_nearest", degradation_id="pillow_bicubic_224_56_224_x4",
            detector_id="skimage_hog36_sklearn_exact_euclidean_1nn", restorer_id="SwinIR-S_x4",
            calibration_source="normal_calibration_only", metric_definition=dict(primary="pooled_aupro", max_fpr=0.3, num_thresholds=200, connectivity=4),
            bank_spec=dict(capacity=inputs.settings["bank_capacity"], dimension=36,
                selection="same clean-reference patch ordinals", packages=packages),
            checkpoints_sha256=dict(swinir=CHECKPOINT_SHA256)))
    code = source_hashes()
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, encoding="utf-8").strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--ignore-submodules=all"], cwd=ROOT, encoding="utf-8").strip())
    provenance = dict(source_commit=source_commit, source_worktree_dirty=dirty,
        normal_fit_calibration_disjoint=True, test_gt_used_for_selection=False,
        input_manifest_sha256=inputs.base["input_inventory_sha256"] or object_sha(inputs.receipts),
        split_manifest_sha256=digest(inputs.reference / "split.json"),
        test_manifest_sha256=object_sha(inputs.split["test_paths"]),
        query_manifest_sha256=object_sha(sorted((sample, query, row)
                                              for (sample, query), row in inputs.quality.items())),
        bank_manifest_sha256=dict(clean=digest(inputs.reference / "status.json"),
            swinir_restored=digest(domain_root / "swinir_restored/bank/status.json")),
        bank_vector_counts=dict(clean=len(inputs.indices), swinir_restored=len(inputs.indices)), code_sha256=code,
        clean_reference_results_reused=True, reference_prediction_sha256=inputs.base["prediction_sha256"])
    write_json(out / "config.json", config)
    write_json(out / "provenance.json", provenance)
    write_csv(out / "summary.csv", summary)
    write_csv(out / "per_image.csv", images)
    manifest = dict(kind="bank_domain_study_results", schema_version=1, status="COMPLETE", evidence_kind=evidence_kind,
        files={name: digest(out / name) for name in ("summary.csv", "per_image.csv", "config.json", "provenance.json")})
    write_json(out / "bank_domain_manifest.json", manifest)
    return manifest
