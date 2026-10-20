import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.check_tiled_cpu_integration import dummy_fixture
from scripts import profile_pcb_model_smoke as cli
from sr_anomaly import pcb_model_resources as resource
from sr_anomaly.bounded_bank import file_sha256


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    for name in resource.CODE:
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(name, encoding="utf-8")
    manifest = tmp_path / resource.runner.GEOMETRY / "MANIFEST.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("fixture-manifest", encoding="utf-8")
    reference = tmp_path / "fixture-reference.json"
    reference.write_text("fixture-reference", encoding="utf-8")
    scientific = tmp_path / resource.runner.PROTOCOL
    scientific.parent.mkdir(parents=True, exist_ok=True)
    scientific.write_text("fixture scientific protocol", encoding="utf-8")
    split = tmp_path / "data/split_csv/1cls.csv"
    split.parent.mkdir(parents=True)
    split.write_text("fixture split", encoding="utf-8")
    checkpoints = {}
    for name in ("backbone", "swinir"):
        checkpoint = tmp_path / (name + ".pth")
        checkpoint.write_bytes(b"synthetic checkpoint bytes, not model weights")
        checkpoints[name] = {"path": str(checkpoint), "sha256": file_sha256(checkpoint)}
    report = {"status": "PREFLIGHT_PASS", "scope": "model-smoke", "blockers": [],
              "source_worktree_dirty": True, "data_root": str(tmp_path / "data"),
              "execution": {"actual_device": "cpu"}, "memory": {"fit_vectors": 37632},
              "manifest_sha256": file_sha256(manifest),
              "references_sha256": {"fixture-reference.json": file_sha256(reference)},
              "code_sha256": {resource.CODE[0]: file_sha256(tmp_path / resource.CODE[0])},
              "protocol_sha256": file_sha256(scientific), "checkpoints": checkpoints,
              "official_csv_sha256": file_sha256(split)}
    monkeypatch.setattr(resource.runner, "preflight", lambda *a, **kw: report.copy())
    output, _ = resource.prepare(tmp_path, None, None, None, run_id="fixture")
    return tmp_path, output


class FixtureAdapter:
    def __init__(self, extractor):
        self.extract, self.bank, self.closed = extractor, None, False

    def bind_bank(self, bank):
        assert not bank.flags.writeable
        self.bank = bank

    def predict(self, tile):
        assert self.bank is not None
        return tile[..., 0].astype(np.float32), float(tile[0, 0, 1])

    def close(self):
        self.closed, self.bank = True, None


def fixture_execution(monkeypatch):
    parents, loader, extractor, _, _ = dummy_fixture()
    adapter = FixtureAdapter(extractor)
    def execute(report, root, data_root, output, *, factory, loader):
        measured, transform = factory(root, "cpu", None, None)
        try:
            return resource.runner.run_raw_smoke(parents, loader, measured, transform, output,
                provenance={"input_kind": "synthetic"}, patch_shape=(2, 2), dimension=4, capacity=17)
        finally:
            measured.close()
    monkeypatch.setattr(resource.runner, "execute_smoke", execute)
    return adapter, loader


def test_synthetic_roundtrip_existing_raw_smoke(prepared, monkeypatch):
    root, output = prepared
    adapter, loader = fixture_execution(monkeypatch)
    before_torch, before_faiss = "torch" in sys.modules, "faiss" in sys.modules
    state = resource.execute(output, root, factory=lambda *a: (adapter, lambda tile, variant: tile), loader=loader)
    assert state["status"] == "MODEL_SMOKE_RESOURCE_COMPLETE_NOT_FULL_APPROVAL"
    assert not state["model_execution_started"] and state["factory_call_started"] and adapter.closed
    measured = json.loads((output / "resources.json").read_text())
    assert measured["input_kind"] == "injected_fixture_NOT_real_model_evidence"
    assert measured["scope"] == {"expected_smoke_vectors": 37632, "full_bank_capacity_not_validated": 262144}
    assert not measured["full_bank_validated"] and not measured["full_pilot_approved"]
    assert not measured["gt_callback_used"] and measured["metrics"] is None
    assert measured["observed_feature_counts"]["observed_vectors"] == 32
    assert measured["phase_summary"]["model_factory"]["call_count"] == 1
    assert measured["phase_summary"]["bank_bind_CPU_scorer_index"]["call_count"] == 1
    assert measured["phase_summary"]["restoration_swinir_x4"]["call_count"] == 10
    assert measured["phase_summary"]["detector_inference_including_CPU_FAISS"]["call_count"] == 30
    assert measured["cuda_at_start"] is None and measured["cuda_at_end"] is None
    assert measured["process_memory"]["sample_count"] > 0
    assert state["resources_sha256"] == file_sha256(output / "resources.json")
    raw = resource.memory.read_json(output / "raw/status.json")
    parents = {p.sample: p for p in dummy_fixture()[0]}
    for row in raw["rows"]:
        np.testing.assert_array_equal(np.load(output / "raw" / row["file"], allow_pickle=False),
                                      loader(parents[row["sample"]])[..., 0].astype(np.float32))
    assert ("torch" in sys.modules) == before_torch and ("faiss" in sys.modules) == before_faiss
    with pytest.raises(RuntimeError, match="PREFLIGHT_PASS"):
        resource.execute(output, root)


def test_recorder_deterministic_time_sync_and_failure():
    ticks = iter([1., 3., 5., 8.])
    calls = []
    probe = lambda: {"rss_bytes": 10, "os_lifetime_peak_rss_bytes": 20}
    recorder = resource.Recorder(lambda: calls.append("sync"), clock=lambda: next(ticks), process_probe=probe)
    assert recorder.call("phase", lambda: 7) == 7
    def fail():
        raise ValueError("fixture")
    with pytest.raises(ValueError, match="fixture"):
        recorder.call("phase", fail)
    assert calls == ["sync"] * 4
    assert [r["elapsed_seconds"] for r in recorder.rows] == [2., 3.]
    assert [r["completed"] for r in recorder.rows] == [True, False]
    assert recorder.summary()["phase"] == {"call_count": 2, "completed_calls": 1,
        "sum_elapsed_seconds": 5., "min_elapsed_seconds": 2., "max_elapsed_seconds": 3.}


def test_cuda_helpers_are_injected_no_real_torch(monkeypatch):
    calls = []
    fake = SimpleNamespace(cuda=SimpleNamespace(
        synchronize=lambda device: calls.append(("sync", device)),
        reset_peak_memory_stats=lambda device: calls.append(("reset", device)),
        memory_allocated=lambda device: 1, memory_reserved=lambda device: 2,
        max_memory_allocated=lambda device: 3, max_memory_reserved=lambda device: 4))
    monkeypatch.setitem(sys.modules, "torch", fake)
    sync, snapshot = resource._cuda_tools("cpu")
    sync()
    assert snapshot() is None and not calls
    sync, snapshot = resource._cuda_tools("cuda")
    sync()
    assert calls == [("sync", "cuda"), ("reset", "cuda"), ("sync", "cuda")]
    assert snapshot()["max_reserved_bytes_since_profiler_start"] == 4
    with pytest.raises(ValueError, match="resolved"):
        resource._cuda_tools("auto")


@pytest.mark.parametrize("name", resource.CODE)
def test_changed_wrapper_sources_rejected_before_factory(prepared, name):
    root, output = prepared
    (root / name).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="source changed"):
        resource.execute(output, root, factory=lambda *a: pytest.fail("factory must not start"))
    assert not (output / "raw").exists()


@pytest.mark.parametrize("name", ["fixture-reference.json", resource.runner.GEOMETRY / "MANIFEST.json"])
def test_changed_frozen_reference_rejected_before_factory(prepared, name):
    root, output = prepared
    (root / name).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="metadata changed"):
        resource.execute(output, root, factory=lambda *a: pytest.fail("factory must not start"))


@pytest.mark.parametrize("name", ["backbone.pth", "swinir.pth", resource.runner.PROTOCOL,
                                  "data/split_csv/1cls.csv"])
def test_changed_checkpoint_protocol_split_rejected_before_cuda(prepared, monkeypatch, name):
    root, output = prepared
    (root / name).write_bytes(b"changed")
    monkeypatch.setattr(resource, "_cuda_tools", lambda *a: pytest.fail("CUDA setup must not start"))
    with pytest.raises(ValueError, match="changed after preflight"):
        resource.execute(output, root, factory=lambda *a: pytest.fail("factory must not start"))


@pytest.mark.parametrize("change", ["full_scope", "blocked", "vector_count", "protocol_hash", "approval"])
def test_invalid_protocol_rejected(prepared, change):
    root, output = prepared
    protocol = resource.memory.read_json(output / "PROTOCOL.json")
    if change == "full_scope":
        protocol["preflight"]["scope"] = "full-pilot"
    elif change == "blocked":
        protocol["preflight"]["blockers"] = ["fixture blocker"]
    elif change == "vector_count":
        protocol["preflight"]["memory"]["fit_vectors"] = 262144
    elif change == "approval":
        protocol["full_pilot_approved"] = True
    else:
        protocol["kind"] = "changed"
    resource.memory.write_json(output / "PROTOCOL.json", protocol)
    if change != "protocol_hash":
        state = resource.memory.read_json(output / "status.json")
        state["protocol_sha256"] = file_sha256(output / "PROTOCOL.json")
        resource.memory.write_json(output / "status.json", state)
    with pytest.raises(RuntimeError):
        resource.execute(output, root, factory=lambda *a: pytest.fail("factory must not start"))


def test_failure_preserves_resource_and_partial_raw(prepared, monkeypatch):
    root, output = prepared
    _, loader = fixture_execution(monkeypatch)
    def fail(*args):
        raise ValueError("intentional factory failure")
    with pytest.raises(ValueError, match="intentional factory failure"):
        resource.execute(output, root, factory=fail, loader=loader)
    state = resource.memory.read_json(output / "status.json")
    measured = resource.memory.read_json(output / "resources.json")
    assert state["status"] == "FAILED" and not measured["completed"]
    assert measured["phase_summary"]["model_factory"]["completed_calls"] == 0
    assert (output / "stage_times.csv").exists()


def test_monitor_failure_refuses_success(prepared, monkeypatch):
    root, output = prepared
    adapter, loader = fixture_execution(monkeypatch)
    original_finish = resource.memory.Monitor.finish
    def failed_finish(self):
        original_finish(self)
        raise OSError("fixture sampler error")
    monkeypatch.setattr(resource.memory.Monitor, "finish", failed_finish)
    with pytest.raises(RuntimeError, match="sampler error"):
        resource.execute(output, root, factory=lambda *a: (adapter, lambda t, v: t), loader=loader)
    assert resource.memory.read_json(output / "status.json")["status"] == "FAILED"


def test_predict_failure_preserves_failed_raw_bank_and_timing(prepared, monkeypatch):
    root, output = prepared
    adapter, loader = fixture_execution(monkeypatch)
    def fail(tile):
        raise ValueError("intentional predictor failure")
    adapter.predict = fail
    with pytest.raises(ValueError, match="intentional predictor failure"):
        resource.execute(output, root, factory=lambda *a: (adapter, lambda t, v: t), loader=loader)
    assert adapter.closed
    assert resource.memory.read_json(output / "raw/status.json")["status"] == "FAILED"
    assert (output / "raw/bank/bank.npy").is_file()
    measured = resource.memory.read_json(output / "resources.json")
    assert not measured["completed"]
    assert measured["phase_summary"]["detector_inference_including_CPU_FAISS"]["completed_calls"] == 0


@pytest.mark.parametrize("name", ["raw", "resources.json", "stage_times.csv"])
def test_existing_payload_refused(prepared, name):
    root, output = prepared
    (output / name).touch()
    with pytest.raises(FileExistsError, match="never overwritten"):
        resource.execute(output, root)


def test_prepare_is_preflight_only_and_never_overwrites(prepared):
    root, output = prepared
    assert not (output / "raw").exists()
    assert not resource.memory.read_json(output / "status.json")["model_execution_started"]
    with pytest.raises(FileExistsError):
        resource.prepare(root, None, None, None, run_id="fixture")


def test_failed_preflight_keeps_failure_state(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("missing metadata")
    monkeypatch.setattr(resource.runner, "preflight", fail)
    with pytest.raises(ValueError, match="missing metadata"):
        resource.prepare(tmp_path, None, None, None, run_id="failed")
    assert resource.memory.read_json(tmp_path / "outputs/pcb-model-resource-smoke/failed/status.json")["status"] == "FAILED_PREFLIGHT"


def test_default_loader_uses_hash_bound_rgb_not_gt(prepared, monkeypatch):
    root, output = prepared
    adapter, loader = fixture_execution(monkeypatch)
    from sr_anomaly import pcb_input_binding
    class Inputs:
        def __init__(self, source_root, data_root):
            assert source_root == root
            self.rgb_receipts = {}
        def rgb(self, parent):
            self.rgb_receipts[parent.sample] = {"synthetic": True}
            return loader(parent)
        def evaluation_mask(self, parent):
            pytest.fail("Model smoke must never request GT")
        def verify_references(self):
            self.rgb_receipts["verified_at_completion"] = True
    monkeypatch.setattr(pcb_input_binding, "FrozenPCBInputs", Inputs)
    resource.execute(output, root, factory=lambda *a: (adapter, lambda t, v: t))
    measured = resource.memory.read_json(output / "resources.json")
    assert len(measured["rgb_receipts"]) == 6 and not measured["gt_callback_used"]
    assert measured["rgb_receipts"]["verified_at_completion"]


def test_cli_defaults_to_preflight_and_rejects_full_scope(prepared, monkeypatch):
    root, output = prepared
    monkeypatch.setattr(cli, "ROOT", root)
    calls = []
    monkeypatch.setattr(resource, "prepare", lambda *a, **kw: (calls.append(kw) or output, {"status": "PREFLIGHT_PASS", "blockers": []}))
    monkeypatch.setattr(resource, "execute", lambda *a, **kw: pytest.fail("CLI default must not execute"))
    assert cli.main(["--run-id", "cli-preflight"]) == 0
    assert calls[0]["device"] == "auto"
    with pytest.raises(SystemExit):
        cli.main(["--run-id", "no-full", "--scope", "full-pilot", "--execute"])


def test_blocked_cli_does_not_execute_even_with_flag(prepared, monkeypatch):
    root, output = prepared
    monkeypatch.setattr(cli, "ROOT", root)
    monkeypatch.setattr(resource, "prepare", lambda *a, **kw: (output, {"status": "PREFLIGHT_BLOCKED", "blockers": ["fixture"]}))
    monkeypatch.setattr(resource, "execute", lambda *a, **kw: pytest.fail("Blocked preflight cannot execute"))
    assert cli.main(["--run-id", "blocked", "--execute"]) == 2
