# Image-score aggregation on stored maps — full report (status COMPLETE: 40/40 units, 200/200 cells)

- **Protocol:** `docs/IMAGE_SCORE_AGGREGATION_V0.1.md`, fixed at `exp/image-score-aggregation-juhyung@4afae6d` (14:20 KST, 2026-11-11). It was committed before any non-original rule was compared against labels. Nothing was changed after it was fixed.
- **Rules:** `original` (stored score), `map_max`, top 0.1/0.5/1 % mean (k = 51/251/502 of 224×224).
- **Calibration:** per unit and rule, on calibration normals only, with existing robust median/IQR and q0.99.
- **Metrics:** image AUROC is primary. F1, test-normal FPR and miss rate are supplementary. The stored pooled AU-PRO is the fixed reference.
- **Scope:** Hazelnut and Screw × {v1 `none`, noise v2 σ5/σ15 × noise seed 23/37} × 4 restorers = 40 stored units.
  - This is a **re-evaluation of the same predictions**, not new inference. It adds no conditions to the realistic study.
  - All units of a category share the same test images (Hazelnut 110, Screw 160).

## Runs (measured)

| part | session | source | time (KST) | units | anchors |
| --- | --- | --- | --- | --- | --- |
| Hazelnut | `sessions/000.json` | `84d9c9a` (clean) | 14:30:37–14:30:43 | 20/20 | A and B exact |
| Screw | `sessions/001.json` | `78ac166` (clean) | 14:33:21–14:33:28 | 20/20 | A and B exact |

- **Run code:** the run-code SHA-256 values in `PROTOCOL.json` are identical for both sessions. Between `84d9c9a` and `78ac166` only the exporter and the derived-table script changed.
- **Anchor A, original score:** recomputation is bit-identical to each stored receipt (image robust params, threshold, AUROC, F1, FPR, miss rate).
- **Anchor B, map payload:** the pixel robust params and threshold refit from calibration maps are identical to the receipt, and the npz SHA-256 equals the receipt.
- **Memory:** `_budget` with the fixed 2 GiB reserve and a real payload plan of 159.7 MiB (Hazelnut) or 155.9 MiB (Screw) per unit. All passed; this is a plan, not a measured peak.
- **Inputs:** no model, bank, FAISS, GT or RGB was loaded. Source arrays were opened read-only and are unchanged.
- **original vs map_max:** never equal (0 images in any unit). Per-unit Pearson correlation is 0.991–0.998 for Hazelnut and 0.964–0.987 for Screw (descriptive).

## Results (measured; all cells in `summary.csv`; `derived/auroc_by_rule.csv`, `derived/restorer_contrasts_by_rule.csv`)

Image AUROC range over the 20 units of each category:

| category | original | map_max | top 0.1 % | top 0.5 % | top 1 % |
| --- | --- | --- | --- | --- | --- |
| hazelnut | 0.780–0.998 | 0.783–0.999 | 0.786–0.999 | 0.800–0.998 | 0.809–0.998 |
| screw | 0.411–0.679 | 0.429–0.658 | 0.432–0.655 | 0.436–0.643 | 0.432–0.632 |

Rule − original image AUROC (min to max over 20 units; units below 0):

| category | map_max | top 0.1 % | top 0.5 % | top 1 % |
| --- | --- | --- | --- | --- |
| hazelnut | −0.015 to +0.010 | −0.017 to +0.009 | −0.021 to +0.019 | −0.021 to +0.028 |
| screw | −0.045 to +0.018 (15/20 < 0) | −0.051 to +0.021 (15/20) | −0.074 to +0.037 (15/20) | −0.095 to +0.047 (14/20) |

Screw supplementary metrics at the fixed q0.99 threshold, over all units and rules:
- miss rate 0.85–1.00
- F1 0–0.26
- test-normal FPR 0–0.15

SwinIR − Bicubic image AUROC by rule. Columns are original / map_max / top0.1 / top0.5 / top1; the AU-PRO Δ is the fixed reference.

| category | realization | condition | image AUROC Δ by rule | AU-PRO Δ |
| --- | --- | --- | --- | --- |
| hazelnut | v1 | none | +0.002 / +0.003 / +0.003 / +0.002 / +0.002 | +0.021 |
| hazelnut | noise23 | σ5 | −0.060 / −0.047 / −0.048 / −0.046 / −0.045 | −0.019 |
| hazelnut | noise37 | σ5 | −0.054 / −0.049 / −0.047 / −0.047 / −0.050 | −0.031 |
| hazelnut | noise23 | σ15 | −0.070 / −0.062 / −0.059 / −0.044 / −0.035 | −0.077 |
| hazelnut | noise37 | σ15 | −0.055 / −0.052 / −0.047 / −0.037 / −0.031 | −0.079 |
| screw | v1 | none | +0.199 / +0.168 / +0.165 / +0.154 / +0.138 | +0.057 |
| screw | noise23 | σ5 | +0.130 / +0.144 / +0.143 / +0.144 / +0.138 | −0.002 |
| screw | noise37 | σ5 | +0.087 / +0.133 / +0.132 / +0.138 / +0.141 | −0.011 |
| screw | noise23 | σ15 | +0.073 / +0.068 / +0.068 / +0.065 / +0.071 | −0.044 |
| screw | noise37 | σ15 | −0.093 / −0.081 / −0.080 / −0.068 / −0.062 | −0.046 |

The supplementary RealESRNet/RealESRGAN − SwinIR contrasts for all realizations and rules are in `derived/restorer_contrasts_by_rule.csv`.

## Reading (descriptive; same images re-used; no interval computed here)

- **Screw:** within these five fixed rules, aggregating the stored post-processed map does not lift image AUROC away from the 0.41–0.68 band.
  - Map-based rules are lower than the stored score in most units.
  - Within this rule family, the near-chance Screw image score after ×4 round trips is not explained by the choice between the stored patch-max score and max/top-k aggregation of the smoothed map.
- **Hazelnut:** rules change image AUROC by at most about 0.03. At σ15 the SwinIR − Bicubic image gap narrows as k grows (about −0.06 to −0.07 with `original`, −0.03 with top 1 %), but it keeps its sign.
- **Screw restorer contrasts:** the image-AUROC contrasts are between values near or below 0.5. Their signs differ from the AU-PRO contrasts in several cells, so they are not read as a detection ranking.

## Limits

- **No baseline outside ×4:** there is no clean (non-×4) Screw unit in this scope. The study shows aggregation sensitivity after ×4 only, not how much of a clean-to-×4 drop aggregation accounts for.
- **One rule family:** all five rules are max- or upper-tail-type statistics on the smoothed map at one bank/split seed (11). Other aggregations, an unsmoothed patch map, or bank-domain changes are outside v0.1. The parallel bank-domain study is relevant here.
- **Repeats are not independent:** the noise repeats and v1 `none` re-use the same images. The per-image rows (`units/*.csv`: sample, split, label, rule, raw and normalized score, threshold, flagged, source npz SHA-256) are returned for the CPU's common bootstrap, with repeats grouped by image.

## Private (local, not returned)

| artifact | note |
| --- | --- |
| 40 source `units/*.npz` | unchanged; SHA-256 per unit receipt `source_sha256.npz` |
