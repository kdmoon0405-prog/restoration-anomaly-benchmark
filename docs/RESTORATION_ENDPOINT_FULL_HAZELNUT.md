# Full Hazelnut restoration-endpoint confirmation (frozen before inference)

Status: preparation only, 2026-09-29. No full-endpoint predictions or results exist. This protocol must not be revised after viewing the full run.

## Question and role

Do PSNR-oriented and perceptual/GAN-oriented restoration endpoints exhibit different image-quality–anomaly-localization trade-offs on the full Hazelnut test set?

This is a within-category stability check of the pre-frozen 25-image pilot, not a new model search, an independent validation category, or an objective-only causal ablation. Hazelnut remains development data. The primary pair is the two official RRDB endpoints; Bicubic and SwinIR-S provide fixed context.

The pilot observed RRDB-ESRGAN minus RRDB-PSNR: PSNR `-2.622296 dB`, SSIM `-0.034490`, LPIPS `-0.042595`, and pooled AU-PRO@0.3 `+0.005096`. Direct per-image AU-PRO favored ESRGAN on 11/20 anomalies and PSNR on 9/20. The quality-character difference is clear in this subset; the localization ordering is too small and mixed to claim a stable endpoint ranking. These observations justify exactly one full Hazelnut confirmation, not another endpoint or a search.

## Frozen cohort and manifest

MVTec AD Hazelnut `test/` contains 110 images, verified locally before manifest creation: 40 good; 70 anomalous (crack 18, cut 17, hole 18, print 17). The tracked [`full_manifest.csv`](../analysis/restoration_objective_full/full_manifest.csv) contains every image exactly once in lexical relative-path order, with label, defect type, mask path, and image/mask SHA-256. There is no pilot-result-based selection. Its frozen SHA-256 is `2ddb62748c750b3e4fae2b4b0b0cb4f3c354fd02faac74c95117afe1b3e116cc` (LF line endings). The runner checks this hash, reconstructs all rows from the local dataset, and checks 110/40/70 before loading models. A different path is accepted only if its bytes match this hash.

The old `pilot25` profile remains the default. Its manifest SHA-256 remains `4d3b23548b5add0f067bec44330062870cde00a1521b9680198744f32bbf3603` and its 25/5/20 count guard is unchanged in scientific meaning. The `full110` profile uses the same runner and four methods, with a distinct output directory. No arbitrary expected hash can be passed on the command line.

## Clean-reference audit

Historical Branch A `outputs/legacy-patchcore/hazelnut-full391-test110-repro/clean_predictions.npz` contains 110 labels/scores and 110×224×224 masks/maps. Its `test_paths` and the `clean` rows of `per_image.csv` match all current test paths in exactly the manifest's lexical order. Labels match, and all 110 saved masks match the masks recomputed from current files using nearest-neighbor `Resize(256)` and `CenterCrop(224)`, including all-zero good masks. Scores/maps are finite.

Both runners apply RGB conversion, bilinear `Resize(256)`, `CenterCrop(224)`, `ToTensor`, and the same upstream MVTec ImageNet mean/std to Clean. Both use `PatchCore.predict` for scores/maps, the same upstream source commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`, WideResNet50 `layer2+layer3`, 1024/1024 dimensions, patch size 3, IdentitySampler, and CPU exact FAISS. The historical run's model spec equals the current bank metadata spec. Its two bank hashes match the frozen bank: `7c2728899e9e4aeca619d5c6f24ad47456c1603cc16e4c846a80f002c6ddc8b4` and `e665e08ac3d108ae095566df7baf7e966561333fdf50a6d85c6f5d77bfc3f9b4`. There was no calibration threshold in that full Branch A run. Its Clean path does not use the old Pillow Bicubic degradation.

The historical run did not save source-image hashes at inference time, so byte-for-byte identity of *historical* source RGB files cannot be independently proven today. Its local `results.json` also contains a malformed escaped Windows `model_dir` string; the audit read the other JSON fields after redacting that one string in memory, without changing the artifact. Therefore historical Clean predictions are a **contextual no-degradation reference only**, not a numerically exact new-run anchor or a fifth method. Do not rerun Clean for this endpoint question: the four new comparisons all start from the frozen MATLAB-compatible degraded input, and no Clean score is required for their primary analysis. If a future claim requires byte-proven Clean pairing, freeze and run a separate Clean control before making that claim. Never mix historical Pillow-Bicubic scores with new MATLAB-Bicubic scores.

## Frozen input, restorers, detector

Canonical RGB: bilinear `Resize(256)` then `CenterCrop(224)`. Pin BasicSR MATLAB-compatible bicubic, antialiasing enabled, `224×224 → 56×56` RGB uint8. The *same LR bytes* go to all three learned restorers. Bicubic baseline uses that same BasicSR implementation for `56×56 → 224×224`; no Pillow Bicubic in the new four-way comparison.

Variants are exactly `bicubic_x4`, `swinir_x4`, `rrdb_psnr_x4`, and `rrdb_esrgan_x4`, with the pinned pilot source commits, checkpoints, and checkpoint-hash checks unchanged. No Real-ESRGAN, new SR model, fusion, gating, or interpolation alpha. The primary endpoint pair is RRDB-PSNR versus RRDB-ESRGAN. Their official checkpoints differ in training data as well as objective (DF2K versus DF2K+OST); do not attribute a difference to loss alone.

Reuse only the frozen 391-normal Hazelnut Branch A PatchCore bank described above. The runner checks all bank/model metadata and artifact hashes, loads without fitting (`fit_performed=false`), and retains CPU exact FAISS. Do not refit, normalize branches, calibrate thresholds, or use test masks during inference. Masks enter only evaluation.

## Outcomes and per-image analysis

Primary localization outcome: dataset-level pooled AU-PRO@0.3, using the existing 200-threshold implementation. Secondary detection: Pixel AUROC and Image AUROC. Quality: PSNR, SSIM, AlexNet LPIPS (lower is better). Full execution requires `--with-lpips`. F1 and threshold calibration remain absent/null.

For each of the 70 anomalous images, record per-image Pixel AUROC, per-image AU-PRO@0.3, ROI mean, background mean, and ROI–background gap. Relative to the *new* MATLAB-Bicubic map, each learned variant is a localization regression iff its per-image AU-PRO delta is `<0`; among regressions, suppression iff gap delta `<0`, otherwise geometry candidate (`>=0`). Delta `>=0` is improvement/tie. These are map-level descriptions, not proven feature-space mechanisms. No magnitude cutoff.

For each anomaly, directly calculate RRDB-ESRGAN minus RRDB-PSNR for PSNR, SSIM, LPIPS, per-image Pixel AUROC, per-image AU-PRO, ROI mean, and ROI–background gap. Summarize the direct per-image AU-PRO delta by mean, median, minimum, maximum, and ESRGAN/PSNR/tie counts (strict sign, no cutoff). The direct comparison and Bicubic-relative taxonomy answer different questions.

## Pre-frozen uncertainty and figures

- Paired anomalous-image bootstrap of the **mean** direct per-image AU-PRO delta (ESRGAN minus PSNR): resample the 70 paired-image deltas with replacement, sample size 70, 5,000 repeats, NumPy RNG seed 2026; report observed mean and 2.5th/97.5th percentile of bootstrap means. This is not a pooled AU-PRO CI.
- For each learned restorer's Bicubic-relative regression rate, report count/70 and a two-sided 95% Wilson binomial interval, with `z=1.959963984540054`. The denominator is all 70 anomalous images; subtype counts remain descriptive.
- No CI-driven model selection, new significance test, multiple-testing claim, or causal inference.

Pre-register two anomalous-image scatter figures, with one point per image, defect-type color, and separate panels for SwinIR, RRDB-PSNR, and RRDB-ESRGAN. In Figure A, x is `PSNR(restoration) − PSNR(Bicubic)`; in Figure B, x is `LPIPS(Bicubic) − LPIPS(restoration)` (positive means improvement). Both use y = `per-image AU-PRO(restoration) − per-image AU-PRO(Bicubic)`. Report descriptive Spearman rho for each x/y pair in each model panel, using average ranks for ties; undefined if either variable is constant. Do not read correlation as causation. Post-run `quality_localization.csv`, two PNGs, `endpoint_bootstrap.json`, and `regression_intervals.csv` may be produced under this frozen rule; none is a result in this preparation commit.

## Interpretation fixed before results

- **A:** Fidelity/perceptual trade-off persists and localization direction is broadly consistent with the pilot. Retain an endpoint-dependent quality–localization trade-off as a substantive *Hazelnut* result; no objective-causality claim.
- **B:** Quality trade-off persists but localization difference is small or uncertain. Report differing image-quality character with no stable downstream ranking; close model-comparison expansion, do not add GAN models.
- **C:** Localization direction reverses materially. Record the pilot localization signal as sample-sensitive/unstable; do not search for a favorable subset or another endpoint.

All three are valid. No post-hoc numerical cutoff or threshold may be introduced to choose a story. The full Hazelnut result is still development evidence, not external generalization or final Capsule validation. Feature NN-distance work is considered only if a stable scientifically useful endpoint-dependent failure pattern remains. Phase C gating, Capsule, new degradation, new detector, and new endpoint models stay closed. Capsule remains untouched until a separately frozen final method and evaluation plan authorize its single validation use.

## Execution boundary and runtime

Future output mirrors the pilot: `results.json`, `summary.csv`, `per_image.csv`, `regression_taxonomy.csv`, `objective_pair_per_image.csv`, four prediction NPZs, and `images/`. The full direct-pair CSV additionally records ROI-mean delta. The runner refuses a nonempty output directory and verifies manifest/source/checkpoint/bank provenance before inference.

The pilot recorded 342.224 seconds of summed restoration+detector stages over 25 images on an MX570 A. Linear extrapolation to 110 images is about 1,506 seconds (25.1 minutes) **for those timed stages only**. Loading, LPIPS, image writing, and environment differences make full wall time unknown; reserve substantially more than 25 minutes and record the actual wall time. This is an estimate, not a measured full-run result.

From `research_code/` on the CUDA machine, after syncing this preparation commit and installing the pinned dependencies/checkpoints/bank/data, validate the frozen manifest and then run once:

```powershell
.venv\Scripts\python -X utf8 scripts\create_restoration_objective_manifest.py --cohort full110 --check
.venv\Scripts\python -X utf8 scripts\run_restoration_objective_pilot.py --cohort full110 --device cuda --with-lpips --output-dir outputs\restoration-objective\hazelnut-full110-gpu
```

Do **not** run this command during protocol preparation. The original pilot command without `--cohort` still selects `pilot25`.
