"""Read-only full-cap synthetic-probe metadata review, never full-run approval."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import re
import subprocess

from . import pcb_fullcap_probe as probe
from . import pcb_resource_review as limited
from .bounded_bank import file_sha256

_require, _number, _cuda = limited._require, limited._number, limited._cuda
FILES = ("PROTOCOL.json", "status.json", "resources.json", "stage_times.csv")
PASS = "CONSISTENCY_VERIFIED_NOT_FULL_APPROVAL"
REJECT = "REJECTED_NOT_FULL_APPROVAL"


def _json(directory, name):
    path = limited.safe_source(directory, name)
    _require(path.stat().st_size <= 16 * 1024**2, "Metadata file exceeds 16 MiB")
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def finite(token):
        result = float(token)
        _require(math.isfinite(result), "Nonfinite JSON number")
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_float=finite, parse_constant=finite)
    _require(isinstance(value, dict), "Metadata object required")
    return value


def _digest(value):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "Invalid SHA256")
    return value


def _bytes(value):
    number = _number(value)
    _require(number.is_integer(), "Noninteger byte/count measurement")
    return int(number)


def _source_binding(root, protocol):
    expected = probe._bound_sources(root)  # Lazy definitions only; no runtime/model creation.
    _require(protocol["source_sha256"] == expected, "Bound source hash/coverage mismatch")
    commit = protocol["source_commit"]
    _require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit), "Invalid execution source commit")
    actual = subprocess.check_output(["git", "rev-parse", "--verify", commit + "^{commit}"], cwd=root,
                                     text=True, stderr=subprocess.PIPE).strip()
    _require(actual == commit, "Unknown execution source commit")
    # Git compares canonical blobs, while the binding above checks actual Windows bytes.
    diff = subprocess.run(["git", "diff", "--quiet", commit, "--", *sorted(expected)], cwd=root,
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    _require(diff.returncode == 0, "Execution commit differs from reviewed bound source")
    return expected


def _reference(root, directory, protocol, source_names):
    _require(directory is not None, "Explicit --reference-run required; remote JSON paths are never followed")
    directory = Path(directory).resolve()
    hashes = protocol["reference_sha256"]
    _require(set(hashes) == set(probe.REFERENCE_FILES), "Incomplete reference hash coverage")
    for name, digest in hashes.items():
        path = limited.safe_source(directory, name)
        _require(path.stat().st_size <= 16 * 1024**2, "Reference metadata exceeds 16 MiB")
        _require(file_sha256(path) == _digest(digest), "Reference hash mismatch: " + name)
    old = _json(directory, "PROTOCOL.json")
    report = old["preflight"]
    # Reject extra paths before the older checker can open any declared source/reference.
    allowed = set(source_names) | set(limited.ORIGINAL_CODE) | set(probe.measured.CODE)
    _require(set(old["wrapper_code_sha256"]) == set(probe.measured.CODE)
             and set(report["code_sha256"]) <= allowed, "Unsafe reference source coverage")
    runner = probe.measured.runner
    refs = {str(p).replace("\\", "/") for p in (runner.GEOMETRY / "MANIFEST.json",
        runner.GEOMETRY / "PROTOCOL.json", runner.BUDGET / "PROTOCOL.json", runner.BUDGET / "selection_plan.json")}
    _require(set(old["input_reference_sha256"]) == refs, "Unsafe reference metadata paths")
    accepted = limited.validate(directory, root)
    _require(accepted["execution_class"] == "REPORTED_CUDA_LIMITED_SMOKE", "Reference is not reported CUDA limited evidence")
    _require(protocol["plan"] == probe.resource_plan(accepted["os_lifetime_peak_rss_bytes"]), "Resource planning scenario mismatch")
    return accepted, _json(directory, "resources.json")


def _timings(directory, resource):
    path = limited.safe_source(directory, "stage_times.csv")
    _require(path.stat().st_size <= 1024**2, "Timing metadata exceeds 1 MiB")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = ["stage", "perf_counter_start", "perf_counter_end", "elapsed_seconds", "completed",
                  "rss_before_bytes", "rss_after_bytes", "os_lifetime_peak_rss_after_bytes"] + ["cuda_"+k for k in limited.CUDA_FIELDS]
        _require(reader.fieldnames == fields, "Timing CSV schema mismatch")
        rows = list(reader)
    _require(all(set(r) == set(fields) for r in rows), "Malformed CSV row")
    start, end = (_number(resource[k]) for k in ("perf_counter_start", "perf_counter_end"))
    _require(end > start and math.isclose(_number(resource["elapsed_seconds"]), end-start,
             rel_tol=1e-9, abs_tol=1e-9), "Outer timing mismatch")
    n = probe.SPEC["query_tiles"]
    order = ["synthetic_payload_fill", "model_factory", "bank_bind_CPU_scorer_index"] + [s
        for _ in range(n) for variant in probe.models.VARIANTS for s in
        ("restoration_swinir_x4" if variant == "swinir_x4" else "preparation_"+variant,
         "detector_inference_including_CPU_FAISS")] + ["adapter_close"]
    _require([r["stage"] for r in rows] == order, "Phase/call order or count mismatch")
    start_cuda, end_cuda = _cuda(resource["cuda_at_start"]), _cuda(resource["cuda_at_end"])
    _require(all(a <= b for a, b in zip(start_cuda[2:], end_cuda[2:])) and end_cuda[2] > 0,
             "CUDA cumulative peak mismatch")
    previous, peaks, highwater = start, start_cuda[2:], 0
    recorder = probe.measured.Recorder(lambda: None)
    detector_times = []
    for row in rows:
        begin, finish, elapsed = (_number(row[k]) for k in ("perf_counter_start", "perf_counter_end", "elapsed_seconds"))
        _require(previous <= begin <= finish <= end and row["completed"] == "True"
                 and math.isclose(elapsed, finish-begin, rel_tol=1e-9, abs_tol=1e-9), "Overlapping/incomplete stage timing")
        previous = finish
        before, after, peak = (_bytes(row[k]) for k in ("rss_before_bytes", "rss_after_bytes", "os_lifetime_peak_rss_after_bytes"))
        _require(0 < before <= peak and 0 < after <= peak and highwater <= peak, "Stage RSS/high-water mismatch")
        highwater = peak
        counters = _cuda({k: row["cuda_" + k] for k in limited.CUDA_FIELDS})
        _require(all(a <= b for a, b in zip(peaks, counters[2:])), "CUDA row peak decreased")
        peaks = counters[2:]
        recorder.rows.append(dict(stage=row["stage"], elapsed_seconds=elapsed, completed=True))
        if row["stage"] == "detector_inference_including_CPU_FAISS":
            detector_times.append(elapsed)
    expected = recorder.summary()
    summary = resource["phase_summary"]
    _require(set(summary) == set(expected), "Phase summary inventory mismatch")
    for stage, values in expected.items():
        _require(set(summary[stage]) == set(values), "Phase summary field mismatch")
        for key, value in values.items():
            if key.endswith("calls") or key == "call_count":
                _require(type(summary[stage][key]) is int and summary[stage][key] == value, "Phase summary count mismatch")
            else:
                _require(math.isclose(_number(summary[stage][key]), value, rel_tol=1e-9, abs_tol=1e-9), "Phase summary time mismatch")
    memory = resource["process_memory"]
    baseline, sampled, lifetime = (_bytes(memory[k]) for k in
        ("baseline_rss_bytes", "sampled_peak_rss_bytes", "os_process_lifetime_peak_rss_bytes"))
    _require(0 < baseline <= sampled <= lifetime and highwater <= lifetime
             and _bytes(memory["sample_count"]) >= 2, "Sampled RSS/high-water mismatch")
    _require(_number(memory["sampling_interval_seconds"]) > 0 and bool(memory["measurement_method"]), "Missing sampling method")
    _bytes(memory["system_available_min_observed_bytes"])
    for key in ("sampled_workspace_disk_max_bytes", "sampled_output_disk_max_bytes"):
        _bytes(memory[key])
    _require(all(a <= b for a, b in zip(peaks, end_cuda[2:])), "Final CUDA peak below stage observations")
    total = sum(v["sum_elapsed_seconds"] for v in expected.values())
    _require(total <= end-start or math.isclose(total, end-start, rel_tol=1e-9, abs_tol=1e-9), "Child sum exceeds outer interval")
    return end-start, total, expected, detector_times


def validate(directory, source_root, reference_run=None):
    directory, source_root = Path(directory).resolve(), Path(source_root).resolve()
    protocol, state, resource = [_json(directory, n) for n in FILES[:3]]
    _require(all(v.get("kind") == probe.KIND for v in (state, protocol, resource)), "Wrong resource artifact kind")
    for name, key in (("PROTOCOL.json", "protocol_sha256"), ("resources.json", "resources_sha256"), ("stage_times.csv", "timings_sha256")):
        _require(file_sha256(limited.safe_source(directory, name)) == _digest(state[key]), "Artifact hash mismatch: " + name)
    for v in (state, protocol, resource):
        _require(all(v.get(k) is False for k in ("actual_pcb_bank_created", "full_bank_validated", "full_pilot_approved"))
                 and v.get("metrics") is None and "metrics" in v, "Forbidden bank/metric/approval claim")
    if state.get("status") == probe.FIXTURE_COMPLETE or resource.get("input_kind") == "injected_fixture_NOT_GPU_evidence":
        return dict(status=REJECT, execution_class="INJECTED_FIXTURE_NOT_GPU_EVIDENCE", full_pilot_approved=False,
                    cuda_execution_reported=False, error="CPU/injected fixture is not full-cap CUDA resource evidence")
    if protocol.get("device") == "cpu":
        return dict(status=REJECT, execution_class="REPORTED_CPU_NOT_GPU_EVIDENCE", full_pilot_approved=False,
                    cuda_execution_reported=False, error="CPU report is not CUDA resource evidence")
    _require(state.get("status") == resource.get("status") == probe.COMPLETE, "Incomplete/failed/not-executed probe")
    _require(protocol["spec"] == probe.SPEC and resource["actual_shape"] == [probe.SPEC["rows"], probe.SPEC["dimension"]], "Fixed spec/shape mismatch")
    _require(protocol["input_kind"] == resource["input_kind"] == "SYNTHETIC_BANK_AND_RGB_NOT_RESEARCH_PREDICTIONS"
             and protocol["device"] == "cuda" and protocol["live_cuda_verified"] is False, "Input/device contract mismatch")
    _require(type(protocol["source_worktree_dirty"]) is bool and protocol["blockers"] == state["blockers"] == [], "Invalid preflight/dirty metadata")
    _require(state["payload_allocation_started"] is True and state["model_factory_call_started"] is True
             and state["model_execution_started"] is resource["model_execution_started"] is True, "Execution flags mismatch")
    _require(all(resource[k] is False for k in ("predictions_exported", "gt_callback_used", "process_exit_self_verified")), "Prediction/GT/process-exit claim")
    _require(all(resource[k] is True for k in ("actual_fullcap_payload_observed", "payload_unchanged", "adapter_close_returned", "payload_cleanup"))
             and resource["payload_retained"] is False and resource["error"] is None, "Payload/cleanup contract mismatch")
    payload = directory / "synthetic_bank_payload.npy"
    _require(not payload.exists() and not payload.is_symlink(), "Payload still present despite cleanup claim")
    _digest(resource["synthetic_payload_sha256"])
    sources = _source_binding(source_root, protocol)
    accepted, old_resource = _reference(source_root, reference_run, protocol, sources)
    _require(set(protocol["checkpoints"]) == {"backbone", "swinir"}, "Checkpoint inventory mismatch")
    for name, digest in (("backbone", probe.models.BACKBONE_SHA256), ("swinir", probe.models.SWINIR_SHA256)):
        _require(protocol["checkpoints"][name]["sha256"] == digest, "Pinned checkpoint hash mismatch")
    _require(protocol["requested_queries_per_variant"] == probe.SPEC["query_tiles"], "Requested query count mismatch")
    gpu = resource["cuda_device"]
    _require(isinstance(gpu, dict) and all(isinstance(gpu.get(k), str) and gpu[k] for k in
             ("gpu_name", "torch_version", "cuda_runtime")), "Missing reported CUDA runtime/device")
    _require(0 < _bytes(gpu["free_bytes"]) <= _bytes(gpu["total_bytes"])
             and gpu["previous_peak_is_only_a_floor"] is True, "CUDA free/total or floor contract mismatch")
    _require(_bytes(gpu["free_bytes"]) >= _bytes(old_resource["cuda_at_end"]["max_reserved_bytes_since_profiler_start"]), "CUDA pre-allocation floor mismatch")
    for name in ("python_version", "numpy_version"):
        _require(isinstance(resource[name], str) and bool(resource[name]), "Missing runtime version")
    outer, child, summary, times = _timings(directory, resource)
    expected = [(i, v) for i in range(probe.SPEC["query_tiles"]) for v in probe.models.VARIANTS]
    queries = resource["query_checks"]
    _require([(q["tile"], q["variant"]) for q in queries] == expected
             and all(type(q["tile"]) is int and q["finite"] is True for q in queries), "Query inventory/finite report mismatch")
    _require(all(math.isclose(_number(q["detector_seconds"]), t, rel_tol=1e-9, abs_tol=1e-9)
                 for q, t in zip(queries, times, strict=True)), "Query/CSV detector time mismatch")
    _require(resource["drive_delta_is_not_exclusive_output_size"] is True, "Disk accounting disclaimer missing")
    for key in ("drive_free_bytes_at_start", "drive_free_bytes_at_end", "output_payload_before_cleanup_bytes"):
        _bytes(resource[key])
    for key in ("available_ram_snapshot_bytes", "free_disk_snapshot_bytes"):
        _bytes(protocol[key])  # Snapshots were recorded after guards, not their exact decision inputs.
    _require(resource["output_payload_before_cleanup_bytes"] >= protocol["plan"]["bank_payload_bytes"], "Output payload below bank size")
    return dict(status=PASS, execution_class="REPORTED_CUDA_SYNTHETIC_FULLCAP_PROBE", full_pilot_approved=False,
        actual_pcb_bank_created=False, full_bank_validated=False, metrics=None, cuda_execution_reported=True,
        source_commit=protocol["source_commit"], source_worktree_dirty=protocol["source_worktree_dirty"],
        resource_plan_estimate=protocol["plan"], available_ram_snapshot_bytes=protocol["available_ram_snapshot_bytes"],
        free_disk_snapshot_bytes=protocol["free_disk_snapshot_bytes"],
        outer_seconds=outer, child_phase_sum_seconds=child, outer_minus_child_seconds=outer-child, phase_summary=summary,
        process_memory=resource["process_memory"], cuda_device=gpu, cuda_at_start=resource["cuda_at_start"], cuda_at_end=resource["cuda_at_end"],
        drive_free_bytes_at_start=resource["drive_free_bytes_at_start"], drive_free_bytes_at_end=resource["drive_free_bytes_at_end"],
        drive_free_change_bytes=resource["drive_free_bytes_at_end"]-resource["drive_free_bytes_at_start"],
        output_payload_before_cleanup_bytes=resource["output_payload_before_cleanup_bytes"],
        spec=protocol["spec"], actual_shape_reported=resource["actual_shape"], dtype_contract_from_bound_source="float32",
        input_files_sha256={n: file_sha256(limited.safe_source(directory, n)) for n in FILES},
        input_file_hashes_verified=[n for n in FILES if n != "status.json"],
        status_file_hash_role="Computed receipt only; no external trusted digest supplied",
        reference_file_hashes_verified=list(probe.REFERENCE_FILES),
        reference_payload_coverage=accepted["payload_coverage"], reference_raw_file_hashes_verified=accepted["raw_file_hashes_verified"],
        reference_raw_files_not_supplied=accepted["raw_files_not_supplied"],
        payload_coverage="METADATA_ONLY_PAYLOAD_CLEANUP_REPORTED", synthetic_payload_sha256_reported=resource["synthetic_payload_sha256"],
        synthetic_payload_file_hash_independently_verified=False, raw_array_contents_independently_checked=False,
        checkpoint_file_hashes_independently_verified=False, query_finite_checks_reported=len(queries))


def review(directory, output, source_root, reference_run=None):
    directory, output = Path(directory).resolve(), Path(output).resolve()
    for source in (directory, Path(reference_run).resolve() if reference_run is not None else None):
        if source is not None:
            _require(not output.is_relative_to(source) and not source.is_relative_to(output), "Review input/output trees must be disjoint")
    output.mkdir(parents=True, exist_ok=False)
    try:
        result = validate(directory, source_root, reference_run)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, subprocess.SubprocessError) as error:
        result = dict(status=REJECT, full_pilot_approved=False, cuda_execution_reported=False,
                      error=f"{type(error).__name__}: {error}")
    own_root = Path(__file__).resolve().parents[2]
    result.update(independent_remote_execution_verified=False, actual_pcb_bank_created=False,
        full_bank_validated=False, metrics=None, input_directory=str(directory),
        reference_directory=str(Path(reference_run).resolve()) if reference_run is not None else None,
        checker_source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=own_root, text=True).strip(),
        checker_worktree_dirty=bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=own_root, text=True).strip()),
        reviewer_source_sha256={n: file_sha256(own_root/n) for n in
            ("src/sr_anomaly/pcb_fullcap_review.py", "scripts/review_pcb_fullcap_probe.py")},
        limitations=["Reported metadata consistency is not independent remote-execution attestation.",
            "Deleted/omitted synthetic payload, raw arrays and checkpoint contents are not independently checked.",
            "Outer/child times and unrelated peaks must not be added; no speedup or throughput conclusion.",
            "CUDA counters are PyTorch counters; drive-wide free-space changes are not exclusive output size.",
            "This synthetic resource scope does not validate actual fit/selection, producer or full pilot."])
    for key, value in (("input_file_hashes_verified", []), ("reference_file_hashes_verified", []),
                       ("payload_coverage", "UNVERIFIED_REJECTED_OR_FIXTURE")):
        result.setdefault(key, value)
    (output/"review.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    lines = ["# Full-cap synthetic resource metadata review", "", "Status: " + result["status"],
        "Execution class: " + result.get("execution_class", "REJECTED_OR_INCOMPLETE"),
        "Full pilot approved: false", "", "## Verification scope", "",
        "Only explicitly supplied metadata and reviewed local source bindings are checked. No models or arrays are loaded.", ""]
    if result["status"] == PASS:
        lines += ["Execution commit: " + result["source_commit"], "Checker commit: " + result["checker_source_commit"],
            "Payload coverage: " + result["payload_coverage"], "Reference payload coverage: " + result["reference_payload_coverage"],
            "", "## Reported resource observations", "",
            f"Outer seconds: {result['outer_seconds']}; child phase sum: {result['child_phase_sum_seconds']}. Do not add them.",
            "Process memory (distinct sampled/lifetime fields): " + json.dumps(result["process_memory"]),
            "CUDA cumulative end counters: " + json.dumps(result["cuda_at_end"]),
            f"Drive free change: {result['drive_free_change_bytes']} bytes; output payload before cleanup: {result['output_payload_before_cleanup_bytes']} bytes.",
            "Reference raw files not supplied: " + json.dumps(result["reference_raw_files_not_supplied"]), ""]
    else:
        lines += ["Reason: " + result["error"], ""]
    lines += ["## Limits and next gates", "", *["- " + s for s in result["limitations"]],
              "", "Next: actual PCB fit/selection, full-producer integration, current RAM/disk gates and separate final approval."]
    (output/"REVIEW.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return result
