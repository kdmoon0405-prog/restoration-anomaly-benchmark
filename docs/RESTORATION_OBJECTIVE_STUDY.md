# Restoration-objective study: frozen pilot design

Date: 2026-09-23
Branch: `exp/restoration-objective-study`
Status: design and execution path frozen before pilot inference. No GPU pilot result exists yet.

## 1. Research question

Primary question:

> Does restoration objective alter the trade-off between image reconstruction quality and anomaly-evidence preservation?

Under one fixed x4 low-resolution input, compare a distortion-oriented RRDB endpoint with a perceptual/GAN-oriented RRDB endpoint. Measure reconstruction quality, pooled PatchCore localization, and anomalous-image regression patterns. A GAN endpoint may help, hurt, or make little difference; all three outcomes are valid.

## 2. Motivation

The current results show that average restoration benefit and sample-level defect-evidence preservation are not equivalent. The next useful variable is the restoration objective, not another detector, fusion weight, or category search. The practical inspection question is when a restored view can be trusted and when degraded/original evidence should remain available.

This study is Phase B, restoration-character analysis. The completed Hazelnut/Screw work is Phase A, failure characterization. Selective preservation or reliability-aware gating is Phase C and is not implemented here.

## 3. Current evidence kept unchanged

- Hazelnut, SwinIR-S minus Bicubic: PSNR `+2.313490 dB`, SSIM `+0.022492`, Pixel AUROC `+0.001159`, pooled AU-PRO@0.3 `+0.024551`. Among 70 anomalous images, 30 localization regressions split into 14 suppression patterns and 16 geometry candidates.
- Screw, SwinIR-S minus Bicubic: PSNR `+2.437479 dB`, SSIM `+0.016426`, Image AUROC `+0.198606`, Pixel AUROC `+0.019490`, pooled AU-PRO@0.3 `+0.055000`. Among 119 anomalous images, 23 regressed; all 23 met the suppression-pattern rule.
- The six selected Screw cases gave mean SwinIR-minus-Bicubic feature-gap changes of `-1.258936` for suppression cases (n=3) and `+0.327375` for success controls (n=3). This is consistent with relative defect-feature normalization in those selected cases, not proof of a population mechanism.
- The prespecified five-point global map-fusion search selected restored-only (`alpha=0`). It is a separate negative ablation and is not reopened in this study.

Existing predictions, metrics, taxonomy, and interpretations are not rewritten by the new pilot.

## 4. Model candidates audited

### Original ESRGAN family

Official source: [xinntao/ESRGAN](https://github.com/xinntao/ESRGAN), commit `73e9b634cf987f5996ac2dd33f4050922398a921`, Apache-2.0.

Both selected checkpoints use `RRDBNet(3, 3, 64, 23, gc=32)` and x4 upsampling. Official inference reads a BGR OpenCV image, reverses it to RGB, converts it to float `[0,1]`, runs the model, clamps to `[0,1]`, reverses RGB back to BGR, rounds to 8-bit, and writes it. The local adapter starts from PIL RGB, so it skips the two cancelling BGR/RGB conversions while preserving the tensor channel order and range.

The downloaded original checkpoint files are plain 702-key PyTorch state dictionaries and load strictly with the official `RRDBNet_arch.py`:

| Endpoint | Official file | Training data/objective | SHA-256 |
| --- | --- | --- | --- |
| distortion/PSNR | `RRDB_PSNR_x4.pth` | DF2K; L1 pixel loss | `f372b59f22929e1bc83fa58d78215c96f976de3b2eaeee736da1b348913da6cc` |
| perceptual/GAN | `RRDB_ESRGAN_x4.pth` | DF2K+OST; initialized from a PSNR model, then perceptual loss before activation + relativistic GAN loss + L1 | `65fece06e1ccb48853242aa972bdf00ad07a7dd8938d2dcbdf4221b59f6372ce` |

The [official paper](https://arxiv.org/abs/1809.00219) fixes x4 and MATLAB bicubic LR generation. The repository warns that a different downsampling kernel may cause artifacts. The endpoints share architecture and nominal task, but their documented training sets are not identical. The pilot therefore estimates an **official endpoint difference**, not a causal objective-only effect.

The repository states Python 3 and PyTorch >=1.0. Strict checkpoint loading and a synthetic forward pass were verified locally with Python 3.11.16 and PyTorch 2.14.0 CPU. The adapter uses `.to(device)` and is CUDA-compatible; actual NVIDIA execution remains unverified.

### Real-ESRGAN family

Official source audited: [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN), commit `a4abfb2979a7bbff3f69f58f58ae324608821e27`, BSD-3-Clause. `RealESRNet_x4plus` and `RealESRGAN_x4plus` use the same DF2K+OST high-order synthetic degradation pipeline. The official configs train Real-ESRNet with L1, then Real-ESRGAN with L1, perceptual, and GAN losses. That pipeline includes mixed blur kernels, two resize stages, noise, and JPEG ranges rather than the controlled MATLAB-bicubic input used here.

## 5. Selected model pair

Primary comparison: `RRDB_PSNR_x4` versus `RRDB_ESRGAN_x4`.

It keeps the RRDB architecture, scale, official source, and controlled bicubic SR task fixed while changing the endpoint objective. The training-data difference is recorded as a limitation. Bicubic is the no-learned-restoration baseline. SwinIR-S x4 remains the earlier distortion-oriented reference, but the scientific comparison is the two RRDB endpoints.

No network-parameter interpolation, output fusion, fine objective weighting, or additional GAN model is part of the pilot.

## 6. Excluded candidates and reasons

- Real-ESRNet/Real-ESRGAN: deferred to a future realistic-degradation phase. Their high-order blur/noise/JPEG training process changes the restoration task relative to this controlled bicubic experiment.
- Real-ESRGAN variants, ESRGAN network interpolation, Restormer, and additional SR models: excluded because they add architecture, degradation, or search confounds before the primary endpoint comparison is known to matter.
- New anomaly detector: excluded. PatchCore stays a fixed downstream measurement instrument.

## 7. Degradation-kernel issue

Existing Branch A creates LR with `PIL.Image.Resampling.BICUBIC` from 224x224 to 56x56 and returns the Bicubic baseline with the same Pillow implementation. It is not the MATLAB-compatible kernel named by the original ESRGAN training protocol.

Option A would preserve direct continuity with historical Branch A but expose both RRDB endpoints to a known training-kernel mismatch. Option B creates a separate internal pilot using an official MATLAB-compatible implementation. The old Branch A result remains historical and unchanged either way.

## 8. Selected degradation protocol

Option B is selected because it is cleaner for the primary RRDB endpoint comparison.

- Canonical clean image: the frozen PatchCore transform, `Resize(256, bilinear)` then `CenterCrop(224)`.
- LR generation: [BasicSR](https://github.com/XPixelGroup/BasicSR) `basicsr.utils.matlab_functions.imresize`, commit `8d56e3a045f9fb3e1d8872f92ee4a4f07f886b0a`, Apache-2.0; scale `0.25`, antialiasing enabled.
- LR storage/input: clamp to `[0,1]`, round to 8-bit RGB, exactly 56x56.
- Bicubic baseline: the same BasicSR implementation at scale `4.0`, exactly 224x224.
- SwinIR-S, RRDB-PSNR, and RRDB-ESRGAN all receive the same 56x56 RGB image bytes.
- Learned outputs are clamped, rounded to 8-bit RGB, and must be 224x224.

Consequently, new pilot values are internally paired but are not numerically appended to the historical Pillow-Bicubic Branch A table as if the degradation were unchanged.

## 9. Pilot manifest rule

Dataset: MVTec AD Hazelnut, development/exploration only.

Before inference, select the lexicographically first five paths in each test stratum: normal/good, crack, cut, hole, and print. There is no random draw and no use of saved prediction quality, regression labels, or anomaly-map values. The fixed 25 images are:

- normal: `good/000` through `good/004`
- crack: `crack/000` through `crack/004`
- cut: `cut/000` through `cut/004`
- hole: `hole/000` through `hole/004`
- print: `print/000` through `print/004`

The tracked manifest is `analysis/restoration_objective_pilot/pilot_manifest.csv`, SHA-256 `4d3b23548b5add0f067bec44330062870cde00a1521b9680198744f32bbf3603`. `.gitattributes` fixes LF endings so this digest is portable. The manifest records source/mask paths and their hashes; changing a selected file causes the runner to stop.

## 10. Detector freeze

Reuse the exact Hazelnut Branch A 391-normal bank at `checkpoints/legacy-patchcore/hazelnut-seed11-train391`. No fit is allowed.

- Amazon PatchCore commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`
- WideResNet50, `layer2` + `layer3`
- pretrain/target embedding dimension 1024/1024
- patch size 3, IdentitySampler
- Resize(256), CenterCrop(224), ImageNet normalization
- CPU `FAISS IndexFlatL2` exact search
- same bank checksum for every restoration variant
- frozen bank SHA-256: `patchcore_params.pkl` `7c2728899e9e4aeca619d5c6f24ad47456c1603cc16e4c846a80f002c6ddc8b4`; `nnscorer_search_index.faiss` `e665e08ac3d108ae095566df7baf7e966561333fdf50a6d85c6f5d77bfc3f9b4`

The GPU is used for the backbone and restoration models only. The runner rejects a missing, changed, non-Hazelnut, non-391, or differently configured bank.

## 11. Metrics

Image quality per image and by variant:

- PSNR, higher is better
- SSIM, higher is better
- AlexNet LPIPS, lower is better, using the repository's existing optional interface

Detection:

- Image AUROC
- Pixel AUROC
- pooled AU-PRO@0.3 using the existing 200-threshold implementation

F1 and thresholds are absent. Test labels are never used to fit a threshold.

For anomalous images, also record per-image Pixel AUROC, per-image AU-PRO@0.3, ROI mean, background mean, and ROI-background gap. Each learned restoration is classified relative to the new-pilot Bicubic baseline. `RRDB_ESRGAN - RRDB_PSNR` quality and detection deltas are reported separately as the primary descriptive comparison.

## 12. Failure taxonomy

For each learned restoration versus Bicubic:

- localization regression: `delta_per_image_aupro < 0`
- suppression pattern: localization regression and `delta_roi_bg_gap < 0`
- geometry candidate: localization regression and `delta_roi_bg_gap >= 0`
- improvement or tie: `delta_per_image_aupro >= 0`

No magnitude cutoff is added. These are anomaly-map patterns, not mechanism labels. The direct RRDB-ESRGAN versus RRDB-PSNR comparison stays descriptive and does not rename the frozen taxonomy.

## 13. Qualitative figure plan

Freeze one row per selected sample:

1. Clean RGB
2. 56x56 LR shown with nearest-neighbor display scaling, plus Bicubic RGB
3. SwinIR RGB
4. RRDB-PSNR RGB
5. RRDB-ESRGAN RGB
6. GT mask
7. Bicubic anomaly map
8. SwinIR anomaly map
9. RRDB-PSNR anomaly map
10. RRDB-ESRGAN anomaly map

All four anomaly maps for a sample share `vmin=min(all maps)` and `vmax=max(all maps)`. Restored RGB panels must remain visible; a map-only figure is insufficient. A defect ROI crop may be added beside the fixed full-image row, not substituted for it. Case selection for display must follow deterministic metric ordering and cannot replace population counts.

## 14. Stop/go rule

After the 25-image pilot, consider full Hazelnut only if at least one actual endpoint difference is visible in the stored outputs:

- PSNR/SSIM versus LPIPS trade-off,
- pooled AU-PRO difference,
- regression count or subtype-composition difference,
- repeatable qualitative defect-structure difference,
- distinct RRDB-PSNR versus RRDB-ESRGAN downstream behavior.

No post-hoc significance or magnitude cutoff will be invented. If the endpoints are nearly indistinguishable across these views, stop the objective branch and do not add GAN variants. If the pilot proceeds, the same code and conditions run all 110 Hazelnut images; Hazelnut remains development data.

## 15. Compute estimate

The pilot performs 25 images x 4 PatchCore detector calls = 100 detector inferences and 25 images x 3 learned restorers = 75 restoration calls. It loads, but does not fit, the 391-normal bank. On an MX570-class NVIDIA laptop, allow roughly 10-30 minutes including the 1.26 GB bank staging/load, optional CPU LPIPS, image writes, and CPU exact FAISS. This is a planning range, not a measured benchmark; the runner stores per-variant restoration and detector times.

## 16. Expected outputs

`outputs/restoration-objective/hazelnut-pilot25-<run>/` will contain:

- `results.json`: source revisions, device, manifest/checkpoint/bank hashes, protocol, aggregate metrics, and RRDB endpoint deltas
- `summary.csv`: one aggregate row per variant
- `per_image.csv`: quality, scores, timings, and anomalous-image localization statistics
- `regression_taxonomy.csv`: Bicubic-relative sample taxonomy for each learned restorer
- `objective_pair_per_image.csv`: direct RRDB-ESRGAN minus RRDB-PSNR sample deltas, with localization fields empty for normal images
- `<variant>_predictions.npz`: labels, scores, masks, and maps
- `images/`: clean, LR, GT, and all restored RGB images for later fixed-layout rendering

The runner is non-overwriting. No pilot output is created in this design commit.

## 17. Limitations

- The official RRDB endpoints differ in documented training data (DF2K versus DF2K+OST) as well as objective. Results cannot isolate the loss function causally.
- Hazelnut has already informed earlier questions and is a development category.
- Twenty-five images provide a feasibility signal, not a stable category estimate or significance test.
- LPIPS is a natural-image perceptual metric, not a defect-preservation metric.
- MVTec's synthetic/controlled setting does not establish performance under camera blur, noise, compression, or surgical imaging.
- CPU exact FAISS keeps detector semantics fixed but limits speedup from CUDA.

## 18. Future mitigation connection

Only if objective-dependent regression is observed, preselect bounded failure and success cases before a feature-space follow-up. Reuse the same bank and report `D_defect`, `D_background`, and `G_feature` as in the frozen Screw analysis. Do not run all-model/all-image NN analysis at pilot stage.

A later industrial mitigation may preserve both degraded and restored branches, then use restoration confidence or feature disagreement to decide when restoration should be trusted. That is a new Phase C method and requires rules frozen before Capsule; it is not part of this branch.

## 19. Capsule untouched rule

Capsule stays unopened and unused for checkpoint choice, stop/go judgment, threshold selection, case inspection, or code debugging. Screw is not used for objective-model selection. Grid and SurgClean are not run. Capsule may be used once only after the final method, metrics, thresholds, and analysis code are frozen and the team confirms that nobody used its outputs for development.

## Reproduction commands

Initialize pinned sources:

```powershell
git submodule update --init --recursive
```

Download the two original official checkpoints without adding `gdown` to project dependencies:

```powershell
New-Item -ItemType Directory -Force checkpoints\esrgan | Out-Null
uvx --from gdown gdown "https://drive.google.com/uc?id=1pJ_T-V1dpb1ewoEra1TGSWl5e6H7M4NN" -O checkpoints\esrgan\RRDB_PSNR_x4.pth
uvx --from gdown gdown "https://drive.google.com/uc?id=1TPrz5QKd8DHHt1k8SRtm6tMiPjz_Qene" -O checkpoints\esrgan\RRDB_ESRGAN_x4.pth
Get-FileHash -Algorithm SHA256 checkpoints\esrgan\RRDB_PSNR_x4.pth,checkpoints\esrgan\RRDB_ESRGAN_x4.pth
```

Validate the pre-inference manifest without rewriting it:

```powershell
.venv\Scripts\python -X utf8 scripts\create_restoration_objective_manifest.py --check
```

GPU pilot command, after installing a CUDA-enabled PyTorch build and `.[legacy,lpips]`:

```powershell
.venv\Scripts\python -X utf8 scripts\run_restoration_objective_pilot.py --device cuda --with-lpips --output-dir outputs\restoration-objective\hazelnut-pilot25-gpu
```

The command performs no PatchCore fit. Do not reuse a partial nonempty output directory.
