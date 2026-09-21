# Experiment protocol v0.2: x4 restoration and localization regression

Date: 2026-09-21. This version records a rule set **after** hazelnut exploration. Hazelnut findings are retrospective and cannot be presented as prospective validation of these rules. Keep the original `EXPERIMENT_PROTOCOL.md` as the v0.1 history.

## Research question and fixed comparison

고정된 x4 SR 조건에서 평균 localization은 개선되지만, 어떤 defect에서 regression이 발생하며 그 원인이 feature-space anomaly suppression인지 spatial distortion인지 분석한다.

- Dataset and development category: MVTec AD `hazelnut`. PatchCore is a fixed downstream evaluator, not the proposed model.
- Detector: Amazon official PatchCore at `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`; WideResNet50, `layer2` + `layer3`, 1024/1024 embedding, patch size 3, IdentitySampler, Resize(256) → CenterCrop(224). Keep the same fitted memory bank within each paired comparison.
- Input: canonical 224×224 clean image → bicubic downsample to 56×56 → bicubic x4 or official SwinIR-S x4 → 224×224. The x4 checkpoint SHA-256 is `09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e`.
- GT masks receive the same spatial transform with nearest-neighbor resizing. Test labels and masks are used only after inference for evaluation, case classification, and explicitly post-hoc oracles.
- Branch A is the fixed 391-normal-train / 110-test reproduction comparison, with no F1 because no independent normal calibration split remains. Branch B uses 313 fit / 78 normal calibration / 110 test and is a separate fusion study; its scores must not be compared to Branch A as if the memory banks were identical.

Primary **dataset-level** metric: pooled AU-PRO@0.3. The local evaluator uses 200 sampled score thresholds. Secondary metrics: Pixel AUROC, Image AUROC, PSNR, and SSIM. Report aggregate results and per-anomalous-image AU-PRO deltas separately; their means are not the pooled AU-PRO. F1, when reported for Branch B, uses only held-out normal calibration thresholds and is not a primary endpoint.

## Regression taxonomy (SwinIR minus Bicubic)

For each anomalous test image with a nonempty GT mask, calculate per-image AU-PRO@0.3 and the raw anomaly-map mean inside and outside the defect ROI. Define `delta_roi_bg_gap` as the SwinIR ROI−background gap minus the Bicubic gap.

| Label | Exact rule |
| --- | --- |
| Localization regression | `delta_per_image_aupro < 0` |
| Suppression-type regression | `delta_per_image_aupro < 0 AND delta_roi_bg_gap < 0` |
| Spatial/geometry-type regression candidate | `delta_per_image_aupro < 0 AND delta_roi_bg_gap >= 0` |
| Improvement or tie | `delta_per_image_aupro >= 0` |

The two regression subtypes partition localization regressions. They describe anomaly-map behavior, not a proven causal mechanism. Do not use “strong failure” as the primary definition. Report each delta's magnitude and counts by subtype; do not invent a new numerical cutoff from the hazelnut results. Raw ROI-score decrease alone is not a regression criterion.

## Post-hoc analysis and oracle limits

Rank the most negative and most positive per-image AU-PRO deltas for case review. Each figure keeps Clean / Bicubic / SwinIR / GT / Bicubic anomaly map / SwinIR anomaly map; the two maps share the same color range **within the image**. Review both suppression-type and geometry-candidate cases, including successful controls.

The deprecated ROI-mean selector is retained only as `preliminary_roi_mean_oracle.json`; it is not a localization upper bound. The new `oracle_localization_headroom.json` contains:

1. A per-image screening oracle: separately take the larger Bicubic/SwinIR per-image AU-PRO and Pixel AUROC on each anomalous image, then report wins, ties, means, and restored-only headroom. These are GT-assisted, non-deployable *per-image mean* upper bounds for choosing one of the two existing branches; they do not bound a newly fused anomaly map.
2. A whole-map post-hoc selector: on anomalous images choose the branch with higher per-image AU-PRO, keep SwinIR on normal images, and recompute Image AUROC, Pixel AUROC, and pooled AU-PRO with `evaluate_predictions()`. **These pooled outcomes are not guaranteed upper bounds**, even though the per-image screening mean is.

For feature-space follow-up, use only preselected failure and success cases. Compare corresponding PatchCore feature-grid patches against the **same fixed normal memory bank**: ROI distance, background distance, and their paired changes from Bicubic to SwinIR. Map GT occupancy to the feature grid and record the rule used for boundary patches. A reduced ROI distance alone does not prove defect suppression; inspect the ROI−background contrast and map coverage together. Do not run whole-dataset feature inference solely for this exploratory step.

## Leakage and next-category rule

- Hazelnut is the development/exploration category. Its 110 test images have already informed the question and taxonomy; they are not an untouched confirmation set.
- Screw is the next cross-category stress candidate. Add Grid only if it tests a distinct unresolved mechanism and the method remains fixed. Record category choice before viewing its results; report complete categories, not selected favorable defects.
- Capsule is reserved for one untouched final validation **only if no team member has used its labels or outputs for method selection**. Freeze method, metrics, threshold source, category/case selection rules, and analysis code before that run. A single final category is a confirmation check, not universal generalization.
- Do not use test results to change the SR checkpoint, detector settings, preprocessing, or thresholds. Do not tune a fusion weight on Screw or Capsule labels.
- A later coarse fusion-weight search `alpha ∈ {0, 0.25, 0.5, 0.75, 1}` remains possible **only if** the two-branch oracle shows useful complementarity. If hazelnut labeled results are used to choose `alpha`, explicitly relabel that activity as development/model selection; do not call its selected performance an unbiased hazelnut test result. Freeze the chosen rule before Capsule. No weight search is part of this v0.2 analysis run.

## Amendment, 2026-09-21: saved-prediction scalar-weight feasibility ablation

This amendment records a later decision; it does not rewrite the v0.2 decision above. The Branch A oracle headroom was small, but the Branch B predictions are already saved, so checking only `alpha=0.5` would be an incomplete and cheap-to-resolve test of global scalar fusion. **Before running this analysis**, fix the five-point grid `alpha ∈ {0.00, 0.25, 0.50, 0.75, 1.00}`, where alpha weights Bicubic/degraded and `1-alpha` weights SwinIR/restored. Apply the same alpha to calibrated image scores and anomaly maps. No new PatchCore or SwinIR inference, fine search, or adaptive gating is authorized by this amendment.

Choose the best alpha by **dataset-level pooled AU-PRO@0.3 only**; break an exact tie toward the smaller alpha. Report Pixel AUROC, Image AUROC, mean/median anomalous-image AU-PRO, and their requested comparisons as supplementary outcomes, never as alternative selection criteria. For each alpha, report Bicubic-relative per-image AU-PRO regression counts and magnitudes, split by ROI-background gap sign. Alpha=1 has zero Bicubic-relative regressions by construction; these counts are safety descriptors, not a selection objective. Do not calculate F1 or derive test-set thresholds.

Validate that alpha=0, 0.5, and 1 reproduce the saved restored-only, equal-mean, and degraded-only predictions and primary/secondary metrics within numerical tolerance. Hazelnut remains development data: a selected alpha is a candidate, not an unbiased test estimate. Fine search would require a separate explicit decision after reviewing pooled gain versus restored-only and defect-risk magnitudes; it is not run automatically. Screw and Capsule rules above remain unchanged.

## Amendment, 2026-09-21: targeted PatchCore feature-distance check

The nine Hazelnut images were selected after reviewing the Hazelnut outcomes, so this is an exploratory mechanism check, not an independent test: geometry candidates `crack/013`, `crack/015`, `print/005`; map-gap suppression candidates `crack/001`, `crack/017`, `hole/014`; success controls `crack/006`, `cut/003`, `hole/006`. Reuse the **same checksum-verified Branch A 391-normal PatchCore memory bank** for both x4 branches. No fit, separate branch banks, new checkpoint, threshold tuning, or whole-test feature inference is allowed. Saved 224-pixel maps supply localization metrics, but cannot substitute for upstream patch embeddings or FAISS nearest-neighbor distances.

For each selected image and branch, query the official PatchCore patch embeddings against that bank and retain the nearest-neighbor **squared-L2** distance on its actual feature grid. Map the canonical 224×224 binary GT mask to that grid using continuous per-cell area occupancy `w_j` (no outcome-chosen cutoff). Compute `D_defect = sum(w_j d_j)/sum(w_j)`, `D_background = sum((1-w_j)d_j)/sum(1-w_j)`, and `G_feature = D_defect - D_background`, then SwinIR-minus-Bicubic deltas. Record the actual grid shape and the occupancy rule. Grid-cell occupancy is an operational approximation to a receptive-field patch label; do not call it an exact patch-footprint GT assignment. Join these with saved-map per-image AU-PRO, Pixel AUROC, and ROI-background gap. Report all nine cases and descriptive subtype summaries without significance claims or causal language.

If suppression candidates show lower `D_defect` and `G_feature` after restoration while controls do not, describe the result as *consistent with* movement toward the normal memory manifold. If the patterns do not separate, retain the taxonomy as map-level behavior and revise the mechanism hypothesis. The selected-case test cannot prove that SR erased a defect. Screw remains the preselected cross-category stress test only after this Hazelnut analysis is reviewed; Capsule remains untouched.
