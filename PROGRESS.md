# Progress

Date: 2026-09-20

## Implemented

- CPU-safe framework: deterministic degradations, MVTec AD/AD 2/VisA adapters, manifests, PSNR/SSIM, optional LPIPS, model protocols, YAML runner, CSV aggregation, bounded experiment matrices, image/pixel AUROC and F1, and AU-PRO@0.3.
- Anomalib 2.6.2 PatchCore CPU training/export and official SwinIR-S x2 restoration pilot (scripts/fit_patchcore.py, scripts/run_cpu_pilot.py). Its thresholds come from held-out normal training images.
- Jihyuk-style pilot using the official Amazon PatchCore source pinned to fcaa92f124fb1ad74a7acf56726decd4b27cbcad: WideResNet50, layer2+layer3, 1024/1024 embeddings, patch size 3, IdentitySampler, Resize(256) then CenterCrop(224). It saves a checksum-verified FAISS memory bank and handles FAISS's Windows non-ASCII-path limitation through an ASCII staging directory.
- The legacy pilot compares clean, bicubic x4, and optional official SwinIR-S x4 on the same detector and test images. It records per-image true FAISS squared-L2 nearest-neighbor distances, runtimes, raw NPZ outputs, summary CSV, and a quality-vs-detection comparison. F1 uses only held-out normal images for threshold calibration. The x4 checkpoint SHA-256 is 09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e.
- Downloaded and locally ignored the official full MVTec AD archive, official VisA archive/Anomalib conversion, SwinIR-S x2/x4 checkpoints, and model artifacts. MVTec AD 2 (roughly 32 GB) is not downloaded.

## Verified CPU results

- Python 3.11 audit baseline: 93 passed. Synthetic end-to-end smoke test also passes.
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
- both ROI-background gap and per-image AU-PRO decreased on 14/70 (20.0%); under the current taxonomy these are suppression patterns, and the older "strong failure" name is deprecated.

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

The small-defect hypothesis is not supported in hazelnut so far: Spearman(defect area ratio, ROI-mean delta) = -0.0318, and the suppression-subtype median defect-area ratio (0.02286) is close to the remaining images (0.02091).

Suppression-subtype counts by defect type (historically called strong failure):

- crack: 4/18;
- cut: 1/17;
- hole: 7/18;
- print: 2/17.

The concentration in hole was a follow-up signal, not a final generalization. The later selected-case visual and NN-distance analyses are recorded below and did not establish a clean causal separation.

The first ROI-mean-based oracle is not treated as a valid localization upper bound: choosing the branch with the larger GT ROI raw mean reduced AU-PRO relative to restored-only. Its JSON remains a historical artifact and is not used in the current analysis.

## Protocol v0.2 and saved-prediction reanalysis (2026-09-21)

- `docs/EXPERIMENT_PROTOCOL_V0.2.md` freezes the hazelnut post-hoc taxonomy: 30/70 per-image AU-PRO regressions, partitioned into 14 suppression-type (`gap < 0`) and 16 geometry candidates (`gap >= 0`). It introduces no magnitude cutoff and treats the labels as map-level patterns, not proven feature-space causes.
- `scripts/analyze_hazelnut_failures.py` now ranks worst/best cases by per-image AU-PRO delta, shares the two anomaly-map color limits within each figure, and writes `regression_taxonomy.csv` and `selected_cases.csv`. The historical ROI-mean oracle file is left untouched.
- The new GT-assisted screening oracle gives mean per-image AU-PRO 0.907052 versus restored-only 0.903398 (headroom +0.003655). Choosing whole maps by per-image AU-PRO gives pooled AU-PRO 0.840458 versus restored-only 0.843461 (delta -0.003003); pooled selection is not a guaranteed upper bound.
- Reanalysis used the existing 110-test NPZ files only (`--render-cases 0`); no PatchCore or SwinIR inference was run. At this point the coarse grid was deferred; the later saved-prediction feasibility ablation below executed it and selected restored-only, with no fine search.

## Branch B saved-prediction feasibility ablation (decision recorded before execution, 2026-09-21)

The Branch A oracle headroom is small, but a five-point global scalar fusion check needs no new fit or inference because Branch B predictions are already saved. Testing only alpha=0.5 would not rule out the other coarse weights. The grid `{0.00, 0.25, 0.50, 0.75, 1.00}` and pooled AU-PRO@0.3 as the **sole** alpha-selection metric were fixed before this analysis; Pixel/Image AUROC and Bicubic-relative defect regression are supplementary/risk descriptors. Hazelnut remains development data. Fine search and adaptive gating are not part of this step.

### Observed result (saved predictions only)

`scripts/analyze_fusion_weights.py` read `outputs/fusion-patchcore/hazelnut-313x78-test110/` and wrote `analysis/hazelnut/fusion_weight_search/`. Pooled AU-PRO@0.3 for alpha 0/0.25/0.5/0.75/1 was 0.841263/0.838005/0.833354/0.826236/0.817486. The primary metric selects alpha=0 (restored-only); the best interior alpha 0.25 is 0.003258 below restored-only. Pixel AUROC at alpha=0.5 is higher than at alpha=0 (0.985360 vs 0.985051), but it is not the selection objective. Localization regression counts against Bicubic were 30/27/24/18/0; alpha=1 has zero by definition, so these counts are risk descriptors, not selection criteria. The alpha=0/0.5/1 predictions and recorded evaluations all matched exactly (maximum score/map/metric difference 0). No fine search or adaptive gating was run. This single development-category result does not justify a finer scalar search now; a new, separately specified study would be needed if an interior weight later improves the primary metric over both endpoints.

## Remaining work and boundaries

- Two-branch plan (agreed 2026-09-20): Branch A = Jihyuk-setting reproduction on all 391 hazelnut normals (AUROC/AU-PRO, F1 empty). Branch B = detection improvement on a fixed 80/20 split (313 fit / 78 calibration, seed 11), robust median/IQR per-variant normalization, fixed mean_0.5_0.5 vs restored-only as the first comparison, degraded-only and max as preset baselines. `src/sr_anomaly/fusion.py` plus `scripts/run_fusion_patchcore.py` implement Branch B; `split.json` freezes the reused image lists and all F1 thresholds come from fused calibration normals. The later five-point Hazelnut ablation selected restored-only and does not justify fine search. Hazelnut remains development/exploration; final validation belongs on untouched `capsule` only after all rules are frozen.
- The full hazelnut 110-test evaluation is complete. The next model-inference step, when needed, is preselected cross-category stress on Screw; Grid is optional and Capsule remains untouched final validation. Full IdentitySampler plus exact FAISS search is expensive even with a GPU backbone. For F1, use an independent normal calibration set or leave it empty; do not tune on test labels. Branch B uses its own 313-image bank; the 391 bank must not be reused because its 78 calibration images would leak into the memory bank.
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
    .venv\Scripts\python -X utf8 scripts\analyze_fusion_weights.py
    .venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 16 --test-limit 20 --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --output-dir outputs\legacy-patchcore\hazelnut-pilot-16x20-rerun
    .venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 0 --test-limit 10 --calibration-limit 0 --skip-nn-stats --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --output-dir outputs\legacy-patchcore\hazelnut-full-train-test10-rerun

On a fresh machine, follow the data/checkpoint download commands in README.md first. Each completed legacy output directory is non-overwriting; choose a new --output-dir for a rerun.

## Selected Hazelnut qualitative review (2026-09-21)

Hypothesis: the map-gap suppression and geometry-candidate labels may correspond to visibly different anomaly-map patterns. Condition: nine cases fixed from the prior Hazelnut analysis (three per group), Branch A saved PatchCore maps and GT, Bicubic and SwinIR x4 RGB, shared anomaly-map color scale within each sample. Only the nine SwinIR RGB panels were reconstructed with the original checksum-verified checkpoint (25.3 s on this CPU); no PatchCore fit or inference was rerun. Outputs: `analysis/hazelnut/qualitative_cases/` has nine six-panel figures, a nine-row CSV, and per-case observations. In `crack/013`, AU-PRO fell 0.076146 despite Pixel AUROC rising 0.004057 and map ROI-background gap rising 0.423456; the thin upper GT branch remains diffuse. `crack/001` shows a weaker restored-map hotspot with AU-PRO and gap both falling. The success control `hole/006` gained 0.139957 AU-PRO while its gap fell 0.370210, so raw gap direction alone is not a failure test. These are visual observations, not causal proof. Next: compare official PatchCore patch-to-bank squared-L2 distances for the same nine cases.

## Selected Hazelnut PatchCore NN-distance check (2026-09-21)

Hypothesis: map-gap suppression cases may lose defect-to-background feature separation after SR, while geometry cases may retain it despite lower localization. Condition: the same nine exploratory cases, exact checksum-verified Branch A 391-normal FAISS bank for both x4 branches, official PatchCore embedding and nearest-neighbor squared-L2, continuous GT occupancy averaged over each actual 28×28 feature-grid cell. This mapping approximates ROI membership and does not equal the backbone receptive-field footprint. Saved 224×224 maps supplied per-image AU-PRO/Pixel AUROC/map gaps. There was no fit or whole-test feature inference; all 18 recomputed maps matched saved predictions exactly. Results: mean SwinIR−Bicubic ΔD_defect/Δfeature gap were -0.6123/-0.2491 (suppression, n=3), +0.0044/+0.3506 (geometry candidates, n=3), and +0.1345/+0.4580 (success controls, n=3). Joint ΔD_defect<0 and Δfeature gap<0 occurred in 2/3 suppression cases, 0/3 geometry candidates, and 1/3 controls (`hole/006`); `crack/017` lost defect distance but gained a small +0.00346 feature gap. Thus the selected cases do not cleanly separate a causal feature-suppression mechanism. Retain “suppression” as a map-score pattern; geometry cases are consistent with a spatial coverage/localization issue but do not prove it. Full values and source validation are in `analysis/hazelnut/nn_distance_selected.csv` and `nn_distance_selected_summary.md`. No significance claim is made for n=3 groups.

Next: preselected Screw cross-category stress after freezing the same x4 model/detector, pooled AU-PRO@0.3 primary metric, taxonomy, full-category reporting, and no fusion/threshold tuning. Local CUDA is unavailable and Screw has no fitted PatchCore bank; do not open Capsule. A minimal device switch can prepare the existing Branch A runner for a GPU machine without changing the algorithm.

The Branch A runner now accepts `--device {cpu,auto,cuda}` with `cpu` as the unchanged default. The resolved device is used only for the PatchCore backbone/embedding and SwinIR; exact FAISS remains CPU and the detector model specification remains unchanged, allowing reuse of compatible saved banks. An explicit unavailable CUDA request fails before the run. Result JSON and per-image CSV record the resolved device.

GPU execution support is now shared by Branch A and Branch B. Both keep CPU as the default, use the selected device for PatchCore/SwinIR, and retain `FaissNN(False, 4)` on CPU. CUDA timing synchronizes immediately before and after PatchCore fit, SwinIR restoration, and detector inference; Branch B aggregate calibration/test timing is synchronized as well. Each result JSON adds `requested_device`, `actual_device`, `cuda_available`, and CUDA-only `gpu_name` without changing detector specs, splits, calibration, normalization, fusion, thresholds, metrics, or saved prediction schemas. CPU-only tests pass; numerical parity and timing remain to be checked on an NVIDIA machine.

GPU Screw command after installing a CUDA-enabled PyTorch build:

    .venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --category screw --train-limit 0 --test-limit 0 --calibration-limit 0 --skip-nn-stats --seed 11 --device cuda --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --model-dir checkpoints\legacy-patchcore\screw-seed11-train320 --output-dir outputs\legacy-patchcore\screw-full320-test160

Expected artifacts are a checksum-bound Screw PatchCore bank in the model directory and full-category clean/Bicubic/SwinIR prediction NPZ, CSV, and result JSON in the output directory. Do not reuse a partial output directory after failure; use a new empty output directory.

## SurgClean extension status (2026-09-21)

SurgClean is not present in `data/external/`; only MVTec AD and VisA are available locally. No download, experiment, or metric was attempted. `docs/SURGCLEAN_EXTENSION_PLAN.md` limits a future pilot to Desmoke, two official severity levels, and one matched official model after the dataset structure, terms, split, checkpoint, and evaluation protocol are verified. Because the described adjacent clean frames are unaligned, raw PSNR/SSIM is not accepted as a primary paired conclusion without an official alignment/evaluation procedure. This extension remains separate from MVTec and is lower priority than the frozen Screw stress test.

## Generic cross-category saved-prediction analysis (2026-09-21)

`scripts/analyze_cross_category.py` freezes the Hazelnut per-image taxonomy and deterministic case ranking before Screw results exist. It reads only a completed Branch A run directory and writes `per_anomaly.csv`, `regression_taxonomy.csv`, `summary.json`, `selected_cases.csv`, and `CROSS_CATEGORY_NOTE.md`; it cannot fit or run PatchCore/SwinIR. Applied to the saved Hazelnut run, it reproduced 70 anomalous images, 30 localization regressions (14 suppression, 16 geometry candidates), 40 improvement/ties, and the four stored mean deltas to floating-point precision. Synthetic guard/ranking tests pass. Screw inference and Screw analysis outputs remain ungenerated.

## Device parity and category reporting tools (2026-09-22)

`scripts/compare_cpu_cuda_runs.py` freezes exact artifact checks and configurable numeric comparison (`atol=rtol=1e-5` by default) for the saved CPU/CUDA fusion smoke runs. Device metadata may differ; model/split/checkpoint/method metadata, prediction shapes, labels, and masks may not. It reports numeric, raw-prediction, and separate runtime differences. No CUDA result or parity output exists yet. `scripts/aggregate_category_results.py` reads stored legacy run and cross-category summaries without inference or metric recomputation. `analysis/reporting/category_summary.csv` and `.md` currently contain Hazelnut only; Screw is omitted until both required artifacts exist.

## Research and reproducibility audit (2026-09-22)

`docs/RESEARCH_AUDIT.md` records the design, code, artifact, performance, and claim-boundary review. The audit added fail-fast verification for the frozen SwinIR checkpoint, Branch B split replay, cross-category source configuration, reporting/parity source consistency, and a read-only full-run preflight. The existing Hazelnut cross-category summary is now tracked under `analysis/hazelnut/` so the reporting table no longer depends on an ignored derived file. No saved prediction or research metric was recomputed. All 93 tests pass. Local Screw execution remains blocked only by unavailable CUDA; the dataset, pinned sources/checkpoint, and frozen command are present, while the Screw bank and result artifacts do not yet exist.

## Screw full cross-category result (2026-09-22)

- **Hypothesis:** the Hazelnut aggregate localization benefit and sample-level regression pattern may recur in Screw under the unchanged x4 protocol.
- **Condition:** received CUDA Branch A artifact, 320 normal train / 160 test (41 normal, 119 anomalous), seed 11, no calibration/F1, pinned PatchCore and SwinIR-S x4. Analysis reused saved predictions only.
- **Baseline:** Bicubic x4. SwinIR-S x4 is the fixed comparison; no fusion or test-label tuning.
- **Metric:** pooled AU-PRO@0.3 primary; Pixel/Image AUROC and PSNR/SSIM secondary; the Hazelnut-frozen per-image taxonomy describes heterogeneity.
- **Result:** SwinIR minus Bicubic was +2.437479 dB PSNR, +0.016426 SSIM, +0.198606 Image AUROC, +0.019490 Pixel AUROC, and +0.055000 pooled AU-PRO. Of 119 anomalous images, 23 regressed in per-image AU-PRO; all 23 met the suppression-pattern rule and none met the geometry-candidate rule. The other 96 improved or tied. Regressions were concentrated in `thread_side` (12/23 images) and `thread_top` (8/23) within this category.
- **Interpretation:** the aggregate restoration benefit and sample-level regression coexistence recur in Screw. The subtype composition differs from Hazelnut (14 suppression / 16 geometry): Screw's 23 regressions are all map-score suppression patterns.
- **Limitation:** two MVTec categories do not establish generality. Defect-type concentration is descriptive, and suppression is not a proven feature-space cause. The received ZIP does not include the 320-normal FAISS bank.
- **Next experiment:** run the frozen six-case selected NN-distance handoff only after the exact Screw bank is copied from the GPU machine. Do not open Capsule or add Grid/SurgClean before that check is recorded.

Outputs are under `analysis/screw/` and the two-category paper table under `analysis/reporting/`. The source ZIP SHA256 is `DB6B7CAB2F356B4C48710E29A9C0D145957E9816BAB910AF50AB3F43A334B5D6`. No full GPU inference was run on this CPU machine. All 96 tests pass after adding the defect-type, saved-map rendering, and bounded selected-manifest checks.
