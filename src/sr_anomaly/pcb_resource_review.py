"""Read-only consistency review of limited-smoke returns, never execution approval."""
from __future__ import annotations

from collections import Counter
import csv
import json
import math
from pathlib import Path

from .bounded_bank import file_sha256
from . import pcb_model_resources as profiler
from .pcb_tiled_models import VARIANTS
from .pcb_tiled_runner import GEOMETRY, PROTOCOL, load_inventory, safe_source, smoke_parents
from .pcb_tiling import tile_boxes
from .tiled_cpu_pipeline import Parent, validate_parents

COMPLETE = "MODEL_SMOKE_RESOURCE_COMPLETE_NOT_FULL_APPROVAL"
CUDA_FIELDS = ("allocated_bytes", "reserved_bytes", "max_allocated_bytes_since_profiler_start",
               "max_reserved_bytes_since_profiler_start")
ORIGINAL_CODE = ("src/sr_anomaly/pcb_tiled_models.py", "src/sr_anomaly/pcb_tiled_runner.py", "scripts/run_pcb_tiled_patchcore.py",
    "src/sr_anomaly/device.py", "src/sr_anomaly/bounded_bank.py", "src/sr_anomaly/tiled_cpu_pipeline.py",
    "src/sr_anomaly/pcb_tiling.py", "src/sr_anomaly/real_models.py", "src/sr_anomaly/metrics.py",
    "src/sr_anomaly/fusion.py", "third_party/SwinIR/models/network_swinir.py",
    "third_party/patchcore-inspection/src/patchcore/backbones.py", "src/sr_anomaly/pcb_board_analysis.py")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    _require(not isinstance(value, bool), "Boolean is not a measurement")
    value = float(value)
    _require(math.isfinite(value) and value >= 0, "Nonfinite/negative measurement")
    return value


def _cuda(values):
    _require(isinstance(values, dict) and set(values) == set(CUDA_FIELDS), "Missing CUDA counters")
    result = [_number(values[k]) for k in CUDA_FIELDS]
    _require(all(v.is_integer() for v in result), "Noninteger CUDA byte counters")
    allocated, reserved, peak_a, peak_r = result
    _require(allocated <= reserved <= peak_r and allocated <= peak_a <= peak_r, "Inconsistent CUDA counters")
    return result


def validate(directory, source_root):
    """Metadata can pass with omitted arrays; report that coverage, never infer it."""
    directory, source_root = Path(directory).resolve(), Path(source_root).resolve()
    state = _read(directory / "status.json")
    _require(state.get("status") == COMPLETE, "Incomplete/not-executed resource artifact")
    protocol, resource = [_read(directory / n) for n in ("PROTOCOL.json", "resources.json")]
    _require(state.get("kind") == protocol.get("kind") == resource.get("kind") == profiler.KIND
             and state.get("status") == COMPLETE and resource.get("completed") is True, "Incomplete/wrong resource artifact")
    _require(all(v.get("full_pilot_approved") is False for v in (state, protocol, resource))
             and state.get("metrics_exported") is False and protocol.get("metrics") is None
             and resource.get("metrics") is None and resource.get("full_bank_validated") is False,
             "Forbidden full-bank/metric/approval claim")
    for name, digest in (("PROTOCOL.json", state.get("protocol_sha256")),
                         ("resources.json", state.get("resources_sha256")),
                         ("stage_times.csv", state.get("timings_sha256")),
                         ("raw/status.json", resource.get("raw_status_sha256"))):
        _require(file_sha256(directory / name) == digest, f"Hash mismatch: {name}")
    report = protocol["preflight"]
    _require(protocol.get("scope") == report.get("scope") == "model-smoke"
             and report.get("status") == "PREFLIGHT_PASS" and report.get("blockers") == [], "Invalid limited-smoke preflight")
    _require(protocol.get("smoke_bank_vectors_expected") == 37632
             and protocol.get("full_bank_capacity_not_validated") == 262144, "Changed bank scope")
    wrapper = protocol.get("wrapper_code_sha256", {})
    _require(set(wrapper) == set(profiler.CODE), "Missing wrapper source coverage")
    original, references = report.get("code_sha256", {}), protocol.get("input_reference_sha256", {})
    _require(bool(original) and bool(references), "Missing original source/reference coverage")
    _require(file_sha256(source_root / PROTOCOL) == report.get("protocol_sha256"), "Scientific protocol mismatch")
    for group in (wrapper, original, references):
        for name, digest in group.items():
            _require(file_sha256(safe_source(source_root, name)) == digest, f"Reviewed source/reference mismatch: {name}")

    fixture = resource.get("input_kind") == "injected_fixture_NOT_real_model_evidence"
    _require(fixture or resource.get("input_kind") == "existing_limited_raw_model_smoke", "Unknown execution kind")
    _require(resource.get("scope") == {"expected_smoke_vectors": 37632, "full_bank_capacity_not_validated": 262144}, "Resource scope mismatch")
    device = report["execution"].get("actual_device")
    _require(device in ("cpu", "cuda") and resource.get("gt_callback_used") is False, "Device/GT contract mismatch")
    _require(isinstance(protocol.get("source_worktree_dirty"), bool)
             and protocol["source_worktree_dirty"] == report.get("source_worktree_dirty"), "Dirty-source metadata mismatch")
    _require(state.get("factory_call_started") is True, "No model factory call recorded")
    if not fixture:
        _require(state.get("model_execution_started") is True, "Real model execution not recorded")
        _require(set(ORIGINAL_CODE) <= set(original), "Incomplete original execution-source coverage")
        _require(isinstance(report.get("source_commit"), str) and len(report["source_commit"]) == 40,
                 "Missing real execution source commit")
    if device == "cuda":
        _require(report["execution"].get("cuda_available") is True, "CUDA unavailable in execution metadata")
        _require(fixture or bool(report["execution"].get("gpu_name")), "Missing real GPU name")
        start_cuda, end_cuda = _cuda(resource.get("cuda_at_start")), _cuda(resource.get("cuda_at_end"))
        _require(all(a <= b for a, b in zip(start_cuda[2:], end_cuda[2:])), "CUDA cumulative peak decreased")
        _require(fixture or end_cuda[2] > 0, "Real CUDA execution has no allocated peak")
    else:
        _require(resource.get("cuda_at_start") is None and resource.get("cuda_at_end") is None, "CPU run claims CUDA counters")

    raw = _read(directory / "raw/status.json")
    _require(resource.get("raw_status") == raw.get("status"), "Raw completion summary mismatch")
    _require(raw.get("status") == "COMPLETE" and raw.get("scope") == "model-smoke"
             and raw.get("bank_unchanged") is True and raw.get("smoke_bank") == "CREATED_SUBSET_ONLY"
             and raw.get("full_pcb_bank") == "NOT_CREATED" and raw.get("metrics") is None
             and raw.get("thresholds") is None and raw.get("calibration") == "NOT_CREATED_RAW_MAPS_ONLY", "Invalid raw-smoke contract")
    parents = validate_parents(Parent(p["sample"], p["split"], p["label"], tuple(p["size_wh"])) for p in raw["parents"])
    _require(raw["parents"] == report.get("parents"), "Raw/preflight parent mismatch")
    _require(report.get("variants") == list(VARIANTS), "Variant mismatch")
    if not fixture:
        _require(raw.get("provenance", {}).get("input_kind") == "fit_normal_feature_stream"
                 and raw["provenance"].get("preflight") == report, "Raw/preflight provenance mismatch")
        _require(raw.get("selection_indices_sha256") == report.get("selection_indices_sha256"), "Raw/preflight selection mismatch")
        frozen, input_rows, _ = load_inventory(source_root / GEOMETRY)
        _require(parents == smoke_parents(frozen), "Not the pre-fixed limited parent selection")
        _require(all(raw.get("feature_counts", {}).get(k) == 37632 for k in
                     ("observed_vectors", "validated_vectors", "stored_vectors")), "Not a 37632-vector smoke")
        receipts, frozen_rows = resource.get("rgb_receipts", {}), {r["sample"]: r for r in input_rows}
        _require(set(receipts) == {p.sample for p in parents}, "Missing consumed RGB receipts")
        for p in parents:
            receipt = receipts[p.sample]
            _require(receipt.get("file_sha256") == frozen_rows[p.sample]["image_sha256"]
                     and receipt.get("shape") == [p.size_wh[1], p.size_wh[0], 3]
                     and receipt.get("dtype") == "uint8"
                     and (receipt.get("sample"), receipt.get("split"), receipt.get("label")) == (p.sample, p.split, p.label)
                     and receipt.get("size_wh") == list(p.size_wh)
                     and receipt.get("coordinate_transform") == "identity_no_exif_transpose"
                     and isinstance(receipt.get("decoded_rgb_sha256"), str)
                     and len(receipt["decoded_rgb_sha256"]) == 64, "Consumed RGB receipt mismatch")
    _require(resource.get("observed_feature_counts") == raw.get("feature_counts"), "Feature-count summary mismatch")
    inventory = {p.sample: p for p in parents if p.split != "fit"}
    expected = {(p.sample, v) for p in inventory.values() for v in VARIANTS}
    observed, declared = set(), {}
    for i, row in enumerate(raw["rows"]):
        key, parent = (row["sample"], row["variant"]), inventory.get(row["sample"])
        _require(parent is not None and key in expected and key not in observed
                 and row["split"] == parent.split and row["label"] == parent.label
                 and row["size_wh"] == list(parent.size_wh) and row["file"] == f"predictions/{i:04d}.npy", "Prediction inventory mismatch")
        # Scores may legitimately be negative after other protocols, but must be finite here.
        _require(math.isfinite(float(row["score"])), "Nonfinite image score")
        observed.add(key)
        declared[row["file"]] = row["sha256"]
    _require(observed == expected, "Missing predictions")
    bank_hashes = raw.get("bank_artifact_sha256", {})
    _require(set(bank_hashes) == {"status.json", "bank.npy", "selected_indices.npy"}, "Missing bank hash inventory")
    declared.update({"bank/" + name: digest for name, digest in bank_hashes.items()})
    verified, missing = [], []
    for name, digest in declared.items():
        path = safe_source(directory / "raw", name)
        if path.exists():
            _require(path.is_file(), f"Expected a file: {name}")
            _require(file_sha256(path) == digest, f"Raw payload hash mismatch: {name}")
            verified.append(name)
        else:
            missing.append(name)
    bank_metadata_verified = "bank/status.json" in verified
    if bank_metadata_verified:
        bank = _read(directory / "raw/bank/status.json")
        _require(bank.get("status") == "COMPLETE" and bank.get("progress") == raw.get("feature_counts")
                 and bank.get("selection_indices_sha256") == raw.get("selection_indices_sha256"), "Bank/raw metadata mismatch")
        for name in ("bank.npy", "selected_indices.npy"):
            _require(bank.get("artifact_sha256", {}).get(name) == bank_hashes[name], "Bank checksum inventories disagree")
        if not fixture:
            _require(bank.get("dimension") == 1024 and bank.get("capacity") == 262144
                     and bank.get("total_vectors") == bank.get("selected_count") == 37632, "Changed limited bank shape/capacity")

    with (directory / "stage_times.csv").open(encoding="utf-8", newline="") as handle:
        times = list(csv.DictReader(handle))
    outer_start, outer_end = _number(resource["perf_counter_start"]), _number(resource["perf_counter_end"])
    _require(outer_start <= outer_end and math.isclose(_number(resource["outer_elapsed_seconds"]),
             outer_end - outer_start, rel_tol=1e-9, abs_tol=1e-9), "Outer timing mismatch")
    grouped, previous, cuda_peaks = {}, outer_start, [0., 0.]
    for row in times:
        begin, end, elapsed = (_number(row[k]) for k in ("perf_counter_start", "perf_counter_end", "elapsed_seconds"))
        _require(previous <= begin <= end <= outer_end and row["completed"] == "True"
                 and math.isclose(elapsed, end - begin, rel_tol=1e-9, abs_tol=1e-9), "Overlapping/incomplete/invalid stage timing")
        previous = end
        before, after, peak = (_number(row[k]) for k in ("rss_before_bytes", "rss_after_bytes", "os_lifetime_peak_rss_after_bytes"))
        _require(0 < before <= peak and 0 < after <= peak, "Stage RSS/high-water mismatch")
        if device == "cuda":
            counters = _cuda({k: row["cuda_" + k] for k in CUDA_FIELDS})
            _require(all(a <= b for a, b in zip(cuda_peaks, counters[2:])), "CUDA cumulative row peak decreased")
            cuda_peaks = counters[2:]
        else:
            _require(all(not row.get("cuda_" + k) for k in CUDA_FIELDS), "CPU timing row claims CUDA counters")
        grouped.setdefault(row["stage"], []).append(elapsed)
    tiles = {p.sample: len(tile_boxes(p.size_wh)) for p in parents}
    predicted_tiles = sum(tiles[p.sample] for p in parents if p.split != "fit")
    calls = {"model_factory": 1, "adapter_close": 1, "bank_bind_CPU_scorer_index": 1,
             "feature_extraction": sum(math.ceil(tiles[p.sample] / 2) for p in parents if p.split == "fit"),
             "detector_inference_including_CPU_FAISS": 3 * predicted_tiles,
             "preparation_clean": predicted_tiles, "preparation_bicubic_x4": predicted_tiles,
             "restoration_swinir_x4": predicted_tiles}
    _require(Counter({k: len(v) for k, v in grouped.items()}) == Counter(calls), "Wrapped phase call counts mismatch")
    summary = resource.get("phase_summary", {})
    _require(set(summary) == set(grouped), "Phase summary inventory mismatch")
    for stage, values in grouped.items():
        actual = summary[stage]
        _require(set(actual) == {"call_count", "completed_calls", "sum_elapsed_seconds", "min_elapsed_seconds", "max_elapsed_seconds"},
                 "Unknown/incomplete phase summary schema")
        _require(actual["call_count"] == actual["completed_calls"] == len(values), "Phase count mismatch")
        for name, expected_value in (("sum_elapsed_seconds", sum(values)), ("min_elapsed_seconds", min(values)), ("max_elapsed_seconds", max(values))):
            _require(math.isclose(_number(actual[name]), expected_value, rel_tol=1e-9, abs_tol=1e-9), "Phase time summary mismatch")
    observed_memory = resource["process_memory"]
    baseline, sample, peak = (_number(observed_memory[k]) for k in
        ("baseline_rss_bytes", "sampled_peak_rss_bytes", "os_process_lifetime_peak_rss_bytes"))
    _require(0 < baseline <= sample <= peak and observed_memory["sample_count"] >= 2, "Sampled RSS/high-water mismatch")
    _require(all(v.is_integer() for v in (baseline, sample, peak)), "Noninteger RSS byte counters")
    _require(all(_number(row["os_lifetime_peak_rss_after_bytes"]) <= peak for row in times), "Global OS high-water below stage observation")
    _number(observed_memory["system_available_min_observed_bytes"])
    if device == "cuda":
        _require(all(a <= b for a, b in zip(cuda_peaks, end_cuda[2:])), "CUDA final peak below recorded stages")
    return {"status": "CONSISTENCY_VERIFIED_NOT_FULL_APPROVAL", "full_pilot_approved": False,
        "execution_class": "INJECTED_FIXTURE_NOT_GPU_EVIDENCE" if fixture else "REPORTED_CUDA_LIMITED_SMOKE" if device == "cuda" else "REPORTED_CPU_LIMITED_SMOKE",
        "cuda_execution_reported": not fixture and device == "cuda", "independent_remote_execution_verified": False,
        "source_worktree_dirty": protocol.get("source_worktree_dirty"),
        "source_commit": report.get("source_commit"), "raw_file_hashes_verified": verified, "raw_files_not_supplied": missing,
        "payload_coverage": "ALL_DECLARED_FILE_HASHES_VERIFIED" if not missing else "PARTIAL_OR_METADATA_ONLY",
        "bank_metadata_verified": bank_metadata_verified,
        "raw_array_shape_or_finite_contents_independently_checked": False,
        "outer_seconds": outer_end - outer_start, "phase_summary": summary,
        "sampled_peak_rss_bytes": int(sample), "os_lifetime_peak_rss_bytes": int(peak),
        "limitations": ["Hash consistency is not independent attestation of remote execution.",
            "No dataset/checkpoint bytes are rehashed here; execution-time bindings are reviewed metadata.",
            "No missing raw map/bank bytes are inferred as verified; no arrays are loaded.",
            "Outer/child times and process/stage peaks must not be added; instrumented latency is not throughput.",
            "PyTorch CUDA counters are not whole-system VRAM; limited bank does not validate full bank or pilot."]}


def review(directory, output, source_root):
    directory, output = Path(directory).resolve(), Path(output).resolve()
    _require(not output.is_relative_to(directory) and not directory.is_relative_to(output), "Review output/source trees must be disjoint")
    output.mkdir(parents=True, exist_ok=False)
    try:
        result = validate(directory, source_root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {"status": "REJECTED_NOT_FULL_APPROVAL", "full_pilot_approved": False,
                  "error": f"{type(error).__name__}: {error}"}
    result["input_directory"] = str(directory)
    result["reviewer_source_sha256"] = file_sha256(Path(__file__))
    (output / "review.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result
