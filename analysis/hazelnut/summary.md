# Hazelnut restoration failure analysis

## Scope
- Source run: `outputs\legacy-patchcore\hazelnut-full391-test110-repro`
- Anomalous test images analyzed: 70
- Comparison: SwinIR-S x4 minus Bicubic x4
- No model or hyperparameter tuning was performed.

## Aggregate performance (110 test images)
- Bicubic: PSNR 36.4654, SSIM 0.93173, image AUROC 0.998214, pixel AUROC 0.983933, AU-PRO@0.3 0.818910.
- SwinIR: PSNR 38.7789, SSIM 0.95422, image AUROC 0.998214, pixel AUROC 0.985092, AU-PRO@0.3 0.843461.
- Pooled AU-PRO delta (SwinIR − Bicubic): +0.024551.

## Sample-level localization regression (70 anomalous images)
- Per-image AU-PRO decreased: 30/70; mean delta among regressions -0.008528, range [-0.076146, -0.000173].
- Suppression-type (AU-PRO↓ and ROI-background gap↓): 14.
- Geometry-type candidate (AU-PRO↓ and ROI-background gap≥0): 16.
- Improvement or tie: 40.
- These labels describe map-score patterns; they do not establish a feature-space cause.

## Oracle headroom
- Per-image AU-PRO screening: Bicubic wins 30, SwinIR wins 40, ties 0; mean Bicubic 0.890483, SwinIR 0.903398, oracle 0.907052; headroom vs restored +0.003655.
- Per-image pixel AUROC screening headroom vs restored: +0.001202.
- Whole-map post-hoc selection delta vs restored: image AUROC -0.000714, pixel AUROC -0.000431, pooled AU-PRO -0.003003.
- This GT-assisted selection is non-deployable. Per-image mean headroom is an upper bound for two-branch screening; pooled metrics need not improve.

## Defect-size hypothesis
- Spearman(defect area ratio, ROI-mean delta): -0.03180851901546802
- The current hazelnut analysis does not support the simple smaller-defect → stronger-failure hypothesis. Size is not used to define regression.

## Interpretation limits
- GT masks were used only after inference. `preliminary_roi_mean_oracle.json` is a deprecated historical artifact, not a localization upper bound.
- `bootstrap_ci.json` intervals for pixel AUROC/AU-PRO concern mean per-image paired deltas, not pooled dataset metrics.
- `regression_taxonomy.csv`, `selected_cases.csv`, and `oracle_localization_headroom.json` retain the exact magnitudes and selection outcomes.
- Coarse fusion-weight search remains a later option on hazelnut development data only if oracle complementarity justifies it; no weight is chosen here.
