# Bicubic normal-bank extension

Evidence: model_predictions. Primary contrasts use stored pooled AU-PRO@0.3.
The Bicubic-bank rows are matched to the existing clean-bank rows for the same query RGB.
The SwinIR-query contrast is within the Bicubic bank. No detector metrics were recomputed.
Per-image deltas are supplementary; pooled AU-PRO confidence intervals were not computed.

| query | clean-bank pooled AU-PRO | Bicubic-bank pooled AU-PRO | delta |
|---|---:|---:|---:|
| bicubic_x4 | 0.799066 | 0.898887 | +0.099821 |
| swinir_x4 | 0.853182 | 0.861553 | +0.008372 |
