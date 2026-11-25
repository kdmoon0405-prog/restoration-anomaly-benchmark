"""Reviewed bank reuse, fixed integration cohort only; full production stays blocked."""
from __future__ import annotations

import csv
from dataclasses import asdict
import gc
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np

from . import bounded_bank as bank
from . import pcb_fit_bank as fit
from . import pcb_tiling as geometry
from .pcb_full_producer import _save
from .tiled_cpu_pipeline import TilePrediction, assemble_board, Parent

KIND = "reviewed_bank_reuse_integration_not_full_pilot"
COMPLETE = "BANK_REUSE_INTEGRATION_COMPLETE_NOT_FULL_APPROVAL"
FIXTURE_COMPLETE = "INJECTED_REUSE_COMPLETE_NOT_GPU_EVIDENCE"
SPEC = fit.SPEC.copy()
FIT_COMMIT = "865f26aabf4598354e1b8fb4605dc9ff09a7e810"
BANK_SHA256 = "19c3bb03a6b84475bfdc36602d05b975c57c387da81f0713c5da86b8d2f1278e"
SELECTION_SHA256 = "480f53ec4fbe355a3a5948e6a895dfdd63058eb903b8e108613a8e3a63afb402"
BANK_FILES = ("PROTOCOL.json", "status.json", "resources.json", "stage_times.csv",
              "fit_progress.json", "fit_rgb_receipts.json", "bank/status.json",
              "bank/bank.npy", "bank/selected_indices.npy")
CODE = ("src/sr_anomaly/pcb_reuse_inference.py", "scripts/run_pcb_reuse_inference.py",
        "src/sr_anomaly/pcb_full_producer.py", "src/sr_anomaly/pcb_board_analysis.py")


def _canonical(value):
    return json.dumps(value,sort_keys=True,allow_nan=False)


def _read(directory, name):
    return fit.memory.read_json(fit.runner.safe_source(directory, name))


def _hashes(directory):
    return {name: bank.file_sha256(fit.runner.safe_source(directory, name)) for name in BANK_FILES}


def _sources(root):
    return fit._sources(root) | {n: bank.file_sha256(root/n) for n in CODE}


def _frozen(root, inputs):
    parents, rows, _ = fit.runner.load_inventory(root/fit.runner.GEOMETRY)
    fitted, selection = fit._inventory(root, inputs)
    if tuple(inputs.parents) != parents or selection != SELECTION_SHA256:
        raise ValueError("Frozen inventory/selection changed")
    return fitted, {r['sample']:r for r in rows}


def admit_bank(root, bank_run, inputs):
    """No recorded remote path is opened. Validate only explicitly supplied bank-run."""
    bank_run = Path(bank_run).resolve()
    for name in BANK_FILES:
        if not fit.runner.safe_source(bank_run, name).is_file():
            raise ValueError("Missing bank-run payload/metadata: "+name)
    state, p, r, b = (_read(bank_run,n) for n in ("status.json","PROTOCOL.json","resources.json","bank/status.json"))
    fitted, rows = _frozen(root, inputs)
    for obj in (state,r):
        if (obj.get('kind') != fit.KIND or obj.get('status') != fit.COMPLETE
                or obj.get('actual_pcb_bank_created') is not True
                or obj.get('fit_bank_integrity_validated') is not True
                or any(obj.get(k) is not False for k in ('full_bank_validated','full_cohort_inference_complete','full_pilot_approved','gt_callback_used'))
                or any(obj.get(k) is not None for k in ('calibration','thresholds','metrics'))):
            raise ValueError("Only the reviewed real-fit bank is admitted")
    if (state.get('fixture_injected') is not False or r.get('input_kind') != 'fit_normal_feature_stream'
            or state.get('actual_device')!='cuda' or r.get('actual_device')!='cuda'
            or state.get('cuda_available') is not True or r.get('cuda_available') is not True):
        raise ValueError("Synthetic/injected bank is not a real-fit input")
    for name,key in (('PROTOCOL.json','protocol_sha256'),('resources.json','resources_sha256'),('stage_times.csv','timings_sha256')):
        if bank.file_sha256(bank_run/name) != state[key]:
            raise ValueError("Fit root hash link changed: "+name)
    if (p['kind'] != fit.KIND or p['spec'] != SPEC or r['settings'] != SPEC
            or p.get('patch_shape')!=[28,28] or p.get('batch_tiles')!=2 or p.get('requested_device')!='cuda'
            or p['source_commit'] != FIT_COMMIT or p['source_worktree_dirty'] is not True
            or p['code_sha256'] != fit._sources(root) or p['references_sha256'] != fit._references(root)
            or p['geometry_id'] != inputs.geometry_id or p['official_csv_sha256'] != inputs.official_sha256
            or p['selection_indices_sha256'] != SELECTION_SHA256
            or _canonical(p['fit_parents']) != _canonical([asdict(x) for x in fitted])
            or p['fit_input_sha256'] != {x.sample:rows[x.sample]['image_sha256'] for x in fitted}):
        raise ValueError("Fit model/source/reference/settings/input compatibility mismatch")
    provenance = b['provenance']
    if (set(b['artifact_sha256'])!={'bank.npy','selected_indices.npy'}
            or set(r['bank_sha256'])!={'bank.npy','selected_indices.npy','status.json'}
            or provenance['input_kind'] != 'fit_normal_feature_stream' or provenance['artifact_kind'] != fit.KIND
            or provenance['fit_protocol_sha256'] != state['protocol_sha256']
            or provenance['source_commit'] != p['source_commit']
            or provenance['source_worktree_dirty'] != p['source_worktree_dirty']
            or provenance['selection_indices_sha256'] != SELECTION_SHA256
            or b['artifact_sha256']['bank.npy'] != BANK_SHA256
            or r['bank_sha256']['bank.npy'] != BANK_SHA256
            or r['bank_sha256']['status.json'] != bank.file_sha256(bank_run/'bank/status.json')
            or r['bank_sha256']['selected_indices.npy'] != b['artifact_sha256']['selected_indices.npy']):
        raise ValueError("Reviewed bank identity/provenance mismatch")
    for name,expected in (('backbone',fit.models.BACKBONE_SHA256),('swinir',fit.models.SWINIR_SHA256)):
        if p['checkpoints'][name]['sha256'] != expected:  # Before the 1 GiB bank scan.
            raise ValueError("Bank checkpoint identity differs")
    # Existing loader verifies NPY bytes, indices, count and dtype. Additional finite
    # scan is chunked; this helper closes its own validation mmaps before returning.
    verified = fit._verify_bank(bank_run, SPEC, SELECTION_SHA256)
    if r.get('actual_shape')!=[verified['selected_count'],verified['dimension']]:
        raise ValueError('Fit resource shape receipt differs from saved bank')
    expected_counts = dict(observed_vectors=SPEC['total_vectors'], validated_vectors=SPEC['total_vectors'],
                           stored_vectors=min(SPEC['capacity'],SPEC['total_vectors']))
    if any(verified['progress'][k] != v or r['feature_counts'][k] != v for k,v in expected_counts.items()):
        raise ValueError("Bank population/storage counts differ")
    progress, receipts = _read(bank_run,'fit_progress.json'), _read(bank_run,'fit_rgb_receipts.json')
    if (progress['loaded_fit_parents'] != len(fitted) or progress['consumed_vectors'] != SPEC['total_vectors']
            or list(receipts) != [x.sample for x in fitted]
            or r['fit_rgb_receipts_sha256'] != bank.file_sha256(bank_run/'fit_rgb_receipts.json')):
        raise ValueError("Incomplete fit input receipts")
    for parent in fitted:
        item=receipts[parent.sample]
        if (item['file_sha256'] != rows[parent.sample]['image_sha256'] or item['dtype'] != 'uint8'
                or item['shape'] != [*parent.size_wh[::-1],3]):
            raise ValueError("Fit receipt identity/geometry changed")
    hashes = {n:bank.file_sha256(bank_run/n) for n in BANK_FILES if not n.endswith('.npy')}
    hashes.update({'bank/'+n:digest for n,digest in verified['artifact_sha256'].items()})
    return dict(fit_commit=p['source_commit'], fit_source_worktree_dirty=p['source_worktree_dirty'],
        shape=[verified['selected_count'],verified['dimension']], selection_indices_sha256=SELECTION_SHA256,
        file_sha256=hashes, fit_checkpoint_sha256={k:v['sha256'] for k,v in p['checkpoints'].items()})


def selected_parents(inputs):
    return tuple(p for p in fit.runner.smoke_parents(inputs.parents) if p.split != 'fit')


def counts(parents):
    return dict(parents=len(parents), maps=len(parents)*3,
        queries=sum(len(geometry.tile_boxes(p.size_wh)) for p in parents)*3,
        reference_rgb=sum(p.split=='test' for p in parents),
        variant_rgb=sum(p.split=='test' for p in parents)*3)


def resource_plan(parents):
    """Inference-specific allocation scenario, not the fit plan or a proven bound."""
    b=SPEC['capacity']*SPEC['dimension']*4
    pixels=max(p.size_wh[0]*p.size_wh[1] for p in parents)
    tiles=max(len(geometry.tile_boxes(p.size_wh)) for p in parents)
    terms=dict(bank_mmap_scorer_CPU_index_copies_bytes=3*b,
        two_full_query_distance_array_scenario_bytes=2*784*SPEC['capacity']*4,
        query_workspace_bytes=8*784*SPEC['dimension']*4,
        bank_finite_chunk_bytes=SPEC['max_chunk_vectors']*SPEC['dimension'],
        indices_bytes=SPEC['capacity']*8, native_board_and_map_workspace_bytes=32*pixels,
        one_board_tile_map_and_RGB_spool_bytes=tiles*224*224*7,
        CPU_model_runtime_allowance_bytes=2*1024**3, metadata_allowance_bytes=64*1024**2)
    raw=sum(p.size_wh[0]*p.size_wh[1]*4*3 for p in parents)
    rgb=sum(p.size_wh[0]*p.size_wh[1]*3+len(geometry.tile_boxes(p.size_wh))*224*224*3*3
            for p in parents if p.split=='test')
    return dict(terms=terms,payload_scenario_bytes=sum(terms.values()),
        required_available_ram_bytes=sum(terms.values())+fit.memory.RAM_RESERVE,
        ram_reserve_bytes=fit.memory.RAM_RESERVE, expected_new_array_file_bytes=raw+rgb,
        required_free_disk_bytes=raw+rgb+64*1024**2+fit.memory.DISK_RESERVE,
        existing_bank_copied=False, estimates_not_measured=True, upper_bound=False,
        exclusions=['Extra FAISS/BLAS/allocator/page-cache/VRAM allocations are not bounded.',
                    'No calibration/quality/evaluation stacks are allocated by this integration.'])


def unit_ledger(recorder,first,t0,t1,t2,snapshot,**fields):
    """Board x variant spans. Leaf calls lie INSIDE the inclusive span: never add both.

    RSS here is call-boundary/unit-end sampling; the OS value is the process-lifetime
    high-water mark read at unit end, NOT this unit's peak.
    """
    leaves=recorder.rows[first:]
    leaf=sum(r['elapsed_seconds'] for r in leaves)
    process=fit.memory.process_memory()
    boundary=[v for r in leaves for v in (r['rss_before_bytes'],r['rss_after_bytes'])]
    return dict(fields,inclusive_unit_seconds=t2-t0,inclusive_assemble_seconds=t1-t0,
        leaf_calls_within_unit=len(leaves),leaf_seconds_within_unit=leaf,
        assemble_spool_exclusive_seconds=t1-t0-leaf,map_save_hash_seconds=t2-t1,
        call_boundary_rss_max_bytes=max(boundary,default=None),rss_at_unit_end_bytes=process['rss_bytes'],
        os_process_lifetime_peak_rss_at_unit_end_bytes=process['os_lifetime_peak_rss_bytes'],
        **{f'torch_cuda_{k}_at_unit_end':v for k,v in (snapshot() or {}).items()})


def _guard(plan, output):
    fit.memory.guard_memory(plan['payload_scenario_bytes'])
    if shutil.disk_usage(output).free < plan['required_free_disk_bytes']:
        raise OSError('BLOCKED_DISK: integration output and fixed reserve unavailable')


def _context(root,bank_run,data_root,backbone,swinir,output):
    if not all(fit.runner.safe_source(bank_run,n).is_file() for n in BANK_FILES):
        raise ValueError('Actual bank-run including both NPY files must be explicitly supplied')
    inputs=fit.binding.FrozenPCBInputs(root,data_root)
    selected=selected_parents(inputs)
    plan=resource_plan(selected)
    _guard(plan,output)  # Before mapping/scanning the large bank.
    admission=admit_bank(root,bank_run,inputs)
    checkpoints=fit._checkpoints(backbone,swinir)
    file_hashes={p.sample:bank.file_sha256(fit.runner.safe_source(data_root,p.sample)) for p in selected}
    if any(file_hashes[p.sample] != inputs._row(p)['image_sha256'] for p in selected):
        raise ValueError('Integration source RGB checksum changed')
    return inputs,dict(kind=KIND,scope='integration-smoke',spec=SPEC.copy(),
        bank_admission=admission,bank_run_recorded_location=str(bank_run),
        data_root_recorded_location=str(data_root),parents=[asdict(p) for p in selected],counts=counts(selected),
        input_file_sha256=file_hashes,geometry_id=inputs.geometry_id,code_sha256=_sources(root),
        references_sha256=fit._references(root),checkpoints=checkpoints,plan=plan,
        source_commit=fit._git(root,'rev-parse','HEAD'),
        source_worktree_dirty=bool(fit._git(root,'status','--porcelain')),requested_device='cuda',
        python_executable=sys.executable,python_version=sys.version,numpy_version=np.__version__,
        calibration=None,thresholds=None,metrics=None,full_pilot_approved=False)


def prepare(root,bank_run,data_root,backbone,swinir,*,run_id):
    root,bank_run,data_root=map(lambda p:Path(p).resolve(),(root,bank_run,data_root))
    output=(root/'outputs/pcb-reuse-inference'/fit.safe_component(run_id,'run-id')).resolve()
    if any(output.is_relative_to(src) or src.is_relative_to(output) for src in (bank_run,data_root)):
        raise ValueError('Bank/input/output trees must be disjoint')
    output.mkdir(parents=True,exist_ok=False)
    state=dict(kind=KIND,status='PREPARING',bank_created_this_run=False,bank_reused=False,
        actual_bank_reused=False,full_cohort_inference_complete=False,full_pilot_approved=False,
        calibration=None,thresholds=None,metrics=None,gt_callback_used=False,model_execution_started=False)
    fit.memory.write_json(output/'status.json',state)
    try:
        _,protocol=_context(root,bank_run,data_root,backbone,swinir,output)
        missing=[n for n in ('torch','torchvision','faiss','timm') if importlib.util.find_spec(n) is None]
        protocol['blockers']=['missing runtime: '+n for n in missing]
        fit.runner.write_json(output/'PROTOCOL.json',protocol)
        state.update(status='PREFLIGHT_BLOCKED' if missing else 'PREFLIGHT_PASS',
                     protocol_sha256=bank.file_sha256(output/'PROTOCOL.json'),blockers=protocol['blockers'])
    except BaseException as error:
        state.update(status='BLOCKED_MEMORY' if isinstance(error,MemoryError) else 'FAILED_PREFLIGHT',
                     error=f'{type(error).__name__}: {error}')
        fit.memory.write_json(output/'status.json',state)
        raise
    fit.memory.write_json(output/'status.json',state)
    return output,state


def _validate(output,root,bank_run,data_root):
    state,p=_read(output,'status.json'),_read(output,'PROTOCOL.json')
    if (output.parent != (root/'outputs/pcb-reuse-inference').resolve()
            or state.get('kind')!=KIND or state.get('status')!='PREFLIGHT_PASS'
            or state.get('protocol_sha256')!=bank.file_sha256(output/'PROTOCOL.json')
            or p.get('scope')!='integration-smoke' or p.get('spec')!=SPEC or p.get('blockers')
            or any(state.get(k) is not False for k in ('bank_created_this_run','bank_reused','actual_bank_reused',
                'full_cohort_inference_complete','full_pilot_approved','gt_callback_used','model_execution_started'))):
        raise ValueError('Only an unchanged owned integration preflight may execute')
    if any((output/n).exists() for n in ('predictions','rgb','resources.json','stage_times.csv')):
        raise FileExistsError('Existing integration output is never overwritten/resumed')
    checks=p['checkpoints']
    inputs,current=_context(root,bank_run,data_root,checks['backbone']['path'],checks['swinir']['path'],output)
    if _canonical(current) != _canonical({k:v for k,v in p.items() if k!='blockers'}):
        raise ValueError('Source/input/bank/checkpoint/plan changed after preflight')
    return state,p,inputs


def execute(output,root,bank_run,data_root,*,factory=None):
    output,root,bank_run,data_root=map(lambda p:Path(p).resolve(),(output,root,bank_run,data_root))
    fixture=factory is not None
    if fixture and SPEC['total_vectors']*SPEC['dimension']>4096:
        raise ValueError('Injected CPU execution requires a tiny bank fixture')
    try:
        state,p,inputs=_validate(output,root,bank_run,data_root)
    except Exception as error:
        # Only this CLI's still-unexecuted owned preflight may be marked rejected.
        # Never rewrite a completed/foreign run on a retry or bad --output path.
        if output.parent==(root/'outputs/pcb-reuse-inference').resolve():
            previous=_read(output,'status.json')
            if previous.get('kind')==KIND and previous.get('status')=='PREFLIGHT_PASS':
                previous.update(status='BLOCKED_MEMORY' if isinstance(error,MemoryError) else 'REJECTED_BEFORE_MODELS',
                                error=f'{type(error).__name__}: {error}')
                fit.memory.write_json(output/'status.json',previous)
        raise
    parents=tuple(Parent(x['sample'],x['split'],x['label'],tuple(x['size_wh'])) for x in p['parents'])
    result=dict(kind=KIND,input_kind='injected_fixture' if fixture else 'actual_bank_reuse',
        fixture_injected=fixture,bank_created_this_run=False,bank_reused=False,actual_bank_reused=False,
        full_cohort_inference_complete=False,full_pilot_approved=False,calibration=None,thresholds=None,metrics=None,
        gt_callback_used=False,rows=[],reference_rows=[],rgb_rows=[],bind_calls=0,predict_calls=0,
        transform_calls={v:0 for v in fit.models.VARIANTS},adapter_close_returned=False,
        fit_execution=p['bank_admission'],bank_run_recorded_location=str(bank_run))
    adapter=transform=values=indices=recorder=None
    monitor,started,failure=fit.measured._OutputMonitor(output),False,None
    start=time.perf_counter()
    result['free_disk_bytes_at_start']=shutil.disk_usage(output).free
    state.update(status='RUNNING',fixture_injected=fixture)
    fit.memory.write_json(output/'status.json',state)
    try:
        _guard(p['plan'],output)
        if fixture:
            sync,snapshot,device=lambda:None,lambda:None,dict(actual_device='cpu',cuda_available=False)
        else:
            sync,snapshot,device=fit._cuda()
        result.update(device)
        result['model_execution_started']=not fixture
        recorder=fit.measured.Recorder(sync,cuda_snapshot=snapshot)
        monitor.start();started=True
        checkpoints=p['checkpoints']
        adapter,transform=recorder.call('model_factory',factory or fit.models.create_models,root,
            'cpu' if fixture else 'cuda',checkpoints['backbone']['path'],checkpoints['swinir']['path'])
        values,indices,_=recorder.call('load_complete_bank_mmap_verify',bank.load_complete_bank,bank_run/'bank')
        recorder.call('bind_existing_bank_CPU_exact_index',adapter.bind_bank,values)
        result.update(bind_calls=1,bank_reused=True,actual_bank_reused=not fixture,board_ledger=[])
        (output/'predictions').mkdir();(output/'rgb').mkdir()
        for parent in parents:
            if parent.split not in ('calibration','test'):
                raise ValueError('Fit RGB may not enter inference')
            rgb=recorder.call('source_rgb_decode_verify',inputs.rgb,parent)
            boxes=geometry.tile_boxes(parent.size_wh)
            if parent.split=='test':
                result['reference_rows'].append(dict(recorder.call('reference_rgb_save_hash',_save,output,
                    f"rgb/reference-{len(result['reference_rows']):04d}.npy",rgb),sample=parent.sample))
            for variant in fit.models.VARIANTS:
                first=len(recorder.rows)
                def stream():
                    spool=None
                    try:
                        if parent.split=='test':
                            name=f"rgb/tiles-{len(result['rgb_rows']):04d}.npy"
                            spool=np.lib.format.open_memmap(output/name,mode='w+',dtype=np.uint8,shape=(len(boxes),224,224,3))
                        for tile_id,(tile,box) in enumerate(zip(geometry.extract_tiles(rgb,boxes),boxes,strict=True)):
                            original=tile.copy()
                            prepared=np.array(recorder.call('prepare_'+variant,transform,tile,variant),copy=True)
                            fit.models.check_rgb(prepared)
                            if not np.array_equal(tile,original) or (variant=='clean' and not np.array_equal(prepared,original)):
                                raise ValueError('Transform mutated input or changed clean RGB')
                            before=prepared.copy()
                            if spool is not None:spool[tile_id]=prepared
                            anomaly_map,score=recorder.call('detector_inference_including_CPU_FAISS',adapter.predict,prepared)
                            if not np.array_equal(prepared,before):
                                raise ValueError('Predictor mutated produced RGB')
                            result['predict_calls']+=1;result['transform_calls'][variant]+=1
                            yield TilePrediction(parent.sample,variant,tile_id,box,anomaly_map,score)
                        if spool is not None:
                            spool.flush();spool._mmap.close();spool=None
                            result['rgb_rows'].append(dict(sample=parent.sample,variant=variant,file=name,
                                sha256=bank.file_sha256(output/name),shape=[len(boxes),224,224,3],dtype='uint8',boxes=[list(b) for b in boxes]))
                    finally:
                        if spool is not None:spool._mmap.close()
                predictions=stream()
                t0=time.perf_counter()
                try:board=assemble_board(parent.sample,variant,parent.size_wh,predictions)
                finally:predictions.close()
                t1=time.perf_counter()
                result['rows'].append(dict(_save(output,f"predictions/{len(result['rows']):04d}.npy",board.anomaly_map),
                    sample=parent.sample,split=parent.split,label=parent.label,variant=variant,size_wh=list(parent.size_wh),score=board.score))
                t2=time.perf_counter()
                result['board_ledger'].append(unit_ledger(recorder,first,t0,t1,t2,snapshot,
                    sample=parent.sample,split=parent.split,variant=variant))
                del board
            del rgb
        if (result['predict_calls']!=p['counts']['queries'] or len(result['rows'])!=p['counts']['maps']
                or len(result['reference_rows'])!=p['counts']['reference_rgb'] or len(result['rgb_rows'])!=p['counts']['variant_rgb']):
            raise ValueError('Incomplete integration inventory/call counts')
        inputs.verify_references()
        after=recorder.call('bank_and_source_rehash_after_inference',lambda:(_hashes(bank_run),_sources(root)))
        if after!=(p['bank_admission']['file_sha256'],p['code_sha256']):
            raise ValueError('Bank/source changed during inference')
        result.update(bank_unchanged=True,rgb_receipts=inputs.rgb_receipts)
        state['status']=FIXTURE_COMPLETE if fixture else COMPLETE
    except BaseException as error:
        failure=error
        state.update(status='BLOCKED_MEMORY' if isinstance(error,MemoryError) else 'FAILED',error=f'{type(error).__name__}: {error}')
    finally:
        try:
            if adapter is not None:
                recorder.call('adapter_close',adapter.close);result['adapter_close_returned']=True
        except BaseException as error:
            failure=failure or error;state.update(status='FAILED',cleanup_error=str(error))
        adapter=transform=None
        for value in (values,indices):
            if value is not None:value._mmap.close()
        values=indices=value=None
        gc.collect()
        result['owned_references_cleared']=True
        try:
            if started:
                result['process_memory']=monitor.finish()
                result['process_memory'].pop('sampled_workspace_disk_max_bytes',None)
            result['cuda_at_end']=snapshot() if recorder else None
        except BaseException as error:
            failure=failure or error;state.update(status='FAILED',resource_error=str(error))
        end=time.perf_counter()
        result.update(status=state['status'],perf_counter_start=start,perf_counter_end=end,outer_elapsed_seconds=end-start,
            phase_summary=recorder.summary() if recorder else {},
            output_payload_bytes_before_resource_files=fit.memory.disk_bytes(output),free_disk_bytes_at_end=shutil.disk_usage(output).free)
        fit.memory.write_json(output/'resources.json',result)
        rows=recorder.rows if recorder else []
        with (output/'stage_times.csv').open('x',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]) if rows else ['stage','elapsed_seconds'])
            writer.writeheader();writer.writerows(rows)
        state.update(bank_reused=result['bank_reused'],actual_bank_reused=result['actual_bank_reused'],
            model_execution_started=not fixture and result.get('model_execution_started',False),
            resources_sha256=bank.file_sha256(output/'resources.json'),timings_sha256=bank.file_sha256(output/'stage_times.csv'))
        fit.memory.write_json(output/'status.json',state)
    if failure is not None:raise failure
    return state


def load_integration(directory,*,bank_run,_fixture=False):
    """Explicit bank required. Never open the recorded bank path or admit a full cohort."""
    directory=Path(directory).resolve();bank_run=Path(bank_run).resolve()
    state,p,r=(_read(directory,n) for n in ('status.json','PROTOCOL.json','resources.json'))
    expected=FIXTURE_COMPLETE if _fixture else COMPLETE
    if (state.get('status')!=expected or state.get('kind')!=KIND or r.get('status')!=expected
            or p.get('scope')!='integration-smoke' or r.get('fixture_injected') is not _fixture
            or state.get('full_pilot_approved') is not False or state.get('full_cohort_inference_complete') is not False
            or state.get('fixture_injected') is not _fixture or state.get('bank_reused') is not True
            or state.get('actual_bank_reused') is not (not _fixture) or state.get('gt_callback_used') is not False
            or any(state.get(k) is not None for k in ('calibration','thresholds','metrics'))
            or state.get('bank_created_this_run') is not False or not r.get('bank_unchanged')
            or p.get('kind')!=KIND or p.get('spec')!=SPEC
            or r.get('bank_created_this_run') is not False or r.get('bank_reused') is not True
            or r.get('actual_bank_reused') is not (not _fixture)
            or r.get('adapter_close_returned') is not True
            or any(r.get(k) is not False for k in ('gt_callback_used','full_cohort_inference_complete','full_pilot_approved'))
            or any(r.get(k) is not None for k in ('calibration','thresholds','metrics'))):
        raise ValueError('Not a complete integration artifact of this scope')
    for name,key in (('PROTOCOL.json','protocol_sha256'),('resources.json','resources_sha256'),('stage_times.csv','timings_sha256')):
        if bank.file_sha256(directory/name)!=state[key]:raise ValueError('Integration hash link changed')
    if _hashes(bank_run)!=p['bank_admission']['file_sha256']:
        raise ValueError('Explicit bank source changed or missing')
    if p['bank_admission']['file_sha256']['bank/bank.npy']!=BANK_SHA256:
        raise ValueError('Integration used an unreviewed bank')
    parents=tuple(Parent(x['sample'],x['split'],x['label'],tuple(x['size_wh'])) for x in p['parents'])
    if not _fixture:
        frozen,_,_=fit.runner.load_inventory(Path(__file__).resolve().parents[2]/fit.runner.GEOMETRY)
        expected=tuple(x for x in fit.runner.smoke_parents(frozen) if x.split!='fit')
        if parents!=expected:raise ValueError('Integration is not the fixed three-parent inventory')
    if p['counts']!=counts(parents) or r['predict_calls']!=p['counts']['queries'] or r['bind_calls']!=1:
        raise ValueError('Integration call/count contract differs')
    expected_pairs=[(x,v) for x in parents for v in fit.models.VARIANTS]
    test=[x for x in parents if x.split=='test']
    if (len(r['rows'])!=len(expected_pairs) or len(r['reference_rows'])!=len(test)
            or len(r['rgb_rows'])!=len(test)*3):raise ValueError('Incomplete map/RGB inventory')
    for i,(row,(parent,variant)) in enumerate(zip(r['rows'],expected_pairs,strict=True)):
        if (row['sample']!=parent.sample or row['variant']!=variant or row['split']!=parent.split
                or row['label']!=parent.label or row['file']!=f'predictions/{i:04d}.npy'
                or row['size_wh']!=list(parent.size_wh) or row['shape']!=list(parent.size_wh[::-1])
                or row['dtype']!='float32' or type(row['score']) not in (float,int) or not np.isfinite(row['score'])):
            raise ValueError('Map/sample/variant geometry mismatch')
    for i,(row,parent) in enumerate(zip(r['reference_rows'],test,strict=True)):
        if row['sample']!=parent.sample or row['file']!=f'rgb/reference-{i:04d}.npy' or row['shape']!=[*parent.size_wh[::-1],3] or row['dtype']!='uint8':
            raise ValueError('Reference RGB mismatch')
    for i,(row,(parent,variant)) in enumerate(zip(r['rgb_rows'],[(x,v) for x in test for v in fit.models.VARIANTS],strict=True)):
        boxes=geometry.tile_boxes(parent.size_wh)
        if (row['sample']!=parent.sample or row['variant']!=variant or row['file']!=f'rgb/tiles-{i:04d}.npy'
                or row['boxes']!=[list(b) for b in boxes] or row['shape']!=[len(boxes),224,224,3] or row['dtype']!='uint8'):
            raise ValueError('Variant RGB mismatch')
    # Validate supplied payloads one at a time, never all maps/RGB in RAM together.
    for row in r['rows']+r['reference_rows']+r['rgb_rows']:
        path=fit.runner.safe_source(directory,row['file'])
        if bank.file_sha256(path)!=row['sha256']:raise ValueError('Integration payload hash mismatch')
        value=np.load(path,mmap_mode='r',allow_pickle=False)
        try:
            if list(value.shape)!=row['shape'] or str(value.dtype)!=row['dtype']:
                raise ValueError('Integration payload shape/dtype mismatch')
            if value.dtype==np.float32:
                for y in range(0,len(value),256):
                    if not np.isfinite(value[y:y+256]).all():raise ValueError('Nonfinite saved map')
        finally:value._mmap.close()
    if [(x['sample'],x['variant']) for x in r.get('board_ledger',[])]!=[(x.sample,v) for x,v in expected_pairs]:
        raise ValueError('Board x variant ledger incomplete')
    check_spool(directory,r,test)
    return r,parents


def check_spool(directory,r,test):
    """Clean tiles reassemble byte-equal to the reference; restored variants differ from clean."""
    from .pcb_tiled_models import assemble_rgb
    load=lambda row:np.load(fit.runner.safe_source(directory,row['file']),allow_pickle=False)
    tiles={(x['sample'],x['variant']):x for x in r['rgb_rows']}
    for parent,ref in zip(test,r['reference_rows'],strict=True):
        clean=load(tiles[parent.sample,'clean'])
        if not np.array_equal(assemble_rgb(parent.size_wh,clean),load(ref)):
            raise ValueError('Clean RGB spool does not reassemble to the reference board')
        for variant in fit.models.VARIANTS[1:]:
            if np.array_equal(load(tiles[parent.sample,variant]),clean):
                raise ValueError('Restored variant spool equals clean tiles')
        del clean


class IntegrationRGBSpool:
    """Read produced uint8 RGB for existing assemble_rgb/quality callbacks, no model."""
    def __init__(self,directory,*,bank_run,_fixture=False):
        self.directory=Path(directory)
        state,parents=load_integration(directory,bank_run=bank_run,_fixture=_fixture)
        self.parents={p.sample:p for p in parents if p.split=='test'}
        self.references={r['sample']:r for r in state['reference_rows']}
        self.variants={(r['sample'],r['variant']):r for r in state['rgb_rows']}

    def _array(self,row):
        path=fit.runner.safe_source(self.directory,row['file'])
        if bank.file_sha256(path)!=row['sha256']:raise ValueError('RGB payload checksum mismatch')
        values=np.load(path,allow_pickle=False)
        if list(values.shape)!=row['shape'] or values.dtype!=np.uint8:raise ValueError('RGB shape/dtype mismatch')
        return values

    def reference(self,parent):
        if self.parents.get(parent.sample)!=parent:raise ValueError('RGB parent outside test inventory')
        return self._array(self.references[parent.sample])

    def tiles(self,parent,variant):
        if self.parents.get(parent.sample)!=parent or (parent.sample,variant) not in self.variants:raise ValueError('Unknown test variant')
        yield from self._array(self.variants[parent.sample,variant])
