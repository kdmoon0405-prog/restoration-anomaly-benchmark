# GPU pilot handoff

## Goal

Complete one paired pilot on MVTec AD `bottle`:

```text
clean test reference
degraded test -> PatchCore
degraded test -> one restoration model -> the same PatchCore
```

Do not expand to every dataset or restoration model until this pilot produces complete artifacts.

## Fixed pilot decisions

- Fit PatchCore only on clean `train/good` images.
- Create a deterministic normal-only validation subset before fitting.
- Reuse the same fitted PatchCore instance for the paired `no_restoration` and `restored` branches.
- Dataset: MVTec AD `bottle`.
- Degradations: Gaussian blur and low resolution.
- Severities: 1, 3, and 5.
- Seeds: 11, 29, and 47.
- Run one restoration checkpoint at a time.

This gives 18 experiment cells and 36 paired result rows. A matched-transform detector fit is a separate follow-up experiment, not part of this pilot.

## 1. Record the environment

Clone the repository and verify the existing CPU path before editing it:

```powershell
git clone https://github.com/kdmoon0405-prog/restoration-anomaly-benchmark.git
cd restoration-anomaly-benchmark
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts\smoke_test.py
nvidia-smi
```

Save the following in `environment.txt`:

- operating system;
- GPU name and VRAM;
- NVIDIA driver and CUDA runtime;
- Python, PyTorch, torchvision, and Anomalib versions;
- output of `torch.cuda.is_available()`;
- the exact dependency installation commands.

Keep an exact `pip freeze` output in `pip-freeze.txt`. Do not replace the existing CPU dependency file with a machine-specific CUDA lock file.

## 2. Validate the data

Place the official MVTec AD category under `data/mvtec_ad/bottle/`. Do not commit the dataset.

Confirm that the adapter sees:

- `train/good` as normal training data;
- `test/good` as normal test data;
- every defect subdirectory as anomalous test data;
- the matching `ground_truth` masks.

Store the normal train/validation file lists and split seed. Record the dataset source and archive checksum.

## 3. Connect PatchCore

Use a maintained implementation such as Anomalib rather than copying PatchCore internals.

The current common detector interface covers inference only. The minimum integration is:

1. add `scripts/fit_patchcore.py` to create the memory bank/checkpoint from normal training images;
2. add a thin `PatchCoreAdapter` that loads the fitted artifact and returns image scores and full-resolution anomaly maps;
3. register `patchcore` in `build_anomaly_detector()`;
4. record backbone, feature layers, input size, normalization, coreset ratio, seed, and package version.

First produce the clean reference and all 18 `no_restoration` cells. Do not tune settings using test labels.

## 4. Connect one restoration model

Before coding, verify that the public checkpoint was trained for the selected degradation. Record its official source, license, and SHA-256.

Implement a thin `RestorationModel.restore()` adapter and register its config name. Its returned image must be RGB and match the original image size before quality or detector evaluation.

There is one scale-handling constraint: the current `low_resolution` degradation downsamples and bicubic-upsamples back to the original size. A SwinIR or Real-ESRGAN super-resolution checkpoint must not be treated as a valid native low-resolution experiment until the adapter receives the native reduced image or the degradation contract is extended. Do not hide an extra resize inside the adapter without recording it.

Restormer should likewise be used only when its checkpoint degradation matches the configured blur. If no available checkpoint matches, finish the PatchCore baseline and report the mismatch instead of forcing a restoration result.

## 5. Export and evaluate

Export detector predictions as NPZ arrays:

- `labels`: `[N]`;
- `scores`: `[N]`;
- `masks`: `[N, H, W]`;
- `anomaly_maps`: `[N, H, W]`.

Run the existing evaluator without F1 thresholds unless a validation-derived threshold was fixed in advance:

```powershell
.venv\Scripts\python scripts\evaluate_predictions.py outputs\pilot\predictions.npz --output outputs\pilot\evaluation.json
```

Required metrics are image AUROC, pixel AUROC, and AU-PRO@0.3. Report image or pixel F1 only with a stored validation-derived threshold. Anomaly maps and masks must have identical shapes; NaN and infinity values are failures.

## Deliverables

Commit only code, configs, and short environment metadata:

- PatchCore fitting script and adapter;
- one restoration adapter, if a matching checkpoint exists;
- exact YAML configs;
- `environment.txt` and `pip-freeze.txt`;
- train/validation split lists and seeds;
- checkpoint source and SHA-256 records;
- a short failure/OOM log.

Transfer datasets, checkpoints, memory banks, NPZ files, anomaly maps, and full output directories outside Git. The handoff must include:

- every `run_metadata.json`, `manifest.jsonl`, `results.jsonl`, and `results.csv`;
- `predictions.npz` and `evaluation.json`;
- an aggregated comparison CSV;
- the exact command used for every run.

## Acceptance checks

- All existing tests and the smoke test still pass.
- All 18 cells have paired `no_restoration` and `restored` rows when restoration is available.
- The same sample, degradation, severity, seed, and fitted detector are used within each pair.
- Image AUROC is present; pixel AUROC and AU-PRO are present when masks exist.
- Test labels were not used to select thresholds, checkpoints, severities, or preprocessing.
- A fresh clone can reproduce the result structure from the committed commands and configs.

