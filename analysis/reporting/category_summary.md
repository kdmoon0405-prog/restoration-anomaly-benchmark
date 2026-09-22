# Category result summary

| category | train_count | test_count |
| --- | --- | --- |
| hazelnut | 391 | 110 |
| screw | 320 | 160 |

## Image quality

| category | bicubic_psnr | swinir_psnr | delta_psnr | bicubic_ssim | swinir_ssim | delta_ssim |
| --- | --- | --- | --- | --- | --- | --- |
| hazelnut | 36.465447 | 38.778937 | 2.313490 | 0.931733 | 0.954225 | 0.022492 |
| screw | 35.507249 | 37.944728 | 2.437479 | 0.951995 | 0.968421 | 0.016426 |

## Detection

| category | bicubic_image_auroc | swinir_image_auroc | delta_image_auroc | bicubic_pixel_auroc | swinir_pixel_auroc | delta_pixel_auroc | bicubic_au_pro | swinir_au_pro | delta_au_pro |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hazelnut | 0.998214 | 0.998214 | 0.000000 | 0.983933 | 0.985092 | 0.001159 | 0.818910 | 0.843461 | 0.024551 |
| screw | 0.480016 | 0.678623 | 0.198606 | 0.951112 | 0.970602 | 0.019490 | 0.801397 | 0.856397 | 0.055000 |

## Regression taxonomy

| category | localization_regression_count | localization_regression_rate | suppression_count | suppression_rate | geometry_candidate_count | geometry_candidate_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hazelnut | 30 | 0.428571 | 14 | 0.200000 | 16 | 0.228571 |
| screw | 23 | 0.193277 | 23 | 0.193277 | 0 | 0.000000 |

Only categories supplied with both completed run artifacts and a cross-category summary are included.
