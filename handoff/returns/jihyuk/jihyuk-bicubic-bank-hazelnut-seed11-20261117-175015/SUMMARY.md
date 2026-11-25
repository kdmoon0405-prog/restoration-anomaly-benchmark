# Bicubic normal-bank extension

Evidence: model_predictions. Primary contrasts use stored pooled AU-PRO@0.3.
The Bicubic-bank rows are matched to the existing clean-bank rows for the same query RGB.
The SwinIR-query contrast is within the Bicubic bank. No detector metrics were recomputed.
Per-image deltas are supplementary; pooled AU-PRO confidence intervals were not computed.

| query | clean-bank pooled AU-PRO | Bicubic-bank pooled AU-PRO | delta |
|---|---:|---:|---:|
| bicubic_x4 | 0.817519 | 0.837985 | +0.020466 |
| swinir_x4 | 0.841252 | 0.854893 | +0.013641 |
