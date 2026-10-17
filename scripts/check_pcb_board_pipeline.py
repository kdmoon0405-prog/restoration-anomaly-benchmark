"""Synthetic-only multi-process PCB board lifecycle check; NEVER runs real models/data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import weakref

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from sr_anomaly import pcb_board_analysis as board
from sr_anomaly import pcb_tiling as geometry
from sr_anomaly.bounded_bank import file_sha256
from sr_anomaly.dataset import safe_component
from sr_anomaly.pcb_tiled_models import PatchCoreTiles, VARIANTS
from sr_anomaly.pcb_tiled_runner import (BUDGET, GEOMETRY, available_ram, load_inventory,
                                         run_raw_smoke, write_json)
from sr_anomaly.tiled_cpu_pipeline import Parent

RAM_CAP = 1024**3  # Technical synthetic-test ceiling, NOT a research hyperparameter.


def fixture():
    parents = tuple(Parent(f"synthetic/{name}", split, label, (336,224)) for name,split,label in (
        ("fit-a","fit",0), ("fit-b","fit",0), ("cal-a","calibration",0), ("cal-b","calibration",0),
        ("test-normal","test",0), ("test-anomaly","test",1)))
    def rgb(parent):
        h,w = parent.size_wh[::-1]
        y,x = np.indices((h,w))
        code = next(i for i,p in enumerate(parents) if p.sample == parent.sample)
        return np.stack(((x+code*13)%256, (y+code*7)%256, (x+y)%256), axis=-1).astype(np.uint8)
    def transform(tile, variant):
        return np.clip(tile.astype(np.int16)+VARIANTS.index(variant), 0,255).astype(np.uint8)
    def gt(parent):
        if parent.split != "test":
            raise AssertionError("GT requested outside evaluation test split")
        mask = np.zeros(parent.size_wh[::-1], bool)
        if parent.label:
            mask[100:120,150:170] = True
            mask[120,170] = True  # diagonal singleton: 4-connectivity, not geometry's8.
        return mask
    return parents, rgb, transform, gt


class Owned:
    pass


class FakeNN:
    def __init__(self):
        self.search_index = np.zeros(8, np.float32)
    def reset_index(self):
        self.search_index = None


class FakeAdapter:
    close = PatchCoreTiles.close
    def __init__(self):
        self.model = Owned()
        self.model.anomaly_scorer = Owned()
        self.model.anomaly_scorer.nn_method = FakeNN()
        self.bound = False
    def extract(self, tiles):
        values = np.empty((len(tiles),2,2,4), np.float32)
        for i,tile in enumerate(tiles):
            values[i] = float(tile[0,0,0])+np.arange(16, dtype=np.float32).reshape(2,2,4)
        return values
    def bind_bank(self, bank):
        assert not bank.flags.writeable
        self.model.anomaly_scorer.detection_features = bank.copy()
        self.bound = True
    def predict(self, tile):
        assert self.bound
        return tile[...,0].astype(np.float32)/255., float(tile[0,0,1])+100.


def produce(payload):
    parents,rgb,transform,_ = fixture()
    adapter = FakeAdapter()
    model = weakref.ref(adapter.model)
    index = weakref.ref(adapter.model.anomaly_scorer.nn_method.search_index)
    try:
        result = run_raw_smoke(parents,rgb,adapter,transform,payload/"raw", patch_shape=(2,2), dimension=4,
            capacity=7, provenance={"input_kind":"synthetic", "fixture":"generated-board-lifecycle-v0.6"})
        scorer_copy = weakref.ref(adapter.model.anomaly_scorer.detection_features)
    finally:
        adapter.close()
    gc.collect()
    released = model() is None and index() is None and scorer_copy() is None
    if not released:
        raise AssertionError("Owned fake model/index/scorer feature references retained")
    return {"raw_status":result["status"], "owned_model_index_features_released":released}


def worker(stage, payload, variant=None):
    protocol = json.loads((payload/"PROTOCOL.json").read_text(encoding="utf-8"))
    if protocol.get("input_kind") != "synthetic":
        raise ValueError("This checker accepts generated synthetic inputs ONLY")
    for name,digest in protocol["code_sha256"].items():
        if file_sha256(ROOT/name) != digest:
            raise ValueError("Worker source differs from frozen synthetic protocol")
    parents,rgb,transform,gt = fixture()
    if stage == "produce":
        result = produce(payload)
    elif stage == "calibration":
        board.fit_calibration(payload/"raw",payload/"calibration",ram_budget=RAM_CAP)
        result = {"calibration":"COMPLETE_SYNTHETIC_ONLY"}
    elif stage == "normalize":
        board.apply_calibration(payload/"raw",payload/"calibration",payload/"normalized",ram_budget=RAM_CAP)
        result = {"normalized":"COMPLETE_SYNTHETIC_ONLY"}
    elif stage == "quality":
        def tiles(parent,name):
            return (transform(tile,name) for tile in geometry.extract_tiles(rgb(parent),geometry.tile_boxes(parent.size_wh)))
        board.quality_report(parents,rgb,tiles,payload/"quality",provenance={"input_kind":"synthetic"},ram_budget=RAM_CAP)
        result = {"quality":"COMPLETE_SYNTHETIC_ONLY"}
    else:
        board.evaluate_variant(payload/"raw",payload/"calibration",payload/"normalized",variant,gt,
                               payload/"evaluation"/variant,ram_budget=RAM_CAP)
        result = {"evaluation":"COMPLETE_SYNTHETIC_ONLY", "variant":variant}
    result.update(stage=stage,pid=os.getpid(),rss_peak_bytes=None)
    return result


def check_reference(payload):
    """Small generated cohort ONLY; unchanged helpers provide independent batch references."""
    from PIL import Image
    from sr_anomaly.evaluation import evaluate_predictions
    from sr_anomaly.fusion import normalize, quantile_threshold, robust_params
    from sr_anomaly.metrics import psnr,ssim
    source,parents = board.load_raw_run(payload/"raw")
    _,fitted = board.load_calibration(payload/"calibration",payload/"raw")
    normalized = board.load_normalized(payload/"normalized",payload/"raw",payload/"calibration")
    inventory = {p.sample:p for p in parents}
    _,rgb,transform,gt = fixture()
    for variant in VARIANTS:
        calibration = [r for r in source["rows"] if r["split"] == "calibration" and r["variant"] == variant]
        pixels = np.concatenate([np.asarray(board._map(payload/"raw",r)).ravel() for r in calibration])
        scores = np.asarray([r["score"] for r in calibration])
        assert fitted[variant]["image"] == robust_params(scores)
        assert fitted[variant]["pixel"] == robust_params(pixels)
        assert fitted[variant]["pixel_threshold"] == quantile_threshold(normalize(pixels,robust_params(pixels)),.99)
        rows = [r for r in source["rows"] if r["split"] == "test" and r["variant"] == variant]
        maps = np.stack([np.asarray(board._map(payload/"raw",r)) for r in rows])
        normalized_maps = normalize(maps,fitted[variant]["pixel"])
        saved = [r for r in normalized["rows"] if r["variant"] == variant]
        for row,expected in zip(saved,normalized_maps,strict=True):
            np.testing.assert_array_equal(board._map(payload/"normalized",row,dtype=np.float64),expected)
        reference = evaluate_predictions(np.asarray([r["label"] for r in rows]),
            normalize(np.asarray([r["score"] for r in rows]),fitted[variant]["image"]),
            masks=np.stack([gt(inventory[r["sample"]]) for r in rows]),anomaly_maps=normalized_maps,
            image_threshold=fitted[variant]["image_threshold"],pixel_threshold=fitted[variant]["pixel_threshold"],max_fpr=.3)
        assert reference == board._complete(payload/"evaluation"/variant)["metrics"]
        del maps,normalized_maps,pixels
    quality = board._complete(payload/"quality")
    for row in quality["rows"]:
        reference = Image.fromarray(rgb(inventory[row["sample"]]))
        candidate = Image.fromarray(transform(np.asarray(reference),row["variant"]))
        assert float(row["psnr"]) == psnr(reference,candidate)
        assert row["ssim"] == ssim(reference,candidate)
    return {"calibration_reference_equal":True,"normalized_files_exact":True,
            "unchanged_evaluator_reference_equal":True,"board_quality_reference_equal":True}


def run(run_id):
    run_id = safe_component(run_id,"run-id")
    report = ROOT/"analysis/pcb_board_pipeline"/run_id
    payload = ROOT/"outputs/pcb-board-pipeline"/run_id
    if report.exists() or payload.exists():
        raise FileExistsError("Existing output is never overwritten")
    source_files = ["src/sr_anomaly/pcb_board_analysis.py","scripts/check_pcb_board_pipeline.py",
        "src/sr_anomaly/pcb_tiled_models.py","src/sr_anomaly/pcb_tiled_runner.py",
        "src/sr_anomaly/bounded_bank.py","src/sr_anomaly/tiled_cpu_pipeline.py","src/sr_anomaly/pcb_tiling.py",
        "src/sr_anomaly/evaluation.py","src/sr_anomaly/fusion.py","src/sr_anomaly/metrics.py",
        "docs/PCB_FULL_FOV_PROTOCOL_V0.6.md"]
    protocol = {"input_kind":"synthetic", "frozen_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        "code_sha256":{n:file_sha256(ROOT/n) for n in source_files},"rule_id":board.RULE_ID,
        "toy_settings":{"fit":2,"calibration":2,"test":2,"size_wh":[336,224],"patch_grid":[2,2],"D":4,"K":7},
        "real_data_or_model_execution":False,"full_pilot":"NOT_READY_FOR_FULL_PILOT"}
    report.mkdir(parents=True)
    payload.mkdir(parents=True)
    write_json(report/"PROTOCOL.json",protocol)
    write_json(payload/"PROTOCOL.json",protocol)
    stages=[]
    sequence=[("produce",None),("calibration",None),("normalize",None),("quality",None)]+[("evaluate",v) for v in VARIANTS]
    for stage,variant in sequence:
        command=[sys.executable,str(Path(__file__).resolve()),"--worker",stage,"--payload",str(payload)]
        if variant:
            command += ["--variant",variant]
        child=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",timeout=120)
        if child.returncode:
            write_json(report/"FAILED.json",{"stage":stage,"exit":child.returncode,"stderr":child.stderr[-3000:]})
            raise RuntimeError(f"Synthetic stage failed: {stage}: {child.stderr[-2000:]}")
        stages.append(json.loads(child.stdout))
    reference=check_reference(payload)
    native_parents,_,_=load_inventory(ROOT/GEOMETRY)
    native_reference=json.loads((ROOT/GEOMETRY/"resource_estimate.json").read_text(encoding="utf-8"))
    native=board.memory_plan(native_parents,region_mask_bytes=native_reference["aupro_retained_region_bool_masks_bytes"])
    native.update(available_ram_bytes=available_ram(),gpu_host_ram="UNCONFIRMED",rss_peak_bytes=None)
    native["status"]="BLOCKED_MEMORY"  # Native peak/workspaces unvalidated, regardless of a transient RAM snapshot.
    result={"scope":"SYNTHETIC_ONLY_NOT_RESEARCH_RESULTS","cpu":"CPU_CALIBRATION_QUALITY_TEST_PASS",
        "synthetic_memory_lifecycle":"MEMORY_LIFECYCLE_VALIDATED", "full_memory":"BLOCKED_MEMORY",
        "stages":stages,"all_workers_exited_before_next_stage":True,"reference":reference,
        "real_gpu_smoke":"NOT_REVIEWED_NO_LOCAL_EVIDENCE", "full_pilot":"NOT_READY_FOR_FULL_PILOT",
        "actual_pcb_bank":"NOT_CREATED","actual_pcb_calibration":"NOT_CREATED"}
    write_json(report/"result.json",result)
    write_json(report/"memory_plan.json",native)
    print(json.dumps({"report":str(report.relative_to(ROOT)),"cpu":result["cpu"],"full_memory":result["full_memory"]}))
    return result


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run-id")
    cli.add_argument("--worker",choices=("produce","calibration","normalize","quality","evaluate"),help=argparse.SUPPRESS)
    cli.add_argument("--payload",type=Path,help=argparse.SUPPRESS)
    cli.add_argument("--variant",choices=VARIANTS,help=argparse.SUPPRESS)
    args=cli.parse_args()
    if args.worker:
        if args.payload is None or (args.worker == "evaluate" and args.variant is None):
            cli.error("worker payload/variant required")
        print(json.dumps(worker(args.worker,args.payload,args.variant)))
    elif args.run_id:
        run(args.run_id)
    else:
        cli.error("--run-id required")


if __name__ == "__main__":
    main()
