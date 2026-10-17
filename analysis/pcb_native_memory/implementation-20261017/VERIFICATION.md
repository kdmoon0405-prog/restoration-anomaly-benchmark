# Native memory rehearsal implementation verification

2026-10-17 KST. Isolated branch `exp/pcb-native-memory-readiness` from public
`d732574`; original `exp/profiling-results-demo`/`79a1c0f` and incoming CUDA ZIP,
NPY/status/preflight/review were not modified. No unpublished original history is
part of this branch. No actual model, restorer, FAISS, full cohort prediction or
GPU execution was run. Full runner remains unchanged and blocked.

## Executed checks

Final small resource run (ignored local output):
`outputs/pcb-native-memory/small-execute-20261017-final/`

- Status MEMORY_REHEARSAL_COMPLETE_NOT_FULL_APPROVAL; scope small only.
- 2 calibration/2 test generated336x224 boards; no dataset/real GT read.
- 12 sequential workers exited0: three variants times four stages.
- All workers recorded empty Torch/FAISS/PatchCore runtime imports.
- Maximum of INDIVIDUAL worker OS lifetime peak working sets:109289472 bytes
  (104.23MiB). This is NOT summed process memory, native/full peak, or VRAM.
- Minimum worker-sampled available system RAM:2670620672 bytes; sampled, not a
  guarantee of the machine's continuous minimum.
- Variant workspaces removed; resource CSV and12 worker JSON hashes validated
  by load_completed_rehearsal(). No performance numbers were exported.
- Python3.11.16, NumPy2.4.6, Pillow12.3.0, scikit-image0.26.0; Windows64-bit.

Final native PRE-FLIGHT ONLY (ignored local output):
`outputs/pcb-native-memory/native-preflight-20261017-final/`

- Frozen721/180/200 inventory, native1404x1070. Actual dataset root supplied only
  for official CSV verification and GT existence checks; GT was not decoded.
- Status BLOCKED_MEMORY; available2856202240 bytes at that check.
- Required21923497568 bytes: unchanged19776013920-byte evaluation planning
  envelope plus fixed2147483648-byte OS/runtime reserve.
- Required free disk4681310976 bytes: one-variant workspace plan plus1GiB margin.
- No work directory, native arrays or worker was created. No native --execute run.
- Native scores, quality, actual calibration, CPU/CUDA parity and model/VRAM
  peaks remain untested.32GB total RAM does not imply this gate passes.

Final full suite:280 passed,1 skipped (optional MVTec-data integration test),
124.98s. Local retained log:outputs/native-memory-final-pytest-20261017-c.log.
No-Torch/FAISS environment:22 focused unit tests passed. Existing CPU smoke passed
with2 generated result rows. Initial default sandbox pytest temp directory and
Git/MSYS/LFS status helpers were restricted: tests used a unique workspace-local
basetemp; full-suite verification uses approved normal MSYS execution. No guards,
system settings, installed dependencies or research definitions were relaxed.

Pre-commit evidence records public base d732574 and dirty=true while new source
was being implemented. Content hashes bind the actual source used; do not relabel
that historical metadata clean or substitute a later commit hash into it.
All12 recorded source-file hashes from the final small run match the final
implementation checkout. Existing runner/evaluator/calibration/model adapter
sources have no diff against d732574; only the new resource path was added.

## Reproduction from repository root

```powershell
python -m pytest -q
python scripts/smoke_test.py
$small = 'memory-small-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_native_memory.py --run-id $small --scope small --execute
$check = 'memory-native-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_native_memory.py --run-id $check --scope native --data-root data/external/VisA
git diff --check
```

In this restricted local test environment, pytest used a fresh unique directory
under outputs/ via --basetemp. Native preflight here is EXPECTED to return2, not
permission to lower its budget or run full. See the dedicated handoff for32GB
operator commands and prerequisites; only that later operator may perform a
conditional model-free native resource run after fresh PREFLIGHT_PASS.
