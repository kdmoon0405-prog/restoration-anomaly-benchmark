# Normal-bank domain study

## Question and scope

This study asks whether changing the RGB domain of the normal PatchCore fit bank changes anomaly detection when every query image and its restoration are held fixed. It is a new 2×2 study. Historical Branch B/full110 summaries are not copied into its tables; a prior bank or prediction cache can only be reused after byte-level compatibility has been established.

The initial category queue is Hazelnut seed 11, Screw seed 11, then Hazelnut and Screw seeds 23 and 37. The fixed seed list is `(11, 23, 37)`. Capsule is gated until the team supplies a receipt confirming prior test-label/output use. It must not be described as untouched based only on this repository's history.

The first PatchCore queue is 2 categories × 3 seeds × 4 cells. If the Capsule history receipt and staged-study gates pass later, the maximum planned scope becomes 3 categories × 3 seeds × 4 cells = 36 dataset evaluation conditions. These are queues, not completed results. Each category/seed/domain fit is performed once and reused for its two query domains. Runs are sequential; no simultaneous model banks are loaded.

## Frozen 2×2 conditions

| Normal fit-bank RGB | Query Bicubic x4 | Query SwinIR-S x4 |
| --- | --- | --- |
| Clean canonical RGB | clean-bank / bicubic-query | clean-bank / SwinIR-query |
| Canonical RGB → Bicubic x4 degradation → SwinIR-S x4 restoration | restored-bank / bicubic-query | restored-bank / SwinIR-query |

For restored fit images, the code applies the degradation and restoration to canonical RGB before tensor conversion and ImageNet normalization. It never reconstructs RGB from an already normalized tensor. Both banks use the same ordered normal fit paths, 80/20 train/calibration split, identity patch sampler, WideResNet50-2 layers `layer2`/`layer3`, 224-pixel center crop, 1024-dimensional embedding, 3-pixel patch, CPU exact FAISS, and PatchCore implementation commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`. The bank length is checked against the fit image count × 784 patches and all vectors must be finite.

The official test set is never used for fit or calibration. For each train/seed split, calibration contains normal train/good images only. The normal calibration set is evaluated separately against each fitted bank and query variant. Every cell gets its own median/IQR normalization (existing standard-deviation and unit fallbacks) and q=0.99 thresholds from that cell's normal calibration predictions.

The query variants are computed once per image and reused across both bank fits. Each raw artifact carries the ordered test image hashes and RGB hashes for Bicubic and SwinIR queries. Completion checks compare those identities between banks. PSNR/SSIM are computed once per test query and stored in `query_quality.csv`; quality is not duplicated as a bank effect.

## Preprocessing and metrics

The image preprocessing, SwinIR-S x4 checkpoint, PatchCore adapter, and raw prediction function are reused from `scripts/run_fusion_patchcore.py`. The local WideResNet50-2 ImageNet V1 checkpoint must match SHA-256 `95faca4d11227dddf8633dbb5ff6c8a9003c1aa5b8945c73834b8007b10950b8`; the SwinIR checkpoint must match the SHA recorded in that runner. Both checkpoints load from local paths, so no implicit torchvision backbone download is needed. The query path is canonical clean RGB → 56×56 Bicubic downsample → either the existing Bicubic x4 upsample or SwinIR-S x4 restoration.

Primary metric is the existing pooled AU-PRO@0.3. Secondary metrics are image AUROC, pixel AUROC, calibration-threshold F1, query PSNR/SSIM, and anomalous-image per-image AU-PRO. Normal per-image AU-PRO is blank/not applicable. Research metrics are computed only after all test predictions and masks have been produced; test labels do not select models, fit data, calibration, or thresholds.

Analysis keeps two contrasts separate:

- **Bank-domain effect:** restored-bank minus clean-bank for the same query.
- **Query-domain effect:** SwinIR-query minus Bicubic-query for the same bank.

Pooled AU-PRO deltas are point estimates. The paired percentile bootstrap is only for the mean anomalous-image per-image AU-PRO delta; it is not reported as a pooled AU-PRO confidence interval. Per-image rows retain the sample path and defect subtype. Defect summaries and best/worst cases use metric delta order with lexical path tie-breaking. Seed variation is descriptive; the same test images repeated across seeds are not independent samples.

## Output and integrity

Run outputs go to a fresh path:

```powershell
.venv\Scripts\python.exe scripts\run_bank_domain_study.py `
  --category hazelnut --seed 11 --device cuda `
  --data-root data\external\MVTecAD `
  --run-id <unique-run-id>
```

Each run directory contains `status.json`, `raw_clean.npz`, `raw_swinir_restored.npz`, `test_masks_for_local_analysis.npz`, `summary.csv`, `per_image.csv`, and `query_quality.csv`. Raw query score/maps, calibration score/maps, masks, ordered sample identity, bank hashes, input hashes, package versions, runtime, resource snapshots, and file hashes are retained. The actual in-memory bank/index is not redundantly serialized; its feature count, finite-value check, byte count, and SHA-256 are recorded before the index is freed. Failed run directories are preserved. Retry with a fresh run-id; do not replace failed outputs.

Analyze only a hash-verified complete run, with one `--run-dir` argument per category/seed:

```powershell
.venv\Scripts\python.exe scripts\analyze_bank_domain_full_runs.py `
  --run-dir outputs\bank-domain-study\<run-id>\hazelnut\seed11 `
  --output-dir outputs\bank-domain-study-analysis\<analysis-id>
```

The analyzer rechecks run status, expected cell/sample order, raw NPZ shapes/finiteness, bank hashes, and the shared query identity before writing pooled contrasts, paired per-image deltas and bootstrap CIs, defect summaries, quality, normal-calibration changes, runtime/resource tables, and its SHA-256 manifest.

RAM planning is a conservative visible-payload scenario (`3 × bank bytes + one 8-image embedding chunk + 2 GiB reserve`); it is not a measured peak. Disk planning reserves space for the four full-resolution raw map arrays plus a 2 GiB reserve; it is not a promise that all future runs fit. Current available RAM and disk are checked before each run, and available RAM is checked again before each sequential bank fit. Runtime-reported CUDA peak allocation is scoped to the PatchCore fit/inference phase after a fresh peak-stat reset; it excludes the earlier query restoration phase. It is not whole-process peak VRAM.

## Required inputs and current gate

The current checkout contains the VisA inputs and both required model checkpoints, but no MVTec AD Hazelnut or Screw data. The official category package has not been downloaded. No MVTec download is triggered by the runner, and it never fetches all 15 categories. The run exits before loading the model if the selected category directory is missing.

Provide these official MVTec AD folders under `data/external/MVTecAD/`, plus `dataset_provenance.json`:

- `hazelnut/train/good/` and the complete `hazelnut/test/` normal and anomaly subtype folders with matching `hazelnut/ground_truth/<subtype>/<image-stem>_mask.png` masks.
- `screw/train/good/` and the complete `screw/test/` normal and anomaly subtype folders with matching `screw/ground_truth/<subtype>/<image-stem>_mask.png` masks.
- The license/attribution text from the official package, official download/source information, downloaded archive SHA-256, and an extracted file inventory/SHA-256 record.

Check the category counts against the official MVTec AD paper before running: Hazelnut has 391 train-good, 40 test-good, and 70 defective test images across 4 defect types; Screw has 320 train-good, 41 test-good, and 119 defective test images across 5 defect types. See the [official dataset paper](https://www.mvtec.com/fileadmin/Redaktion/mvtec.com/05_research_teaching/datasets/mvtec_ad.pdf). The new 80/20 split is made only from those official train-good images, so Hazelnut seed 11 gives 313 fit / 78 normal-calibration images.

The provenance receipt must identify `MVTec AD`, the official source URL, delivered category names, a 64-character archive SHA-256, the relative license-file path, and the license file SHA-256. If the original archive is retained under the data root, include its relative path as `archive_file` and the runner verifies that hash too. Every fit/calibration/test image and anomaly mask is independently hashed into the run status.

MVTec AD is distributed under CC BY-NC-SA 4.0 for non-commercial research; obtain these categories from the [official MVTec AD page](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) and preserve its license/attribution. This folder layout has no split CSV: the official `train/good`, `test`, and `ground_truth` directories define its split. Do not substitute a mirror with unknown provenance or pull the full dataset to avoid the category-only handoff.

**Exact CPU input handoff request:** Hazelnut and Screw category folders listed above are entirely absent from this PC. Please provide only those two official categories (all `train/good`, all test subtypes, matching pixel masks), the original license/attribution, and `dataset_provenance.json` with official source URL, archive SHA-256, license-file hash, and extracted inventory hashes. No other MVTec category or VisA download is needed for the first four PatchCore batches.

Capsule requires a separate receipt with `all_team_members_confirmed_no_test_use: true`, `patchcore_hazelnut_screw_seed11_reviewed: true`, and `efficientad_seed11_complete_or_protocol_frozen: true` before any Capsule test labels or predictions are opened. Without it, Capsule is blocked and cannot support an untouched-category claim.

## EfficientAD follow-up gate

Only after Hazelnut/Screw PatchCore seed-11 results are complete should the EfficientAD seed-11 comparison start. Use a maintained upstream implementation in a separate environment if needed; do not reimplement the detector or modify the PatchCore environment. The [Anomalib EfficientAD implementation](https://github.com/open-edge-platform/anomalib/tree/main/src/anomalib/models/image/efficient_ad) is a candidate to pin and review. Its documented training uses ImageNette images in the training loss and computes map-normalization quantiles on normal/good validation data. Freeze its source commit, dependencies, teacher checkpoint, ImageNette source/hash, geometry, and normal-only validation/calibration path before training. Never select a checkpoint or threshold from MVTec test anomalies. If the chosen maintained recipe requires anomaly-labelled validation, stop that comparison and declare a different protocol before using labels.

The planned detector comparison is Hazelnut/Screw seed 11 with query inputs Clean, Bicubic x4, and SwinIR x4. It is not multiplied across all PatchCore bank-domain cells. Category-specific training is permitted only on normal training images. Test masks enter after prediction, at evaluation only.

## Implementation checks

`tests/test_bank_domain_study.py` contains pure-array tests plus a small fake-model end-to-end exercise. The fake test runs the orchestration with temporary synthetic images, checks normal-only fit batches and four-cell payload/identity binding, preserves a simulated failure, then succeeds with a fresh run-id. It does not train the real PatchCore model, touch MVTec data, or count as a GPU/model result.
