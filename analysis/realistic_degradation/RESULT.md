# Realistic LR degradation × restorer — result (Hazelnut, Screw; one execution each)

## Provenance

- Runs (local only, not in Git):
  - `outputs/realistic-degradation/hazelnut-v1`: 2026-11-09 01:53–06:42, wall 17,419 s, 28/28 units in one session
  - `outputs/realistic-degradation/screw-v1`: 28/28 units
    - The first process (started 08:46) completed 14 units. It was stopped by hand at 10:55 because the laptop overheated. It did not write a session file because session files are written at process end.
    - The `--resume` process (11:06–13:23, `sessions/000.json`) verified and skipped those 14 receipts, then ran the remaining 14.
- Command: `GIT_LFS_SKIP_SMUDGE=1 .venv/Scripts/python.exe scripts/run_realistic_degradation.py --category <cat> --device cuda --with-lpips [--resume]`
- Environment:
  - NVIDIA GeForce MX570 A
  - Python 3.11.2, torch 2.14.0+cu126, faiss 1.15.1, numpy 2.4.6
  - Source commit `afb36ab`, worktree dirty (pre-existing untracked files only)
- Protocol, family `realistic_lr_degradation_v1` (from `PROTOCOL.json`):
  - Clean 224 crop → MATLAB-bicubic ×0.25 LR → degradation (seeded per sample) → restorer ×4 → PatchCore.
  - Degradations: none, Gaussian noise σ5/σ15, Gaussian blur σ0.8/σ1.6, JPEG q90/q50.
  - Restorers: MATLAB-bicubic ×4, SwinIR-S ×4, RealESRNet_x4plus, RealESRGAN_x4plus.
  - Bank: a clean-normal-only bank, fit once per category (Hazelnut 313 images, Screw 256 images).
  - Calibration: per unit, on restored held-out train-good images (Hazelnut 78, Screw 64). Robust median/IQR normalization, image and pixel thresholds at q0.99.
  - Test sets: Hazelnut 110 (40 good, 70 anomalous); Screw 160 (41 good, 119 anomalous).
  - GT masks are loaded only after predictions are saved.
  - AU-PRO@0.3 uses 200 thresholds and 4-connectivity.
- Derived: `derived/` from `scripts/summarize_return_package.py`, which reads saved receipts and CSVs only.
- These banks are separate from the Screw four-endpoint run (320-image bank). Do not subtract numbers across the two runs.

## Pooled AU-PRO@0.3 (test set; bold = best in row)

| category | degradation | Bicubic | SwinIR | RealESRNet | RealESRGAN |
| --- | --- | --- | --- | --- | --- |
| hazelnut | none | 0.822 | **0.843** | 0.830 | 0.815 |
| hazelnut | noise σ5 | 0.766 | 0.726 | 0.790 | **0.797** |
| hazelnut | noise σ15 | 0.613 | 0.567 | 0.749 | **0.762** |
| hazelnut | blur σ0.8 | 0.774 | 0.775 | 0.792 | **0.792** |
| hazelnut | blur σ1.6 | 0.706 | 0.705 | 0.712 | **0.742** |
| hazelnut | JPEG q90 | 0.776 | 0.774 | 0.799 | **0.804** |
| hazelnut | JPEG q50 | 0.692 | 0.681 | 0.764 | **0.788** |
| screw | none | 0.801 | **0.858** | 0.826 | 0.831 |
| screw | noise σ5 | 0.749 | 0.738 | 0.824 | **0.828** |
| screw | noise σ15 | 0.672 | 0.635 | **0.764** | 0.758 |
| screw | blur σ0.8 | 0.769 | **0.773** | 0.773 | 0.772 |
| screw | blur σ1.6 | 0.727 | 0.725 | **0.797** | 0.764 |
| screw | JPEG q90 | 0.770 | 0.725 | 0.813 | **0.828** |
| screw | JPEG q50 | 0.737 | 0.713 | 0.769 | **0.781** |

Full metrics, including PSNR, SSIM, LPIPS, Image/Pixel AUROC, F1, thresholds and miss/false-alarm rates, are in `derived/summary_56.csv`.

## Observations (descriptive; one run, two categories, no confidence intervals)

1. **No added degradation:** SwinIR has the highest AU-PRO in both categories.
2. **With added degradation:** a Real-ESR* model ranks highest in 11 of 12 degraded condition×category cells. At full precision, Screw blur σ0.8 ranks SwinIR first (0.7726005601), followed by RealESRNet (0.7725502431), a difference of 0.0000503170. Both round to 0.773 in the table. This ordering has no pooled confidence interval.
3. **SwinIR under noise:** on noise σ5, σ15, JPEG q90 and JPEG q50, SwinIR is at or below Bicubic in AU-PRO. On noise σ15 it has the lowest PSNR of all units (21.5 dB in both categories).
4. **Paired per-anomaly-image AU-PRO vs Bicubic** (`derived/delta_vs_bicubic.csv`, `delta_distribution.png`):
   - RealESRGAN, noise σ15: better on 62/70 Hazelnut images and 93/119 Screw images.
   - RealESRGAN, JPEG q50: better on 65/70 Hazelnut images and 79/119 Screw images.
   - SwinIR, noise σ15: worse on 52/70 Hazelnut images and 82/119 Screw images.
5. **Quality vs localization over units** (`derived/quality_detection_scatter.png`; Spearman over units, descriptive only):

   | quality metric | Hazelnut (n=28) | Screw (n=28) | both (n=56) |
   | --- | --- | --- | --- |
   | PSNR | +0.86 | +0.20 | +0.50 |
   | SSIM | +0.86 | +0.63 | +0.71 |
   | LPIPS | −0.90 | −0.74 | −0.82 |

   On Screw, RealESRGAN has PSNR 27.5–30.2 dB and is among the highest in AU-PRO. The minimum PSNR depends on the degradation condition, including the lower SwinIR value under strong noise. Because units share images and conditions, these correlations are not evidence that one causes the other.
6. **Image-level classification on Screw is unusable in this run:**
   - Image AUROC is 0.39–0.67 across the 28 units.
   - At the q0.99 threshold, the anomaly miss rate is 0.87–1.00.
   - Report this image-level failure alongside the pixel-level metrics: Pixel AUROC 0.88–0.97, AU-PRO 0.64–0.86.
   - Hazelnut image AUROC ranges 0.77–1.00.
7. **Per defect type** (`derived/per_defect_type.csv`):
   - The lowest-AU-PRO types are Hazelnut crack/cut and Screw manipulated_front.
   - Bicubic mean per-image AU-PRO over the 7 conditions is 0.65 (crack), 0.73 (cut) and 0.51 (manipulated_front).
   - On these types, RealESRNet and RealESRGAN are higher than Bicubic and SwinIR by about 0.07–0.15.
   - Each defect type has only 17–25 images.
8. **Runtime** (`derived/runtime.csv`, `runtime_performance.png`):
   - Each unit took 505–683 s, of which PatchCore predict took 427–635 s. Predict time varied across units and sessions. The current records do not isolate restorer, thermal and execution-order effects through a controlled timing comparison.
   - Restoration time per image was 0.03–0.08 s for Bicubic, 0.21–0.27 s for SwinIR, and 0.25–0.32 s for RealESRNet/RealESRGAN.
   - Restoration is under 15% of each unit's time.

## Not claimed

- No causal claim about what kind of restoration "helps detection".
- No population claim beyond these two MVTec categories, these degradation strengths, and this seed.
- The checkpoints differ in more than their objective (training data and degradation model).
- Success/regression cases are listed as sample IDs in `derived/success_regression_cases.csv`. RGB panels are not committed, because the dataset license keeps RGB local.
