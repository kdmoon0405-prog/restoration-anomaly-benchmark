# PCB resource-bounded bank v0.3

2026-10-16 KST. **DRAFT / NOT_READY_FOR_PILOT**.
Resource-bounded selection/CPU implementation only. Actual PCB bank/calibration: **NOT_CREATED**.
v0.1 blocked resize, v0.2 native geometry, original IdentitySampler results and runners remain unchanged.

## Single fixed design

Implementation: `uniform_global_patch_preselection_stream_v0_3`.
Known population N=27,132,672 normal-fit patch vectors, dimension D=1024 float32,
capacity K=262,144, local seed 11, input chunk limit 8,192 vectors.
The count comes from the saved native-tiling manifest: 721 fit parents ×48 tiles ×784 patches.
This is a runtime contract to validate later, not newly extracted feature evidence.

Preselect `min(N,K)` unique global IDs using CPython standard-library
`random.Random(seed).sample(range(N), min(N,K))`, then sort ascending and encode little-endian int64.
No global Python/NumPy RNG state is modified. Reproducibility records Python/NumPy versions,
algorithm, seed and exact selected-index SHA. Cross-version RNG implementation equivalence is
not assumed; archived indices and their hash are authoritative.
The generated NPY payload is local-only under outputs/. Transfer it with its hash for GPU
handoff, or reproduce with matching versions and verify the exact hash before any feature extraction.

The standard sampler does not materialize range(N) for N much larger than K; its
near-population pool branch has size O(K). Sample/sort Python lists/sets and integer objects
are O(K) auxiliary memory, not zero memory. No population-sized mask/permutation is made.

This is uniform sampling without replacement over the overlapping-tile PATCH POOL, not
uniform sampling of physical source pixels. It is NOT greedy coreset or IdentitySampler.
Overlap duplicates spatial context and rare normal modes can be missed. K is a hardware-budget
candidate, not a demonstrated optimum. No GT, calibration/test feature or test score selects K/seed.

## Stream and completion contract

Preallocate only `[min(N,K),D]`, never `[N,D]` for a large N>K, an accumulated chunk list
or a pairwise distance matrix. Consume one NumPy chunk at a time; reject non-2D/wrong-D,
non-native-float32, empty/oversized and any nonfinite input, even in unselected rows.
Do not silently cast, filter, drop, truncate or adjust N. Input short/long counts fail the run.
Selected IDs must be sorted, unique, in bounds and have exactly min(N,K) entries.
The builder releases its current chunk before requesting another. Upstream model/producer
buffering is outside this API and must be bounded by future integration.

Each new artifact directory starts BUILDING. Payloads are written with temporary names,
flushed and hashed; COMPLETE status is atomically published only after both NPY files exist.
Exceptions leave FAILED where status writes remain possible; an interrupted/unwritable
status may remain BUILDING, never a usable success. Loader rejects non-COMPLETE, missing,
checksum/shape/count/index mismatch. It hashes sequentially and returns read-only mmap arrays.
No power-loss durability beyond the OS/filesystem is claimed. Existing output is rejected.

## Global ordering and provenance

1. Fit parents in the frozen v0.2 INPUTS.csv fit-row order, not newly shuffled/sorted.
2. Parent's layout boxes in frozen row-major tile order (y then x).
3. `_embed`: input/batch order, then feature-grid row y, column x fastest.

Static evidence is PatchMaker Unfold/reshape/permute and `_embed` flattening, plus saved
bank shape 784 patches/input (28×28). Layer alignment does not change that reference patch order.
Patch-grid coordinates are NOT exact physical-pixel centers. Actual native runner wiring and
an observed-count/ordering integration check remain pending; do not infer completion from this plan.
The future adapter must fail on inconsistent patch shape/order/count, never silently reselect IDs.
It must stream `_embed` chunks into this builder, not invoke the old full-concatenation `_fit`
and merely replace its downstream sampler. No such runner integration was performed here.

Execution metadata records source commit/code SHA, geometry ID, N/K/D/dtype, RNG/seed,
selected count/index SHA, input/layout/parent-order references, versions, expected/observed/
validated/stored counts and status. No dataset image or GT is read for index selection.
Synthetic artifact status is explicitly separate from actual PCB bank creation.

## Payload budget, not measured peak memory

| Payload/scenario | Size |
|---|---:|
| Previous full IdentitySampler vectors | 103.503 GiB |
| New capped bank vectors | 1 GiB |
| Selected int64 indices | 2 MiB |
| Input chunk, D=1024 float32 | ≤32 MiB |
| Selected-row gather temporary | ≤32 MiB |
| Finite-check boolean temporary | ≤8 MiB |
| Hypothetical bank + scorer copy + CPU index | 3 GiB |

Last row is a future integration scenario, not an executed FAISS allocation. Scenarios overlap;
do not add them as a measured total. Python sample/sort overhead, allocator/runtime, upstream
model activations/prefetch, page cache and FAISS scratch are excluded. Synthetic allocation and
weak-reference guards are not RSS/VRAM measurements. Tests do not allocate a real 1 GiB bank.

Native-resolution evaluation remains unchanged: about 1.119 GiB float32 test maps/method,
2.239 GiB for one float64 copy or full-length int64 array, plus other evaluator buffers.
An index cap alone does not establish full-pipeline feasibility. No speedup or anomaly metric is claimed.

## Still pending before any pilot

- Anomaly-map overlap merger and board-level score.
- Normal calibration/normalization stage and scope, separate from fit normals.
- Tile-wise x4 and boundary treatment; not equivalent to a full-board LR image.
- Native evaluation memory/lifecycle plan with unchanged metric definitions.
- Separate PCB runner integration, checkpoint identity and hardware/device smoke.

Comparisons would use the SAME newly frozen bank for Clean/Bicubic/SwinIR; no Hazelnut bank/
threshold reuse. Changing the bank method starts a separate protocol family and does not rewrite
past conclusions. Test GT stays structure/evaluation only. No performance-selected bank tuning.
Existing negative gates and full110 B/B-uncertain remain unchanged. No model, feature extraction,
FAISS index, restoration/degradation, calibration or anomaly metric is executed by this work.
