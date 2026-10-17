from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from scripts.check_pcb_native_memory import ROOT, main
from sr_anomaly import pcb_native_memory as memory
from sr_anomaly.fusion import normalize, quantile_threshold, robust_params

GIB = 1024**3


@pytest.fixture
def resources(monkeypatch):
    # Only tiny fixtures execute in tests; this probe stub never authorizes native allocations.
    monkeypatch.setattr(memory, "available_ram", lambda: 64*GIB)


def test_default_is_preflight_only_no_arrays_models_or_gt(tmp_path, resources, monkeypatch):
    monkeypatch.setattr(memory.subprocess, "check_output", lambda args, **kwargs: "d732574\n" if "rev-parse" in args else "")
    monkeypatch.setattr(memory.np, "empty", lambda *a, **k: pytest.fail("Array allocated in preflight"))
    monkeypatch.setattr(memory, "evaluation_mask", lambda *a: pytest.fail("GT in preflight"))
    monkeypatch.setattr(memory.subprocess, "Popen", lambda *a, **k: pytest.fail("Worker in preflight"))
    state, output = memory.run(ROOT, "preflight-only", "small", execute=False, output_base=tmp_path)
    assert state["status"] == "PREFLIGHT_PASS"
    assert not (output/"work").exists()
    assert state["model_execution"] is False


def test_native_plan_and_gt_content_not_read(tmp_path, resources, monkeypatch):
    data = tmp_path / "data"
    actual_is_file = Path.is_file
    actual_sha = memory.file_sha256
    official_sha = memory.read_json(ROOT/memory.GEOMETRY/"PROTOCOL.json")["official_csv_sha256"]
    monkeypatch.setattr(Path, "is_file", lambda p: True if p.is_relative_to(data) else actual_is_file(p))
    monkeypatch.setattr(memory, "file_sha256", lambda p: official_sha if Path(p)==data/"split_csv/1cls.csv" else actual_sha(p))
    monkeypatch.setattr(memory.Image, "open", lambda *a, **k: pytest.fail("GT decoded in preflight"))
    monkeypatch.setattr(memory.np, "empty", lambda *a, **k: pytest.fail("Native array allocation"))
    protocol = memory.preflight(ROOT, "native", data)
    assert protocol["status"] == "PREFLIGHT_PASS"
    assert protocol["parent_counts"] == {"fit":721, "calibration":180, "test":200}
    plan = protocol["memory_plan"]
    assert plan["existing_board_plan"]["evaluation_planning_envelope_bytes"] == 19776013920
    assert plan["required_available_ram_bytes"] == 19776013920+2*GIB
    assert protocol["native_region_mask_reference_bytes"] == 498756960


def test_memory_disk_missing_input_guards(tmp_path, resources, monkeypatch):
    monkeypatch.setattr(memory, "available_ram", lambda: 1)
    state, output = memory.run(ROOT, "blocked", "small", execute=True, output_base=tmp_path)
    assert state["status"] == "BLOCKED_MEMORY"
    assert not (output/"work").exists()
    monkeypatch.setattr(memory, "available_ram", lambda: 64*GIB)
    monkeypatch.setattr(memory.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))
    assert memory.preflight(ROOT,"small",None)["status"] == "PREFLIGHT_BLOCKED"
    assert memory.preflight(ROOT,"native",None)["status"] == "BLOCKED_INPUTS"


def test_missing_measurement_support_blocks_without_allocating(tmp_path, resources, monkeypatch):
    def unsupported():
        raise OSError('measurement unavailable')
    monkeypatch.setattr(memory,'process_memory',unsupported)
    state,output=memory.run(ROOT,'measurement-blocked','small',execute=True,output_base=tmp_path)
    assert state['status']=='PREFLIGHT_BLOCKED' and not (output/'work').exists()
    protocol=memory.read_json(output/'PROTOCOL.json')
    assert protocol['orchestrator_memory_at_preflight'] is None
    assert protocol['environment']['pointer_bits'] in (32,64)


def test_cleanup_refuses_unowned_paths(tmp_path):
    run=tmp_path/'run';outside=tmp_path/'user';outside.mkdir()
    with pytest.raises(ValueError,match='cleanup outside'):
        memory.remove_owned_tree(run,outside)
    assert outside.exists()


def test_guard_accounts_for_already_live_arrays_without_weakening_cap(monkeypatch):
    monkeypatch.setattr(memory,"available_ram",lambda:int(2.5*GIB))
    with pytest.raises(MemoryError):
        memory.guard_memory(GIB)
    memory.guard_memory(GIB,live_bytes=GIB)
    with pytest.raises(MemoryError):
        memory.guard_memory(GIB,cap=2*GIB,live_bytes=GIB)


def test_output_overwrite_and_invalid_run_ids(tmp_path, resources):
    memory.run(ROOT,"one","small",output_base=tmp_path)
    with pytest.raises(FileExistsError):
        memory.run(ROOT,"one","small",output_base=tmp_path)
    with pytest.raises(ValueError):
        memory.run(ROOT,"../escape","small",output_base=tmp_path)


def test_monitor_sampling_is_not_os_peak_or_sum(tmp_path, monkeypatch):
    rss = iter((10,20,15))
    free = iter((100,80,90))
    monkeypatch.setattr(memory,"process_memory",lambda:{"rss_bytes":next(rss),"os_lifetime_peak_rss_bytes":30,"method":"fixture"})
    monkeypatch.setattr(memory,"available_ram",lambda:next(free))
    monkeypatch.setattr(memory,"disk_bytes",lambda p:7)
    monitor=memory.Monitor(tmp_path)
    for _ in range(3):
        monitor.next_disk=0
        monitor.sample()
    assert monitor.values["sampled_peak_rss_bytes"] == 20
    assert monitor.values["os_process_lifetime_peak_rss_bytes"] == 30
    assert monitor.values["system_available_min_observed_bytes"] == 80
    assert monitor.values["sample_count"] == 3


def test_real_process_measurement_is_bytes():
    values=memory.process_memory()
    assert values["rss_bytes"]>0
    assert values["os_lifetime_peak_rss_bytes"]>=values["rss_bytes"]


def test_generator_is_deterministic_and_ignores_gt_labels_paths(tmp_path):
    parents=memory.small_parents()
    changed=tuple(replace(p,label=1-p.label,sample='changed/'+str(i)) for i,p in enumerate(parents))
    one,two=tmp_path/"a",tmp_path/"b"
    one.mkdir(); two.mkdir()
    left=memory._raw_fixture(one,parents,"clean","test")
    right=memory._raw_fixture(two,changed,"clean","test")
    assert [(r["sha256"],r["score"]) for r in left] == [(r["sha256"],r["score"]) for r in right]


def test_calibration_reuses_exact_helpers_and_removes_raw_temporary_maps(tmp_path, resources):
    output=tmp_path/"run"
    (output/"work").mkdir(parents=True)
    protocol=memory.preflight(ROOT,"small",None)
    memory.perform_stage(ROOT,output,protocol,"calibration","clean")
    fitted=memory.read_json(output/"work/clean/synthetic_parameters.json")["params"]
    arrays=[];scores=[]
    for i in range(2):
        rng=memory._rng("clean",0,i)
        arrays.append(rng.random((224,336),dtype=np.float32))
        scores.append(rng.random())
    pixels=np.concatenate([a.ravel() for a in arrays]).astype(np.float64)
    assert fitted["pixel"] == robust_params(pixels)
    assert fitted["image"] == robust_params(np.array(scores))
    assert fitted["pixel_threshold"] == quantile_threshold(normalize(pixels,fitted["pixel"]),.99)
    assert not (output/"work/clean/calibration").exists()


def test_normalization_evaluation_helpers_do_not_export_synthetic_metrics(tmp_path, resources, monkeypatch):
    from sr_anomaly import evaluation
    output=tmp_path/"run";(output/"work").mkdir(parents=True)
    protocol=memory.preflight(ROOT,"small",None)
    for stage in ("calibration","normalization"):
        memory.perform_stage(ROOT,output,protocol,stage,"clean")
    called=[]
    def evaluate(labels,scores,**kwargs):
        assert kwargs['anomaly_maps'].dtype==np.float64
        assert kwargs['masks'].dtype==bool
        assert kwargs['anomaly_maps'].shape==(2,224,336)
        assert kwargs['max_fpr']==.3
        called.append(True)
        return {"fake_performance_sentinel":123456789}
    monkeypatch.setattr(evaluation,"evaluate_predictions",evaluate)
    result=memory.perform_stage(ROOT,output,protocol,"evaluation","clean")
    assert called and result=={"helpers_completed":True,"research_metrics_exported":False}
    assert not any('123456789' in p.read_text() for p in output.rglob('*.json'))


def test_degenerate_calibration_uses_existing_unit_fallback(tmp_path, resources, monkeypatch):
    class Constant:
        def random(self,size=None,dtype=np.float64):
            return 0. if size is None else np.zeros(size,dtype=dtype)
    monkeypatch.setattr(memory,"_rng",lambda *a:Constant())
    output=tmp_path/"run";(output/"work").mkdir(parents=True)
    memory.perform_stage(ROOT,output,memory.preflight(ROOT,"small",None),"calibration","clean")
    params=memory.read_json(output/"work/clean/synthetic_parameters.json")["params"]
    assert params['image']['method']==params['pixel']['method']=='unit_fallback'
    assert params['image_threshold']==params['pixel_threshold']==0.


def test_gt_checksum_native_binary_and_eval_only(tmp_path):
    parent=memory.small_parents()[-1]
    mask=np.zeros((224,336),np.uint8);mask[0,0]=3
    path=tmp_path/"gt.png";Image.fromarray(mask).save(path)
    rows={parent.sample:{"mask":"gt.png","mask_sha256":memory.file_sha256(path)}}
    result=memory.evaluation_mask(parent,rows,tmp_path)
    assert result.dtype==bool and result.sum()==1 and result[0,0]
    with pytest.raises(ValueError,match="test evaluation"):
        memory.evaluation_mask(replace(parent,split="calibration"),rows,tmp_path)
    rows[parent.sample]["mask_sha256"]="0"*64
    with pytest.raises(ValueError,match="hash mismatch"):
        memory.evaluation_mask(parent,rows,tmp_path)


def test_gt_wrong_native_shape_not_resized(tmp_path):
    parent=memory.small_parents()[-1]
    path=tmp_path/"gt.png";Image.fromarray(np.ones((5,6),np.uint8)).save(path)
    rows={parent.sample:{"mask":"gt.png","mask_sha256":memory.file_sha256(path)}}
    with pytest.raises(ValueError,match="shape mismatch"):
        memory.evaluation_mask(parent,rows,tmp_path)


def test_worker_refuses_real_smoke_or_incomplete_artifact(tmp_path):
    memory.write_json(tmp_path/"PROTOCOL.json",{"kind":"fit_normal_feature_stream"})
    memory.write_json(tmp_path/"status.json",{"status":"COMPLETE"})
    with pytest.raises(ValueError,match="authorization"):
        memory.worker(ROOT,tmp_path,"evaluation","clean")
    with pytest.raises(ValueError):
        memory.load_completed_rehearsal(tmp_path)


def test_failed_worker_writes_failure_without_metric_values(tmp_path, resources, monkeypatch):
    output=tmp_path/"run";output.mkdir();(output/"work").mkdir();(output/"stages").mkdir()
    protocol=memory.preflight(ROOT,"small",None)
    memory.write_json(output/"PROTOCOL.json",protocol)
    memory.write_json(output/"status.json",{"status":"BUILDING","active_stage":["clean","calibration"],
        "protocol_sha256":memory.file_sha256(output/"PROTOCOL.json")})
    def fail(*args):
        raise RuntimeError("controlled worker failure")
    monkeypatch.setattr(memory,"perform_stage",fail)
    with pytest.raises(RuntimeError,match="controlled"):
        memory.worker(ROOT,output,"calibration","clean")
    record=memory.read_json(output/"stages/clean-calibration.json")
    assert record["status"]=="FAILED" and record["sample_count"]>=2
    assert "metrics" not in record


def test_worker_source_tampering_is_rejected(tmp_path, resources):
    protocol=memory.preflight(ROOT,"small",None)
    protocol['code_sha256']['src/sr_anomaly/pcb_native_memory.py']='0'*64
    memory.write_json(tmp_path/"PROTOCOL.json",protocol)
    memory.write_json(tmp_path/"status.json",{'status':'BUILDING','active_stage':['clean','calibration'],
        'protocol_sha256':memory.file_sha256(tmp_path/"PROTOCOL.json")})
    with pytest.raises(ValueError,match='source/reference'):
        memory.worker(ROOT,tmp_path,'calibration','clean')


@pytest.mark.parametrize("returncode",[0,1])
def test_orchestrator_rejects_missing_or_failed_worker_result(tmp_path, resources, monkeypatch, returncode):
    # Freeze Git-derived metadata before substituting a subprocess fixture.
    protocol=memory.preflight(ROOT,"small",None)
    monkeypatch.setattr(memory,"preflight",lambda *a,**k:protocol)
    class Process:
        def __init__(self,*a,**k): pass
        def poll(self):return returncode
        def wait(self,*a,**k):return returncode
    monkeypatch.setattr(memory.subprocess,"Popen",Process)
    with pytest.raises(RuntimeError,match="failed/incomplete"):
        memory.run(ROOT,"failure","small",execute=True,output_base=tmp_path)
    state=memory.read_json(tmp_path/"failure/status.json")
    assert state["status"]=="FAILED"
    assert not (tmp_path/"failure/stage_memory.csv").exists()


def test_timeout_terminates_only_owned_worker(tmp_path, resources, monkeypatch):
    protocol=memory.preflight(ROOT,"small",None)
    monkeypatch.setattr(memory,"preflight",lambda *a,**k:protocol)
    owned=[]
    class Process:
        def __init__(self,*a,**k):self.code=None;owned.append(self)
        def poll(self):return self.code
        def terminate(self):self.code=-15
        def wait(self,*a,**k):return self.code
    monkeypatch.setattr(memory.subprocess,"Popen",Process)
    with pytest.raises(TimeoutError):
        memory.run(ROOT,"timeout","small",execute=True,output_base=tmp_path,timeout=1e-12)
    assert len(owned)==1 and owned[0].code==-15
    assert memory.read_json(tmp_path/"timeout/status.json")["owned_worker_exited"]


def test_cli_worker_cannot_execute_without_execute_flag():
    with pytest.raises(SystemExit):
        main(["--worker","calibration","--variant","clean","--payload","unused"])
