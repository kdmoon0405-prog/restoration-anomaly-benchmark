"""Guarded real normal-fit stream only; no prediction, calibration or full executor."""
from __future__ import annotations

import csv
from dataclasses import asdict
import gc
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

from . import bounded_bank as bank
from . import pcb_input_binding as binding
from . import pcb_model_resources as measured
from . import pcb_native_memory as memory
from . import pcb_tiled_models as models
from . import pcb_tiled_runner as runner
from . import pcb_tiling as geometry
from .dataset import safe_component
from .tiled_cpu_pipeline import feature_chunks

KIND = "actual_pcb_normal_fit_bank_only_not_full_pilot"
COMPLETE = "REAL_FIT_BANK_COMPLETE_NOT_FULL_APPROVAL"
FIXTURE_COMPLETE = "INJECTED_FIT_FIXTURE_COMPLETE_NOT_RESEARCH_BANK"
SPEC = dict(total_vectors=27132672, dimension=1024, capacity=262144, seed=11,
            max_chunk_vectors=8192)
CODE = ("src/sr_anomaly/pcb_fit_bank.py", "scripts/run_pcb_fit_bank.py",
        "src/sr_anomaly/pcb_input_binding.py", "src/sr_anomaly/tiled_cpu_pipeline.py",
        "src/sr_anomaly/bounded_bank.py", "src/sr_anomaly/pcb_tiled_models.py",
        "src/sr_anomaly/pcb_model_resources.py", "src/sr_anomaly/pcb_native_memory.py",
        "src/sr_anomaly/pcb_tiled_runner.py", "src/sr_anomaly/pcb_tiling.py")
REFERENCES = (runner.GEOMETRY/"MANIFEST.json", runner.GEOMETRY/"PROTOCOL.json",
              runner.GEOMETRY/"INPUTS.csv", runner.GEOMETRY/"layouts.json",
              runner.BUDGET/"PROTOCOL.json", runner.BUDGET/"selection_plan.json", runner.PROTOCOL)


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _references(root):
    return {p.as_posix(): bank.file_sha256(root/p) for p in REFERENCES}


def _sources(root):
    frozen = memory.read_json(root/runner.GEOMETRY/"PROTOCOL.json")["code_sha256"]
    budget = memory.read_json(root/runner.BUDGET/"PROTOCOL.json")
    for manifest in (frozen, budget["code_sha256"]):
        if not manifest:
            raise ValueError("Missing frozen source bindings")
        for name, digest in manifest.items():
            if bank.file_sha256(runner.safe_source(root, name)) != digest:
                raise ValueError("Frozen source changed: "+name)
    for name, revision in (("SwinIR", models.SWINIR_COMMIT),
                           ("patchcore-inspection", models.PATCHCORE_COMMIT)):
        if _git(root/"third_party"/name, "rev-parse", "HEAD") != revision:
            raise ValueError("Pinned submodule revision changed: "+name)
    return {name: bank.file_sha256(runner.safe_source(root, name))
            for name in sorted(set(CODE) | set(frozen) | set(budget["code_sha256"]))}


def _inventory(root, inputs):
    """Metadata only. Return ONLY normal-fit descriptors to the extraction path."""
    fit = tuple(p for p in inputs.parents if p.split == "fit")
    tiles = sum(len(geometry.tile_boxes(p.size_wh)) for p in fit)
    budget = memory.read_json(root/runner.BUDGET/"PROTOCOL.json")
    if (budget["settings"] != SPEC or len(fit) != 721 or any(p.label != 0 for p in fit)
            or tiles != 34608 or tiles*784 != SPEC["total_vectors"]):
        raise ValueError("Frozen fit inventory/settings differ from 721/34608/27132672")
    for name, digest in budget["geometry_references"].items():
        if bank.file_sha256(root/runner.GEOMETRY/name) != digest:
            raise ValueError("Budget geometry reference changed")
    _, indices = bank.selection_plan(**SPEC)
    selection = bank.index_sha256(indices)
    if selection != memory.read_json(root/runner.BUDGET/"selection_plan.json")["selection_indices_sha256"]:
        raise ValueError("Frozen selected-index SHA mismatch; never reselect")
    return fit, selection


def resource_plan(fit):
    """Explicit fit-only payload scenarios; not measured peaks or upper bounds."""
    b = SPEC["capacity"]*SPEC["dimension"]*4
    terms = dict(two_bank_resident_copy_scenario_bytes=2*b,
        selection_python_numpy_workspace_scenario_bytes=64*1024**2,
        feature_float_bool_chunk_bytes=SPEC["max_chunk_vectors"]*SPEC["dimension"]*5,
        three_feature_batch_buffers_bytes=3*2*784*SPEC["dimension"]*4,
        native_rgb_decode_scenario_bytes=max(p.size_wh[0]*p.size_wh[1] for p in fit)*16,
        model_checkpoint_cpu_runtime_scenario_bytes=2*1024**3,
        metadata_timing_workspace_scenario_bytes=64*1024**2)
    payload = sum(terms.values())
    return dict(terms=terms, bank_payload_bytes=b, payload_scenario_bytes=payload,
        required_available_ram_bytes=payload+memory.RAM_RESERVE,
        ram_reserve_bytes=memory.RAM_RESERVE,
        required_free_disk_bytes=b+SPEC["capacity"]*8+64*1024**2+memory.DISK_RESERVE,
        estimates_not_measured=True, upper_bound=False,
        assumptions=["Bank writer allocation and resident saved/mmap pages deliberately overlap in the scenario.",
            "2 GiB model/checkpoint/runtime allowance is a planning assumption, not an observed peak.",
            "Existing factory constructs both PatchCore and SwinIR; neither scorer binding nor restoration is called.",
            "GPU activations/allocator and extra OS/library/page-cache effects are not bounded.",
            "No global feature stack, prediction maps or calibration/evaluation arrays are created."])


def _checkpoints(backbone, swinir):
    result = {}
    for name, path, expected in (("backbone", backbone, models.BACKBONE_SHA256),
                                 ("swinir", swinir, models.SWINIR_SHA256)):
        path = Path(path).resolve()
        if bank.file_sha256(path) != expected:
            raise ValueError("Pinned checkpoint changed: "+name)
        result[name] = dict(path=str(path), sha256=expected)
    return result


def _fit_hashes(inputs, fit):
    receipts = {}
    for parent in fit:
        digest = bank.file_sha256(runner.safe_source(inputs.data_root, parent.sample))
        if digest != inputs._row(parent)["image_sha256"]:
            raise ValueError("Frozen fit RGB checksum mismatch: "+parent.sample)
        receipts[parent.sample] = digest
    return receipts


def _guard(plan, output):
    memory.guard_memory(plan["payload_scenario_bytes"])
    if shutil.disk_usage(output).free < plan["required_free_disk_bytes"]:
        raise OSError("BLOCKED_DISK: fit bank plus metadata and fixed disk reserve unavailable")


def prepare(root, data_root, backbone, swinir, *, run_id):
    """Static preflight: hashes/metadata only, no Torch/FAISS imports or models."""
    root, data_root = Path(root).resolve(), Path(data_root).resolve()
    output = (root/"outputs/pcb-fit-bank"/safe_component(run_id, "run-id")).resolve()
    if output.is_relative_to(data_root) or data_root.is_relative_to(output):
        raise ValueError("Fit output and input trees must be disjoint")
    output.mkdir(parents=True, exist_ok=False)
    state = dict(kind=KIND, status="PREPARING", actual_pcb_bank_created=False,
        fit_bank_integrity_validated=False, full_bank_validated=False,
        full_cohort_inference_complete=False, full_pilot_approved=False,
        metrics=None, thresholds=None, calibration=None, gt_callback_used=False,
        model_execution_started=False)
    memory.write_json(output/"status.json", state)
    try:
        inputs = binding.FrozenPCBInputs(root, data_root)
        fit, selection = _inventory(root, inputs)
        plan = resource_plan(fit)
        protocol = dict(kind=KIND, spec=SPEC.copy(), patch_shape=[28,28], batch_tiles=2,
            geometry_id=inputs.geometry_id, data_root=str(data_root),
            fit_parents=[asdict(p) for p in fit], fit_input_sha256=_fit_hashes(inputs, fit),
            official_csv_sha256=inputs.official_sha256,
            selection_indices_sha256=selection, plan=plan,
            code_sha256=_sources(root),
            references_sha256=_references(root),
            checkpoints=_checkpoints(backbone, swinir),
            source_commit=_git(root, "rev-parse", "HEAD"),
            source_worktree_dirty=bool(_git(root, "status", "--porcelain")),
            requested_device="cuda", actual_device=None, cuda_available=None, gpu_name=None,
            cuda_check="EXECUTE_ONLY_NOT_CHECKED_BY_STATIC_PREFLIGHT",
            python_executable=sys.executable, python_version=sys.version,
            numpy_version=np.__version__, fit_order="INPUTS.csv -> row-major tiles -> batch/patch-y/patch-x",
            metrics=None, full_pilot_approved=False)
        blockers = ["runtime dependency missing: "+name for name in ("torch", "torchvision", "faiss", "timm")
                    if importlib.util.find_spec(name) is None]
        try:
            _guard(plan, output)
        except (MemoryError, OSError) as error:
            blockers.append(str(error))
        protocol.update(blockers=blockers, available_ram_bytes=runner.available_ram(),
                        free_disk_bytes=shutil.disk_usage(output).free)
        runner.write_json(output/"PROTOCOL.json", protocol)
        state.update(status="PREFLIGHT_BLOCKED" if blockers else "PREFLIGHT_PASS",
            blockers=blockers, protocol_sha256=bank.file_sha256(output/"PROTOCOL.json"))
    except BaseException as error:
        state.update(status="FAILED_PREFLIGHT", error=f"{type(error).__name__}: {error}")
        memory.write_json(output/"status.json", state)
        raise
    memory.write_json(output/"status.json", state)
    return output, state


def _validate(output, root):
    if output.parent != (root/"outputs/pcb-fit-bank").resolve():
        raise ValueError("Only owned fit output may execute")
    state, protocol = memory.read_json(output/"status.json"), memory.read_json(output/"PROTOCOL.json")
    if (state.get("kind") != KIND or state.get("status") != "PREFLIGHT_PASS"
            or state.get("protocol_sha256") != bank.file_sha256(output/"PROTOCOL.json")
            or protocol.get("kind") != KIND or protocol.get("spec") != SPEC
            or protocol.get("patch_shape") != [28,28] or protocol.get("batch_tiles") != 2
            or protocol.get("requested_device") != "cuda" or protocol.get("blockers")
            or protocol.get("full_pilot_approved") is not False or protocol.get("metrics") is not None
            or any(state.get(name) is not False for name in ("actual_pcb_bank_created",
                "fit_bank_integrity_validated", "full_bank_validated", "full_cohort_inference_complete",
                "full_pilot_approved", "gt_callback_used", "model_execution_started"))):
        raise ValueError("Incomplete, modified or wrong fit-only preflight")
    if any((output/name).exists() for name in ("bank", "resources.json", "stage_times.csv", "fit_progress.json")):
        raise FileExistsError("Existing fit payload/progress is never overwritten or resumed")
    inputs = binding.FrozenPCBInputs(root, protocol["data_root"])
    fit, selection = _inventory(root, inputs)
    if ([asdict(p) for p in fit] != [dict(p, size_wh=tuple(p["size_wh"])) for p in protocol["fit_parents"]]
            or selection != protocol["selection_indices_sha256"]
            or inputs.official_sha256 != protocol["official_csv_sha256"]
            or inputs.geometry_id != protocol["geometry_id"]
            or _fit_hashes(inputs, fit) != protocol["fit_input_sha256"]
            or _sources(root) != protocol["code_sha256"]
            or _references(root) != protocol["references_sha256"]
            or _git(root, "rev-parse", "HEAD") != protocol["source_commit"]
            or bool(_git(root, "status", "--porcelain")) != protocol["source_worktree_dirty"]
            or resource_plan(fit) != protocol["plan"]):
        raise ValueError("Fit source/input/reference/order/selection/provenance changed after preflight")
    checks = protocol["checkpoints"]
    if _checkpoints(checks["backbone"]["path"], checks["swinir"]["path"]) != checks:
        raise ValueError("Checkpoint receipts changed")
    return state, protocol, inputs, fit


def _cuda():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required for actual fit-only execution; CPU fallback is forbidden")
    sync, snapshot = measured._cuda_tools("cuda")
    return sync, snapshot, dict(requested_device="cuda", actual_device="cuda", cuda_available=True,
        gpu_name=torch.cuda.get_device_name(torch.cuda.current_device()),
        torch_version=torch.__version__, cuda_runtime=torch.version.cuda)


def _verify_bank(output, settings, selection):
    values = indices = None
    try:
        values, indices, metadata = bank.load_complete_bank(output/"bank")
        if (any(metadata[k] != v for k,v in settings.items())
                or metadata["selection_indices_sha256"] != selection
                or metadata["progress"]["observed_vectors"] != settings["total_vectors"]):
            raise ValueError("Stored bank settings/count/selection mismatch")
        for start in range(0, len(values), settings["max_chunk_vectors"]):
            if not np.isfinite(values[start:start+settings["max_chunk_vectors"]]).all():
                raise ValueError("Stored bank contains nonfinite features")
        return metadata
    finally:
        for value in (values, indices):
            if value is not None:
                value._mmap.close()


def execute(output, root, *, factory=None, _fixture=None):
    """One fresh fit, no resume. Private injection is tiny CPU testing only."""
    output, root = Path(output).resolve(), Path(root).resolve()
    state, protocol, inputs, fit = _validate(output, root)
    fixture = factory is not None
    if fixture != (_fixture is not None):
        raise ValueError("CPU injection requires explicit tiny settings and a fake factory")
    settings, patch_shape = SPEC.copy(), (28,28)
    if fixture:
        settings, patch_shape = _fixture["settings"], tuple(_fixture["patch_shape"])
        for k,v in settings.items():
            bank._integer(v, k, 0 if k == "seed" else 1)
        if (set(settings) != set(SPEC) or settings["total_vectors"]*settings["dimension"] > 4096
                or len(patch_shape) != 2 or any(type(n) is not int or n < 1 for n in patch_shape)):
            raise ValueError("Injected fixture exceeds tiny feature budget")
    result = dict(kind=KIND, input_kind="injected_synthetic_fixture_NOT_research_bank" if fixture else "fit_normal_feature_stream",
        actual_pcb_bank_created=False, fit_bank_integrity_validated=False, full_bank_validated=False,
        full_cohort_inference_complete=False, full_pilot_approved=False,
        metrics=None, thresholds=None, calibration=None, gt_callback_used=False,
        model_execution_started=False, adapter_close_returned=False, references_released=False,
        process_exit_self_verified=False, settings=settings, patch_shape=list(patch_shape),
        timing_semantics="Disjoint child calls are inside outer time; fit_stream_wall_seconds also contains extraction, never add it to children.",
        peak_semantics="Sampled RSS/OS lifetime peak/CUDA counters are distinct, not general upper bounds.",
        python_executable=sys.executable, python_version=sys.version, numpy_version=np.__version__)
    adapter = transform = chunks = recorder = None
    monitor, started, failure = measured._OutputMonitor(output), False, None
    begin = time.perf_counter()
    state.update(status="RUNNING", fixture_injected=fixture)
    memory.write_json(output/"status.json", state)
    result["free_disk_bytes_at_start"] = shutil.disk_usage(output).free
    try:
        _guard(protocol["plan"], output)
        if fixture:
            sync, snapshot, device = lambda: None, lambda: None, dict(actual_device="cpu", cuda_available=False)
        else:
            sync, snapshot, device = _cuda()
        result.update(device)
        state.update({k: result[k] for k in ("actual_device", "cuda_available")})
        state["gpu_name"] = result.get("gpu_name")
        result["cuda_at_start"] = snapshot()
        recorder = measured.Recorder(sync, cuda_snapshot=snapshot)
        monitor.start()
        started = True
        actual_factory = models.create_models if factory is None else factory
        state["model_execution_started"] = result["model_execution_started"] = not fixture
        memory.write_json(output/"status.json", state)
        checks = protocol["checkpoints"]
        adapter, transform = recorder.call("model_factory", actual_factory, root,
            "cpu" if fixture else "cuda", checks["backbone"]["path"], checks["swinir"]["path"])
        # Retain the existing factory's SwinIR closure until cleanup; never call it.
        progress = dict(loaded_fit_parents=0, current_fit_parent=None, consumed_vectors=0)
        last_write = [0.0]

        def load(parent):
            if parent not in fit or parent.split != "fit" or parent.label != 0:
                raise ValueError("Only frozen normal-fit RGB may enter extraction")
            values = inputs.rgb(parent)
            progress.update(loaded_fit_parents=progress["loaded_fit_parents"]+1, current_fit_parent=parent.sample)
            memory.write_json(output/"fit_progress.json", progress)
            return values

        def extract(rgb):
            return recorder.call("feature_extraction", adapter.extract, rgb)

        def stream():
            source = feature_chunks(fit, load, extract, patch_shape=patch_shape,
                dimension=settings["dimension"], batch_tiles=2, max_chunk_vectors=settings["max_chunk_vectors"])
            try:
                for values in source:
                    rows = len(values)
                    yield values
                    progress["consumed_vectors"] += rows
                    if time.perf_counter()-last_write[0] >= 5:
                        memory.write_json(output/"fit_progress.json", progress)
                        last_write[0] = time.perf_counter()
                    del values
            finally:
                source.close()

        chunks = stream()
        provenance = dict(input_kind="synthetic" if fixture else "fit_normal_feature_stream",
            artifact_kind="injected_fixture" if fixture else KIND,
            fit_protocol_sha256=state["protocol_sha256"], source_commit=protocol["source_commit"],
            source_worktree_dirty=protocol["source_worktree_dirty"],
            selection_indices_sha256=protocol["selection_indices_sha256"], geometry_id=protocol["geometry_id"])
        stream_start = time.perf_counter()
        bank.save_bank(chunks, output/"bank", provenance=provenance, **settings)
        result["fit_stream_wall_seconds_including_extraction_and_save"] = time.perf_counter()-stream_start
        memory.write_json(output/"fit_progress.json", progress)
        if progress["loaded_fit_parents"] != len(fit) or progress["consumed_vectors"] != settings["total_vectors"]:
            raise ValueError("Fit parent/vector stream incomplete")
        selection = protocol["selection_indices_sha256"]
        if fixture:
            _, selected = bank.selection_plan(**settings)
            selection = bank.index_sha256(selected)
            del selected
        metadata = recorder.call("saved_bank_integrity", _verify_bank, output, settings, selection)
        result.update(feature_counts=metadata["progress"], actual_shape=[metadata["selected_count"], metadata["dimension"]],
            selection_indices_sha256=selection,
            bank_sha256={n: bank.file_sha256(output/"bank"/n) for n in ("bank.npy", "selected_indices.npy", "status.json")})
        inputs.verify_references()
        if not fixture and (_sources(root) != protocol["code_sha256"]
                            or _references(root) != protocol["references_sha256"]
                            or _checkpoints(checks["backbone"]["path"], checks["swinir"]["path"]) != checks
                            or _fit_hashes(inputs, fit) != protocol["fit_input_sha256"]):
            raise ValueError("Sources or fit inputs changed during execution")
        runner.write_json(output/"fit_rgb_receipts.json", inputs.rgb_receipts)
        result["fit_rgb_receipts_sha256"] = bank.file_sha256(output/"fit_rgb_receipts.json")
        result.update(fit_bank_integrity_validated=not fixture, actual_pcb_bank_created=not fixture)
        state["status"] = FIXTURE_COMPLETE if fixture else COMPLETE
    except BaseException as error:
        failure = error
        status = ("BLOCKED_MEMORY" if isinstance(error, MemoryError) else
                  "BLOCKED_DISK" if str(error).startswith("BLOCKED_DISK:") else "FAILED")
        state.update(status=status, error=f"{type(error).__name__}: {error}")
    finally:
        cleanup_errors = []
        for name, closer in (("stream", chunks.close if chunks is not None else None),
                             ("adapter", (lambda: recorder.call("adapter_close", adapter.close)) if adapter is not None else None)):
            if closer is None:
                continue
            try:
                closer()
                if name == "adapter":
                    result["adapter_close_returned"] = True
            except BaseException as error:
                failure = failure or error
                cleanup_errors.append(f"{type(error).__name__}: {error}")
        closer = None
        if cleanup_errors:
            state.update(status="FAILED", cleanup_errors=cleanup_errors)
        chunks = adapter = transform = None
        gc.collect()
        result["references_released"] = True
        result["reference_release_scope"] = "Owned adapter/transform/chunk variables cleared; exception frames or allocator caches may persist until CLI process exit."
        try:
            if started:
                result["process_memory"] = monitor.finish()
                result["process_memory"].pop("sampled_workspace_disk_max_bytes", None)
            result["cuda_at_end"] = snapshot() if recorder else None
        except BaseException as error:
            failure = failure or error
            state.update(status="FAILED", resource_error=f"{type(error).__name__}: {error}")
        end = time.perf_counter()
        result.update(status=state["status"], perf_counter_start=begin, perf_counter_end=end,
            outer_elapsed_seconds=end-begin, phase_summary=recorder.summary() if recorder else {},
            output_payload_bytes_before_resource_files=memory.disk_bytes(output),
            free_disk_bytes_at_end=shutil.disk_usage(output).free)
        memory.write_json(output/"resources.json", result)
        rows = recorder.rows if recorder else []
        fields = list(rows[0]) if rows else ["stage", "elapsed_seconds", "completed"]
        with (output/"stage_times.csv").open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        state.update(actual_pcb_bank_created=result["actual_pcb_bank_created"],
            fit_bank_integrity_validated=result["fit_bank_integrity_validated"],
            resources_sha256=bank.file_sha256(output/"resources.json"),
            timings_sha256=bank.file_sha256(output/"stage_times.csv"))
        memory.write_json(output/"status.json", state)
    if failure is not None:
        raise failure
    return state
