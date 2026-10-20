"""Opt-in resource evidence around the unchanged, limited raw model smoke."""
from __future__ import annotations

import csv
import os
from pathlib import Path
import shutil
import time

from . import pcb_native_memory as memory
from . import pcb_tiled_runner as runner
from .bounded_bank import DEFAULT_CAPACITY, file_sha256
from .dataset import safe_component

KIND = "limited_model_smoke_resource_instrumentation_not_full_pilot"
CODE = ("src/sr_anomaly/pcb_model_resources.py", "scripts/profile_pcb_model_smoke.py",
        "src/sr_anomaly/pcb_input_binding.py", "src/sr_anomaly/pcb_native_memory.py")


def prepare(root, data_root, backbone_checkpoint, swinir_checkpoint, *, run_id, device="auto", ram_budget=None):
    """Fresh existing preflight only; neither models nor bank arrays are created."""
    root = Path(root)
    output = root / "outputs/pcb-model-resource-smoke" / safe_component(run_id, "run-id")
    output.mkdir(parents=True, exist_ok=False)
    state = {"kind": KIND, "status": "PREPARING", "full_pilot_approved": False,
             "model_execution_started": False, "factory_call_started": False, "metrics_exported": False}
    memory.write_json(output / "status.json", state)
    try:
        report = runner.preflight(root, data_root, backbone_checkpoint, swinir_checkpoint,
                                  scope="model-smoke", device=device, ram_budget=ram_budget)
        protocol = {"kind": KIND, "scope": "model-smoke", "preflight": report,
                    "wrapper_code_sha256": {name: file_sha256(root / name) for name in CODE},
                    "input_reference_sha256": {
                        (runner.GEOMETRY / "MANIFEST.json").as_posix(): report["manifest_sha256"],
                        **{Path(name).as_posix(): digest for name, digest in report["references_sha256"].items()}},
                    "smoke_bank_vectors_expected": 37632, "full_bank_capacity_not_validated": DEFAULT_CAPACITY,
                    "source_worktree_dirty": report["source_worktree_dirty"],
                    "metrics": None, "full_pilot_approved": False}
        runner.write_json(output / "PROTOCOL.json", protocol)
        state.update(status=report["status"], protocol_sha256=file_sha256(output / "PROTOCOL.json"))
        memory.write_json(output / "status.json", state)
        return output, report
    except BaseException as error:
        state.update(status="FAILED_PREFLIGHT", error=f"{type(error).__name__}: {error}")
        memory.write_json(output / "status.json", state)
        raise


def _cuda_tools(device):
    if device == "cpu":
        return lambda: None, lambda: None
    if device != "cuda":
        raise ValueError("A resolved cpu/cuda device is required")
    import torch
    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)

    def snapshot():
        return {"allocated_bytes": torch.cuda.memory_allocated(device),
                "reserved_bytes": torch.cuda.memory_reserved(device),
                "max_allocated_bytes_since_profiler_start": torch.cuda.max_memory_allocated(device),
                "max_reserved_bytes_since_profiler_start": torch.cuda.max_memory_reserved(device)}
    return lambda: torch.cuda.synchronize(device), snapshot


class Recorder:
    """Disjoint wrapped calls; outer execution time includes these plus IO/assembly."""
    def __init__(self, synchronize, *, clock=time.perf_counter, process_probe=memory.process_memory,
                 cuda_snapshot=lambda: None):
        self.synchronize, self.clock, self.rows = synchronize, clock, []
        self.process_probe, self.cuda_snapshot = process_probe, cuda_snapshot

    def call(self, stage, function, *args, **kwargs):
        self.synchronize()
        rss_before = self.process_probe()["rss_bytes"]
        start, success = self.clock(), False
        try:
            result = function(*args, **kwargs)
            success = True
            return result
        finally:
            self.synchronize()
            end = self.clock()
            process = self.process_probe()
            self.rows.append({"stage": stage, "perf_counter_start": start, "perf_counter_end": end,
                "elapsed_seconds": end - start, "completed": success, "rss_before_bytes": rss_before,
                "rss_after_bytes": process["rss_bytes"],
                "os_lifetime_peak_rss_after_bytes": process["os_lifetime_peak_rss_bytes"],
                **{f"cuda_{key}": value for key, value in (self.cuda_snapshot() or {}).items()}})

    def summary(self):
        return {stage: {"call_count": len(rows), "completed_calls": sum(r["completed"] for r in rows),
                        "sum_elapsed_seconds": sum(r["elapsed_seconds"] for r in rows),
                        "min_elapsed_seconds": min(r["elapsed_seconds"] for r in rows),
                        "max_elapsed_seconds": max(r["elapsed_seconds"] for r in rows)}
                for stage in sorted({r["stage"] for r in self.rows})
                for rows in [[r for r in self.rows if r["stage"] == stage]]}


class _MeasuredAdapter:
    def __init__(self, adapter, recorder):
        self.adapter, self.recorder = adapter, recorder

    def extract(self, rgb):
        return self.recorder.call("feature_extraction", self.adapter.extract, rgb)

    def bind_bank(self, bank):
        return self.recorder.call("bank_bind_CPU_scorer_index", self.adapter.bind_bank, bank)

    def predict(self, rgb):
        return self.recorder.call("detector_inference_including_CPU_FAISS", self.adapter.predict, rgb)

    def close(self):
        close = getattr(self.adapter, "close", None)
        try:
            if close is not None:
                self.recorder.call("adapter_close", close)
        finally:
            self.adapter = None


class _OutputMonitor(memory.Monitor):
    def sample(self):
        disk_due = time.perf_counter() >= self.next_disk
        super().sample()
        if disk_due:
            self.values["sampled_output_disk_max_bytes"] = max(
                self.values.get("sampled_output_disk_max_bytes", 0), memory.disk_bytes(self.output))


def _validate(output, root):
    state = memory.read_json(output / "status.json")
    protocol = memory.read_json(output / "PROTOCOL.json")
    if (state.get("status") != "PREFLIGHT_PASS" or state.get("kind") != KIND
            or protocol.get("kind") != KIND or protocol.get("scope") != "model-smoke"
            or state.get("protocol_sha256") != file_sha256(output / "PROTOCOL.json")):
        raise RuntimeError("Only an owned, unchanged PREFLIGHT_PASS limited smoke can execute")
    report = protocol["preflight"]
    if (report.get("scope") != "model-smoke" or report.get("status") != "PREFLIGHT_PASS"
            or report.get("blockers") or report.get("memory", {}).get("fit_vectors") != 37632
            or protocol.get("full_pilot_approved") is not False):
        raise RuntimeError("Full-pilot, incomplete or changed smoke contract is forbidden")
    expected = protocol.get("wrapper_code_sha256", {})
    if set(expected) != set(CODE) or any(file_sha256(root / n) != digest for n, digest in expected.items()):
        raise ValueError("Profiler/binding executable source changed after preflight")
    references = protocol.get("input_reference_sha256", {})
    if not references or any(file_sha256(runner.safe_source(root, n)) != digest for n, digest in references.items()):
        raise ValueError("Frozen input/reference metadata changed after preflight")
    code = report.get("code_sha256", {})
    if not code or any(file_sha256(runner.safe_source(root, n)) != digest for n, digest in code.items()):
        raise ValueError("Original smoke executable source changed after preflight")
    if file_sha256(root / runner.PROTOCOL) != report.get("protocol_sha256"):
        raise ValueError("Scientific protocol changed after preflight")
    checkpoints = report.get("checkpoints", {})
    if set(checkpoints) != {"backbone", "swinir"} or any(
            not item.get("path") or not item.get("sha256")
            or file_sha256(item["path"]) != item["sha256"] for item in checkpoints.values()):
        raise ValueError("Checkpoint changed after preflight; no CUDA/model setup permitted")
    if file_sha256(runner.safe_source(report["data_root"], "split_csv/1cls.csv")) != report["official_csv_sha256"]:
        raise ValueError("Official split CSV changed after preflight")
    if (output / "raw").exists() or (output / "resources.json").exists() or (output / "stage_times.csv").exists():
        raise FileExistsError("Existing payload/resource output is never overwritten")
    return state, protocol


def execute(output, root, *, factory=None, loader=None):
    """Only the old model-smoke executes; injection is for CPU fixtures, not full execution."""
    output, root = Path(output), Path(root)
    state, protocol = _validate(output, root)
    report = protocol["preflight"]
    recorder = None
    monitor = _OutputMonitor(output)
    started = False
    resource = {"kind": KIND, "input_kind": "injected_fixture_NOT_real_model_evidence" if factory is not None or loader is not None
                else "existing_limited_raw_model_smoke", "full_bank_validated": False,
                "full_pilot_approved": False, "metrics": None, "process_id": os.getpid(), "gt_callback_used": False,
                "timing_semantics": "wrapped calls are disjoint; outer execution includes calls, IO and assembly; do not add outer and child times",
                "peak_semantics": "sampled RSS differs from OS process-lifetime high-water; neither is a general upper bound; CUDA counters exclude CPU FAISS and non-PyTorch GPU allocations",
                "warmup_policy": "no extra warmup/model calls; existing first-call overhead is included",
                "scope": {"expected_smoke_vectors": 37632, "full_bank_capacity_not_validated": DEFAULT_CAPACITY}}
    resource["free_disk_bytes_at_start"] = shutil.disk_usage(output).free
    state.update(status="MEASURING", model_execution_started=False)
    memory.write_json(output / "status.json", state)
    inputs = None
    start = time.perf_counter()
    try:
        if loader is None:
            from .pcb_input_binding import FrozenPCBInputs
            inputs = FrozenPCBInputs(root, report["data_root"])
            loader = inputs.rgb  # No GT callback is passed to the model-smoke path.
        monitor.start()
        started = True
        sync, cuda_snapshot = _cuda_tools(report["execution"]["actual_device"])
        recorder = Recorder(sync, cuda_snapshot=cuda_snapshot)
        resource["cuda_at_start"] = cuda_snapshot()
        actual_factory = runner.create_models if factory is None else factory

        def measured_factory(*args):
            state.update(factory_call_started=True, model_execution_started=factory is None)
            memory.write_json(output / "status.json", state)
            adapter, transform = recorder.call("model_factory", actual_factory, *args)
            def transformed(tile, variant):
                stage = "restoration_swinir_x4" if variant == "swinir_x4" else f"preparation_{variant}"
                return recorder.call(stage, transform, tile, variant)
            return _MeasuredAdapter(adapter, recorder), transformed

        raw = runner.execute_smoke(report, root, report["data_root"], output / "raw",
                                   factory=measured_factory, loader=loader)
        sync()
        resource.update(cuda_at_end=cuda_snapshot(), raw_status=raw["status"],
                        observed_feature_counts=raw.get("feature_counts"),
                        raw_status_sha256=file_sha256(output / "raw/status.json"))
        if raw["status"] != "COMPLETE":
            raise RuntimeError("Underlying limited model-smoke did not complete")
        if factory is None and (raw.get("feature_counts", {}).get("observed_vectors") != 37632
                                or raw.get("feature_counts", {}).get("stored_vectors") != 37632):
            raise ValueError("Actual limited smoke bank differs from frozen 37,632-vector scope")
        if inputs is not None:
            inputs.verify_references()
        state["status"] = "MODEL_SMOKE_RESOURCE_COMPLETE_NOT_FULL_APPROVAL"
    except BaseException as error:
        state.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        resource.update(perf_counter_start=start, perf_counter_end=time.perf_counter())
        resource["outer_elapsed_seconds"] = resource["perf_counter_end"] - start
        if inputs is not None:
            resource["rgb_receipts"] = inputs.rgb_receipts
            resource["gt_callback_used"] = False
        if started:
            try:
                resource["process_memory"] = monitor.finish()
            except BaseException as error:
                resource["process_memory"] = monitor.values
                state.update(status="FAILED", error=f"Resource monitor: {type(error).__name__}: {error}")
        resource["phase_summary"] = recorder.summary() if recorder is not None else {}
        if "process_memory" in resource:
            resource["process_memory"].pop("sampled_workspace_disk_max_bytes", None)
        resource["completed"] = state["status"] == "MODEL_SMOKE_RESOURCE_COMPLETE_NOT_FULL_APPROVAL"
        resource["output_payload_bytes_before_resource_files"] = memory.disk_bytes(output)
        resource["free_disk_bytes_at_end"] = shutil.disk_usage(output).free
        runner.write_json(output / "resources.json", resource)
        with (output / "stage_times.csv").open("x", newline="", encoding="utf-8") as handle:
            fields = ("stage", "perf_counter_start", "perf_counter_end", "elapsed_seconds", "completed",
                "rss_before_bytes", "rss_after_bytes", "os_lifetime_peak_rss_after_bytes",
                "cuda_allocated_bytes", "cuda_reserved_bytes", "cuda_max_allocated_bytes_since_profiler_start",
                "cuda_max_reserved_bytes_since_profiler_start")
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(recorder.rows if recorder is not None else [])
        state.update(resources_sha256=file_sha256(output / "resources.json"),
                     timings_sha256=file_sha256(output / "stage_times.csv"))
        memory.write_json(output / "status.json", state)
    if state["status"] != "MODEL_SMOKE_RESOURCE_COMPLETE_NOT_FULL_APPROVAL":
        raise RuntimeError(state.get("error", "Incomplete resource evidence"))
    return state
