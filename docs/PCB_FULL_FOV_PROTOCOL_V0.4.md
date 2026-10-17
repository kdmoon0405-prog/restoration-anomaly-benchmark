# PCB tiled CPU integration v0.4

2026-10-16 KST. **DRAFT_CPU_INTEGRATION / NOT_READY_FOR_PILOT**.
Actual PCB bank/calibration: **NOT_CREATED**. Existing protocols/results are preserved.
One pre-fixed synthetic plumbing baseline, not a performance-selected aggregation method.

## Implemented and fixed in this draft

New implementation `native_tiled_stream_meanmap_maxtilescore_cpu_v0_4` connects the existing
native224 geometry and bounded-bank APIs using injected NumPy callbacks. No Torch/FAISS/model
import, real dataset image/GT load, degradation, calibration or anomaly metric is required/run.

Parent descriptors carry sample/split/label/size, not image arrays. Images are provided one parent
at a time by a loader. Samples must be unique across nonempty fit/calibration/test inventories;
fit and calibration labels must be normal. Only fit parents can enter the feature generator.
Synthetic annotations are checked for binary values and source-coordinate shape only; extractor
and predictor signatures never receive GT or parent labels.

Feature callback: stacked native uint8 tiles `[B,224,224,3]` -> float32 `[B,Py,Px,D]`.
Flatten order is parent order -> canonical row-major tile order -> patch y -> patch x.
Features stream directly into the unchanged bounded-bank builder; all count/finite/chunk guards
remain active. Fit batch boundaries may cross parent boundaries but never split membership.
Future `_embed` wrapper must reshape its flat return to this contract and verify observed patch
shape/order/count. It must not call the old whole-concatenation `_fit`. This real wrapper is pending.

Predictor callback: one native tile and the read-only synthetic bank -> float32 `[224,224]` map
plus finite scalar tile image score. Each variant is a separate injected callable. The dummy
variants do not stand for actual Clean/Bicubic/SwinIR outputs or restoration quality.

### Board map and score

Map rule: snapshot tile outputs, validate sample/variant/ID/box, then reduce in canonical tile-ID
order. Accumulate raw maps in float64, coverage in uint32, divide by geometric coverage, return
float32. No clip, tile-wise min-max, GT weight, adaptive weight or learned gate. Missing/duplicate/
unknown tiles, wrong coordinates, nonfinite/wrong dtype/shape and zero coverage are errors.
Input arrival order does not change the reduction order. Buffers can be reused by callbacks
because the assembler snapshots maps before requesting the next tile.

Board score is **max of the original tile IMAGE SCORES**, NOT the maximum of the assembled map.
The same geometry/map/score rule applies to every variant. This differs from old input families
and does not establish optimal localization or normal-board calibration.
`reassemble_exact()` remains an unchanged RGB/GT identity audit, not a prediction merger.

### Persistence and errors

New output only. Overall BUILDING -> COMPLETE only after synthetic bank, all map files and
before/after bank hashes agree; failure leaves FAILED where status can be written. Bank arrays
are read-only mmap during cal/test prediction. No fit/update operation occurs in those phases.
The reader rejects non-COMPLETE or checksum/source/shape/sample/variant/label/split mismatch.
Maps use numeric file IDs, never sample text as a filesystem target, and reload one at a time.
OS power-loss durability is not claimed. Interrupted/incomplete artifacts must not be used.

## Synthetic execution contract, not PCB parameters

Toy inventory: 2 normal fit / 1 normal calibration / 2 test parents, sizes336×224 and448×336.
Toy patch grid2×2, D4, K17, seed11, feature tile batch2. Expected fit vectors32.
Variants `dummy_a`/`dummy_b`; test annotations are synthetic coordinate masks only.
This small configuration does not modify real planned D1024/K262144 or real parent split721/180/200.
The integration's actual run PROTOCOL.json freezes code/reference hashes and rules before execution.
Array payloads stay in ignored outputs/, small summaries under analysis/pcb_cpu_integration/.

## Calibration code inspected, NOT applied

Existing fusion.py helpers are potential building blocks: `robust_params()` fits median/IQR,
then std/unit fallback for a numerically degenerate scale (`1e-12` guard); `normalize()` applies
`(x-median)/scale`; `quantile_threshold()` uses normal calibration values.
The existing runner calibrates per-variant image scores and pooled pixels from normal inputs.
`fit_fusion_calibration()` additionally couples normalization to fusion methods/thresholds and
cannot simply be adopted as this no-fusion board protocol.

All board normalization formulas, before/after-merger placement, pixel pooling/weighting,
threshold quantile, fallback handling and exact usage of180 PCB normal calibration parents are
**PENDING**. Raw dummy maps/scores are saved without calibration. No calibration values or test
thresholds are computed. Existing helper float64 materialization is also a memory prerequisite.

## Other prerequisites still pending

- Actual `_embed` and detector/restorer wrapper, checkpoint identity and count/order integration proof.
- Tile-wise224→56→224 degradation/restoration and boundary/context handling; not full-board LR.
- PSNR/SSIM aggregation and overlap accounting, without double-counting source pixels.
- Native-resolution metric storage/evaluation lifecycle with unchanged metric definitions.
- Full model/upstream/scorer/index memory and actual hardware/device smoke.

Before real inference, resolve these by explicit protocol decisions, not test-performance selection.
Do not call successful dummy plumbing a GPU-ready or validated detector. Category-specific normal
fit/calibration remain separate; no Hazelnut bank/threshold reuse. Uniform patch sampling can miss
normal modes. Existing negative gating and full110 B/B-uncertain remain unchanged.

## Memory scope

Feature phase retains one parent RGB plus a bounded copied-tile list/stack and one feature batch;
producer buffering is outside the API. Bank/index/gather/finite-check budgets remain v0.3 values.
Prediction phase handles one parent/variant: owned tile-map buffer, float64 accumulator,
uint32 coverage and float32 output coexist during assembly; they are released before the next
variant. No dataset map stack is built. Readers mmap one board and may allocate a board-sized
finite-check boolean array. A caller that retains all returned arrays defeats that lifecycle.

Payload calculations and synthetic tests are NOT RSS/VRAM or runtime measurements. mmap does
not eliminate evaluator float64 copies, sorting/rank arrays, region masks or OS page cache.
The memory plan reports phases separately, without adding overlapping scenarios as a measured peak.

## Executed CPU result (2026-10-16)

`analysis/pcb_cpu_integration/tiled-dummy-20261016/`: **synthetic integration PASS**.
All 32 expected dummy feature vectors were observed, 17 stored (D=4; bank 272 bytes), six maps
were saved/reloaded with exact values and max tile scores. Bank artifact hashes were unchanged.
Synthetic tests also establish GT change/removal nonuse, batch-independent feature/bank ordering,
reused map-buffer snapshots, canonical reduction independent of input tile arrival, overlap
hand-calculation and error/overwrite/incomplete-artifact guards.

Native 1404×1070 resource scenario: tile-map buffer 9,633,792 bytes, accumulator 12,018,240,
coverage 6,009,120, output 6,009,120; source RGB 4,506,840. These are calculated payloads, not
measured native model memory. No actual PCB RGB/GT or feature was read. Actual PCB bank/
calibration remain NOT_CREATED and pilot NOT_READY_FOR_PILOT. Existing negative/full110 verdicts
are unchanged. Tests: full 208 passed; no-Torch/FAISS focused 21 passed; both CPU smokes passed.
