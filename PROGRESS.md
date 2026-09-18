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
- Published `main` to `kdmoon0405-prog/restoration-anomaly-benchmark` and added a concrete GPU pilot handoff checklist.

## Verification

- `python -B -m pytest -q -p no:cacheprovider`: 58 passed.
- `python -B scripts/smoke_test.py`: passed; 2 result rows (`no_restoration`, `restored`).
- Placeholder/absolute-path scan over Python, Markdown, YAML, TOML, and text files: no matches.
- `graphify update .`: rebuilt 398 nodes, 590 edges, and 34 communities.

The machine has Python 3.12 and 3.13, but no Python 3.11 interpreter. Tests ran on Python 3.13. The package declares Python `>=3.11`, and the implementation uses Python 3.11-compatible syntax and standard-library APIs.

## Current blockers

- No previous student/research code or trained checkpoints are available.
- The Linux GPU server is not available.
- No labeled industrial dataset split was configured in this session, so anomaly scores, AUROC, AU-PRO, F1, localization metrics, and GPU memory were not produced.

## Exact next steps

1. Follow `docs/GPU_HANDOFF.md` on the GPU notebook and record its exact environment.
2. Download or mount the licensed MVTec AD `bottle` category and validate split/mask paths.
3. Connect a maintained PatchCore implementation and complete the no-restoration baseline.
4. Connect one degradation-matched restoration checkpoint and run the paired pilot.
5. Add CUDA peak-memory capture with the real GPU path.

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
