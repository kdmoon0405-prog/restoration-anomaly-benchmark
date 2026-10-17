# Bounded-bank CPU verification

2026-10-16 KST. Base `41d45ca`, branch `exp/profiling-results-demo`.
Execution rules/code frozen at `2026-10-16T07:53:05.290136+00:00` before selection/demo.

## Executed scope and status

- PCB planning population: 27,132,672 normal-fit patch IDs, K=262,144, D=1024, seed 11.
- Only index preselection was executed for PCB. Observed actual PCB feature vectors: **0**.
- Actual PCB bank/calibration **NOT_CREATED**; pilot **NOT_READY_FOR_PILOT**.
- Lazy SYNTHETIC stream: 1,000,003 rows, D=8, K=257, max input chunk 8,192.
- Observed/validated all 1,000,003 synthetic rows; stored 257; selected values match the
  independent row/column formula exactly. Synthetic bank payload 8,224 bytes, indices 2,056 bytes.
- Synthetic artifact COMPLETE is not a trained/created PCB bank. No actual 1 GiB bank was allocated.

No model loading, real feature extraction, fit/inference, FAISS index/search experiment,
degradation, restoration, calibration/threshold or anomaly metric was executed.
No raw RGB/GT was read; existing geometry audit was not rerun.

## Memory-bounded evidence

Uses installed CPython standard-library random.sample(range(N), k), local Random(11), then sorts.
For the actual N/K, inspected installed source has pool-branch threshold 1,048,597 < N=27,132,672:
the set-based branch is used, not a population-sized list. Near-population branch remains O(K).
Python integer/list/set and sort transient overhead is not included in NumPy payload figures.

Builder allocates `[min(N,K),D]` once, validates one chunk and gathers selected rows only;
no feature concatenation, accumulated chunk list, population-sized permutation/mask or pairwise
matrix. The lazy-stream test guards explicit bank allocation shape and checks weak references
to ensure old chunks are not retained. These checks are NOT a measured RSS/VRAM profile.
Upstream buffering/model memory is outside the builder's guarantee.

Payloads: capped bank 1 GiB; indices 2 MiB; input chunk ≤32 MiB; gather temporary ≤32 MiB;
finite-check temporary ≤8 MiB. Gather and finite-check phases differ; scenarios must not be
blindly summed as a measured peak. Hypothetical scorer+CPU-index payload 2 GiB, or three bank
copies 3 GiB, are future integration scenarios, not created allocations. Native test maps and
evaluation temporaries remain unchanged and still need a full-pipeline memory plan.

## Correctness and artifact safety

- Full pytest: **187 passed**, 60.57 s.
- Focused bounded-bank tests: **33 passed**; separate no-Torch/no-FAISS Python 3.11 environment
  **33 passed**. Both environments' CPU smoke tests passed (2 rows).
- Tests include batch-independent selection/value identity, all/partial population, endpoints,
  local RNG isolation, invalid config/indices/shapes/dtypes/nonfinite input (including unselected
  rows), short/long streams, chunk limit, lazy allocation/lifetime guards, BUILDING/FAILED rejection,
  producer/payload-write failures, checksum mismatch, read-only mmap and overwrite rejection.
- Code/geometry references and production index raw/file SHA rechecked after execution: match.
- Protected previous geometry/runners/metrics/third-party code/results have no diff.
- git diff --check passed. No dependency or actual bank/coreset setting changed.

Uniform patch sampling is a NEW bank method, not IdentitySampler or greedy coreset.
It samples the overlapping tile patch population, not physical pixels; normal-mode preservation
or anomaly performance is not established. Existing negative gates/full110 B/B-uncertain remain unchanged.

## Hashes and outputs

PROTOCOL SHA256: `ad902d280dc15ced24a0a5e7626424b3ae5849eacaa2e4364c3857c09b7124b7`.
Selected IDs (little-endian int64, no header):
`480f53ec4fbe355a3a5948e6a895dfdd63058eb903b8e108613a8e3a63afb402`.
NPY index file: `691add22b7e57066214ab12f5e098b640c236d51e612ca077c9181b5c31b1335`.

Small reports/manifests are here. Index NPY and tiny synthetic bank/status are local-only under
`outputs/pcb-bank-budget/pcb2-uniform-cap262144-20261016/`, not committed. Transfer the index
artifact or recreate under matching recorded versions and verify its SHA before future integration.

## Reproduce from repository root (PowerShell)

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_test.py
$bankRun = 'pcb2-bank-budget-replay-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/check_pcb_bank_budget.py --run-id $bankRun
git diff --check
```

Existing report/payload directories are rejected. No command triggers a real PCB experiment.
Remaining prerequisites are the pending items in `docs/PCB_FULL_FOV_PROTOCOL_V0.3.md`.
