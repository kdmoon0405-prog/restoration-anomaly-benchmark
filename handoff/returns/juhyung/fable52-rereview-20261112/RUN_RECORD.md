# Run record — Fable 5.2 re-review, phone audit re-run and reproduction checks (status COMPLETE)

- **Why:** the 2026-11-12 design review was assigned to Fable 5.2, but the earlier work that day was done with Claude Opus 5.5 because of a settings mistake. The user switched the model to Claude Fable 5.2 (`claude-fable-5-2`) and asked for a re-run.
- **Redone with Fable 5.2:** design draft v1 and the re-review (`DESIGN_DRAFT_FABLE52_20261112_v1.md`, `DESIGN_REVIEW_FABLE52_20261112.md`, both in this return), plus a review of the phone tool.
  - The v1 draft is **not independent**: the earlier draft and the evidence were already in context.
- **Kept:** every earlier document and result. Returns `0a3cfdf` and `4394521` are unchanged.
- **Source:** `exp/phone-lighting-juhyung@aa2f7fa`, clean.

## Changes from the review

1. **Quality metrics now use unwarped pixels** (protocol pre-data amendment 2; no real photo seen yet; thresholds unchanged).
   - Measured on synthetic input: a 0.25 / 0.5 px bilinear warp alone lowered sharpness to 0.79× / 0.73× and the noise estimate to 0.45× / 0.29×. The unwarped reference was unaffected, so reference-vs-other comparisons were biased.
2. **Capture guide now requires JPEG.** This environment cannot decode HEIC/HEIF or RAW (PIL 12.3 without `pillow_heif`). Such files would all be RETAKE (unreadable). Nothing was installed.
3. **Claims narrowed** (see the review, §2): C1 to noisy-LR inputs, C2 wording on AU-PRO, C3 not a poster claim until real photos arrive.
4. **Open risk, not changed:** alignment across lighting directions on reflective metal is untested. The synthetic lighting is only a smooth gradient.

## Re-run of the synthetic demo (measured on synthetic input)

- Same input as `phone-synthetic-demo-20261112` (`input/`), new output directory.
- 16/16 rows reached the expected state and reason. No state differs from the earlier run.
- Totals unchanged: PASS 7, REVIEW 6 (+1 unlisted file), RETAKE 4; 14 slots, 7 resolved.
- Metric values of non-reference images moved slightly, as intended. Example: `left_r2` sharpness 0.08335 → 0.08364.
- Tests: `tests/test_phone_capture.py` 7 passed (1 new), `tests/test_inspection_station.py` 17 passed. The full suite was not re-run after this change.

## Reproduction of the v0.2 clean control

- Re-ran `run_image_score_aggregation_clean_control.py` at `exp/image-score-aggregation-juhyung@f66eb67` into a scratch directory.
- `summary.csv` is byte-identical to the returned one (SHA-256 `ce633fc5…efc1`). 3/3 units, 15 cells, anchors exact.
- This is a reproduction check, not a new result. The model used does not affect these numbers.

## Not verified

- Real photos, physical latency, lux: none.
- Mobile layout of `report.html`: still unverified.
