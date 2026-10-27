# Two-operator PCB smoke handoff

2026-10-27. Delivery branch: `exp/pcb-full-producer-integration`.
It includes code baseline `ef2ca8614cb1067a26af034a45ecf339b9d58a4f`.
Record the actual fetched HEAD for every new run; historical local-only commit
IDs in older reports are not instructions to fetch unpublished history.

## Receive the code without replacing existing work

For an existing clean checkout, fetch and inspect before switching. Preserve
notebook edits, untracked files, environments and past successful/failed runs.
Do not reset, clean, force-push or merge into main. If a separate checkout is
needed, explicitly reuse the existing CUDA Python/data/checkpoint paths.

For a first installation in an unused parent directory:

```powershell
git clone --branch exp/pcb-full-producer-integration https://github.com/kdmoon0405-prog/restoration-anomaly-benchmark.git
Set-Location restoration-anomaly-benchmark
git rev-parse HEAD
git merge-base --is-ancestor ef2ca8614cb1067a26af034a45ecf339b9d58a4f HEAD
git -c core.autocrlf=true submodule update --init -- third_party/SwinIR third_party/patchcore-inspection
```

Required fixed submodules: SwinIR `6545850fbf8df298df73d81f3e8cba638787c8bd`,
PatchCore `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`. Do not update them to
upstream HEAD or change frozen hashes to accommodate a different checkout.

A new clone/worktree does not contain `.venv`, data, checkpoints or raw outputs.
Use Python3.11. Existing operators should reuse their working CUDA environment.
First-time operators create a dedicated environment, install a compatible CUDA
Torch/torchvision pair using the official PyTorch installer instructions for
their actual GPU/driver, then install this project's `.[dev,legacy]` extras.
Do not overwrite another environment or silently substitute CPU Torch.
FAISS stays `faiss-cpu`/CPU exact search; Anomalib and other restoration models
are not prerequisites. Record exact installation commands, versions and Python
executable. Stop CUDA execution if the actual device is unsupported.

Commands below assume this environment is active as `python`:

```powershell
python -m pip check
python -c "import sys,torch,torchvision,faiss,timm; print(sys.executable); print(torch.__version__,torchvision.__version__); print(torch.version.cuda,torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
python scripts/setup_pcb_gpu_inputs.py --visa-root data/external/VisA
python scripts/setup_pcb_gpu_inputs.py --visa-root data/external/VisA --verify-only
$env:VISA_ROOT = (Resolve-Path 'data/external/VisA').Path
```

If data already exists elsewhere, use its actual path consistently instead of
downloading another copy. Checkpoint overrides are `PATCHCORE_BACKBONE_CHECKPOINT`
and `SWINIR_X4_CHECKPOINT`. Setup verifies the licensed pcb2 Release bundle and
two original-publisher checkpoints through `configs/pcb_gpu_inputs.json`.
It runs no model. It needs no MVTec/full-VisA download and does not put inputs
in Git. The bundle contains1101 RGB,100 GT, official CSV and legal files;
its274645313bytes are an input archive size, not an execution disk/RAM budget.

## Established GPU operator: instrumented limited smoke

Read `PCB_MODEL_RESOURCE_SMOKE.md` and `PCB_RESOURCE_RETURN_REVIEW.md`.
Preserve the prior raw CUDA smoke and native synthetic rehearsal.

```powershell
$check = 'juhyung-resource-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/profile_pcb_model_smoke.py --run-id $check --device cuda --data-root "$env:VISA_ROOT"
```

Only an actual `PREFLIGHT_PASS`/exit0 permits the following limited run, whose
fresh preflight is rechecked. Never lower a resource guard or stop other user
processes to force a pass.

```powershell
$run = 'juhyung-resource-smoke-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/profile_pcb_model_smoke.py --run-id $run --device cuda --data-root "$env:VISA_ROOT" --execute
$review = 'outputs/pcb-model-resource-review/juhyung-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/review_pcb_model_resources.py --run "outputs/pcb-model-resource-smoke/$run" --output $review
```

Expected top-level status: `MODEL_SMOKE_RESOURCE_COMPLETE_NOT_FULL_APPROVAL`;
raw status: `COMPLETE`. Keep outer versus child timing, sampled RSS versus OS
lifetime high-water, and CUDA allocated/reserved cumulative counters separate.
Do not sum overlapping timing or unrelated peaks. Instrumented latency includes
probe/synchronization overhead; post-exit nvidia-smi is not a measured peak.
The consistency checker does not attest remote execution or inspect array
contents. Missing transferred payloads remain explicitly unverified.

## First-time GPU operator: clean-install independent raw smoke

Read `PCB_INPUT_BINDING_HANDOFF.md` and the limited-smoke portions of
`PCB_TILED_GPU_HANDOFF.md`. Run the CPU tests/smoke before CUDA:

```powershell
$temp = Join-Path ([IO.Path]::GetTempPath()) ('sr-first-gpu-tests-' + [guid]::NewGuid().ToString('N'))
python -m pytest -q --basetemp $temp
python scripts/smoke_test.py
$audit = 'jihyuk-input-hashes-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_input_binding.py --run-id $audit --data-root "$env:VISA_ROOT" --execute --hashes-only
$check = 'jihyuk-first-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/run_pcb_tiled_patchcore.py --run-id $check --scope model-smoke --device cuda --data-root "$env:VISA_ROOT"
```

After `PREFLIGHT_PASS`/exit0 only:

```powershell
$run = 'jihyuk-first-raw-smoke-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/run_pcb_tiled_patchcore.py --run-id $run --scope model-smoke --device cuda --data-root "$env:VISA_ROOT" --execute
```

This tests first-install/input/model execution on another host, not strict
cross-device numerical parity or independent replication of dataset performance.
Unmeasured peaks remain unmeasured. Do not treat successful metadata checks as
an independent array-content audit. Inspect the saved raw status/files directly.

## Return records and remaining gates

Both tasks use the fixed1-fit/1-calibration/2-test parents, all native tiles,
one subset bank(37632,1024) and9 native finite board maps. Neither fits full
calibration nor creates thresholds or research metrics. Preserve dirty-source
truth and original failed runs; never overwrite an output/run-id.

Return exact command, HEAD/submodules/environment, exit codes, preflight,
status and bank/status, file-hash inventory and a short review. The instrumented
operator also returns PROTOCOL/resources/stage_times and checker review.json.
Keep received bytes immutable. List omitted bank/maps; transfer needed arrays
privately, never through Git. Keep datasets/checkpoints/private journals out of
commits. Neither GPU operator needs to commit/push these run artifacts.

The subset bank does not validate full262144-bank resources. Full-producer disk
and lifecycle, actual-model full-bank resources and explicit final approval
remain separate prerequisites. Full execution gates stay closed. No category,
metric, geometry, seed, bank, gating/fusion or threshold search is authorized.

## CPU publication checks (2026-10-27)

Full pytest:397 passed/3 skipped in205.37s; existing CPU smoke:2 rows passed.
Two real generated-worker tests required2186018816 available bytes including
the unchanged2GiB reserve, versus1848459264/1848520704 measured at focused
confirmation; they were skipped without overriding resources. The remaining
skip needs optional MVTec data. Focused confirmation:1 passed/2 skipped.
This is not a new native-memory or actual-model validation. Both GPU operators
must still run their own fresh preflight. No actual fit/inference or native180/200
execution was performed for publication.
