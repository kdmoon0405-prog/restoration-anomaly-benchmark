# Screw four-endpoint comparison — result (one execution, rules frozen in `docs/RESTORATION_ENDPOINT_SCREW.md`)

## Provenance

- Run `outputs/restoration-objective/screw-full160` (local only), executed 2026-11-01, wall time 3,064.5 s, MX570 A
  - command: `run_restoration_objective_pilot.py --cohort screw160 --device cuda --with-lpips`
  - source commit `54cf3c7` (dirty: pre-existing untracked files only)
  - torch 2.14.0+cu126, LPIPS 0.1.4
  - `results.json` SHA-256 `f8b3113e…4ad5`; the CSV/NPZ hashes are in `results.json.artifact_sha256`
- Cohort: all 160 Screw test images (41 good, 119 anomalous), manifest `b680d671…51ec`
- Bank: existing Screw 320-normal bank, loaded and not refit (`fit_performed=false`)
- Derived: `derived/` from `scripts/analyze_restoration_endpoint_category.py`, which reads saved CSVs only
- MATLAB-bicubic family: none of these numbers is subtracted from the historical Pillow-Bicubic Screw results

## Aggregate (test 160; pooled metrics)

| variant | PSNR | SSIM | LPIPS ↓ | Image AUROC | Pixel AUROC | AU-PRO@0.3 |
| --- | --- | --- | --- | --- | --- | --- |
| bicubic_x4 | 35.532 | 0.9525 | 0.2161 | 0.4792 | 0.9511 | 0.8016 |
| swinir_x4 | 37.953 | 0.9685 | 0.0975 | 0.6864 | 0.9714 | 0.8594 |
| rrdb_psnr_x4 | 38.282 | 0.9698 | 0.0975 | 0.7196 | 0.9763 | **0.8785** |
| rrdb_esrgan_x4 | 34.954 | 0.9499 | **0.0500** | 0.7090 | 0.9709 | 0.8654 |

## Primary endpoint pair: RRDB-ESRGAN − RRDB-PSNR

- **Quality:** ΔPSNR −3.328 dB, ΔSSIM −0.0199, ΔLPIPS −0.0474. The fidelity-vs-perceptual trade-off is
  reproduced: ΔPSNR<0 and ΔLPIPS<0.
- **Pooled AU-PRO:** −0.0131. ΔPixel AUROC −0.0054, ΔImage AUROC −0.0107.
- **Per-image AU-PRO over 119 anomalies:**
  - mean D = −0.0236, median −0.0143, min −0.234, max +0.281
  - PSNR better on 80, ESRGAN better on 39, 0 ties
  - paired bootstrap of the mean (5,000 repeats, seed 2026): 95% CI [−0.0369, −0.0100]
- **Frozen case: C** (P<0, D<0, CI.upper<0).
  - Interpretation: on Screw, the perceptual/GAN endpoint localized worse than the PSNR endpoint, even though its
    LPIPS was better.
  - This is an official-endpoint difference only. The checkpoints also differ in training data (DF2K vs DF2K+OST),
    so it is not an objective-only cause.

### By defect type (direct ESRGAN − PSNR per-image AU-PRO)

| defect | n | mean | median | ESRGAN/PSNR wins | mean Δ ROI–bg gap |
| --- | --- | --- | --- | --- | --- |
| manipulated_front | 24 | +0.0108 | +0.0033 | 13/11 | +0.230 |
| scratch_head | 24 | **−0.0789** | −0.0597 | 4/20 | −0.215 |
| scratch_neck | 25 | **−0.0419** | −0.0150 | 3/22 | −0.165 |
| thread_side | 23 | +0.0002 | +0.0069 | 12/11 | +0.298 |
| thread_top | 23 | −0.0058 | −0.0087 | 7/16 | +0.541 |

The negative mean comes mainly from the two scratch types. For those, the ROI–background gap also fell (a
suppression-like map pattern). The other three types are near zero or mixed. This is descriptive: 23–25 images per
type, no per-type test.

## Bicubic-relative context (each learned restorer)

- Strict-sign localization regressions out of 119, with Wilson 95% intervals:
  - SwinIR 22 (0.185 [0.125, 0.264])
  - RRDB-PSNR 18 (0.151 [0.098, 0.226])
  - RRDB-ESRGAN 32 (0.269 [0.197, 0.355])
- Median per-image gain vs Bicubic: +0.067, +0.077 and +0.038 respectively.
- Baseline terciles (39/39/41): regressions concentrate where Bicubic was already high. Spearman(baseline,
  delta) is −0.67, −0.77 and −0.62. This is a ceiling/baseline association, not a mechanism.
- Spearman(PSNR gain, AU-PRO gain): 0.25 / 0.34 / 0.25. Spearman(LPIPS improvement, AU-PRO gain):
  0.13 / 0.07 / −0.03. These are descriptive only.

## Direction vs Hazelnut full110 (two categories = two observations, not a population estimate)

| quantity (ESRGAN − PSNR) | Hazelnut | Screw | direction |
| --- | --- | --- | --- |
| ΔPSNR | −2.696 | −3.328 | agree |
| ΔSSIM | −0.0346 | −0.0199 | agree |
| ΔLPIPS | −0.0441 | −0.0474 | agree |
| Δ pooled AU-PRO | +0.0068 | −0.0131 | **disagree** |
| Δ Pixel AUROC | +0.0005 | −0.0054 | disagree |
| Δ Image AUROC | +0.0011 | −0.0107 | disagree |
| mean per-image D | +0.0051 | −0.0236 | disagree |
| case | B (B-uncertain) | C | disagree |

The image-quality character of the two endpoints is consistent across both categories. The localization ranking is
not: small and uncertain on Hazelnut, PSNR-favoured on Screw. Better perceptual quality (LPIPS) did not translate into
better defect localization, and the sign of the downstream effect depends on category and defect type.

## Limits

- One bank and seed per category; the 119 images are paired repeated measurements, not independent replicates.
- Screw informed earlier (Pillow-Bicubic) questions, so it is not untouched validation.
- LPIPS is a natural-image metric.
- The defect-type split is descriptive.
