# Image-score failure diagnosis — PCB SwinIR F1 drop and Screw low Image AUROC (2026-11-09)

Scope: post-hoc diagnosis from saved scores/maps (`scripts/diagnose_image_score.py`), plus one separate small
re-prediction of a single board fixed by inventory order (`scripts/profile_pcb_exact_batch.py --board-recheck`).

- Test labels/GT are used only to describe results.
- No threshold, checkpoint, bank or method was reselected.
- Original results and success judgements are unchanged.

## Status legend

- **Confirmed:** checked directly on saved arrays or code.
- **Consistent:** the explanation fits the current evidence, but no intervention has tested it.
- **Hypothesis:** needs new data or a controlled run.

## 1. Implementation checks (PCB)

| check | result | status |
| --- | --- | --- |
| Board score definition | `assemble_board` returns `max(tile image score)` over 48 tiles. The board map is a separate overlap-mean of tile maps. Score ≠ map max by design. | confirmed (code) |
| Tile image score definition | PatchCore `_predict`: max over 28×28 patch NN squared-L2 distances (k=1), before bilinear upsampling and Gaussian σ=4. The map is the smoothed upsampled patch grid. | confirmed (code) |
| Manifest ↔ file ↔ sample/variant | All 1140 rows follow the frozen plan (parent-major, variant-minor), and `predictions/i.npy` ↔ index i | confirmed (`pcb_threshold_report.json`) |
| q0.99 image thresholds | Reconstructed from the 180 calibration scores, they match the stored thresholds exactly for all 3 variants | confirmed |
| Score ↔ map coupling | raw score / map max ≈ 1.08–1.16. Spearman(score, map max): anomalies 0.92–0.96, normals 0.64–0.86 (normal maxima are small and noisy) | confirmed (`pcb_map_score_summary.csv`) |
| Board score = max of recomputed tile scores; stored map reproduces | First test board in inventory order (`Anomaly/000.JPG`), clean and swinir_x4, 48 tiles each, re-predicted from the hash-verified stored RGB spool with the same bank/index. The board score equals the stored score bitwise and is the max of the 48 tile scores (argmax tile 10 in both variants). The assembled map equals the stored map bitwise (max abs diff 0). Tile score / tile-map max ≈ 1.09–1.10. (`../pcb_exact_batch/run-20261109-211614/diagnostic_board_recheck.csv`) | confirmed (1 board × 2 variants) |

**No implementation error was found in score/map linkage, ordering or thresholds.**

## 2. PCB: why SwinIR's Image F1 falls (0.697 vs Bicubic 0.816)

Frozen q0.99 results:

| variant | TP | FN | FP | TN |
| --- | --- | --- | --- | --- |
| clean | 76 | 24 | 4 | 96 |
| Bicubic | 71 | 29 | 3 | 97 |
| SwinIR | 54 | 46 | 1 | 99 |

| quantity (normalized image score) | clean | Bicubic | SwinIR |
| --- | --- | --- | --- |
| calibration top-3 | 2.28 / 2.24 / 2.08 | 3.01 / 2.78 / 2.70 | 2.82 / 2.43 / 2.22 |
| q0.99 threshold (interpolates between the 3rd and 2nd highest of 180) | 2.114 | 2.721 | 2.264 |
| raw calibration median / IQR scale | 4.365 / 0.605 | 5.388 / 0.385 | 5.445 / 0.513 |
| test-normal max | 3.10 | 3.19 | 2.75 |
| test-anomaly median | 2.71 | 3.44 | 2.35 |
| post-hoc TPR at test FPR 1% / 3% / 5% / 10% | .65/.71/.84/.97 | .57/.82/.86/.95 | .57/.70/.72/.88 |
| anomaly map peak inside GT | 0.80 | 0.68 | 0.79 |

Reading (post-hoc):

1. **Operating point, the larger part (consistent):**
   - At the frozen thresholds, the realized test-normal FPR differs: SwinIR 1/100, Bicubic 3/100.
   - At an equal 1% test FPR, SwinIR and Bicubic have the same TPR (0.57).
   - If SwinIR's threshold had landed at 3 FP, its TPR would be 0.70 (F1 ≈ 0.81, close to Bicubic's 0.816).
   - With 180 calibration normals, q0.99 rests on the top-3 calibration scores. A 1-vs-3 FP difference on 100 test normals is within the sampling noise of such a tail.
   - Calibration-only alternatives show how sensitive the threshold is (diagnostic only, not adopted): SwinIR TP is 55 at q0.98 and 45 at q0.995.
2. **Ranking, a real but smaller part (consistent):**
   - Image AUROC is 0.954 vs 0.968.
   - Between 3% and 10% test FPR, SwinIR's TPR is 0.07–0.14 lower than Bicubic's.
   - The SwinIR raw normal-score IQR is wider than Bicubic's: 0.513 vs 0.385. Paired SwinIR−Bicubic raw score on normals: median +0.10, SD 0.38. Anomaly raw medians are similar (6.65 vs 6.71). The robust scale is larger, so normalized anomaly scores are smaller.
3. **Not a localization failure (confirmed on saved maps):**
   - 25 anomalies are Bicubic-TP→SwinIR-FN (8 flip the other way).
   - On those 25, the SwinIR map peak lies inside the defect for 68% of boards (Bicubic 56%), and the peak tile is the same across all variants on 72%.
   - The board was located, but its tile maximum was not high enough relative to the wider SwinIR normal spread.
4. **Top-scoring tile proxy:** using the board-map argmax tile as the proxy, 98% / 95% / 96% of anomaly peaks fall in a GT-overlapping tile (clean / Bicubic / SwinIR). The peak tile is the same across the three variants on 70% of anomaly boards. Peaks on border tiles are rare (≤5%).

**Judgement:** the F1 drop is mostly a threshold-transfer effect, from a q0.99 tail on 180 normals, plus a smaller ranking loss from wider normal-score spread after SwinIR. A single frozen threshold cannot attribute it to one cause. No threshold change is proposed. The research-relevant fact is the wider normal spread.

## 3. Screw: low Image AUROC even without added degradation

| family | variant | Image AUROC | normal median score | anomaly−normal median | anomaly map peak in GT | AUROC of map max |
| --- | --- | --- | --- | --- | --- | --- |
| historical PIL | clean | 0.984 | 1.24 | +1.09 | 0.76 | 0.983 |
| historical PIL | bicubic_x4 | 0.480 | 5.72 | −0.09 | 0.14 | 0.453 |
| historical PIL | swinir_x4 | 0.679 | 3.53 | +0.43 | 0.40 | 0.634 |
| MATLAB endpoint | bicubic_x4 | 0.479 | 5.75 | −0.10 | 0.13 | 0.450 |
| MATLAB endpoint | swinir_x4 | 0.686 | 3.52 | +0.41 | 0.41 | 0.641 |
| MATLAB endpoint | rrdb_psnr_x4 | 0.720 | 3.40 | +0.45 | 0.42 | 0.691 |
| MATLAB endpoint | rrdb_esrgan_x4 | 0.709 | 3.27 | +0.64 | 0.29 | 0.682 |
| realistic none | bicubic_x4 | 0.466 | 5.83 | −0.14 | 0.15 | 0.452 |
| realistic none | swinir_x4 | 0.665 | 3.61 | +0.33 | 0.40 | 0.620 |
| realistic none | realesrnet_x4plus | 0.582 | 4.90 | +0.10 | 0.25 | 0.561 |
| realistic none | realesrgan_x4plus | 0.646 | 4.66 | +0.46 | 0.22 | 0.628 |

Protocol differences (`screw/screw_family_score_diagnosis.csv`; sample order and GT verified identical across sources):

| | historical PIL | MATLAB endpoint | realistic family |
| --- | --- | --- | --- |
| LR operator | Pillow bicubic 224→56→224 | BasicSR MATLAB bicubic | BasicSR MATLAB bicubic + degradation |
| bank | `screw-seed11-train320`, 320 clean train-good | same bank, loaded, `fit_performed=false` | own fit, 256 clean train-good (64 held out) |
| seed / split | 11 / all 320 train in bank | 11 / same | split seed 11, calibration fraction 0.2 |
| backbone / features | WRN50 layer2+3, 1024-d, patch 3, IdentitySampler, CPU IndexFlatL2 k=1 | same | same |
| image score | PatchCore image max | same | same |
| calibration | none used for AUROC | none (no F1) | per-unit robust + q0.99 (affects F1 only, not AUROC) |
| test | 160 (41 good / 119 anomalous) | same 160 | same 160 |

Reading:

- **Confirmed:**
  - The failure is not specific to the realistic family. Bicubic Image AUROC is 0.480 / 0.479 / 0.466 across three families that differ in LR operator and in bank size or composition.
  - Clean queries on the same type of clean bank reach 0.984.
- **Confirmed on saved maps:**
  - After any ×4 round trip, every normal's score rises about 3–5× (median 1.24 → 3.3–5.8).
  - The anomaly−normal gap shrinks from +1.09 to between −0.14 and +0.64.
  - The anomaly map peak moves out of the defect: in GT 76% for clean, 13–15% for Bicubic, 22–42% for learned restorers.
  - Pixel-level localization survives (AU-PRO 0.80–0.86), so defect evidence is still present locally. The image maximum is instead taken over restoration-induced off-bank texture elsewhere in the image.
- **Consistent explanation:**
  - The bank holds only clean normal patches, while queries are restored images.
  - The restoration residual is large relative to the defect signal and varies between images, so it dominates the image-level max.
  - On PCB this effect is much weaker: native-resolution 224 tiles, larger defects relative to the tile, and a 262k-vector bank of clean tiles. Its image AUROC drops only 0.971 → 0.954–0.968.
- **Hypothesis:**
  - A bank of normals passed through the same restoration (matched-domain bank) would restore Screw image AUROC substantially if the cause is domain mismatch. It would not if the ×4 LR step destroys the defect evidence that the image max needs.
  - That is the discriminating experiment. It is the matched Bicubic bank control assigned to another workstream, so it is not run here.
  - A second, cheaper check needs no new inference: compare image AUROC with a top-k-mean or GT-free central-region aggregation on saved maps. This only describes how the aggregation behaves and would not be adopted as a method.

## Files

- `pcb/`: `pcb_threshold_report.json`, `pcb_score_distribution.csv`, `pcb_threshold_sensitivity_diagnostic.csv` (diagnostic only), `pcb_matched_fpr_tpr.csv` (post-hoc), `pcb_per_map.csv` (1140 rows), `pcb_map_score_summary.csv`, `pcb_per_board_decisions.csv`
- `screw/screw_family_score_diagnosis.csv`
