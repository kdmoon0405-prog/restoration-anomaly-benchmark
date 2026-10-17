# PCB board calibration, quality and process lifecycle v0.6

2026-10-17 KST. CPU implementation adopted by explicit user request, NOT full-pilot approval.
Preserve v0.1–v0.5 and every prior result. Negative gating/full110 B/B-uncertain unchanged.
Actual PCB bank/calibration NOT_CREATED; real GPU smoke NOT_REVIEWED; full execution disabled.

## Adopted single rule, before real results

No conflict was found between v0.5's proposal and existing fusion/metric functions. Adopt it
as the current separate native-tiling protocol, not a retrospective change to earlier documents:

- One PCB CLEAN normal-fit shared bank for Clean/Bicubic-x4/SwinIR-S-x4. Fit721, calibration180,
  test100 normal/100 anomaly, frozen parent/tile/patch order, seed/bank/geometry unchanged.
- Raw tile maps → board overlap mean first; image score=max original tile IMAGE scores.
- Per variant: image median/IQR on180 normal BOARD scores; SEPARATE pixel median/IQR on all
  assembled normal calibration BOARD pixels. Each physical pixel once per board; pixel-weighted
  pooling, not tile pooling or equal-board weighting. No fit/test predictions select statistics.
- Reuse robust_params/normalize/quantile_threshold unchanged: median/IQR, std/unit fallback,
  1e-12 numerical guard; fixed0.99 normal quantile if threshold is needed. No threshold search.
  Apply the SAME fitted normalization to test scores/maps. Thresholds are in normalized domains.
  This does not guarantee a target test FPR. No fusion function or new weighting.
- Native RGB overlap mean in float64, rint ties-to-even, clip[0,255], uint8. Existing PSNR/SSIM
  once per TEST board, arithmetic parent means, no overlap/tile double counting. Positive infinite
  PSNR is retained explicitly as JSON string "Infinity", never replaced by a finite value/null.
- GT accepted ONLY by detection evaluation. Primary pooled AU-PRO@0.3, secondary Pixel/Image
  AUROC, PSNR/SSIM. Existing metric definitions, four-connectivity, threshold generation, ties,
  max-FPR interpolation/integration are unchanged. Geometry's eight-connectivity is unrelated.

## Implemented artifact path

pcb_board_analysis.py reads COMPLETE raw artifacts, verifies parent/split/row/path inventory,
bank provenance/hashes and each consumed map's hash/shape/dtype/finite values. Calibration reads
ONLY calibration map values; test map validation is deferred until application. Metadata can bind
test checksums without allowing test values/labels to affect statistics. Real model-smoke output
is explicitly rejected as a full calibration cohort. Production input requires the exact frozen
721/180/200 inventory and reserved full-pilot-raw scope; no real producer is enabled in this version.

Calibration stores separate variant params/thresholds plus raw-source hash, rule ID, normal sample
inventory and pixel counts. Loader rejects incomplete/changed/source/rule/count mismatches.
Application streams one test map at a time and saves float64 normalized maps/scores, binding raw
and calibration status hashes. No overwrites or nested source/output mutation. FAILED artifacts
remain invalid; this is not a cryptographic authenticity/signature or power-loss guarantee.

Quality takes a native RGB loader and ALREADY PRODUCED variant tile iterator. It does not load
or run a restoration model, read GT, or export dataset RGB. A future real producer must supply
its existing restored tiles/RGB without rerunning inference merely for quality. Full producer
orchestration remains a separate approval task; no synthetic output is a real restoration result.

## Memory and lifecycle

Calibration: one variant's float64 pixel pool. Fit existing robust_params, normalize the pool
BOARD BY BOARD with existing normalize, then run the unchanged exact quantile_threshold. This
avoids a second whole normalized cohort array but NOT median/quantile/std copies. No approximation,
subsampling or external-sort evaluator is introduced. Each variant helper returns scalars only.

Evaluation: one variant's float64 normalized stack + boolean masks, not all three variant stacks.
No extra full raw float32 stack. Exact existing evaluate_predictions is called. Per-board binary
GT/shape/label checks and4-connected region-count memory guard precede that call. Different native
test shapes are rejected; never resize/pad to satisfy the legacy evaluator. Caller must bind actual
GT files to the frozen audit before a future real run; native binary mask callback is eval-only.

Synthetic checker uses SEPARATE processes: fake raw prediction → calibration → normalization →
quality → one evaluation process PER variant. Parent waits for each worker to exit before starting
the next. Model/index/scorer references are explicitly closed on success/error in the real smoke
adapter too. Reference-release tests are not proof that OS RSS/VRAM caches shrink; process exit
provides the stronger lifetime boundary. No worker imports/executes a real backbone/restorer.

Let Pcal be pooled calibration pixels, Ptest test pixels, Bmax largest native board pixel count:

- calibration float64 pool8Pcal; pool+quantile-copy scenario16Pcal;
  technical planning envelope24Pcal+32Bmax, not a measured peak.
- normalized test map files for3 variants24Ptest bytes on disk, in addition to raw artifacts/bank.
- evaluator visible simultaneous scenario36Ptest: float64 maps8, caller masks1, binary masks1,
  uint8 labels1, positive1, order8, sorted scores8, ranks8. Additional scratch/advanced-index buffers
  are excluded from that visible scenario. v0.5's39P was a different raw-float32+copy scenario.
- technical evaluator envelope64Ptest+known region-mask bytes+32Bmax; checked again after GT region
  counts. Quality RGB payload34Bmax; technical quality envelope512Bmax for additional image/SSIM
  work. Envelopes are explicit safety scenarios, NOT proven library upper bounds or tuning rules.

All estimates exclude unvalidated workspace/runtime/OS effects. Native peak remains UNVALIDATED;
mmap does not remove quantile, rank, sort or region-mask allocations. Current available RAM is
recorded at execution; GPU teammate RAM remains unconfirmed without evidence. Even a generous
RAM reading cannot automatically approve full inference/evaluation.

## Verification and remaining gates

scripts/check_pcb_board_pipeline.py runs GENERATED synthetic fixtures only (toy2 fit/2 calibration/
2 test,336×224, grid2×2/D4/K7). It freezes code hashes first, runs process-separated stages, compares
calibration/normalization/quality/evaluation against unchanged helper references, and records only
synthetic checks in analysis/. Arrays/metric values remain explicitly synthetic local outputs.

Separate statuses: CPU_CALIBRATION_QUALITY_TEST_PASS; MEMORY_LIFECYCLE_VALIDATED for synthetic
ownership/process lifetimes ONLY; native BLOCKED_MEMORY; GPU smoke not reviewed; full NOT_READY.
No actual PCB/Capsule model/feature/SR/degradation/metric execution is authorized by this checker.

Next before full pilot: review actual GPU raw smoke and host RAM/VRAM; measure/validate exact native
postprocessing working set on adequate hardware; integrate a full raw/RGB producer with process
handoff and audited GT loader; explicitly review full execution approval. Full --execute still blocks.
