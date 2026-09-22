# SR/restoration anomaly research framework

This directory contains a CPU-safe experiment path for the question: can restoration improve image-quality metrics while weakening evidence used by an anomaly detector?

The runnable path is:

```text
original -> deterministic degradation -> optional restoration -> anomaly detector -> metrics/results
```

Every configured restoration run also keeps the `no_restoration` baseline. The built-in anomaly detector is a no-op, so anomaly scores and dataset-level detection metrics remain empty until a real detector is connected.

The historical v0.1 decisions remain in [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md); the current frozen rules are in [docs/EXPERIMENT_PROTOCOL_V0.2.md](docs/EXPERIMENT_PROTOCOL_V0.2.md). The current Screw GPU checklist is in [docs/GPU_HANDOFF.md](docs/GPU_HANDOFF.md).

## Setup and checks

Windows PowerShell with Python 3.11:

```powershell
cd research_code
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python scripts\smoke_test.py
.venv\Scripts\python -m pytest -q
```

Linux:

```bash
cd research_code
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/smoke_test.py
.venv/bin/python -m pytest -q
```

The smoke test creates one synthetic image in a temporary directory, runs degradation, identity restoration, metrics, manifest writing, and removes the temporary files.

## Real CPU pilot

The first real-data path uses MVTec AD `bottle`, Anomalib PatchCore, and the official lightweight SwinIR-S x2 checkpoint. MVTec AD is licensed CC BY-NC-SA 4.0 for non-commercial use. Dataset archives, extracted images, checkpoints, and experiment outputs are ignored by Git.

```powershell
git submodule update --init
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev,pilot]"
New-Item -ItemType Directory -Force checkpoints\swinir | Out-Null
curl.exe -L --fail --output checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth
.venv\Scripts\python scripts\fit_patchcore.py
.venv\Scripts\python scripts\run_cpu_pilot.py
```

`fit_patchcore.py` lets Anomalib download and verify the official MVTec AD archive when it is missing. It fits PatchCore on a deterministic normal-only training split, keeps held-out normal images for threshold calibration, and exports a Torch artifact. `run_cpu_pilot.py` compares clean, bicubic x2, and SwinIR-S x2 images with the same fitted detector. It writes raw NPZ predictions, PSNR/SSIM, image and pixel AUROC, validation-threshold F1, AU-PRO, per-image CSV rows, and a comparison CSV.

The expected SwinIR x2 checkpoint SHA-256 is `193b229909ca89cd8b55de9c9e7fce146ae759d59dfcd78d8feb9dd1d6fa0fd7`. This x2 pilot is limited to `low_resolution` severity 1, whose x2 bicubic degradation matches the public SwinIR-S x2 checkpoint. It does not claim results for Gaussian blur or unmatched x6 restoration.

## Jihyuk-style PatchCore CPU pilot

`run_legacy_patchcore.py` uses Amazon's original PatchCore source at commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`, rather than the Anomalib adapter above. It matches the notebook's WideResNet50, layer2+layer3, 1024/1024 embedding, patch size 3, IdentitySampler, and Resize(256) -> CenterCrop(224) image settings. Its default 16-image training subset and 4-image balanced test subset are a CPU pilot, not a reproduction of the notebook's full training result. The x4 test path downsamples the canonical 224 image to 56, then applies bicubic x4 or optional SwinIR-S x4 restoration. Masks use nearest-neighbor resizing; the upstream notebook's exact mask interpolation and the provenance of its reported result cells remain unverified.

```powershell
git submodule update --init
uv pip install --python .venv\Scripts\python.exe -e ".[dev,legacy]"
.venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 16 --test-limit 4
New-Item -ItemType Directory -Force checkpoints\swinir | Out-Null
curl.exe -L --fail --output checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth
.venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 16 --test-limit 4 --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth
```

The script reuses a checksum-verified local FAISS memory bank on subsequent runs. It writes per-image and summary CSV files, raw prediction NPZ files, and `results.json` with image/pixel AUROC, AU-PRO, PSNR/SSIM, runtimes, and actual FAISS squared-L2 nearest-neighbor distance statistics. F1 uses the 99th percentile of separate held-out normal training images, never test labels. The x4 checkpoint SHA-256 is `09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e`. Set `--train-limit 0 --test-limit 0 --calibration-limit 0` only when ready for the much slower full-memory baseline; F1 is then absent unless an independent calibration split is supplied. Add `--skip-nn-stats` to omit the second FAISS search per image when only detection metrics are needed; nearest-neighbor statistic fields will then be empty. The default `--device cpu` preserves existing runs. On a CUDA-enabled PyTorch environment, `--device cuda` moves PatchCore feature extraction and SwinIR to CUDA while exact FAISS remains on CPU. `--device auto` chooses CUDA only when available; an explicit unavailable CUDA request fails before the experiment starts.

## Two-branch evaluation: reproduction vs detection improvement

Branch A (Jihyuk-setting reproduction) fits on all 391 normal hazelnut training images and reports AUROC/AU-PRO with F1 left empty:

```powershell
.venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 0 --test-limit 0 --calibration-limit 0 --skip-nn-stats --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --output-dir outputs\legacy-patchcore\hazelnut-full391-test110-repro
```

Branch B (detection improvement) splits normal training images 80/20 with a fixed seed (hazelnut: 313 fit / 78 calibration), fits per-variant robust (median/IQR) normalization on calibration normals only, and compares four fixed methods — degraded-only, restored-only, equal-average `mean_0.5_0.5`, and `max` — with F1 thresholds from fused calibration scores. Test labels are never used for fitting, normalization, or thresholds. Hazelnut is the development/exploration category; final validation belongs on an unseen category such as `capsule`:

```powershell
.venv\Scripts\python -X utf8 scripts\run_fusion_patchcore.py --category hazelnut --seed 11 --train-ratio 0.8 --test-limit 0 --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --output-dir outputs\fusion-patchcore\hazelnut-313x78-test110
```

`split.json` stores the exact reused image lists. `--train-limit/--calibration-limit/--test-limit` caps are cheap plumbing checks only, not research results. The pre-fixed five-point Hazelnut saved-prediction ablation selected restored-only (`alpha=0`) by pooled AU-PRO@0.3; no fine search or adaptive gating is authorized. This development result is not an unseen-category estimate.

Branch B accepts the same `--device {cpu,auto,cuda}` option as Branch A. PatchCore and SwinIR use the resolved device; exact FAISS stays on CPU. CUDA timings synchronize before and after fit, restoration, and detector inference. `results.json` records `requested_device`, `actual_device`, `cuda_available`, and `gpu_name` only for CUDA runs.

## Current research sequence

Hazelnut development and the preselected full Screw Branch A stress test are complete under the same x4 checkpoint, detector, preprocessing, pooled AU-PRO@0.3 implementation, and post-hoc taxonomy. The next bounded GPU task is the six-case Screw NN-distance check in `analysis/screw/NN_HANDOFF.md`; do not rerun the full category. A SurgClean restoration-character pilot may follow only after its separate entry gate is satisfied. Capsule remains untouched final validation and must not be used for method selection.

## Run an experiment

Put images under `data/images/`, then run:

```powershell
py -3.11 scripts\run_experiment.py configs\example.yaml
```

Relative paths in a config are resolved from the config file's directory. An existing experiment directory is never overwritten. Change `experiment.id` before rerunning the same config.

The included degradations are `gaussian_blur`, `motion_blur`, `gaussian_noise`, `jpeg_compression`, `brightness`, `contrast`, and `low_resolution`. Severity is an integer from 1 to 5. The runner derives a stable per-image seed from the experiment seed unless a degradation supplies its own `seed`.

Required config sections are shown in [configs/example.yaml](configs/example.yaml). `dataset.limit` provides a cheap CPU/GPU trial guard. Optional fields such as `dataset.split`, `dataset.category`, model checkpoint settings, and `preprocessing` are copied into `run_metadata.json`.

## Outputs

Each run writes `outputs/<experiment-id>/`:

- `run_metadata.json`: config hash, package versions, platform, dataset split/category, preprocessing, and model configs.
- `manifest.jsonl`: source/output paths, stage, degradation parameters, severity, actual seed, restoration model, and reproducibility metadata.
- `results.jsonl`: nested quality-vs-detection schema and per-stage runtime.
- `results.csv`: flat rows for analysis.
- `images/`: degraded/restored images and future anomaly maps.

`detection.dataset_metrics` stays `null` with the no-op detector. AUROC, AU-PRO, F1, and localization metrics must be computed by a real dataset-aware detector/evaluator; the framework does not fill them with dummy values.

Evaluate a detector-produced NPZ file containing `labels`, `scores`, and optionally `masks` plus `anomaly_maps`:

```powershell
py -3.11 scripts\evaluate_predictions.py predictions.npz --output outputs\evaluation.json --image-threshold 0.5 --pixel-threshold 0.5
```

Threshold arguments are optional. If omitted, AUROC/AU-PRO are computed and F1 stays empty. Test labels must not be used to choose a threshold.

Render all degradation severity levels before launching a matrix:

```powershell
py -3.11 scripts\make_degradation_sheet.py data\images\sample.png outputs\degradation-sheet.png --seed 11
```

LPIPS is opt-in:

```powershell
.venv\Scripts\python -m pip install -e ".[lpips]"
```

Then add `lpips` to `metrics`. It is not imported during the normal CPU smoke path.

## Result aggregation and bounded matrices

Combine completed runs and produce a grouped comparison table:

```powershell
py -3.11 scripts\aggregate_results.py outputs\run-a\results.csv outputs\run-b\results.csv --output-dir outputs\comparison
```

Generate configs from a small matrix:

```powershell
py -3.11 scripts\generate_matrix.py configs\matrix.example.yaml --output-dir configs\generated
```

Generation stops before writing if the Cartesian product exceeds `max_runs`. The hard ceiling is 256 configs.

## Adapter locations

- Dataset adapters: `src/sr_anomaly/dataset.py`. Available adapters are `folder`, `mvtec_ad`, `mvtec_ad2`, and `visa_csv`. Labeled adapters populate `ImageSample.mask_path` and attach split/category/label data in `metadata`; MVTec AD 2 private splits deliberately leave labels empty.
- Restoration adapters: `src/sr_anomaly/models.py`. Wrap SwinIR, Restormer, or Real-ESRGAN behind `RestorationModel.restore()`, then register the config name in `build_restoration()`. Keep repository-specific preprocessing and checkpoint loading inside that adapter.
- Anomaly adapters: the same file. Wrap PatchCore or EfficientAD behind `AnomalyDetector.predict()`. Return a raw image score and pixel map in `AnomalyPrediction`; compute AUROC/AU-PRO only after the whole labeled split has been evaluated.
- Previous student code: add a thin adapter around its existing inference entry point. Do not copy model internals into this package unless reuse is impossible.

GPU-specific libraries and large model repositories are intentionally absent. Add them when checkpoints, the previous code, and the Linux GPU environment are available.
