# CPU input binding and resource-smoke instrumentation

2026-10-20 KST. Base d88573d on the separate exp/pcb-full-producer-integration
worktree. The original exp/profiling-results-demo checkout and its existing
progress edits were preserved. No actual model, GPU, FAISS index, full bank,
calibration or anomaly-performance experiment was executed.

## Actual input-file evidence

Ignored outputs/pcb-input-binding/pcb2-input-hashes-final-20261020-180759:
all1101 RGB file hashes,100 anomaly-GT file hashes and100 normal-test no-file
policy records agree with the frozen geometry/official split. No decoding was
claimed by that hash-only artifact.

Ignored outputs/pcb-input-binding/pcb2-input-decode-final-20261020-180807:
INPUT_BINDING_VALIDATED_NOT_FULL_APPROVAL. All1101 RGB native shapes/uint8
decodings and200 test bool masks passed the new callbacks. Counts721 fit-normal,
180 calibration-normal,100 test-normal and100 test-anomaly are unchanged.
All100 anomaly masks are native/nonempty; normal masks are implicit zeros.
Four-connected regions332; existing evaluator region-mask payload498756960bytes,
not the geometry audit's eight-connected324 component count.

RGB verification68.7332422s and GT input verification4.7935433s are structural
file-audit elapsed times, NOT model runtime/throughput. No RSS peak was measured
for this audit. Protocol availability snapshot2473545728bytes passed its
96145920byte single-board array plan +2147483648byte reserve. Earlier availability
snapshot2011963392bytes and an initial blocked decode attempt are preserved;
resource state later changed, but no process/cleanup cause is inferred. No other
user process was closed and no OS/pagefile settings were changed.

Protocol/receipt hashes, CSV counts and all six audit-source hashes were
independently checked after completion. Consumed-byte RGB/GT hashes, decoded
hashes and no-GT normal policy remain in ignored CSVs. The successful protocol
truthfully records source d88573d/dirty=true before the new commit; it is not
rewritten to a later clean source or labelled as predictions.

## Model-resource tooling, not a model result

New default-preflight CLI wraps the unchanged limited model-smoke. Model factory,
extraction, bank bind, per-variant preparation/restoration, detector and close
have synchronized conditional-CUDA timing; outer elapsed is not added to child
times. Sampled RSS, OS process-lifetime high-water and PyTorch CUDA counters have
separate labels. Original exact CPU FAISS and all model/scientific settings stay
unchanged. No extra warmup/inference, alternate bank or metric was introduced.
Source/reference/protocol/official-CSV/checkpoint drift is rejected before
factory/CUDA setup; failures preserve partial raw/resource evidence.

Actual local CPU preflight at
outputs/pcb-model-resource-smoke/pcb2-model-resource-preflight-20261020-180410
is PREFLIGHT_PASS with factory/model_execution_started=false. Both checkpoint
hashes and source references match. Recorded torch2.14.0+cpu, actual_device=cpu,
cuda_available=false; this is not CUDA execution validation. The preflight's
37632-vector bank scope is NOT the full262144-bank resource requirement.

## Testing scope and remaining limits

Generated-file callback/fake-producer/quality/evaluator integration passes.
Binding/native/budget related tests75passed; no-Torch binding/budget53passed.
Resource-profiler injected tests29passed in both environments. Test-only RAM
isolation now applies to tiny in-process board/producer fixtures. Real subprocess
tests use the actual probe and are skipped only if the existing RAM prerequisite
is unavailable; no child receives fake RAM and production guards are unchanged.

The first full-suite attempt recorded21 failures/354 passes/1 skip:20 legacy tiny
tests coupled to actual desktop RAM, plus an os.replace WinError5 under the
OneDrive temp directory followed by a leftover-partial error. Failed artifacts
are preserved. No atomic-state-writer/scientific source was changed to hide this;
final tests use a fresh OS-temp directory outside OneDrive.

Final full suite:376passed/1 optional-data skip,221.69s, with no resource skips;
the generated-data subprocess paths ran with actual child resource probes.
CPU smoke passed(2 result rows). git diff--check passed. Logs remain ignored:
outputs/cpu-readiness-final-tests.log, outputs/cpu-readiness-full-tests.log,
outputs/cpu-readiness-smoke.log, outputs/input-binding-final-tests.log,
outputs/input-binding-notorch-tests.log, outputs/model-resource-focused.log,
outputs/model-resource-notorch.log and outputs/synthetic-resource-isolation-focused.log.

Original science/model/geometry/guard/protocol sources remain byte-identical to
d88573d. Dataset files, original predictions/results/hashes and old protocol
history were not edited. New code/test/docs only; data/RGB/checkpoints stay
ignored. Full native evaluation still needs its20.42GiB guard; the local15.53GiB
host is not authorized for that allocation. Remaining: separately authorized CUDA
limited resource smoke, full-bank model/index resource evidence, producer disk
budget review and explicit full-execution approval. No push/main merge/deploy.
