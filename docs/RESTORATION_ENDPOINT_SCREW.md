# Screw restoration-endpoint comparison (frozen before inference)

Status: frozen 2026-10-31 before any Screw endpoint inference. No Screw four-endpoint prediction exists at this commit.
Owner: 심주형. This is a separately designed follow-up study requested by the project owner after the Hazelnut full110
branch was closed (`RESTORATION_ENDPOINT_FULL_HAZELNUT.md` says expansion needs a separately designed study; this is it).
The Hazelnut text, artifacts and its B-uncertain result are unchanged.

## Question

Does the fixed four-endpoint comparison (MATLAB Bicubic, SwinIR-S, RRDB-PSNR, RRDB-ESRGAN, all from the same x4 LR)
behave the same way on Screw as on Hazelnut? Report the quality trade-off, pooled/per-image localization differences,
defect-wise magnitudes, and direction agreement with Hazelnut. Negative or opposite results are kept.

Screw is a second MVTec category, not untouched validation: the historical Pillow-Bicubic Screw Branch A result informed
earlier questions. The checkpoints differ in training data (DF2K vs DF2K+OST) as well as objective; no objective-only
causal claim is made.

## Frozen inputs

- Cohort: every MVTec AD Screw `test/` image (160 = 41 good + 119 anomalous: manipulated_front 24, scratch_head 24,
  scratch_neck 25, thread_side 23, thread_top 23) in lexical path order.
  Manifest `analysis/restoration_objective_screw/full_manifest.csv`, SHA-256
  `b680d6714fd9e1ca222ef4a5192478fd970c0b2dc70c5672d9c7aeb7e2bd51ec`, built by the same `build_full_manifest` rule.
- Detector bank: existing Screw Branch A clean-normal bank `checkpoints/legacy-patchcore/screw-seed11-train320`
  (all 320 `train/good`, seed 11, same frozen PatchCore settings as Hazelnut). Artifact SHA-256
  `patchcore_params.pkl 7c272889…c8b4`, `nnscorer_search_index.faiss d4910f28…cd12`. Loaded, never refit.
  Query is the four restored test variants only; CPU exact FAISS `IndexFlatL2`.
- Degradation family: identical to Hazelnut full110: canonical `Resize(256, bilinear)+CenterCrop(224)`, BasicSR MATLAB
  bicubic x0.25 antialias to 56×56 uint8; Bicubic baseline is the same implementation x4. The same LR bytes go to all
  learned restorers. Historical Pillow-Bicubic Screw numbers are never subtracted from these values.
- Restorers/checkpoints: unchanged pins (SwinIR-S x4 `09fad24e…`, RRDB_PSNR_x4 `f372b59f…`, RRDB_ESRGAN_x4 `65fece06…`).
  No new model is downloaded.
- GT masks: nearest `Resize(256)+CenterCrop(224)`, used only in evaluation.

Command (one execution):

```powershell
.venv\Scripts\python -X utf8 scripts\run_restoration_objective_pilot.py --cohort screw160 --device cuda --with-lpips
```

## Outcomes

Same runner outputs as Hazelnut full110. Primary: pooled AU-PRO@0.3 (200 thresholds). Secondary: Pixel AUROC, Image
AUROC, PSNR/SSIM/LPIPS. No thresholds/F1/calibration. Per anomaly: per-image Pixel AUROC, per-image AU-PRO@0.3,
ROI mean, background mean, ROI–background gap. Bicubic-relative taxonomy unchanged (strict sign).

Derived by `scripts/analyze_restoration_endpoint_category.py` (reads saved CSV/NPZ only, imports the frozen Hazelnut
helpers): ESRGAN−PSNR paired bootstrap of the mean per-image AU-PRO delta over all 119 anomalies (5,000 repeats,
seed 2026), Wilson 95% intervals of Bicubic-relative regression rates, the frozen tau grid {0, .005, .01, .02, .05},
`|delta|<=0.01` share and quantiles, baseline terciles sorted by (Bicubic AU-PRO, path) with sizes 39/39/41 (floor, the
remainder goes to the last group, the same rule that gave Hazelnut 23/23/24), descriptive Spearman (average ranks),
taxonomy contingency, and a defect-type table (count, mean/median direct delta, ESRGAN/PSNR/tie counts, mean quality
deltas).

Classification of the direct ESRGAN−PSNR localization result (`P` pooled delta, `D` mean paired per-image delta, `CI`
its bootstrap interval): **A** `P>0 AND D>0 AND CI.lower>0`; **C** `P<0 AND D<0 AND CI.upper<0`; **B** otherwise, with
B-small iff CI ⊂ [−0.01, +0.01]. Hazelnut's additional `D50` condition has no Screw analogue (no Screw pilot) and is
dropped; this is stated, not hidden. Quality trade-off reproduction is reported separately
(`mean ΔPSNR<0 AND mean ΔLPIPS<0`).

Hazelnut comparison: for each of mean ΔPSNR, ΔSSIM, ΔLPIPS, pooled ΔAU-PRO, ΔPixel AUROC, ΔImage AUROC, D and the
A/B/C case, report the sign in each category and `agree`/`disagree`. Two categories are two observations, not a
population estimate; no pooled cross-category test is made.

## Limits

One seed, one bank, one category; 119 anomalous images are paired repeated measurements on the same bank, not
independent seeds. LPIPS is a natural-image metric. MVTec's controlled imaging does not establish camera/compression
behaviour (that is the separate realistic-degradation family).
