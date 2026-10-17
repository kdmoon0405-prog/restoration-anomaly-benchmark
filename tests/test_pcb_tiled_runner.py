from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

from scripts.check_tiled_cpu_integration import dummy_fixture
from scripts.run_pcb_tiled_patchcore import main, parser
from sr_anomaly import bounded_bank
from sr_anomaly import pcb_tiled_runner as runner
from sr_anomaly import pcb_tiled_models as models
from sr_anomaly.tiled_cpu_pipeline import feature_chunks

ROOT = Path(__file__).resolve().parents[1]


class FakeAdapter:
    def __init__(self, extractor):
        self.extract = extractor
        self.bank = None

    def bind_bank(self, bank):
        assert not bank.flags.writeable
        self.bank = bank

    def predict(self, rgb):
        assert self.bank is not None
        return rgb[..., 0].astype(np.float32), float(rgb[0, 0, 1])+100.


def test_raw_runner_synthetic_roundtrip_reference_and_label_nonuse(tmp_path):
    parents, loader, extractor, _, _ = dummy_fixture()
    results = []
    for i, inventory in enumerate((parents, [replace(p, label=1-p.label) if p.split == "test" else p for p in parents])):
        out = tmp_path/str(i)
        result = runner.run_raw_smoke(inventory, loader, FakeAdapter(extractor), lambda t, v: t, out,
            provenance={"input_kind": "synthetic"}, patch_shape=(2, 2), dimension=4, capacity=17)
        assert result["status"] == "COMPLETE" and result["bank_unchanged"]
        assert result["feature_counts"]["observed_vectors"] == 32
        assert result["thresholds"] is None and result["metrics"] is None
        assert len(result["rows"]) == 9  # one calibration + two test, three variants each
        for row in result["rows"]:
            values = np.load(out/row["file"], allow_pickle=False)
            parent = next(p for p in parents if p.sample == row["sample"])
            np.testing.assert_array_equal(values, loader(parent)[..., 0].astype(np.float32))
            assert not np.shares_memory(values, loader(parent))
            assert bounded_bank.file_sha256(out/row["file"]) == row["sha256"]
        results.append([(r["score"], r["sha256"]) for r in result["rows"]])
        with pytest.raises(FileExistsError):
            runner.run_raw_smoke(parents, loader, FakeAdapter(extractor), lambda t,v:t, out,
                provenance={"input_kind": "synthetic"}, patch_shape=(2, 2), dimension=4, capacity=17)
    assert results[0] == results[1]


def test_fit_only_and_wrong_index_sha_fails_before_extraction(tmp_path):
    parents, loader, extractor, _, _ = dummy_fixture()
    called = []
    def extract(rgb):
        called.append(rgb.copy())
        return extractor(rgb)
    stream = feature_chunks([p for p in parents if p.split == "fit"], loader, extract,
                             patch_shape=(2, 2), dimension=4, batch_tiles=3)
    assert sum(len(c) for c in stream) == 32
    assert len(called) == 3
    with pytest.raises(ValueError, match="Only normal fit"):
        list(feature_chunks(parents, loader, extract, patch_shape=(2, 2), dimension=4, batch_tiles=3))
    called.clear()
    with pytest.raises(ValueError, match="before extraction"):
        runner.run_raw_smoke(parents, loader, FakeAdapter(extract), lambda t,v:t, tmp_path/"bad-index",
            provenance={"input_kind": "synthetic"}, patch_shape=(2, 2), dimension=4, expected_index_sha="wrong")
    assert not called
    assert json.loads((tmp_path/"bad-index/status.json").read_text())["status"] == "FAILED"


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:/absolute", "a\\b", "a/../../escape"])
def test_source_path_guard(tmp_path, name):
    with pytest.raises(ValueError):
        runner.safe_source(tmp_path, name)


def test_geometry_manifest_tamper_guard(tmp_path):
    directory = tmp_path/"audit"
    directory.mkdir()
    for name in ("MANIFEST.json", "PROTOCOL.json", "INPUTS.csv", "layouts.json"):
        (directory/name).write_bytes((ROOT/runner.GEOMETRY/name).read_bytes())
    (directory/"INPUTS.csv").write_text("altered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        runner.load_inventory(directory)


def test_deterministic_smoke_selection_and_resource_formula():
    parents, _, _ = runner.load_inventory(ROOT/runner.GEOMETRY)
    smoke = runner.smoke_parents(parents)
    assert [p.split for p in smoke] == ["fit", "calibration", "test", "test"]
    assert [p.label for p in smoke] == [0, 0, 0, 1]
    assert smoke == runner.smoke_parents(parents)
    plan = runner.memory_plan(parents)
    assert plan["fit_vectors"] == 27132672
    assert plan["bank_bytes"] == 1024**3
    assert plan["pixel_AUROC_visible_live_payload_lower_bound_bytes"] == 11717784000
    assert runner.memory_plan(smoke)["fit_vectors"] == 37632


@pytest.fixture
def isolated_preflight(monkeypatch, tmp_path):
    """Tracked metadata + synthetic file/hash/device probes; NO dataset/checkpoint reads."""
    original_file = Path.is_file
    original_sha = bounded_bank.file_sha256
    fake_data = tmp_path/"data"
    backbone, swinir = tmp_path/"backbone.pth", tmp_path/"swinir.pth"
    expected_csv = json.loads((ROOT/runner.GEOMETRY/"PROTOCOL.json").read_text())["official_csv_sha256"]
    def is_file(path):
        return True if path.is_relative_to(tmp_path) else original_file(path)
    def sha(path):
        path = Path(path)
        if path == backbone:
            return models.BACKBONE_SHA256
        if path == swinir:
            return models.SWINIR_SHA256
        if path == fake_data/"split_csv/1cls.csv":
            return expected_csv
        assert not path.is_relative_to(fake_data), "preflight read RGB/GT!"
        return original_sha(path)
    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(bounded_bank, "file_sha256", sha)
    monkeypatch.setattr(runner, "probe_device", lambda device: {"actual_device": "cpu", "requested_device": device,
                                                              "cuda_available": False, "torch_installed": True})
    monkeypatch.setattr(runner.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(runner, "available_ram", lambda: 64*1024**3)
    monkeypatch.setattr(runner, "create_models", lambda *args: pytest.fail("model creation in preflight"))
    return fake_data, backbone, swinir


def test_preflight_no_models_data_read_or_downloading_and_full_blocked(isolated_preflight):
    data, backbone, swinir = isolated_preflight
    report = runner.preflight(ROOT, data, backbone, swinir, scope="model-smoke", device="auto")
    assert report["status"] == "PREFLIGHT_PASS"
    assert report["actual_pcb_bank"] == "NOT_CREATED"
    full = runner.preflight(ROOT, data, backbone, swinir)
    assert full["status"] == "PREFLIGHT_BLOCKED"
    assert full["selection_indices_sha256"] == "480f53ec4fbe355a3a5948e6a895dfdd63058eb903b8e108613a8e3a63afb402"
    assert any("native evaluation" in b for b in full["blockers"])


def test_resource_checkpoint_and_unresolved_block_before_factory(isolated_preflight, monkeypatch, tmp_path):
    data, backbone, swinir = isolated_preflight
    report = runner.preflight(ROOT, data, backbone, swinir, scope="model-smoke", ram_budget=1)
    assert report["status"] == "PREFLIGHT_BLOCKED"
    with pytest.raises(RuntimeError, match="before model construction"):
        runner.execute_smoke(report, ROOT, data, tmp_path/"unused")
    monkeypatch.setattr(Path, "is_file", lambda p: False)
    report = runner.preflight(ROOT, None, None, None, scope="model-smoke")
    assert any("backbone checkpoint" in b for b in report["blockers"])
    assert any("swinir checkpoint" in b for b in report["blockers"])
    full = dict(report, scope="full-pilot", status="PREFLIGHT_PASS", blockers=[])
    with pytest.raises(RuntimeError):
        runner.execute_smoke(full, ROOT, data, tmp_path/"unused")


def test_execute_calls_factory_only_after_fresh_guards(isolated_preflight, monkeypatch, tmp_path):
    data, backbone, swinir = isolated_preflight
    report = runner.preflight(ROOT, data, backbone, swinir, scope="model-smoke")
    calls = []
    def factory(*args):
        calls.append(args)
        return "fake-adapter", "fake-transform"
    def body(parents, loader, adapter, transform, output, **kwargs):
        assert len(parents) == 4 and adapter == "fake-adapter"
        assert kwargs["expected_index_sha"] == report["selection_indices_sha256"]
        return {"status": "synthetic-dispatch-pass"}
    monkeypatch.setattr(runner, "run_raw_smoke", body)
    result = runner.execute_smoke(report, ROOT, data, tmp_path/"payload", factory=factory)
    assert result["status"] == "synthetic-dispatch-pass" and len(calls) == 1
    with pytest.raises(FileExistsError):
        runner.execute_smoke(report, ROOT, data, tmp_path, factory=factory)
    report["code_sha256"] = {"src/sr_anomaly/pcb_tiled_models.py": "invalid"}
    with pytest.raises(ValueError, match="source changed"):
        runner.execute_smoke(report, ROOT, data, tmp_path/"payload", factory=factory)
    assert len(calls) == 1


def test_invalid_checkpoint_hash_is_not_accepted(isolated_preflight, monkeypatch):
    data, backbone, swinir = isolated_preflight
    sha = bounded_bank.file_sha256
    monkeypatch.setattr(bounded_bank, "file_sha256", lambda p: "bad" if Path(p) == backbone else sha(p))
    result = runner.preflight(ROOT, data, backbone, swinir, scope="model-smoke")
    assert "backbone checkpoint missing/hash mismatch" in result["blockers"]


def test_cuda_error_without_torch(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    assert runner.probe_device("auto")["actual_device"] == "cpu"
    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        runner.probe_device("cuda")
    with pytest.raises(ValueError):
        runner.probe_device("invalid")


def test_cli_default_and_bad_budget():
    args = parser().parse_args(["--run-id", "check"])
    assert not args.execute and args.scope == "full-pilot"
    for value in ("nan", "inf", "0", "-1"):
        with pytest.raises(SystemExit):
            main(["--run-id", "check", "--ram-budget-gib", value])


def test_rgb_merge_and_tile_variants_are_native_and_deterministic():
    first, second = np.full((224,224,3), 2, np.uint8), np.full((224,224,3), 7, np.uint8)
    result = models.assemble_rgb((336,224), iter([first, second]))
    assert np.all(result[:, :112] == 2) and np.all(result[:, 224:] == 7)
    assert np.all(result[:, 112:224] == 4)  # rint(4.5) ties-to-even
    with pytest.raises(ValueError):
        models.assemble_rgb((336,224), [first])
    class Restorer:
        def restore(self, low):
            assert low.size == (56,56)
            return low.resize((224,224), Image.Resampling.NEAREST)
    assert models.tile_variant(first, "clean") is first
    for name in models.VARIANTS:
        output = models.tile_variant(first, name, Restorer())
        np.testing.assert_array_equal(output, models.tile_variant(first, name, Restorer()))
    with pytest.raises(ValueError):
        models.tile_variant(first, "swinir_x4")
    with pytest.raises(ValueError):
        models.tile_variant(first.astype(float), "clean")


def test_execute_closes_owned_adapter_on_failure(isolated_preflight,monkeypatch,tmp_path):
    data,backbone,swinir=isolated_preflight
    report=runner.preflight(ROOT,data,backbone,swinir,scope="model-smoke")
    class Adapter:
        closed=False
        def close(self): self.closed=True
    adapter=Adapter()
    def fail(*a,**k): raise RuntimeError("synthetic failure")
    monkeypatch.setattr(runner,"run_raw_smoke",fail)
    with pytest.raises(RuntimeError,match="synthetic failure"):
        runner.execute_smoke(report,ROOT,data,tmp_path/"failed",factory=lambda *a:(adapter,None))
    assert adapter.closed
