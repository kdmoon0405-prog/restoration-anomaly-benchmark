# SR/restoration anomaly research framework

This directory contains a CPU-safe experiment path for the question: can restoration improve image-quality metrics while weakening evidence used by an anomaly detector?

The runnable path is:

```text
original -> deterministic degradation -> optional restoration -> anomaly detector -> metrics/results
```

Every configured restoration run also keeps the `no_restoration` baseline. The built-in anomaly detector is a no-op, so anomaly scores and dataset-level detection metrics remain empty until a real detector is connected.

The pre-experiment decisions are recorded in [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md). The first GPU operator checklist is in [docs/GPU_HANDOFF.md](docs/GPU_HANDOFF.md).

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
