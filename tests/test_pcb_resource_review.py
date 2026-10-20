import csv
from dataclasses import asdict
import json

import pytest

from test_pcb_model_resources import prepared, fixture_execution  # Reuse explicitly injected tiny fixture.
from scripts.check_tiled_cpu_integration import dummy_fixture
from sr_anomaly import pcb_model_resources as profiler
from sr_anomaly import pcb_resource_review as reviewer
from sr_anomaly.bounded_bank import file_sha256
from sr_anomaly.pcb_tiled_models import VARIANTS


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def refresh(output):
    state = reviewer._read(output / "status.json")
    resource = reviewer._read(output / "resources.json")
    resource["raw_status_sha256"] = file_sha256(output / "raw/status.json")
    write(output / "resources.json", resource)
    state.update(protocol_sha256=file_sha256(output / "PROTOCOL.json"),
                 resources_sha256=file_sha256(output / "resources.json"),
                 timings_sha256=file_sha256(output / "stage_times.csv"))
    write(output / "status.json", state)


@pytest.fixture
def completed(prepared, monkeypatch):
    root, output = prepared
    protocol = reviewer._read(output / "PROTOCOL.json")
    protocol["preflight"].update(parents=[asdict(p) for p in dummy_fixture()[0]], variants=list(VARIANTS))
    write(output / "PROTOCOL.json", protocol)
    state = reviewer._read(output / "status.json")
    state["protocol_sha256"] = file_sha256(output / "PROTOCOL.json")
    write(output / "status.json", state)
    adapter, loader = fixture_execution(monkeypatch)
    profiler.execute(output, root, factory=lambda *a: (adapter, lambda t, v: t), loader=loader)
    return root, output


def test_fixture_consistency_is_not_gpu_or_full_evidence(completed, tmp_path):
    root, output = completed
    result = reviewer.validate(output, root)
    assert result["status"] == "CONSISTENCY_VERIFIED_NOT_FULL_APPROVAL"
    assert result["execution_class"] == "INJECTED_FIXTURE_NOT_GPU_EVIDENCE"
    assert not result["cuda_execution_reported"] and not result["full_pilot_approved"]
    assert not result["independent_remote_execution_verified"]
    assert result["payload_coverage"] == "ALL_DECLARED_FILE_HASHES_VERIFIED"
    assert not result["raw_array_shape_or_finite_contents_independently_checked"]
    saved = reviewer.review(output, tmp_path / "review", root)
    assert saved["status"] == result["status"]
    with pytest.raises(FileExistsError):
        reviewer.review(output, tmp_path / "review", root)
    with pytest.raises(ValueError, match="disjoint"):
        reviewer.review(output, output / "overwrite", root)


def test_missing_heavy_arrays_are_unverified_not_fabricated_success(completed):
    root, output = completed
    # A transfer package may omit arrays. Metadata checks still have honest limited coverage.
    (output / "raw/bank/bank.npy").unlink()
    (output / "raw/predictions/0000.npy").unlink()
    result = reviewer.validate(output, root)
    assert result["payload_coverage"] == "PARTIAL_OR_METADATA_ONLY"
    assert set(result["raw_files_not_supplied"]) == {"bank/bank.npy", "predictions/0000.npy"}
    assert not result["cuda_execution_reported"]


@pytest.mark.parametrize("name", ["PROTOCOL.json", "resources.json", "stage_times.csv", "raw/status.json", "raw/predictions/0000.npy"])
def test_hash_chain_or_present_payload_tampering_rejected(completed, name):
    root, output = completed
    with (output / name).open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises((ValueError, json.JSONDecodeError), match="mismatch|Extra data"):
        reviewer.validate(output, root)


@pytest.mark.parametrize("change", ["summary", "rss", "cuda_claim", "gt", "counts", "approval", "source", "dirty"])
def test_recomputed_hashes_cannot_hide_semantic_mismatch(completed, change):
    root, output = completed
    resource = reviewer._read(output / "resources.json")
    if change == "summary":
        resource["phase_summary"]["model_factory"]["sum_elapsed_seconds"] += 1
    elif change == "rss":
        resource["process_memory"]["sampled_peak_rss_bytes"] = resource["process_memory"]["os_process_lifetime_peak_rss_bytes"] + 1
    elif change == "cuda_claim":
        resource["cuda_at_end"] = {k: 10 for k in reviewer.CUDA_FIELDS}
    elif change == "gt":
        resource["gt_callback_used"] = True
    elif change == "counts":
        resource["observed_feature_counts"]["stored_vectors"] += 1
    elif change == "approval":
        resource["full_pilot_approved"] = True
    elif change == "source":
        (root / profiler.CODE[0]).write_bytes(b"changed source")
    elif change == "dirty":
        protocol = reviewer._read(output / "PROTOCOL.json")
        protocol["source_worktree_dirty"] = False
        write(output / "PROTOCOL.json", protocol)
    write(output / "resources.json", resource)
    refresh(output)
    with pytest.raises(ValueError):
        reviewer.validate(output, root)


@pytest.mark.parametrize("change", ["overlap", "elapsed", "failed_call", "missing_call"])
def test_timing_domain_consistency(completed, change):
    root, output = completed
    with (output / "stage_times.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    if change == "overlap":
        rows[1]["perf_counter_start"] = rows[0]["perf_counter_start"]
    elif change == "elapsed":
        rows[0]["elapsed_seconds"] = "nan"
    elif change == "failed_call":
        rows[0]["completed"] = "False"
    else:
        rows.pop()
    with (output / "stage_times.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    refresh(output)
    with pytest.raises(ValueError):
        reviewer.validate(output, root)


def test_preflight_or_incomplete_return_is_rejected_without_models(prepared, tmp_path):
    root, output = prepared
    result = reviewer.review(output, tmp_path / "not-executed", root)
    assert result["status"] == "REJECTED_NOT_FULL_APPROVAL" and not result["full_pilot_approved"]


@pytest.mark.parametrize("values", [dict(allocated_bytes=20, reserved_bytes=10, max_allocated_bytes_since_profiler_start=20, max_reserved_bytes_since_profiler_start=20),
                                   dict(allocated_bytes=1, reserved_bytes=2, max_allocated_bytes_since_profiler_start=0, max_reserved_bytes_since_profiler_start=2)])
def test_cuda_counter_arithmetic_without_cuda_import(values):
    with pytest.raises(ValueError, match="CUDA"):
        reviewer._cuda(values)


def test_synthetic_cuda_metadata_branch_is_not_independent_execution_attestation(completed, monkeypatch):
    # Manufacture only unit-test metadata; no CUDA calls or actual GPU results.
    root, output = completed
    protocol = reviewer._read(output / "PROTOCOL.json")
    for name in reviewer.ORIGINAL_CODE:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("synthetic source reference, not executed", encoding="utf-8")
        protocol["preflight"]["code_sha256"][name] = file_sha256(path)
    protocol["preflight"].update(source_commit="e" * 40,
        execution={"actual_device": "cuda", "cuda_available": True, "gpu_name": "synthetic unit metadata, not hardware"})
    raw = reviewer._read(output / "raw/status.json")
    protocol["preflight"]["selection_indices_sha256"] = raw["selection_indices_sha256"]
    raw["provenance"] = {"input_kind": "fit_normal_feature_stream", "preflight": protocol["preflight"]}
    raw["feature_counts"] = {k: 37632 for k in ("observed_vectors", "validated_vectors", "stored_vectors")}
    resource = reviewer._read(output / "resources.json")
    resource.update(input_kind="existing_limited_raw_model_smoke", observed_feature_counts=raw["feature_counts"],
        cuda_at_start=dict(zip(reviewer.CUDA_FIELDS, [0, 0, 0, 0])),
        cuda_at_end=dict(zip(reviewer.CUDA_FIELDS, [4, 8, 4, 8])), rgb_receipts={})
    parents = reviewer.validate_parents(reviewer.Parent(p["sample"], p["split"], p["label"], tuple(p["size_wh"])) for p in raw["parents"])
    for parent in parents:
        resource["rgb_receipts"][parent.sample] = {**asdict(parent), "size_wh": list(parent.size_wh),
            "file_sha256": "a" * 64, "decoded_rgb_sha256": "b" * 64,
            "shape": [parent.size_wh[1], parent.size_wh[0], 3], "dtype": "uint8",
            "coordinate_transform": "identity_no_exif_transpose"}
    monkeypatch.setattr(reviewer, "load_inventory", lambda path: (parents, [{"sample": p.sample, "image_sha256": "a" * 64} for p in parents], {}))
    monkeypatch.setattr(reviewer, "smoke_parents", lambda p: p)  # Isolate counter/coverage policy.
    for name in ("status.json", "bank.npy", "selected_indices.npy"):
        (output / "raw/bank" / name).unlink()  # Metadata-only return, not fake full-bank bytes.
    with (output / "stage_times.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        row.update({"cuda_" + k: str(v) for k, v in zip(reviewer.CUDA_FIELDS, [4, 8, 4, 8])})
    with (output / "stage_times.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    state = reviewer._read(output / "status.json")
    state["model_execution_started"] = True
    write(output / "status.json", state)
    write(output / "PROTOCOL.json", protocol)
    write(output / "raw/status.json", raw)
    write(output / "resources.json", resource)
    refresh(output)
    result = reviewer.validate(output, root)
    assert result["execution_class"] == "REPORTED_CUDA_LIMITED_SMOKE" and result["cuda_execution_reported"]
    assert not result["independent_remote_execution_verified"] and not result["full_pilot_approved"]
    assert not result["bank_metadata_verified"] and result["payload_coverage"] == "PARTIAL_OR_METADATA_ONLY"
