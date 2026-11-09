# Corrections and clarifications to the 2026-11-09 GPU return (juhyung)

This note does not edit the original runtime records:
- raw-run PROTOCOL/status/sessions keep their `source_worktree_dirty=true` flags and source hashes
- unit receipts and the return ZIP `c7c98415…648d` are unchanged

Wording fixes already made on `exp/juhyung-return-review-fixes@5c4ddd8` (rounded tie, operating-point wording, predict-time cause, Screw pixel-only wording) are kept as they are. This note adds only what new measurements change.

| # | original statement (return `4c2fc40`) | status now | evidence |
| --- | --- | --- | --- |
| 1 | PCB: "Detector inference including the CPU exact FAISS search is 97.5% of staged raw time" (§5). Backbone and search were not separated. | **Kept as written.** It is a combined-stage share. A separate small measurement now shows exact search alone is about 3.43 of about 3.50 s per tile, roughly 98% of that stage, on 6 fixed tiles. This is an estimate, not a cohort re-measurement. | `analysis/pcb_exact_batch/RESULT.md` |
| 2 | PCB: "SwinIR Image F1 lower … The gap is in the operating point more than in ranking." | **Superseded by the diagnosis.** Most of the TP gap is operating point (test FPR 1 % vs 3 % at the frozen q0.99; equal TPR at matched 1 % FPR). A smaller ranking loss also exists: 0.07–0.14 lower TPR at 3–10 % FPR, linked to a wider SwinIR normal-score spread. The board peak is inside the defect as often as for clean. | `analysis/image_score_diagnosis/REPORT.md` §2 |
| 3 | Realistic: "Screw image-level classification is unusable in this run" | **Kept, with cause narrowed.** The same failure appears with no added degradation in all three families: PIL 0.480, MATLAB endpoint 0.479, realistic 0.466 for Bicubic, against 0.984 for clean. It is not specific to the realistic family. The map peak leaves the defect after any ×4 round trip. A clean-bank/restored-query mismatch is the consistent explanation. The matched-bank control is still untested. | `analysis/image_score_diagnosis/REPORT.md` §3 |
| 4 | Previous return: "Screw endpoint fit count/seed not machine-readable" (reviewer note) | **Resolved for delivery.** The original `results.json` carries `detector.spec.seed=11`, 320 `train_paths`, `fit_performed=false` and the bank artifact SHA-256. It is delivered privately with the bank `metadata.json`. | private map-delivery ZIP, `provenance/screw_endpoint/` |
| 5 | Score/map linkage was not independently checked | **Checked.** No implementation error was found. 1140/1140 rows follow the plan order, and the 3 thresholds reproduce exactly. One board × 2 variants was re-predicted from its stored spool and reproduced the stored score and map bitwise, with score = max of the 48 tile scores. | `analysis/image_score_diagnosis/REPORT.md` §1 |
