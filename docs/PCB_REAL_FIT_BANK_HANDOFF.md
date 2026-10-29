# PCB real normal-fit bank handoff

2026-10-29. Delivery branch: `exp/pcb-full-producer-integration`.
Use the exact published commit reported by the CPU delivery task; the old
`83ef04e` tree does not contain this CLI. This handoff permits one guarded
fit-only execution after successful preflight. Full cohort inference and full
pilot remain blocked.

## Scope and fixed contract

`scripts/run_pcb_fit_bank.py` defaults to static preflight. It hashes the pinned
source, submodules, geometry/budget references, official CSV, both checkpoints
and compressed fit RGB files. No Torch/FAISS import, image decode or model
construction occurs in preflight. `PREFLIGHT_PASS` is not a live CUDA test;
`--execute` independently checks CUDA and fresh RAM/disk before model setup.
There is no CPU fallback, shape override, output overwrite or resume option.

The sole bank uses clean normal-fit RGB, preserving INPUTS.csv parent order,
native row-major224 tiles, maximum stride192, batch2 and the existing
batch/patch-y/patch-x feature order. Counts are:

| Item | Fixed value |
|---|---:|
| Fit normal parents |721|
| Fit tiles |34,608|
| Patches per tile |784|
| Observed and validated feature vectors |27,132,672|
| Stored bank vectors |262,144|
| Feature dimension / dtype |1,024 / float32|
| Seed / maximum chunk vectors |11 /8,192|

The existing uniform global index selection SHA is
`480f53ec4fbe355a3a5948e6a895dfdd63058eb903b8e108613a8e3a63afb402`.
It is checked against the frozen budget record, not regenerated as a replacement
reference. No global27M-vector feature stack is allocated or saved. Existing
bounded_bank writer/loader contracts are retained; only the completed saved bank
is reusable by a later, separately reviewed inference task.

The existing model factory constructs PatchCore and SwinIR together. This cost
is included in the plan and measurement. Only PatchCore feature extraction is
called. SwinIR/degradation, scorer/index binding, FAISS search, calibration,
thresholds, RGB quality and detection evaluation are absent. The fit callback
accepts only the721 fit descriptors/RGB; no calibration/test RGB or GT is passed.
Metadata validation may inspect the frozen full split descriptors.

## Existing CUDA checkout commands

Preserve the existing checkout, venv, datasets, checkpoints, branches and prior
outputs. A new checkout does not inherit those inputs. Verify a clean/safely
preserved worktree before switching; do not reset/clean or overwrite changes.

```powershell
git fetch origin exp/pcb-full-producer-integration
$pcbCommit = (git rev-parse origin/exp/pcb-full-producer-integration).Trim()
git merge-base --is-ancestor a7b2a26c26aa7a26589a0da4f3af88e297c006a3 $pcbCommit
git cat-file -e "${pcbCommit}:scripts/run_pcb_fit_bank.py"
git cat-file -e "${pcbCommit}:docs/PCB_REAL_FIT_BANK_HANDOFF.md"
```

Check each exit code, and compare `$pcbCommit` with the CPU operator's delivered
full commit before execution. Do not use an old smoke as a substitute if a file
is absent. Then:

```powershell
git switch --detach $pcbCommit
git -c core.autocrlf=true submodule update --init -- third_party/SwinIR third_party/patchcore-inspection
$pcbPython = (Resolve-Path '.venv/Scripts/python.exe').Path
$pcbData = (Resolve-Path 'data/external/VisA').Path
& $pcbPython -c "import sys,torch; print(sys.executable); print(torch.__version__); print(torch.cuda.is_available())"
& $pcbPython scripts/run_pcb_fit_bank.py --help
$pcbCheck = 'pcb-real-fit-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $pcbPython scripts/run_pcb_fit_bank.py --run-id $pcbCheck --data-root $pcbData --device cuda
```

Both commands resolve existing inputs. If their paths differ, use the actual
existing paths and record them. Default backbone is
`$TORCH_HOME/hub/checkpoints/wide_resnet50_2-95faca4d.pth` (or the user torch
cache), default SR checkpoint is
`checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth`.
Explicit `--backbone-checkpoint`/`--swinir-checkpoint` or existing
`PATCHCORE_BACKBONE_CHECKPOINT`/`SWINIR_X4_CHECKPOINT` are supported. No downloads
occur in this runner; `scripts/setup_pcb_gpu_inputs.py --help` documents the
separate existing input setup if a first-time operator needs it.

After actual `PREFLIGHT_PASS`, review blockers/plan and run once with a NEW ID:

```powershell
$pcbRun = 'pcb-real-fit-bank-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $pcbPython scripts/run_pcb_fit_bank.py --run-id $pcbRun --data-root $pcbData --device cuda --execute
$pcbExit = $LASTEXITCODE
Write-Output "Fit exit code: $pcbExit"
```

Use the same explicit checkpoint options in preflight and execute when needed.
The execution invocation creates and validates its own fresh preflight. Keep
the process running until completion or a recorded failure; progress is in
`outputs/pcb-fit-bank/<run-id>/fit_progress.json`. It records the currently
loaded fit parent and the consumed vector count after accepted chunks. It is a
progress receipt, not a resumable checkpoint. Failed/partial outputs remain
invalid; never edit status to COMPLETE or silently restart/refit.

## Artifacts and integrity

The root artifact kind is `actual_pcb_normal_fit_bank_only_not_full_pilot`.
Actual success is `REAL_FIT_BANK_COMPLETE_NOT_FULL_APPROVAL`.
Tiny injected CPU tests use `INJECTED_FIT_FIXTURE_COMPLETE_NOT_RESEARCH_BANK`;
their provenance and actual-bank flags cannot be used as research-bank evidence.

Output layout:

```text
outputs/pcb-fit-bank/<run-id>/
  PROTOCOL.json
  status.json
  fit_progress.json
  fit_rgb_receipts.json
  resources.json
  stage_times.csv
  bank/
    status.json
    bank.npy
    selected_indices.npy
```

Check root status, protocol/resource/timing links and bank/status counts. The
bank loader verifies file hashes, shape/dtype, indices and selection digest;
the runner separately checks observed count and chunked finiteness. Successful
actual runs set `actual_pcb_bank_created=true` and
`fit_bank_integrity_validated=true`. `full_bank_validated`,
`full_cohort_inference_complete` and `full_pilot_approved` stay false;
`calibration`, `thresholds` and `metrics` remain null. Integrity validation is
not detector performance validation. Do not pass this new real-fit kind to the
synthetic full-cap/limited resource reviewer.

Record the source commit AND original dirty flag, interpreter, CUDA/device and
checkpoint/source/input receipts. Do not replace the execution commit with a
later checker commit, or change dirty=true to false. RGB decoded receipts are
fit-only checksums/shape metadata, not dataset images. Retain the actual bank
privately for the later inference task; do not delete it after returning metadata.

## Resources and lifecycle

PROTOCOL records a fit-specific planning scenario: two resident bank payloads,
selection workspace64MiB, float/bool validation chunk, three feature-batch
buffers, native RGB decode workspace, model/checkpoint/runtime allowance2GiB,
metadata/timing allowance64MiB, plus unchanged OS/runtime RAM reserve2GiB.
Disk requires the bank+indices+metadata margin64MiB and fixed disk reserve1GiB.
For the frozen721-board inventory the current scenario is4.204393GiB of fit
payload,6.204393GiB required available RAM including reserve, and2.064453GiB
required free disk. These numbers are computed from the plan, not observed RSS.
Both are explicit estimates, not measured upper bounds. GPU activations and
additional library/OS/page-cache effects remain unbounded. The earlier4.144GiB
synthetic observation is not used as the actual-fit peak estimate.

Before the long stream, the saved preflight bindings and live RAM/disk/CUDA are
checked again. No other processes or OS/pagefile settings are changed. If
blocked, report the actual requirement/available values; do not shrink bank,
change geometry/seed, skip parents or lower reserves.

`resources.json` separates sampled RSS, OS lifetime high-water and PyTorch CUDA
allocated/reserved counters. CUDA synchronizes before/after timed calls. Child
calls are disjoint (factory, feature extraction batches, saved-bank validation,
adapter close). Outer time includes those plus stream bookkeeping, file writes,
hashing and cleanup. The separate fit-stream wall time also contains extraction;
do not add it to child times or to outer time. Drive free change is not exclusive
output size. No warmup/extrapolated full-cohort throughput is claimed.

The bank writer consumes one chunk into the bounded bank, releases it after
save, then the loader validates a read-only mmap and closes it. Cleanup attempts
stream and adapter closure independently and releases the transform closure
holding SwinIR. Reference-release fields cover owned variables only; exceptions
and allocator caches may persist until this dedicated CLI process exits.
Process exit/leak freedom is not self-attested by the runner.

Return a small ZIP with the relative layout preserved: root metadata/progress/
fit receipts/resources/timings, bank/status.json, separate preflight metadata,
EXECUTION_RECORD.md and SHA256SUMS.txt. Include no bank.npy/indices arrays,
dataset RGB/GT, checkpoints, venv or private research notes. Without those arrays
the receiving reviewer can check supplied metadata/hash links, not independently
verify missing bank contents. Do not flatten multiple status.json names. Keep
the bank on the GPU host, no commit/push of returned artifacts.

## CPU reproduction and remaining gates

From the repository, use the already installed explicit Python environment:

```powershell
$pcbTemp = Join-Path ([IO.Path]::GetTempPath()) ('pcb-fit-tests-' + [guid]::NewGuid().ToString('N'))
& $pcbPython -m pytest -q tests/test_pcb_fit_bank.py --basetemp $pcbTemp
& $pcbPython scripts/smoke_test.py
git diff --check
```

CPU tests use tiny fabricated RGB/features and verify no cal/test/GT, no
restoration/prediction/index binding, settings/order/source/input drift, resource
shortage, invalid streams/artifacts, CUDA failure, cleanup and reuse contracts.
They do not run the actual models. Full producer integration,180-normal
calibration/200-test inference and exact native postprocessing resources/final
execution review remain separate. No full pilot is approved by this handoff.
