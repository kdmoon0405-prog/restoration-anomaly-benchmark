"""Small fake-model streaming/process integration; no real-data execution interface."""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter
import weakref

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from scripts.check_pcb_board_pipeline import FakeAdapter, fixture
from sr_anomaly import pcb_board_analysis as board
from sr_anomaly import pcb_full_producer as producer
from sr_anomaly import pcb_native_memory as memory
from sr_anomaly.bounded_bank import _status, file_sha256
from sr_anomaly.dataset import safe_component
from sr_anomaly.pcb_tiled_models import VARIANTS
from sr_anomaly.pcb_tiled_runner import GEOMETRY, load_inventory, write_json

KIND = "synthetic_producer_process_integration_not_full_pilot"
SEQUENCE = (("produce", None), ("calibration", None), ("normalize", None), ("quality", None)) + tuple(
    ("evaluate", v) for v in VARIANTS)
CODE = ("scripts/check_pcb_full_producer.py", "src/sr_anomaly/pcb_full_producer.py",
        "scripts/check_pcb_board_pipeline.py", *memory.CODE[1:])
RAM_CAP = 1024**3  # Small fake fixture only; never a native execution override.


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fake_produce(output, protocol):
    parents, rgb, transform, _ = fixture()
    refs, counts = [], {"factory": 0, "bind_bank": 0, "transform": {v: 0 for v in VARIANTS}}
    class Adapter(FakeAdapter):
        def bind_bank(self, bank):
            counts["bind_bank"] += 1
            super().bind_bank(bank)
            refs.append(weakref.ref(self.model.anomaly_scorer.detection_features))
    def factory():
        counts["factory"] += 1
        adapter = Adapter()
        refs.extend((weakref.ref(adapter), weakref.ref(adapter.model),
                     weakref.ref(adapter.model.anomaly_scorer.nn_method.search_index)))
        def apply(tile, variant):
            counts["transform"][variant] += 1
            return transform(tile, variant)
        return adapter, apply
    result = producer.produce(parents, rgb, factory, output / "raw",
        provenance={"input_kind": "synthetic", "fixture": "generated-board-lifecycle-v0.6",
                    "source_commit": protocol["source_commit"], "code_sha256": protocol["code_sha256"]},
        patch_shape=(2, 2), dimension=4, capacity=7)
    gc.collect()
    released = all(ref() is None for ref in refs)
    if not released or counts["factory"] != 1 or counts["bind_bank"] != 1 or counts["transform"] != result["transform_calls"]:
        raise AssertionError("Fake factory/bank/RGB reuse/reference lifetime mismatch")
    return {"owned_fake_model_index_features_released": released, "call_counts": counts}


def worker(root, output, stage, variant=None):
    root, output = Path(root), Path(output)
    state = _read(output / "status.json")
    protocol = _read(output / "PROTOCOL.json")
    if (state.get("status") != "BUILDING" or state.get("kind") != KIND
            or state.get("active_stage") != [stage, variant]
            or state.get("protocol_sha256") != file_sha256(output / "PROTOCOL.json")
            or protocol.get("input_kind") != "synthetic"
            or (stage, variant) not in SEQUENCE):
        raise ValueError("Unowned/incomplete/wrong synthetic worker request")
    for name, digest in protocol["code_sha256"].items():
        if file_sha256(root / name) != digest:
            raise ValueError("Worker executable source changed")
    start = perf_counter()
    parents = fixture()[0]  # Descriptors only; no GT callback outside evaluation.
    if stage == "produce":
        result = _fake_produce(output, protocol)
    elif stage == "calibration":
        board.fit_calibration(output / "raw", output / "calibration", ram_budget=RAM_CAP)
        result = {"calibration": "COMPLETE_SYNTHETIC_ONLY"}
    elif stage == "normalize":
        board.apply_calibration(output / "raw", output / "calibration", output / "normalized", ram_budget=RAM_CAP)
        result = {"normalization": "COMPLETE_SYNTHETIC_ONLY"}
    elif stage == "quality":
        spool = producer.RGBSpool(output / "raw")
        board.quality_report(parents, spool.reference, spool.tiles, output / "quality",
            provenance={"input_kind": "synthetic", "raw_status_sha256": file_sha256(output / "raw/status.json"),
                        "rgb_source": "lossless_already_produced_tiles_no_second_transform"}, ram_budget=RAM_CAP)
        result = {"quality": "COMPLETE_SYNTHETIC_ONLY", "transform_calls_this_stage": 0}
    else:
        # Only evaluation selects/invokes the generated GT callback.
        gt = fixture()[3]
        board.evaluate_variant(output / "raw", output / "calibration", output / "normalized",
                               variant, gt, output / "evaluation" / variant, ram_budget=RAM_CAP)
        result = {"evaluation": "COMPLETE_SYNTHETIC_ONLY", "variant": variant}
    if any(n in sys.modules for n in ("torch", "faiss", "patchcore")):
        raise RuntimeError("Unexpected model runtime imported by fake worker")
    result.update(stage=stage, variant=variant, pid=os.getpid(), elapsed_seconds=perf_counter() - start,
                  process_memory=memory.process_memory(), model_runtime_imports=[],
                  scope="GENERATED_SYNTHETIC_ONLY_NOT_RESEARCH_RESULTS")
    write_json(output / "stages" / f"{stage}-{variant or 'all'}.json", result)
    return result


def _validate_outputs(output, state):
    if (state.get("protocol_sha256") != file_sha256(output / "PROTOCOL.json")
            or len(state.get("workers", [])) != len(SEQUENCE)):
        raise ValueError("Incomplete source/worker records")
    for record, (stage, variant) in zip(state["workers"], SEQUENCE, strict=True):
        expected = f"stages/{stage}-{variant or 'all'}.json"
        log = f"logs/{stage}-{variant or 'all'}.txt"
        if (record["file"] != expected or record["log"] != log or record["returncode"] != 0
                or file_sha256(output / expected) != record["sha256"]
                or file_sha256(output / log) != record["log_sha256"]):
            raise ValueError("Worker record/log checksum or sequence mismatch")
    source, _ = board.load_raw_run(output / "raw")
    board.load_calibration(output / "calibration", output / "raw")
    normalized = board.load_normalized(output / "normalized", output / "raw", output / "calibration")
    for row in normalized["rows"]:
        board._map(output / "normalized", row, dtype=np.float64)
    for row in source["rows"]:
        board._map(output / "raw", row)
    expected = {"raw/status.json", "calibration/status.json", "normalized/status.json", "quality/status.json"}
    expected.update(f"evaluation/{v}/status.json" for v in VARIANTS)
    if set(state["artifact_status_sha256"]) != expected:
        raise ValueError("Incomplete artifact status inventory")
    for name, digest in state["artifact_status_sha256"].items():
        if file_sha256(output / name) != digest:
            raise ValueError("Completed artifact status checksum mismatch")


def load_completed(output):
    output = Path(output)
    state = _read(output / "status.json")
    if (state.get("kind") != KIND or state.get("status") != "SYNTHETIC_INTEGRATION_PASS_NOT_FULL_APPROVAL"
            or not state.get("rgb_spool_removed") or state.get("full_pilot_approved") is not False):
        raise ValueError("Incomplete/wrong synthetic integration artifact")
    if (output / "raw/rgb").exists():
        raise ValueError("Successful RGB workspace cleanup not complete")
    _validate_outputs(output, state)
    return state


def run(root, run_id, *, timeout=120):
    root = Path(root).resolve()
    run_id = safe_component(run_id, "run ID")
    output = root / "outputs/pcb-full-producer" / run_id
    if output.exists():
        raise FileExistsError("Existing output is never overwritten")
    parents = fixture()[0]
    native, _, _ = load_inventory(root / GEOMETRY)
    native_plan = producer.resource_plan(native)
    region = _read(root / GEOMETRY / "resource_estimate.json")["aupro_retained_region_bool_masks_bytes"]
    native_plan["postprocessing"] = board.memory_plan(native, region_mask_bytes=region)
    synthetic_plan = producer.resource_plan(parents, patch_shape=(2, 2), dimension=4, capacity=7)
    board._budget(max(synthetic_plan["producer_prediction_visible_bytes"],
                      synthetic_plan["postprocessing"]["quality_planning_envelope_bytes"]), RAM_CAP)
    protocol = {"input_kind": "synthetic", "kind": KIND, "real_execution": False,
                "code_sha256": {n: file_sha256(root / n) for n in dict.fromkeys(CODE)},
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                "source_worktree_dirty": bool(subprocess.check_output(
                    ["git", "status", "--porcelain", "--ignore-submodules=all"], cwd=root, text=True).strip()),
                "synthetic_plan": synthetic_plan, "native_metadata_only_plan": native_plan,
                "native_allocations_or_GT_reads": False, "native_memory_validation": "PENDING_TEAMMATE_REPORT",
                "actual_model_peak": "UNMEASURED", "full_pilot": "BLOCKED"}
    state = {"kind": KIND, "workers": [], "active_stage": None, "full_pilot_approved": False,
             "actual_pcb_bank": "NOT_CREATED", "actual_pcb_calibration": "NOT_CREATED"}
    output = board._new_output(output, state, disk_bytes=synthetic_plan["disk_payload_before_cleanup_bytes"])
    write_json(output / "PROTOCOL.json", protocol)
    state["protocol_sha256"] = file_sha256(output / "PROTOCOL.json")
    (output / "stages").mkdir()
    (output / "logs").mkdir()
    try:
        for stage, variant in SEQUENCE:
            state["active_stage"] = [stage, variant]
            _status(output, state)
            command = [sys.executable, str(root / "scripts/check_pcb_full_producer.py"),
                       "--worker", stage, "--payload", str(output)]
            if variant:
                command += ["--variant", variant]
            start = perf_counter()
            log = f"logs/{stage}-{variant or 'all'}.txt"
            try:
                child = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
            except subprocess.TimeoutExpired as error:
                # subprocess.run kills and waits only its owned child on timeout.
                (output / log).write_text(str(error), encoding="utf-8")
                raise
            (output / log).write_text(child.stdout + child.stderr, encoding="utf-8")
            if child.returncode:
                raise RuntimeError(f"Worker failed: {stage}/{variant}: {child.stderr[-1500:]}")
            name = f"stages/{stage}-{variant or 'all'}.json"
            result = _read(output / name)
            if result["stage"] != stage or result["variant"] != variant or result["model_runtime_imports"]:
                raise ValueError("Worker completion metadata mismatch")
            state["workers"].append({"file": name, "sha256": file_sha256(output / name),
                "log": log, "log_sha256": file_sha256(output / log), "returncode": child.returncode,
                "pid": result["pid"], "launch_to_exit_seconds": perf_counter() - start})
        # Keep RGB on ANY failure. Remove only this owned, consumed workspace after all exits.
        raw = output / "raw"
        spool = raw / "rgb"
        if spool.is_symlink() or spool.resolve() != raw.resolve() / "rgb":
            raise ValueError("Unexpected RGB workspace cleanup target")
        statuses = ["raw/status.json", "calibration/status.json", "normalized/status.json", "quality/status.json"]
        statuses += [f"evaluation/{v}/status.json" for v in VARIANTS]
        if any(_read(output / n).get("status") != "COMPLETE" for n in statuses):
            raise ValueError("Incomplete downstream artifact; preserve RGB workspace")
        state["artifact_status_sha256"] = {n: file_sha256(output / n) for n in statuses}
        _validate_outputs(output, state)
        state["rgb_spool_bytes_before_cleanup"] = memory.disk_bytes(spool)
        shutil.rmtree(spool)
        state.update(status="SYNTHETIC_INTEGRATION_PASS_NOT_FULL_APPROVAL", active_stage=None,
                     all_workers_exited_before_next_stage=True, rgb_spool_removed=True)
        _status(output, state)
        return load_completed(output), output
    except BaseException as error:
        board._fail(output, state, error)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--worker", choices=("produce", "calibration", "normalize", "quality", "evaluate"), help=argparse.SUPPRESS)
    parser.add_argument("--payload", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--variant", choices=VARIANTS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        if args.payload is None:
            parser.error("Owned synthetic worker payload required")
        worker(ROOT, args.payload, args.worker, args.variant)
    else:
        if args.run_id is None:
            parser.error("--run-id required")
        result, output = run(ROOT, args.run_id)
        print(json.dumps({"status": result["status"], "output": str(output), "full_pilot_approved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
