"""Tiny injected fit lifecycle and static preflight; never real models or full arrays."""
import copy
import gc
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import weakref

import numpy as np
import pytest

from scripts import run_pcb_fit_bank as cli
from sr_anomaly import bounded_bank as bank
from sr_anomaly import pcb_fit_bank as fit
from sr_anomaly.tiled_cpu_pipeline import Parent


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root, data = tmp_path/"code", tmp_path/"data"
    root.mkdir()
    data.mkdir()
    parents = (Parent("a", "fit", 0, (224,224)), Parent("b", "fit", 0, (224,224)))
    for p in parents:
        (data/p.sample).write_bytes(p.sample.encode())
    expected = {p.sample: bank.file_sha256(data/p.sample) for p in parents}
    class Inputs:
        def __init__(self, *args):
            self.parents = parents+(Parent("no-cal", "calibration", 0, (224,224)),
                                    Parent("no-test", "test", 1, (224,224)))
            self.geometry_id = "fixture_geometry"
            self.data_root = data
            self.official_sha256 = "0"*64
            self.rgb_receipts = {}

        def _row(self, parent):
            assert parent in parents, "cal/test metadata cannot enter fit hash path"
            return {"image_sha256": expected[parent.sample]}

        def rgb(self, parent):
            assert parent in parents, "cal/test RGB cannot enter fit callback"
            self.rgb_receipts[parent.sample] = {"shape": [224,224,3]}
            return np.full((224,224,3), ord(parent.sample), np.uint8)

        def evaluation_mask(self, *args):
            pytest.fail("GT must never be requested")

        def verify_references(self):
            pass

    monkeypatch.setattr(fit.binding, "FrozenPCBInputs", Inputs)
    monkeypatch.setattr(fit, "_inventory", lambda *a: (parents, "a"*64))
    source = root/"bound-source.py"
    source.write_text("frozen fixture source", encoding="utf-8")
    monkeypatch.setattr(fit, "_sources", lambda r: {"bound-source.py": bank.file_sha256(source)})
    ref = Path("reference.json")
    (root/ref).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(fit, "REFERENCES", (ref,))
    checkpoints = [tmp_path/"backbone.pth", tmp_path/"swinir.pth"]
    for p in checkpoints:
        p.write_bytes(p.name.encode())
    monkeypatch.setattr(fit.models, "BACKBONE_SHA256", bank.file_sha256(checkpoints[0]))
    monkeypatch.setattr(fit.models, "SWINIR_SHA256", bank.file_sha256(checkpoints[1]))
    monkeypatch.setattr(fit, "_git", lambda *a: "f"*40 if "rev-parse" in a else "")
    monkeypatch.setattr(fit.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(fit.runner, "available_ram", lambda: 64*1024**3)
    monkeypatch.setattr(fit.memory, "available_ram", lambda: 64*1024**3)
    monkeypatch.setattr(fit.shutil, "disk_usage", lambda p: SimpleNamespace(free=64*1024**3))
    output, state = fit.prepare(root, data, *checkpoints, run_id="tiny")
    assert state["status"] == "PREFLIGHT_PASS"
    settings = dict(total_vectors=2, dimension=4, capacity=1, seed=11, max_chunk_vectors=8192)
    refs = []
    class Adapter:
        def __init__(self):
            self.closed = False

        def extract(self, rgb):
            return np.repeat(rgb[:, :1, :1, :1].astype(np.float32), 4, axis=3)

        def bind_bank(self, *args):
            pytest.fail("No scorer/index binding in fit-only execution")

        def predict(self, *args):
            pytest.fail("No prediction in fit-only execution")

        def close(self):
            self.closed = True

    def factory(*args):
        adapter = Adapter()
        refs.append(weakref.ref(adapter))
        def transform(*args):
            pytest.fail("No restoration/degradation in fit-only execution")
        return adapter, transform
    return SimpleNamespace(root=root, data=data, output=output, state=state, parents=parents,
        source=source, ref=root/ref, checkpoints=checkpoints, settings=settings,
        injection={"settings": settings, "patch_shape": (1,1)}, factory=factory, refs=refs, Adapter=Adapter)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_tiny_fit_end_to_end_and_reuse_contract(setup):
    x = setup
    state = fit.execute(x.output, x.root, factory=x.factory, _fixture=x.injection)
    assert state["status"] == fit.FIXTURE_COMPLETE
    assert not state["actual_pcb_bank_created"] and not state["fit_bank_integrity_validated"]
    values, indices, meta = bank.load_complete_bank(x.output/"bank")
    try:
        _, expected = bank.selection_plan(**x.settings)
        np.testing.assert_array_equal(indices, expected)
        np.testing.assert_array_equal(values, np.full((1,4), 97+int(expected[0]), np.float32))
        assert meta["progress"]["observed_vectors"] == meta["progress"]["validated_vectors"] == 2
        assert meta["progress"]["stored_vectors"] == 1
        assert not values.flags.writeable
    finally:
        values._mmap.close()
        indices._mmap.close()
    resources = read(x.output/"resources.json")
    assert resources["adapter_close_returned"] and resources["references_released"]
    assert resources["actual_device"] == "cpu" and not resources["cuda_available"]
    assert not resources["gt_callback_used"] and resources["metrics"] is None
    assert not resources["full_bank_validated"] and not resources["full_pilot_approved"]
    assert resources["phase_summary"]["feature_extraction"]["call_count"] == 1
    assert resources["phase_summary"]["adapter_close"]["call_count"] == 1
    assert len(read(x.output/"fit_rgb_receipts.json")) == 2
    assert read(x.output/"fit_progress.json")["consumed_vectors"] == 2
    for file, key in (("resources.json", "resources_sha256"), ("stage_times.csv", "timings_sha256")):
        assert bank.file_sha256(x.output/file) == state[key]
    gc.collect()
    assert all(r() is None for r in x.refs)
    with pytest.raises(ValueError, match="preflight"):
        fit.execute(x.output, x.root, factory=x.factory, _fixture=x.injection)


@pytest.mark.parametrize("target", ["source", "ref", "checkpoint", "rgb", "protocol", "status", "spec", "order", "gate"])
def test_post_preflight_changes_rejected_before_factory(setup, target):
    x = setup
    if target in ("source", "ref", "checkpoint", "rgb"):
        path = {"source": x.source, "ref": x.ref, "checkpoint": x.checkpoints[0], "rgb": x.data/"a"}[target]
        path.write_bytes(b"changed")
    elif target in ("status", "gate"):
        value = read(x.output/"status.json")
        if target == "status":
            value["status"] = "FAILED"
        else:
            value["full_pilot_approved"] = True
        fit.memory.write_json(x.output/"status.json", value)
    else:
        value = read(x.output/"PROTOCOL.json")
        if target == "spec":
            value["spec"]["capacity"] = 1
        elif target == "order":
            value["fit_parents"].reverse()
        else:
            value["source_commit"] = "0"*40
        fit.memory.write_json(x.output/"PROTOCOL.json", value)
        if target in ("spec", "order"):
            state = read(x.output/"status.json")
            state["protocol_sha256"] = bank.file_sha256(x.output/"PROTOCOL.json")
            fit.memory.write_json(x.output/"status.json", state)
    with pytest.raises(ValueError):
        fit.execute(x.output, x.root, factory=x.factory, _fixture=x.injection)
    assert not x.refs and not (x.output/"bank").exists()


@pytest.mark.parametrize("name", ["bank", "resources.json", "stage_times.csv", "fit_progress.json"])
def test_existing_payload_rejected(setup, name):
    (setup.output/name).touch()
    with pytest.raises(FileExistsError):
        fit.execute(setup.output, setup.root, factory=setup.factory, _fixture=setup.injection)
    assert not setup.refs


def test_preflight_output_never_overwritten_and_paths_guarded(setup):
    x = setup
    with pytest.raises(FileExistsError):
        fit.prepare(x.root, x.data, *x.checkpoints, run_id="tiny")
    with pytest.raises(ValueError):
        fit.prepare(x.root, x.data, *x.checkpoints, run_id="../bad")
    with pytest.raises(ValueError, match="disjoint"):
        fit.prepare(x.root, x.root, *x.checkpoints, run_id="overlap")


@pytest.mark.parametrize("failure", ["ram", "disk"])
def test_fresh_resource_guard_and_blocked_preflight(setup, monkeypatch, failure):
    x = setup
    if failure == "ram":
        monkeypatch.setattr(fit.memory, "available_ram", lambda: 1)
    else:
        monkeypatch.setattr(fit.shutil, "disk_usage", lambda p: SimpleNamespace(free=1))
    with pytest.raises((MemoryError, OSError)):
        fit.execute(x.output, x.root, factory=x.factory, _fixture=x.injection)
    assert read(x.output/"status.json")["status"] == ("BLOCKED_MEMORY" if failure == "ram" else "BLOCKED_DISK")
    assert not x.refs and not (x.output/"bank").exists()
    output, state = fit.prepare(x.root, x.data, *x.checkpoints, run_id="blocked")
    assert state["status"] == "PREFLIGHT_BLOCKED" and state["blockers"]
    assert not (output/"bank").exists()


@pytest.mark.parametrize("mode", ["nan", "dtype", "shape", "close", "extract"])
def test_adapter_failures_preserve_failed_evidence(setup, mode):
    x = setup
    class Broken(x.Adapter):
        def extract(self, rgb):
            if mode == "extract":
                raise RuntimeError("fake extraction failed")
            values = super().extract(rgb)
            if mode == "nan":
                values[0,0,0,0] = np.nan
            elif mode == "dtype":
                values = values.astype(np.float64)
            elif mode == "shape":
                values = values[:, :, :, :3]
            return values

        def close(self):
            super().close()
            if mode == "close":
                raise RuntimeError("fake cleanup failed")
    with pytest.raises((ValueError, RuntimeError)):
        fit.execute(x.output, x.root, factory=lambda *a: (Broken(), None), _fixture=x.injection)
    assert read(x.output/"status.json")["status"] == "FAILED"
    if mode != "close":
        assert read(x.output/"bank/status.json")["status"] == "FAILED"
    assert not read(x.output/"resources.json")["full_pilot_approved"]


@pytest.mark.parametrize("vectors", [1,3])
def test_short_and_overlong_stream_are_not_complete(setup, vectors):
    x = setup
    injection = copy.deepcopy(x.injection)
    injection["settings"]["total_vectors"] = vectors
    with pytest.raises(ValueError, match="stream"):
        fit.execute(x.output, x.root, factory=x.factory, _fixture=injection)
    assert read(x.output/"bank/status.json")["status"] == "FAILED"


def test_fixture_allocation_guard_and_no_implicit_injection(setup):
    x = setup
    with pytest.raises(ValueError, match="tiny"):
        fit.execute(x.output, x.root, factory=x.factory)
    invalid = copy.deepcopy(x.injection)
    invalid["settings"]["total_vectors"] = 1000000
    with pytest.raises(ValueError, match="budget"):
        fit.execute(x.output, x.root, factory=x.factory, _fixture=invalid)
    assert not x.refs


def test_no_cuda_fails_before_models_and_stores_failure(setup, monkeypatch):
    x = setup
    def unavailable():
        raise RuntimeError("CUDA required; CPU fallback forbidden")
    monkeypatch.setattr(fit, "_cuda", unavailable)
    monkeypatch.setattr(fit.models, "create_models", lambda *a: pytest.fail("model created on CPU"))
    with pytest.raises(RuntimeError, match="CUDA required"):
        fit.execute(x.output, x.root)
    state = read(x.output/"status.json")
    assert state["status"] == "FAILED" and not state["model_execution_started"]


def test_cuda_helper_checks_availability_without_cpu_fallback(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    with pytest.raises(RuntimeError, match="CUDA required"):
        fit._cuda()


def test_cuda_metadata_and_synchronization_helper(monkeypatch):
    sync, snapshot = lambda: None, lambda: {"allocated_bytes": 1}
    monkeypatch.setattr(fit.measured, "_cuda_tools", lambda device: (sync, snapshot))
    fake = SimpleNamespace(__version__="fixture-not-GPU-evidence", version=SimpleNamespace(cuda="fixture"),
        cuda=SimpleNamespace(is_available=lambda: True, current_device=lambda: 2,
                             get_device_name=lambda index: "fixture-gpu-"+str(index)))
    monkeypatch.setitem(sys.modules, "torch", fake)
    a,b,device = fit._cuda()
    assert a is sync and b is snapshot
    assert device["actual_device"] == "cuda" and device["cuda_available"]
    assert device["gpu_name"] == "fixture-gpu-2"


@pytest.mark.parametrize("field", ["index", "nonfinite"])
def test_saved_bank_tamper_rejected_by_integrity_check(setup, field):
    x = setup
    fit.execute(x.output, x.root, factory=x.factory, _fixture=x.injection)
    metadata = read(x.output/"bank/status.json")
    path = x.output/"bank"/("selected_indices.npy" if field == "index" else "bank.npy")
    values = np.load(path, allow_pickle=False)
    values.flat[0] = 100 if field == "index" else np.nan
    with path.open("wb") as stream:
        np.save(stream, values, allow_pickle=False)
    if field == "nonfinite":
        metadata["artifact_sha256"]["bank.npy"] = bank.file_sha256(path)
        fit.memory.write_json(x.output/"bank/status.json", metadata)
    with pytest.raises(ValueError):
        fit._verify_bank(x.output, x.settings, metadata["selection_indices_sha256"])


def test_import_and_static_preflight_deny_runtime_in_fresh_process(tmp_path):
    # Real frozen metadata plus injected file receipts: no dataset/model file required.
    root = Path(__file__).resolve().parents[1]
    code = r'''
import importlib.abc, sys
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch','torchvision','faiss','timm','patchcore'}:
            raise AssertionError('Runtime import: '+fullname)
sys.meta_path.insert(0,Deny())
sys.path.insert(0,str(__import__('pathlib').Path(sys.argv[1])/'src'))
from sr_anomaly import pcb_fit_bank as f
from types import SimpleNamespace
from pathlib import Path
root=Path(sys.argv[1])
parents,_,manifest=f.runner.load_inventory(root/f.runner.GEOMETRY)
inputs=SimpleNamespace(parents=parents,geometry_id=manifest['geometry_id'],official_sha256='0'*64)
parents,selection=f._inventory(root,inputs)
assert len(parents)==721 and selection=='480f53ec4fbe355a3a5948e6a895dfdd63058eb903b8e108613a8e3a63afb402'
f._sources=lambda r:{'fixture-source':'0'*64}
f.binding.FrozenPCBInputs=lambda *a:inputs
f._fit_hashes=lambda *a:{}
f._checkpoints=lambda *a:{}
f.importlib.util.find_spec=lambda name:object()
f._guard=lambda *a:None
output,state=f.prepare(root,Path(sys.argv[2]),Path(sys.argv[2])/'backbone',Path(sys.argv[2])/'swinir',run_id=sys.argv[3])
assert state['status']=='PREFLIGHT_PASS' and not (output/'bank').exists()
'''
    import uuid
    run_id = "pytest-static-import-"+uuid.uuid4().hex
    result = subprocess.run([sys.executable, "-c", code, str(root), str(tmp_path), run_id],
        capture_output=True, text=True, cwd=root)
    assert result.returncode == 0, result.stderr[-1800:]


@pytest.mark.parametrize("drift", ["source", "revision"])
def test_frozen_source_and_submodule_revision_guard_without_vendored_files(tmp_path, monkeypatch, drift):
    source = tmp_path/"source.py"
    source.write_bytes(b"fixture source")
    for directory in (fit.runner.GEOMETRY, fit.runner.BUDGET):
        path = tmp_path/directory
        path.mkdir(parents=True, exist_ok=True)
        (path/"PROTOCOL.json").write_text(json.dumps({"code_sha256": {"source.py": bank.file_sha256(source)}}))
    monkeypatch.setattr(fit, "CODE", ("source.py",))
    monkeypatch.setattr(fit, "_git", lambda root,*args:
        fit.models.SWINIR_COMMIT if root.name == "SwinIR" else fit.models.PATCHCORE_COMMIT)
    assert fit._sources(tmp_path) == {"source.py": bank.file_sha256(source)}
    if drift == "source":
        source.write_bytes(b"changed source")
    else:
        monkeypatch.setattr(fit, "_git", lambda *a: "0"*40)
    with pytest.raises(ValueError, match="changed"):
        fit._sources(tmp_path)


def test_cli_preflight_does_not_execute(setup, monkeypatch):
    x = setup
    monkeypatch.setattr(cli, "ROOT", x.root)
    monkeypatch.setattr(cli.fit, "execute", lambda *a: pytest.fail("Implicit execution"))
    args = ["--run-id", "cli", "--data-root", str(x.data),
            "--backbone-checkpoint", str(x.checkpoints[0]), "--swinir-checkpoint", str(x.checkpoints[1])]
    assert cli.main(args) == 0
    with pytest.raises(SystemExit):
        cli.main(args+["--device", "cpu"])
    with pytest.raises(SystemExit):
        cli.main(args+["--capacity", "1"])
