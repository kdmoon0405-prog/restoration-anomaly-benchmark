# Progress

Date: 2026-09-20

## Implemented

- CPU-safe framework: deterministic degradations, MVTec AD/AD 2/VisA adapters, manifests, PSNR/SSIM, optional LPIPS, model protocols, YAML runner, CSV aggregation, bounded experiment matrices, image/pixel AUROC and F1, and AU-PRO@0.3.
- Anomalib 2.6.2 PatchCore CPU training/export and official SwinIR-S x2 restoration pilot (scripts/fit_patchcore.py, scripts/run_cpu_pilot.py). Its thresholds come from held-out normal training images.
- Jihyuk-style pilot using the official Amazon PatchCore source pinned to fcaa92f124fb1ad74a7acf56726decd4b27cbcad: WideResNet50, layer2+layer3, 1024/1024 embeddings, patch size 3, IdentitySampler, Resize(256) then CenterCrop(224). It saves a checksum-verified FAISS memory bank and handles FAISS's Windows non-ASCII-path limitation through an ASCII staging directory.
- The legacy pilot compares clean, bicubic x4, and optional official SwinIR-S x4 on the same detector and test images. It records per-image true FAISS squared-L2 nearest-neighbor distances, runtimes, raw NPZ outputs, summary CSV, and a quality-vs-detection comparison. F1 uses only held-out normal images for threshold calibration. The x4 checkpoint SHA-256 is 09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e.
- Downloaded and locally ignored the official full MVTec AD archive, official VisA archive/Anomalib conversion, SwinIR-S x2/x4 checkpoints, and model artifacts. MVTec AD 2 (roughly 32 GB) is not downloaded.

## Verified CPU results

- Python 3.11 pytest: 63 passed. Synthetic end-to-end smoke test also passes.
- Bottle Anomalib pilot: 168 normal training, 41 normal calibration, 4 balanced test images. SwinIR-S x2 vs bicubic x2: mean PSNR +0.8185 dB and SSIM +0.00629; pixel AUROC -0.000071 and AU-PRO -0.000203. Four images are only a pipeline check.
- Hazelnut original-PatchCore pilot: 16 normal training, 4 held-out normal calibration, 20 balanced test images (10 normal, 10 anomalous), seed 11. Bicubic x4: PSNR 37.2866 dB, SSIM 0.93454, image AUROC 0.99, pixel AUROC 0.985777, AU-PRO@0.3 0.687230. SwinIR-S x4: PSNR 39.5309 dB, SSIM 0.95545, image AUROC 1.00, pixel AUROC 0.986678, AU-PRO@0.3 0.691774. SwinIR minus bicubic: +2.2443 dB PSNR, +0.02091 SSIM, +0.000901 pixel AUROC, +0.004544 AU-PRO. The CSV/JSON include image/pixel F1 and all raw predictions. The small, balanced subset and 16-image memory bank cannot establish a full-dataset research conclusion.
- Hazelnut full-memory pilot: trained the original IdentitySampler on all 391 normal training images; saved the 1.26 GB FAISS index. On 10 balanced test images (5/5), clean pixel AUROC/AU-PRO were 0.987115/0.841313; bicubic x4 were 0.974984/0.721629; SwinIR-S x4 were 0.980693/0.758324. SwinIR minus bicubic: +2.0830 dB PSNR, +0.02177 SSIM, +0.005708 pixel AUROC, +0.036695 AU-PRO. All image AUROCs were 1.0 on this small subset. F1 is deliberately null because all training images entered the memory bank and no independent normal calibration set remained. Per-image NN statistics were measured in a separate 4-image full-memory run; the 10-image run used --skip-nn-stats to avoid doubling FAISS searches.
- The original Jihyuk notebook's reported numbers cannot be assigned reliably to specific clean/degraded/restored runs from its saved cells. The new pilot matches its detector settings, not a verified reproduction of those reported numbers. Our mask preprocessing uses nearest-neighbor interpolation; the upstream dataset loader defaults to bilinear.
- Hazelnut Branch A full result (391 train / 110 test, seed 11, F1 null by design): clean image/pixel AUROC 1.0/0.986880, AU-PRO 0.875000. Bicubic x4: PSNR 36.4654, SSIM 0.93173, image AUROC 0.998214, pixel AUROC 0.983933, AU-PRO 0.818910. SwinIR-S x4: PSNR 38.7789, SSIM 0.95422, image AUROC 0.998214, pixel AUROC 0.985092, AU-PRO 0.843461. SwinIR minus bicubic: +2.3135 dB, +0.02249 SSIM, 0.0 image AUROC, +0.001159 pixel AUROC, +0.024551 AU-PRO. Full-dataset run, no sampling, so no seed variation applies.
- Hazelnut Branch B full result (313 fit / 78 calibration / 110 test, seed 11, robust median/IQR per-variant normalization): degraded_only image AUROC/F1 0.997857/0.96296, pixel AUROC 0.984044, AU-PRO 0.817486, pixel F1 0.57004. restored_only 0.998571/0.96296, 0.985051, 0.841263, 0.58034. mean_0.5_0.5 1.0/0.97810, 0.985360, 0.833354, 0.57440. max 0.999643/0.97059, 0.985290, 0.840552, 0.58067. Mean minus restored: +0.00143 image AUROC, +0.01514 image F1, +0.000309 pixel AUROC, -0.005939 pixel F1, -0.007909 AU-PRO. Max minus restored: +0.001071, +0.007625, +0.000239, +0.000332, -0.000711. Fusion helps image-level slightly but does not beat restored-only on localization; single seed, so no unchanged/improved verdict per protocol.
- The teammate models.py/runner.py were reviewed but not copied: the factory definition and image_score assignment are commented out, and the proposed memory-bank statistics are pixel-map statistics rather than nearest-neighbor distances. The existing runner already preserves per-stage runtimes and unique output paths.


## Hazelnut defect-level post-hoc analysis

Using the completed Branch A 391-train / 110-test predictions, 70 anomalous test images were re-analyzed with GT masks used only after inference.

Per-image SwinIR-S x4 minus Bicubic x4 findings:

- defect ROI raw mean decreased on 49/70 anomalous images (70.0%);
- defect-to-background mean gap decreased on 25/70 (35.7%);
- per-image Pixel AUROC decreased on 30/70 (42.9%);
- per-image AU-PRO decreased on 30/70 (42.9%);
- both ROI-background gap and per-image AU-PRO decreased on 14/70 (20.0%), used as the current exploratory "strong failure" subset.

Mean deltas across anomalous images:

- defect ROI mean: -0.180891;
- defect-to-background gap: +0.178580;
- per-image Pixel AUROC: +0.001745;
- per-image AU-PRO: +0.012914.

A paired image-resampling bootstrap (5000 repeats, seed 2026) gave:

- image-AUROC delta estimate 0.0, 95% CI [-0.005482, +0.005778];
- mean per-anomaly Pixel-AUROC delta +0.001745, 95% CI [+0.000147, +0.003495];
- mean per-anomaly AU-PRO delta +0.012914, 95% CI [+0.004487, +0.022950];
- mean defect-ROI raw-score delta -0.180891, 95% CI [-0.277204, -0.082284].

Important interpretation: raw defect ROI score often falls after SwinIR, but the background score can fall even more, so raw ROI-score decrease alone is not a valid restoration-failure criterion. Aggregate localization improves on average while a nontrivial sample-level regression subset remains.

The small-defect hypothesis is not supported in hazelnut so far: Spearman(defect area ratio, ROI-mean delta) = -0.0318, and the strong-failure median defect-area ratio (0.02286) is close to the remaining images (0.02091).

Current exploratory strong-failure counts by defect type:

- crack: 4/18;
- cut: 1/17;
- hole: 7/18;
- print: 2/17.

The concentration in hole is a follow-up signal, not a final generalization. The next analysis should compare representative failure and success cases visually, then compute PatchCore feature-to-normal-memory distances only for selected samples to distinguish feature suppression from spatial localization/geometry failure.

The first ROI-mean-based oracle is not treated as a valid localization upper bound: choosing the branch with the larger GT ROI raw mean reduced AU-PRO relative to restored-only. The oracle definition must be revised before use in any final claim.

## Remaining work and boundaries

- Two-branch plan (agreed 2026-09-20): Branch A = Jihyuk-setting reproduction on all 391 hazelnut normals (AUROC/AU-PRO, F1 empty). Branch B = detection improvement on a fixed 80/20 split (313 fit / 78 calibration, seed 11), robust median/IQR per-variant normalization, fixed mean_0.5_0.5 vs restored-only as the first comparison, degraded-only and max as preset baselines. New `src/sr_anomaly/fusion.py` (pure NumPy, 8 unit tests) plus `scripts/run_fusion_patchcore.py` implement Branch B; `split.json` freezes the reused image lists and all F1 thresholds come from fused calibration normals. Hazelnut is development/exploration; final validation goes to unseen `capsule`. Weight search (0/0.25/0.5/0.75/1) only after mean_0.5_0.5 is checked, picked on synthetic/dev cases, frozen, then evaluated once on unseen data.
- The full hazelnut memory bank is ready. Evaluate all 110 test images and repeat across seeds/categories on a faster machine; CPU inference takes roughly 13 seconds per image-condition with this bank, before dataset metrics. Full IdentitySampler plus exact FAISS search is expensive even with a GPU backbone. For F1, use an independent normal calibration set or leave it empty; do not tune on test labels. Branch B needs its own 313-image bank; the 391 bank must not be reused because its 78 calibration images would leak into the memory bank.
- Sandbox note (2026-09-20): this container's egress fails TLS (curl exit 35) to release-assets.githubusercontent.com, download.pytorch.org, huggingface.co, and mydrive.ch, so the SwinIR checkpoint and MVTec archive cannot be fetched here. torch 2.14/torchvision 0.29/timm 1.0.29/faiss-cpu 1.15.1 install from PyPI, both submodules check out at their pinned commits, and the real PatchCore/SwinIR import surface verifies. Real-data runs (Branch A/B, capsule final) go to the local Windows machine or a GPU box that already holds the dataset and checkpoints.
- Connect other restoration checkpoints only after the degradation scale/task matches each model. EDSR, Restormer, Real-ESRGAN, EfficientAD, previous student code, and previous student weights are not available here. No metrics have been fabricated for them.
- Obtain MVTec AD 2 only if its size and data terms fit the experiment, and run VisA categories after selecting comparable splits.
- The current AU-PRO@0.3 uses 200 sampled thresholds; report this implementation detail in comparisons with external papers.

## Reproduce on this machine

From research_code/ in PowerShell, with the already downloaded ignored dataset/checkpoints:

    git submodule update --init
    uv pip install --python .venv\Scripts\python.exe -e ".[dev,pilot,legacy]"
    .venv\Scripts\python -X utf8 -m pytest -q -p no:cacheprovider
    .venv\Scripts\python -X utf8 scripts\smoke_test.py
    .venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 16 --test-limit 20 --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --output-dir outputs\legacy-patchcore\hazelnut-pilot-16x20-rerun
    .venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 0 --test-limit 10 --calibration-limit 0 --skip-nn-stats --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --output-dir outputs\legacy-patchcore\hazelnut-full-train-test10-rerun

On a fresh machine, follow the data/checkpoint download commands in README.md first. Each completed legacy output directory is non-overwriting; choose a new --output-dir for a rerun.
