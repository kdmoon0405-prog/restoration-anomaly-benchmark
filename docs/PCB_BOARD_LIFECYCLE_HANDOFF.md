# PCB board lifecycle handoff after v0.6 CPU check

2026-10-17 KST. This adds to, not rewrites, the v0.5 GPU handoff.

## What is resolved

v0.5's board calculation proposal is explicitly adopted in v0.6. Existing robust helpers,
quantile0.99 and PSNR/SSIM are reused. Artifact/split/hash guards and normalized map persistence
are implemented; test GT is evaluation-only. Synthetic integration independently matches existing
batch helpers and unchanged evaluation.py. Seven sequential worker exits separate fake inference,
calibration, normalization, quality and each variant evaluation. Model/scorer/index and large-array
reference release is tested. This is CPU plumbing/equivalence evidence, not native peak or CUDA evidence.

## Still blocked

- No local real GPU smoke artifact has been reviewed. Use the existing limited raw smoke command
  from PCB_TILED_GPU_HANDOFF.md with this code package/current source hashes. Record actual Torch,
  CUDA/GPU, system RAM/VRAM, checkpoint hashes and raw completion evidence.
- Full native evaluation working set remains unvalidated. Planning envelope≈18.42GiB, visible
  normalized-input AUROC scenario≈10.07GiB; calibration pool2.01GiB/envelope6.09GiB. The envelopes
  are technical safety scenarios, not measured peaks/proven upper bounds. Current host total15.53GiB;
  teammate host RAM unconfirmed. More VRAM alone does not remove CPU evaluation allocations.
- Normalized test artifacts add≈6.72GiB disk, excluding raw maps/bank/header/metadata/free-space margin.
- Full producer/orchestrator is NOT enabled. A future producer must supply COMPLETE full-pilot-raw
  artifacts with exact frozen721/180/200 parents and already produced RGB tiles/boards for quality.
  Do not rerun SR merely to reconstruct RGB for quality. Real smoke subset is not a production cohort.
- Actual GT loader must verify the frozen official GT file hashes, return binary native masks and
  run only in the evaluator process. No implicit resize/pad/dilation or test-dependent selection.

## When GPU raw smoke arrives, inspect before approving anything

Check pinned source/checkpoint/geometry, selected subset parent lists/index SHA, observed37632
features/D1024,9 finite native board maps, source/file hashes, immutable bank and actual CUDA model
devices with CPU exact FAISS. Bind to the actual source revision, not a claimed latest branch name.
Different source versions require reviewing changes; do not declare CPU/CUDA parity without evidence.
Do not compute research metrics from the1/1/2 smoke subset or reuse its bank/calibration for full.

Then validate native postprocessing memory on adequate hardware without altering metric semantics
or introducing approximations. GPU hardware review and native resource approval are separate gates.
Only a subsequent explicit task may enable a full producer/process pipeline and launch the pilot.

## CPU reproduction, PowerShell from research_code

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_test.py
$boardRun = 'board-lifecycle-synthetic-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/check_pcb_board_pipeline.py --run-id $boardRun
git diff --check
```

This checker generates its own images/GT and toy feature outputs. It accepts no real dataset or
checkpoint argument, never calls a real restoration/anomaly model and exports no dataset RGB.
Synthetic evaluation values stay in ignored outputs; analysis/result.json contains validation
booleans/statuses only, never fabricated PCB performance. New IDs prevent overwrites.
