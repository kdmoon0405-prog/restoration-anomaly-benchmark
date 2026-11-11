# Run record — image-score aggregation, Hazelnut part (status COMPLETE: 20/20 units, 100/100 cells)

- **What:** five fixed image-score rules re-applied to stored Hazelnut predictions, per `docs/IMAGE_SCORE_AGGREGATION_V0.1.md`. The protocol was committed as `4afae6d` at 14:20 KST, before any non-original rule was evaluated against labels.
  - Rules: `original`, `map_max`, top 0.1/0.5/1 % mean with k = 51/251/502.
- **Not new inference:** these are re-evaluations of existing predictions. Each unit points to its original run (`source_public_record`, `source_npz_sha256`, `source_receipt_sha256`, `source_run_protocol_sha256`).
  - 4 units are realistic v1 `none`.
  - 16 units are noise v2 σ5/σ15 × noise seed 23/37.
  - All re-use the same 110 Hazelnut test images (40 normal, 70 anomaly) and 78 calibration normals. They are not independent samples.
- **Source:** `exp/image-score-aggregation-juhyung@84d9c9a`, tracked and untracked clean (`source_worktree_dirty=false`), in a separate worktree.
  - Later commits on the branch (`1cfe140` exporter `.`-root mapping, `78ac166` derived-table script) do not touch the run code. Code SHA-256 values are in `PROTOCOL.json`.
- **Command:** `run_image_score_aggregation.py --data-root <GPU checkout> --output outputs/image-score-aggregation-20261111-a --categories hazelnut`
  - Time: 14:30:37–14:30:43 KST, 2026-11-11, about 0.22 s per unit (measured).
- **Inputs (read-only):**
  - Each unit's npz, csv, receipt and run PROTOCOL SHA-256 were checked against the receipt.
  - npz schema read from headers before loading: calibration_maps 78×224×224 float32, test_maps 110×224×224 float32, scores float64.
  - No model, bank, FAISS, GT mask or RGB was loaded.
- **Memory:** `_budget` with the fixed 2 GiB reserve and a real payload plan of 159.7 MiB per unit. Passed for all units; this is a plan, not a measured peak.
- **Anchors:** all 20 units EXACT.
  - A, original score: the recomputed robust params, threshold, AUROC, F1, FPR and miss rate are bit-identical to the stored receipt.
  - B, map payload: the pixel robust params and pixel threshold refit from calibration maps are identical to the receipt.
- **original vs map_max:** never equal (0/188 per unit). The PatchCore image score is the max of unsmoothed patch scores, and the map is upsampled and smoothed. Pearson correlation is 0.991–0.998 (descriptive).

## Results (measured; all 100 cells in `summary.csv`, wide view in `derived-hazelnut/`)

- **Rule − original image AUROC** over the 20 units:

  | rule | range |
  | --- | --- |
  | map_max | −0.015 to +0.010 |
  | top 0.1 % | −0.017 to +0.009 |
  | top 0.5 % | −0.021 to +0.019 |
  | top 1 % | −0.021 to +0.028 |

- **SwinIR − Bicubic image AUROC** per rule. Columns are original / map_max / top0.1 / top0.5 / top1; the stored pooled AU-PRO Δ is the fixed reference.

  | realization | condition | image AUROC Δ by rule | AU-PRO Δ |
  | --- | --- | --- | --- |
  | v1 | none | +0.002 / +0.003 / +0.003 / +0.002 / +0.002 | +0.021 |
  | noise23 | σ5 | −0.060 / −0.047 / −0.048 / −0.046 / −0.045 | −0.019 |
  | noise37 | σ5 | −0.054 / −0.049 / −0.047 / −0.047 / −0.050 | −0.031 |
  | noise23 | σ15 | −0.070 / −0.062 / −0.059 / −0.044 / −0.035 | −0.077 |
  | noise37 | σ15 | −0.055 / −0.052 / −0.047 / −0.037 / −0.031 | −0.079 |

- **RealESRNet/RealESRGAN − SwinIR:** positive in all rules and realizations except v1 `none`, where it is −0.007 to −0.021. At σ15 it shrinks from original to top 1 %, e.g. noise37 RealESRNet +0.060 → +0.013. See `derived-hazelnut/restorer_contrasts_by_rule.csv`.

Reading (Hazelnut, descriptive):
- The image AUROC level is high for all rules and moves by at most about 0.03 between rules.
- The restorer ordering in image AUROC keeps its sign across rules.
- At σ15 the SwinIR gap narrows as more map area enters the score.
- The repeats re-use the same images, and no interval is computed here. The per-image rows (`units/*.csv`, with sample/label/split/rule/raw score/threshold/source npz SHA) are for the CPU's common bootstrap with noise repeats grouped by image.

## Private (local, not returned)

| artifact | note |
| --- | --- |
| source `units/*.npz` (20) | unchanged; SHA-256 in each receipt `source_sha256.npz` |
