# Hazelnut restoration failure analysis

## Scope
- Source run: `C:\Users\문경돈\OneDrive\바탕 화면\DesignProject\research_code\outputs\legacy-patchcore\hazelnut-full391-test110-repro`
- Anomalous test images analyzed: 70
- Comparison: SwinIR-S x4 minus Bicubic x4
- No model or hyperparameter tuning was performed.

## Defect-ROI evidence
- Improved ROI mean: 21/70 (30.0%)
- Decreased ROI mean: 49/70 (70.0%)
- Tied: 0/70 (0.0%)
- Mean ROI-mean delta: -0.180891
- Median ROI-mean delta: -0.208462
- Spearman(defect area ratio, ROI-mean delta): -0.03180851901546802

## Interpretation rules
- Positive delta means SwinIR produced stronger anomaly-map evidence inside the GT defect ROI than Bicubic.
- Negative delta is a candidate restoration-induced anomaly suppression case.
- GT masks are used only after inference for post-hoc evaluation.
- See `bootstrap_ci.json` for paired uncertainty estimates.
- See `oracle_headroom.json` for a deliberately non-deployable GT-assisted upper bound.

## Next decision
- If negative-ROI cases concentrate in small defects or a specific defect type, prioritize feature-space NN-distance analysis on those cases.
- If failures are rare and unstructured, do not expand fusion-weight search; proceed to the preselected cross-category stress tests.
