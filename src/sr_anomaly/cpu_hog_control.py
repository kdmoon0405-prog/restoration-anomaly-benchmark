"""Real CPU HOG nearest-normal controls using trusted feature/search libraries."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import gc
import hashlib
import math
import time

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import map_coordinates

from .analysis_io import csv_rows, digest, new_output, read_json, write_csv, write_json
from .dataset import MVTecADFolder
from .fusion import split_train_calibration, robust_params, normalize, quantile_threshold
from .metrics import psnr, ssim
from .models import AnomalyPrediction
from .pcb_native_memory import available_ram, process_memory


def canonical(image, *, mask=False):
    width, height = image.size
    if width <= height:
        size = 256, int(height * 256 / width)
    else:
        size = int(width * 256 / height), 256
    resized = image.resize(size, Image.Resampling.NEAREST if mask else Image.Resampling.BILINEAR)
    left, top = round((size[0] - 224) / 2), round((size[1] - 224) / 2)
    return resized.crop((left, top, left + 224, top + 224))


def query_image(clean, variant, settings):
    if variant == "clean":
        return clean.copy()
    low = clean.resize((56, 56), Image.Resampling.BICUBIC)
    bicubic = low.resize((224, 224), Image.Resampling.BICUBIC)
    if variant == "bicubic_x4":
        return bicubic
    if variant == "unsharp_x4":
        return bicubic.filter(ImageFilter.UnsharpMask(**settings["unsharp"]))
    raise ValueError("Unknown CPU query variant")


def hog_descriptors(image, settings):
    from skimage.color import rgb2gray
    from skimage.feature import hog
    gray = rgb2gray(np.asarray(image.convert("RGB"), dtype=np.float32) / 255)
    kwargs = dict(settings["hog"])
    kwargs["pixels_per_cell"] = tuple(kwargs["pixels_per_cell"])
    kwargs["cells_per_block"] = tuple(kwargs["cells_per_block"])
    values = hog(gray, feature_vector=False, **kwargs)
    if values.shape != (27, 27, 2, 2, 9):
        raise ValueError("Unexpected HOG grid; this protocol fixes canonical224")
    return np.asarray(values.reshape(729, 36), dtype=np.float32)


class HOGMemoryDetector:
    name = "cpu_hog_knn"

    def __init__(self, bank, settings):
        from sklearn.neighbors import NearestNeighbors
        bank = np.asarray(bank, dtype=np.float32)
        if bank.ndim != 2 or bank.shape[1] != 36 or not len(bank) or not np.isfinite(bank).all():
            raise ValueError("Expected a finite [N,36] HOG bank")
        self.settings = settings
        self.neighbors = NearestNeighbors(n_neighbors=1, algorithm="brute", metric="euclidean", n_jobs=1).fit(bank)
        y, x = np.mgrid[:224, :224]
        self.coordinates = np.asarray([(y + 0.5 - 8) / 8, (x + 0.5 - 8) / 8], dtype=np.float32)

    def predict(self, image):
        features = hog_descriptors(image, self.settings)
        distances = self.neighbors.kneighbors(features, return_distance=True)[0][:, 0]
        grid = distances.reshape(27, 27)
        anomaly_map = map_coordinates(grid, self.coordinates, order=1, mode="nearest", prefilter=False)
        return AnomalyPrediction(float(distances.max()), np.asarray(anomaly_map, dtype=np.float32),
                                 dict(feature_grid=[27, 27], descriptor_dimension=36))


def _guard(required, phase):
    available = available_ram()
    if available < required:
        raise MemoryError(f"{phase}: available {available} bytes, required {required}")
    return dict(phase=phase, available_before_bytes=available, required_available_bytes=required)


class CanonicalCache:
    def __init__(self, output, input_manifest=None):
        self.directory = Path(output) / "canonical"
        self.directory.mkdir()
        self.receipts = {}
        self.expected = {}
        if input_manifest is not None:
            report = read_json(Path(input_manifest))
            inventory = Path(input_manifest).parent / report["inventory_file"]
            if digest(inventory) != report["inventory_sha256"]:
                raise ValueError("Input inventory changed")
            self.expected = {r["path"]: r["sha256"] for r in csv_rows(inventory)}

    def image(self, sample):
        key = sample.relative_path.as_posix()
        path = self.directory / sample.relative_path
        if key not in self.receipts:
            raw = sample.path.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            if self.expected and self.expected.get(key) != sha:
                raise ValueError("Source image differs from frozen inventory")
            with Image.open(BytesIO(raw)) as image:
                clean = canonical(image.convert("RGB"))
            path.parent.mkdir(parents=True, exist_ok=True)
            clean.save(path, format="PNG")
            self.receipts[key] = dict(source_file_sha256=sha, canonical_file_sha256=digest(path))
        if digest(path) != self.receipts[key]["canonical_file_sha256"]:
            raise ValueError("Canonical cache changed")
        with Image.open(path) as image:
            return image.convert("RGB")


def infer_category(data_root, output, settings, category, *, input_manifest=None):
    from threadpoolctl import threadpool_limits
    data_root, output = Path(data_root).resolve(), Path(output).resolve()
    train = MVTecADFolder(data_root, category, "train").samples()
    test = MVTecADFolder(data_root, category, "test").samples()
    if any(s.metadata["label"] for s in train):
        raise ValueError("The fit pool must contain normal images")
    fit_idx, cal_idx = split_train_calibration(len(train), settings["fit_ratio"], settings["seed"])
    fit, cal = [train[i] for i in fit_idx], [train[i] for i in cal_idx]
    bank_size = min(settings["bank_capacity"], len(fit) * 729)
    required = (settings["reserve_ram_bytes"] + settings["runtime_allowance_bytes"]
                + 3 * len(cal) * 224 * 224 * 4 + bank_size * 36 * 4)
    guard = _guard(required, "HOG inference")
    out = new_output(output, [data_root])
    cache = CanonicalCache(out, input_manifest)
    started = time.perf_counter()
    state = dict(status="RUNNING", study_family=settings["study_family"], category=category,
                 seed=settings["seed"], device="cpu", settings=settings, guard=guard)
    write_json(out / "status.json", state)
    try:
        with threadpool_limits(limits=settings["cpu_threads"]):
            selected = np.sort(np.random.default_rng(settings["seed"]).choice(
                len(fit) * 729, bank_size, replace=False))
            bank = np.empty((bank_size, 36), dtype=np.float32)
            cursor = 0
            for i, sample in enumerate(fit):
                local = selected[(selected >= i * 729) & (selected < (i + 1) * 729)] - i * 729
                if len(local):
                    feature = hog_descriptors(cache.image(sample), settings)
                    bank[cursor:cursor + len(local)] = feature[local]
                    cursor += len(local)
            if cursor != bank_size:
                raise ValueError("Bank enumeration mismatch")
            np.save(out / "bank.npy", bank, allow_pickle=False)
            np.save(out / "selected_indices.npy", selected, allow_pickle=False)
            detector = HOGMemoryDetector(bank, settings)
            fit_seconds = time.perf_counter() - started
            all_rows, calibration = [], {}
            test_raw_files = {}
            for variant in settings["variants"]:
                cal_started = time.perf_counter()
                cal_maps = np.empty((len(cal), 224, 224), dtype=np.float32)
                cal_scores = np.empty(len(cal), dtype=np.float64)
                for i, sample in enumerate(cal):
                    prepared = query_image(cache.image(sample), variant, settings)
                    prediction = detector.predict(prepared)
                    cal_maps[i], cal_scores[i] = prediction.pixel_map, prediction.image_score
                image_params, pixel_params = robust_params(cal_scores), robust_params(cal_maps)
                normalized_cal_maps = normalize(cal_maps, pixel_params)
                params = dict(image_params=image_params, pixel_params=pixel_params,
                    image_threshold=quantile_threshold(normalize(cal_scores, image_params), settings["normal_quantile"]),
                    pixel_threshold=quantile_threshold(normalized_cal_maps, settings["normal_quantile"]),
                    normal_calibration_count=len(cal), seconds=time.perf_counter() - cal_started)
                calibration[variant] = params
                del cal_maps, cal_scores, normalized_cal_maps
                gc.collect()
                temp = out / f"{variant}-maps.npy"
                maps = np.lib.format.open_memmap(temp, mode="w+", dtype=np.float32, shape=(len(test), 224, 224))
                scores = np.empty(len(test), dtype=np.float64)
                for i, sample in enumerate(test):
                    clean = cache.image(sample)
                    prepared = query_image(clean, variant, settings)
                    prediction_started = time.perf_counter()
                    prediction = detector.predict(prepared)
                    maps[i] = normalize(prediction.pixel_map, pixel_params).astype(np.float32)
                    scores[i] = float(normalize(np.asarray(prediction.image_score), image_params))
                    all_rows.append(dict(sample=sample.relative_path.as_posix(), label=sample.metadata["label"],
                        variant=variant, image_score=float(scores[i]),
                        rgb_sha256=hashlib.sha256(np.asarray(prepared).tobytes()).hexdigest(),
                        psnr=psnr(clean, prepared) if variant != "clean" else "",
                        ssim=ssim(clean, prepared) if variant != "clean" else "",
                        detector_seconds=time.perf_counter() - prediction_started))
                maps.flush()
                maps._mmap.close()
                np.save(out / f"{variant}-scores.npy", scores, allow_pickle=False)
                test_raw_files[variant] = temp
            del detector, bank
            gc.collect()
        # Evaluation input preparation follows all model predictions.
        masks = np.zeros((len(test), 224, 224), dtype=bool)
        gt_receipts = {}
        for i, sample in enumerate(test):
            if sample.mask_path:
                raw = sample.mask_path.read_bytes()
                name = sample.mask_path.relative_to(data_root).as_posix()
                sha = hashlib.sha256(raw).hexdigest()
                if cache.expected and cache.expected.get(name) != sha:
                    raise ValueError("Source GT differs from frozen inventory")
                with Image.open(BytesIO(raw)) as image:
                    masks[i] = np.asarray(canonical(image.convert("L"), mask=True)) > 0
                gt_receipts[name] = sha
        labels = np.array([s.metadata["label"] for s in test], dtype=np.int8)
        for variant, temp in test_raw_files.items():
            maps = np.load(temp, mmap_mode="r", allow_pickle=False)
            scores = np.load(out / f"{variant}-scores.npy", allow_pickle=False)
            np.savez_compressed(out / f"{variant}_predictions.npz",
                                labels=labels, masks=masks, maps=maps, scores=scores)
            maps._mmap.close()
            assert temp.resolve().is_relative_to(out)
            temp.unlink()
        write_csv(out / "per_image_inference.csv", all_rows)
        write_json(out / "calibration.json", calibration)
        write_json(out / "rgb_receipts.json", cache.receipts)
        write_json(out / "gt_receipts.json", gt_receipts)
        write_json(out / "split.json", dict(category=category, seed=settings["seed"],
            fit_paths=[s.relative_path.as_posix() for s in fit],
            calibration_paths=[s.relative_path.as_posix() for s in cal],
            test_paths=[s.relative_path.as_posix() for s in test]))
        state.update(status="INFERENCE_COMPLETE", normal_fit_count=len(fit), normal_calibration_count=len(cal),
            test_count=len(test), bank_vectors=bank_size, descriptor_dimension=36,
            fit_seconds=fit_seconds, inference_elapsed_seconds=time.perf_counter() - started,
            process_memory=process_memory(), available_ram_after_bytes=available_ram(),
            geometry_empty_anomaly_masks=int(np.sum((labels == 1) & ~masks.any(axis=(1, 2)))),
            source_code_sha256=digest(Path(__file__)),
            input_inventory_sha256=digest(Path(input_manifest)) if input_manifest else None,
            bank_sha256=digest(out / "bank.npy"),
            prediction_sha256={v: digest(out / f"{v}_predictions.npz") for v in settings["variants"]})
        write_json(out / "status.json", state)
        return state
    except BaseException as error:
        state.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        write_json(out / "status.json", state)
        raise


def evaluate_category(directory):
    from .evaluation import evaluate_predictions, area_under_per_region_overlap, binary_roc_auc
    directory = Path(directory)
    state = read_json(directory / "status.json")
    if state["status"] != "INFERENCE_COMPLETE":
        raise ValueError("Evaluation needs completed inference")
    if state["source_code_sha256"] != digest(Path(__file__)):
        raise ValueError("HOG source changed after inference")
    for variant, expected in state["prediction_sha256"].items():
        if digest(directory / f"{variant}_predictions.npz") != expected:
            raise ValueError("Saved CPU prediction changed")
    settings = state["settings"]
    required = settings["reserve_ram_bytes"] + state["test_count"] * 224 * 224 * 45
    guard = _guard(required, "HOG exact evaluation")
    calibration = read_json(directory / "calibration.json")
    source_rows = {(r["sample"], r["variant"]): r for r in csv_rows(directory / "per_image_inference.csv")}
    paths = read_json(directory / "split.json")["test_paths"]
    summary, per_image, details = [], [], {}
    started = time.perf_counter()
    for variant in settings["variants"]:
        with np.load(directory / f"{variant}_predictions.npz", allow_pickle=False) as z:
            labels, masks, maps, scores = (z[n] for n in ("labels", "masks", "maps", "scores"))
        params = calibration[variant]
        evaluation = evaluate_predictions(labels, scores, masks, maps,
            image_threshold=params["image_threshold"], pixel_threshold=params["pixel_threshold"], max_fpr=0.3)
        own = [source_rows[sample, variant] for sample in paths]
        mean_psnr = float(np.mean([float(r["psnr"]) for r in own])) if variant != "clean" else None
        mean_ssim = float(np.mean([float(r["ssim"]) for r in own])) if variant != "clean" else None
        row = dict(study_family=state["study_family"], category=state["category"], seed=state["seed"],
            variant=variant, bank_domain="clean", query_domain=variant,
            train_count=state["normal_fit_count"], calibration_count=state["normal_calibration_count"],
            test_count=state["test_count"], mean_psnr=mean_psnr, mean_ssim=mean_ssim,
            image_auroc=evaluation["classification"]["image_auroc"],
            image_f1=evaluation["classification"]["image_f1"],
            pixel_auroc=evaluation["localization"]["pixel_auroc"],
            au_pro=evaluation["localization"]["au_pro"],
            pixel_f1=evaluation["localization"]["pixel_f1"])
        summary.append(row)
        details[variant] = dict(evaluation=evaluation, mean_psnr="inf" if mean_psnr is not None and math.isinf(mean_psnr) else mean_psnr,
                                mean_ssim=mean_ssim)
        for i, sample in enumerate(paths):
            mask = masks[i].astype(bool)
            pro = area_under_per_region_overlap(mask[None], maps[i:i + 1], max_fpr=0.3, num_thresholds=200) if mask.any() else None
            auc = binary_roc_auc(mask.ravel(), maps[i].ravel()) if mask.any() and (~mask).any() else None
            per_image.append(dict(source_rows[sample, variant],
                per_image_aupro=pro, per_image_pixel_auroc=auc,
                roi_bg_gap=float(maps[i][mask].mean() - maps[i][~mask].mean()) if mask.any() and (~mask).any() else None))
        del labels, masks, maps, scores
        gc.collect()
    write_csv(directory / "summary.csv", summary)
    write_csv(directory / "per_image.csv", per_image)
    write_json(directory / "results.json", dict(study_family=state["study_family"], category=state["category"],
        seed=state["seed"], settings=settings, variants=details, bank_sha256=state["bank_sha256"]))
    state.update(status="EVALUATED_COMPLETE", evaluation_elapsed_seconds=time.perf_counter() - started,
        evaluation_guard=guard, evaluation_process_memory=process_memory(),
        artifact_sha256={name: digest(directory / name) for name in ("summary.csv", "per_image.csv", "results.json")})
    write_json(directory / "status.json", state)
    return state
