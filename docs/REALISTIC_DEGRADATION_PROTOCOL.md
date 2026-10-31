# Realistic-LR degradation × restoration model family v1 (frozen before test inference)

Status: frozen 2026-10-31 before any test inference of this family. Owner: 심주형. Family id
`realistic_lr_degradation_v1`. Code: `src/sr_anomaly/realistic_degradation.py`,
`scripts/run_realistic_degradation.py`. Separate from the bicubic endpoint family; no number from that family is
subtracted from this one.

## Question

Under one controlled extra LR degradation (noise, blur or JPEG), how do a classical bicubic upsample, a
bicubic-trained SR model (SwinIR-S), and an officially released realistic-degradation SR pair (Real-ESRNet vs
Real-ESRGAN) compare in image quality, normal-calibrated detection risk and localization? This is a model-by-model
performance/risk comparison under synthetic degradations. It is not a claim about real camera acquisition, and not
an objective-only causal claim.

## Restoration pair (selected before test performance)

`RealESRNet_x4plus` vs `RealESRGAN_x4plus`, official [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)
(BSD-3-Clause) release assets v0.1.1 / v0.1.0.

| | Real-ESRNet x4plus | Real-ESRGAN x4plus |
| --- | --- | --- |
| Architecture | RRDBNet 23 blocks, 64 feat, grow 32, x4 | same |
| Training data / degradation | DF2K+OST, high-order blur/resize/noise/JPEG synthesis | same |
| Objective | L1 | L1 + perceptual + GAN (initialised from Real-ESRNet) |
| File SHA-256 (computed at download; publisher gives none; size 67,040,989 B matches API) | `a820b9bd…81df` | `4fa0d389…82f1` |

Why: the task (blind x4 SR of blurred/noisy/compressed LR) matches this protocol's inputs, unlike the controlled
MATLAB-bicubic ESRGAN pair. Architecture, data and degradation pipeline are shared, so the pair differs mainly in
objective. However, Real-ESRGAN is fine-tuned from Real-ESRNet, so the two are not independent models, and nothing is
attributed to the loss alone. Resources: ~16.7M parameters each, 56→224 inference on the existing GPU; no new venv is
needed. Weights load with `strict=True` from the pinned BasicSR `rrdbnet_arch.py` (commit `8d56e3a…`). Only its
registry/logger/DCN imports are stubbed; RRDBNet does not use them. Inference follows the official `RealESRGANer`:
RGB float [0,1], no tile/pre-pad, clamp, `rint`×255 → uint8. **Deviation:** fp32 instead of the official default
fp16, for deterministic comparison with the other models. Restormer is a denoising/deblurring model, not x4 SR, and is
not included.

Context models: `bicubic_x4`, the BasicSR MATLAB bicubic x4 used by the endpoint family, and `swinir_x4`
(SwinIR-S classical x4, bicubic-trained, existing pin `09fad24e…`). Total: 4 restorers.

## Degradation (rows fixed)

Canonical clean 224×224 uses `Resize(256, bilinear)+CenterCrop(224)`. LR is BasicSR MATLAB bicubic ×0.25 with
antialias, clipped and `rint` to RGB uint8 56×56. That is identical to the endpoint family. Then **exactly one**
extra operation on LR uint8 (0..255 units):

1. `none`
2. `noise_s5`, `noise_s15`: i.i.d. per pixel and channel N(0, σ²), σ ∈ {5, 15} in 8-bit units, added in float64,
   then `rint` (half-to-even) and clip to [0,255]. RNG is `numpy.random.default_rng(seed)` with
   `seed = little-endian int of sha256("realistic_lr_degradation_v1|seed11|<category>|<sample path>|<condition>")[:8]`.
   It is independent of processing order.
3. `blur_s0.8`, `blur_s1.6`: separable float64 Gaussian, σ in LR pixels, radius ⌈3σ⌉, normalised kernel,
   reflect-101 border (`numpy.pad(mode="reflect")`), `rint`, clip.
4. `jpeg_q90`, `jpeg_q50`: Pillow JPEG encode at that quality with defaults (4:2:0 chroma subsampling, no
   optimize), then decode to RGB. The Pillow and libjpeg versions are recorded per run.

No noise × blur × JPEG products are included. All 4 restorers receive the same degraded LR bytes.

## Split, bank, calibration

- Categories: MVTec AD Hazelnut and Screw, all official test images (110 = 40+70; 160 = 41+119), lexical order.
- Fixed split of `train/good`: sorted paths, `default_rng(11).permutation`, first `round(0.2 n)` → calibration
  normals (Hazelnut 78, Screw 64), rest → fit (313, 256). New family, so a new **clean-normal** bank per category is
  fit once on the clean canonical fit images. Settings are the frozen PatchCore settings (WRN50 layer2+3, 1024/1024,
  patch 3, IdentitySampler, CPU exact `IndexFlatL2`) with seed 11. The bank is reused for all 7×4 conditions. There
  is no degraded/restored bank and no bank-domain change in this family.
- Calibration per (category, condition, restorer): the calibration normals pass through the same degradation and
  restorer. Then existing `fusion.robust_params` (median/IQR) is fit on calibration image scores and, separately, on
  pooled calibration pixels, and the existing `quantile_threshold(q=0.99)` on the normalized values. Test uses those
  fixed values only. GT never enters inference, the bank or calibration.

Planned: 2 categories × 7 degradations × 4 restorers = **56 dataset-evaluation conditions**. Completed conditions are
reported against this plan.

## Outcomes

- Primary: pooled AU-PRO@0.3 (existing 200-threshold implementation, 4-connectivity).
- Secondary: Pixel AUROC, Image AUROC, PSNR/SSIM/LPIPS(Alex) of the restored image vs clean canonical, and
  calibration-threshold risk: image false-alarm rate on test normals, image miss rate on test anomalies, image F1 and
  pixel F1 at the calibrated thresholds.
- Per anomalous image: per-image AU-PRO@0.3, Pixel AUROC, ROI/background mean and gap, defect area.
- Descriptive comparisons per category×condition:
  - Real-ESRGAN − Real-ESRNet;
  - each restorer − Bicubic;
  - each condition − `none` within each restorer.
- Uncertainty: paired bootstrap of the mean per-image AU-PRO delta (Real-ESRGAN − Real-ESRNet) over that cell's
  anomalies, 5,000 repeats, seed 2026. This is descriptive; 14 cells are reported without a multiplicity-corrected
  test or model selection.

Reporting distinguishes repeated measurements on the same images/bank from independent categories (2) and seeds (1).

## Execution

Units are (condition, restorer). Each unit saves raw float32 calibration/test maps and scores, its restored PNG cache
and a receipt (hashes). Resume skips verified receipts and refuses a different code/config/bank. One category per
process; GPU for backbone/SR only.
