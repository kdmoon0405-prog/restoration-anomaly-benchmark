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

All three are valid. No post-hoc numerical cutoff or threshold may be introduced to choose a story. The full Hazelnut result is still development evidence, not external generalization or final Capsule validation. The dated amendments below define the final classification and stop rule. Additional NN-distance work, Phase C gating, Capsule, new degradation, new detector, and new endpoint models are closed for this graduation project.

## Execution boundary and runtime

Future output mirrors the pilot: `results.json`, `summary.csv`, `per_image.csv`, `regression_taxonomy.csv`, `objective_pair_per_image.csv`, four prediction NPZs, and `images/`. The full direct-pair CSV additionally records ROI-mean delta. The runner refuses a nonempty output directory and verifies manifest/source/checkpoint/bank provenance before inference.

The pilot recorded 342.224 seconds of summed restoration+detector stages over 25 images on an MX570 A. Linear extrapolation to 110 images is about 1,506 seconds (25.1 minutes) **for those timed stages only**. Loading, LPIPS, image writing, and environment differences make full wall time unknown; reserve substantially more than 25 minutes and record the actual wall time. This is an estimate, not a measured full-run result.

From `research_code/` on the CUDA machine, after syncing this preparation commit and installing the pinned dependencies/checkpoints/bank/data, validate the frozen manifest and then run once:

```powershell
.venv\Scripts\python -X utf8 scripts\create_restoration_objective_manifest.py --cohort full110 --check
.venv\Scripts\python -X utf8 scripts\run_restoration_objective_pilot.py --cohort full110 --device cuda --with-lpips --output-dir outputs\restoration-objective\hazelnut-full110-gpu
```

Do **not** run this command during protocol preparation. The original pilot command without `--cohort` still selects `pilot25`.

## Pre-inference preregistration hardening (2026-09-29, after `982cbe0`)

An external design review occurred after preparation commit `982cbe0` and before any full110 inference. This dated amendment supersedes the qualitative A/B/C wording above; it does not alter the cohort, manifest/hash, degradation, models/checkpoints, PatchCore bank, primary pooled AU-PRO@0.3, strict-sign taxonomy, bootstrap seed/repeats, or GPU command. The review itself remains private/local.

Define every direct endpoint delta as RRDB-ESRGAN minus RRDB-PSNR. Report quality-trade-off reproduction independently as `mean_delta_psnr < 0 AND mean_delta_lpips < 0`. Classify *localization* on all 70 anomalous images by this deterministic rule:

- **A:** pooled AU-PRO delta `> 0`, mean paired per-image AU-PRO delta `> 0`, and 95% bootstrap CI lower bound `> 0`.
- **C:** pooled AU-PRO delta `< 0`, mean paired per-image AU-PRO delta `< 0`, and 95% bootstrap CI upper bound `< 0`.
- **B:** every other result, including mixed directions, near-zero deltas, or a CI containing zero.

Pooled AU-PRO and mean per-image AU-PRO are different estimands. A and C require agreement of both directions and uncertainty excluding zero. Quality trade-off is reported separately and cannot force A/B/C. No effect-size threshold chooses a case, and no case proves objective causality.

Keep regression taxonomy at `delta_per_image_aupro < 0`. Add a *secondary* magnitude sensitivity for each learned model relative to the new MATLAB Bicubic baseline: for each frozen `tau ∈ {0, 0.005, 0.01, 0.02, 0.05}`, report `count(delta < -tau)` and `count / anomalous-image denominator`. No tau is privileged as the true or meaningful cutoff. For direct RRDB per-anomaly deltas at the same tau grid, report counts `delta > +tau` and `delta < -tau`; do not select a model from these counts. If applied to historical Hazelnut/Screw artifacts, label these counts **post-hoc sensitivity**, not preregistered analysis. Pilot tau counts in this code-validation step are also post-hoc and do not revise the pilot GO/STOP decision.

The full anomalous set comprises 20 images already in pilot25 and 50 that were not. The primary result uses all 70. Separately label the 50 as the **pilot-unseen within-category confirmation subset** and report its direct endpoint per-image AU-PRO mean, median, min/max, positive/negative/tie counts, and the same tau sensitivity. The overlapping pilot20 is a reproducibility check: compare each future full-run per-image model metric against the original pilot artifact using `atol=rtol=1e-5`, report mismatches explicitly, and do not use overlap or unseen50 to redefine A/B/C. Neither subset is external validation.

For each learned model, report the count and rate of `delta_roi_bg_gap < 0` both among regression images and among non-regression images. These denominators provide base-rate context for suppression counts. The taxonomy remains a descriptive post-inference anomaly-map pattern, not an independently proven feature-space mechanism; selected NN-distance cases are consistency evidence only. No normalized-gap taxonomy is introduced.

The primary descriptive figure is now a two-panel presentation: (A) sorted **direct RRDB ESRGAN-minus-PSNR** per-image AU-PRO deltas for all anomalous images, one visible mark per image, defect-type color, and a visible zero line; (B) learned-model Bicubic-relative regression counts across the frozen tau grid. The originally registered PSNR-gain and LPIPS-improvement versus AU-PRO-gain scatter figures remain supporting figures, with descriptive per-model Spearman rho. Do not hide near-zero marks or interpret rho causally.

`scripts/analyze_restoration_endpoint_full.py` is frozen before full inference. It reads completed runner CSV/JSON and the tracked manifests only, never imports or calls restoration/PatchCore. It writes `analysis_summary.json`, `endpoint_bootstrap.json`, `regression_intervals.csv`, `magnitude_sensitivity.csv`, `endpoint_pair_sensitivity.csv`, `taxonomy_base_rates.csv`, `quality_localization.csv`, and the four registered PNG figures. AlexNet LPIPS and existing aligned RGB outputs could support a defect-ROI fidelity descriptor, but the tracked pilot artifact lacks those RGB files. ROI fidelity is intentionally deferred: adding image-loading and a new metric now is unnecessary for this preregistered comparison, and it is not an A/B/C criterion.

Only after the future full runner has completed, derive the frozen analysis without rerunning any model:

```powershell
.venv\Scripts\python -X utf8 scripts\analyze_restoration_endpoint_full.py --run-dir outputs\restoration-objective\hazelnut-full110-gpu --output-dir analysis\restoration_objective_full\derived
```

## Second pre-inference review hardening (2026-10-01, after `607510b`)

A second external adversarial review was conducted before inference. No full110 prediction or result exists at this amendment. This section supersedes the previous A/B/C and subset-confirmation rules only where explicitly stated; all frozen scientific inputs, metrics, taxonomy, tau grid, bootstrap, figures, and execution commands remain unchanged.

The contribution is quantifying the magnitude and distribution of localization changes, their relation to baseline performance, and their association with conventional image quality. The existence of strict-sign regressions alone is not the headline or a practical failure rate. Report in this order: aggregate quality/detection; per-image delta distribution; magnitude sensitivity; baseline-performance diagnostic; quality–localization association; supporting taxonomy.

### Final interpretation and confirmation

All direct deltas are RRDB-ESRGAN minus RRDB-PSNR. Let `P` be full110 pooled AU-PRO delta, `D70` the mean paired per-image AU-PRO delta over all 70 anomalies, `CI` its existing paired-bootstrap 95% interval, and `D50` the mean over the 50 anomalies absent from pilot25.

- **A:** `P > 0 AND D70 > 0 AND CI.lower > 0 AND D50 > 0`.
- **C:** `P < 0 AND D70 < 0 AND CI.upper < 0 AND D50 < 0`.
- **B:** every other outcome, including a zero/mixed unseen50 direction.
- Within B only, **B-small** means `CI` is fully contained in `[-0.01, +0.01]`, inclusive; **B-uncertain** covers other B outcomes. This band is a pre-declared magnitude descriptor, not an industrial equivalence margin, statistical equivalence, practical equivalence proof, or non-inferiority.

Quality-trade-off reproduction remains separately `mean_delta_psnr < 0 AND mean_delta_lpips < 0`; it cannot choose A/B/C. Checkpoints differ in training data as well as objective, so there is no objective-only causal claim.

Retain pilot20 overlap reproducibility and anomalous pilot-unseen50 summaries. Additionally, the **pilot-unseen85 within-category subset** comprises every test image absent from pilot25: 35 normal + 50 anomaly. Read the four saved NPZs in manifest order, validate paired shapes/labels/masks and CSV score order, and reuse existing evaluation to report pooled AU-PRO, Pixel AUROC, and valid Image AUROC per variant, plus direct RRDB pooled delta. These are secondary confirmation, not external validation, an independent dataset, or a held-out test set. A/B/C uses `P/D70/CI/D50`, never unseen85 pooled AU-PRO.

Pooled AU-PRO is reported as a point estimate; the preregistered paired bootstrap quantifies uncertainty of the mean anomalous-image AU-PRO difference, not pooled AU-PRO. No expensive pooled bootstrap or Wilcoxon is added: they address different estimands or add a test not needed for this frozen comparison.

### Magnitude, baseline, and map context

For each learned restorer versus MATLAB Bicubic, retain every frozen tau count/rate. Add inclusive `count/rate(|delta AU-PRO| <= 0.01)` and minimum, 25th percentile, median, 75th percentile, maximum (NumPy's default linear quantiles) in `localization_delta_distribution.csv`. No threshold is selected as the true failure cutoff.

Sort the 70 anomalies by `(Bicubic per-image AU-PRO, lexical sample path)` ascending. Split into low/middle/high groups of **23/23/24**. For each learned restorer and group, `baseline_tercile_regression.csv` records count, mean baseline AU-PRO, mean delta, strict regression count/rate, and `delta < -0.01` count/rate. Report descriptive Spearman between baseline AU-PRO and restoration delta, with average-rank ties. This is a ceiling/baseline association diagnostic, not regression-to-the-mean causality or a new primary question.

`taxonomy_contingency.csv` makes four cells explicit per restorer: negative/nonnegative AU-PRO delta crossed with negative/nonnegative ROI–background-gap delta. Existing base-rate denominators and strict-sign taxonomy remain unchanged. This is a post-inference anomaly-map description, not a mechanism classifier. Selected PatchCore NN-distance analyses are historical consistency/resolution-level diagnostics only: maps derive from those distances, so they are not independent mechanism evidence.

Report the four-method quality/localization ordering descriptively from saved `summary.csv` (also carried into `analysis_summary.json`). Keep the per-image Spearman associations for each learned restorer distinct from this method-level ranking; four methods are not a correlation analysis. No binary rho threshold is adopted. Within this setup, quality improvement may not guarantee localization improvement for each image; it does not establish that PSNR/LPIPS is an unreliable proxy in general. The optional method-level plot is omitted because the aggregate table already supplies the comparison. ROI fidelity, including arbitrary 8-pixel ROI PSNR and new MAE/MSE families, stays deferred; the frozen metrics answer the central question without another spatial choice.

### Execution record and end of the GPU branch

Runner changes are provenance only. Retain repository HEAD, requested/actual device, GPU name, `fit_performed=false`, bank/detector, checkpoint and manifest hashes, and existing per-stage timings. Add Python/PyTorch/torch-CUDA-build/cuDNN versions; LPIPS package version when enabled; exact `sys.argv`, `sys.orig_argv` (including interpreter flags), and parsed arguments; and `artifact_sha256` for the four CSVs (`summary`, `per_image`, `regression_taxonomy`, `objective_pair_per_image`) and four prediction NPZs. End-to-end `wall_clock_seconds` spans main entry through setup, inference, evaluation, file writes, and artifact hashing, with final device synchronization; it excludes interpreter import startup and final `results.json` serialization. No RGB-per-file hashes or self-hash are required. Scientific outputs and their computation are unchanged.

Additional derived outputs are `localization_delta_distribution.csv`, `baseline_tercile_regression.csv`, `taxonomy_contingency.csv`, and, for a completed full run only, `pilot_unseen_confirmation.csv`; summary JSON includes the final case, B descriptor, baseline association, and unseen85 metrics. There are no empty pre-run result placeholders. Pilot25-derived additions are post-hoc code-validation descriptors only, not a changed pilot decision.

**One valid full110 execution closes this restoration-endpoint GPU branch for every A/B/C outcome.** No further endpoints, Real-ESRGAN, network interpolation, NN-distance cases, adaptive gating/Phase C, Capsule, new degradation/detector, Screw reruns, or SurgClean follow. Existing selected NN analyses may remain supporting appendix evidence. Capsule stays unused in the graduation thesis; no untouched-category final generalization claim is made. Any expansion requires a separately designed future study, not a continuation triggered by full110. Full110 is now ready for one execution; no further preregistration changes are planned.
