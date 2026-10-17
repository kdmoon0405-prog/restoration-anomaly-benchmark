# PCB tiled GPU handoff, raw smoke only

This session runs CPU tests/preflight only. No real PatchCore/SwinIR/index/PCB inference has run.
Use the same code package/local commit and frozen audit/bank metadata; this document does not
authorize pushing it or imply it is already available on the remote repository.

## Required inputs and environment

- Existing legacy Torch/torchvision/timm/faiss-cpu environment; Torch must report CUDA available.
- Entire VisA root, with split_csv/1cls.csv and paths matching archived geometry INPUTS.csv.
  Parent split721/180/200 and all native tiles stay fixed. No previous Hazelnut bank reuse.
- third_party/patchcore-inspection and SwinIR at pinned revisions in v0.5.
- Existing ImageNet V1 backbone local checkpoint and SwinIR-S x4 checkpoint with exact v0.5 hashes.
  Runner does not download weights. Missing/mismatched inputs must be supplied, not bypassed.
- Read v0.5 before execution. Preflight report records source commit AND code hashes/dirty flag;
  pre-commit validation can have dirty=true. Bind evidence to content hashes, not commit alone.

System RAM: full capped bank/scorer/index payload scenario3GiB BEFORE model/chunks/maps/evaluation.
For smoke,1 fit parent ×48 tiles ×784 patches gives37632 vectors, bank154140672 bytes (147MiB),
and bank/scorer/index441MiB before other buffers/models. This is NOT a minimum guaranteed host
RAM requirement or RSS measurement. Native model VRAM and FAISS workspace are NOT measured;
an actual limited smoke is required. Larger GPU does not remove CPU exact-index/evaluation costs.
Minimum smoke payload disk estimate≈199MiB; metadata/temporary files/checkpoints/free-space margin
are additional. Preflight measures free disk and available RAM, not a hardware benchmark.

## Windows PowerShell, from research_code

The relative locations below already exist on the CPU workspace. On another machine, put data/
weights in those locations or set VISA_ROOT/PATCHCORE_BACKBONE_CHECKPOINT/SWINIR_X4_CHECKPOINT
to their actual local paths. Never use literal placeholder paths.
Backbone defaults to TORCH_HOME/hub/checkpoints or the standard user .cache/torch/hub/checkpoints.

```powershell
$env:VISA_ROOT = (Resolve-Path 'data/external/VisA').Path
$env:SWINIR_X4_CHECKPOINT = (Resolve-Path 'checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth').Path
.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"

$checkId = 'pcb-tiled-cuda-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/run_pcb_tiled_patchcore.py --run-id $checkId --scope model-smoke --device cuda
```

Inspect analysis/pcb_tiled_preflight/$checkId/preflight.json. Proceed only on exit0/PREFLIGHT_PASS,
matching checkpoint/source hashes and sufficient actual RAM/disk. PASS is input/payload readiness
for LIMITED smoke, not measured VRAM safety or full-pilot approval.

The following command is for the GPU operator later, NOT executed in the CPU task:

```powershell
$smokeId = 'pcb-tiled-cuda-raw-smoke-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/run_pcb_tiled_patchcore.py --run-id $smokeId --scope model-smoke --device cuda --execute
```

Preflight is recomputed by the execute command, not loaded from a possibly stale JSON.
Fixed smoke parents: first fit normal, first cal normal, first normal test, first anomaly test
in frozen inventory order. Entire board/all48 tiles each, not a GT-selected subset. Three variants
share the smoke clean-fit bank. CPU FAISS remains exact. Smoke can be slow; no speedup is claimed.
Calibration parent output is RAW only, no fitted statistics/threshold/F1 or anomaly metrics.
No GT is loaded. No dataset RGB is exported. A smoke bank is NOT the full fit bank.

Linux: use the same CLI with `.venv/bin/python` and export VISA_ROOT/SWINIR_X4_CHECKPOINT to actual
local locations. Paths are resolved at runtime; no Windows paths are embedded in code.

## What to return after a real smoke

- analysis/pcb_tiled_preflight/$smokeId/preflight.json
- outputs/pcb-tiled-smoke/$smokeId/status.json
- bank/status.json, bank.npy, selected_indices.npy, all predictions/*.npy under that output
- command/exit status, Torch/CUDA/GPU and observed RAM/VRAM or OOM details, if actually measured
- checksum verification and raw-map shape/finite/count inspection; archive partial failures too

Root COMPLETE means raw artifact completion, not validated research performance/device parity.
There should be9 native board maps:3 variants × (1 cal +2 test), with immutable bank hashes.
Do not return dataset RGB/GT/checkpoints in a public commit. Large arrays are local-only outputs.
Do not convert smoke results into full AUROC/AU-PRO or a normal-calibration claim.

## Full pilot is not executable yet

No full --execute command is supplied. v0.5 intentionally rejects it before constructing models.
After smoke, first approve the single proposed board calibration/quality rule and implement/test
its artifact lifecycle; validate unchanged native evaluator memory/lifecycle (39P visible payload
lower-bound alone≈10.91GiB for200 test boards, excluding sorting/model/index), then explicitly
review and enable a full executor. More VRAM alone is not sufficient.

Read-only full preflight, which is EXPECTED to exit2 until those prerequisites are resolved:

```powershell
$fullCheck = 'pcb-tiled-full-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/run_pcb_tiled_patchcore.py --run-id $fullCheck --scope full-pilot --device cuda
```
