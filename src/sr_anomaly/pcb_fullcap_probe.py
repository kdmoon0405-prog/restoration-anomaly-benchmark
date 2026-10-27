"""Bounded resource fixture, never a fitted PCB bank or performance experiment."""
from __future__ import annotations

import csv
import gc
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

from . import pcb_model_resources as measured
from . import pcb_native_memory as memory
from . import pcb_resource_review as review
from . import pcb_tiled_models as models
from .bounded_bank import _integer, file_sha256
from .dataset import safe_component

KIND = "fullcap_synthetic_payload_resource_probe_not_research_bank"
COMPLETE = "FULLCAP_SYNTHETIC_RESOURCE_COMPLETE_NOT_FULL_APPROVAL"
FIXTURE_COMPLETE = "INJECTED_FIXTURE_COMPLETE_NOT_GPU_EVIDENCE"
SPEC = dict(rows=262144, dimension=1024, seed=11, query_tiles=2, chunk_vectors=8192)
CODE = ("src/sr_anomaly/pcb_fullcap_probe.py", "scripts/check_pcb_fullcap_probe.py")
REFERENCE_FILES = ("PROTOCOL.json", "status.json", "resources.json", "stage_times.csv", "raw/status.json")


def resource_plan(observed_small_peak):
    """An explicit allocation scenario, not a measured/safe upper bound."""
    observed_small_peak = _integer(observed_small_peak, "observed RSS")
    bank = SPEC["rows"] * SPEC["dimension"] * 4
    pairwise = 2 * 784 * SPEC["rows"] * 4
    generation = SPEC["chunk_vectors"] * SPEC["dimension"] * 5
    queries = 8 * 784 * SPEC["dimension"] * 4 + SPEC["query_tiles"] * 224 * 224 * 3
    payload = 3 * bank + pairwise + generation + queries + observed_small_peak
    return dict(bank_payload_bytes=bank, bank_input_scorer_index_copy_scenario_bytes=3*bank,
        two_pairwise_distance_arrays_scenario_bytes=pairwise, generation_float_and_bool_chunk_bytes=generation,
        query_workspace_scenario_bytes=queries, retained_entire_small_run_peak_scenario_bytes=observed_small_peak,
        payload_scenario_bytes=payload, ram_reserve_bytes=memory.RAM_RESERVE,
        required_available_ram_bytes=payload+memory.RAM_RESERVE,
        required_free_disk_bytes=bank+1024**2+memory.DISK_RESERVE,
        estimates_not_measured=True, upper_bound=False,
        limitations=["Copies/scratch plus an entire old RSS peak intentionally overlap in this planning scenario.",
            "FAISS/BLAS/runtime/page-cache allocations outside this scenario are not bounded.",
            "Synthetic values and six cold/first-call queries do not establish production throughput."])


def _checkpoints(backbone, swinir):
    return {name: dict(path=str(Path(path).resolve()), sha256=file_sha256(path))
        for name, path in (("backbone", backbone), ("swinir", swinir))}


def _validate_checkpoints(checkpoints):
    if set(checkpoints) != {"backbone", "swinir"}:
        raise ValueError("Exactly two pinned checkpoints required")
    for name, expected in (("backbone", models.BACKBONE_SHA256), ("swinir", models.SWINIR_SHA256)):
        item = checkpoints[name]
        if item["sha256"] != expected or file_sha256(item["path"]) != expected:
            raise ValueError(f"Pinned {name} checkpoint missing/changed")


def _bound_sources(root):
    frozen = memory.read_json(root/measured.runner.GEOMETRY/"PROTOCOL.json")["code_sha256"]
    if not frozen:
        raise ValueError("Missing frozen model/preprocessing source coverage")
    for name, digest in frozen.items():
        if file_sha256(measured.runner.safe_source(root, name)) != digest:
            raise ValueError("Frozen model/preprocessing source changed")
    for name, revision in (("SwinIR", models.SWINIR_COMMIT), ("patchcore-inspection", models.PATCHCORE_COMMIT)):
        actual = subprocess.check_output(["git", "-C", str(root/"third_party"/name), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise ValueError("Pinned model submodule revision changed")
    return {name: file_sha256(measured.runner.safe_source(root, name)) for name in sorted(set(CODE) | set(frozen))}


def prepare(root, reference, backbone, swinir, *, run_id):
    """No Torch/FAISS import, model creation or large allocation in preflight."""
    root, reference = Path(root).resolve(), Path(reference).resolve()
    output = root / "outputs/pcb-fullcap-probe" / safe_component(run_id, "run-id")
    if output.exists():
        raise FileExistsError("Existing output is never overwritten")
    if output.is_relative_to(reference) or reference.is_relative_to(output):
        raise ValueError("Reference and output trees must be disjoint")
    accepted = review.validate(reference, root)
    if accepted["execution_class"] != "REPORTED_CUDA_LIMITED_SMOKE":
        raise ValueError("A reviewed reported-CUDA limited smoke is required, not a CPU/injected fixture")
    sources = _bound_sources(root)
    plan = resource_plan(accepted["os_lifetime_peak_rss_bytes"])
    blockers, checkpoints = [], {}
    try:
        checkpoints = _checkpoints(backbone, swinir)
        _validate_checkpoints(checkpoints)
    except (OSError, ValueError) as error:
        blockers.append("BLOCKED_INPUTS: " + str(error))
    try:
        memory.guard_memory(plan["payload_scenario_bytes"])
    except MemoryError as error:
        blockers.append(str(error))
    ancestor = output.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < plan["required_free_disk_bytes"]:
        blockers.append("BLOCKED_DISK: payload plus fixed disk reserve unavailable")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    protocol = dict(kind=KIND, spec=SPEC.copy(), plan=plan, reference_run=str(reference),
        reference_sha256={name: file_sha256(reference/name) for name in REFERENCE_FILES},
        source_sha256=sources, source_commit=source,
        source_worktree_dirty=dirty, checkpoints=checkpoints, device="cuda",
        available_ram_snapshot_bytes=memory.available_ram(),
        free_disk_snapshot_bytes=shutil.disk_usage(ancestor).free,
        live_cuda_verified=False, requested_queries_per_variant=2, actual_pcb_bank_created=False,
        full_bank_validated=False, full_pilot_approved=False, metrics=None,
        input_kind="SYNTHETIC_BANK_AND_RGB_NOT_RESEARCH_PREDICTIONS", blockers=blockers)
    output.mkdir(parents=True, exist_ok=False)
    memory.write_json(output/"PROTOCOL.json", protocol)
    status = ("PREFLIGHT_PASS" if not blockers else "BLOCKED_MEMORY" if any(b.startswith("BLOCKED_MEMORY") for b in blockers)
              else "BLOCKED_INPUTS" if any(b.startswith("BLOCKED_INPUTS") for b in blockers) else "BLOCKED_DISK")
    state = dict(kind=KIND, status=status, blockers=blockers, protocol_sha256=file_sha256(output/"PROTOCOL.json"),
                 actual_pcb_bank_created=False, full_bank_validated=False, full_pilot_approved=False,
                 model_execution_started=False, payload_allocation_started=False, metrics=None)
    memory.write_json(output/"status.json", state)
    return output, state


def _validate(output, root):
    state, protocol = [memory.read_json(output/name) for name in ("status.json", "PROTOCOL.json")]
    if (state.get("status") != "PREFLIGHT_PASS" or state.get("kind") != KIND
            or protocol.get("kind") != KIND or protocol.get("spec") != SPEC
            or protocol.get("full_pilot_approved") is not False or protocol.get("full_bank_validated") is not False
            or state.get("protocol_sha256") != file_sha256(output/"PROTOCOL.json")
            or any(v.get("actual_pcb_bank_created") is not False or v.get("full_bank_validated") is not False
                   or v.get("full_pilot_approved") is not False or v.get("metrics") is not None
                   or v.get("blockers") != [] for v in (state, protocol))
            or protocol.get("device") != "cuda"
            or protocol.get("input_kind") != "SYNTHETIC_BANK_AND_RGB_NOT_RESEARCH_PREDICTIONS"):
        raise ValueError("Only an unchanged owned probe PREFLIGHT_PASS may execute")
    if protocol["source_sha256"] != _bound_sources(root):
        raise ValueError("Probe or frozen source changed after preflight")
    if set(protocol["reference_sha256"]) != set(REFERENCE_FILES):
        raise ValueError("Incomplete accepted-evidence hash coverage")
    reference = Path(protocol["reference_run"])
    for name, digest in protocol["reference_sha256"].items():
        if file_sha256(reference/name) != digest:
            raise ValueError("Accepted smoke evidence changed after preflight")
    accepted = review.validate(reference, root)
    if accepted["execution_class"] != "REPORTED_CUDA_LIMITED_SMOKE":
        raise ValueError("Changed reference execution kind")
    if protocol["plan"] != resource_plan(accepted["os_lifetime_peak_rss_bytes"]):
        raise ValueError("Resource planning scenario changed")
    _validate_checkpoints(protocol["checkpoints"])
    for name in ("synthetic_bank_payload.npy", "resources.json", "stage_times.csv"):
        if (output/name).exists():
            raise FileExistsError("Existing probe payload is never overwritten")
    return state, protocol


def _cuda(minimum_free):
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; no CPU fallback or payload allocation")
    free, total = torch.cuda.mem_get_info()
    if free < minimum_free:
        raise MemoryError("BLOCKED_VRAM: free bytes below the previous small-run reserved peak (only a floor)")
    sync, snapshot = measured._cuda_tools("cuda")
    return sync, snapshot, dict(gpu_name=torch.cuda.get_device_name(0), free_bytes=free, total_bytes=total,
        torch_version=torch.__version__, cuda_runtime=torch.version.cuda, previous_peak_is_only_a_floor=True)


def _fill(path, shape):
    with path.open("xb"):
        pass
    values = np.lib.format.open_memmap(path, mode="w+", dtype=np.float32, shape=shape)
    rng = np.random.default_rng(SPEC["seed"])
    try:
        for start in range(0, shape[0], SPEC["chunk_vectors"]):
            size = min(SPEC["chunk_vectors"], shape[0]-start)
            chunk = rng.standard_normal((size, shape[1]), dtype=np.float32)
            if not np.isfinite(chunk).all():
                raise ValueError("Nonfinite synthetic resource fixture")
            values[start:start+size] = chunk
        values.flush()
    finally:
        del values
        gc.collect()


def execute(output, root, *, factory=None, _fixture_shape=None):
    """CLI executes in its own process; injection is for tiny CPU tests only."""
    # shortcut: calls are workload-bounded, not time-bounded; add a worker timeout before unattended runs.
    output, root = Path(output).resolve(), Path(root).resolve()
    if output.parent != (root/"outputs/pcb-fullcap-probe").resolve():
        raise ValueError("Only the owned probe output directory may execute")
    state, protocol = _validate(output, root)
    fixture = factory is not None
    if fixture and _fixture_shape is None:
        raise ValueError("Injected CPU fixtures require an explicit tiny shape")
    if _fixture_shape is not None and not fixture:
        raise ValueError("Only injected CPU fixtures may override allocation shape")
    shape = tuple(_fixture_shape or (SPEC["rows"], SPEC["dimension"]))
    if len(shape) != 2 or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in shape):
        raise ValueError("Positive fixture shape required")
    if fixture and math.prod(shape) > 4096:
        raise ValueError("Injected CPU fixture exceeds 4096 floats")
    payload = output/"synthetic_bank_payload.npy"
    result = dict(kind=KIND, input_kind="injected_fixture_NOT_GPU_evidence" if fixture else protocol["input_kind"],
        python_version=sys.version.split()[0], numpy_version=np.__version__,
        actual_shape=list(shape), actual_pcb_bank_created=False, full_bank_validated=False,
        full_pilot_approved=False, metrics=None, predictions_exported=False, gt_callback_used=False,
        model_execution_started=False, actual_fullcap_payload_observed=False, query_checks=[],
        process_exit_self_verified=False, adapter_close_returned=False, payload_cleanup=False)
    result["drive_free_bytes_at_start"] = shutil.disk_usage(output).free
    adapter = transform = bank = recorder = None
    monitor, started = measured._OutputMonitor(output), False
    begin = time.perf_counter()
    state.update(status="MEASURING")
    memory.write_json(output/"status.json", state)
    try:
        memory.guard_memory(protocol["plan"]["payload_scenario_bytes"])
        if shutil.disk_usage(output).free < protocol["plan"]["required_free_disk_bytes"]:
            raise OSError("BLOCKED_DISK: insufficient fresh disk budget")
        previous = memory.read_json(Path(protocol["reference_run"])/"resources.json")
        if fixture:
            sync, snapshot, gpu = lambda: None, lambda: None, None
        else:
            sync, snapshot, gpu = _cuda(previous["cuda_at_end"]["max_reserved_bytes_since_profiler_start"])
        result.update(cuda_device=gpu, cuda_at_start=snapshot())
        recorder = measured.Recorder(sync, cuda_snapshot=snapshot)
        monitor.start()
        started = True
        state["payload_allocation_started"] = True
        memory.write_json(output/"status.json", state)
        recorder.call("synthetic_payload_fill", _fill, payload, shape)
        before = file_sha256(payload)
        bank = np.load(payload, mmap_mode="r", allow_pickle=False)
        if bank.shape != shape or bank.dtype != np.float32 or bank.flags.writeable:
            raise ValueError("Synthetic read-only payload contract mismatch")
        checkpoints = protocol["checkpoints"]
        result["model_execution_started"] = not fixture
        state.update(model_factory_call_started=True, model_execution_started=not fixture)
        memory.write_json(output/"status.json", state)
        actual = models.create_models if factory is None else factory
        adapter, transform = recorder.call("model_factory", actual, root, "cpu" if fixture else "cuda",
            checkpoints["backbone"]["path"], checkpoints["swinir"]["path"])
        recorder.call("bank_bind_CPU_scorer_index", adapter.bind_bank, bank)
        tiles = np.random.default_rng(SPEC["seed"]).integers(0, 256,
            (SPEC["query_tiles"], 224, 224, 3), dtype=np.uint8)
        for index, tile in enumerate(tiles):
            for variant in models.VARIANTS:
                stage = "restoration_swinir_x4" if variant == "swinir_x4" else "preparation_"+variant
                rgb = recorder.call(stage, transform, tile, variant)
                models.check_rgb(rgb)
                values, score = recorder.call("detector_inference_including_CPU_FAISS", adapter.predict, rgb)
                if values.shape != (224, 224) or values.dtype != np.float32 or not np.isfinite(values).all() or not math.isfinite(score):
                    raise ValueError("Nonfinite/invalid synthetic-query output")
                result["query_checks"].append(dict(tile=index, variant=variant, finite=True,
                    detector_seconds=recorder.rows[-1]["elapsed_seconds"]))
        after = file_sha256(payload)
        if after != before:
            raise ValueError("Synthetic input payload changed during binding/query")
        result.update(synthetic_payload_sha256=before, payload_unchanged=True,
            actual_fullcap_payload_observed=not fixture and shape == (SPEC["rows"], SPEC["dimension"]))
        state["status"] = FIXTURE_COMPLETE if fixture else COMPLETE
    except Exception as error:
        state.update(status="FAILED", error=f"{type(error).__name__}: {error}")
    finally:
        try:
            if adapter is not None:
                recorder.call("adapter_close", adapter.close)
                result["adapter_close_returned"] = True
        except Exception as error:
            state.update(status="FAILED", error="Adapter cleanup: "+str(error))
        adapter = transform = bank = None
        gc.collect()
        try:
            if started:
                result["process_memory"] = monitor.finish()
            result["cuda_at_end"] = snapshot() if recorder is not None else None
        except Exception as error:
            state.update(status="FAILED", error="Resource monitor: "+str(error))
        if state["status"] in (COMPLETE, FIXTURE_COMPLETE):
            try:
                result["output_payload_before_cleanup_bytes"] = memory.disk_bytes(output)
                payload.unlink()
                result["payload_cleanup"] = True
            except OSError as error:
                state.update(status="FAILED", error="Payload cleanup: "+str(error))
        end = time.perf_counter()
        result.update(status=state["status"], perf_counter_start=begin, perf_counter_end=end, elapsed_seconds=end-begin,
            phase_summary=recorder.summary() if recorder else {}, error=state.get("error"),
            payload_retained=payload.exists(), drive_free_bytes_at_end=shutil.disk_usage(output).free,
            drive_delta_is_not_exclusive_output_size=True)
        memory.write_json(output/"resources.json", result)
        fields = ["stage", "perf_counter_start", "perf_counter_end", "elapsed_seconds", "completed",
                  "rss_before_bytes", "rss_after_bytes", "os_lifetime_peak_rss_after_bytes"] + ["cuda_"+n for n in review.CUDA_FIELDS]
        with (output/"stage_times.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(recorder.rows if recorder else [])
        state.update(resources_sha256=file_sha256(output/"resources.json"), timings_sha256=file_sha256(output/"stage_times.csv"))
        memory.write_json(output/"status.json", state)
    return state
