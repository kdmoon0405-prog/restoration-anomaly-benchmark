# Full Hazelnut restoration-endpoint confirmation (result)

Status: one valid full110 execution completed and verified. This closes the restoration-endpoint GPU branch per `docs/RESTORATION_ENDPOINT_FULL_HAZELNUT.md`. Source run: `outputs/restoration-objective/hazelnut-full110-gpu/`. Derived analysis: `analysis/restoration_objective_full/derived/`. Preregistration commit: `fddad881276da120ffcce1362ce062f85ea4759a`.

All numbers below are read directly from the saved `results.json`/`summary.csv` and the frozen analysis outputs; none is recomputed by hand.

## 1. Aggregate quality/detection (110 images: 40 normal, 70 anomaly)

| Variant | PSNR | SSIM | LPIPS | Image AUROC | Pixel AUROC | Pooled AU-PRO@0.3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bicubic_x4 | 36.483 | 0.93218 | 0.17212 | 0.99821 | 0.98406 | 0.82034 |
| swinir_x4 | 38.795 | 0.95441 | 0.09244 | 0.99821 | 0.98497 | 0.84275 |
| rrdb_psnr_x4 | 38.861 | 0.95521 | 0.08882 | 0.99893 | 0.98459 | 0.84528 |
| rrdb_esrgan_x4 | 36.164 | 0.92065 | 0.04469 | 1.00000 | 0.98510 | 0.85208 |

F1/threshold fields are null for all four variants (no calibration was performed, as frozen).

## 2. Direct RRDB comparison and final case

All direct deltas are RRDB-ESRGAN minus RRDB-PSNR.

- **P** (full110 pooled AU-PRO delta): `+0.006790420`
- **D70** (mean paired per-image AU-PRO delta, 70 anomalies): `+0.005109973` (median `+0.000746`, min `-0.036286`, max `+0.251776`; ESRGAN wins 39/70, PSNR wins 31/70, ties 0)
- **CI** (paired bootstrap, seed 2026, 5,000 repeats, mean per-image delta): `[-0.000907, +0.013954]`
- **D50** (pilot-unseen 50 anomalies): `+0.005062470` (median `+0.001137`, min `-0.036286`, max `+0.251776`; ESRGAN wins 28/50, PSNR wins 22/50)
- Quality-trade-off reproduction (`mean_delta_psnr < 0 AND mean_delta_lpips < 0`): **true** (`-2.6963 dB`, `-0.04413`)

Applying the frozen rule: `P > 0`, `D70 > 0`, `D50 > 0`, but `CI.lower = -0.000907` is not `> 0`, so the agreement condition for **A** fails on the CI leg alone (all three directional signs agree; uncertainty does not exclude zero). `C` is not met (directions are positive, not negative). Final case: **B**. Since the CI `[-0.000907, +0.013954]` is not fully contained in `[-0.01, +0.01]` (its upper bound exceeds `0.01`), the descriptor is **B-uncertain**, not B-small.

Pooled AU-PRO (`P`) is a point estimate; the bootstrap CI quantifies uncertainty of the mean per-image delta (`D70`), not of `P`. They are different estimands and are not combined into one interval.

The two official RRDB checkpoints differ in training data (DF2K vs DF2K+OST) as well as training objective, so this result compares two shipped *endpoints*, not an isolated loss-function effect.

## 3. Per-image localization delta distribution (vs new MATLAB-Bicubic, 70 anomalies)

| Variant | min | q25 | median | q75 | max | \|Δ\|≤0.01 count/rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| swinir_x4 | -0.0697 | -0.0019 | +0.0014 | +0.0118 | +0.2200 | 44/70 (62.9%) |
| rrdb_psnr_x4 | -0.0807 | -0.0033 | +0.0010 | +0.0145 | +0.2704 | 41/70 (58.6%) |
| rrdb_esrgan_x4 | -0.1001 | -0.0004 | +0.0029 | +0.0130 | +0.2927 | 43/70 (61.4%) |

Most per-image deltas for all three learned restorers sit close to zero; a minority of images carry the largest magnitude moves in either direction.

## 4. Frozen tau magnitude sensitivity (Bicubic-relative, `count(delta < -tau)` / 70)

| tau | swinir_x4 | rrdb_psnr_x4 | rrdb_esrgan_x4 |
| --- | ---: | ---: | ---: |
| 0.00 | 29 (41.4%) | 30 (42.9%) | 22 (31.4%) |
| 0.005 | 11 (15.7%) | 15 (21.4%) | 9 (12.9%) |
| 0.01 | 8 (11.4%) | 11 (15.7%) | 8 (11.4%) |
| 0.02 | 5 (7.1%) | 8 (11.4%) | 4 (5.7%) |
| 0.05 | 2 (2.9%) | 2 (2.9%) | 2 (2.9%) |

The strict-sign regression rate at `tau=0` (29/70, 30/70, 22/70) drops sharply as the magnitude threshold grows; no single tau is treated as the "true" cutoff. Two-sided 95% Wilson intervals for the `tau=0` rate: swinir `41.4% [30.6, 53.1]`, rrdb_psnr `42.9% [31.9, 54.5]`, rrdb_esrgan `31.4% [21.8, 43.0]`.

Direct RRDB-pair sensitivity (`all_anomalies`, 70): at `tau=0.01`, 9 images favor ESRGAN by more than `0.01` and 7 favor PSNR by more than `0.01`; 54/70 fall within the `±0.01` band. The `pilot_unseen_within_category` subset (50) shows the same pattern (6 vs 6 beyond `tau=0.01`, 38/50 within band).

## 5. Baseline tercile diagnostic (70 anomalies sorted by Bicubic per-image AU-PRO, lexical ties; groups 23/23/24)

| Variant | Group | Mean Bicubic AU-PRO | Mean Δ | Strict regression rate |
| --- | --- | ---: | ---: | ---: |
| swinir_x4 | low | 0.7296 | +0.0363 | 26.1% |
| swinir_x4 | middle | 0.9490 | +0.0008 | 39.1% |
| swinir_x4 | high | 0.9902 | -0.0014 | 58.3% |
| rrdb_psnr_x4 | low | 0.7296 | +0.0424 | 30.4% |
| rrdb_psnr_x4 | middle | 0.9490 | -0.0008 | 39.1% |
| rrdb_psnr_x4 | high | 0.9902 | -0.0017 | 58.3% |
| rrdb_esrgan_x4 | low | 0.7296 | +0.0551 | 17.4% |
| rrdb_esrgan_x4 | middle | 0.9490 | +0.0013 | 26.1% |
| rrdb_esrgan_x4 | high | 0.9902 | -0.0009 | 50.0% |

All three learned restorers show a descriptive negative association between Bicubic baseline AU-PRO and the restoration delta (Spearman: swinir `-0.422`, rrdb_psnr `-0.315`, rrdb_esrgan `-0.528`): images with an already-high Bicubic baseline tend to show smaller or negative deltas, and the strict regression rate is highest in the high-baseline tercile for every variant. This is a ceiling/baseline-association diagnostic, not a claim of regression-to-the-mean causality.

## 6. Quality–localization descriptive association

Per-model Spearman rho (ties by average rank), each learned restorer vs its own Bicubic reference, per anomalous image:

| Variant | PSNR-gain vs AU-PRO-gain | LPIPS-improvement vs AU-PRO-gain |
| --- | ---: | ---: |
| swinir_x4 | -0.029 | -0.075 |
| rrdb_psnr_x4 | -0.150 | -0.126 |
| rrdb_esrgan_x4 | -0.206 | +0.139 |

These per-image correlations are weak and inconsistent in sign across models; they do not show that a given image's quality gain predicts its localization gain. This is a descriptive, non-causal association limited to this set of images and does not support a general claim that PSNR or LPIPS is an unreliable proxy.

## 7. Supporting taxonomy (2×2) and base-rate context

`delta_per_image_aupro < 0` defines a regression; among regressions, `delta_roi_bg_gap < 0` is "suppression", otherwise "geometry candidate" (map-level description only):

| Variant | regression & gap<0 | regression & gap≥0 | non-regression & gap<0 | non-regression & gap≥0 |
| --- | ---: | ---: | ---: | ---: |
| swinir_x4 | 13 | 16 | 11 | 30 |
| rrdb_psnr_x4 | 9 | 21 | 10 | 30 |
| rrdb_esrgan_x4 | 13 | 9 | 30 | 18 |

Negative-gap base rate is similar between regression and non-regression images for swinir/rrdb_psnr (≈27–45% vs ≈25–30%), but higher for rrdb_esrgan in both groups (59% regression, 63% non-regression) — a negative ROI–background-gap delta is common for this variant generally, not specific to regressions. This taxonomy and the historical selected-case NN-distance checks describe map-level/feature-distance patterns; because the anomaly maps are themselves derived from those same NN distances, they are consistency diagnostics, not an independently proven mechanism.

## 8. Pilot20 overlap reproducibility

The 20 Hazelnut images shared with the original 25-image pilot were re-evaluated inside this full110 run and compared against the stored pilot25 artifact: 720 compared values, max absolute difference `2.98e-08`, 0 mismatches at `atol=rtol=1e-5`. The full run reproduces the original pilot numerically.

## 9. Pilot-unseen50 direction and pilot-unseen85 secondary result

The 50 anomalies absent from pilot25 show the same direction as the full 70 (`D50 = +0.005062`, ESRGAN 28/50 vs PSNR 22/50), consistent with `D70`.

The pilot-unseen85 within-category subset (35 normal + 50 anomaly, every image absent from pilot25) gives, per variant, pooled AU-PRO `0.830319 / 0.855865 / 0.858417 / 0.864750` (bicubic/swinir/rrdb_psnr/rrdb_esrgan) and a pooled RRDB delta of `+0.006333`, the same sign as `P`. This is secondary confirmation inside the same development category, not an independent dataset or held-out test set, and it does not redefine the A/B/C case above (which uses `P`/`D70`/`CI`/`D50` only).

## 10. Runtime, provenance, and interpretation limits

See `EXECUTION_RECORD.md` for full runtime/provenance detail. Summary: GPU `NVIDIA GeForce MX570 A`, `fit_performed=false`, end-to-end `wall_clock_seconds=3563.56` (~59.4 min) for the full110 run; all manifest/checkpoint/bank/source-commit hashes matched their frozen expected values, and all 8 output artifact hashes were independently recomputed and matched the values recorded in `results.json`.

**Interpretation limits.** This is a within-category (Hazelnut) development-data stability check, not an independent validation category; Capsule was not used, and no untouched-category final-generalization claim is made here. The official RRDB-PSNR/RRDB-ESRGAN checkpoints differ in training data as well as objective, so no part of this result is an objective-only causal claim about the training loss. The quality trade-off (lower PSNR/SSIM, lower — better — LPIPS for ESRGAN) is reproduced and is a substantive result; the localization direction is positive on every pre-specified summary (`P`, `D70`, `D50`) but the bootstrap CI includes zero, so it is reported as case **B (B-uncertain)**: a quality trade-off with a small and not-yet-distinguishable-from-zero mean localization difference, not a proven ranking in either direction. The taxonomy and NN-distance-style diagnostics describe anomaly-map patterns and are not used, here or elsewhere in this document, as evidence of a causal feature-space mechanism, and restoration is not characterized as removing or preserving defects in a mechanistic sense.
