# Bank-domain stored-result analysis

Complete unique category/seed runs: 3. Duplicate copies removed: 0.
Evidence kinds: model_predictions.
Primary: stored dataset pooled AU-PRO@0.3. No detector evaluation was rerun.

| family/category/seed | paired contrast | delta pooled AU-PRO | mean per-image delta |
|---|---|---:|---:|
| patchcore_bank_domain_v1/hazelnut/11 | swinir_restored:bicubic_x4_minus_clean:bicubic_x4 | 0.008414 | 0.000700 |
| patchcore_bank_domain_v1/hazelnut/11 | swinir_restored:swinir_x4_minus_clean:swinir_x4 | 0.006430 | -0.000377 |
| patchcore_bank_domain_v1/hazelnut/23 | swinir_restored:bicubic_x4_minus_clean:bicubic_x4 | 0.008514 | -0.000257 |
| patchcore_bank_domain_v1/hazelnut/23 | swinir_restored:swinir_x4_minus_clean:swinir_x4 | 0.007095 | -0.000235 |
| patchcore_bank_domain_v1/screw/11 | swinir_restored:bicubic_x4_minus_clean:bicubic_x4 | 0.059660 | 0.080146 |
| patchcore_bank_domain_v1/screw/11 | swinir_restored:swinir_x4_minus_clean:swinir_x4 | 0.085246 | 0.076425 |

Per-image CIs are supplementary and computed within each seed; repeated seeds do not multiply independent images.
Same-query quality is counted once across banks. Protocol hashes keep geometry/kernel/model families separate.
Source digests are recorded; raw arrays and remote execution were not independently observed.
Synthetic fixtures require explicit opt-in and are labelled in every data table.
Plots are deferred until actual result artifacts are supplied.
