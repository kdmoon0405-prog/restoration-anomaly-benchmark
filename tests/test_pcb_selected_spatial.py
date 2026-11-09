import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from sr_anomaly.analysis_io import digest, write_csv, write_json
from sr_anomaly.pcb_selected_spatial import VARIANTS, describe_maps, load_map, seam_geometry


def maps_and_params():
    maps = {v: np.zeros((224, 416), dtype=np.float32) for v in VARIANTS}
    params = {v: dict(pixel=dict(median=0, scale=1)) for v in VARIANTS}
    return maps, params


def test_component_connectivity_gaps_centroid_and_seams():
    maps, params = maps_and_params()
    mask = np.zeros((224, 416), dtype=bool)
    mask[10, 10] = mask[11, 11] = True
    for v, value in zip(VARIANTS, [4, 2, 1], strict=True):
        maps[v][mask] = value
    result, normalized, seam = describe_maps(maps, mask, params)
    assert len(result["components"]) == 2 and result["connectivity"] == 4
    assert result["comparison"]["delta_raw_roi_bg_gap"] == -1
    assert result["comparison"]["centroid_displacement_pixels"] == 0
    assert result["gt_on_seam_pixels"] == 0
    assert np.isclose(result["comparison"]["map_correlation"], 1)
    assert normalized["bicubic_x4"].shape == seam.shape
    xs, ys, _ = seam_geometry(mask.shape)
    assert xs == [192, 224] and ys == []
    step = {v: np.zeros((224, 416), dtype=np.float32) for v in VARIANTS}
    for values in step.values():
        values[:, 192:] = 1
    descriptors, _, _ = describe_maps(step, mask, params)
    assert descriptors["variants"]["clean"]["seam_gradient_mean"] == .5
    assert descriptors["variants"]["clean"]["nonseam_gradient_mean"] == 0


def test_frozen_variant_normalization_is_not_raw_gap():
    maps, params = maps_and_params()
    mask = np.zeros((224, 416), dtype=np.uint8)
    mask[10:12, 10:12] = 1
    maps["bicubic_x4"][mask.astype(bool)] = 2
    maps["swinir_x4"][mask.astype(bool)] = 1
    params["bicubic_x4"]["pixel"] = dict(median=10, scale=2)
    params["swinir_x4"]["pixel"] = dict(median=3, scale=.5)
    result, _, _ = describe_maps(maps, mask, params)
    assert result["comparison"]["delta_raw_roi_bg_gap"] == -1
    assert result["comparison"]["delta_normalized_roi_bg_gap"] == 1


def test_empty_roi_constant_maps_and_alignment_guards():
    maps, params = maps_and_params()
    mask = np.zeros((224, 416), dtype=bool)
    result, _, _ = describe_maps(maps, mask, params)
    assert result["components"] == [] and result["gt_on_seam_ratio"] is None
    assert result["comparison"]["map_correlation"] is None
    assert result["comparison"]["centroid_displacement_pixels"] is None
    with pytest.raises(ValueError, match="Background"):
        describe_maps(maps, ~mask, params)
    with pytest.raises(ValueError, match="matching GT"):
        describe_maps(maps, mask[:, :-1], params)
    maps["clean"][0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        describe_maps(maps, mask, params)


def test_map_file_hash_path_dtype_and_shape_guards(tmp_path):
    p = tmp_path / "map.npy"
    np.save(p, np.zeros((224, 224), np.float32), allow_pickle=False)
    assert load_map(tmp_path, "map.npy", digest(p), (224, 224)).dtype == np.float32
    with pytest.raises(ValueError, match="relative"):
        load_map(tmp_path, "../map.npy", digest(p), (224, 224))
    with pytest.raises(ValueError, match="SHA256"):
        load_map(tmp_path, "map.npy", "0" * 64, (224, 224))
    with pytest.raises(ValueError, match="shape"):
        load_map(tmp_path, "map.npy", digest(p), (224, 225))
    np.save(p, np.zeros((224, 224), np.float64), allow_pickle=False)
    with pytest.raises(ValueError, match="dtype"):
        load_map(tmp_path, "map.npy", digest(p), (224, 224))


@pytest.fixture
def metadata_fixture(tmp_path, monkeypatch):
    root, metadata = tmp_path / "code", tmp_path / "metadata"
    selection_dir = root / "analysis/gpu_return_20261109"
    raw_root = metadata / "pcb/raw-run"
    cal_root = metadata / "pcb/postprocess/calibration"
    for directory in (selection_dir, raw_root, cal_root):
        directory.mkdir(parents=True)
    units, cases = [], []
    for i in range(9):
        case = dict(sample=f"sample-{i}")
        for v in VARIANTS:
            name, sha = f"predictions/{i}-{v}.npy", "1" * 64
            units.append(dict(sample=case["sample"], variant=v, split="test", label="1", file=name, sha256=sha))
            case[f"{v}_file"], case[f"{v}_sha256"] = name, sha
        cases.append(case)
    write_csv(raw_root / "units_manifest.csv", units)
    write_csv(selection_dir / "selected_native_map_cases.csv", cases)
    write_json(raw_root / "bank_status.json", dict(status="COMPLETE", provenance={"fixture": True}))
    bank_hashes = {"status.json": digest(raw_root / "bank_status.json"), "bank.npy": "2" * 64}
    write_json(raw_root / "PROTOCOL.json", dict(bank_copy_sha256=bank_hashes,
        source_commit="a" * 40, source_worktree_dirty=True))
    write_json(raw_root / "status.json", dict(status="COMPLETE", scope="full-pilot-raw",
        bank_unchanged=True, actual_bank_reused=True, bank_artifact_sha256=bank_hashes,
        provenance={"fixture": True}, protocol_sha256=digest(raw_root / "PROTOCOL.json"),
        units_manifest_sha256=digest(raw_root / "units_manifest.csv")))
    write_json(cal_root / "status.json", dict(status="COMPLETE", raw_status_sha256=digest(raw_root / "status.json")))
    for v in VARIANTS:
        write_json(cal_root / f"{v}.json", dict(pixel=dict(median=0, scale=1)))
    names = ["pcb/raw-run/PROTOCOL.json", *[f"pcb/postprocess/calibration/{v}.json" for v in VARIANTS]]
    write_json(selection_dir / "analysis_manifest.json", dict(sources={name: digest(metadata / name) for name in names}))
    write_json(selection_dir / "selected_cases_manifest.json", dict(
        table_sha256=digest(selection_dir / "selected_native_map_cases.csv"),
        source_analysis_sha256=digest(selection_dir / "analysis_manifest.json")))
    script = Path(__file__).resolve().parents[1] / "scripts/analyze_pcb_selected_maps.py"
    spec = importlib.util.spec_from_file_location("selected_map_demo", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake_script = root / "scripts/analyze_pcb_selected_maps.py"
    fake_source = root / "src/sr_anomaly/pcb_selected_spatial.py"
    for path in (fake_script, fake_source):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic source receipt\n", encoding="utf-8")
    monkeypatch.setattr(module, "__file__", str(fake_script))
    monkeypatch.setattr(module, "ROOT", root)
    return module, root, metadata


def test_missing_arrays_are_waiting_not_results(metadata_fixture, tmp_path):
    module, root, metadata = metadata_fixture
    out = tmp_path / "waiting"
    state = module.run(tmp_path / "unreceived-maps", metadata, tmp_path / "data", out)
    assert state["status"] == "WAITING_FOR_SELECTED_MAPS" and state["maps_analyzed"] == 0
    assert len(state["missing_files"]) == 27
    assert not (out / "spatial_descriptors.csv").exists()
    with pytest.raises(FileExistsError):
        module.run(tmp_path / "unreceived-maps", metadata, tmp_path / "data", out)


def test_metadata_source_and_bank_binding_rejection(metadata_fixture):
    module, root, metadata = metadata_fixture
    selected = root / "analysis/gpu_return_20261109/selected_native_map_cases.csv"
    assert len(module.verify_metadata(metadata, selected)[0]) == 9
    raw_path = metadata / "pcb/raw-run/status.json"
    raw = json.loads(raw_path.read_text('utf-8'))
    raw["provenance"] = {"fixture": False}
    write_json(raw_path, raw)
    with pytest.raises(ValueError, match="binding"):
        module.verify_metadata(metadata, selected)
    with (metadata / "pcb/raw-run/PROTOCOL.json").open('a') as stream:
        stream.write(' ')
    with pytest.raises(ValueError, match="reviewed return"):
        module.verify_metadata(metadata, selected)


@pytest.mark.parametrize("budget_failure", [False, True])
def test_synthetic_complete_pipeline_and_memory_failure(metadata_fixture, tmp_path, monkeypatch, budget_failure):
    from types import SimpleNamespace
    from PIL import Image
    from sr_anomaly.analysis_io import csv_rows, read_json
    from sr_anomaly import pcb_board_analysis, pcb_input_binding

    module, root, metadata = metadata_fixture
    bundle = root / "analysis/gpu_return_20261109"
    selection_path = bundle / "selected_native_map_cases.csv"
    cases = csv_rows(selection_path)
    units_path = metadata / "pcb/raw-run/units_manifest.csv"
    units = csv_rows(units_path)
    maps_root = tmp_path / "maps"
    parents = []
    hashes = {}
    for i, case in enumerate(cases):
        case.update(selection_group="synthetic", regression_type="improvement_or_tie")
        parents.append(SimpleNamespace(sample=case["sample"], split="test", label=1, size_wh=(224, 224)))
        for variant in VARIANTS:
            path = maps_root / case[f"{variant}_file"]
            path.parent.mkdir(parents=True, exist_ok=True)
            values = np.full((224, 224), i, dtype=np.float32)
            values[10, 10] += 1
            np.save(path, values, allow_pickle=False)
            hashes[path] = digest(path)
            case[f"{variant}_sha256"] = digest(path)
    for unit in units:
        unit["sha256"] = digest(maps_root / unit["file"])
    write_csv(units_path, units)
    write_csv(selection_path, cases)
    protocol_path = metadata / "pcb/raw-run/PROTOCOL.json"
    protocol = read_json(protocol_path)
    protocol["references_sha256"] = {}
    write_json(protocol_path, protocol)
    raw_path = metadata / "pcb/raw-run/status.json"
    raw = read_json(raw_path)
    raw.update(protocol_sha256=digest(protocol_path), units_manifest_sha256=digest(units_path),
               parents=[dict(sample=p.sample, split=p.split, label=p.label, size_wh=list(p.size_wh)) for p in parents])
    write_json(raw_path, raw)
    cal_status = metadata / "pcb/postprocess/calibration/status.json"
    calibration = read_json(cal_status)
    calibration["raw_status_sha256"] = digest(raw_path)
    write_json(cal_status, calibration)
    analysis_path = bundle / "analysis_manifest.json"
    analysis = read_json(analysis_path)
    analysis["sources"]["pcb/raw-run/PROTOCOL.json"] = digest(protocol_path)
    write_json(analysis_path, analysis)
    write_json(bundle / "selected_cases_manifest.json", dict(
        table_sha256=digest(selection_path), source_analysis_sha256=digest(analysis_path)))
    callbacks = []

    class FakeInputs:
        def __init__(self, root, data):
            self.parents = parents
            self.gt_receipts, self.rgb_receipts = {}, {}

        def evaluation_mask(self, parent):
            callbacks.append(("posthoc_gt", parent.sample))
            self.gt_receipts[parent.sample] = {"synthetic": True}
            mask = np.zeros((224, 224), dtype=bool)
            mask[10, 10] = True
            return mask

        def rgb(self, parent):
            self.rgb_receipts[parent.sample] = {"synthetic": True}
            return np.zeros((224, 224, 3), dtype=np.uint8)

    def budget(*args):
        if budget_failure:
            raise MemoryError("BLOCKED_MEMORY synthetic guard")

    monkeypatch.setattr(pcb_input_binding, "FrozenPCBInputs", FakeInputs)
    monkeypatch.setattr(pcb_board_analysis, "_budget", budget)
    monkeypatch.setattr(module, "render_case", lambda path, *args: Image.new('RGB', (1, 1)).save(path))
    out = tmp_path / "result"
    if budget_failure:
        with pytest.raises(MemoryError):
            module.run(maps_root, metadata, tmp_path / "data", out)
        assert read_json(out / "manifest.json")["status"] == "FAILED"
        assert callbacks == []
    else:
        state = module.run(maps_root, metadata, tmp_path / "data", out)
        assert state["status"] == "COMPLETE" and state["maps_analyzed"] == 27
        assert len(csv_rows(out / "spatial_descriptors.csv")) == 27
        assert len(csv_rows(out / "component_descriptors.csv")) == 9
        assert len(callbacks) == 9 and state["research_metrics_recomputed"] is False
    assert all(digest(path) == sha for path, sha in hashes.items())
