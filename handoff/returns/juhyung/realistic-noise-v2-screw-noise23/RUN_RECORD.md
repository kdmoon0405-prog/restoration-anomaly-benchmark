# Run record — realistic noise v2, Screw, noise seed 23 (status COMPLETE, 8/8 units)

- **What:** v1 LR Gaussian noise (σ5, σ15) re-drawn with noise seed 23, × {Bicubic, SwinIR, RealESRNet, RealESRGAN}. This is the third of 4 runs in the fixed 32-unit queue.
- **Fixed:**
  - split/bank seed 11
  - v1 `screw-v1` bank bytes, load-only
  - v1 fit/calibration/test paths and train SHA verified
  - geometry, checkpoints, exact search family A
- **Seed:** per-sample seed = sha256(`realistic_lr_noise_v2|split_seed11|noise_seed23|screw|<sample>|<condition>`)[:8], little-endian.
  - The same LR bytes go to all 4 restorers.
  - The degraded LR differs from v1 for 224/224 images in both conditions.
- **Source:** `exp/realistic-noise-v2-juhyung@40d57dd`.
  - Tracked tree clean. `source_worktree_dirty=true` because of untracked files only, recorded as-is.
- **Session:** one session, `sessions/000.json`, 2026-11-10 22:56 – 2026-11-11 00:53 KST (7,010 s wall). No interruption.
  - Unit times were 664–666 s for the first three units and 922–1,039 s for the last five (measured wall time on a shared laptop).
- **PROTOCOL in this return:** `PROTOCOL.public.json` is the original `PROTOCOL.json` with one value changed. `v1_bank_dir` holds a local absolute path and was replaced by the repo-relative `outputs/realistic-degradation/screw-v1/bank`. All other bytes are identical.
  - The original stays local, SHA-256 `0afcd71261c4d39739d94fc455e68cd352bd26163af44d737bd245adae18b0be`.
  - Unit receipts reference `protocol_sha256` of the original.

## Results (measured; `summary.csv`, per-image `units/*.csv`)

Image AUROC stays near or below 0.5 for every restorer. This is the known Screw image-score failure, also present in v1 and other families; see `analysis/image_score_diagnosis`. Pixel-level AU-PRO is the reported endpoint.

| condition | restorer | AU-PRO s23 (v1) | image AUROC s23 (v1) |
| --- | --- | --- | --- |
| noise_s5 | bicubic | 0.752 (0.749) | 0.470 (0.411) |
| noise_s5 | swinir | 0.750 (0.738) | 0.599 (0.567) |
| noise_s5 | realesrnet | 0.825 (0.824) | 0.571 (0.558) |
| noise_s5 | realesrgan | 0.826 (0.828) | 0.626 (0.631) |
| noise_s15 | bicubic | 0.667 (0.672) | 0.434 (0.449) |
| noise_s15 | swinir | 0.623 (0.635) | 0.507 (0.466) |
| noise_s15 | realesrnet | 0.762 (0.764) | 0.482 (0.449) |
| noise_s15 | realesrgan | 0.778 (0.758) | 0.501 (0.443) |

Contrasts. Pooled Δ and per-image Δ (119 test anomalies) are reported separately.

| condition | contrast | pooled Δ s23 (v1) | per-image mean / median Δ s23 | images < 0 |
| --- | --- | --- | --- | --- |
| noise_s5 | SwinIR − Bicubic (primary) | −0.002 (−0.011) | +0.003 / +0.009 | 53/119 |
| noise_s15 | SwinIR − Bicubic (primary) | −0.044 (−0.037) | −0.047 / −0.038 | 81/119 |
| noise_s5 | RealESRNet − SwinIR | +0.075 (+0.086) | +0.093 / +0.040 | 31/119 |
| noise_s5 | RealESRGAN − SwinIR | +0.076 (+0.090) | +0.092 / +0.024 | 36/119 |
| noise_s15 | RealESRNet − SwinIR | +0.140 (+0.128) | +0.156 / +0.149 | 22/119 |
| noise_s15 | RealESRGAN − SwinIR | +0.155 (+0.123) | +0.173 / +0.175 | 19/119 |

Reading:
- **σ5 SwinIR − Bicubic:** about zero. The pooled Δ is −0.002, the per-image mean and median are slightly positive, and 53/119 images are negative. The pooled and per-image signs disagree, so no direction is claimed for this cell. v1 was −0.011.
- **σ15 SwinIR − Bicubic:** negative in both v1 and seed 23.
- **Supplementary contrasts:** positive in both.
- These are repeated measurements on the same 119 images, not independent samples.

## Not included (private, local)

| artifact | path | note |
| --- | --- | --- |
| original protocol | `PROTOCOL.json` | contains a local path. SHA-256 above |
| per-unit maps/scores | `units/*.npz` (8 files) | SHA-256 in each unit receipt `files` |
| bank | v1 `screw-v1` bank | load-only, unchanged |
