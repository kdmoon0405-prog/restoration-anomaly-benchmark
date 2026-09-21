# Hazelnut Raw Artifacts

## Source run

**Run ID**

`hazelnut-full391-test110-repro`

**Dataset**

`MVTec AD / hazelnut`

**Experiment**

- 391 normal train images
- 110 test images
- PatchCore: Amazon official implementation
- Backbone: WideResNet50
- Feature layers: layer2 + layer3
- IdentitySampler
- Bicubic x4 vs SwinIR-S x4
- Canonical preprocessing: Resize(256) → CenterCrop(224)
- GT masks are used only for evaluation/post-hoc analysis

**Code commit**

`c265bad1d6f98038449e28fa2063b25b595da0d9`

---

## Raw prediction artifacts

### 1. clean_predictions.npz

**SHA256**

`7B08BA7D09CF691EF17BB950B7F1A960207924D5D51CA43EE30FAD3D8C59664D`

**Size**

`19,542,590 bytes`

**Local run path**

`outputs/legacy-patchcore/hazelnut-full391-test110-repro/clean_predictions.npz`

---

### 2. bicubic_x4_predictions.npz

**SHA256**

`028702FBB1D8FCACC97EEE212177E6BE3254E1F358240425B3F6CDC8CBDB6980`

**Size**

`19,469,482 bytes`

**Local run path**

`outputs/legacy-patchcore/hazelnut-full391-test110-repro/bicubic_x4_predictions.npz`

---

### 3. swinir_x4_predictions.npz

**SHA256**

`DFD21D849C1B6944C353479172384405501719C73582FD45D784D97FB08E3DC3`

**Size**

`19,538,124 bytes`

**Local run path**

`outputs/legacy-patchcore/hazelnut-full391-test110-repro/swinir_x4_predictions.npz`

---

## What these NPZ files contain

These files are the raw numerical prediction artifacts from the completed Hazelnut experiment.

They are used for post-hoc analysis without rerunning the full PatchCore/SwinIR pipeline.

Typical stored arrays include:

- `labels`: image-level normal/anomaly labels
- `scores`: image-level anomaly scores
- `masks`: GT pixel masks
- `maps`: full-resolution anomaly maps

These raw predictions support analyses such as:

- defect ROI anomaly-score statistics
- background anomaly-score statistics
- ROI-background gap
- per-image Pixel AUROC
- per-image AU-PRO
- anomaly-map correlation
- failure-case visualization
- additional post-hoc defect-level analyses

---

## Storage policy

These NPZ files are **not committed to normal Git history**.

They are valuable reproducibility artifacts, but they are binary and can become large when many variants, categories, or anomaly maps are accumulated.

The recommended storage split is:

### Git repository

Store:

- source code
- configs
- exact run commands
- split definitions and seeds
- checkpoint/source hashes
- CSV/JSON summaries
- selected plots and qualitative figures
- research decision logs
- this artifact manifest

### External artifact storage

Store:

- raw `*_predictions.npz`
- full anomaly-map dumps
- PatchCore FAISS memory banks
- model checkpoints
- datasets

Possible storage locations include:

- local experiment disk
- OneDrive / Google Drive / team shared drive
- Git LFS
- GitHub release/workflow artifacts
- other dedicated artifact storage

---

## Reproducibility rule

The SHA256 hashes above are used to verify that a future file is exactly the same artifact used in this analysis.

The hashes do **not** allow the files to be reconstructed, so the original NPZ files must be preserved separately.

For a complete artifact record, also keep:

- experiment/run ID
- code commit
- exact command
- file size
- dataset/category
- model/checkpoint version
- storage location known to the team

---

## Current downstream analysis derived from these artifacts

The current Hazelnut defect-level analysis uses these stored predictions rather than rerunning the full 391-train / 110-test experiment.

Key findings currently recorded elsewhere in the repository include:

- defect ROI raw mean decreased on 49/70 anomalous images
- defect-background gap decreased on 25/70
- per-image Pixel AUROC decreased on 30/70
- per-image AU-PRO decreased on 30/70
- strong failure candidate (`ΔROI-background gap < 0` and `Δper-image AU-PRO < 0`) occurred on 14/70 anomalous images
- the current Hazelnut results do not support a simple “smaller defect → stronger SR failure” hypothesis
- failure analysis is shifting toward defect morphology/type and feature-space/spatial-localization causes

See:

- `docs/RESEARCH_DECISION_LOG.md`
- `PROGRESS.md`
- `analysis/hazelnut/README.md`
- `analysis/hazelnut/hazelnut_per_defect.csv`
- `analysis/hazelnut/strong_failure_cases.csv`
- `analysis/hazelnut/bootstrap_ci.json`
- `analysis/hazelnut/qualitative_cases/` (nine fixed six-panel figures, case CSV, descriptive observations)
- `analysis/hazelnut/nn_distance_selected.csv` (official PatchCore patch-to-bank squared-L2 for nine fixed cases)
- `analysis/hazelnut/nn_distance_selected_summary.md`

The selected-case NN outputs were generated from the same checksum-verified 391-normal FAISS bank and the pinned SwinIR checkpoint. They do not replace or modify the raw prediction artifacts above. All 18 recomputed Bicubic/SwinIR maps matched their stored NPZ maps exactly.
