"""Real 180/200 cohort raw producer: reviewed bank byte-copy, unit receipts, verified resume.

No refit, no GT, no calibration here. The finished artifact is the existing v0.6
`load_raw_run` contract (scope full-pilot-raw, raw/bank copy, bank provenance), so the
existing calibration/normalization/quality/evaluation code consumes it unchanged.
"""
from __future__ import annotations

import csv
from dataclasses import asdict
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time

import numpy as np

from . import bounded_bank as bank
from . import pcb_fit_bank as fit
from . import pcb_reuse_inference as reuse
from . import pcb_tiling as geometry
from .tiled_cpu_pipeline import TilePrediction, assemble_board, Parent

KIND = "pcb_full_cohort_raw_real_bank_reuse"
SCOPE = "full-pilot-raw"  # Required by existing load_raw_run for real inputs.
COMPLETE = "COMPLETE"  # Existing reader requires exactly this.
RESUMABLE = "INCOMPLETE_RESUMABLE"
EXECUTION_FAMILY = "faiss_cpu_IndexFlatL2_4threads_k1_one_tile_per_search_v1"
BANK_COPY = ("status.json", "bank.npy", "selected_indices.npy")
CODE = reuse.CODE + ("src/sr_anomaly/pcb_full_cohort.py", "scripts/run_pcb_full_cohort.py")
OUTPUT_BASE = "outputs/pcb-full-cohort"
STOP_FILE = "STOP_REQUESTED"


def _sources(root):
    return fit._sources(root) | {n: bank.file_sha256(root/n) for n in CODE}


def units(parents):
    """Fixed order: frozen parent order x VARIANTS; row index == predictions/{i:04d}.npy."""
    query = [p for p in parents if p.split != "fit"]
    return [(i, p, v) for i, (p, v) in enumerate((p, v) for p in query for v in fit.models.VARIANTS)]


def _test_index(parents):
    return {p.sample: j for j, p in enumerate(p for p in parents if p.split == "test")}


def _runtime():
    import torch
    return dict(torch_version=torch.__version__, cuda_runtime=torch.version.cuda,
                gpu_name=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)


def _context(root, bank_run, data_root, backbone, swinir, output):
    inputs = fit.binding.FrozenPCBInputs(root, data_root)
    parents = tuple(inputs.parents)
    if parents != fit.runner.load_inventory(root/fit.runner.GEOMETRY)[0]:
        raise ValueError("Full cohort requires exact frozen 721/180/200 inventory")
    query = [p for p in parents if p.split != "fit"]
    plan = reuse.resource_plan(query)
    plan["required_free_disk_bytes"] += sum((Path(bank_run)/"bank"/n).stat().st_size for n in BANK_COPY)
    reuse._guard(plan, output)
    admission = reuse.admit_bank(root, bank_run, inputs)
    checkpoints = fit._checkpoints(backbone, swinir)
    hashes = {p.sample: bank.file_sha256(fit.runner.safe_source(data_root, p.sample)) for p in query}
    if any(hashes[p.sample] != inputs._row(p)["image_sha256"] for p in query):
        raise ValueError("Cohort source RGB checksum changed")
    return inputs, dict(kind=KIND, scope=SCOPE, spec=reuse.SPEC.copy(), execution_family=EXECUTION_FAMILY,
        bank_admission=admission, bank_run_recorded_location=str(bank_run), data_root_recorded_location=str(data_root),
        parents=[asdict(p) for p in parents], counts=reuse.counts(query), units=len(units(parents)),
        input_file_sha256=hashes, geometry_id=inputs.geometry_id, code_sha256=_sources(root),
        references_sha256=fit._references(root), checkpoints=checkpoints, plan=plan, runtime=_runtime(),
        python_version=sys.version, numpy_version=np.__version__, gt_callback_used=False,
        calibration=None, thresholds=None, metrics=None)


def _volatile(protocol):
    # Commit/dirty are recorded per session; identity is the content hashes above.
    return {k: v for k, v in protocol.items() if k not in ("source_commit", "source_worktree_dirty", "blockers")}


def _copy_bank(bank_run, output):
    """Byte-copy reviewed bank so raw/bank satisfies the existing reader. Source opened read-only."""
    target = output/"bank"
    target.mkdir()
    for name in BANK_COPY:
        with (bank_run/"bank"/name).open("rb") as src, (target/(name+".partial")).open("xb") as dst:
            shutil.copyfileobj(src, dst, 16*1024**2)
            dst.flush(); os.fsync(dst.fileno())
        os.replace(target/(name+".partial"), target/name)
    copied = {n: bank.file_sha256(target/n) for n in BANK_COPY}
    if copied != {n: bank.file_sha256(bank_run/"bank"/n) for n in BANK_COPY} or copied["bank.npy"] != reuse.BANK_SHA256:
        raise ValueError("Bank byte-copy differs from reviewed source")
    return copied


def prepare(root, bank_run, data_root, backbone, swinir, *, run_id):
    root, bank_run, data_root = (Path(p).resolve() for p in (root, bank_run, data_root))
    output = (root/OUTPUT_BASE/fit.safe_component(run_id, "run-id")).resolve()
    if any(output.is_relative_to(s) or s.is_relative_to(output) for s in (bank_run, data_root)):
        raise ValueError("Bank/input/output trees must be disjoint")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    state = dict(kind=KIND, scope=SCOPE, status="PREPARING", bank_created_this_run=False, gt_callback_used=False,
                 full_cohort_inference_complete=False, calibration=None, thresholds=None, metrics=None)
    fit.memory.write_json(output/"status.json", state)
    try:
        _, protocol = _context(root, bank_run, data_root, backbone, swinir, output)
        protocol.update(source_commit=fit._git(root, "rev-parse", "HEAD"),
                        source_worktree_dirty=bool(fit._git(root, "status", "--porcelain")),
                        bank_copy_sha256=_copy_bank(bank_run, output))
        fit.runner.write_json(output/"PROTOCOL.json", protocol)
        state.update(status="PREFLIGHT_PASS", protocol_sha256=bank.file_sha256(output/"PROTOCOL.json"), sessions=[])
    except BaseException as error:
        state.update(status="BLOCKED_MEMORY" if isinstance(error, MemoryError) else "FAILED_PREFLIGHT",
                     error=f"{type(error).__name__}: {error}")
        fit.memory.write_json(output/"status.json", state)
        raise
    fit.memory.write_json(output/"status.json", state)
    return output, state


def _save_atomic(directory, name, values):
    path = fit.runner.safe_source(directory, name)
    partial = path.with_name(path.name+".partial")
    with partial.open("xb") as stream:
        np.save(stream, values, allow_pickle=False)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(partial, path)
    return {"file": name, "sha256": bank.file_sha256(path), "shape": list(values.shape), "dtype": str(values.dtype)}


def _unit_files(index, parent, variant, tests):
    files = [f"predictions/{index:04d}.npy"]
    if parent.split == "test":
        j = tests[parent.sample]
        files.append(f"rgb/tiles-{3*j+fit.models.VARIANTS.index(variant):04d}.npy")
        if variant == "clean":
            files.append(f"rgb/reference-{j:04d}.npy")
    return files


def _receipt_path(output, index):
    return output/"units"/f"{index:04d}.json"


def verify_unit(output, index, parent, variant, tests, protocol_sha):
    """True only for a receipt bound to this protocol whose payload bytes still match."""
    path = _receipt_path(output, index)
    if not path.is_file():
        return None
    receipt = fit.memory.read_json(path)
    files = _unit_files(index, parent, variant, tests)
    if (receipt.get("protocol_sha256") != protocol_sha or receipt.get("sample") != parent.sample
            or receipt.get("variant") != variant or receipt.get("index") != index
            or sorted(receipt["files"]) != sorted(files)):
        raise ValueError(f"Unit receipt {index} identity differs; refuse resume")
    for name, row in receipt["files"].items():
        if bank.file_sha256(fit.runner.safe_source(output, name)) != row["sha256"]:
            raise ValueError(f"Unit {index} payload changed after receipt; refuse resume")
    return receipt


def _discard_unreceipted(output, index, parent, variant, tests):
    removed = []
    for name in _unit_files(index, parent, variant, tests):
        for path in (output/name, output/(name+".partial")):
            if path.exists():
                path.unlink(); removed.append(path.relative_to(output).as_posix())
    return removed


class _Lock:
    def __init__(self, output):
        self.path = output/"RUN.lock"

    def __enter__(self):
        if self.path.exists():
            pid = int(self.path.read_text().strip() or 0)
            if pid and _alive(pid):
                raise RuntimeError(f"Run is locked by live process {pid}")
            self.stale = pid
            self.path.unlink()
        else:
            self.stale = None
        with self.path.open("x") as handle:
            handle.write(str(os.getpid()))
        return self

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def _alive(pid):
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _validate(output, root, bank_run, data_root):
    if output.parent != (root/OUTPUT_BASE).resolve():
        raise ValueError("Only an owned full-cohort run directory may execute")
    state, protocol = reuse._read(output, "status.json"), reuse._read(output, "PROTOCOL.json")
    if (state.get("kind") != KIND or state.get("status") not in ("PREFLIGHT_PASS", "RUNNING", RESUMABLE)
            or state.get("protocol_sha256") != bank.file_sha256(output/"PROTOCOL.json")
            or protocol.get("scope") != SCOPE or protocol.get("spec") != reuse.SPEC or protocol.get("blockers")
            or state.get("gt_callback_used") is not False):
        raise ValueError("Not a resumable full-cohort run of this exact protocol (COMPLETE/foreign never rerun)")
    checks = protocol["checkpoints"]
    inputs, current = _context(root, bank_run, data_root, checks["backbone"]["path"], checks["swinir"]["path"], output)
    if reuse._canonical(_volatile(current)) != reuse._canonical({k: v for k, v in _volatile(protocol).items()
                                                                  if k != "bank_copy_sha256"}):
        raise ValueError("Code/input/bank/checkpoint/config/runtime differs from protocol; resume refused")
    if {n: bank.file_sha256(output/"bank"/n) for n in BANK_COPY} != protocol["bank_copy_sha256"]:
        raise ValueError("Bank copy changed")
    return state, protocol, inputs


def execute(output, root, bank_run, data_root, *, factory=None, max_units=None, note=""):
    """Run/resume missing units. Completed receipts are verified and skipped, never rewritten."""
    output, root, bank_run, data_root = (Path(p).resolve() for p in (output, root, bank_run, data_root))
    fixture = factory is not None
    if fixture and reuse.SPEC["total_vectors"]*reuse.SPEC["dimension"] > 4096:
        raise ValueError("Injected execution requires a tiny bank fixture")
    with _Lock(output) as lock:
        state, protocol, inputs = _validate(output, root, bank_run, data_root)
        protocol_sha = state["protocol_sha256"]
        parents = tuple(Parent(x["sample"], x["split"], x["label"], tuple(x["size_wh"])) for x in protocol["parents"])
        tests = _test_index(parents)
        plan = units(parents)
        for d in ("units", "predictions", "rgb", "sessions"):
            (output/d).mkdir(exist_ok=True)
        session = len(state.get("sessions", []))
        meta = dict(session=session, pid=os.getpid(), note=note, stale_lock_pid=lock.stale,
            source_commit=fit._git(root, "rev-parse", "HEAD"), source_worktree_dirty=bool(fit._git(root, "status", "--porcelain")),
            start_time=time.strftime("%Y-%m-%dT%H:%M:%S"), fixture_injected=fixture, skipped_verified_units=0,
            discarded_unreceipted=[], completed_units=[], predict_calls=0, transform_calls={v: 0 for v in fit.models.VARIANTS},
            bind_calls=0, stage_aggregate={})
        todo = []
        t_verify = time.perf_counter()
        for index, parent, variant in plan:
            if verify_unit(output, index, parent, variant, tests, protocol_sha) is not None:
                meta["skipped_verified_units"] += 1
            else:
                meta["discarded_unreceipted"] += _discard_unreceipted(output, index, parent, variant, tests)
                todo.append((index, parent, variant))
        meta["receipt_verification_seconds"] = time.perf_counter()-t_verify
        if max_units is not None:
            todo = todo[:max_units]
        state.update(status="RUNNING", active_session=session)
        fit.memory.write_json(output/"status.json", state)
        adapter = transform = values = indices = recorder = None
        monitor, started, failure, stopped = fit.measured._OutputMonitor(output), False, None, False
        start = time.perf_counter()
        stage_csv = output/"sessions"/f"{session:03d}-stage_times.csv"
        writer_handle = writer = None
        try:
            if todo:
                reuse._guard(protocol["plan"], output)
                sync, snapshot, device = ((lambda: None), (lambda: None), dict(actual_device="cpu", cuda_available=False)) \
                    if fixture else fit._cuda()
                meta.update(device)
                recorder = fit.measured.Recorder(sync, cuda_snapshot=snapshot)
                monitor.start(); started = True
                checks = protocol["checkpoints"]
                adapter, transform = recorder.call("model_factory", factory or fit.models.create_models, root,
                    "cpu" if fixture else "cuda", checks["backbone"]["path"], checks["swinir"]["path"])
                values, indices, _ = recorder.call("load_complete_bank_mmap_verify", bank.load_complete_bank, output/"bank")
                recorder.call("bind_existing_bank_CPU_exact_index", adapter.bind_bank, values)
                meta["bind_calls"] = 1
                writer_handle = stage_csv.open("x", encoding="utf-8", newline="")
                current_parent = rgb = None
                for index, parent, variant in todo:
                    if (output/STOP_FILE).exists():
                        stopped = True
                        break
                    if parent is not current_parent:
                        rgb = recorder.call("source_rgb_decode_verify", inputs.rgb, parent)
                        current_parent = parent
                    receipt = _run_unit(output, recorder, adapter, transform, index, parent, variant, rgb, tests, meta, snapshot)
                    receipt.update(protocol_sha256=protocol_sha, session=session)
                    fit.memory.write_json(_receipt_path(output, index), receipt)  # Written last: unit is complete.
                    meta["completed_units"].append(index)
                    rows, recorder.rows = recorder.rows, []
                    if writer is None and rows:
                        writer = csv.DictWriter(writer_handle, fieldnames=["unit", *rows[0]])
                        writer.writeheader()
                    for row in rows:
                        writer.writerow({"unit": index, **row})
                        agg = meta["stage_aggregate"].setdefault(row["stage"], dict(calls=0, sum_elapsed_seconds=0., max_elapsed_seconds=0.))
                        agg["calls"] += 1; agg["sum_elapsed_seconds"] += row["elapsed_seconds"]
                        agg["max_elapsed_seconds"] = max(agg["max_elapsed_seconds"], row["elapsed_seconds"])
                    writer_handle.flush()
                rgb = None
            after = (reuse._hashes(bank_run), _sources(root), {n: bank.file_sha256(output/"bank"/n) for n in BANK_COPY})
            if after != (protocol["bank_admission"]["file_sha256"], protocol["code_sha256"], protocol["bank_copy_sha256"]):
                raise ValueError("Bank/source/bank-copy changed during inference")
            inputs.verify_references()
        except BaseException as error:
            failure = error
            meta["error"] = f"{type(error).__name__}: {error}"
        finally:
            try:
                if adapter is not None:
                    (recorder.call("adapter_close", adapter.close) if recorder else adapter.close())
            except BaseException as error:
                failure = failure or error; meta["cleanup_error"] = str(error)
            adapter = transform = None
            for value in (values, indices):
                if value is not None:
                    value._mmap.close()
            values = indices = value = None
            gc.collect()
            if writer_handle is not None:
                if recorder is not None and recorder.rows and writer is not None:
                    writer.writerows({"unit": None, **r} for r in recorder.rows)
                writer_handle.close()
            try:
                if started:
                    meta["process_memory"] = monitor.finish()
                    meta["process_memory"].pop("sampled_workspace_disk_max_bytes", None)
            except BaseException as error:
                failure = failure or error; meta["resource_error"] = str(error)
            meta.update(end_time=time.strftime("%Y-%m-%dT%H:%M:%S"), outer_elapsed_seconds=time.perf_counter()-start,
                        stopped_by_request=stopped, stage_times_file=stage_csv.name if stage_csv.exists() else None)
            name = f"sessions/{session:03d}.json"
            fit.memory.write_json(output/name, meta)
            state.setdefault("sessions", []).append(dict(file=name, sha256=bank.file_sha256(output/name)))
            state.pop("active_session", None)
            done = sum(_receipt_path(output, i).is_file() for i, _, _ in plan)
            state.update(units_complete=done, units_total=len(plan))
            if failure is None and done == len(plan):
                try:
                    _finalize(output, protocol, parents, plan, tests, state, fixture)
                except BaseException as error:
                    failure = error; state.update(status=RESUMABLE, error=f"finalize: {error}")
            elif failure is None:
                state.update(status=RESUMABLE, error=None)
            else:
                state.update(status="BLOCKED_MEMORY" if isinstance(failure, MemoryError) else RESUMABLE, error=meta["error"])
            fit.memory.write_json(output/"status.json", state)
    if failure is not None:
        raise failure
    return state


def _run_unit(output, recorder, adapter, transform, index, parent, variant, rgb, tests, meta, snapshot):
    boxes = geometry.tile_boxes(parent.size_wh)
    files, spool_name = {}, None
    first = len(recorder.rows)
    if parent.split == "test" and variant == "clean":
        name = _unit_files(index, parent, variant, tests)[2]
        files[name] = recorder.call("reference_rgb_save_hash", _save_atomic, output, name, rgb)
    if parent.split == "test":
        spool_name = _unit_files(index, parent, variant, tests)[1]

    def stream():
        spool = None
        partial = output/(spool_name+".partial") if spool_name else None
        try:
            if spool_name:
                spool = np.lib.format.open_memmap(partial, mode="w+", dtype=np.uint8, shape=(len(boxes), 224, 224, 3))
            for tile_id, (tile, box) in enumerate(zip(geometry.extract_tiles(rgb, boxes), boxes, strict=True)):
                original = tile.copy()
                prepared = np.array(recorder.call("prepare_"+variant, transform, tile, variant), copy=True)
                fit.models.check_rgb(prepared)
                if not np.array_equal(tile, original) or (variant == "clean" and not np.array_equal(prepared, original)):
                    raise ValueError("Transform mutated input or changed clean RGB")
                before = prepared.copy()
                if spool is not None:
                    spool[tile_id] = prepared  # Same prepared RGB that is predicted.
                anomaly_map, score = recorder.call("detector_inference_including_CPU_FAISS", adapter.predict, prepared)
                if not np.array_equal(prepared, before):
                    raise ValueError("Predictor mutated produced RGB")
                meta["predict_calls"] += 1; meta["transform_calls"][variant] += 1
                yield TilePrediction(parent.sample, variant, tile_id, box, anomaly_map, score)
            if spool is not None:
                spool.flush(); spool._mmap.close(); spool = None
                os.replace(partial, output/spool_name)
                path = output/spool_name
                files[spool_name] = dict(file=spool_name, sha256=bank.file_sha256(path), shape=[len(boxes), 224, 224, 3],
                                         dtype="uint8", boxes=[list(b) for b in boxes])
        finally:
            if spool is not None:
                spool._mmap.close()

    predictions = stream()
    t0 = time.perf_counter()
    try:
        board = assemble_board(parent.sample, variant, parent.size_wh, predictions)
    finally:
        predictions.close()
    t1 = time.perf_counter()
    map_name = f"predictions/{index:04d}.npy"
    files[map_name] = _save_atomic(output, map_name, board.anomaly_map)
    t2 = time.perf_counter()
    if len(files) != len(_unit_files(index, parent, variant, tests)):
        raise ValueError("Unit payload inventory incomplete")
    ledger = reuse.unit_ledger(recorder, first, t0, t1, t2, snapshot, sample=parent.sample, split=parent.split, variant=variant)
    return dict(index=index, sample=parent.sample, split=parent.split, label=parent.label, variant=variant,
                size_wh=list(parent.size_wh), score=board.score, files=files, ledger=ledger)


def _finalize(output, protocol, parents, plan, tests, state, fixture):
    """Assemble the existing load_raw_run inventory from verified receipts only."""
    rows, refs, rgbs = [], [], {}
    for index, parent, variant in plan:
        r = verify_unit(output, index, parent, variant, tests, state["protocol_sha256"])
        if r is None:
            raise ValueError("Missing unit receipt")
        rows.append(dict(r["files"][f"predictions/{index:04d}.npy"], sample=parent.sample, split=parent.split,
                         label=parent.label, variant=variant, size_wh=list(parent.size_wh), score=r["score"]))
        if parent.split == "test":
            j = tests[parent.sample]
            name = f"rgb/tiles-{3*j+fit.models.VARIANTS.index(variant):04d}.npy"
            rgbs[name] = dict(r["files"][name], sample=parent.sample, variant=variant)
            if variant == "clean":
                ref = f"rgb/reference-{j:04d}.npy"
                refs.append(dict(r["files"][ref], sample=parent.sample))
    rgb_rows = [rgbs[k] for k in sorted(rgbs)]
    test = [p for p in parents if p.split == "test"]
    reuse.check_spool(output, dict(rgb_rows=rgb_rows, reference_rows=refs), test)
    with (output/"units_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index", "sample", "split", "label", "variant", "score", "file", "sha256"])
        writer.writeheader()
        writer.writerows({k: r[k] for k in writer.fieldnames if k != "index"} | {"index": i} for i, r in enumerate(rows))
    bank_status = reuse._read(output/"bank", "status.json")
    state.update(status=COMPLETE, scope=SCOPE, parents=protocol["parents"], provenance=bank_status["provenance"],
        inference_provenance=dict(kind=KIND, execution_family=EXECUTION_FAMILY, protocol_sha256=state["protocol_sha256"],
            source_commit_at_preflight=protocol["source_commit"], fixture_injected=fixture),
        geometry_id=protocol["geometry_id"], rows=rows, reference_rows=refs, rgb_rows=rgb_rows,
        bank_artifact_sha256=protocol["bank_copy_sha256"], bank_unchanged=True, bank_created_this_run=False,
        actual_bank_reused=not fixture, full_cohort_inference_complete=True, gt_callback_used=False,
        units_manifest_sha256=bank.file_sha256(output/"units_manifest.csv"), error=None)


class FullRGBSpool:
    """Read produced test RGB of a COMPLETE full run for existing quality_report; no model."""
    def __init__(self, raw):
        from . import pcb_board_analysis as board
        self.raw = Path(raw)
        self.state, parents = board.load_raw_run(raw)
        if self.state.get("kind") != KIND:
            raise ValueError("Not a full-cohort raw run")
        test = [p for p in parents if p.split == "test"]
        self.parents = {p.sample: p for p in test}
        if ([r["sample"] for r in self.state["reference_rows"]] != [p.sample for p in test]
                or [(r["sample"], r["variant"]) for r in self.state["rgb_rows"]] != [(p.sample, v) for p in test for v in fit.models.VARIANTS]):
            raise ValueError("RGB inventory mismatch")
        self.references = {r["sample"]: r for r in self.state["reference_rows"]}
        self.variants = {(r["sample"], r["variant"]): r for r in self.state["rgb_rows"]}

    def _array(self, row):
        path = fit.runner.safe_source(self.raw, row["file"])
        if bank.file_sha256(path) != row["sha256"]:
            raise ValueError("RGB checksum mismatch")
        values = np.load(path, allow_pickle=False)
        if list(values.shape) != row["shape"] or values.dtype != np.uint8:
            raise ValueError("RGB shape/dtype mismatch")
        return values

    def reference(self, parent):
        if self.parents.get(parent.sample) != parent:
            raise ValueError("RGB requested outside test inventory")
        return self._array(self.references[parent.sample])

    def tiles(self, parent, variant):
        if self.parents.get(parent.sample) != parent or variant not in fit.models.VARIANTS:
            raise ValueError("RGB requested outside test inventory")
        yield from self._array(self.variants[parent.sample, variant])
