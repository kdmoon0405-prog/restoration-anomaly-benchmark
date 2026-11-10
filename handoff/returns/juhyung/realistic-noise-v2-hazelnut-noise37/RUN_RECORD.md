# Run record — realistic noise v2, Hazelnut, noise seed 37 (status COMPLETE, 8/8 units)

- **What:** v1 LR Gaussian noise (σ5, σ15) re-drawn with noise seed 37, × {Bicubic, SwinIR, RealESRNet, RealESRGAN}. This is the second of 4 runs in the fixed 32-unit queue.
- **Fixed:** identical to run `realistic-noise-v2-hazelnut-noise23`:
  - split/bank seed 11
  - v1 bank bytes, load-only
  - v1 fit/calibration/test paths and train SHA verified
  - geometry, checkpoints, exact search family A
- **Seed:** per-sample seed = sha256(`realistic_lr_noise_v2|split_seed11|noise_seed37|<cat>|<sample>|<condition>`)[:8], little-endian. The same LR bytes go to all 4 restorers (`degraded_lr_sha256`).
- **Source:** `exp/realistic-noise-v2-juhyung@40d57dd`.
  - Tracked tree clean. `source_worktree_dirty=true` because of untracked files only, recorded as-is.
- **Session:** one session, `sessions/000.json`, 2026-11-10 21:36–22:55 KST (4,745 s wall). No interruption.
  - Unit times: 493–533 s at σ5 and 658–680 s at σ15 (measured wall times).
- **Check:** seed 23 and seed 37 differ for all 188 images in both conditions, in both degraded-LR SHA-256 and image score. σ5 SwinIR image AUROC is equal in both runs (0.910357 = 2549/2800 concordant pairs). This is a tie in a discrete metric, not a re-used realization.

## Results (measured; `summary.csv`, per-image `units/*.csv`)

Pooled AU-PRO@0.3 and image AUROC for seed 37, with seed 23 and v1 for reference.

| condition | restorer | AU-PRO s37 / s23 / v1 | image AUROC s37 / s23 / v1 |
| --- | --- | --- | --- |
| noise_s5 | bicubic | 0.789 / 0.776 / 0.766 | 0.965 / 0.971 / 0.972 |
| noise_s5 | swinir | 0.758 / 0.758 / 0.726 | 0.910 / 0.910 / 0.906 |
| noise_s5 | realesrnet | 0.799 / 0.800 / 0.790 | 0.970 / 0.975 / 0.972 |
| noise_s5 | realesrgan | 0.792 / 0.801 / 0.797 | 0.960 / 0.983 / 0.976 |
| noise_s15 | bicubic | 0.593 / 0.641 / 0.613 | 0.873 / 0.851 / 0.840 |
| noise_s15 | swinir | 0.515 / 0.564 / 0.567 | 0.818 / 0.780 / 0.800 |
| noise_s15 | realesrnet | 0.739 / 0.743 / 0.749 | 0.878 / 0.883 / 0.871 |
| noise_s15 | realesrgan | 0.761 / 0.767 / 0.762 | 0.898 / 0.906 / 0.907 |

Contrasts. Pooled Δ and per-image Δ (70 test anomalies, seed 37) are reported separately.

| condition | contrast | pooled Δ s37 / s23 / v1 | per-image mean / median Δ s37 | images < 0 s37 |
| --- | --- | --- | --- | --- |
| noise_s5 | SwinIR − Bicubic (primary) | −0.031 / −0.019 / −0.040 | −0.033 / −0.004 | 46/70 |
| noise_s15 | SwinIR − Bicubic (primary) | −0.079 / −0.077 / −0.046 | −0.087 / −0.052 | 60/70 |
| noise_s5 | RealESRNet − SwinIR | +0.041 / +0.042 / +0.064 | +0.046 / +0.010 | 18/70 |
| noise_s5 | RealESRGAN − SwinIR | +0.034 / +0.043 / +0.071 | +0.045 / +0.014 | 15/70 |
| noise_s15 | RealESRNet − SwinIR | +0.224 / +0.179 / +0.182 | +0.265 / +0.231 | 9/70 |
| noise_s15 | RealESRGAN − SwinIR | +0.246 / +0.203 / +0.194 | +0.272 / +0.232 | 8/70 |

Reading:
- Hazelnut now has three noise realizations: v1, s23 and s37. Every contrast keeps its sign across all three.
- Across realizations the pooled contrast moves by up to about 0.04 for SwinIR − Bicubic (−0.019 to −0.040 at σ5, −0.046 to −0.079 at σ15) and up to about 0.05 for the supplementary contrasts.
- σ15 absolute AU-PRO for Bicubic and SwinIR also moves by about 0.05 between seeds.
- These are repeated measurements on the same 70 images. They describe noise-realization variability only, not sampling uncertainty over images.

## Not included (private, local)

| artifact | path | note |
| --- | --- | --- |
| per-unit maps/scores | `units/*.npz` (8 files) | SHA-256 in each unit receipt `files` |
| bank | v1 `hazelnut-v1` bank | load-only, unchanged |
