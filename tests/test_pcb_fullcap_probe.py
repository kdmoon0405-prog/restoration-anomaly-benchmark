import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import check_pcb_fullcap_probe as cli
from sr_anomaly import pcb_fullcap_probe as probe
from sr_anomaly.bounded_bank import file_sha256


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root, reference = tmp_path/"code", tmp_path/"received"
    for name in probe.CODE:
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture source", encoding="utf-8")
    frozen_source = root/"src/frozen.py"
    frozen_source.write_text("fixture frozen model source", encoding="utf-8")
    geometry = root/probe.measured.runner.GEOMETRY/"PROTOCOL.json"
    geometry.parent.mkdir(parents=True, exist_ok=True)
    geometry.write_text(json.dumps({"code_sha256": {"src/frozen.py": file_sha256(frozen_source)}}), encoding="utf-8")
    for name in probe.REFERENCE_FILES:
        path = reference/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    (reference/"resources.json").write_text(json.dumps({"cuda_at_end": {
        "max_reserved_bytes_since_profiler_start": 123}}), encoding="utf-8")
    checkpoints = [tmp_path/"backbone.pth", tmp_path/"swinir.pth"]
    for index, path in enumerate(checkpoints):
        path.write_bytes(f"fake checkpoint{index}, never model weights".encode())
    monkeypatch.setattr(probe.models, "BACKBONE_SHA256", file_sha256(checkpoints[0]))
    monkeypatch.setattr(probe.models, "SWINIR_SHA256", file_sha256(checkpoints[1]))
    monkeypatch.setattr(probe.review, "validate", lambda *a: {
        "execution_class": "REPORTED_CUDA_LIMITED_SMOKE", "os_lifetime_peak_rss_bytes": 1024**2})
    monkeypatch.setattr(probe.memory, "available_ram", lambda: 64*1024**3)
    def source_git(args, **kwargs):
        if "status" in args:
            return ""
        if "-C" in args:
            return probe.models.SWINIR_COMMIT if "SwinIR" in str(args) else probe.models.PATCHCORE_COMMIT
        return "f"*40
    monkeypatch.setattr(probe.subprocess, "check_output", source_git)
    output, state = probe.prepare(root, reference, *checkpoints, run_id="fixture")
    assert state["status"] == "PREFLIGHT_PASS"
    return root, reference, checkpoints, output


class FakeAdapter:
    def __init__(self, *, bad=None):
        self.bank = None
        self.closed = False
        self.bad = bad
        self.bound_values = None
        self.predict_calls = 0

    def extract(self, *args):
        raise AssertionError("No training/embedding extraction is part of this resource probe")

    def bind_bank(self, values):
        assert values.dtype == np.float32 and not values.flags.writeable
        self.bank = values
        self.bound_values = values.copy()

    def predict(self, rgb):
        self.predict_calls += 1
        if self.bad == "raise":
            raise RuntimeError("fake prediction failed")
        dtype = np.float64 if self.bad == "dtype" else np.float32
        shape = (1, 1) if self.bad == "shape" else (224, 224)
        value = np.nan if self.bad == "nan" else float(rgb[0, 0, 0])
        return np.full(shape, value, dtype), 1.

    def close(self):
        self.closed = True
        self.bank = None


def run_fake(root, output, adapter):
    return probe.execute(output, root, factory=lambda *a: (adapter, lambda tile, variant: tile),
                         _fixture_shape=(7, 4))


def test_tiny_roundtrip_determinism_cleanup_and_no_runtime_imports(prepared):
    root, reference, checkpoints, output = prepared
    runtimes = {name: name in sys.modules for name in ("torch", "faiss")}
    adapter = FakeAdapter()
    state = run_fake(root, output, adapter)
    assert state["status"] == probe.FIXTURE_COMPLETE and adapter.closed and adapter.predict_calls == 6
    result = probe.memory.read_json(output/"resources.json")
    assert result["actual_shape"] == [7, 4] and result["payload_cleanup"]
    assert result["input_kind"] == "injected_fixture_NOT_GPU_evidence"
    for name in ("model_execution_started", "actual_fullcap_payload_observed", "actual_pcb_bank_created",
                 "full_bank_validated", "full_pilot_approved", "predictions_exported", "gt_callback_used"):
        assert result[name] is False
    assert result["metrics"] is None and len(result["query_checks"]) == 6
    assert result["phase_summary"]["bank_bind_CPU_scorer_index"]["call_count"] == 1
    assert result["phase_summary"]["detector_inference_including_CPU_FAISS"]["call_count"] == 6
    assert result["cuda_at_start"] is None and result["cuda_at_end"] is None
    assert not (output/"synthetic_bank_payload.npy").exists() and not (output/"raw").exists()
    assert file_sha256(output/"resources.json") == state["resources_sha256"]
    assert {name: name in sys.modules for name in runtimes} == runtimes
    again, _ = probe.prepare(root, reference, *checkpoints, run_id="again")
    second = FakeAdapter()
    run_fake(root, again, second)
    np.testing.assert_array_equal(adapter.bound_values, second.bound_values)
    assert result["synthetic_payload_sha256"] == probe.memory.read_json(again/"resources.json")["synthetic_payload_sha256"]


@pytest.mark.parametrize("bad", ["raise", "dtype", "shape", "nan"])
def test_failure_preserves_partial_payload_but_closes_owned_adapter(prepared, bad):
    root, _, _, output = prepared
    adapter = FakeAdapter(bad=bad)
    state = run_fake(root, output, adapter)
    result = probe.memory.read_json(output/"resources.json")
    assert state["status"] == "FAILED" and adapter.closed
    assert result["payload_retained"] and not result["payload_cleanup"]
    assert not result["full_bank_validated"] and result["metrics"] is None


@pytest.mark.parametrize("target", ["source", "frozen", "reference", "checkpoint", "status", "plan", "spec", "coverage", "approval"])
def test_drift_or_forged_protocol_refused_before_factory(prepared, target):
    root, reference, checkpoints, output = prepared
    if target == "source":
        (root/probe.CODE[0]).write_text("changed", encoding="utf-8")
    elif target == "frozen":
        (root/"src/frozen.py").write_text("changed", encoding="utf-8")
    elif target == "reference":
        (reference/"resources.json").write_text("changed", encoding="utf-8")
    elif target == "checkpoint":
        checkpoints[0].write_bytes(b"changed")
    elif target == "status":
        state = probe.memory.read_json(output/"status.json")
        state["status"] = "MEASURING"
        probe.memory.write_json(output/"status.json", state)
    else:
        protocol = probe.memory.read_json(output/"PROTOCOL.json")
        if target == "spec":
            protocol["spec"]["rows"] = 6
        elif target == "coverage":
            protocol["reference_sha256"].pop("resources.json")
        elif target == "approval":
            protocol["full_pilot_approved"] = True
        else:
            protocol["plan"]["payload_scenario_bytes"] = 1
        probe.memory.write_json(output/"PROTOCOL.json", protocol)
        state = probe.memory.read_json(output/"status.json")
        state["protocol_sha256"] = file_sha256(output/"PROTOCOL.json")
        probe.memory.write_json(output/"status.json", state)
    with pytest.raises(ValueError):
        run_fake(root, output, FakeAdapter())
    assert not (output/"synthetic_bank_payload.npy").exists()


def test_resource_shortage_blocks_before_any_payload_or_model(prepared, monkeypatch):
    root, reference, checkpoints, output = prepared
    monkeypatch.setattr(probe.memory, "available_ram", lambda: 0)
    blocked, state = probe.prepare(root, reference, *checkpoints, run_id="blocked")
    assert state["status"] == "BLOCKED_MEMORY" and any("BLOCKED_MEMORY" in b for b in state["blockers"])
    with pytest.raises(ValueError):
        run_fake(root, blocked, FakeAdapter())
    adapter = FakeAdapter()
    state = run_fake(root, output, adapter)
    assert state["status"] == "FAILED" and "BLOCKED_MEMORY" in state["error"]
    assert not (output/"synthetic_bank_payload.npy").exists() and not adapter.closed


def test_fresh_disk_shortage_and_live_cuda_failure_never_allocate(prepared, monkeypatch):
    root, _, _, output = prepared
    with monkeypatch.context() as disk:
        disk.setattr(probe.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))
        assert run_fake(root, output, FakeAdapter())["status"] == "FAILED"
    assert not (output/"synthetic_bank_payload.npy").exists()


def test_live_cuda_unavailable_never_calls_factory(prepared, monkeypatch):
    root, _, _, output = prepared
    def unavailable(*a):
        raise RuntimeError("CUDA is unavailable")
    monkeypatch.setattr(probe, "_cuda", unavailable)
    monkeypatch.setattr(probe.models, "create_models", lambda *a: pytest.fail("No factory before CUDA check"))
    state = probe.execute(output, root)
    assert state["status"] == "FAILED" and "CUDA is unavailable" in state["error"]
    assert not (output/"synthetic_bank_payload.npy").exists()


def test_existing_output_payload_and_reexecution_are_refused(prepared):
    root, reference, checkpoints, output = prepared
    with pytest.raises(FileExistsError):
        probe.prepare(root, reference, *checkpoints, run_id="fixture")
    payload = output/"synthetic_bank_payload.npy"
    payload.write_bytes(b"previous incomplete fixture, preserve")
    with pytest.raises(FileExistsError):
        run_fake(root, output, FakeAdapter())
    assert payload.read_bytes() == b"previous incomplete fixture, preserve"


@pytest.mark.parametrize("shape", [None, (262144, 1024), (True, 4), (0, 4), (7, 4, 3)])
def test_injected_fixtures_must_be_explicit_and_tiny(prepared, shape):
    root, _, _, output = prepared
    with pytest.raises(ValueError):
        probe.execute(output, root, factory=lambda *a: None, _fixture_shape=shape)
    assert not (output/"synthetic_bank_payload.npy").exists()


def test_fixed_plan_and_reference_kind_guards(prepared, monkeypatch):
    root, reference, checkpoints, _ = prepared
    plan = probe.resource_plan(1024**3)
    assert plan["bank_payload_bytes"] == 1024**3
    assert plan["required_available_ram_bytes"] == plan["payload_scenario_bytes"]+2*1024**3
    assert not plan["upper_bound"] and plan["estimates_not_measured"]
    for peak in (True, -1, 0, 1.5):
        with pytest.raises((ValueError, TypeError)):
            probe.resource_plan(peak)
    monkeypatch.setattr(probe.review, "validate", lambda *a: {"execution_class": "INJECTED_FIXTURE_NOT_GPU_EVIDENCE"})
    with pytest.raises(ValueError, match="reported-CUDA"):
        probe.prepare(root, reference, *checkpoints, run_id="bad-reference")


def test_cli_defaults_to_preflight_and_has_no_scope_or_shape_override(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(cli.probe, "prepare", lambda *a, **kw: (tmp_path, {"status": "PREFLIGHT_PASS"}))
    monkeypatch.setattr(cli.probe, "execute", lambda *a: seen.append(a) or {"status": probe.COMPLETE})
    assert cli.main(["--run-id", "example", "--smoke-run", str(tmp_path)]) == 0 and not seen
    assert cli.main(["--run-id", "example", "--smoke-run", str(tmp_path), "--execute"]) == 0 and len(seen) == 1
    with pytest.raises(SystemExit):
        cli.main(["--run-id", "example", "--smoke-run", str(tmp_path), "--scope", "full-pilot"])


def test_submodule_drift_and_fill_race_refused(prepared, monkeypatch, tmp_path):
    root, reference, checkpoints, _ = prepared
    monkeypatch.setattr(probe.subprocess, "check_output", lambda *a, **kw: "wrong-revision")
    with pytest.raises(ValueError, match="submodule"):
        probe.prepare(root, reference, *checkpoints, run_id="drift")
    payload = tmp_path/"unowned.npy"
    payload.write_bytes(b"preserve existing data")
    with pytest.raises(FileExistsError):
        probe._fill(payload, (7, 4))
    assert payload.read_bytes() == b"preserve existing data"


@pytest.mark.parametrize("failure", ["cleanup", "monitor"])
def test_cleanup_or_monitor_error_prevents_completion(prepared, monkeypatch, failure):
    root, _, _, output = prepared
    adapter = FakeAdapter()
    if failure == "cleanup":
        def bad_close():
            adapter.bank = None
            raise RuntimeError("close failed")
        adapter.close = bad_close
    else:
        original = probe.measured._OutputMonitor.finish
        def bad_finish(self):
            original(self)
            raise OSError("monitor failed")
        monkeypatch.setattr(probe.measured._OutputMonitor, "finish", bad_finish)
    assert run_fake(root, output, adapter)["status"] == "FAILED"
    result = probe.memory.read_json(output/"resources.json")
    assert result["payload_retained"] and not result["payload_cleanup"]


def test_complete_reexecution_and_nonowned_path_are_rejected(prepared, tmp_path):
    root, _, _, output = prepared
    run_fake(root, output, FakeAdapter())
    with pytest.raises(ValueError):
        run_fake(root, output, FakeAdapter())
    with pytest.raises(ValueError, match="owned"):
        run_fake(root, tmp_path/"unowned", FakeAdapter())


def test_cli_execute_never_bypasses_blocked_preflight(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.probe, "prepare", lambda *a, **kw: (tmp_path, {"status": "BLOCKED_MEMORY"}))
    monkeypatch.setattr(cli.probe, "execute", lambda *a: pytest.fail("Blocked CLI must not execute"))
    assert cli.main(["--run-id", "blocked", "--smoke-run", str(tmp_path), "--execute"]) == 2
