import gc
import json
from pathlib import Path
import weakref

import numpy as np
import pytest

from scripts.check_pcb_board_pipeline import RAM_CAP, fixture, produce
from sr_anomaly import pcb_board_analysis as board
from sr_anomaly import pcb_tiled_runner as runner
from sr_anomaly.bounded_bank import file_sha256
from sr_anomaly.fusion import normalize, quantile_threshold, robust_params
from sr_anomaly.pcb_tiled_models import VARIANTS


@pytest.fixture(autouse=True)
def synthetic_available_ram(monkeypatch):
    # Only tiny, in-process generated fixtures: test logic, not current desktop RAM.
    monkeypatch.setattr(runner, "available_ram", lambda: 64 * 1024**3)


@pytest.fixture
def raw(tmp_path):
    assert produce(tmp_path)["owned_model_index_features_released"]
    return tmp_path/"raw"


def dump(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def prepare(raw,tmp_path):
    cal,normalized=tmp_path/"cal",tmp_path/"normalized"
    board.fit_calibration(raw,cal,ram_budget=RAM_CAP)
    board.apply_calibration(raw,cal,normalized,ram_budget=RAM_CAP)
    return cal,normalized


def test_exact_calibration_reload_application_and_scopes(raw,tmp_path):
    cal,norm=prepare(raw,tmp_path)
    source,_=board.load_raw_run(raw)
    state,params=board.load_calibration(cal,raw)
    assert len(state["calibration_samples"]) == 2
    for v in VARIANTS:
        rows=[r for r in source["rows"] if r["variant"] == v and r["split"] == "calibration"]
        pixels=np.concatenate([np.asarray(board._map(raw,r)).ravel() for r in rows])
        scores=np.asarray([r["score"] for r in rows])
        assert params[v]["pixel"] == robust_params(pixels)
        assert params[v]["image"] == robust_params(scores)
        assert params[v]["pixel_threshold"] == quantile_threshold(normalize(pixels,robust_params(pixels)),.99)
        assert params[v]["image_threshold"] == quantile_threshold(normalize(scores,robust_params(scores)),.99)
    normalized=board.load_normalized(norm,raw,cal)
    assert len(normalized["rows"]) == 6
    for row in normalized["rows"]:
        original=next(r for r in source["rows"] if (r["sample"],r["variant"]) == (row["sample"],row["variant"]))
        np.testing.assert_array_equal(board._map(norm,row,dtype=np.float64),normalize(board._map(raw,original),params[row["variant"]]["pixel"]))
    with pytest.raises(FileExistsError):
        board.fit_calibration(raw,cal,ram_budget=RAM_CAP)


def test_test_values_labels_and_gt_do_not_fit_calibration(raw,tmp_path,monkeypatch):
    board.fit_calibration(raw,tmp_path/"first")
    _,first=board.load_calibration(tmp_path/"first",raw)
    source=json.loads((raw/"status.json").read_text())
    for row in source["rows"]:
        if row["split"] == "test":
            values=np.load(raw/row["file"],allow_pickle=False)
            np.save(raw/row["file"],values*17+200,allow_pickle=False)
            row["sha256"]=file_sha256(raw/row["file"])
            row["label"]=1-row["label"]
    for p in source["parents"]:
        if p["split"] == "test":
            p["label"]=1-p["label"]
    dump(raw/"status.json",source)
    original=board._map
    def calibration_only(directory,row,**kwargs):
        assert row["split"] == "calibration", "test prediction read by calibration!"
        return original(directory,row,**kwargs)
    monkeypatch.setattr(board,"_map",calibration_only)
    board.fit_calibration(raw,tmp_path/"second")
    _,second=board.load_calibration(tmp_path/"second",raw)
    assert first == second
    with pytest.raises(ValueError,match="source"):
        board.load_calibration(tmp_path/"first",raw)


@pytest.mark.parametrize("values,method",[(np.zeros(16),"unit_fallback"),(np.r_[np.zeros(15),100.],"std_fallback")])
def test_existing_fallbacks_exact(tmp_path,values,method):
    directory=tmp_path/"predictions"
    directory.mkdir()
    np.save(directory/"0000.npy",values.astype(np.float32).reshape(4,4),allow_pickle=False)
    row={"file":"predictions/0000.npy","sha256":file_sha256(directory/"0000.npy"),"size_wh":[4,4],"score":1.}
    result=board._fit_variant(tmp_path,[row])
    assert result["pixel"]["method"] == method
    assert result["pixel"] == robust_params(values)
    assert result["pixel_threshold"] == quantile_threshold(normalize(values,robust_params(values)),.99)


@pytest.mark.parametrize("mutation",["incomplete","split","path","missing","real-smoke"])
def test_raw_invalid_artifacts_rejected(raw,tmp_path,mutation):
    source=json.loads((raw/"status.json").read_text())
    if mutation == "incomplete": source["status"]="BUILDING"
    elif mutation == "split": source["rows"][0]["split"]="test"
    elif mutation == "path": source["rows"][0]["file"]="../outside.npy"
    elif mutation == "missing": source["rows"].pop()
    else: source["provenance"]["input_kind"]="fit_normal_feature_stream"
    dump(raw/"status.json",source)
    with pytest.raises(ValueError):
        board.fit_calibration(raw,tmp_path/"cal")


def test_calibration_and_normalized_tampering_rejected(raw,tmp_path):
    cal,norm=prepare(raw,tmp_path)
    (cal/"clean.json").write_text("{}",encoding="utf-8")
    with pytest.raises(ValueError,match="checksum"):
        board.load_calibration(cal,raw)
    state=json.loads((norm/"status.json").read_text())
    state["rows"][0]["split"]="calibration"
    dump(norm/"status.json",state)
    with pytest.raises(ValueError,match="inventory"):
        board.load_normalized(norm,raw,cal)


def test_memory_disk_and_source_output_guards(raw,tmp_path,monkeypatch):
    with pytest.raises(MemoryError,match="BLOCKED_MEMORY"):
        board.fit_calibration(raw,tmp_path/"no-memory",ram_budget=1)
    assert not (tmp_path/"no-memory").exists()
    with pytest.raises(ValueError,match="disjoint"):
        board.fit_calibration(raw,raw/"nested")
    board.fit_calibration(raw,tmp_path/"cal")
    real_usage=board.shutil.disk_usage
    monkeypatch.setattr(board.shutil,"disk_usage",lambda path:real_usage(path)._replace(free=1))
    with pytest.raises(OSError,match="disk"):
        board.apply_calibration(raw,tmp_path/"cal",tmp_path/"no-disk")
    assert not (tmp_path/"no-disk").exists()


def test_region_mask_explosion_blocks_before_existing_evaluator(raw,tmp_path,monkeypatch):
    cal,norm=prepare(raw,tmp_path)
    from sr_anomaly import evaluation
    monkeypatch.setattr(evaluation,"evaluate_predictions",lambda *a,**k:pytest.fail("unsafe evaluator called"))
    def checkerboard(parent):
        y,x=np.indices(parent.size_wh[::-1])
        return ((x+y)%2 == 0) if parent.label else np.zeros(parent.size_wh[::-1],bool)
    with pytest.raises(MemoryError,match="BLOCKED_MEMORY"):
        board.evaluate_variant(raw,cal,norm,"clean",checkerboard,tmp_path/"eval",
                               ram_budget=board.RAM_RESERVE+64*1024**2)
    assert json.loads((tmp_path/"eval/status.json").read_text())["status"] == "FAILED"


def test_large_phase_arrays_released_and_metric_reference_unchanged(raw,tmp_path,monkeypatch):
    refs=[]
    allocate=board.np.empty
    def tracked(*args,**kwargs):
        value=allocate(*args,**kwargs)
        if value.size > 10000:
            refs.append(weakref.ref(value))
        return value
    monkeypatch.setattr(board.np,"empty",tracked)
    cal,norm=prepare(raw,tmp_path)
    gc.collect()
    assert refs and all(r() is None for r in refs)
    from sr_anomaly.evaluation import evaluate_predictions
    _,_,_,gt=fixture()
    result=board.evaluate_variant(raw,cal,norm,"clean",gt,tmp_path/"eval",ram_budget=RAM_CAP)
    gc.collect()
    assert all(r() is None for r in refs)
    state=board.load_normalized(norm,raw,cal)
    rows=[r for r in state["rows"] if r["variant"] == "clean"]
    source,parents=board.load_raw_run(raw)
    inventory={p.sample:p for p in parents}
    _,params=board.load_calibration(cal,raw)
    expected=evaluate_predictions(np.asarray([r["label"] for r in rows]),np.asarray([r["score"] for r in rows]),
        masks=np.stack([gt(inventory[r["sample"]]) for r in rows]),
        anomaly_maps=np.stack([board._map(norm,r,dtype=np.float64) for r in rows]),
        image_threshold=params["clean"]["image_threshold"],pixel_threshold=params["clean"]["pixel_threshold"],max_fpr=.3)
    assert result["metrics"] == expected
    assert result["aupro_region_mask_payload_bytes"] == 2*224*336  # diagonal singleton remains separate


def test_board_quality_uses_test_only_no_gt_and_preserves_infinity(tmp_path):
    from sr_anomaly import pcb_tiling as geometry
    parents,rgb,transform,_=fixture()
    called=[]
    def rgb_test(parent):
        assert parent.split == "test"
        called.append(parent.sample)
        return rgb(parent)
    def tiles(parent,variant):
        for tile in geometry.extract_tiles(rgb(parent),geometry.tile_boxes(parent.size_wh)):
            yield transform(tile,variant)
    result=board.quality_report(parents,rgb_test,tiles,tmp_path/"quality",provenance={"input_kind":"synthetic"})
    assert len(called) == 2 and len(result["rows"]) == 6
    assert result["summary"]["clean"] == {"test_boards":2,"mean_psnr":"Infinity","mean_ssim":1.}
    assert result == json.loads((tmp_path/"quality/status.json").read_text())
