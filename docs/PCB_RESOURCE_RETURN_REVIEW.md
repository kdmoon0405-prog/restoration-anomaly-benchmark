# Reviewing returned limited-smoke measurements

2026-10-20. scripts/review_pcb_model_resources.py is read-only and imports no
model/CUDA/FAISS runtime. It accepts a returned profiler folder, not a dataset,
checkpoint or inference command. Existing folders and source/output overlap are
refused. It writes a fresh review.json with its own checker-source hash.

Checks include root/protocol/resources/timing/raw-status hashes, locally reviewed
source/reference byte hashes, limited scope and no-metric/no-full-approval flags,
raw parent/variant/native-size inventory, feature counts, consumed RGB receipts,
present raw-file hashes and optional bank metadata. Original data/checkpoints
are NOT independently rehashed by this checker. Hash consistency is not an
independent attestation that remote execution actually occurred.

Timing CSV intervals must be finite, completed, disjoint, contained in the outer
interval and match recomputed call counts/sum/min/max. Numeric consistency uses
1e-9 relative/absolute serialization tolerance, not a research selection cutoff.
RSS samples, process-lifetime high-water and CUDA cumulative counters are checked
for internal consistency. No outer+child time or unrelated peak sum is used.
CUDA cumulative maxima are not stage-local peaks or whole-system VRAM.

CPU and injected fixture returns never count as actual CUDA evidence. A reported
CUDA classification additionally needs CUDA availability/counters, actual-model
flags, the fixed real37632-vector cohort and frozen RGB receipts. No classification
approves the full262144 bank, producer or pilot. independent_remote_execution_verified
is always false: consistent metadata is not an independent observation of the
remote machine. CUDA-labelled metadata fixtures in unit tests are not actual GPU
results. The checker does not compare
against a non-instrumented run or conclude that cached VRAM is a leak.

Missing heavy arrays are allowed ONLY with explicit PARTIAL_OR_METADATA_ONLY
coverage and the exact unverified file list. If supplied bytes have the wrong
hash, review fails. Even ALL_DECLARED_FILE_HASHES_VERIFIED does not assert an
independent NPY shape/finite-content check: no arrays are loaded. Disk/RSS values
measured remotely are not compared with the size of a metadata-only ZIP.

Required return: status.json, PROTOCOL.json, resources.json, stage_times.csv and
raw/status.json. Include raw/bank/status.json when possible. Raw bank/maps may be
transferred separately without pushing them into Git. Failed/preflight-only
returns correctly produce REJECTED_NOT_FULL_APPROVAL, never fake completion.

From a clone containing the reviewed source version and its activated Python:

```powershell
$review = 'analysis/pcb_model_resource_review/' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/review_pcb_model_resources.py --run $env:PCB_RESOURCE_RETURN --output $review
$temp = Join-Path ([IO.Path]::GetTempPath()) ('sr-resource-review-' + [guid]::NewGuid().ToString('N'))
python -m pytest -q tests/test_pcb_resource_review.py --basetemp $temp
```

PCB_RESOURCE_RETURN must point to the unpacked returned run root. The default
source root is the local clone; mismatched/unknown source bytes are rejected,
not silently upgraded. Keep the received original immutable. Current tests use
explicitly injected generated fixtures only; no actual GPU return exists yet.

## Local verification (2026-10-20)

Full pytest: 399 passed, 1 optional-data skip in178.95s. Reviewer tests in the
Torch/FAISS-free environment:23 passed in13.67s. Existing CPU smoke passed with
2 result rows. Fresh OS-temporary pytest directories avoid conflating test
filesystem issues with source/artifact validity. A real local CPU preflight-only
folder was correctly rejected; it is not a completed model/resource execution.
Timing/counter tests use generated fixtures, including explicitly synthetic
CUDA-labelled metadata, not actual GPU measurements. Original scientific,
model, geometry, memory-guard and v0.6 protocol sources remain unchanged relative
to4b3368e. No push, full approval or actual model/native execution.
