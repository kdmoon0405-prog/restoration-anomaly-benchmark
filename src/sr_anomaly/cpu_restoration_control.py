"""Fixed CPU SwinIR RGB cache and HOG-bank reuse, separated from evaluation."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import gc
import hashlib
import os
import shutil
import time

import numpy as np
from PIL import Image

from .analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json
from .cpu_hog_control import HOGMemoryDetector, _guard
from .fusion import robust_params, normalize, quantile_threshold
from .metrics import psnr, ssim
from .pcb_native_memory import available_ram, process_memory

CHECKPOINT_SHA256 = "09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e"


def _checkpoint(path, state):
    temporary = path.with_suffix(".tmp")
    write_json(temporary, state)
    for attempt in range(7):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 6:
                raise
            time.sleep(0.05 * 2**attempt)


def cache_restoration(inputs, output, repository, checkpoint, *, resume=False, model_factory=None,
                      include_fit=False, reuse_cache=None):
    sources, references = {}, []
    for directory in sorted(Path(p).resolve() for p in inputs):
        state = read_json(directory / "status.json")
        if state["status"] != "EVALUATED_COMPLETE":
            raise ValueError("CPU cache requires completed HOG references")
        split = read_json(directory / "split.json")
        receipts = read_json(directory / "rgb_receipts.json")
        selected = split["calibration_paths"] + split["test_paths"]
        if include_fit:
            selected += split["fit_paths"]
        for sample in sorted(set(selected)):
            source = relative_source(directory / "canonical", sample)
            expected = receipts[sample]["canonical_file_sha256"]
            if sample in sources and sources[sample][1] != expected:
                raise ValueError("Same source query differs across seed caches")
            sources[sample] = source, expected
        references.append(dict(path=str(directory), status_sha256=digest(directory / "status.json"),
                               receipts_sha256=digest(directory / "rgb_receipts.json")))
    if not sources or digest(checkpoint) != CHECKPOINT_SHA256:
        raise ValueError("Missing queries or incorrect fixed SwinIR checkpoint")
    binding = dict(checkpoint_sha256=CHECKPOINT_SHA256,
        network_sha256=digest(Path(repository) / "models/network_swinir.py"),
        adapter_sha256=digest(Path(__file__).with_name("real_models.py")),
        code_sha256=digest(Path(__file__)), source_runs=references,
        canonical_shape=[224, 224], low_shape=[56, 56], device="cpu", cpu_threads=4,
        source_queries={name: sha for name, (_, sha) in sorted(sources.items())})
    prior = None
    if reuse_cache is not None:
        reuse_cache = Path(reuse_cache).resolve()
        prior = read_json(reuse_cache / "status.json")
        if prior["status"] != "CPU_RESTORATION_CACHE_COMPLETE":
            raise ValueError("Reusable restoration cache is incomplete")
        for key in ("checkpoint_sha256", "network_sha256", "adapter_sha256", "canonical_shape",
                    "low_shape", "device", "cpu_threads"):
            if prior["binding"][key] != binding[key]:
                raise ValueError("Reusable cache model/geometry differs")
        binding["reused_cache_status_sha256"] = digest(reuse_cache / "status.json")
    binding["include_fit"] = include_fit
    output = Path(output).resolve()
    if resume:
        state = read_json(output / "status.json")
        if state["binding"] != binding:
            raise ValueError("CPU restoration cache binding changed")
        for sample, row in state["completed"].items():
            if digest(relative_source(output / "images", sample)) != row["output_sha256"]:
                raise ValueError("Completed restoration cache changed")
        if state["status"] == "CPU_RESTORATION_CACHE_COMPLETE":
            return state
    else:
        output = new_output(output, [*inputs, *([reuse_cache] if reuse_cache is not None else [])])
        state = dict(status="RUNNING", worker_pid=os.getpid(), binding=binding, completed={}, target_queries=len(sources))
    required = 1280 * 1024**2
    state["available_before_bytes"] = available_ram()
    state["required_available_bytes"] = required
    state["required_disk_bytes"] = 1024**3 + len(sources) * 224 * 224 * 4
    state["free_disk_before_bytes"] = shutil.disk_usage(output).free
    if state["available_before_bytes"] < required or state["free_disk_before_bytes"] < state["required_disk_bytes"]:
        state.update(status="BLOCKED_RESOURCES", worker_pid=None)
        _checkpoint(output / "status.json", state)
        raise MemoryError("CPU restoration cache resource guard blocked execution")
    state.update(status="RUNNING", worker_pid=os.getpid())
    _checkpoint(output / "status.json", state)
    if model_factory is None:
        import torch
        from .real_models import SwinIRLightweight
        torch.set_num_threads(4)
        model_factory = lambda: SwinIRLightweight(repository, checkpoint, device="cpu", scale=4)
    started = time.perf_counter()
    try:
        model = model_factory()
        for sample, (source, expected) in sorted(sources.items()):
            if sample in state["completed"]:
                continue
            if prior is not None and sample in prior["completed"]:
                receipt = prior["completed"][sample]
                previous = relative_source(reuse_cache / "images", sample)
                if receipt["input_sha256"] != expected or digest(previous) != receipt["output_sha256"]:
                    raise ValueError("Reusable RGB cache/source changed")
                destination = relative_source(output / "images", sample)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise FileExistsError("Unrecorded cached image exists; choose a new run")
                shutil.copyfile(previous, destination)
                state["completed"][sample] = dict(receipt, reused_from_prior_cache=True,
                    original_restoration_seconds=receipt["restoration_seconds"], restoration_seconds=0.0)
                _checkpoint(output / "status.json", state)
                continue
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("Canonical CPU input changed")
            with Image.open(BytesIO(raw)) as image:
                clean = image.convert("RGB")
            low = clean.resize((56, 56), Image.Resampling.BICUBIC)
            tick = time.perf_counter()
            restored = model.restore(low)
            seconds = time.perf_counter() - tick
            if restored.size != (224, 224):
                raise ValueError("CPU restoration returned an unexpected size")
            destination = relative_source(output / "images", sample)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError("Unrecorded cached image exists; preserve it and choose a new run")
            restored.save(destination, format="PNG")
            quality = psnr(clean, restored)
            state["completed"][sample] = dict(input_sha256=expected, output_sha256=digest(destination),
                restoration_seconds=seconds, psnr="inf" if np.isinf(quality) else quality, ssim=ssim(clean, restored))
            _checkpoint(output / "status.json", state)
        del model
        gc.collect()
        state.update(status="CPU_RESTORATION_CACHE_COMPLETE", worker_pid=None,
            elapsed_seconds=time.perf_counter() - started, process_memory=process_memory(),
            reused_queries=sum(r.get("reused_from_prior_cache", False) for r in state["completed"].values()),
            generated_queries=sum(not r.get("reused_from_prior_cache", False) for r in state["completed"].values()))
        _checkpoint(output / "status.json", state)
        return state
    except BaseException as error:
        state.update(status="FAILED", worker_pid=None, error=f"{type(error).__name__}: {error}")
        _checkpoint(output / "status.json", state)
        raise


def infer_restored_control(reference, cache, output):
    from threadpoolctl import threadpool_limits
    reference, cache = Path(reference), Path(cache)
    base, cached = read_json(reference / "status.json"), read_json(cache / "status.json")
    if base["status"] != "EVALUATED_COMPLETE" or cached["status"] != "CPU_RESTORATION_CACHE_COMPLETE":
        raise ValueError("Need complete HOG reference and restoration cache")
    feature_source = Path(__file__).with_name("cpu_hog_control.py")
    if base["source_code_sha256"] != digest(feature_source) or digest(reference / "bank.npy") != base["bank_sha256"]:
        raise ValueError("HOG feature source or bank changed")
    split = read_json(reference / "split.json")
    settings = dict(base["settings"], variants=["swinir_x4"])
    _guard(settings["reserve_ram_bytes"] + settings["runtime_allowance_bytes"]
           + (len(split["calibration_paths"]) + len(split["test_paths"])) * 224 * 224 * 4, "CPU SwinIR HOG reuse")
    out = new_output(Path(output), [reference, cache])
    state = dict(status="RUNNING", study_family=base["study_family"], category=base["category"],
        seed=base["seed"], settings=settings, device="cpu", normal_fit_count=base["normal_fit_count"],
        normal_calibration_count=base["normal_calibration_count"], test_count=base["test_count"],
        source_code_sha256=digest(feature_source), producer_source_sha256=digest(Path(__file__)),
        input_inventory_sha256=base["input_inventory_sha256"], bank_sha256=base["bank_sha256"],
        bank_source_run=str(reference.resolve()), bank_created_this_run=False,
        cache_status_sha256=digest(cache / "status.json"))
    write_json(out / "status.json", state)

    def restored(sample):
        path = relative_source(cache / "images", sample)
        row = cached["completed"][sample]
        if digest(path) != row["output_sha256"]:
            raise ValueError("Cached restored query changed")
        with Image.open(path) as image:
            return image.convert("RGB"), row

    started = time.perf_counter()
    with threadpool_limits(limits=settings["cpu_threads"]):
        bank = np.load(reference / "bank.npy", allow_pickle=False, mmap_mode="r")
        model = HOGMemoryDetector(bank, settings)
        cal = split["calibration_paths"]
        cal_maps, cal_scores = np.empty((len(cal), 224, 224), dtype=np.float32), np.empty(len(cal))
        for i, sample in enumerate(cal):
            prediction = model.predict(restored(sample)[0])
            cal_maps[i], cal_scores[i] = prediction.pixel_map, prediction.image_score
        ip, pp = robust_params(cal_scores), robust_params(cal_maps)
        params = dict(image_params=ip, pixel_params=pp,
            image_threshold=quantile_threshold(normalize(cal_scores, ip), settings["normal_quantile"]),
            pixel_threshold=quantile_threshold(normalize(cal_maps, pp), settings["normal_quantile"]))
        del cal_maps, cal_scores
        test = split["test_paths"]
        maps, scores, rows = np.empty((len(test), 224, 224), dtype=np.float32), np.empty(len(test)), []
        for i, sample in enumerate(test):
            image, receipt = restored(sample)
            tick = time.perf_counter()
            prediction = model.predict(image)
            seconds = time.perf_counter() - tick
            maps[i], scores[i] = normalize(prediction.pixel_map, pp), float(normalize(np.asarray(prediction.image_score), ip))
            rows.append(dict(sample=sample, variant="swinir_x4", image_score=float(scores[i]),
                rgb_sha256=hashlib.sha256(np.asarray(image).tobytes()).hexdigest(), psnr=receipt["psnr"],
                ssim=receipt["ssim"], detector_seconds=seconds))
        del model, bank
        gc.collect()
    # GT is loaded only after every calibration/test prediction has been generated.
    prediction_path = reference / "bicubic_x4_predictions.npz"
    if digest(prediction_path) != base["prediction_sha256"]["bicubic_x4"]:
        raise ValueError("Reference GT-bearing prediction changed")
    with np.load(prediction_path, allow_pickle=False) as original:
        labels, masks = original["labels"], original["masks"]
    for row, label in zip(rows, labels, strict=True):
        row["label"] = int(label)
    np.savez_compressed(out / "swinir_x4_predictions.npz", labels=labels, masks=masks, maps=maps, scores=scores)
    if digest(reference / "bank.npy") != base["bank_sha256"]:
        raise ValueError("Read-only HOG bank changed during queries")
    write_json(out / "split.json", split)
    write_json(out / "calibration.json", dict(swinir_x4=params))
    write_csv(out / "per_image_inference.csv", rows)
    state.update(status="INFERENCE_COMPLETE", inference_elapsed_seconds=time.perf_counter() - started,
        process_memory=process_memory(), prediction_sha256=dict(swinir_x4=digest(out / "swinir_x4_predictions.npz")))
    write_json(out / "status.json", state)
    return state
