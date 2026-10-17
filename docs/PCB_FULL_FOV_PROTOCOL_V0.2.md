# PCB full-FOV native tiling v0.2

2026-10-16 KST. **DRAFT: geometry validation is separate from pilot readiness.**
v0.1/full-frame224 and its BLOCKED_GEOMETRY artifacts remain unchanged.
This is one specified candidate, not a resolution/stride search or a performance-selected method.

## Fixed native geometry

ID: `pcb_native224_maxstride192_halfup_v0_2`.
Native RGB and `GT > 0` are sliced at the same coordinates, with no resize, interpolation,
padding, dilation, adaptive crop, filtering or GT-dependent tile selection.
Tile size is 224×224; maximum stride 192. For each axis length L:

```text
L < 224: reject with an explicit error; no fallback transform
L = 224: starts = [0]
L > 224:
  intervals = ceil((L - 224) / 192)
  n = intervals + 1
  start[i] = round_half_up(i * (L - 224) / intervals), i=0..intervals
```

Rounding uses exact nonnegative integer arithmetic:
`(2*i*(L-224)+intervals)//(2*intervals)`. Half ties go upward, not to even.
First/last starts are 0/L-224. Tile order is row-major y then x. Boxes use exclusive x1/y1.
The coordinate map is tile `(u,v)` → source `(x0+u,y0+v)`; inverse subtracts that offset.
Native 1404×1070 inputs imply 8×6 = 48 tiles, not 48 independent boards.
Overlap duplicates context and increases bank size; it is not additional independent data.

## CPU structural rules fixed before this audit

The execution PROTOCOL.json stores rules, source commit/code hashes and input/reference hashes
before image inspection. Each image must have complete positive coverage, valid unique coordinates,
RGB/GT slices identical to the source, and exact original-coordinate reconstruction.
Overlapping RGB/GT/ID values must agree. Original binary-GT 8-connected IDs must reconstruct
exactly, including each previously unsampled ID from v0.1. These are annotation components,
not physical defect counts. Components may cross tiles; counting per-tile components is not the test.
Structural 8-connectivity does not change the existing AU-PRO implementation's 4-connectivity.

Absent official normal masks are recorded as implicit-zero arrays for this geometry check, not
fabricated official GT files. All anomaly cases/small components are retained. Source RGB and
GT SHA must match the prior frozen inventory. Reassembly here is identity checking of raw arrays,
**not an implemented anomaly-map fusion rule**.

Synthetic tests cover non-square images, exact-size and small-input handling, half-up ties,
corners, seam-crossing and one-pixel regions, multiple IDs, empty normal GT, deterministic tiles,
duplicate/out-of-bounds/uncovered boxes, inconsistent overlap and missing/wrong-shaped tiles.
Figures reuse historical fixed examples plus the lexical first normal test image. Zooms are
explanatory only, never adaptive model inputs. RGB figures stay local-only.

## Split, resource planning and no model execution

Reuse official VisA CSV, seed 11, fit ratio 0.8 and the exact prior image-level partitions:
721 fit-normal / 180 calibration-normal / 100 normal + 100 anomaly test.
All tiles inherit the parent partition; overlapping/neighboring tiles cannot cross partitions.
Manifest links relative paths, label, source hashes, size-specific tile coordinates and checksums.
Team prior pcb2 use remains unconfirmed. No claim of GT-untouched independent validation is made.

Resource arithmetic uses saved backbone/bank shape metadata, not model loading:
WideResNet50 layer2/layer3, pretrain/target embedding 1024, patchsize 3,
IdentitySampler (no coreset reduction), CPU exact FAISS. Saved 245,392 vectors / 313 fit boards
imply 784 patches per existing 224 input. New estimate is tile_count×784×1024×4 bytes.
The reference Hazelnut bank supplies shape/config only; no bank/threshold is reused for PCB.
No bank/coreset settings are changed. Payload estimates are not measured RSS, VRAM or runtime.

Current fit code collects features and concatenates them; ConcatMerger makes a copy and CPU
IndexFlatL2 stores vectors. Report separate overlapping buffer scenarios, not an additive grand total.
Map/evaluation estimates must include native H×W, float64 conversions, sorting/rank arrays and
the existing evaluator's retained per-region masks. Count 4-connected evaluation regions only for
memory planning; do not compute new anomaly metrics or alter that implementation.

## Items deliberately NOT frozen for inference

- Anomaly-map overlap merger and seam policy (raw identity reconstruction does not decide it).
- Board-level image score and quality-metric aggregation/overlap weighting.
- Normal calibration stage/domain, normalization, thresholds after board assembly.
- Tile-wise `224 → 56 → 224` degradation/restoration order, boundary treatment and naming.
  Tile-wise x4 is not a single full-board LR image or the old full-board224 x4 condition.
- Resource-feasible bank/fit plan, runner integration, checkpoint SHA and hardware/device smoke.

Before any pilot, resolve these by an explicit protocol revision, without test performance selection.
Category-specific bank and held-out normal calibration are still not created. No Hazelnut reuse.
Planned comparisons remain Clean/Bicubic-x4/SwinIR-S-x4; primary pooled AU-PRO@0.3,
secondary Pixel AUROC, Image AUROC, PSNR/SSIM. Test GT is only for structure/evaluation,
not checkpoint/threshold/weight/geometry performance tuning. Full-board evaluation must assemble
maps/masks in source coordinates before evaluation, not treat tiles as independent test images.

This native tiling family changes context/scale and cannot be pooled with old center-crop or
full-frame224 results as identical preprocessing. Existing negative gates and full110 B/B-uncertain
remain unchanged. No PCB/Capsule inference, degradation, fit, FAISS benchmark or metric ran here.

Actual audit artifacts and the post-run verdict are under
`analysis/pcb_geometry/pcb2-native224-tiling-20261016/`. The run's output is never overwritten.

## Post-run structural verdict (2026-10-16)

**GEOMETRY_IDENTITY_PASS / NOT_READY_FOR_PILOT**. All 1,101 images reconstruct exactly;
100 official anomaly masks and 1,001 implicit normal background arrays were checked.
Coverage is 1–4 per source pixel; no uncovered pixels, errors or lost original components.
All 324 original 8-connected IDs are preserved. The 19 IDs lost by v0.1 reconstruct at exactly
their original source areas. This is identity preservation, not a restoration/detection result.
Fit/calibration/test tiles: 34,608 / 8,640 / 9,600. Original 721/180/200 parent split is unchanged.

Unchanged full IdentitySampler fit implies 27,132,672×1,024 float32 vectors:
103.503 GiB index payload alone. Three simultaneous vector payloads in the current fit path
are approximately 310.509 GiB, excluding other allocations; this is not a measured peak.
Post-fit retained scorer features plus index payload are approximately 207.006 GiB.
The current CPU host reports 15.53 GiB physical RAM; even index payload alone exceeds it.
CUDA availability does not eliminate the deliberately CPU exact-FAISS index requirement.
Do not launch full fit or silently reduce the bank to fit memory. Resource design needs an
explicit subsequent decision; the candidate has not become a GPU-ready experiment.

One method's full-board test float32 maps require 1.119 GiB payload, three methods 3.358 GiB.
An evaluator float64 score copy or one full-length int64 order/rank array each needs 2.239 GiB.
Its 332 four-connected annotation regions retain about 0.465 GiB boolean region masks.
These are separate, sometimes overlapping allocations, not a verified evaluator peak or runtime.
No anomaly metric was calculated. Detailed formulas, counts and limitations are in resource_estimate.json.
