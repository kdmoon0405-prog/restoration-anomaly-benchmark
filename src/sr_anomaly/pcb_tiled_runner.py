"""Read-only preflight and separately guarded raw model-smoke execution."""
from __future__ import annotations

from dataclasses import asdict
import csv
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess

import numpy as np

from . import bounded_bank as bounded
from . import pcb_tiling as geometry
from .device import device_metadata, resolve_device
from .pcb_tiled_models import (BACKBONE_SHA256, PATCHCORE_COMMIT, SWINIR_COMMIT, SWINIR_SHA256,
                               VARIANTS, create_models)
from .tiled_cpu_pipeline import Parent, TilePrediction, assemble_board, feature_chunks, validate_parents

GEOMETRY = Path("analysis/pcb_geometry/pcb2-native224-tiling-20261016")
BUDGET = Path("analysis/pcb_bank_budget/pcb2-uniform-cap262144-20261016")
PROTOCOL = Path("docs/PCB_FULL_FOV_PROTOCOL_V0.6.md")


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def safe_source(root, relative):
    name = PurePosixPath(relative)
    if (not relative or "\\" in relative or name.is_absolute() or PureWindowsPath(relative).drive
            or any(part in (".", "..") for part in name.parts)):
        raise ValueError("Unsafe source path in manifest")
    result = Path(root).joinpath(*name.parts).resolve()
    if not result.is_relative_to(Path(root).resolve()):
        raise ValueError("Source escapes dataset root")
    return result


def load_inventory(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "MANIFEST.json").read_text(encoding="utf-8"))
    for filename, key in (("PROTOCOL.json", "protocol_sha256"), ("INPUTS.csv", "inputs_csv_sha256"),
                          ("layouts.json", "layouts_sha256")):
        if bounded.file_sha256(directory / filename) != manifest[key]:
            raise ValueError(f"Geometry artifact hash mismatch: {filename}")
    if manifest["geometry_id"] != geometry.GEOMETRY_ID or manifest["partition_overlap"]:
        raise ValueError("Wrong geometry or overlapping split")
    with (directory / "INPUTS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    parents = validate_parents(Parent(r["sample"], r["partition"], int(r["label"]),
                                      (int(r["source_width"]), int(r["source_height"]))) for r in rows)
    composition = {s: {"normal": sum(p.split == s and p.label == 0 for p in parents),
                       "anomaly": sum(p.split == s and p.label == 1 for p in parents)}
                   for s in ("fit", "calibration", "test")}
    if composition != manifest["partitions"]:
        raise ValueError("Split/label counts differ from manifest")
    for r, p in zip(rows, parents, strict=True):
        safe_source(directory, p.sample)
        if int(r["tile_count"]) != len(geometry.tile_boxes(p.size_wh)):
            raise ValueError("Tile count differs from geometry")
    return parents, rows, manifest


def smoke_parents(parents):
    """Pre-fixed first fit/cal and first normal/anomaly test in frozen inventory order."""
    selected = [next(p for p in parents if p.split == s) for s in ("fit", "calibration")]
    selected += [next(p for p in parents if p.split == "test" and p.label == v) for v in (0, 1)]
    return validate_parents(selected)


def memory_plan(parents, *, capacity=bounded.DEFAULT_CAPACITY, dimension=1024, batch_tiles=2):
    tiles = {s: sum(len(geometry.tile_boxes(p.size_wh)) for p in parents if p.split == s)
             for s in ("fit", "calibration", "test")}
    pixels = {s: sum(p.size_wh[0]*p.size_wh[1] for p in parents if p.split == s) for s in tiles}
    n = tiles["fit"]*784
    bank = min(n, capacity)*dimension*4
    largest = max(w*h for w, h in (p.size_wh for p in parents))
    tile_maps = max(len(geometry.tile_boxes(p.size_wh)) for p in parents)*224*224*4
    board = largest*(3+8+4+4) + tile_maps
    return {"estimated_not_measured": True, "tiles": tiles, "pixels": pixels, "fit_vectors": n,
            "bank_bytes": bank, "scorer_copy_bytes": bank, "CPU_index_vector_bytes": bank,
            "selected_indices_bytes": min(n, capacity)*8,
            "feature_chunk_bytes": batch_tiles*784*dimension*4,
            "bank_scorer_index_plus_chunk_and_board_bytes": 3*bank+batch_tiles*784*dimension*4+board,
            "calibration_float32_pixel_pool_bytes": pixels["calibration"]*4,
            "calibration_float64_plus_quantile_copy_bytes": pixels["calibration"]*16,
            "test_float32_map_one_variant_bytes": pixels["test"]*4,
            "pixel_AUROC_visible_live_payload_lower_bound_bytes": pixels["test"]*39,
            "pixel_AUROC_lower_bound_formula": "4 map +1 mask +8 float64 score +1 uint8 label +1 positive +8 order +8 sorted_score +8 ranks bytes/pixel",
            "evaluation_locations": ["evaluation.py:pixel_metrics", "evaluation.py:binary_roc_auc", "evaluation.py:area_under_per_region_overlap"],
            "minimum_payload_disk_bytes": bank+min(n, capacity)*8+3*(pixels["calibration"]+pixels["test"])*4,
            "scope": "one shared clean-fit bank; variants sequential; raw maps only in model smoke",
            "excluded": ["model/activations/VRAM", "FAISS scratch", "Python allocator/index-selection objects", "filesystem page cache", "sort/unique workspace", "AU-PRO region-mask list", "calibration copies beyond scenario", "RGB quality workspaces"],
            "evaluation_peak_validated": False}


def available_ram():
    if os.name == "nt":
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (n, ctypes.c_ulonglong) for n in ("total", "available", "page_total", "page_available", "virtual", "virtual_available", "extended")]
        value = Memory()
        value.length = ctypes.sizeof(value)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            raise OSError("Cannot read available system RAM")
        return int(value.available)
    return int(os.sysconf("SC_AVPHYS_PAGES")*os.sysconf("SC_PAGE_SIZE"))


def probe_device(requested):
    try:
        import torch
    except ImportError:
        resolved = resolve_device(requested, False)
        return device_metadata(requested, resolved, False) | {"torch_installed": False}
    cuda = torch.cuda.is_available()
    resolved = resolve_device(requested, cuda)
    return device_metadata(requested, resolved, cuda, torch.cuda.get_device_name(0) if resolved == "cuda" else None) | {
        "torch_installed": True, "torch_version": torch.__version__}


def preflight(root, data_root, backbone_checkpoint, swinir_checkpoint, *, scope="full-pilot", device="auto", ram_budget=None):
    root = Path(root)
    if scope not in ("full-pilot", "model-smoke"):
        raise ValueError("Invalid execution scope")
    blockers = []
    parents, rows, manifest = load_inventory(root / GEOMETRY)
    if manifest["partitions"] != {"fit": {"normal": 721, "anomaly": 0}, "calibration": {"normal": 180, "anomaly": 0},
                                   "test": {"normal": 100, "anomaly": 100}}:
        raise ValueError("Frozen pcb2 721/180/200 split required")
    frozen = json.loads((root / GEOMETRY / "PROTOCOL.json").read_text(encoding="utf-8"))
    budget = json.loads((root / BUDGET / "PROTOCOL.json").read_text(encoding="utf-8"))
    for name, digest in budget["geometry_references"].items():
        if bounded.file_sha256(root / GEOMETRY / name) != digest:
            raise ValueError(f"Bank geometry reference mismatch: {name}")
    settings = budget["settings"]
    if settings != dict(total_vectors=27132672, dimension=1024, capacity=262144, seed=11, max_chunk_vectors=8192):
        raise ValueError("Frozen bank settings changed")
    for p in parents:
        if data_root is None or not safe_source(data_root, p.sample).is_file():
            blockers.append("dataset files missing; set --data-root or VISA_ROOT")
            break
    if data_root is not None:
        official = Path(data_root) / "split_csv/1cls.csv"
        if not official.is_file() or bounded.file_sha256(official) != frozen["official_csv_sha256"]:
            blockers.append("official VisA split CSV missing/hash mismatch")
        if any(r["mask"] and not safe_source(data_root, r["mask"]).is_file() for r in rows):
            blockers.append("audited test mask files missing (existence only; no GT content read)")
    checkpoints = {}
    for name, path, expected in (("backbone", backbone_checkpoint, BACKBONE_SHA256), ("swinir", swinir_checkpoint, SWINIR_SHA256)):
        digest = bounded.file_sha256(path) if path and Path(path).is_file() else None
        checkpoints[name] = {"path": str(path) if path else None, "sha256": digest, "expected_sha256": expected}
        if digest != expected:
            blockers.append(f"{name} checkpoint missing/hash mismatch")
    for directory, revision in (("patchcore-inspection", PATCHCORE_COMMIT), ("SwinIR", SWINIR_COMMIT)):
        actual = subprocess.check_output(["git", "-C", str(root/"third_party"/directory), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            blockers.append(f"{directory} source commit mismatch")
    # Verify the exact vendored feature/metric code already bound into the geometry audit.
    for name, digest in frozen["code_sha256"].items():
        if bounded.file_sha256(root / name) != digest:
            blockers.append(f"frozen code hash mismatch: {name}")
    execution = probe_device(device)
    if not execution["torch_installed"]:
        blockers.append("PyTorch unavailable")
    for name in ("torchvision", "faiss", "timm"):
        if importlib.util.find_spec(name) is None:
            blockers.append(f"runtime dependency missing: {name}")
    selected = smoke_parents(parents) if scope == "model-smoke" else parents
    plan = memory_plan(selected)
    from .pcb_board_analysis import memory_plan as postprocessing_memory_plan
    region_reference = json.loads((root/GEOMETRY/"resource_estimate.json").read_text(encoding="utf-8"))
    postprocessing = postprocessing_memory_plan(parents,
        region_mask_bytes=region_reference["aupro_retained_region_bool_masks_bytes"])
    if memory_plan(parents)["fit_vectors"] != settings["total_vectors"]:
        raise ValueError("Fit feature population differs from bank protocol")
    _, indices = bounded.selection_plan(total_vectors=plan["fit_vectors"], dimension=1024,
                                        capacity=settings["capacity"], seed=settings["seed"])
    selection_sha = bounded.index_sha256(indices)
    selection_reference = json.loads((root/BUDGET/"selection_plan.json").read_text(encoding="utf-8"))
    if scope == "full-pilot" and selection_sha != selection_reference["selection_indices_sha256"]:
        blockers.append("frozen selected-index SHA mismatch; do not silently reselect")
    ram = available_ram()
    if ram_budget is not None:
        if not isinstance(ram_budget, int) or isinstance(ram_budget, bool) or ram_budget <= 0:
            raise ValueError("RAM budget must be a positive integer byte count")
        ram = min(ram, ram_budget)
    if plan["bank_scorer_index_plus_chunk_and_board_bytes"] > ram:
        blockers.append("visible bank/index/buffer payload exceeds available/capped RAM")
    if scope == "full-pilot":
        if plan["pixel_AUROC_visible_live_payload_lower_bound_bytes"] > ram:
            blockers.append("native evaluator visible live payload already exceeds available/capped RAM")
        blockers += ["native evaluation peak not validated; full executor remains disabled",
                     "real GPU smoke review and final full execution approval pending"]
        for stage in ("calibration", "evaluation", "quality"):
            if postprocessing[f"{stage}_planning_envelope_bytes"] > ram:
                blockers.append(f"BLOCKED_MEMORY: {stage} planning envelope exceeds available/capped RAM")
    disk = shutil.disk_usage(root).free
    if plan["minimum_payload_disk_bytes"] > disk:
        blockers.append("minimum artifact payload exceeds free disk; checkpoint/overhead excluded")
    code = ("src/sr_anomaly/pcb_tiled_models.py", "src/sr_anomaly/pcb_tiled_runner.py", "scripts/run_pcb_tiled_patchcore.py",
            "src/sr_anomaly/device.py", "src/sr_anomaly/bounded_bank.py", "src/sr_anomaly/tiled_cpu_pipeline.py",
            "src/sr_anomaly/pcb_tiling.py", "src/sr_anomaly/real_models.py", "src/sr_anomaly/metrics.py",
            "src/sr_anomaly/fusion.py", "third_party/SwinIR/models/network_swinir.py",
            "third_party/patchcore-inspection/src/patchcore/backbones.py", "src/sr_anomaly/pcb_board_analysis.py")
    return {"status": "PREFLIGHT_BLOCKED" if blockers else "PREFLIGHT_PASS", "scope": scope,
            "blockers": blockers, "execution": execution, "checkpoints": checkpoints, "memory": plan,
            "board_postprocessing_memory": postprocessing, "real_gpu_smoke_review": "NOT_REVIEWED_BY_PREFLIGHT",
            "ram_available_or_capped_bytes": ram, "disk_free_bytes": disk,
            "geometry_id": geometry.GEOMETRY_ID, "manifest_sha256": bounded.file_sha256(root / GEOMETRY / "MANIFEST.json"),
            "protocol_sha256": bounded.file_sha256(root / PROTOCOL),
            "official_csv_sha256": frozen["official_csv_sha256"],
            "bank_settings": settings, "parents": [asdict(p) for p in selected],
            "full_partition_counts": manifest["partitions"], "variants": list(VARIANTS),
            "selection_indices_sha256": selection_sha, "bank_scope": "shared clean normal-fit bank; smoke subset is not full bank",
            "cpu_adapter_validation": "NOT_RUN_BY_PREFLIGHT; see separate CPU test verification",
            "data_root": str(data_root) if data_root is not None else None,
            "references_sha256": {str(path): bounded.file_sha256(root/path) for path in
                                   (GEOMETRY/"PROTOCOL.json", BUDGET/"PROTOCOL.json", BUDGET/"selection_plan.json")},
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "source_worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()),
            "code_sha256": {n: bounded.file_sha256(root/n) for n in code},
            "actual_pcb_bank": "NOT_CREATED", "actual_pcb_calibration": "NOT_CREATED",
            "real_model_smoke": "REAL_MODEL_SMOKE_NOT_RUN", "pilot": "NOT_READY_FOR_FULL_PILOT"}


def run_raw_smoke(parents, loader, adapter, transform, output, *, provenance, patch_shape=(28, 28),
                  dimension=1024, capacity=bounded.DEFAULT_CAPACITY, expected_index_sha=None):
    """Shared execution body for injected synthetic tests and explicit real model smoke."""
    parents = validate_parents(parents)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    state = {"status": "BUILDING", "scope": "model-smoke", "provenance": provenance,
             "calibration": "NOT_CREATED_RAW_MAPS_ONLY", "thresholds": None, "metrics": None,
             "pilot": "NOT_READY_FOR_FULL_PILOT", "rows": [], "parents": [asdict(p) for p in parents]}
    bounded._status(output, state)
    try:
        fit = tuple(p for p in parents if p.split == "fit")
        n = sum(len(geometry.tile_boxes(p.size_wh)) for p in fit)*int(np.prod(patch_shape))
        _, selected = bounded.selection_plan(total_vectors=n, dimension=dimension, capacity=capacity, seed=11)
        index_sha = bounded.index_sha256(selected)
        if expected_index_sha is not None and index_sha != expected_index_sha:
            raise ValueError("Smoke subset selection-index SHA mismatch before extraction")
        stream = feature_chunks(fit, loader, adapter.extract, patch_shape=patch_shape, dimension=dimension, batch_tiles=2)
        bounded.save_bank(stream, output/"bank", provenance=provenance, total_vectors=n,
                          dimension=dimension, capacity=capacity, seed=11)
        bank, indices, metadata = bounded.load_complete_bank(output/"bank")
        before = {name: bounded.file_sha256(output/"bank"/name) for name in ("status.json", "bank.npy", "selected_indices.npy")}
        adapter.bind_bank(bank)
        (output/"predictions").mkdir()
        for parent in parents:
            if parent.split == "fit":
                continue
            rgb = loader(parent)
            if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.shape != (*parent.size_wh[::-1], 3):
                raise ValueError("Native parent RGB dimensions/dtype mismatch")
            boxes = geometry.tile_boxes(parent.size_wh)
            for variant in VARIANTS:
                def predictions():
                    for i, (tile, box) in enumerate(zip(geometry.extract_tiles(rgb, boxes), boxes, strict=True)):
                        values, score = adapter.predict(transform(tile, variant))
                        yield TilePrediction(parent.sample, variant, i, box, values, score)
                board = assemble_board(parent.sample, variant, parent.size_wh, predictions())
                filename = f"predictions/{len(state['rows']):04d}.npy"
                with (output/filename).open("xb") as handle:
                    np.save(handle, board.anomaly_map, allow_pickle=False)
                state["rows"].append({"sample": parent.sample, "split": parent.split, "label": parent.label,
                    "variant": variant, "size_wh": list(parent.size_wh), "score": board.score,
                    "file": filename, "sha256": bounded.file_sha256(output/filename)})
                del board
            del rgb
        if before != {name: bounded.file_sha256(output/"bank"/name) for name in before}:
            raise ValueError("Bank changed during smoke predictions")
        state.update(status="COMPLETE", bank_unchanged=True, bank_artifact_sha256=before,
                     smoke_bank="CREATED_SUBSET_ONLY", full_pcb_bank="NOT_CREATED",
                     selection_indices_sha256=index_sha, feature_counts=metadata["progress"])
        bounded._status(output, state)
    except BaseException as error:
        state.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        bounded._status(output, state)
        raise
    return state


def execute_smoke(report, root, data_root, output, *, factory=None, loader=None):
    if report["status"] != "PREFLIGHT_PASS" or report["blockers"] or report["scope"] != "model-smoke":
        raise RuntimeError("Execution blocked before model construction; inspect preflight report")
    if Path(output).exists():
        raise FileExistsError("Existing output is never overwritten")
    root = Path(root)
    for name, digest in report["code_sha256"].items():
        if bounded.file_sha256(root/name) != digest:
            raise ValueError("Executable source changed after preflight")
    if bounded.file_sha256(root/PROTOCOL) != report["protocol_sha256"]:
        raise ValueError("Protocol changed after preflight")
    parents = validate_parents(Parent(p["sample"], p["split"], p["label"], tuple(p["size_wh"])) for p in report["parents"])
    rows = {r["sample"]: r for r in load_inventory(root/GEOMETRY)[1]}
    if loader is None:
        from PIL import Image
        def loader(parent):
            path = safe_source(data_root, parent.sample)
            if bounded.file_sha256(path) != rows[parent.sample]["image_sha256"]:
                raise ValueError("Source RGB differs from audited inventory")
            with Image.open(path) as image:
                return np.asarray(image.convert("RGB"))
    factory = create_models if factory is None else factory
    adapter, transform = factory(root, report["execution"]["actual_device"],
                                 report["checkpoints"]["backbone"]["path"], report["checkpoints"]["swinir"]["path"])
    try:
        return run_raw_smoke(parents, loader, adapter, transform, output, expected_index_sha=report["selection_indices_sha256"],
            provenance={"input_kind": "fit_normal_feature_stream", "scope": "model-smoke-not-research-result", "preflight": report})
    finally:
        close = getattr(adapter, "close", None)
        if close is not None:
            close()
