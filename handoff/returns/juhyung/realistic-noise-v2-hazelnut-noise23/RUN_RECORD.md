# Run record — realistic noise v2, Hazelnut, noise seed 23 (status COMPLETE, 8/8 units)

- **What:** v1 LR Gaussian noise (σ5, σ15) re-drawn with noise seed 23, × {Bicubic, SwinIR, RealESRNet, RealESRGAN}. This is the first of 4 runs in the fixed 32-unit queue.
- **Fixed:**
  - split/bank seed 11
  - v1 bank bytes, load-only from `outputs/realistic-degradation/hazelnut-v1`
  - fit/calibration/test paths and train SHA verified against the v1 PROTOCOL
  - geometry, checkpoints, exact search family A
- **Seed:** per-sample seed = sha256(`realistic_lr_noise_v2|split_seed11|noise_seed23|<cat>|<sample>|<condition>`)[:8], little-endian. The same degraded LR bytes go to all 4 restorers; this is checked per image via `degraded_lr_sha256`.
- **Source:** `exp/realistic-noise-v2-juhyung@40d57dd`.
  - Tracked tree clean. `source_worktree_dirty=true` because of untracked files only (listed in `sessions/000.json`), recorded as-is.
  - Code SHA-256 values are in `PROTOCOL.json`.
- **Command:** `run_realistic_noise_v2.py --category hazelnut --noise-seed 23 --device cuda --with-lpips` (GPU: MX570 A).

## Sessions (measured)

| session | time (KST, 2026-11-10) | units | note |
| --- | --- | --- | --- |
| 1 | 15:27 – 17:43 | 7 completed; `noise_s15__realesrgan_x4plus` in progress | Manually stopped on user request. Killed before the session record is written, so there is no `sessions/` file for it. Same source commit, no source change in between. The unfinished unit had no receipt and left no files. |
| 2 (`sessions/000.json`) | 21:26 – 21:35 | 7 skipped (receipts and file hashes re-verified), 1 run | `--resume` |

Unit times in session 1 were 988–1,061 s (first unit 1,508 s). In session 2 it was 499 s, and v1 was about 505–680 s. The difference is almost entirely in `predict`. These are wall times on a shared laptop, not a speed comparison.

## Results (measured; `summary.csv`, per-image `units/*.csv`)

Pooled AU-PRO@0.3 and image AUROC. v1 is the same condition with v1 noise realizations, for reference only.

| condition | restorer | AU-PRO v2 (v1) | image AUROC v2 (v1) |
| --- | --- | --- | --- |
| noise_s5 | bicubic | 0.776 (0.766) | 0.971 (0.972) |
| noise_s5 | swinir | 0.758 (0.726) | 0.910 (0.906) |
| noise_s5 | realesrnet | 0.800 (0.790) | 0.975 (0.972) |
| noise_s5 | realesrgan | 0.801 (0.797) | 0.983 (0.976) |
| noise_s15 | bicubic | 0.641 (0.613) | 0.851 (0.840) |
| noise_s15 | swinir | 0.564 (0.567) | 0.780 (0.800) |
| noise_s15 | realesrnet | 0.743 (0.749) | 0.883 (0.871) |
| noise_s15 | realesrgan | 0.767 (0.762) | 0.906 (0.907) |

Contrasts. Pooled AU-PRO delta and the per-image AU-PRO delta over the 70 test anomalies are reported separately and are not interchangeable.

| condition | contrast | pooled Δ v2 (v1) | per-image mean / median Δ v2 | images < 0 v2 (v1) |
| --- | --- | --- | --- | --- |
| noise_s5 | SwinIR − Bicubic (primary) | −0.019 (−0.040) | −0.022 / −0.006 | 44/70 (48/70) |
| noise_s15 | SwinIR − Bicubic (primary) | −0.077 (−0.046) | −0.103 / −0.055 | 56/70 (52/70) |
| noise_s5 | RealESRNet − SwinIR | +0.042 (+0.064) | +0.038 / +0.010 | 18/70 (18/70) |
| noise_s5 | RealESRGAN − SwinIR | +0.043 (+0.071) | +0.036 / +0.012 | 18/70 (15/70) |
| noise_s15 | RealESRNet − SwinIR | +0.179 (+0.182) | +0.231 / +0.207 | 9/70 (10/70) |
| noise_s15 | RealESRGAN − SwinIR | +0.203 (+0.194) | +0.243 / +0.238 | 10/70 (10/70) |

Reading:
- The sign of every contrast matches v1 for this one additional noise realization.
- The magnitude moves by up to about 0.03 pooled. Example: SwinIR − Bicubic at σ5 is −0.019 vs −0.040.
- The same 70 images are re-used, so v1 and seed 23 are repeated measurements, not independent samples. No pooled seed statistic is computed until all seeds are in. Even then it describes noise-realization variability on the same images only.

## Not included (private, local)

| artifact | path | note |
| --- | --- | --- |
| per-unit maps/scores | `units/*.npz` (8 files) | SHA-256 in each unit receipt `files` |
| bank | v1 `hazelnut-v1` bank | load-only, unchanged |
