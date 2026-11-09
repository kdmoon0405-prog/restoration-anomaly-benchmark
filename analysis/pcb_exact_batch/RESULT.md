# PCB exact-search query batching — result (run-20261109-211614, one execution)

## Setup (fixed before running)

- **Axis:** query tiles per FAISS search call ∈ {1, 2, 4}. Nothing else varies.
- **Kept fixed:**
  - Bank: the reviewed real bank `pcb-real-fit-bank-20261029-163524`, 262,144 × 1024 float32, hash-verified, equal to the raw-run admission, not refit.
  - Index: the upstream scorer bind, CPU `IndexFlatL2` exact, k=1, squared L2, mean over k. 4 OMP threads were verified, matching execution family A.
  - Queries:
    - 6 clean native 224 tiles, chosen by inventory order and tile ordinal only, with no GT or scores: `Normal/0000.JPG` (first calibration board) tiles 0–2 and `Anomaly/000.JPG` (first test board) tiles 0–2.
    - 784 patches per tile.
    - One embedding array (6×784×1024) was reused by every condition and kept local, SHA-256 in `RECORD.json`.
- **Embedding cost** is separate: CUDA `_embed` took 0.249 s for all 6 tiles and is excluded from search timing.
- **Schedule:** 1 warmup pass per condition, then 3 measured passes. The condition order rotates each round: [1,2,4], [2,4,1], [4,1,2]. No condition was added.
- **Batch 4 calls:** with 6 tiles, a batch-4 pass is one 4-tile call plus one 2-tile call.
- **Environment:**
  - MX570 A laptop, Python 3.11.2, torch 2.14.0+cu126, faiss 1.15.1.
  - Branch `exp/pcb-exact-batch-juhyung`.
  - Command: `scripts/profile_pcb_exact_batch.py --output analysis/pcb_exact_batch/run-20261109-211614 --array-dir outputs/pcb-exact-batch/run-20261109-211614 --board-recheck`

## RAM preflight (before allocation; `ram_preflight.csv`)

- **Terms:** bank mmap + scorer merged copy + index storage (3 × 1 GiB), 2 GiB model scenario, fixed queries, per-condition scratch estimate with a concurrent query copy, and a 2 GiB OS reserve.
- **Result:** 7.55–7.57 GB required vs 20.2 GB available. All three conditions passed, and none was BLOCKED_MEMORY.
- **Measured:** RSS was 1.17 GB before bind and 4.39 GB after bind. Sampled peak RSS was 4.47 GB in every condition, and per-condition max RSS after a call differed by ≤ 8 MB. The scratch estimate (6–26 MB) is below what this RSS sampling can resolve.

## Timing (`condition_summary.csv`, `timing_passes.csv`, `timing_calls.csv`)

| query tiles per call | queries per call | calls per pass | pass search s (mean, min–max of 3) | s per tile | speed vs 1 |
| --- | --- | --- | --- | --- | --- |
| 1 | 784 | 6 | 20.59 (20.33–20.77) | 3.43 | 1.00× |
| 2 | 1,568 | 3 | 17.92 (17.48–18.28) | 2.99 | 1.15× |
| 4 | 3,136 | 2 | 13.74 (13.16–14.25) | 2.29 | 1.50× |

- Thermal state was not measured.
- **Spread across rounds:** the three measured passes per condition span ≤ 9%.
  - Batch 1 was flat: 20.67 → 20.33 → 20.77 s.
  - Batch 2 and batch 4 fell slightly from round to round: 18.28 → 17.99 → 17.48 s and 14.25 → 13.80 → 13.16 s.
  - The batch-2 warmup pass (14.86 s) was faster than its measured passes.
  - This drift is observed only and its cause is unknown (cache, frequency or thermal).
- **The ordering is robust to it:** the slowest batch-4 pass is faster than the fastest batch-2 pass, and the slowest batch-2 pass is faster than the fastest batch-1 pass.

## Equivalence vs batch 1 (`equivalence.csv`; rtol 1e-5, atol 1e-6)

| tiles per call | distance max / mean abs diff | strict allclose | NN index changes | score max abs diff | map max / mean abs diff |
| --- | --- | --- | --- | --- | --- |
| 2 | 1.14e-5 / 4.2e-7 | False | 1 of 4,704 (distance-tied within tol) | 0 | 4.6e-6 / 3.2e-7 |
| 4 | 1.14e-5 / 3.3e-7 | False | 1 of 4,704 (distance-tied within tol) | 0 | 4.3e-6 / 2.6e-7 |

- Repeats within each condition were bitwise deterministic.
- Batching changes the float32 BLAS block summation order. The distances are not bitwise identical and narrowly fail the strict tolerance, but every tile image score is identical. Map differences are ≤ 4.6e-6, against patch distances of 0.45–1.84 on these tiles, a relative difference of about 1e-5.
- Path identity: our downstream (patch distances → max / upsample + Gaussian) reproduces `adapter.predict` bitwise for all 6 tiles (`path_identity_vs_predict.csv`).

## What this answers

1. **Search share (measured, small sample):**
   - The earlier 97.5% "detector incl. CPU FAISS" share merged backbone and search.
   - On these fixed tiles, exact search alone is 3.43 s per tile at batch 1, while the CUDA embedding is about 0.04 s per tile.
   - The full-cohort detector stage averaged 3.50 s per tile, so search is about 98% of that stage, given the cohort was one tile per call.
   - This is an estimate from 6 tiles in one thermal state. It is not a re-measurement of the cohort.
2. **Batching helps on this machine:**
   - Four tiles per call cut search time by about a third (1.50×) at the same exact results, up to float32 summation order.
   - A naive projection of 54,720 tiles × (3.43 − 2.29) s gives about 17 h saved on a full cohort. This is an estimate only and extrapolates beyond 6 tiles.
3. **Not done and not claimed:**
   - No larger batch, thread count, GPU FAISS, approximate index, or bank/coreset change.
   - No change to the completed cohort's family A. A batched execution would be a new execution family recorded as such, because maps are not bitwise identical.
