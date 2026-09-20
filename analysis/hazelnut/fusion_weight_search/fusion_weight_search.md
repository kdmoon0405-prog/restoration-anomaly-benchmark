# Five-point scalar fusion feasibility ablation

Source: `outputs/fusion-patchcore/hazelnut-313x78-test110`. Hazelnut is development data; this is not an unbiased final test.

Alpha weights Bicubic/degraded. Fixed grid: 0.00, 0.25, 0.50, 0.75, 1.00. Selection uses pooled AU-PRO@0.3 only; F1 and new thresholds were not computed.

| Alpha | Pooled AU-PRO | Δ vs restored | Pixel AUROC | Regressions vs Bicubic | Worst-10 mean ΔAU-PRO |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0.841263 | +0.000000 | 0.985051 | 30 | -0.024301 |
| 0.25 | 0.838005 | -0.003258 | 0.985349 | 27 | -0.016530 |
| 0.50 | 0.833354 | -0.007909 | 0.985360 | 24 | -0.009693 |
| 0.75 | 0.826236 | -0.015027 | 0.984982 | 18 | -0.004995 |
| 1.00 | 0.817486 | -0.023777 | 0.984044 | 0 | +0.000000 |

Best coarse alpha: **0.00**, pooled AU-PRO 0.841263 (Δ vs restored +0.000000).

Best interior alpha: 0.25, pooled AU-PRO 0.838005 (Δ vs restored -0.003258); exceeds both endpoints: False.

Anchor checks (0/0.5/1): passed against saved predictions and evaluations. Regression counts are risk descriptors; alpha=1 has zero by definition. No fine search or adaptive gating was run.
