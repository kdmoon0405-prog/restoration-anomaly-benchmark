# Image-score aggregation — v0.2 clean control scope (fixed before comparison, 2026-11-12)

v0.1 (`IMAGE_SCORE_AGGREGATION_V0.1.md`, 40 units / 200 cells) is unchanged and not repeated. This is a separate scope with a different study family.

## Question

v0.1 found that Screw image AUROC after ×4 stays at 0.41–0.68 under all five rules. Do the same five rules behave the same way on **clean** (non-×4) Screw predictions? Put differently: is the aggregation sensitivity seen after ×4 also present when the image-level signal is intact?

## Units (fixed: 3 units × 5 rules = 15 cells)

| unit | stored source (GPU local, read-only) | family (master) |
| --- | --- | --- |
| clean | `outputs/legacy-patchcore/screw-full320-test160/clean_predictions.npz` | `historical_recovery` |
| bicubic_x4 | `.../bicubic_x4_predictions.npz` | `historical_recovery` |
| swinir_x4 | `.../swinir_x4_predictions.npz` | `historical_recovery` |

- **Shared setup:** PatchCore `fcaa92f`, seed 11, bank from 320 Screw train images (`checkpoints/legacy-patchcore/screw-seed11-train320`), PIL bicubic ×4 path, SwinIR lightweight ×4.
- **Test set:** the same 160 Screw test images as the realistic family (checked: identical sample order and labels).
- **Not mixed with v0.1:** the bank, ×4 resampler and calibration differ from the realistic v1/v2 units, so these cells are reported as their own family and not pooled.

## Rules

The rules are identical to v0.1: `original`, `map_max`, `top0.1pct_mean`, `top0.5pct_mean`, `top1pct_mean` (k = 51/251/502). The code is `sr_anomaly.image_score_aggregation.aggregate`, unchanged.

## Metrics: what changes from v0.1, and why

- The source run has **no held-out calibration normals**: `results.json` calibration `paths` is empty, and the thresholds are null.
  - So there is no robust/q0.99 calibration.
  - F1, test-normal FPR and miss rate are **not defined** and are reported as null.
- **Primary:** image AUROC (`binary_roc_auc` via `classification_metrics`). It is rank-based, and v0.1's positive affine normalization would not change it anyway.
- **Reference (stored, not recomputed):** pooled AU-PRO.

## Anchors

- **A, original score:**
  - Recomputed image AUROC of `original` must equal `results.json` `variants[v].evaluation.classification.image_auroc` exactly.
  - The npz `scores` and `labels` must equal `per_image.csv` for that variant, in the realistic test order.
- **B, map payload:** pixel AUROC recomputed from the stored `maps` and `masks` with the existing `binary_roc_auc` must equal the stored `pixel_auroc` exactly. GT masks are used here **only** to verify that the payload is unchanged. They are not used for any rule, k or score.

On an anchor mismatch, that unit's other rules are not reported.

## Resources and outputs

- **Resources:** one unit at a time, read-only. `_budget` (2 GiB reserve) runs with the real plan: float32 maps, bool masks, a float64 copy for pixel AUROC, sort workspace, and 64 MiB.
- **Outputs:**
  - per-unit receipt
  - per-image rows (sample, label, rule, raw score, source npz SHA-256)
  - `summary.csv` with all 15 cells

## Interpretation limits

- This is one bank and seed, the same images in every unit, and a historical family.
- It shows whether the rule effect differs between clean and ×4 in this family. It does not explain why ×4 lowers image AUROC.
