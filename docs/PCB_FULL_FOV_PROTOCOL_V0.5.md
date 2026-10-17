# PCB native tiled adapter and guarded execution v0.5

2026-10-16 KST. DRAFT / NOT_READY_FOR_FULL_PILOT.
Actual PCB bounded bank/calibration: NOT_CREATED. Real model smoke: NOT_RUN.
Preserve v0.1–v0.4, crop/resize families and historical results.
Negative gating and full110 B/B-uncertain remain unchanged.

## Fixed implementation contract

Use v0.2 native224/max-stride192/half-up coordinates, unchanged INPUTS.csv parent order,
seed11 and v0.3 uniform global-patch preselection, capacity262144, D1024, chunk≤8192.
Normal parents remain721 fit /180 calibration; test100 normal +100 anomalous. No exclusion,
GT-dependent tile selection, dilation, resize or category-bank/threshold reuse.

v0.3 explicitly specifies ONE shared bank: extract clean native RGB tiles of PCB normal FIT
parents only. Clean/Bicubic-x4/SwinIR-S-x4 query that same bank. No fit from degraded/restored/
calibration/test inputs. This sampled bank is not IdentitySampler/greedy coreset. The upstream
IdentitySampler object is not called: stream the bounded builder, never PatchCore.fit/_fill_memory_bank.

PatchCore source fcaa92f124fb1ad74a7acf56726decd4b27cbcad, WideResNet50-2 ImageNet V1,
layer2/3, patchsize3, pretrain/target1024, NN=1, upstream map resize/Gaussian smoothing,
CPU exact FAISS with4 workers. uint8→float32/255→ImageNet mean/std, NO spatial transform.
`_embed(detach=False, provide_patch_shapes=True)` must return28×28 and B×784×1024 float32;
reshape B,y,x,D without reordering. Fit order is parent→tile→patch-y→patch-x, x fastest.
CPU tests run actual vendored embedding operations on fabricated features, not a real backbone.

Load strictly from explicit local state dict with weights_only=True; instantiate backbone with
weights=None, never a downloading pretrained loader. Checkpoint SHA256:

- backbone V1: 95faca4d11227dddf8633dbb5ff6c8a9003c1aa5b8945c73834b8007b10950b8
- SwinIR-S x4: 09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e

Backbone hash was read from the existing cache, corresponding to torchvision's legacy
pretrained=True V1 file wide_resnet50_2-95faca4d.pth; do not substitute V2.
SwinIR source6545850fbf8df298df73d81f3e8cba638787c8bd and network code hash are recorded.

## Single tile-wise x4 candidate, fixed before predictions

Each native RGB224 tile → Pillow bicubic56 LR. Bicubic: same56→224 Pillow bicubic.
SwinIR: SAME56 LR, existing lightweight x4 wrapper, tile56, overlap0, window8, output224 RGB.
No outside-tile context, adaptive halo, full-board LR or extra crop/padding. 56 is divisible by8;
existing wrapper needs no window padding. Preserve wrapper clamp/rint uint8 conversion.
Tile SR boundary effects are unmeasured; full FOV does not mean full-board restoration context.

Raw maps: canonical tile-ID float64 sum / geometric uint32 coverage → float32.
Board image score=max original tile IMAGE scores, not map max. No clip, tile minmax,
normalization before merger, GT weights or fusion.

## Board calibration/quality proposal, full execution remains blocked

v0.4 left placement/pooling unapproved. Record ONE proposed candidate for review, not a
retroactive approved decision. No values are computed or test-selected:

1. Use all180 held-out normal calibration parents, immutable fit bank; collect each variant's
   raw assembled board maps and max-tile board scores separately.
2. Fit image median/IQR on180 scores and SEPARATE map median/IQR on pooled native board pixels.
   Each physical pixel appears once per board; pixel-weighted pooling, no overlap double count.
3. Reuse fusion.robust_params/normalize: (x-median)/scale; IQR→std→unit fallback and1e-12
   numerical guard. No fit_fusion_calibration, fusion, per-tile or test-image normalization.
4. If reporting threshold/F1, recommend0.99 normal quantile separately per variant/image/map,
   using existing quantile_threshold/NumPy linear quantile. 0.99 comes from both existing runners,
   not test scores; transform thresholds/test values with the same fitted normalization.
   This is not a guarantee of test FPR. Fit/calibration/test remain disjoint.
5. RGB quality: native overlap arithmetic mean in float64 → rint ties-to-even → clip[0,255]
   → uint8 board. Existing PSNR/SSIM against original native RGB once per TEST parent, report
   parent-level means, not tile means. Clean identity PSNR can be infinity; do not fabricate a
   finite replacement. GT is never used in reconstruction/calibration/quality.

Tile transforms and RGB assembler are implemented/testable; full calibration/quality/evaluation
artifact orchestration is NOT enabled. Status: PROPOSED_BOARD_CALIBRATION_AND_QUALITY.
Primary remains pooled AU-PRO@0.3; secondary Pixel AUROC/Image AUROC/PSNR/SSIM.
No test-based checkpoint/preprocessing/threshold/weight reselection or new metric.

## Preflight, limited model smoke, full pilot

Default CLI scope full-pilot is model-free preflight. It checks metadata/checkpoint/source hashes,
manifest/split counts, image/mask PATH existence, device and payload estimates. It does NOT
read RGB/GT content, load checkpoints, create models/index, transform images, predict or evaluate.
Torch may be imported to query CUDA; model libraries are not imported. Exit0=pass, exit2=blocked.
Invalid inputs/cuda unavailable raise explicit errors. CPU_ADAPTER_TEST_PASS comes only from
separate tests, not preflight. Preflight PASS is not real smoke or full readiness.

`--scope model-smoke --execute` is a separate raw diagnostic: FIRST fit normal, FIRST calibration
normal, FIRST normal test and FIRST anomalous test in frozen inventory order; all canonical tiles.
Same capacity CAP/seed, different N/selected IDs from full population, explicitly recorded.
Do not promote smoke bank/threshold/results to full research. NO calibration/threshold/quality/
anomaly metrics/GT. Save raw board maps/scores, immutable bank and provenance in new output only.
Errors leave FAILED when status can be written; factory failure before payload creation leaves
preflight only. Injected fake adapters test the same body without real backbone/search/restoration.

Full-pilot scope ALWAYS blocks in v0.5, including --execute, before model construction; no override.
Actual PCB bank/calibration remain NOT_CREATED until an explicitly authorized future execution.

## Resource gate and remaining prerequisites

Bank1GiB + scorer merge1GiB + CPU index vector1GiB may coexist. Chunks/gather/finite checks,
board buffers, model/activations/workspaces are additional. Calculated payloads are NOT measured
peak/RSS/VRAM or guaranteed sufficiency. Available-RAM cap is a technical guard, not research tuning.

Unchanged evaluation.py pixel_metrics makes float64 maps; binary_roc_auc retains label/positive/
order/sorted_scores/ranks. Visible simultaneous lower-bound scenario:39 bytes/test pixel
(4 map+1 mask+8 score+1 uint8 label+1 positive+8 order+8 sorted_score+8 ranks).
For300456000 pixels:11717784000 bytes (~10.91GiB), excluding sort scratch/model/index/caller copies.
AU-PRO separately keeps region boolean masks/unique-score buffers. Scenarios overlap; don't sum
as measured peak. mmap does not remove evaluator float64/sorting allocations.

Before full pilot: approve board-calibration/quality proposal and implement/test artifact lifecycle;
validate exact native-evaluation peak/lifecycle without metric changes; review actual hardware
smoke, checkpoint/device/order/count evidence. No full command is currently safe to execute.
