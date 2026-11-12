# Run record — image-score aggregation v0.2 clean control (status COMPLETE: 3/3 units, 15/15 cells)

- **Scope:** `docs/IMAGE_SCORE_AGGREGATION_V0.2_CLEAN_CONTROL.md`, fixed at `exp/image-score-aggregation-juhyung@ba2d4de` (13:36 KST, 2026-11-12) before any comparison.
  - Same five rules as v0.1 (k = 51/251/502), applied to the stored historical Screw clean, bicubic_x4 and swinir_x4 predictions (`outputs/legacy-patchcore/screw-full320-test160`, family `historical_recovery`).
  - v0.1 (40 units / 200 cells) is not repeated.
- **Source:** `f66eb67`, clean (`source_worktree_dirty=false`).
- **Time:** 13:37:39–13:38:33 KST (measured).
- **Inputs:**
  - 160 Screw test images (41 normal, 119 anomaly), in the same order and with the same labels as the realistic Screw test set. The run checked this against `outputs/realistic-degradation/screw-v1/units/none__swinir_x4.csv`.
  - npz schema: labels (160,) int64, scores float64, masks bool and maps float32 (160×224×224). npz and json SHA-256 are in the unit receipts.
  - The source has **no calibration normals**. F1, FPR and miss rate are undefined and left empty; image AUROC is the only metric.
- **Memory:** `_budget` with the 2 GiB reserve and a 286 MiB plan per unit. Passed; this is a plan, not a measured peak.
- **Anchors:** all EXACT.
  - A: original image AUROC equals the stored `results.json` value.
  - B: pixel AUROC recomputed from the stored maps and masks equals the stored value. GT masks were used only for this check.
- **original vs map_max:** equal for 0 of 160 images. Pearson 0.993 (clean), 0.978 (Bicubic), 0.982 (SwinIR).

## Results (measured; `summary.csv`)

| unit | original | map_max | top 0.1 % | top 0.5 % | top 1 % | stored AU-PRO |
| --- | --- | --- | --- | --- | --- | --- |
| clean | 0.9842 | 0.9832 | 0.9840 | 0.9842 | 0.9826 | 0.957 |
| bicubic_x4 | 0.4800 | 0.4530 | 0.4497 | 0.4398 | 0.4347 | 0.801 |
| swinir_x4 | 0.6786 | 0.6344 | 0.6262 | 0.6028 | 0.5827 | 0.856 |

Reading (one historical family, one bank/seed, the same 160 images; descriptive):
- **Clean:** every rule gives image AUROC 0.983–0.984. Rule − original ranges from −0.0016 to 0.
- **×4:** every rule is at or below the stored score (Bicubic −0.027 to −0.045, SwinIR −0.044 to −0.096). Image AUROC stays at 0.43–0.68.
- **Conclusion:** in this family, the clean-to-×4 image-AUROC drop (about −0.31 to −0.55) occurs under all five rules, while the rules themselves barely differ on clean. The drop is therefore not produced by the choice between the stored patch-max score and max/top-k map aggregation.
- **Not established:** why ×4 changes the maps. Candidate explanations are the bank/query domain (bank-domain study pending), the representation, and coverage.

## Private (local, not returned)

| artifact | note |
| --- | --- |
| 3 source npz (with GT masks) | unchanged; SHA-256 in unit receipts |
