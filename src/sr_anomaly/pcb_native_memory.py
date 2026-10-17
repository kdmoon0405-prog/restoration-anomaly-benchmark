"""Synthetic-score/RGB resource rehearsal; never a production prediction artifact."""
from __future__ import annotations

import csv
import ctypes
import io
from importlib.metadata import version
import json
import math
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
from PIL import Image

from . import pcb_board_analysis as board
from .bounded_bank import file_sha256
from .dataset import safe_component
from .fusion import normalize
from .pcb_tiled_models import VARIANTS, assemble_rgb
from .pcb_tiled_runner import GEOMETRY, available_ram, load_inventory, safe_source
from .pcb_tiling import tile_boxes
from .tiled_cpu_pipeline import Parent

KIND = "resource_rehearsal_synthetic_scores_rgb_not_predictions"
RAM_RESERVE = 2 * 1024**3  # Fixed technical OS/runtime headroom, not a research threshold.
DISK_RESERVE = 1024**3
SEED = 11
STAGES = ("calibration", "normalization", "quality", "evaluation")
CODE = ("scripts/check_pcb_native_memory.py", "src/sr_anomaly/pcb_native_memory.py",
        "src/sr_anomaly/pcb_board_analysis.py", "src/sr_anomaly/evaluation.py",
        "src/sr_anomaly/fusion.py", "src/sr_anomaly/metrics.py", "src/sr_anomaly/dataset.py",
        "src/sr_anomaly/pcb_tiled_models.py", "src/sr_anomaly/pcb_tiled_runner.py",
        "src/sr_anomaly/pcb_tiling.py", "src/sr_anomaly/tiled_cpu_pipeline.py",
        "src/sr_anomaly/bounded_bank.py")


def write_json(path, value):
    """Replace only state files inside a newly owned rehearsal directory."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def small_parents():
    return tuple(Parent("synthetic/" + name, split, label, (336, 224))
                 for name, split, label in (("fit", "fit", 0), ("cal-a", "calibration", 0),
                     ("cal-b", "calibration", 0), ("normal", "test", 0), ("anomaly", "test", 1)))


def process_memory():
    """RSS/working set and OS process-lifetime high-water mark, both in bytes."""
    if os.name == "nt":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in ("peak", "rss", "peak_paged", "paged",
                    "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
        value = Counters()
        value.cb = ctypes.sizeof(value)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(value), value.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"rss_bytes": int(value.rss), "os_lifetime_peak_rss_bytes": int(value.peak),
                "method": "Windows GetProcessMemoryInfo WorkingSetSize/PeakWorkingSetSize"}
    if sys.platform.startswith("linux"):
        fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
        return {"rss_bytes": int(fields["VmRSS"].split()[0]) * 1024,
                "os_lifetime_peak_rss_bytes": int(fields["VmHWM"].split()[0]) * 1024,
                "method": "Linux /proc/self/status VmRSS/VmHWM (kB converted to bytes)"}
    raise OSError("RSS high-water measurement supports Windows and Linux only")


def disk_bytes(directory):
    total = 0
    for path in Path(directory).rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            pass  # A worker may remove a completed temporary file between samples.
    return total


class Monitor:
    """Sample this worker, not a sum of different processes' unrelated peaks."""
    def __init__(self, output, interval=.1):
        self.output, self.interval = Path(output), interval
        self.stop = threading.Event()
        self.error = None
        self.values = {"sample_count": 0, "sampled_peak_rss_bytes": 0,
                       "sampled_workspace_disk_max_bytes": 0, "sampling_interval_seconds": interval}
        self.next_disk = 0.

    def sample(self):
        snapshot = process_memory()
        free = available_ram()
        if not self.values["sample_count"]:
            self.values.update(baseline_rss_bytes=snapshot["rss_bytes"], system_available_min_observed_bytes=free)
        self.values.update(measurement_method=snapshot["method"],
            os_process_lifetime_peak_rss_bytes=snapshot["os_lifetime_peak_rss_bytes"],
            sampled_peak_rss_bytes=max(self.values["sampled_peak_rss_bytes"], snapshot["rss_bytes"]),
            system_available_min_observed_bytes=min(self.values["system_available_min_observed_bytes"], free))
        self.values["sample_count"] += 1
        if time.perf_counter() >= self.next_disk:
            self.values["sampled_workspace_disk_max_bytes"] = max(
                self.values["sampled_workspace_disk_max_bytes"], disk_bytes(self.output / "work"))
            self.next_disk = time.perf_counter() + 1.

    def _loop(self):
        while not self.stop.wait(self.interval):
            try:
                self.sample()
            except BaseException as error:
                self.error = error
                break

    def start(self):
        self.sample()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def finish(self):
        self.stop.set()
        self.thread.join()
        self.next_disk = 0.
        self.sample()
        if self.error:
            raise OSError("Resource sampling failed") from self.error
        return self.values


def guard_memory(required, cap=None, *, live_bytes=0):
    available = available_ram()
    if cap is not None and required + RAM_RESERVE > cap:
        raise MemoryError("BLOCKED_MEMORY: fixed phase plan plus 2 GiB headroom exceeds RAM cap")
    if max(0, required - live_bytes) + RAM_RESERVE > available:
        raise MemoryError("BLOCKED_MEMORY: insufficient available RAM including fixed 2 GiB headroom")


def stage_plan(parents, region_bytes):
    plan = board.memory_plan(parents, region_mask_bytes=region_bytes)
    largest = max(w*h for w, h in (p.size_wh for p in parents))
    phases = {"calibration": plan["calibration_planning_envelope_bytes"],
              "normalization": 32 * largest, "quality": plan["quality_planning_envelope_bytes"],
              "evaluation": plan["evaluation_planning_envelope_bytes"]}
    cal = sum(w*h for p in parents if p.split == "calibration" for w, h in [p.size_wh])
    test = sum(w*h for p in parents if p.split == "test" for w, h in [p.size_wh])
    # Only one variant's workspace is live; calibration raw files are removed before test generation.
    disk = max(4*cal, 12*test) + 2*1024**2
    return {"existing_board_plan": plan, "phase_payload_plans_bytes": phases,
            "ram_reserve_bytes": RAM_RESERVE, "required_available_ram_bytes": max(phases.values()) + RAM_RESERVE,
            "workspace_disk_payload_plan_bytes": disk, "disk_reserve_bytes": DISK_RESERVE,
            "required_free_disk_bytes": disk + DISK_RESERVE, "estimates_not_measured": True}


def preflight(root, scope, data_root, *, ram_cap=None, output_base=None):
    root = Path(root).resolve()
    if scope not in ("small", "native"):
        raise ValueError("Unknown rehearsal scope")
    if ram_cap is not None and (isinstance(ram_cap, bool) or not isinstance(ram_cap, int) or ram_cap < 1):
        raise ValueError("Positive integer RAM cap bytes required")
    blockers = []
    references = {}
    if scope == "native":
        parents, rows, manifest = load_inventory(root / GEOMETRY)
        if manifest["partitions"] != {"fit": {"normal": 721, "anomaly": 0},
                "calibration": {"normal": 180, "anomaly": 0}, "test": {"normal": 100, "anomaly": 100}}:
            raise ValueError("Frozen 721/180/200 inventory required")
        for filename in ("PROTOCOL.json", "MANIFEST.json", "INPUTS.csv", "layouts.json", "resource_estimate.json"):
            references[str(GEOMETRY / filename)] = file_sha256(root / GEOMETRY / filename)
        region_bytes = read_json(root / GEOMETRY / "resource_estimate.json")["aupro_retained_region_bool_masks_bytes"]
        if data_root is None:
            blockers.append("INPUTS: --data-root required for native GT evaluation")
        else:
            data_root = Path(data_root).resolve()
            protocol = read_json(root / GEOMETRY / "PROTOCOL.json")
            official = data_root / "split_csv/1cls.csv"
            if not official.is_file() or file_sha256(official) != protocol["official_csv_sha256"]:
                blockers.append("INPUTS: official split CSV missing/hash mismatch")
            if any(r["mask"] and not safe_source(data_root, r["mask"]).is_file() for r in rows):
                blockers.append("INPUTS: frozen GT files missing (existence only; content loads in evaluation)")
    else:
        parents = small_parents()
        region_bytes = 2 * 336 * 224
        data_root = None  # Small is fully generated and never accesses a supplied dataset.
    if len({p.size_wh for p in parents if p.split == "test"}) != 1:
        raise ValueError("Unchanged evaluator requires identical native test dimensions")
    plan = stage_plan(parents, region_bytes)
    free = available_ram()
    if plan["required_available_ram_bytes"] > min(free, ram_cap if ram_cap is not None else free):
        blockers.append("MEMORY: phase plan plus fixed 2 GiB OS/runtime headroom exceeds available/capped RAM")
    ancestor = Path(output_base or root / "outputs/pcb-native-memory").resolve()
    while not ancestor.exists():
        ancestor = ancestor.parent
    disk_free = shutil.disk_usage(ancestor).free
    if plan["required_free_disk_bytes"] > disk_free:
        blockers.append("DISK: workspace plan plus fixed 1 GiB headroom exceeds free disk")
    parent_memory = None
    try:
        parent_memory = process_memory()
    except OSError:
        blockers.append("MEASUREMENT: process RSS/high-water measurement unavailable")
    status = ("PREFLIGHT_PASS" if not blockers else "BLOCKED_INPUTS" if any(b.startswith("INPUTS") for b in blockers)
              else "BLOCKED_MEMORY" if any(b.startswith("MEMORY") for b in blockers) else "PREFLIGHT_BLOCKED")
    return {"status": status, "kind": KIND, "scope": scope, "seed": SEED, "blockers": blockers,
            "data_root": str(data_root) if data_root else None, "memory_plan": plan,
            "available_ram_bytes": free, "ram_cap_bytes": ram_cap, "disk_free_bytes": disk_free,
            "native_region_mask_reference_bytes": region_bytes, "references_sha256": references,
            "code_sha256": {p: file_sha256(root / p) for p in CODE},
            "model_execution": False, "research_metrics_exported": False, "full_pilot_approved": False,
            "parent_counts": {s: sum(p.split == s for p in parents) for s in ("fit", "calibration", "test")},
            "native_sizes_wh": sorted({p.size_wh for p in parents}),
            "distribution": "independent seeded uniform float32 raw maps/scores, generated uint8 RGB; not a worst-case proof",
            "orchestrator_memory_at_preflight": parent_memory,
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                "numpy": np.__version__, "pillow": version("Pillow"), "scikit_image": version("scikit-image"),
                "pointer_bits": ctypes.sizeof(ctypes.c_void_p)*8},
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "source_worktree_dirty": bool(subprocess.check_output(
                ["git", "status", "--porcelain", "--ignore-submodules=all"], cwd=root, text=True).strip())}


def _rng(variant, domain, index):
    return np.random.default_rng(np.random.SeedSequence([SEED, VARIANTS.index(variant), domain, index]))


def _raw_fixture(work, parents, variant, split):
    """No label/GT argument enters the value generator."""
    directory = work / split
    directory.mkdir()
    rows = []
    for i, parent in enumerate(p for p in parents if p.split == split):
        rng = _rng(variant, 0 if split == "calibration" else 1, i)
        values = rng.random(parent.size_wh[::-1], dtype=np.float32)
        filename = f"{split}/{i:04d}.npy"
        np.save(work / filename, values, allow_pickle=False)
        rows.append({"sample": parent.sample, "size_wh": list(parent.size_wh), "file": filename,
                     "sha256": file_sha256(work / filename), "score": float(rng.random())})
    return rows


def remove_owned_tree(output, directory):
    output, directory = Path(output).resolve(), Path(directory)
    if directory.is_symlink() or not directory.resolve().is_relative_to(output / "work") or directory.resolve() == output / "work":
        raise ValueError("Refusing cleanup outside an owned variant workspace")
    shutil.rmtree(directory)


def evaluation_mask(parent, rows, data_root):
    if parent.split != "test":
        raise ValueError("GT may only load for test evaluation")
    if not parent.label:
        return np.zeros(parent.size_wh[::-1], bool)
    row = rows[parent.sample]
    path = safe_source(data_root, row["mask"])
    raw = path.read_bytes()
    import hashlib
    if hashlib.sha256(raw).hexdigest() != row["mask_sha256"]:
        raise ValueError("Frozen GT file hash mismatch")
    with Image.open(io.BytesIO(raw)) as image:
        values = np.asarray(image)
        if values.ndim != 2 or values.shape != parent.size_wh[::-1]:
            raise ValueError("Native GT shape mismatch; no resizing/padding allowed")
        mask = values > 0  # Existing binary anomaly definition; original GT bytes are unchanged.
    if not mask.any():
        raise ValueError("Empty anomaly GT refused")
    return mask


def _small_mask(parent):
    mask = np.zeros(parent.size_wh[::-1], bool)
    if parent.label:
        mask[100:120, 150:170] = True
        mask[120, 170] = True
    return mask


def perform_stage(root, output, protocol, stage, variant):
    if protocol["scope"] == "native":
        parents, rows, _ = load_inventory(Path(root) / GEOMETRY)
        rows = {r["sample"]: r for r in rows}
    else:
        parents, rows = small_parents(), {}
    work = output / "work" / variant
    plan = protocol["memory_plan"]["phase_payload_plans_bytes"][stage]
    guard_memory(plan, protocol["ram_cap_bytes"])
    if stage == "calibration":
        work.mkdir(parents=True)
        fitted = board._fit_variant(work, _raw_fixture(work, parents, variant, "calibration"))
        write_json(work / "synthetic_parameters.json", {"kind": KIND, "params": fitted})
        remove_owned_tree(output, work / "calibration")
    elif stage == "normalization":
        fitted = read_json(work / "synthetic_parameters.json")["params"]
        (work / "normalized").mkdir()
        normalized_rows = []
        for row in _raw_fixture(work, parents, variant, "test"):
            values = board._map(work, row)
            normalized = normalize(values, fitted["pixel"])
            filename = f"normalized/{len(normalized_rows):04d}.npy"
            np.save(work / filename, normalized, allow_pickle=False)
            normalized_rows.append(dict(row, file=filename, sha256=file_sha256(work / filename),
                score=float(normalize(np.asarray([row["score"]]), fitted["image"])[0])))
            del values, normalized
        write_json(work / "synthetic_rows.json", {"kind": KIND, "rows": normalized_rows})
        remove_owned_tree(output, work / "test")
    elif stage == "quality":
        from .metrics import psnr, ssim
        for i, parent in enumerate(p for p in parents if p.split == "test"):
            shape = (*parent.size_wh[::-1], 3)
            rgb = _rng(variant, 2, i).integers(0, 256, shape, dtype=np.uint8)
            candidate = _rng(variant, 3, i).integers(0, 256, shape, dtype=np.uint8)
            tiles = (candidate[y0:y1, x0:x1] for x0, y0, x1, y1 in tile_boxes(parent.size_wh))
            reference = Image.fromarray(rgb)
            reconstructed = Image.fromarray(assemble_rgb(parent.size_wh, tiles))
            # Exercise unchanged quality workspaces, never retain/export numeric scores.
            a, b = psnr(reference, reconstructed), ssim(reference, reconstructed)
            if math.isnan(a) or not math.isfinite(b):
                raise ValueError("Synthetic quality calculation invalid")
            del a, b, reference, reconstructed, rgb, candidate, tiles
    elif stage == "evaluation":
        from .evaluation import connected_components, evaluate_predictions
        test = [p for p in parents if p.split == "test"]
        synthetic = read_json(work / "synthetic_rows.json")["rows"]
        if [r["sample"] for r in synthetic] != [p.sample for p in test]:
            raise ValueError("Synthetic test inventory mismatch")
        maps = np.empty((len(test), *test[0].size_wh[::-1]), np.float64)
        masks = np.empty(maps.shape, bool)
        region_bytes = 0
        for i, (parent, row) in enumerate(zip(test, synthetic, strict=True)):
            values = board._map(work, row, dtype=np.float64)
            maps[i] = values
            del values
            mask = evaluation_mask(parent, rows, protocol["data_root"]) if rows else _small_mask(parent)
            masks[i] = mask
            region_bytes += int(connected_components(mask, connectivity=1).max()) * mask.size
            del mask
        if region_bytes != protocol["native_region_mask_reference_bytes"]:
            raise ValueError("GT 4-connected region payload differs from frozen resource reference")
        actual_plan = board.memory_plan(parents, region_mask_bytes=region_bytes)["evaluation_planning_envelope_bytes"]
        guard_memory(actual_plan, protocol["ram_cap_bytes"], live_bytes=maps.nbytes + masks.nbytes)
        fitted = read_json(work / "synthetic_parameters.json")["params"]
        calculated = evaluate_predictions(np.asarray([p.label for p in test]),
            np.asarray([r["score"] for r in synthetic]), masks=masks, anomaly_maps=maps,
            image_threshold=fitted["image_threshold"], pixel_threshold=fitted["pixel_threshold"], max_fpr=.3)
        del calculated, maps, masks  # No performance values enter results/logs.
    else:
        raise ValueError("Unknown resource stage")
    return {"helpers_completed": True, "research_metrics_exported": False}


def worker(root, output, stage, variant):
    output = Path(output).resolve()
    protocol = read_json(output / "PROTOCOL.json")
    state = read_json(output / "status.json")
    if (protocol.get("kind") != KIND or protocol["status"] != "PREFLIGHT_PASS" or state["status"] != "BUILDING"
            or state["active_stage"] != [variant, stage] or stage not in STAGES or variant not in VARIANTS
            or file_sha256(output / "PROTOCOL.json") != state["protocol_sha256"]):
        raise ValueError("Incomplete/invalid rehearsal authorization; raw smoke is not accepted")
    for path, expected in {**protocol["code_sha256"], **protocol["references_sha256"]}.items():
        if file_sha256(Path(root) / path) != expected:
            raise ValueError("Worker source/reference hash mismatch")
    monitor = Monitor(output)
    result = {"stage": stage, "variant": variant, "pid": os.getpid(), "input_kind": KIND,
              "payload_plan_bytes": protocol["memory_plan"]["phase_payload_plans_bytes"][stage],
              "input_sizes_wh": protocol["native_sizes_wh"], "parent_counts": protocol["parent_counts"],
              "dtypes": {"raw_maps": "float32", "normalized_maps": "float64", "eval_masks": "bool", "rgb": "uint8"}}
    start = time.perf_counter()
    result.update(perf_counter_start=start, workspace_bytes_start=disk_bytes(output / "work"))
    monitor.start()
    error = None
    try:
        result.update(perform_stage(root, output, protocol, stage, variant), status="STAGE_COMPLETE")
        imported = [name for name in ("torch", "faiss", "patchcore") if name in sys.modules]
        result["model_runtime_modules_imported"] = imported
        if imported:
            raise RuntimeError("Unexpected model runtime import in model-free worker")
    except BaseException as caught:
        error = caught
        result.update(status="FAILED", error=f"{type(caught).__name__}: {caught}")
    finally:
        try:
            result.update(monitor.finish())
        except BaseException as caught:
            error = caught
            result.update(status="FAILED", measurement_error=type(caught).__name__)
        end = time.perf_counter()
        result.update(perf_counter_end=end, worker_elapsed_seconds=end-start,
                      workspace_bytes_end=disk_bytes(output / "work"))
        write_json(output / "stages" / f"{variant}-{stage}.json", result)
    if error:
        raise error
    return result


def write_table(output, entries):
    fields = ("variant", "stage", "pid", "worker_elapsed_seconds", "parent_launch_to_exit_seconds",
              "payload_plan_bytes", "baseline_rss_bytes", "sampled_peak_rss_bytes",
              "os_process_lifetime_peak_rss_bytes", "system_available_min_observed_bytes",
              "workspace_bytes_start", "workspace_bytes_end", "sampled_workspace_disk_max_bytes", "worker_exit_code")
    with (output / "stage_memory.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(read_json(output / entry["file"]) for entry in entries)


def load_completed_rehearsal(output):
    output = Path(output)
    state = read_json(output / "status.json")
    expected = [(v, s) for v in VARIANTS for s in STAGES]
    if (state.get("kind") != KIND or state.get("status") != "MEMORY_REHEARSAL_COMPLETE_NOT_FULL_APPROVAL"
            or state.get("full_pilot_approved") is not False
            or file_sha256(output / "PROTOCOL.json") != state["protocol_sha256"]
            or [(r["variant"], r["stage"]) for r in state["stages"]] != expected
            or file_sha256(output / "stage_memory.csv") != state["stage_table_sha256"]):
        raise ValueError("Incomplete or modified rehearsal artifact")
    for entry in state["stages"]:
        filename = f"stages/{entry['variant']}-{entry['stage']}.json"
        if entry["file"].replace("\\", "/") != filename or file_sha256(output / filename) != entry["sha256"]:
            raise ValueError("Worker record checksum/path mismatch")
        record = read_json(output / filename)
        if record.get("status") != "STAGE_COMPLETE" or record.get("worker_exit_code") != 0 or not record.get("worker_exited"):
            raise ValueError("Unfinished rehearsal worker")
    return state


def run(root, run_id, scope, data_root=None, *, execute=False, ram_cap=None, output_base=None, timeout=3600):
    root = Path(root).resolve()
    run_id = safe_component(run_id, "run-id")
    output = Path(output_base or root / "outputs/pcb-native-memory").resolve() / run_id
    if output.exists():
        raise FileExistsError("Existing rehearsal output is never overwritten; use a new run-id")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Positive finite per-worker timeout required")
    if data_root and (output.is_relative_to(Path(data_root).resolve()) or Path(data_root).resolve().is_relative_to(output)):
        raise ValueError("Dataset and rehearsal output trees must be disjoint")
    protocol = preflight(root, scope, data_root, ram_cap=ram_cap, output_base=output.parent)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "PROTOCOL.json", protocol)
    state = {"kind": KIND, "scope": scope, "status": protocol["status"], "execute_requested": execute,
             "full_pilot_approved": False, "model_execution": False, "research_metrics_exported": False,
             "protocol_sha256": file_sha256(output / "PROTOCOL.json"), "stages": []}
    write_json(output / "status.json", state)
    if protocol["status"] != "PREFLIGHT_PASS" or not execute:
        return state, output
    (output / "work").mkdir()
    (output / "stages").mkdir()
    (output / "logs").mkdir()
    state["status"] = "BUILDING"
    child = None
    try:
        for variant in VARIANTS:
            for stage in STAGES:
                required = protocol["memory_plan"]["phase_payload_plans_bytes"][stage]
                guard_memory(required, ram_cap)
                if shutil.disk_usage(output).free < protocol["memory_plan"]["required_free_disk_bytes"]:
                    raise OSError("Insufficient current disk including fixed headroom")
                state["active_stage"] = [variant, stage]
                write_json(output / "status.json", state)
                started = time.perf_counter()
                parent_rss = process_memory()["rss_bytes"]
                free_min = available_ram()
                with (output / "logs" / f"{variant}-{stage}.txt").open("x", encoding="utf-8") as log:
                    child = subprocess.Popen([sys.executable, str(root / "scripts/check_pcb_native_memory.py"),
                        "--worker", stage, "--variant", variant, "--payload", str(output), "--execute"],
                        cwd=root, stdout=log, stderr=subprocess.STDOUT)
                    while child.poll() is None:
                        if time.perf_counter()-started > timeout:
                            raise TimeoutError("Owned worker exceeded per-stage timeout; no readiness approval")
                        free_min = min(free_min, available_ram())
                        if free_min < RAM_RESERVE:
                            raise MemoryError("BLOCKED_MEMORY: available RAM fell below fixed runtime reserve")
                        time.sleep(.1)
                code = child.wait()
                state.update(last_worker_exit_code=code, owned_worker_exited=True)
                child = None
                path = output / "stages" / f"{variant}-{stage}.json"
                if path.is_file() and read_json(path).get("error", "").startswith("MemoryError:"):
                    raise MemoryError("BLOCKED_MEMORY: worker recheck failed; inspect preserved stage record")
                if code or not path.is_file():
                    raise RuntimeError(f"Worker failed/incomplete: {variant}/{stage}; inspect preserved log")
                result = read_json(path)
                if result.get("status") != "STAGE_COMPLETE" or result["stage"] != stage or result["variant"] != variant:
                    raise RuntimeError("Incomplete or wrong worker result")
                result.update(worker_exit_code=code, worker_exited=True,
                    parent_launch_to_exit_seconds=time.perf_counter()-started,
                    orchestrator_rss_at_launch_bytes=parent_rss,
                    orchestrator_rss_after_worker_exit_bytes=process_memory()["rss_bytes"],
                    parent_observed_system_available_min_bytes=min(free_min, available_ram()))
                write_json(path, result)
                state["stages"].append({"stage": stage, "variant": variant, "file": str(path.relative_to(output)),
                                        "sha256": file_sha256(path)})
                write_json(output / "status.json", state)
                print(f"{variant}/{stage}: STAGE_COMPLETE", flush=True)
            remove_owned_tree(output, output / "work" / variant)
        write_table(output, state["stages"])
        state.update(status="MEMORY_REHEARSAL_COMPLETE_NOT_FULL_APPROVAL", active_stage=None,
                     variant_workspaces_removed=True, synthetic_scenario_only=True,
                     stage_table_sha256=file_sha256(output / "stage_memory.csv"),
                     native_rehearsal_measured=scope == "native", measured_scenario_not_universal_peak_bound=True)
    except BaseException as error:
        if child is not None and child.poll() is None:
            child.terminate()  # Only this Popen-owned worker, never another user process.
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if child is not None:
            state.update(failed_worker_exit_code=child.poll(), owned_worker_exited=child.poll() is not None)
        state.update(status="BLOCKED_MEMORY" if isinstance(error, MemoryError) else "FAILED",
                     error=f"{type(error).__name__}: {error}", failed_workspace_preserved=True)
        write_json(output / "status.json", state)
        raise
    write_json(output / "status.json", state)
    try:
        load_completed_rehearsal(output)
    except BaseException as error:
        state.update(status="FAILED", error=f"Final artifact validation failed: {type(error).__name__}")
        write_json(output / "status.json", state)
        raise
    return state, output
