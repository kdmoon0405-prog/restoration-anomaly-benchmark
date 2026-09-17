# Experiment protocol

Version: 0.1, written before the first real detector/restoration experiment.

## Research question

Measure whether restoration improves perceptual image quality while leaving anomaly detection unchanged or making it worse. Quality and detection are reported separately; PSNR, SSIM, or LPIPS are not used as substitutes for anomaly metrics.

## Pipeline and comparisons

Every experimental cell contains both paths:

```text
original -> degradation -> detector
original -> degradation -> restoration -> detector
```

The first path is the paired no-restoration baseline. Original images without synthetic degradation may be recorded as a reference, but they do not replace the paired baseline.

Initial scope:

- Dataset: MVTec AD.
- Engineering pilot: `bottle` category.
- Controlled degradations: Gaussian blur and low resolution.
- Severities: 1, 3, and 5.
- Detector: PatchCore.
- Restoration: one available checkpoint/model at a time.
- Seeds: 11, 29, and 47 for stochastic degradation and repeated fitting where applicable.

Do not add a second detector, restoration model, or dataset until this pilot produces complete manifests and paired results for all cells.

## Current severity definitions

These values are part of the experiment definition and come from `src/sr_anomaly/degradations.py`.

| Degradation | Severity 1 to 5 |
|---|---|
| Gaussian blur radius | 0.7, 1.2, 1.8, 2.6, 3.5 |
| Horizontal motion kernel | 3, 5, 7, 9, 11 pixels |
| Gaussian noise sigma | 5, 10, 18, 28, 40 on uint8 values |
| JPEG quality | 90, 75, 60, 40, 20 |
| Brightness factor | 0.9, 0.8, 0.7, 0.6, 0.5 |
| Contrast factor | 0.9, 0.75, 0.6, 0.45, 0.3 |
| Downsample factor | 2, 3, 4, 5, 6, followed by bicubic upsampling |

Render a degradation contact sheet before model runs. If two adjacent severities are visually indistinguishable or a severity destroys the object beyond the intended robustness range, record the finding and revise this protocol before collecting results.

## Data use and leakage controls

- Train or fit anomaly detectors only on the dataset's normal training images.
- Never select checkpoints, severity levels, thresholds, or preprocessing from test labels.
- MVTec AD has no official validation split. Create a deterministic normal-only validation subset from the training images before fitting. Store the split list and seed in the run artifacts.
- Image and pixel F1 require a threshold fixed before test evaluation. Store its source in the config. Do not report best-test F1 as ordinary F1.
- AUROC and AU-PRO use continuous scores and remain the primary detector metrics.
- For MVTec AD 2, use `validation` for normal-data decisions and `test_public` for local evaluation. `test_private` and `test_private_mixed` have hidden labels; keep their local label and mask fields empty and use the official evaluation server.
- Confirm every anomaly map has the same height and width as its mask. Do not silently resize either during evaluation.

## Metrics and aggregation

Image quality:

- PSNR and SSIM for aligned original/final pairs.
- LPIPS when its optional dependency is installed.

Detection:

- Image AUROC.
- Pixel AUROC and AU-PRO with maximum false-positive rate 0.3 when masks exist.
- Image/pixel F1 only with a validation-derived threshold.

Report each category, degradation, severity, seed, restoration, and detector separately. Aggregate categories with a macro mean so categories with more test images do not dominate. Retain seed-level rows; report mean and spread only after all requested seeds complete.

## Required interpretation table

Each paired result is assigned from measured deltas:

| Quality change | Detection change | Interpretation |
|---|---|---|
| improves | improves | compatible improvement |
| improves | unchanged within seed variation | visual-only improvement |
| improves | degrades | primary failure case |
| degrades/unchanged | improves | detector-specific effect requiring inspection |

Do not assign “unchanged” from a single seed. Use the observed seed variation and retain the raw values.

## Expansion rule

After the pilot passes completeness checks:

1. Add categories with small or boundary-sensitive defects.
2. Add one restoration model or EfficientAD, not both in the same expansion.
3. Add VisA or MVTec AD 2 only after the MVTec AD adapter, masks, and evaluation outputs are verified.

Expand a degradation/model pair when the direction of the detection delta is consistent across the three planned seeds or when a severity transition is visible and reproducible. Otherwise repeat or inspect the cell before multiplying combinations.

## Dataset references and licenses

- MVTec AD official page: https://www.mvtec.com/research-teaching/datasets/mvtec-ad
- MVTec AD 2 official page and evaluation rules: https://www.mvtec.com/research-teaching/datasets/mvtec-ad-2
- VisA repository, split files, and preparation script: https://github.com/amazon-science/spot-diff

MVTec AD and MVTec AD 2 are released for non-commercial research under CC BY-NC-SA terms stated on their official pages. VisA's repository states CC BY 4.0 for the dataset. Do not commit dataset images, masks, checkpoints, or generated outputs to this repository.

