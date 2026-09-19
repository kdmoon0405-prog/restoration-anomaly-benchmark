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
- The original Jihyuk notebook's reported numbers cannot be assigned reliably to specific clean/degraded/restored runs from its saved cells. The new pilot matches its detector settings, not a verified reproduction of those reported numbers. Our mask preprocessing uses nearest-neighbor interpolation; the upstream dataset loader defaults to bilinear.
- The teammate models.py/runner.py were reviewed but not copied: the factory definition and image_score assignment are commented out, and the proposed memory-bank statistics are pixel-map statistics rather than nearest-neighbor distances. The existing runner already preserves per-stage runtimes and unique output paths.

## Remaining work and boundaries

- Run full hazelnut training (391 normal images) and all 110 test images on a machine with enough RAM/time, then repeat across seeds and categories. Full IdentitySampler plus exact FAISS search is expensive even with a GPU backbone. Preserve the normal-only calibration split if reporting F1; if all train images enter the memory bank, use a separate independent calibration set or leave F1 empty.
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

On a fresh machine, follow the data/checkpoint download commands in README.md first. Each completed legacy output directory is non-overwriting; choose a new --output-dir for a rerun.
