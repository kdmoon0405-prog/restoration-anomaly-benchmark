"""Synthetic metadata only: CUDA labels below are never real GPU evidence."""
import copy
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from test_pcb_fullcap_probe import prepared as injected_prepared, run_fake, FakeAdapter
from scripts import review_pcb_fullcap_probe as cli
from sr_anomaly import pcb_fullcap_review as reviewer

probe = reviewer.probe


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(run, rows=None):
    path = run/"stage_times.csv"
    if rows is None:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def refresh(run):
    state = read(run/"status.json")
    state.update({k: reviewer.file_sha256(run/n) for n, k in
        (("PROTOCOL.json", "protocol_sha256"), ("resources.json", "resources_sha256"), ("stage_times.csv", "timings_sha256"))})
    write(run/"status.json", state)


@pytest.fixture(scope="module")
def source_template(tmp_path_factory):
    root = tmp_path_factory.mktemp("fullcap-review-source")
    for name in probe.CODE:
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source, never executed", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-qm", "Synthetic metadata fixture"], cwd=root, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    return root, commit


@pytest.fixture
def completed(tmp_path, monkeypatch, source_template):
    root, reference, run = (tmp_path/n for n in ("code", "reference", "returned"))
    template, commit = source_template
    shutil.copytree(template, root)
    def sources(path):
        return {n: reviewer.file_sha256(root/n) for n in probe.CODE}
    monkeypatch.setattr(probe, "_bound_sources", sources)
    for name in probe.REFERENCE_FILES:
        write(reference/name, {})
    runner = probe.measured.runner
    reference_names = [runner.GEOMETRY/"MANIFEST.json", runner.GEOMETRY/"PROTOCOL.json",
                       runner.BUDGET/"PROTOCOL.json", runner.BUDGET/"selection_plan.json"]
    write(reference/"PROTOCOL.json", {"preflight": {"code_sha256": {}},
        "wrapper_code_sha256": dict.fromkeys(probe.measured.CODE, "a"*64),
        "input_reference_sha256": {n.as_posix(): "a"*64 for n in reference_names}})
    write(reference/"resources.json", {"cuda_at_end": {"max_reserved_bytes_since_profiler_start": 8}})
    accepted = dict(execution_class="REPORTED_CUDA_LIMITED_SMOKE", os_lifetime_peak_rss_bytes=1024**2,
        payload_coverage="PARTIAL_OR_METADATA_ONLY", raw_file_hashes_verified=["bank/status.json"],
        raw_files_not_supplied=[f"predictions/{i:04d}.npy" for i in range(9)]+["bank/bank.npy", "bank/selected_indices.npy"])
    # Isolate reference integration; the unchanged limited checker has its own full contract tests.
    monkeypatch.setattr(reviewer.limited, "validate", lambda *args: copy.deepcopy(accepted))
    false = dict(actual_pcb_bank_created=False, full_bank_validated=False, full_pilot_approved=False, metrics=None)
    protocol = dict(false, kind=probe.KIND, spec=probe.SPEC.copy(), plan=probe.resource_plan(1024**2),
        source_sha256=sources(root), source_commit=commit, source_worktree_dirty=True,
        reference_sha256={n: reviewer.file_sha256(reference/n) for n in probe.REFERENCE_FILES},
        reference_run="Z:/UNSUPPLIED_REMOTE_REFERENCE_NEVER_OPEN", device="cuda", live_cuda_verified=False,
        input_kind="SYNTHETIC_BANK_AND_RGB_NOT_RESEARCH_PREDICTIONS", requested_queries_per_variant=2,
        checkpoints={n: {"path": "Z:/UNSUPPLIED_WEIGHTS_NEVER_OPEN.pth", "sha256": digest} for n, digest in
            (("backbone", probe.models.BACKBONE_SHA256), ("swinir", probe.models.SWINIR_SHA256))},
        available_ram_snapshot_bytes=64*1024**3, free_disk_snapshot_bytes=64*1024**3, blockers=[])
    stages = ["synthetic_payload_fill", "model_factory", "bank_bind_CPU_scorer_index"] + [s
        for _ in range(2) for variant in probe.models.VARIANTS for s in
        ("restoration_swinir_x4" if variant == "swinir_x4" else "preparation_"+variant,
         "detector_inference_including_CPU_FAISS")] + ["adapter_close"]
    rows = [dict(stage=s, perf_counter_start=100+i, perf_counter_end=100+i+.5, elapsed_seconds=.5,
        completed=True, rss_before_bytes=1000, rss_after_bytes=1500, os_lifetime_peak_rss_after_bytes=2000,
        **{"cuda_"+k: v for k, v in zip(reviewer.limited.CUDA_FIELDS, (4, 8, 4, 8))}) for i, s in enumerate(stages)]
    recorder = probe.measured.Recorder(lambda: None)
    recorder.rows = rows
    counters = lambda values: dict(zip(reviewer.limited.CUDA_FIELDS, values))
    resource = dict(false, kind=probe.KIND, status=probe.COMPLETE, actual_shape=[262144, 1024],
        input_kind=protocol["input_kind"], python_version="synthetic unit metadata", numpy_version="synthetic unit metadata",
        model_execution_started=True, actual_fullcap_payload_observed=True, predictions_exported=False,
        gt_callback_used=False, process_exit_self_verified=False, adapter_close_returned=True,
        payload_cleanup=True, payload_retained=False, payload_unchanged=True, synthetic_payload_sha256="a"*64, error=None,
        perf_counter_start=100., perf_counter_end=117., elapsed_seconds=17., phase_summary=recorder.summary(),
        query_checks=[dict(tile=i, variant=v, finite=True, detector_seconds=.5) for i in range(2) for v in probe.models.VARIANTS],
        process_memory=dict(baseline_rss_bytes=1000, sampled_peak_rss_bytes=2500, os_process_lifetime_peak_rss_bytes=3000,
            sample_count=4, sampling_interval_seconds=.1, measurement_method="unit metadata, not OS measurement",
            system_available_min_observed_bytes=10000, sampled_workspace_disk_max_bytes=2000, sampled_output_disk_max_bytes=2000),
        cuda_device=dict(gpu_name="synthetic CUDA label, no actual device", torch_version="fixture", cuda_runtime="fixture",
                         free_bytes=64, total_bytes=128, previous_peak_is_only_a_floor=True),
        cuda_at_start=counters((0, 0, 0, 0)), cuda_at_end=counters((4, 8, 4, 8)),
        drive_free_bytes_at_start=2*1024**3, drive_free_bytes_at_end=2*1024**3+1,
        output_payload_before_cleanup_bytes=1024**3+512, drive_delta_is_not_exclusive_output_size=True)
    write(run/"PROTOCOL.json", protocol)
    write(run/"resources.json", resource)
    write(run/"status.json", dict(false, kind=probe.KIND, status=probe.COMPLETE, blockers=[],
        payload_allocation_started=True, model_factory_call_started=True, model_execution_started=True))
    csv_rows(run, rows)
    refresh(run)
    return root, reference, run


def test_metadata_consistency_not_independent_gpu_or_payload_evidence(completed, tmp_path):
    root, reference, run = completed
    result = reviewer.review(run, tmp_path/"review", root, reference)
    assert result["status"] == reviewer.PASS and result["source_worktree_dirty"] is True
    assert result["source_commit"] != result["checker_source_commit"]
    assert not result["independent_remote_execution_verified"] and not result["full_pilot_approved"]
    assert not result["synthetic_payload_file_hash_independently_verified"]
    assert not result["raw_array_contents_independently_checked"]
    assert not result["checkpoint_file_hashes_independently_verified"]
    assert len(result["reference_raw_files_not_supplied"]) == 11
    assert result["reference_raw_file_hashes_verified"] == ["bank/status.json"]
    assert "status.json" not in result["input_file_hashes_verified"]
    assert result["input_files_sha256"]["status.json"] == reviewer.file_sha256(run/"status.json")
    assert result["drive_free_change_bytes"] == 1  # Can be positive despite output writes.
    assert result["query_finite_checks_reported"] == 6
    assert (tmp_path/"review/REVIEW.md").is_file()
    assert not list(run.rglob("*.npy"))


@pytest.mark.parametrize("field,value", [
    ("actual_shape", [7, 4]), ("gt_callback_used", True), ("payload_cleanup", False),
    ("payload_retained", True), ("payload_unchanged", False), ("actual_fullcap_payload_observed", False),
    ("full_pilot_approved", True), ("actual_pcb_bank_created", True), ("full_bank_validated", True),
    ("metrics", {}), ("process_exit_self_verified", True), ("predictions_exported", True),
    ("model_execution_started", False), ("adapter_close_returned", False), ("synthetic_payload_sha256", "bad"),
    ("output_payload_before_cleanup_bytes", 1), ("drive_free_bytes_at_end", -1), ("elapsed_seconds", -1),
])
def test_rehashed_resource_contract_tampering(completed, field, value):
    root, reference, run = completed
    resource = read(run/"resources.json")
    resource[field] = value
    write(run/"resources.json", resource)
    refresh(run)
    with pytest.raises((ValueError, KeyError)):
        reviewer.validate(run, root, reference)


@pytest.mark.parametrize("field,value", [("spec", {}), ("source_commit", "e"*40), ("source_worktree_dirty", "false"),
    ("source_sha256", {}), ("reference_sha256", {}), ("plan", {}), ("blockers", ["blocked"])])
def test_rehashed_protocol_tampering(completed, field, value):
    root, reference, run = completed
    protocol = read(run/"PROTOCOL.json")
    protocol[field] = value
    write(run/"PROTOCOL.json", protocol)
    refresh(run)
    with pytest.raises((ValueError, KeyError, subprocess.SubprocessError)):
        reviewer.validate(run, root, reference)


@pytest.mark.parametrize("change", ["missing", "duplicate", "wrong_variant", "nan", "duration"])
def test_query_inventory_and_duration(completed, change):
    root, reference, run = completed
    resource = read(run/"resources.json")
    queries = resource["query_checks"]
    if change == "missing":
        queries.pop()
    elif change == "duplicate":
        queries[1] = queries[0].copy()
    elif change == "wrong_variant":
        queries[0]["variant"] = "other"
    elif change == "nan":
        queries[0]["detector_seconds"] = float("nan")
    else:
        queries[0]["detector_seconds"] = .4
    write(run/"resources.json", resource)
    refresh(run)
    with pytest.raises(ValueError):
        reviewer.validate(run, root, reference)


@pytest.mark.parametrize("change", ["overlap", "nan", "negative", "failed", "missing", "order", "rss", "cuda"])
def test_timing_mutations(completed, change):
    root, reference, run = completed
    rows = csv_rows(run)
    if change == "missing":
        rows.pop()
    elif change == "order":
        rows[0]["stage"], rows[1]["stage"] = rows[1]["stage"], rows[0]["stage"]
    else:
        field, value = {"overlap": ("perf_counter_start", "100"), "nan": ("elapsed_seconds", "nan"),
            "negative": ("elapsed_seconds", "-1"), "failed": ("completed", "False"),
            "rss": ("os_lifetime_peak_rss_after_bytes", "1"), "cuda": ("cuda_reserved_bytes", "1")}[change]
        rows[1][field] = value
    csv_rows(run, rows)
    refresh(run)
    with pytest.raises(ValueError):
        reviewer.validate(run, root, reference)


@pytest.mark.parametrize("change", ["summary", "rss", "samples", "available", "cuda", "floor", "checkpoint"])
def test_resource_counter_and_summary_domains(completed, change):
    root, reference, run = completed
    r = read(run/"resources.json")
    if change == "summary":
        r["phase_summary"]["model_factory"]["sum_elapsed_seconds"] = 1
    elif change == "rss":
        r["process_memory"]["sampled_peak_rss_bytes"] = 4000
    elif change == "samples":
        r["process_memory"]["sample_count"] = 1
    elif change == "available":
        r["process_memory"]["system_available_min_observed_bytes"] = -1
    elif change == "cuda":
        r["cuda_at_end"]["max_allocated_bytes_since_profiler_start"] = 1
    elif change == "floor":
        r["cuda_device"]["free_bytes"] = 1
    else:
        p = read(run/"PROTOCOL.json")
        p["checkpoints"]["swinir"]["sha256"] = "a"*64
        write(run/"PROTOCOL.json", p)
    write(run/"resources.json", r)
    refresh(run)
    with pytest.raises(ValueError):
        reviewer.validate(run, root, reference)


@pytest.mark.parametrize("status", ["PREFLIGHT_PASS", "FAILED", "MEASURING"])
def test_noncompletion_not_accepted(completed, tmp_path, status):
    root, reference, run = completed
    state = read(run/"status.json")
    state["status"] = status
    write(run/"status.json", state)
    result = reviewer.review(run, tmp_path/"review", root, reference)
    assert result["status"] == reviewer.REJECT and not result["cuda_execution_reported"]


@pytest.mark.parametrize("fixture", [True, False])
def test_cpu_or_injected_never_passes_as_cuda(completed, tmp_path, fixture):
    root, reference, run = completed
    p, s, r = [read(run/n) for n in reviewer.FILES[:3]]
    if fixture:
        r.update(input_kind="injected_fixture_NOT_GPU_evidence", actual_shape=[7, 4])
        s["status"] = r["status"] = probe.FIXTURE_COMPLETE
    else:
        p["device"] = "cpu"
    for name, value in zip(reviewer.FILES[:3], (p, s, r)):
        write(run/name, value)
    refresh(run)
    result = reviewer.review(run, tmp_path/"review", root, reference)
    assert result["status"] == reviewer.REJECT
    assert "NOT_GPU_EVIDENCE" in result["execution_class"]


def test_missing_reference_never_follows_recorded_remote_path(completed, tmp_path):
    root, reference, run = completed
    p = read(run/"PROTOCOL.json")
    p["reference_run"] = str(reference)  # Even an existing path is not implicitly trusted.
    write(run/"PROTOCOL.json", p)
    refresh(run)
    result = reviewer.review(run, tmp_path/"review", root)
    assert result["status"] == reviewer.REJECT and "Explicit --reference-run" in result["error"]


def test_cleanup_claim_with_present_payload_rejected(completed):
    root, reference, run = completed
    (run/"synthetic_bank_payload.npy").write_bytes(b"tiny contradictory payload, no array allocation")
    with pytest.raises(ValueError, match="still present"):
        reviewer.validate(run, root, reference)


@pytest.mark.parametrize("name", reviewer.FILES)
def test_missing_or_altered_artifact(completed, tmp_path, name):
    root, reference, run = completed
    (run/name).unlink()
    result = reviewer.review(run, tmp_path/"review", root, reference)
    assert result["status"] == reviewer.REJECT


def test_reference_hash_and_untrusted_source_paths(completed):
    root, reference, run = completed
    p = read(reference/"PROTOCOL.json")
    p["preflight"]["code_sha256"]["data/external/VisA/never-open.png"] = "a"*64
    write(reference/"PROTOCOL.json", p)
    protocol = read(run/"PROTOCOL.json")
    protocol["reference_sha256"]["PROTOCOL.json"] = reviewer.file_sha256(reference/"PROTOCOL.json")
    write(run/"PROTOCOL.json", protocol)
    refresh(run)
    with pytest.raises(ValueError, match="Unsafe reference source"):
        reviewer.validate(run, root, reference)


@pytest.mark.parametrize("name", ["PROTOCOL.json", "resources.json", "stage_times.csv"])
def test_altered_artifact_without_refreshed_hash_rejected(completed, name):
    root, reference, run = completed
    with (run/name).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        reviewer.validate(run, root, reference)


def test_reference_bytes_missing_or_changed(completed, tmp_path):
    root, reference, run = completed
    with (reference/"raw/status.json").open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="Reference hash mismatch"):
        reviewer.validate(run, root, reference)
    result = reviewer.review(run, tmp_path/"missing-reference", root, tmp_path/"absent-reference")
    assert result["status"] == reviewer.REJECT


@pytest.mark.parametrize("change", ["kind", "status_digest", "duplicate_json", "list_json", "reference_path", "float_overflow"])
def test_malformed_or_misbound_metadata(completed, tmp_path, change):
    root, reference, run = completed
    p = read(run/"PROTOCOL.json")
    if change == "kind":
        p["kind"] = probe.measured.KIND
    elif change == "reference_path":
        ref = read(reference/"PROTOCOL.json")
        ref["input_reference_sha256"]["../private-checkpoint.pth"] = "a"*64
        write(reference/"PROTOCOL.json", ref)
        p["reference_sha256"]["PROTOCOL.json"] = reviewer.file_sha256(reference/"PROTOCOL.json")
    elif change == "float_overflow":
        resource = read(run/"resources.json")
        resource["process_memory"]["unexpected"] = float("inf")
        (run/"resources.json").write_text(json.dumps(resource).replace("Infinity", "1e999"), encoding="utf-8")
    if change == "duplicate_json":
        (run/"PROTOCOL.json").write_text('{"kind":"x","kind":"y"}', encoding="utf-8")
    elif change == "list_json":
        write(run/"PROTOCOL.json", [])
    else:
        write(run/"PROTOCOL.json", p)
    refresh(run)
    if change == "status_digest":
        state = read(run/"status.json")
        state["protocol_sha256"] = "0"*64
        write(run/"status.json", state)
    result = reviewer.review(run, tmp_path/"review", root, reference)
    assert result["status"] == reviewer.REJECT


def test_snapshot_not_misreported_as_exact_guard_input(completed):
    root, reference, run = completed
    p = read(run/"PROTOCOL.json")
    p["available_ram_snapshot_bytes"] = p["plan"]["required_available_ram_bytes"]-1
    write(run/"PROTOCOL.json", p)
    refresh(run)
    result = reviewer.validate(run, root, reference)
    assert result["status"] == reviewer.PASS
    assert result["available_ram_snapshot_bytes"] == p["available_ram_snapshot_bytes"]


def test_source_byte_or_commit_drift(completed):
    root, reference, run = completed
    (root/probe.CODE[0]).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="source hash"):
        reviewer.validate(run, root, reference)
    protocol = read(run/"PROTOCOL.json")
    protocol["source_sha256"][probe.CODE[0]] = reviewer.file_sha256(root/probe.CODE[0])
    write(run/"PROTOCOL.json", protocol)
    refresh(run)
    with pytest.raises(ValueError, match="commit differs"):
        reviewer.validate(run, root, reference)


def test_cli_outputs_and_no_overwrite_or_input_overlap(completed, tmp_path, monkeypatch):
    root, reference, run = completed
    monkeypatch.setattr(cli, "ROOT", root)
    output = tmp_path/"review"
    args = ["--run", str(run), "--output", str(output), "--reference-run", str(reference)]
    assert cli.main(args) == 0
    with pytest.raises(FileExistsError):
        cli.main(args)
    for unsafe in (run/"review", reference/"review", tmp_path):
        with pytest.raises(ValueError, match="disjoint"):
            reviewer.review(run, unsafe, root, reference)
    assert cli.main(["--run", str(run), "--output", str(tmp_path/"missing-reference")]) == 2


def test_actual_tiny_producer_fixture_never_accepted_as_cuda(injected_prepared, tmp_path):
    root, _, _, run = injected_prepared
    run_fake(root, run, FakeAdapter())  # 7x4 floats and a fake adapter only.
    result = reviewer.review(run, tmp_path/"fixture-review", root)
    assert result["execution_class"] == "INJECTED_FIXTURE_NOT_GPU_EVIDENCE"
    assert result["status"] == reviewer.REJECT and not result["cuda_execution_reported"]


def test_import_guard_in_fresh_process(completed, tmp_path):
    source, reference, run = completed
    root = Path(__file__).resolve().parents[1]
    code = '''import sys, importlib.abc, runpy
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch','faiss','torchvision','timm','patchcore'}:
            raise AssertionError('Forbidden runtime import: '+fullname)
sys.meta_path.insert(0,Deny())
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from sr_anomaly import pcb_fullcap_review as r
source, reference, run, out = map(Path,sys.argv[1:])
r.probe._bound_sources=lambda p:{n:r.file_sha256(source/n) for n in r.probe.CODE}
r.limited.validate=lambda *a:dict(execution_class='REPORTED_CUDA_LIMITED_SMOKE',os_lifetime_peak_rss_bytes=1024**2,
    payload_coverage='PARTIAL_OR_METADATA_ONLY',raw_file_hashes_verified=[],raw_files_not_supplied=['fixture.npy'])
result=r.review(run,out,source,reference)
assert result['status']==r.PASS and not result['independent_remote_execution_verified']
sys.argv=['review_pcb_fullcap_probe.py','--help']
runpy.run_path('scripts/review_pcb_fullcap_probe.py',run_name='__main__')
'''
    result = subprocess.run([sys.executable, "-c", code, str(source), str(reference), str(run), str(tmp_path/"import-guard-review")],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "--reference-run" in result.stdout
