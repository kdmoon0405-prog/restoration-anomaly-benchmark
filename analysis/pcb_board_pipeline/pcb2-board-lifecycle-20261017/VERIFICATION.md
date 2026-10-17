# Board pipeline CPU verification, 2026-10-17 KST

CPU_CALIBRATION_QUALITY_TEST_PASS. MEMORY_LIFECYCLE_VALIDATED applies to SYNTHETIC lifetime/
process tests only. Native BLOCKED_MEMORY; real GPU smoke NOT_REVIEWED; full NOT_READY.
Actual PCB bank/calibration NOT_CREATED. No real model/FAISS/SR/degradation or dataset RGB/GT/
anomaly metric execution. All computed quality/detection metrics use generated synthetic fixtures.

## Executed checks

- Full pytest:243 passed in110.38s.
- Focused new/related tests:31 passed in54.15s; same files in no-Torch/FAISS environment:
  31 passed in53.34s. No optional model runtime is required for this new pipeline.
- Existing CPU smoke in both environments:passed,2 result rows each, isolated temporary inputs.
- Synthetic multi-process checker:PASS. Toy2 fit/2 calibration/2 test,336×224, grid2×2/D4/K7.
  12 raw board maps,6 normalized test maps,3 calibration bundles,6 board-quality rows,3 existing
  evaluator results. These are NOT real restoration/anomaly predictions or population estimates.
- Seven sequential child PIDs:30956 raw,21532 calibration,14320 normalization,16940 quality,
  26636 clean evaluation,31532 bicubic evaluation,31928 swinir evaluation. subprocess.run waited
  for each worker's exit before the next; no real model existed in any process.
- Fake owned model/index/scorer feature weakrefs released. Additional tests prove large pool/
  stack reference release and adapter.close on an injected execution failure. No OS RSS/VRAM
  reduction is inferred from weakrefs; native allocator behavior is not measured.
- Calibration params/thresholds equal existing robust_params/normalize/quantile_threshold.
  Unit/std fallback checked. Perturbed test values/labels cannot affect calibration.
- Saved normalized maps exactly equal existing normalize reference. Existing evaluate_predictions
  results match direct batch references, with unchanged4-connectivity/thresholds/ties/AU-PRO.
  A diagonal singleton is retained as a distinct4-connected component. Checkerboard GT triggers
  BLOCKED_MEMORY before a large legacy region-mask list can be allocated.
- Native RGB mean reconstruction + board PSNR/SSIM match direct helper references; quality loads
  test RGB only, no GT. Clean PSNR remains explicit "Infinity", SSIM1, not a fabricated finite value.
- Incomplete/corrupt/source/rule/split/path/resource/disk/overwrite guards tested. Source/output
  artifact trees must be disjoint. Saved arrays are local-only ignored outputs.

## Code and artifact provenance

Frozen before execution: PROTOCOL.json SHA256
0c36f02c8248fbcff9612e96e9d05d33943cb27ae75607086d30860850436764.
result.json SHA256961edb8baa908352bf84f76282c8b840788cfacdfdb814ace300ee9f7e093adc.
memory_plan.json SHA256c88f6cf439d8a2c94d4383ce9057be20c6da332449568a244db843846cbfd2a6.
All frozen executed source hashes were rechecked after the run. Pre-commit HEAD7167cd1 identifies
the prior revision; exact code hashes bind the new executed source, not HEAD alone.

No diff in original Branch A/B/third-party/bank/geometry/fusion/metrics/evaluation/old protocols/
scientific result paths. Only separate tiled adapter/runner ownership/preflight paths changed.
git diff --check passes. AST-only graph update performed, no API/LLM work. It reports unsupported
five .m sources and empty pyproject.toml extraction; no semantic/full-graph completeness is claimed.

## Native resource plan, not a measurement of a full workload

Counts use existing frozen native audit metadata ONLY, no RGB/GT content read. Native calibration
180/test200, calibration pixels270410400/test300456000. Scenarios are per phase, not summed peaks:

| phase/payload | bytes | approximate GiB |
|---|---:|---:|
| calibration float64 pool |2163283200 |2.01 |
| pool + quantile-copy scenario |4326566400 |4.03 |
| calibration planning envelope |6537922560 |6.09 |
| normalized-input Pixel AUROC visible scenario |10816416000 |10.07 |
| evaluation planning envelope incl. known region masks |19776013920 |18.42 |
| additional normalized test files, disk |7210944000 |6.72 |
| quality planning envelope |769167360 |0.72 |

Original audit supplies region-mask payload498756960 bytes. Evaluation envelope is64Ptest+
region masks+32Bmax; visible scenario36Ptest includes both caller/binary masks and no full raw
float32 stack. Calibration24Pcal+32Bmax envelope includes quantile/normalization copy allowance.
These are explicit technical scenarios, not proven upper bounds, RSS observations or runtime.
Native/library/SSIM workspace, runtime/allocator and page-cache behavior remain unvalidated.

Win32_OperatingSystem CIM snapshot:physical16671768576 bytes (~15.53GiB), available2784985088.
Checker's separate available-RAM snapshot2834808832 bytes; different times/process activity.
No peak RSS/VRAM measured, GPU teammate RAM unconfirmed. Do not infer capacity from VRAM.

Fresh full preflight `analysis/pcb_tiled_preflight/pcb2-board-preflight-20261017/preflight.json`
returned PREFLIGHT_BLOCKED/exit2. It blocks native peak/full-executor/GPU review/approval and
available-RAM/calibration/evaluation envelopes. No --execute was invoked. New status fields do
not grant full execution even if a future available-RAM snapshot is larger.

## Reproduction and next steps

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_test.py
$boardRun = 'board-lifecycle-synthetic-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/check_pcb_board_pipeline.py --run-id $boardRun
$fullCheck = 'pcb-board-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/run_pcb_tiled_patchcore.py --run-id $fullCheck --scope full-pilot --device cpu --data-root data/external/VisA
# Expected exit2; not an inference or test failure.
git diff --check
```

Next:review actual GPU raw smoke and host RAM/VRAM; validate exact native working set on adequate
hardware; separately approve full producer/RGB/audited-GT/process orchestration. See v0.6 and
docs/PCB_BOARD_LIFECYCLE_HANDOFF.md. Existing negative gating/full110 B/B-uncertain preserved.
