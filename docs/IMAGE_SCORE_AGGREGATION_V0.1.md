# Image-score aggregation contrast on stored maps — protocol v0.1 (fixed before any label comparison)

Status: **fixed**. This file is committed before any rule other than the original score is evaluated against test labels. Changing a rule, k, the unit list or the calibration after that point requires a new version (v0.2) and must keep the v0.1 results.

## Question

Screw image AUROC is near 0.5 after ×4 round trips while pixel AU-PRO stays 0.62–0.83. This sub-study asks how much of that image-level drop depends on how the stored post-processed map is aggregated into an image score.

It re-evaluates **existing predictions only**:
- no model, bank or FAISS is built or loaded
- nothing is re-inferred or re-trained
- it adds no new inference conditions and is not counted as new realistic-degradation results

Pixel maps and the stored pooled AU-PRO stay the fixed reference and are not recomputed.

## Units (fixed: 40 stored units × 5 rules = 200 evaluation cells)

| category | family | source run (repo-relative) | conditions | restorers |
| --- | --- | --- | --- | --- |
| hazelnut, screw | `realistic_lr_v1` | `outputs/realistic-degradation/<cat>-v1` | `none` | 4 |
| hazelnut, screw | `realistic_lr_noise_v2`, noise seed 23 | `outputs/realistic-noise-v2/<cat>-noise23` | `noise_s5`, `noise_s15` | 4 |
| hazelnut, screw | `realistic_lr_noise_v2`, noise seed 37 | `outputs/realistic-noise-v2/<cat>-noise37` | `noise_s5`, `noise_s15` | 4 |

- Restorers: `bicubic_x4`, `swinir_x4`, `realesrnet_x4plus`, `realesrgan_x4plus`.
- That is 20 units per category, all at split/bank seed 11.
- The noise-seed repeats and v1 `none` re-use the same test images (Hazelnut 110, Screw 160). They are not independent samples.

## Inputs per unit (read-only)

- `units/<unit>.npz`: `calibration_maps`, `test_maps` (float32, N×224×224, the post-processed map returned by PatchCore `predict`), `calibration_scores`, `test_scores` (float64, the stored PatchCore image score).
- `units/<unit>.csv`: `sample`, `split`, `label`, `defect_type` in the same row order (calibration rows first, then test rows).
- `units/<unit>.json` (receipt): file SHA-256, stored metrics and calibration.
- Before any array is used:
  - The npz and csv SHA-256 must equal the receipt `files`.
  - The csv row count and order must match the npz lengths.
  - The csv `image_score` must equal the npz score bytes.
- GT masks and RGB images are **not** loaded. Test labels are used only for evaluation.

## Rules (fixed)

The map is H×W = 224×224 = 50,176 values. Each rule is applied identically to every calibration and test image.

| rule id | definition |
| --- | --- |
| `original` | stored image score (`*_scores`), unchanged |
| `map_max` | max of the stored post-processed map |
| `top0.1pct_mean` | mean of the k = ceil(0.001·H·W) = **51** largest map values |
| `top0.5pct_mean` | mean of the k = ceil(0.005·H·W) = **251** largest map values |
| `top1pct_mean` | mean of the k = ceil(0.01·H·W) = **502** largest map values |

- k is computed with exact rational arithmetic, not floating point.
- Top-k means are computed in float64 over the flattened map. Only values are averaged, so ties do not matter.
- `original` is **not** assumed to equal `map_max`. The PatchCore image score is the max of the unsmoothed patch scores, while the stored map is upsampled and Gaussian-smoothed. Their equality rate is reported descriptively only.
- k, region and rule are not chosen from GT, defect area or test results.

## Calibration and metrics (fixed; reuses existing functions)

For each unit × rule, on that unit's calibration normals only:
- `sr_anomaly.fusion.robust_params`, then `normalize`, then `quantile_threshold(·, 0.99)`. This is identical to `_unit_metrics` in `scripts/run_realistic_degradation.py`, which `run_realistic_noise_v2.py` reuses.
- Test scores are normalized with those parameters. Flagged = normalized score `>=` threshold.

Metrics:
- **Primary:** image AUROC (`sr_anomaly.evaluation.classification_metrics`).
- **Supplementary:** image F1 at the q0.99 threshold, test-normal false-alarm rate, anomaly miss rate.
- **Reference (copied from the receipt, not recomputed):** pooled AU-PRO@0.3, pixel AUROC.

Test labels never select k, a threshold or a rule. No rule is declared "best" for later use on the basis of these test results.

## Anchors (checked per unit before its other rules are reported)

- **Anchor A, original score.**
  - Recomputing `original` must reproduce the receipt exactly: image robust parameters, `image_threshold`, `image_auroc`, `image_f1`, test-normal FPR and miss rate.
  - On mismatch, the unit's other rules are not reported until the cause is found and recorded.
- **Anchor B, map payload.**
  - The npz SHA-256 must equal the receipt.
  - Pixel robust parameters and `pixel_threshold` refit from `calibration_maps` (float64) must equal the receipt `calibration.pixel` / `pixel_threshold`.
  - This shows the maps read are the maps that produced the stored AU-PRO. It does not involve `original`.

## Resources

Units are processed one at a time: load, compute, write, release. Before each load, `sr_anomaly.pcb_board_analysis._budget` (fixed 2 GiB reserve, unchanged) is called with the real payload plan:
- float32 maps
- one float64 copy of the calibration maps
- one normalized float64 copy
- 64 MiB working headroom

If the guard blocks a unit, that unit is recorded as BLOCKED_MEMORY and independent units continue.

## Outputs

- **Per unit:**
  - receipt JSON with anchors, k, per-rule calibration and metrics, and the source npz/csv/receipt/protocol SHA-256
  - per-image CSV: `sample`, `split`, `label`, `defect_type`, `rule`, `raw_score`, `normalized_score`, `threshold`, `flagged`, `source_npz_sha256`
- **Run:** `summary.csv` (one row per cell; all 200 cells, none filtered) and `PROTOCOL.json` (repo-relative paths only).
- The per-image rows let the CPU run a common image-level bootstrap. Noise repeats of the same image must be grouped there.

## Interpretation limits

- This is a post-hoc re-aggregation of fixed predictions at one bank/split seed.
- A rule-dependent change in AUROC shows sensitivity to aggregation. It does not identify the cause of the Screw drop, which may also come from the reference domain, the representation or bank coverage.
- Results are reported for all rules and units, including ones that do not change.
