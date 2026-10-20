# Limited model-smoke resource instrumentation

2026-10-20 implementation only. No actual model/GPU/index execution is performed
by CPU unit tests. The full producer and full-pilot execution gates are unchanged.

`scripts/profile_pcb_model_smoke.py` wraps existing `preflight(scope="model-smoke")`
and `execute_smoke()`; neither their code nor scientific settings are changed.
Default is preflight-only. `--execute` is an explicit operator action for the
existing limited smoke; there is no full-pilot scope/override option.

One frozen fit parent gives 37,632 vectors, not the 262,144-vector full bank.
The same first calibration parent and first normal/anomaly test parents are used,
all native tiles included. CPU FAISS remains exact IndexFlatL2 with four workers.
No GT callback, calibration fit, threshold selection, quality/anomaly metric or
new warmup inference is added. First-call overhead remains part of the evidence.

## What is measured

- Model factory; feature extraction; CPU scorer/index bank bind; clean/bicubic
  preparation; SwinIR restoration; detector inference including CPU FAISS;
  adapter close. Their timed call intervals are disjoint. Detector time is not
  a separate measurement of FAISS/backbone internals.
- `perf_counter` before/after each call. CUDA actual-device calls synchronize
  before/after timing. CPU injected tests never import Torch or FAISS.
- RSS before/after calls, global sampled RSS (100ms), and OS process-lifetime
  high-water mark. OS lifetime includes preflight/imports and is not a stage-local
  peak. Endpoints and samples can miss short peaks; do not add unrelated peaks.
- PyTorch CUDA allocated/reserved current bytes and max since profiler start,
  reset once before factory construction. They are process-device counters, not
  whole-system VRAM, and exclude non-PyTorch GPU allocations. No allocator cache
  clear is used. A final reserved value is not proof of a leak.
- Minimum sampled available physical RAM, output disk sampling (1s), final output
  payload, and free disk snapshots. Pagefile/virtual commit is not RSS or RAM.

Outer elapsed time includes calls, RGB hashing/loading, bank/map file IO and board
assembly. **Do not add outer time to child phase sums.** Instrumented latency
includes synchronization/probe overhead and is not non-instrumented throughput.
One measured scenario is not a general peak-memory upper bound.

The default input callback is `FrozenPCBInputs.rgb`: exact frozen Parent identity,
native uint8 RGB, hash and decode of the same file bytes. No resize/GT-based tile
selection is introduced. Injected factory/loader fixtures are explicitly marked
as not real model evidence. Wrapper, input-binding and monitor source hashes are
bound in PROTOCOL.json and checked before execution. Frozen manifest/references,
original executor source, both checkpoint bytes, scientific protocol and official
split CSV are rechecked before any CUDA/factory setup. Bound input references are
checked again before completion. Original executor guards are retained. Existing output paths are refused;
partial raw output/timings/failure status remain for diagnosis.

Output: `outputs/pcb-model-resource-smoke/<run-id>/` contains PROTOCOL.json,
status.json, resources.json, stage_times.csv and unchanged executor artifacts in
raw/. Preflight-only runs have no resources.json/raw arrays. Raw COMPLETE is not
calibration, performance validation or full-bank/full-pilot approval.

## Operator commands, only after separate GPU smoke authorization

Use the existing GPU checkout/environment/data; a new worktree does not inherit
untracked data, checkpoints or `.venv`. Supply actual existing roots through
VISA_ROOT, PATCHCORE_BACKBONE_CHECKPOINT and SWINIR_X4_CHECKPOINT if defaults do
not apply. Keep hash guards; do not copy data/weights into Git.

```powershell
$preflight = 'pcb-model-resource-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/profile_pcb_model_smoke.py --run-id $preflight --device cuda --data-root $env:VISA_ROOT
```

Inspect the preflight. Only PREFLIGHT_PASS permits the following **limited** run;
the command recomputes preflight in a fresh unique output, not a stale saved pass.

```powershell
$run = 'pcb-model-resource-smoke-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/profile_pcb_model_smoke.py --run-id $run --device cuda --data-root $env:VISA_ROOT --execute
```

Return protocol/status/resources/timing CSV and original raw status/preflight
hash records. Preserve failures and dirty-source truth. Large arrays, RGB/GT and
checkpoints stay local. An observed subset peak does not validate full bank/index
workspace, full producer RGB spool/disk, whole-board evaluation or full VRAM use.
Existing limited preflight payload checks are not a model/VRAM peak guarantee.

CPU regression test only:

```powershell
$temp = 'outputs/pytest-model-resource-' + [guid]::NewGuid().ToString('N')
.venv\Scripts\python.exe -m pytest -q tests/test_pcb_model_resources.py --basetemp $temp
```
