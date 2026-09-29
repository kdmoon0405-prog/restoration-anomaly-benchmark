# Hazelnut 25-image restoration-endpoint pilot

## Status

Completed on the frozen 25-image Hazelnut development subset. This is a feasibility result, not an untouched-category estimate. The original ZIP and predictions remain outside Git; the small source CSVs and a path-normalized `results.json` are in [`results/`](results/). Source and tracked-copy SHA-256 values are in [`RAW_ARTIFACT_HASHES.csv`](results/RAW_ARTIFACT_HASHES.csv).

## Frozen source and question

Runner source commit: `95d097799c10135a982dbddf91f97b71e3ca29e6` (`exp/restoration-objective-study`). The question is whether the official PSNR-oriented and perceptual/GAN-oriented RRDB endpoints show different image-quality and downstream anomaly-localization trade-offs under one fixed x4 input. The [pre-inference design](../../docs/RESTORATION_OBJECTIVE_STUDY.md) and 25-image [manifest](pilot_manifest.csv) were not changed after viewing results.

## Conditions

- MVTec AD Hazelnut: lexical-first 5 each from good, crack, cut, hole, and print; 5 normal and 20 anomalous images.
- Canonical 224×224 RGB image → pinned BasicSR MATLAB-compatible bicubic 56×56 LR. Bicubic, SwinIR-S, RRDB-PSNR, and RRDB-ESRGAN share that LR input.
- One frozen 391-normal Hazelnut PatchCore bank, no fit in this run; WideResNet50 `layer2+layer3`, IdentitySampler, exact CPU FAISS. Source, bank, checkpoint, and manifest hashes were checked by the runner before inference.
- NVIDIA GeForce MX570 A; requested and actual model device `cuda`. No normal calibration or F1 threshold. Ground-truth masks enter only post-inference evaluation.
- Primary localization measure: pooled AU-PRO@0.3 with the existing 200-threshold implementation. PSNR, SSIM, LPIPS, Image/Pixel AUROC, and anomalous-image AU-PRO are separate measures.

## Aggregate result

These values come from the saved [`summary.csv`](results/summary.csv), not from a new inference. Higher PSNR/SSIM/AUROC/AU-PRO is better; lower LPIPS is better.

| Variant | Mean PSNR | Mean SSIM | Mean LPIPS | Image AUROC | Pixel AUROC | Pooled AU-PRO@0.3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bicubic x4 | 36.06666080860525 | 0.9299967519348921 | 0.17322952628135682 | 1.0 | 0.9847908072089188 | 0.791050335607512 |
| SwinIR-S x4 | 38.484307197115804 | 0.9540026033322406 | 0.09057324290275574 | 1.0 | 0.987827794195565 | 0.8047205871264165 |
| RRDB-PSNR x4 | 38.57639168208291 | 0.9549902730425852 | 0.08713165730237961 | 1.0 | 0.988058711263934 | 0.8075341064347228 |
| RRDB-ESRGAN x4 | 35.95409541923001 | 0.9205007114720292 | 0.04453623495995998 | 1.0 | 0.9886510759651855 | 0.8126297542363347 |

All four Image AUROCs are 1.0 on this 5-normal/20-anomaly subset. That metric does not distinguish the endpoints here. Image/pixel F1 and thresholds are null, not zero.

## Direct endpoint comparison

`RRDB-ESRGAN − RRDB-PSNR`, recalculated from the full-precision summary CSV and checked against `results.json`:

| Measure | Delta |
| --- | ---: |
| Mean PSNR | -2.622296262852899 dB |
| Mean SSIM | -0.03448956157055605 |
| Mean LPIPS | -0.04259542234241963 |
| Image AUROC | 0.0 |
| Pixel AUROC | +0.0005923647012515687 |
| Pooled AU-PRO@0.3 | +0.005095647801611869 |

Among the 20 anomalous images, direct per-image AU-PRO favors ESRGAN in 11, PSNR in 9, with no ties. ESRGAN-minus-PSNR mean is `+0.005228730586261677`, median `+0.00060070251796146`, minimum `-0.026003721611708497`, and maximum `+0.0781594382510824`. These per-image statistics are not the pooled AU-PRO delta. Descriptively, ESRGAN wins 3/5 crack, 2/5 cut, 1/5 hole, and 5/5 print; each stratum is too small for a defect-type claim. Source: [`objective_pair_per_image.csv`](results/objective_pair_per_image.csv).

## Sample-level regression versus the new-pilot Bicubic baseline

The frozen rule is per-image AU-PRO delta `< 0`; suppression means ROI-background gap delta `< 0`, and geometry candidate means gap delta `>= 0`. All counts are among 20 anomalous images per learned variant.

| Variant | Localization regression | Suppression pattern | Geometry candidate | Improvement/tie |
| --- | ---: | ---: | ---: | ---: |
| SwinIR-S x4 | 10 | 4 | 6 | 10 |
| RRDB-PSNR x4 | 8 | 3 | 5 | 12 |
| RRDB-ESRGAN x4 | 5 | 4 | 1 | 15 |

Source: [`regression_taxonomy.csv`](results/regression_taxonomy.csv). The regression subtypes are map-score descriptions, not proven feature-space mechanisms. These new-pilot Bicubic values use a different LR kernel from historical Branch A and are not appended to that earlier table as directly identical conditions.

## Observed fact and interpretation

Observed: RRDB-PSNR has higher PSNR and SSIM; RRDB-ESRGAN has substantially lower LPIPS. ESRGAN also has slightly higher pooled Pixel AUROC/AU-PRO and fewer Bicubic-relative per-image AU-PRO regressions in this fixed subset. Direct endpoint per-image AU-PRO is mixed (11 wins versus 9 losses).

Interpretation: the pilot shows a clear fidelity/perceptual-quality trade-off and a possible endpoint-dependent downstream-localization difference. The small pooled gain and 11/9 paired split do not establish a stable population advantage. A 25-image lexical-first subset is a feasibility sample, not a random representative estimate.

## What this does not support

- “GAN is better for anomaly detection,” statistical superiority, or a population-level defect-type claim.
- An objective-only causal effect: the official RRDB checkpoints differ in both training losses and training data (DF2K versus DF2K+OST). “PSNR-oriented versus perceptual/GAN-oriented endpoint comparison” is the accurate name.
- “SR removes defects” or a proven feature-suppression mechanism from the map-level taxonomy.
- Generality to industrial-camera noise/blur, other categories, or the untouched Capsule validation category.

## Decision

**GO:** prepare a separate full 110-image Hazelnut endpoint run to check whether the pilot signal persists across the complete development category. This is within-category expansion, not independent final validation, and must be a later code/experiment step. **Not yet:** full inference in this result-recording commit, feature NN follow-up, Phase C gating, Capsule, new detector, new degradation, or new fusion search.
