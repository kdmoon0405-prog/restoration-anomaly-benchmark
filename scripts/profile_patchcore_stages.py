"""Bounded profiling of the frozen Branch B bank; never fit or tune models."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
from types import MethodType

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from scripts import run_fusion_patchcore as branch_b
from scripts.run_partial_restoration_feasibility import ANCHORS, BANK, CHECKPOINT, frozen_inputs, load_frozen_bank
from scripts.analyze_map_gating_feasibility import digest, relative, write_csv, write_json
from sr_anomaly.device import elapsed_seconds, resolve_device, start_timer
from sr_anomaly.fusion import normalize
from sr_anomaly.real_models import SwinIRLightweight


def cost_simulation(raw, sr, restored):
    if not np.isfinite([raw, sr, restored]).all() or min(raw, sr, restored) < 0 or sr + restored <= 0:
        raise ValueError("Finite nonnegative measured costs required")
    always = sr + restored
    return {"break_even_call_fraction": (always - raw) / always,
            "note": "cost simulation only; unknown trigger rate/accuracy, not measured savings or equal performance",
            "rows": [{"p": p, "always_sr_seconds": always, "conditional_seconds": raw + p * always,
                      "savings_seconds": always - raw - p * always,
                      "savings_fraction": (always - raw - p * always) / always} for p in (0, .25, .5, .75, 1)]}


@contextmanager
def instrument(model, torch, device, stages):
    """Use original embed(detach=False), then its unchanged per-row detach loop."""
    originals = []
    def timed(name, call, *args, **kwargs):
        started = start_timer(torch, device)
        value = call(*args, **kwargs)
        stages[name] = stages.get(name, 0.) + elapsed_seconds(torch, device, started)
        return value
    original_embed = model._embed
    def embed(self, images, detach=True, provide_patch_shapes=False):
        value = timed("backbone_embedding_seconds", original_embed, images, detach=False,
                      provide_patch_shapes=provide_patch_shapes)
        features, shapes = value if provide_patch_shapes else (value, None)
        if detach:
            features = timed("feature_detach_cpu_numpy_seconds", lambda: [x.detach().cpu().numpy() for x in features])
        return (features, shapes) if provide_patch_shapes else features
    originals.append((model, "_embed", original_embed))
    model._embed = MethodType(embed, model)
    for obj, method, stage in ((model.anomaly_scorer.nn_method, "run", "faiss_search_seconds"),
                               (model.patch_maker, "unpatch_scores", "score_map_postprocessing_seconds"),
                               (model.patch_maker, "score", "score_map_postprocessing_seconds"),
                               (model.anomaly_segmentor, "convert_to_segmentation", "score_map_postprocessing_seconds")):
        original = getattr(obj, method)
        originals.append((obj, method, original))
        setattr(obj, method, lambda *args, _call=original, _stage=stage, **kwargs: timed(_stage, _call, *args, **kwargs))
    try:
        yield
    finally:
        for obj, name, original in originals:
            setattr(obj, name, original)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="hazelnut-ten-20261015")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("Use an alphanumeric unique run-id")
    out = ROOT / "analysis/profiling_results_demo" / args.run_id
    if out.exists():
        raise FileExistsError("Run already exists; choose a new run-id")
    prepare_started = perf_counter()
    inputs = frozen_inputs(ROOT / "data/external/MVTecAD")
    old = json.loads((ROOT / "analysis/partial_restoration_feasibility/PROTOCOL.json").read_text())["inputs"]
    if inputs["cohort"] != old["cohort"]:
        raise ValueError("Original pilot10 filename cohort mismatch")
    torch, transforms, interpolation, _, common, patchcore, _, mvtec = branch_b._official_imports()
    torch.set_num_threads(min(4, torch.get_num_threads()))  # Same original Branch B/pilot setting.
    actual = resolve_device(args.device, torch.cuda.is_available())
    device = torch.device(actual)
    if not list((Path(torch.hub.get_dir()) / "checkpoints").glob("wide_resnet50_2-*.pth")):
        raise RuntimeError("Cached original backbone weights absent; automatic downloads prohibited")
    def no_download(*a, **kw):
        raise RuntimeError("Profiling must not download new weights")
    torch.hub.download_url_to_file = no_download
    versions = {name: importlib.metadata.version(name) for name in ("numpy", "Pillow", "torch", "torchvision", "faiss-cpu")}
    protocol = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "scope": "Timing only; no fit, calibration, metric evaluation, or new candidate inference",
                "cohort": inputs["cohort"], "seed": 11, "source_commit": branch_b.EXPECTED_PATCHCORE_COMMIT,
                "bank": relative(BANK), "checkpoint": relative(CHECKPOINT), "model_spec": inputs["model_spec"],
                "requested_device": args.device, "actual_device": actual, "cuda_available": torch.cuda.is_available(),
                "gpu_name": torch.cuda.get_device_name(device) if actual == "cuda" else None,
                "software": versions, "python": platform.python_version(), "platform": platform.system(),
                "torch_threads": torch.get_num_threads(), "faiss_threads": 4, "batch_size": 1,
                "warmup_samples": inputs["cohort"][:2], "warmup_repeats": 1, "planned_repeats": 2,
                "budget_seconds": 900, "budget_scope": "warmup + instrumented + optional original end-to-end inference wall time; excludes preparation/load/evaluation/file writes",
                "budget_rule": "After fixed warmup, use 2 repeats if projected budget permits, else 1; stop before further calls if even one pass would exceed remaining budget",
                "separate_end_to_end": "one original, uninstrumented pass on all same filenames only if projected remaining budget permits",
                "timer": "perf_counter; CUDA synchronize before/after stages; child-exclusive sum separated from parent detector time",
                "preprocessing": old["preprocessing"], "variants": ["degraded", "restored"],
                "numeric_tolerance": {"atol": 1e-5, "rtol": 1e-5}, "comparison": "raw predictions normalized using existing calibration solely for saved-anchor parity",
                "output": relative(out), "code_sha256": digest(Path(__file__))}
    out.mkdir(parents=True)
    write_json(out / "PROTOCOL.json", protocol)
    manifest = {"protocol_sha256": digest(out / "PROTOCOL.json"),
                "source_sha256": {k.replace("\\", "/"): v for k, v in inputs["source_sha256"].items()}}
    write_json(out / "INPUT_MANIFEST.json", manifest)
    print("Protocol frozen; loading same bank; no fit", flush=True)
    load_started = perf_counter()
    model = load_frozen_bank(torch, common, patchcore, device)
    restorer = SwinIRLightweight(ROOT / "third_party/SwinIR", CHECKPOINT, device=actual, scale=4, tile=56, tile_overlap=0)
    load_seconds = perf_counter() - load_started
    index = model.anomaly_scorer.nn_method.search_index
    bank_memory = {"ntotal": int(index.ntotal), "dimensions": int(index.d),
                   "float32_vector_storage_estimate_bytes": int(index.ntotal * index.d * 4), "note": "CPU index vector estimate, not RSS or GPU memory"}
    resize, crop = transforms.Resize(256, interpolation=interpolation.BILINEAR), transforms.CenterCrop(224)
    tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])
    source = json.loads((ANCHORS / "results.json").read_text())
    cached = {}
    for method in ("degraded_only", "restored_only"):
        with np.load(ANCHORS / f"{method}_predictions.npz", allow_pickle=False) as archive:
            indices = [source["test_paths"].index(sample) for sample in inputs["cohort"]]
            cached[method] = {key: archive[key][indices] for key in ("scores", "maps")}
    if actual == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    rows, parity = [], []
    inference_started = perf_counter()
    deadline = inference_started + 900
    def run_pair(sample, phase, repetition):
        started = start_timer(torch, device)
        with Image.open(ROOT / "data/external/MVTecAD" / sample) as image:
            clean = branch_b._canonical(image.convert("RGB"), resize, crop)
        low = clean.resize((56, 56), Image.Resampling.BICUBIC)
        degraded = low.resize((224, 224), Image.Resampling.BICUBIC)
        preprocessing = elapsed_seconds(torch, device, started)
        for variant in ("degraded", "restored"):
            if perf_counter() >= deadline:
                return False
            stages = {}
            total = start_timer(torch, device)
            started = start_timer(torch, device)
            image = degraded if variant == "degraded" else restorer.restore(low)
            sr_seconds = 0. if variant == "degraded" else elapsed_seconds(torch, device, started)
            started = start_timer(torch, device)
            batch = tensor(image).unsqueeze(0)
            tensor_seconds = elapsed_seconds(torch, device, started)
            detector = start_timer(torch, device)
            if phase == "instrumented":
                with instrument(model, torch, device, stages):
                    scores, maps = model._predict(batch)
            else:
                scores, maps = model._predict(batch)
            detector_seconds = elapsed_seconds(torch, device, detector)
            total_seconds = elapsed_seconds(torch, device, total)
            children = sum(stages.values())
            row = {"sample": sample, "variant": variant, "phase": phase, "repeat": repetition,
                   "image_preprocessing_seconds": preprocessing, "sr_seconds": sr_seconds,
                   "tensor_preprocessing_seconds": tensor_seconds,
                   **{key: stages.get(key) for key in ("backbone_embedding_seconds", "feature_detach_cpu_numpy_seconds", "faiss_search_seconds", "score_map_postprocessing_seconds")},
                   "detector_glue_seconds": detector_seconds - children if stages else None,
                   "detector_total_seconds": detector_seconds, "end_to_end_seconds": preprocessing + total_seconds}
            rows.append(row)
            method = "degraded_only" if variant == "degraded" else "restored_only"
            params = source["fusion_calibration"]
            which = "degraded" if variant == "degraded" else "restored"
            z_map = normalize(np.asarray(maps[0]), params["pixel"][which])
            z_score = normalize(np.asarray(scores[0]), params["image"][which])
            i = inputs["cohort"].index(sample)
            parity.append({"sample": sample, "variant": variant, "phase": phase, "repeat": repetition,
                           "map_max_abs_difference": float(np.abs(z_map - cached[method]["maps"][i]).max()),
                           "score_abs_difference": float(abs(z_score - cached[method]["scores"][i])),
                           "passed": bool(np.allclose(z_map, cached[method]["maps"][i], atol=1e-5, rtol=1e-5)
                                          and np.allclose(z_score, cached[method]["scores"][i], atol=1e-5, rtol=1e-5))})
        return True
    warmup_started = perf_counter()
    for sample in inputs["cohort"][:2]:
        if not run_pair(sample, "warmup", 0):
            break
    warmup_seconds = perf_counter() - warmup_started
    pair_estimate = warmup_seconds / 2
    repeats = 2 if pair_estimate * 20 < deadline - perf_counter() else 1
    write_json(out / "EXECUTION_PLAN.json", {"warmup_seconds": warmup_seconds, "estimated_seconds_per_pair": pair_estimate,
                                            "actual_repeats": repeats, "reason": "Fixed wall-budget estimate from warmup, not performance metrics"})
    print(f"Warmup {warmup_seconds:.2f}s; repeats={repeats}; starting fixed cohort", flush=True)
    for repetition in range(1, repeats + 1):
        for sample in inputs["cohort"]:
            if pair_estimate > deadline - perf_counter() or not run_pair(sample, "instrumented", repetition):
                break
        write_csv(out / "timings.csv", rows)  # Leave useful partial output after each pass.
        print(f"Instrumented repeat {repetition} complete; inference elapsed={perf_counter()-inference_started:.1f}s", flush=True)
    extra = pair_estimate * 10 < deadline - perf_counter()
    if extra:
        for sample in inputs["cohort"]:
            if pair_estimate > deadline - perf_counter() or not run_pair(sample, "end_to_end", 1):
                break
    inference_wall = perf_counter() - inference_started
    write_csv(out / "timings.csv", rows)
    write_json(out / "ANCHOR_PARITY.json", {"checks": parity, "all_passed": all(row["passed"] for row in parity)})
    statistics = {}
    for phase in ("instrumented", "end_to_end"):
        for variant in ("degraded", "restored"):
            selected = [row for row in rows if row["phase"] == phase and row["variant"] == variant]
            if not selected:
                continue
            statistics[f"{phase}/{variant}"] = {"observations": len(selected), "unique_samples": len({row["sample"] for row in selected}),
                                                  "repeats": len({row["repeat"] for row in selected})}
            for key in selected[0]:
                if key.endswith("_seconds") and selected[0][key] is not None:
                    values = [row[key] for row in selected]
                    statistics[f"{phase}/{variant}"][key] = {"mean": float(np.mean(values)), "median": float(np.median(values)), "min": min(values), "max": max(values)}
    chosen_phase = "end_to_end" if "end_to_end/restored" in statistics else "instrumented"
    raw_time = statistics[f"{chosen_phase}/degraded"]["detector_total_seconds"]["mean"] + statistics[f"{chosen_phase}/degraded"]["tensor_preprocessing_seconds"]["mean"]
    sr_time = statistics[f"{chosen_phase}/restored"]["sr_seconds"]["mean"]
    rest_time = statistics[f"{chosen_phase}/restored"]["detector_total_seconds"]["mean"] + statistics[f"{chosen_phase}/restored"]["tensor_preprocessing_seconds"]["mean"]
    summary = {"statistics": statistics, "bank_memory": bank_memory, "load_seconds": load_seconds,
               "preparation_seconds": load_started - prepare_started, "warmup_seconds": warmup_seconds, "inference_wall_seconds": inference_wall,
               "evaluation_seconds": 0, "no_new_research_metrics": True, "all_anchor_checks_passed": all(row["passed"] for row in parity),
               "cost_simulation": cost_simulation(raw_time, sr_time, rest_time), "cost_source_phase": chosen_phase,
               "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(device) if actual == "cuda" else None,
               "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(device) if actual == "cuda" else None,
               "timing_limitations": "Small fixed sample/repeat timing; per-stage synchronization/hook overhead. No production p95/FPS claim. Common RGB read/canonical/degradation cost excluded from conditional-cost comparison, shared by both strategies."}
    write_json(out / "summary.json", summary)
    print(json.dumps({"output": relative(out), "inference_wall_seconds": inference_wall, "parity": summary["all_anchor_checks_passed"]}), flush=True)


if __name__ == "__main__":
    main()
