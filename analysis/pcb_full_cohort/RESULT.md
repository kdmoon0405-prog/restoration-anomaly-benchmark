# PCB (VisA pcb2) full cohort — result (one execution, reviewed bank reused, not refit)

## Provenance

- Raw run `outputs/pcb-full-cohort/pcb-full-cohort-20261101-a` (local only, about 13 GB):
  - `status.json` COMPLETE, 1,140/1,140 units.
  - 380 boards × 3 variants: clean, bicubic_x4 (PIL), swinir_x4.
  - Boards: 180 calibration normals; test 200 (100 good, 100 anomalous).
  - 54,720 tile queries, 48 tiles of 224 px per board.
- Execution family `faiss_cpu_IndexFlatL2_4threads_k1_one_tile_per_search_v1` (A), fixed for the whole cohort:
  - exact search, k=1
  - no approximate index, bank reduction, pixel subsampling or preprocessing change
- Bank: the reviewed bank `pcb-real-fit-bank-20261029-163524` (262,144 × 1024, float32), loaded and hash-verified, `bank_created_this_run=false`.
- Sessions 000–009, 2026-11-01 to 2026-11-09:
  - outer wall time 54.7 h in total
  - sessions 002/003 (4.9 h of the 54.7 h) were slowed by laptop sleep and are flagged in `derived/raw_sessions.csv`
  - every resume verified the existing unit receipts and the protocol hash before continuing
  - source commit: session 000 ran at `54cf3c7`, and sessions 001–009 at `afb36ab`, which adds only Screw analysis files
  - `source_worktree_dirty=true` in every session, recorded as-is
- Environment: NVIDIA GeForce MX570 A, Python 3.11.2, torch 2.14.0+cu126, faiss 1.15.1, numpy 2.4.6.
- Postprocessing (`scripts/run_pcb_full_postprocess.py`, one stage/variant per process, 2026-11-09 00:46–01:14):
  - v0.6 board rule `pcb_board_robust_after_mean_v0_6`, stages: calibration → normalize → quality → evaluate → perboard.
  - Native frozen GT masks are used only in evaluate/perboard, with no resize/pad/dilation.
  - AU-PRO@0.3: 200 thresholds, 4-connectivity.
  - Quality is computed from the stored RGB spool, with no SR rerun.
  - The evaluate stage peaked at about 10.4 GiB RSS. The 21.4 GB guard passed, and no guard was lowered.
- Derived: `derived/` from `scripts/summarize_return_package.py`, which reads saved status/CSV files only.

## Aggregate (test 200 boards)

| variant | PSNR vs clean | SSIM | Image AUROC | Image F1 | Pixel AUROC | AU-PRO@0.3 | Pixel F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| clean | — | 1.000 | **0.9714** | **0.844** | **0.9693** | **0.9517** | 0.178 |
| bicubic_x4 | 28.54 | 0.729 | 0.9680 | 0.816 | 0.9601 | 0.9391 | **0.185** |
| swinir_x4 | 30.93 | 0.789 | 0.9544 | 0.697 | 0.9608 | 0.9440 | 0.184 |

## Paired per-board AU-PRO (100 anomalous boards; `derived/delta_distribution.*`)

| comparison | mean | median | q10 | q90 | better / worse |
| --- | --- | --- | --- | --- | --- |
| SwinIR − Bicubic | +0.0037 | +0.0011 | −0.0067 | +0.0185 | 67 / 33 |
| SwinIR − clean | −0.0070 | −0.0028 | −0.0219 | +0.0010 | 19 / 81 |
| Bicubic − clean | −0.0108 | −0.0036 | −0.0319 | +0.0006 | 14 / 86 |

## Observations (descriptive; one run, no confidence intervals)

1. **Clean is the upper reference:**
   - Both ×4 round-trips lower pooled AU-PRO, by −0.013 (Bicubic) and −0.008 (SwinIR).
   - On most boards, both are below clean.
2. **SwinIR vs Bicubic:**
   - SwinIR has higher PSNR (+2.4 dB) and pooled AU-PRO (+0.005), and is better on 67/100 boards.
   - Its Image F1 at the frozen threshold is lower (0.697 vs 0.816). Saved scores reproduce Bicubic TP=71/FN=29/FP=3/TN=97 and SwinIR TP=54/FN=46/FP=1/TN=99. Image AUROC also changes (0.9544 vs 0.9680). The operating-point loss is observed, while the contributions of calibration and ranking require further diagnosis.
3. **By defect size** (`derived/per_defect_size_tercile.csv`; PCB defect-type labels are not bound in this pipeline, so area terciles are used instead):
   - Large defects (area ratio > 0.0034) have the lowest per-board AU-PRO in every variant: clean 0.883, Bicubic 0.869, SwinIR 0.875.
   - The variant ordering is the same in all three terciles.
4. **§5, search cost:**
   - Detector inference including the CPU exact FAISS search is 97.5% of staged raw time: 191,757 s over 54,720 tile queries, about 3.5 s per tile (`derived/raw_stage_times.csv`).
   - SwinIR preparation is 2.4% of staged raw time, and Bicubic is under 0.02%.
   - Backbone and search time are not separated within that stage. No additional thread/batching comparison was run, and the cohort stayed on family A. GPU exact search (C) was not approved.
5. **Success/regression boards** (largest SwinIR − Bicubic gains and losses) are listed as sample IDs in `derived/success_regression_cases.csv`. RGB panels stay local (dataset license).

## Not claimed

- No causal claim that SR "improves" or "harms" PCB detection.
- No claim beyond VisA pcb2, this ×4 round-trip, this bank and this rule.
