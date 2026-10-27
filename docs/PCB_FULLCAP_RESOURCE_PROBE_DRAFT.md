# Full-cap synthetic resource probe, engineering draft

2026-10-27. Delivery target: `exp/pcb-full-producer-integration`; local feature
branch: `exp/pcb-fullcap-resource-probe`. Fetch the new delivery revision before
using this CLI: it is not present in the old2f418c0 checkout. Publication of this
engineering draft is not authorization to execute the resource probe/full pilot.

The accepted limited GPU report is still37,632 vectors/4 parents. Its measured
outer1073.347s and sampled/lifetime RSS1.675/1.689GiB do not certify full-bank
resources. Detector986.460s includes CPU FAISS plus other work; it is not a
separate FAISS timer. The metadata ZIP does not contain11 reported raw arrays.

## Fixed scope and what success would mean

- Synthetic float32 payload(262144,1024), seed11, generated in8192-row chunks.
  This is NOT a PCB fit bank, selected-index artifact, coreset or training result.
- Two generated uint8 RGB224 tiles; existing clean/bicubic-x4/SwinIR-S-x4 paths;
  exactly six detector calls. No feature extraction/fit/calibration/GT callback.
- Existing pinned models and CPU exact IndexFlatL2/four-worker scorer are reused.
  No model, seed, geometry, bank sampling, metric or production setting changes.
- Maps/scores are checked only for shape/finite values, then discarded. No
  research predictions, quality/anomaly metric, threshold or native board maps.
- Default preflight hashes old accepted CUDA evidence, current bound/frozen
  source/submodules and both publisher checkpoints. It allocates no large arrays
  and never imports Torch/FAISS. Live CUDA is checked only by opt-in execution.

An actual successful probe would show coexistence for THIS synthetic payload
and six queries. It would not validate actual full-fit selection, actual-bank
contents, native380-board producer, representative throughput or full pilot.
`full_bank_validated`, `actual_pcb_bank_created` and `full_pilot_approved` remain
false. Tiny injected CPU tests use a different completion status and cannot be
reported as actual CUDA/full-cap evidence.

## Resource accounting and failure behavior

Planning scenario:three full bank copies +two784x262144 float32 distance arrays
+one generation float/bool chunk +query workspace +the ENTIRE previous small-run
OS RSS peak +unchanged2GiB RAM reserve. This intentionally overlaps quantities;
it is an estimated planning scenario, not a measured simultaneous peak or upper
bound. Unknown FAISS/BLAS/runtime/page-cache allocations may exceed it.
Disk gate includes1GiB payload, metadata margin and existing1GiB disk reserve.
No cap/shape/scope override is exposed by the CLI.

Execution repeats current RAM/disk gates and requires live CUDA/free VRAM at
least the old reserved peak; that VRAM test is only a floor. No CPU fallback.
Original files/hash drift, existing output, incomplete state and unowned output
are rejected before model setup. Workload is finite, but there is no hard
per-FAISS-call timeout. Run the CLI as its own process and retain shell exit code.

The temporary resource-only NPY is deleted after successful query/cleanup/
monitor validation. Failures preserve their partial payload and status for
diagnosis; do not repeatedly accumulate failed1GiB payloads without reviewing
disk space. Owned adapter references are closed; no allocator cache clear or
self-asserted process exit/VRAM leak conclusion. Record sampled RSS separately
from OS lifetime peak; CUDA counters are not whole-system VRAM. Drive free-space
change is not exclusive output size. No unrelated peaks or outer/child sum.

## Commands for a future separately authorized GPU operator

Use the existing CUDA Python and actual checkpoint paths. New checkouts do not
inherit .venv/weights or the accepted reference run. Point PCB_RESOURCE_REFERENCE
to the existing `pcb-resource-juhyung-20261027-161115` run directory, not its parent
or the preflight-only directory. A transferred metadata-only copy is sufficient
for reference validation; it does not supply the new probe's checkpoints.

```powershell
$check = 'pcb-fullcap-probe-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_fullcap_probe.py --run-id $check --smoke-run "$env:PCB_RESOURCE_REFERENCE"
```

Only after actual PREFLIGHT_PASS, review of blockers and separate execution
authorization (not given by this draft):

```powershell
$run = 'pcb-fullcap-probe-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_fullcap_probe.py --run-id $run --smoke-run "$env:PCB_RESOURCE_REFERENCE" --execute
```

Outputs under outputs/pcb-fullcap-probe/run-id:PROTOCOL/status/resources JSON and
stage_times.csv. Real completion status is
FULLCAP_SYNTHETIC_RESOURCE_COMPLETE_NOT_FULL_APPROVAL, not the old limited-smoke
kind. The old review_pcb_model_resources.py deliberately does NOT accept this
new artifact kind. Return original metadata plus shell command/environment/exit
record; never package a synthetic bank as a fitted research bank. Future result
review must check this new scope before any full-pilot decision.

Current local work runs tiny fake adapters only and a no-execute preflight. No
actual CUDA/model/FAISS/full-cap allocation or native evaluation is run locally.

## CPU verification

Full suite:429 passed/1 optional-data skip in180.96s. After final state/timing
metadata additions, all30 new tests were rechecked with Torch/FAISS imports
explicitly denied:30 passed in5.57s. This is import-blocked testing using the
normal environment, not a claim of a freshly installed backend-free environment.
The old temporary no-Torch environment was broken(distutils/pytest startup);
its failure log is preserved and the environment was not modified.

The existing CPU smoke passes. A real local no-execute preflight reports a
required8.283056GiB including the unchanged reserve; inadequate current RAM is
blocked before NPY/model allocation. Historical preflights preserve their own
source commit/dirty flag and snapshots. Fake tests use at most4096 float values,
never a hidden1GiB allocation, and the CLI exposes no fixture/shape override.
