"""Tiny load-only integration and hostile contract checks; no real model/index."""
from dataclasses import asdict
import hashlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import weakref

import numpy as np
import pytest

from sr_anomaly import pcb_reuse_inference as m
from sr_anomaly import bounded_bank as bank
from sr_anomaly.tiled_cpu_pipeline import Parent
from scripts import run_pcb_reuse_inference as cli


def read(p):return m.fit.memory.read_json(p)


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    root,data,br=tmp_path/'code',tmp_path/'data',tmp_path/'old-bank'
    for p in (root,data,br):p.mkdir()
    spec=dict(total_vectors=4,dimension=4,capacity=2,seed=11,max_chunk_vectors=8192)
    monkeypatch.setattr(m,'SPEC',spec)
    parents=(Parent('fit','fit',0,(224,224)),Parent('cal','calibration',0,(224,224)),
             Parent('good','test',0,(224,224)),Parent('bad','test',1,(224,224)))
    hashes={}
    for p in parents:
        if p.split!='fit':(data/p.sample).write_bytes(p.sample.encode())
        hashes[p.sample]=hashlib.sha256(p.sample.encode()).hexdigest()
    rows={p.sample:{'image_sha256':hashes[p.sample]} for p in parents}
    source=root/'source.py';source.write_bytes(b'frozen')
    snapshot=lambda r:{'source.py':bank.file_sha256(source)}
    monkeypatch.setattr(m.fit,'_sources',snapshot)
    monkeypatch.setattr(m.fit,'_references',lambda r:{'reference':'0'*64})
    monkeypatch.setattr(m,'_sources',snapshot)
    monkeypatch.setattr(m.fit,'_git',lambda root,*args:'new-inference-commit' if 'rev-parse' in args else '')
    class Inputs:
        def __init__(self,*args):
            self.parents=parents;self.geometry_id=m.geometry.GEOMETRY_ID
            self.official_sha256='0'*64;self.rgb_receipts={}
        def _row(self,p):return rows[p.sample]
        def rgb(self,p):
            assert p.split!='fit','Fit RGB may not be loaded'
            self.rgb_receipts[p.sample]={'shape':[224,224,3]}
            return np.full((224,224,3),{'cal':20,'good':30,'bad':40}[p.sample],np.uint8)
        def evaluation_mask(self,*args):pytest.fail('GT used')
        def verify_references(self):pass
    monkeypatch.setattr(m.fit.binding,'FrozenPCBInputs',Inputs)
    monkeypatch.setattr(m,'_frozen',lambda *a:((parents[0],),rows))
    for name in ('backbone','swinir'):(tmp_path/(name+'.pth')).write_bytes(name.encode())
    checkpoints={k:dict(path='C:/remote/DO_NOT_OPEN/'+k+'.pth',sha256=bank.file_sha256(tmp_path/(k+'.pth')))
                 for k in ('backbone','swinir')}
    monkeypatch.setattr(m.fit.models,'BACKBONE_SHA256',checkpoints['backbone']['sha256'])
    monkeypatch.setattr(m.fit.models,'SWINIR_SHA256',checkpoints['swinir']['sha256'])
    _,idx=bank.selection_plan(**spec);selection=bank.index_sha256(idx)
    monkeypatch.setattr(m,'SELECTION_SHA256',selection)
    fp=dict(kind=m.fit.KIND,spec=spec,settings=spec,source_commit=m.FIT_COMMIT,source_worktree_dirty=True,
        patch_shape=[28,28],batch_tiles=2,requested_device='cuda',
        code_sha256=snapshot(root),references_sha256=m.fit._references(root),
        geometry_id=m.geometry.GEOMETRY_ID,official_csv_sha256='0'*64,
        selection_indices_sha256=selection,fit_parents=[asdict(parents[0])],
        fit_input_sha256={'fit':hashes['fit']},checkpoints=checkpoints)
    m.fit.memory.write_json(br/'PROTOCOL.json',fp)
    proto_hash=bank.file_sha256(br/'PROTOCOL.json')
    provenance=dict(input_kind='fit_normal_feature_stream',artifact_kind=m.fit.KIND,
        fit_protocol_sha256=proto_hash,source_commit=m.FIT_COMMIT,source_worktree_dirty=True,selection_indices_sha256=selection)
    bs=bank.save_bank([np.arange(16,dtype=np.float32).reshape(4,4)],br/'bank',provenance=provenance,**spec)
    banksha=bs['artifact_sha256']['bank.npy'];monkeypatch.setattr(m,'BANK_SHA256',banksha)
    m.fit.memory.write_json(br/'fit_progress.json',dict(loaded_fit_parents=1,consumed_vectors=4))
    m.fit.memory.write_json(br/'fit_rgb_receipts.json',{'fit':dict(file_sha256=hashes['fit'],dtype='uint8',shape=[224,224,3])})
    (br/'stage_times.csv').write_text('fixture timing\n')
    common=dict(kind=m.fit.KIND,status=m.fit.COMPLETE,actual_pcb_bank_created=True,fit_bank_integrity_validated=True,
        full_bank_validated=False,full_cohort_inference_complete=False,full_pilot_approved=False,
        gt_callback_used=False,calibration=None,thresholds=None,metrics=None,actual_device='cuda',cuda_available=True)
    resource=dict(common,input_kind='fit_normal_feature_stream',settings=spec,feature_counts=bs['progress'],actual_shape=[2,4],
        fit_rgb_receipts_sha256=bank.file_sha256(br/'fit_rgb_receipts.json'),
        bank_sha256=dict(bs['artifact_sha256'],**{'status.json':bank.file_sha256(br/'bank/status.json')}))
    m.fit.memory.write_json(br/'resources.json',resource)
    state=dict(common,fixture_injected=False,protocol_sha256=proto_hash,resources_sha256=bank.file_sha256(br/'resources.json'),
        timings_sha256=bank.file_sha256(br/'stage_times.csv'))
    m.fit.memory.write_json(br/'status.json',state)
    monkeypatch.setattr(m.fit.memory,'guard_memory',lambda *a,**kw:None)
    monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=64*1024**3))
    monkeypatch.setattr(m.importlib.util,'find_spec',lambda n:object())
    out,status=m.prepare(root,br,data,tmp_path/'backbone.pth',tmp_path/'swinir.pth',run_id='tiny')
    assert status['status']=='PREFLIGHT_PASS'
    stats=dict(bind=0,predict=0,transform=0,closed=0)
    refs=[]
    class Adapter:
        def extract(self,*a):pytest.fail('Fit extractor called')
        def bind_bank(self,values):
            assert values.shape==(2,4) and not values.flags.writeable
            stats['bind']+=1
        def predict(self,rgb):
            stats['predict']+=1
            return np.full((224,224),float(rgb[0,0,0]),np.float32),float(rgb[0,0,0])+1
        def close(self):stats['closed']+=1
    def transform(rgb,variant):
        stats['transform']+=1
        return rgb if variant=='clean' else (rgb+{'bicubic_x4':1,'swinir_x4':2}[variant]).astype(np.uint8)
    def factory(*a):
        obj=Adapter();refs.append(weakref.ref(obj));return obj,transform
    return SimpleNamespace(root=root,bank=br,data=data,out=out,parents=parents,stats=stats,refs=refs,factory=factory,
        Adapter=Adapter,transform=transform,source=source,checkpoints=checkpoints,tmp=tmp_path)


def test_end_to_end_reuse_spool_no_refit_GT_and_separate_provenance(prepared,monkeypatch):
    x=prepared
    before=m._hashes(x.bank)
    monkeypatch.setattr(bank,'save_bank',lambda *a,**k:pytest.fail('Bank refitted'))
    state=m.execute(x.out,x.root,x.bank,x.data,factory=x.factory)
    assert state['status']==m.FIXTURE_COMPLETE and not state['actual_bank_reused']
    assert x.stats==dict(bind=1,predict=9,transform=9,closed=1)
    assert before==m._hashes(x.bank) and all(r() is None for r in x.refs)
    r,parents=m.load_integration(x.out,bank_run=x.bank,_fixture=True)
    assert r['fit_execution']['fit_commit']==m.FIT_COMMIT
    assert read(x.out/'PROTOCOL.json')['source_commit']=='new-inference-commit'
    assert len(r['rows'])==9 and len(r['reference_rows'])==2 and len(r['rgb_rows'])==6
    assert all(r[k] is None for k in ('calibration','thresholds','metrics'))
    reader=m.IntegrationRGBSpool(x.out,bank_run=x.bank,_fixture=True)
    for p in parents:
        if p.split!='test':continue
        ref=reader.reference(p)
        for i,v in enumerate(m.fit.models.VARIANTS):
            result=m.fit.models.assemble_rgb(p.size_wh,reader.tiles(p,v))
            np.testing.assert_array_equal(result,ref+i)
    with pytest.raises(ValueError):m.load_integration(x.out,bank_run=x.bank)
    with pytest.raises(ValueError):m.execute(x.out,x.root,x.bank,x.data,factory=x.factory)


@pytest.mark.parametrize('target',['root','bank','source','rgb','payload','index','fit_receipt','scope'])
def test_changes_rejected_before_factory(prepared,target):
    x=prepared
    if target=='root':
        state=read(x.bank/'status.json');state['actual_pcb_bank_created']=False;m.fit.memory.write_json(x.bank/'status.json',state)
    elif target=='bank':
        value=read(x.bank/'bank/status.json');value['selected_count']=1;m.fit.memory.write_json(x.bank/'bank/status.json',value)
    elif target=='source':x.source.write_bytes(b'changed')
    elif target=='rgb':(x.data/'cal').write_bytes(b'changed')
    elif target=='payload':(x.bank/'bank/bank.npy').write_bytes(b'changed')
    elif target=='index':(x.bank/'bank/selected_indices.npy').write_bytes(b'changed')
    elif target=='fit_receipt':(x.bank/'fit_rgb_receipts.json').write_bytes(b'{}')
    else:
        p=read(x.out/'PROTOCOL.json');p['scope']='full-pilot-raw';m.fit.memory.write_json(x.out/'PROTOCOL.json',p)
    with pytest.raises((ValueError,KeyError)):m.execute(x.out,x.root,x.bank,x.data,factory=x.factory)
    assert not x.refs


@pytest.mark.parametrize('failure',['predict','transform','mutate_predict','mutate_transform','close'])
def test_failures_cleanup_and_no_false_complete(prepared,failure):
    x=prepared
    class Broken(x.Adapter):
        def predict(self,rgb):
            if failure=='predict':raise RuntimeError('injected predict failure')
            if failure=='mutate_predict':rgb[:]=255
            return super().predict(rgb)
        def close(self):
            super().close()
            if failure=='close':raise RuntimeError('injected cleanup failure')
    def transform(rgb,v):
        if failure=='transform':raise RuntimeError('injected transform failure')
        if failure=='mutate_transform':rgb[:]=255
        return x.transform(rgb,v)
    with pytest.raises((ValueError,RuntimeError)):
        m.execute(x.out,x.root,x.bank,x.data,factory=lambda *a:(Broken(),transform))
    assert read(x.out/'status.json')['status']=='FAILED'
    assert not read(x.out/'status.json')['full_pilot_approved'] and x.stats['closed']==1


@pytest.mark.parametrize('payload',['predictions/0000.npy','rgb/reference-0000.npy','rgb/tiles-0000.npy'])
def test_reader_rejects_missing_or_modified_payload(prepared,payload):
    x=prepared;m.execute(x.out,x.root,x.bank,x.data,factory=x.factory)
    (x.out/payload).write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash'):m.load_integration(x.out,bank_run=x.bank,_fixture=True)


def test_path_overwrite_and_missing_inputs(prepared):
    x=prepared
    args=(x.root,x.bank,x.data,x.tmp/'backbone.pth',x.tmp/'swinir.pth')
    with pytest.raises(FileExistsError):m.prepare(*args,run_id='tiny')
    with pytest.raises(ValueError):m.prepare(*args,run_id='../bad')
    with pytest.raises(ValueError):m.prepare(x.root,x.root,x.data,*args[-2:],run_id='overlap')
    with pytest.raises(ValueError):m.prepare(x.root,x.tmp/'missing',x.data,*args[-2:],run_id='missing')


@pytest.mark.parametrize('failure',['ram','disk','cuda'])
def test_fresh_resource_and_cuda_failure_before_factory(prepared,monkeypatch,failure):
    x=prepared
    def blocked(*a,**k):raise MemoryError('BLOCKED_MEMORY')
    if failure=='ram':monkeypatch.setattr(m.fit.memory,'guard_memory',blocked)
    elif failure=='disk':monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=1))
    else:
        def no_cuda():raise RuntimeError('CUDA required')
        monkeypatch.setattr(m.fit,'_cuda',no_cuda)
    with pytest.raises((MemoryError,OSError,RuntimeError)):
        m.execute(x.out,x.root,x.bank,x.data,**({} if failure=='cuda' else {'factory':x.factory}))
    assert not x.refs and read(x.out/'status.json')['status']!='COMPLETE'


def test_production_admission_keeps_fake_kind_rejected(prepared):
    x=prepared
    s=read(x.bank/'status.json');s['kind']='synthetic';m.fit.memory.write_json(x.bank/'status.json',s)
    with pytest.raises(ValueError,match='real-fit'):m.admit_bank(x.root,x.bank,m.fit.binding.FrozenPCBInputs())


def test_cli_no_implicit_execution_or_shape_scope_override(prepared,monkeypatch):
    x=prepared;monkeypatch.setattr(cli,'ROOT',x.root)
    monkeypatch.setattr(cli.reuse,'execute',lambda *a:pytest.fail('implicit execution'))
    args=['--run-id','cli','--bank-run',str(x.bank),'--data-root',str(x.data),
          '--backbone-checkpoint',str(x.tmp/'backbone.pth'),'--swinir-checkpoint',str(x.tmp/'swinir.pth')]
    assert cli.main(args)==0
    for extra in (['--device','cpu'],['--scope','full'],['--capacity','1']):
        with pytest.raises(SystemExit):cli.main(args+extra)


def test_imports_and_cli_help_without_model_runtimes():
    root=Path(__file__).resolve().parents[1]
    code="""
import sys,importlib.abc,runpy
class Deny(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'torch','torchvision','faiss','timm','patchcore'}:raise AssertionError('runtime import '+name)
sys.meta_path.insert(0,Deny())
sys.argv=[sys.argv[1],'--help']
runpy.run_path(sys.argv[0],run_name='__main__')
"""
    result=subprocess.run([sys.executable,'-c',code,str(root/'scripts/run_pcb_reuse_inference.py')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr[-1500:]


def test_old_full_and_synthetic_readers_remain_closed(prepared):
    from sr_anomaly import pcb_board_analysis as board
    from sr_anomaly.pcb_full_producer import RGBSpool
    x=prepared;m.execute(x.out,x.root,x.bank,x.data,factory=x.factory)
    for reader in (board.load_raw_run,RGBSpool):
        with pytest.raises(ValueError):reader(x.out)


@pytest.mark.parametrize('mode',['pair','geometry','count','approval','root_GT','fake_upgrade'])
def test_forged_completed_metadata_is_rejected(prepared,mode):
    x=prepared;m.execute(x.out,x.root,x.bank,x.data,factory=x.factory)
    r=read(x.out/'resources.json');s=read(x.out/'status.json')
    if mode=='pair':r['rows'][0]['variant']='swinir_x4'
    elif mode=='geometry':r['rgb_rows'][0]['boxes'][0][0]=1
    elif mode=='count':r['predict_calls']=0
    elif mode=='approval':r['full_pilot_approved']=True
    elif mode=='root_GT':s['gt_callback_used']=True
    else:
        r.update(status=m.COMPLETE,fixture_injected=False,actual_bank_reused=True)
        s.update(status=m.COMPLETE,actual_bank_reused=True)
    m.fit.memory.write_json(x.out/'resources.json',r)
    s['resources_sha256']=bank.file_sha256(x.out/'resources.json')
    m.fit.memory.write_json(x.out/'status.json',s)
    with pytest.raises(ValueError):m.load_integration(x.out,bank_run=x.bank,_fixture=(mode!='fake_upgrade'))


def test_model_construction_failure_and_missing_payload_are_not_complete(prepared):
    x=prepared
    def broken(*args):raise RuntimeError('factory failure')
    with pytest.raises(RuntimeError):m.execute(x.out,x.root,x.bank,x.data,factory=broken)
    assert read(x.out/'status.json')['status']=='FAILED'
    assert not (x.out/'predictions').exists()


def test_self_consistent_same_shape_fake_cannot_replace_reviewed_bank(prepared):
    x=prepared
    path=x.bank/'bank/bank.npy'
    values=np.load(path,allow_pickle=False)+1
    with path.open('wb') as stream:np.save(stream,values,allow_pickle=False)
    b=read(x.bank/'bank/status.json');b['artifact_sha256']['bank.npy']=bank.file_sha256(path)
    m.fit.memory.write_json(x.bank/'bank/status.json',b)
    r=read(x.bank/'resources.json');r['bank_sha256']['bank.npy']=b['artifact_sha256']['bank.npy']
    r['bank_sha256']['status.json']=bank.file_sha256(x.bank/'bank/status.json')
    m.fit.memory.write_json(x.bank/'resources.json',r)
    s=read(x.bank/'status.json');s['resources_sha256']=bank.file_sha256(x.bank/'resources.json')
    m.fit.memory.write_json(x.bank/'status.json',s)
    with pytest.raises(ValueError,match='identity'):m.admit_bank(x.root,x.bank,m.fit.binding.FrozenPCBInputs())


def test_resource_monitor_failure_never_reports_complete(prepared,monkeypatch):
    x=prepared
    class BadMonitor:
        def __init__(self,*a):pass
        def start(self):pass
        def finish(self):raise RuntimeError('injected monitor failure')
    monkeypatch.setattr(m.fit.measured,'_OutputMonitor',BadMonitor)
    with pytest.raises(RuntimeError,match='monitor'):
        m.execute(x.out,x.root,x.bank,x.data,factory=x.factory)
    assert read(x.out/'status.json')['status']=='FAILED' and x.stats['closed']==1
