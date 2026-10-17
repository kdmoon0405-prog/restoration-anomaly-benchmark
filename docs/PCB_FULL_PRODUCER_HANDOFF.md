# Streaming producer candidate and fake-process handoff

2026-10-17. Local branch `exp/pcb-full-producer-integration`, based on published
`bb22cf8a1f7073229ff615b67b3df2a100763827`. This adds CPU integration evidence;
it does not amend scientific v0.6 rules or enable full-pilot execution.

## Implemented connection

`pcb_full_producer.produce()` accepts the existing injected adapter interface
(`extract`, `bind_bank`, `predict`, `close`) and a tile transform. It requires
explicit synthetic provenance before invoking the factory. There is no real
factory default, dataset/checkpoint CLI or force option. The old full-pilot
preflight/execute guard is unchanged and tested even against a falsely passing
full-scope report. A future production entry point remains a separate review.

Normal-fit parents -> existing feature_chunks -> existing bounded save_bank ->
one read-only bank bind -> calibration/test boards -> canonical tile predictions
-> existing assemble_board -> checksummed float32 board files and original
max tile image score. Seed11, capacity262144, max chunk8192, patch28x28/D1024,
batch2 and frozen selection algorithm remain defaults. Tiny fixtures override
only their declared synthetic dimensions/grid/capacity, never native settings.

`assemble_board` still snapshots ONE board's tile maps; this is not a claim of
constant memory independent of a board's tile count. The snapshot and float64
accumulator/coverage/output are counted. No complete fit-feature cohort or
multi-variant dataset map stack is created. Calibration follows existing normal-
only per-variant rules; normalized files are streamed; each variant evaluator
has its own process and uses the unchanged exact evaluator.

Raw synthetic artifacts have a distinct kind/scope, explicit no-real-bank/
calibration/full-approval fields, no checkpoint and no research metrics. Metadata
binds source hashes/commit, geometry, input decoded RGB hashes (NOT compressed
source-file hashes), bank/index checksums and prediction shape/dtype/checksum.
Existing full frozen inventory is inspected as descriptors only. No actual PCB
RGB/GT is read by this checker and no synthetic full cohort is forged.

## Lossless RGB reuse

Only test reference boards and already transformed test tiles are spooled:

- uint8 native HWC reference NPY per test board;
- uint8 [canonical_tile_count,224,224,3] NPY per test board/variant;
- canonical boxes/order, shape/dtype and full file SHA256 in raw status.

For each tile the same prepared RGB is saved and sent to the predictor; an
in-place predictor mutation is rejected. Test tiles are transformed exactly once,
not rerun for quality. Calibration RGB is not retained for quality. RGBSpool
validates metadata and consumed file hashes. The existing quality_report reads
the saved reference and tile sequence, reuses native overlap RGB mean and computes
the existing PSNR/SSIM once per test board. Positive infinite PSNR stays explicit.
No GT reaches production or quality/calibration callbacks.

The producer writes one tile tensor through an mmap and explicitly closes it,
including partial-map validation failures. The quality reader loads ONE board/
variant tile tensor normally (up to7225344 native bytes), counted as additional
payload, not excused by mmap. Source RGB, transform/prediction buffers, map
snapshots and OS page cache are separate memory considerations.

## Process and failure lifecycle

`scripts/check_pcb_full_producer.py --run-id UNIQUE` is a small generated fixture
only. Seven sequential subprocesses:

1. Fake producer owns its model/index/scorer/bank mapping. Close and weak-reference
   checks run before exit; this is object-lifetime evidence, not allocator/VRAM proof.
2. Calibration, using normal boards and existing robust helpers, variants sequential.
3. Normalization, streaming files via existing application logic.
4. Quality, reading produced RGB only, no model factory/transform reachable.
5. Three separate variant evaluation processes; generated GT is invoked only here.

Parent waits for each child exit, validates records, then starts the next. Worker
protocol/source hashes and active phase are checked. Logs, process IDs,
perf_counter worker/launch-to-exit intervals and OS process-lifetime peak RSS are
recorded separately. No sampled continuous/global peak or VRAM measurement is
claimed. Do not sum unrelated process peaks. No worker imports Torch/FAISS/PatchCore.

BUILDING/FAILED is never valid completion. Existing outputs are rejected. Timeouts
kill/wait only the owned subprocess. On worker failure retain raw/RGB/logs for
inspection; do not relaunch into the same directory. After all stages exit and
artifacts validate, delete only the owned raw/rgb workspace. Maps/bank/status and
quality results remain. A failure during cleanup can leave partial cleanup; this
is not a transactional backup/power-loss guarantee. Completed artifact revalidation
rejects altered/missing worker/log/status/map checksums. These checks are not signatures.

Synthetic completion is `SYNTHETIC_INTEGRATION_PASS_NOT_FULL_APPROVAL`.
Raw status remains an immutable record of produced RGB checksums after intentional
spool cleanup. Those temporary RGB files cannot then be reused to rerun quality;
their already-completed quality artifact is separately bound by checksum.

## Native payload planning, not an executed native run

Frozen metadata:721/180/200 parents,34608/8640/9600 tiles,27132672 fit vectors.
Let Bmax be maximum board pixels, Ttest test tiles, Pcal/Ptest pooled pixels,
K=min(N,262144), D=1024, C=batch2*784.

| Payload | Bytes | GiB |
| --- | ---: | ---: |
| Shared bank | 1073741824 | 1.000 |
| One feature chunk | 6422528 | 0.00598 |
| All raw variant cal/test maps | 6850396800 | 6.380 |
| Lossless test RGB spool | 5236574400 | 4.877 |
| All normalized test map files | 7210944000 | 6.716 |
| Retained disk payload before RGB cleanup | 20373754176 | 18.975 |
| Retained disk payload after RGB cleanup | 15137179776 | 14.098 |

Formulas: bank4KD, indices8K, chunk4CD, raw maps12(Pcal+Ptest), normalized24Ptest,
RGB spool3Ptest +9*Ttest*224*224. Disk sums include bank/indices, not original
dataset/checkpoints, NPY headers, JSON/logs or free-space reserve. Failed runs
remain additional disk consumers. The earlier resource rehearsal's4.36GiB disk
gate covers a different one-variant temporary scenario, NOT this producer.

Producer bank-build visible scenario:2*bank+indices+chunk+3Bmax =2160510168 bytes
(2.012GiB). Prediction scenario:3*bank+indices+19Bmax+4*Tmax*224*224+6*224*224
=3261800792 bytes (3.038GiB). Conservative copies are scenarios, not measured
coexistence or library upper bounds. Model/activation/FAISS scratch/Python/runtime/
selection objects/page cache/OS reserves are excluded and must be budgeted before
future real execution. mmap does not remove those allocations.

Existing postprocessing envelopes remain: calibration24Pcal+32Bmax, evaluation
64Ptest+frozen4-connected-region payload+32Bmax, quality512Bmax; the quality
reader additionally holds one saved tile tensor. Native plan binds the frozen
498756960-byte region-mask estimate without decoding GT. Native memory rehearsal
needs a fresh technical gate and actual adequate host; its success cannot certify
this producer's model peak or additional spool disk budget.

## CPU reproduction and remaining approvals

From this implementation worktree (or activate an equivalent Python3.11 env):

```powershell
$py = (Resolve-Path ../../.venv/Scripts/python.exe).Path
& $py -m pytest tests/test_pcb_full_producer.py -q
$run = 'pcb-producer-synthetic-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $py scripts/check_pcb_full_producer.py --run-id $run
& $py scripts/smoke_test.py
git diff --check
```

In a normal clone, use that clone's activated Python rather than the worktree-
relative interpreter path. In restrictive sandbox environments give pytest a
fresh unique --basetemp under outputs/. Generated arrays/RGB/metrics/logs stay
under ignored outputs/pcb-full-producer/. Public verification must contain only
implementation/check booleans/resource observations, never fabricated PCB scores.

Remaining: teammate native postprocessing measurement/review; producer model/RSS/
VRAM and total disk budget; audited real GT callback in the eventual orchestration;
fresh actual source/checkpoint/input binding; explicit final full-execution review.
The present checker deliberately has no real factory or dataset execution path.
No inference, GPU/model smoke rerun, full bank/calibration, tuning or full pilot
is authorized. Original negative gating and full110 B/B-uncertain stay unchanged.

## 2026-10-18 memory-guard correction

The delivered native synthetic rehearsal has now passed for its recorded older
revision; this does not validate actual model/index/VRAM resources or this new
revision's native run. Board wrappers and the rehearsal now share total-cap,
already-live-array and fixed2GiB-reserve accounting. Small checker caps explicitly
include1GiB payload plus2GiB reserve and record this in their protocols. See
PCB_MEMORY_GUARD_ALIGNMENT.md for formulas, CPU boundary checks and remaining
full-execution blockers. Historical evidence above remains unchanged.
