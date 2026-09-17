# Progress

Date: 2026-09-18

## Completed

- Added the `research_code/` scaffold, package metadata, dependency files, local ignore rules, example configs, scripts, tests, and output directory.
- Added deterministic severity 1-5 implementations for Gaussian blur, horizontal motion blur, Gaussian noise, JPEG compression, brightness, contrast, and low-resolution down/up-sampling.
- Added the generic image-folder dataset adapter, stable sample IDs, root-confined output path helpers, and JSONL manifest records with exact degradation parameters and derived seeds.
- Added MVTec AD, MVTec AD 2, and VisA split-CSV adapters with image labels, mask paths, split/category metadata, and hidden-label handling for MVTec AD 2 private splits.
- Added PSNR and RGB SSIM with an optional, lazy LPIPS path.
- Added common dataset, restoration, and anomaly-detector protocols. Identity restoration and a no-op anomaly detector keep the pipeline runnable without model code.
- Added YAML-driven execution with an always-present no-restoration baseline, per-stage runtime, nested quality-vs-detection results, flat CSV results, and non-overwriting experiment directories.
- Added CSV aggregation/comparison tables and bounded matrix generation. Matrix expansion stops above the configured limit or the hard ceiling of 256 runs.
- Added image AUROC/F1, pixel AUROC/F1, AU-PRO@0.3, strict mask/map shape checks, an NPZ evaluation CLI, and degradation contact-sheet generation.
- Added a versioned experiment protocol, MIT license, and GitHub Actions workflow for Python 3.11 CPU tests.
- Documented integration points for PatchCore, EfficientAD, SwinIR, Restormer, Real-ESRGAN, MVTec-family/VisA adapters, and previous student code.

## Verification

- `python -B -m pytest -q -p no:cacheprovider`: 58 passed in 2.83 s.
- `python -B scripts/smoke_test.py`: passed; 2 result rows (`no_restoration`, `restored`).
- Placeholder/absolute-path scan over Python, Markdown, YAML, TOML, and text files: no matches.
- `graphify update .`: rebuilt 398 nodes, 590 edges, and 34 communities.

The machine has Python 3.12 and 3.13, but no Python 3.11 interpreter. Tests ran on Python 3.13. The package declares Python `>=3.11`, and the implementation uses Python 3.11-compatible syntax and standard-library APIs.

## Current blockers

- No previous student/research code or trained checkpoints are available.
- The Linux GPU server is not available.
- No labeled industrial dataset split was configured in this session, so anomaly scores, AUROC, AU-PRO, F1, localization metrics, and GPU memory were not produced.
- The local `main` repository is committed, but no GitHub remote exists. GitHub CLI, Composio, and browser control are unavailable in this environment, so the private remote could not be created here.

## Exact next steps

1. Create a private GitHub repository named `restoration-anomaly-benchmark` under `kdmoon0405-prog`, without a generated README, license, or `.gitignore`.
2. From `research_code/`, run `git remote add origin https://github.com/kdmoon0405-prog/restoration-anomaly-benchmark.git` and `git push -u origin main`.
3. Download or mount one licensed MVTec AD category and validate the stored split/mask paths with the new adapter.
4. Install and connect a maintained PatchCore implementation, then run a small CPU fit/inference smoke test. The current environment has PyTorch but not Anomalib.
5. Wrap received restoration code behind `RestorationModel.restore()` and register its config name in `build_restoration()`.
6. Run the pilot matrix in `docs/EXPERIMENT_PROTOCOL.md`, keeping `no_restoration` rows in the same result schema.
7. Add CUDA peak-memory capture when the GPU path exists.

## Reproduction

From `research_code/`:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python scripts\smoke_test.py
.venv\Scripts\python -m pytest -q
```

Put input images in `data/images/`, then run:

```powershell
.venv\Scripts\python scripts\run_experiment.py configs\example.yaml
```
