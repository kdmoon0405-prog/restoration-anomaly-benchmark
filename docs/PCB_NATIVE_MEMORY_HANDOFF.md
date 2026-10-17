# PCB native postprocessing memory rehearsal

2026-10-17. Branch `exp/pcb-native-memory-readiness`, based on published `d732574`.
This is a CPU resource check, NOT full-pilot approval or another GPU/model smoke.
v0.6 calibration/quality/lifecycle rules already exist; they are not reselected here.

## What the tool does

`scripts/check_pcb_native_memory.py` defaults to preflight only. `--execute` is
required to start workers or create score/RGB arrays. Outputs use a new unique
`outputs/pcb-native-memory/<run-id>/`; existing directories are never overwritten.
No models, bank, scorer or FAISS index are loaded or created. Fresh workers also
check that Torch/FAISS/PatchCore modules were not imported.

For each of clean/bicubic_x4/swinir_x4, four separate sequential worker processes
exercise calibration, normalization, quality and evaluation. These are scenario
names, NOT actual model predictions. Seed11 uniform float32 maps/scores and uint8
RGB are generated independently of image names, labels and GT. Existing
`board._fit_variant`, robust helpers, normalization, native overlap RGB assembly,
PSNR/SSIM and `evaluate_predictions` are called without changing their definitions.
Internal numerical results are discarded, not exported as research metrics.
Temporary synthetic calibration parameters exist only in the owned workspace.
No production raw-run/bank status is forged to bypass production cohort guards.

- small: generated 2 calibration/2 test boards, 336x224; generated GT only.
- native: frozen721/180/200 inventory; no fit stage; all180 calibration and200 test
  boards at native1404x1070. GT files are checked for existence in preflight; actual
  hash-verified masks are decoded ONLY in the evaluation worker. Normal masks are
  empty; anomaly is the original native mask>0. No resizing/padding/dilation/exclusion.
  The actual four-connected region payload must match the frozen498756960-byte
  reference (332 regions, distinct from geometry's8-connected324 components).

Calibration raw maps are removed after fitting. Normalization creates one variant's
float64 files; evaluation copies them into the existing full stack and calls the
unchanged evaluator. Quality rebuilds one native generated RGB board at a time.
Each variant workspace is removed only after all its workers exit successfully.
Failure workspaces/logs remain for inspection. Unexpected OS/process termination can
leave BUILDING artifacts; those are incomplete, never reusable as validated results.

## Resource gates and measurement meaning

Before execution and every phase, check the existing phase payload plan plus a
fixed2GiB OS/runtime reserve against currently available RAM and an optional
downward `--ram-budget-gib` cap. The cap cannot weaken the reserve. Evaluation
rechecks actual GT region payload, accounting for already-live stack/mask arrays
without counting them twice. Parent monitors current available RAM and terminates
ONLY its own worker if available RAM drops below the reserve. Per-worker timeout
defaults to3600s and likewise terminates only the owned worker. No OS/pagefile
changes or other-user process termination are permitted.

Native evaluator plan19776013920 bytes plus reserve2147483648 bytes requires
**21923497568 bytes (20.42GiB) currently available**, not merely32GB installed RAM.
This is a technical gate, not proof of a library memory upper bound. The reported
GPU smoke snapshot20579569664 available bytes would NOT pass it. Use a fresh
preflight after the operator has independently arranged sufficient resources;
do not lower the guard or force execution.

Current one-variant workspace disk plan plus a fixed1GiB free-space margin requires
4681310976 free bytes (about4.36GiB). This excludes other workloads/checkpoints.
The small check uses the same reserve rules with its much smaller array plans.

Measurements are intentionally separate:

- Windows: WorkingSetSize/RSS and PeakWorkingSetSize OS process-lifetime high-water.
  Linux: /proc/self/status VmRSS/VmHWM, kB converted to bytes.
- Worker sampling at100ms reports sampled peak RSS and minimum observed available
  system RAM, not a guaranteed continuous maximum/minimum. OS high-water includes
  that worker's startup/imports, not only its timed action. No private commit or
  virtual size is mislabeled RSS. Linux available-RAM probe reuses the existing
  conservative sysconf available-pages helper, not a claim of MemAvailable.
- Worker perf_counter interval includes fixture generation, I/O and helper work,
  excludes interpreter/import startup and final telemetry JSON writing. Parent
  launch-to-exit timing includes those costs. All timings are instrumented.
- Parent RSS endpoints and parent-observed available-RAM minimum are separate
  fields. Never sum unrelated worker peaks and call that simultaneous machine peak.
- Workspace bytes are exact at endpoints; sampled disk maximum is sampled at about
  one-second intervals. No mmap claim bypasses sort/quantile/region allocations.

A successful synthetic scenario measures THAT scenario, not worst-case detector
values, CPU/CUDA parity, production orchestration or general peak guarantees.
Full model/VRAM peaks and actual PCB performance remain unmeasured by this tool.

## GPU operator: keep the successful existing folder and environment

Do not create a fresh worktree unless you explicitly reconnect data/environment.
From the existing successful PCB smoke repository, first inspect user changes:

```powershell
git status --short
git fetch origin
git switch -c pcb-native-memory-local --track origin/exp/pcb-native-memory-readiness
```

If the local branch exists, inspect/reuse it rather than overwriting it. If switch
is blocked, preserve changes and report; no reset/clean. Keep the existing CUDA
Python environment active even though this task itself performs CPU work only.
Submodule pins are unchanged from the successful smoke.

```powershell
git rev-parse HEAD
python -c "import sys,platform,numpy,skimage; print(sys.version); print(platform.platform()); print('numpy',numpy.__version__,'skimage',skimage.__version__)"
python scripts/setup_pcb_gpu_inputs.py --visa-root data/external/VisA --verify-only
if ($LASTEXITCODE -ne 0) { throw 'Input verification failed' }

$small = 'pcb-memory-small-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_native_memory.py --run-id $small --scope small --execute
if ($LASTEXITCODE -ne 0) { throw 'Small rehearsal failed; inspect preserved output' }

$check = 'pcb-memory-native-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_native_memory.py --run-id $check --scope native --data-root data/external/VisA
if ($LASTEXITCODE -ne 0) { throw 'Native preflight blocked; do NOT force execution' }
```

Inspect PROTOCOL.json and status.json: preflight alone allocates no native arrays
and cannot validate peaks. Only on PREFLIGHT_PASS and after inspecting budgets:

```powershell
$native = 'pcb-memory-native-execute-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_native_memory.py --run-id $native --scope native --data-root data/external/VisA --execute
```

Use a NEW ID for execute; it repeats fresh preflight, not trusting the earlier
snapshot. If timeout or resource failure occurs, preserve it and report. Do not
change evaluator thresholds/algorithm, dimensions or cohorts to make it pass.

## Return and interpretation

Return the environment output, exact command/commit, PROTOCOL.json, status.json,
stage_memory.csv, stages/*.json and logs/*.txt. Include failed/blocked preflights.
Do NOT upload the synthetic array workspace, dataset, weights or original GPU raw
predictions to GitHub. All execution outputs remain ignored/local-only.

Completion status is `MEMORY_REHEARSAL_COMPLETE_NOT_FULL_APPROVAL`, only after12
successful worker exits, workspace cleanup and checksummed CSV/worker records.
`load_completed_rehearsal()` rejects incomplete/changed records. Scope small never
means native memory was tested. BLOCKED_MEMORY/FAILED is not a passing measurement.

Original CUDA smoke:37632x1024 bank,9 maps,12 file hashes independently checked;
its recorded source_worktree_dirty=true is preserved. No smoke rerun, peak
backfill, actual calibration or research result is produced by this rehearsal.
Next remains separate review of native measurements, full producer/GT/process
integration and explicit full-experiment authorization. Existing full-pilot blocks
and negative gating/full110 B/B-uncertain decisions are unchanged.
