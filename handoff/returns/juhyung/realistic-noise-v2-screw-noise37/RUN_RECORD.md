# Run record — realistic noise v2, Screw, noise seed 37 (status COMPLETE, 8/8 units; queue 32/32 complete)

- **What:** v1 LR Gaussian noise (σ5, σ15) re-drawn with noise seed 37, × {Bicubic, SwinIR, RealESRNet, RealESRGAN}. This is the fourth and last run of the fixed 32-unit queue.
- **Fixed:** identical to the other v2 runs:
  - split/bank seed 11
  - v1 `screw-v1` bank bytes, load-only
  - v1 fit/calibration/test paths and train SHA verified
  - geometry, checkpoints, exact search family A
- **Seed:** per-sample seed = sha256(`realistic_lr_noise_v2|split_seed11|noise_seed37|screw|<sample>|<condition>`)[:8], little-endian.
  - The same LR bytes go to all 4 restorers.
  - The degraded LR differs from seed 23 for 224/224 images in both conditions.
  - At σ5, image scores differ from v1 for 224/224 images (Bicubic and SwinIR checked). v1 receipts carry no LR hash.
- **Source:** `exp/realistic-noise-v2-juhyung@40d57dd`.
  - Tracked tree clean. `source_worktree_dirty=true` because of untracked files only, recorded as-is.
- **Session:** one session, `sessions/000.json`, 2026-11-11 00:54–02:15 KST (4,905 s wall). No interruption.
  - Unit times: 499–587 s at σ5, 671–679 s at σ15.
- **PROTOCOL in this return:** `PROTOCOL.public.json` is the original with only the local absolute `v1_bank_dir` replaced by `outputs/realistic-degradation/screw-v1/bank`.
  - Original SHA-256 (local): `ddce8df66c64e90fe0b8a007c88036e2e4540af86ad07c83dc40c57c8ae0a205`.
  - Unit receipts reference the original's `protocol_sha256`.

## Results (measured)

Image AUROC stays near 0.5 (0.41–0.68). This is the known Screw image-score failure, so pixel AU-PRO is the reported endpoint.

| condition | restorer | AU-PRO s37 / s23 / v1 | image AUROC s37 / s23 / v1 |
| --- | --- | --- | --- |
| noise_s5 | bicubic | 0.749 / 0.752 / 0.749 | 0.488 / 0.470 / 0.411 |
| noise_s5 | swinir | 0.738 / 0.750 / 0.738 | 0.575 / 0.599 / 0.567 |
| noise_s5 | realesrnet | 0.825 / 0.825 / 0.824 | 0.591 / 0.571 / 0.558 |
| noise_s5 | realesrgan | 0.826 / 0.826 / 0.828 | 0.679 / 0.626 / 0.630 |
| noise_s15 | bicubic | 0.685 / 0.667 / 0.672 | 0.503 / 0.434 / 0.448 |
| noise_s15 | swinir | 0.639 / 0.623 / 0.635 | 0.411 / 0.507 / 0.466 |
| noise_s15 | realesrnet | 0.784 / 0.762 / 0.764 | 0.529 / 0.482 / 0.448 |
| noise_s15 | realesrgan | 0.777 / 0.778 / 0.758 | 0.513 / 0.501 / 0.443 |

Per-image Δ for seed 37 (119 test anomalies; reported separately from pooled):

| condition | contrast | pooled Δ s37 | per-image mean / median Δ | images < 0 |
| --- | --- | --- | --- | --- |
| noise_s5 | SwinIR − Bicubic (primary) | −0.011 | +0.004 / +0.009 | 49/119 |
| noise_s15 | SwinIR − Bicubic (primary) | −0.046 | −0.056 / −0.043 | 79/119 |
| noise_s5 | RealESRNet − SwinIR | +0.087 | +0.092 / +0.043 | 31/119 |
| noise_s5 | RealESRGAN − SwinIR | +0.087 | +0.091 / +0.037 | 33/119 |
| noise_s15 | RealESRNet − SwinIR | +0.145 | +0.171 / +0.166 | 23/119 |
| noise_s15 | RealESRGAN − SwinIR | +0.138 | +0.167 / +0.126 | 23/119 |

## Queue summary: pooled AU-PRO contrast over three noise realizations (v1 / s23 / s37)

| category | condition | contrast | v1 / s23 / s37 |
| --- | --- | --- | --- |
| hazelnut | noise_s5 | SwinIR − Bicubic | −0.040 / −0.019 / −0.031 |
| hazelnut | noise_s15 | SwinIR − Bicubic | −0.046 / −0.077 / −0.079 |
| hazelnut | noise_s5 | RealESRNet − SwinIR | +0.064 / +0.042 / +0.041 |
| hazelnut | noise_s5 | RealESRGAN − SwinIR | +0.071 / +0.043 / +0.034 |
| hazelnut | noise_s15 | RealESRNet − SwinIR | +0.182 / +0.178 / +0.224 |
| hazelnut | noise_s15 | RealESRGAN − SwinIR | +0.194 / +0.203 / +0.246 |
| screw | noise_s5 | SwinIR − Bicubic | −0.011 / −0.002 / −0.011 |
| screw | noise_s15 | SwinIR − Bicubic | −0.037 / −0.044 / −0.046 |
| screw | noise_s5 | RealESRNet − SwinIR | +0.086 / +0.075 / +0.087 |
| screw | noise_s5 | RealESRGAN − SwinIR | +0.090 / +0.076 / +0.087 |
| screw | noise_s15 | RealESRNet − SwinIR | +0.128 / +0.139 / +0.145 |
| screw | noise_s15 | RealESRGAN − SwinIR | +0.123 / +0.155 / +0.138 |

Reading:
- The pooled sign is the same in all three realizations for all 12 cells.
- The spread across realizations is up to 0.052 (Hazelnut σ15 RealESRGAN − SwinIR).
- **Screw σ5 SwinIR − Bicubic** is small in every realization (−0.002 to −0.011). In both v2 runs its per-image mean and median are positive while pooled is negative. Its direction is therefore not established.
- These are three realizations on the same images. They describe sensitivity to the noise draw only. No seed-pooled interval is reported, and they are not independent samples.

## Not included (private, local)

| artifact | path | note |
| --- | --- | --- |
| original protocol | `PROTOCOL.json` | contains a local path. SHA-256 above |
| per-unit maps/scores | `units/*.npz` (8 files) | SHA-256 in each unit receipt `files` |
| bank | v1 `screw-v1` bank | load-only, unchanged |
