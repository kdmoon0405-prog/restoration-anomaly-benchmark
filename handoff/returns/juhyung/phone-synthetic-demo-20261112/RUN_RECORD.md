# Run record — phone capture audit, SYNTHETIC end-to-end demo (status COMPLETE)

- **Synthetic only:** this is not a real capture, not a physical latency and not a research result. It checks that the pipeline runs from a folder to the report and that every policy rule fires as intended.
- **Source:** `exp/phone-lighting-juhyung@b756110`, clean.
  - Protocol `docs/PHONE_QUALITY_PROTOCOL_V0.1.md`, SHA-256 prefix `a44d500ffd7a`. It was fixed at `e6462ef` before the code; one pre-data amendment (noise estimator) was recorded in the same file.
- **Input:** `scripts/make_phone_synthetic_set.py`
  - 1600×1200 board-like texture, seed 11
  - front/left/right multiplicative shading × 3 repeats
  - injected faults: heavy blur, mild blur, camera shift 6 %, overexposure with a retake, dim, unrelated image, missing file, duplicate file, invalid ID, unlisted file
  - `expected.json` lists the intended state per row
- **Command:** `run_phone_capture_audit.py --input outputs/phone-synthetic-demo-20261112/input --output outputs/phone-synthetic-demo-20261112/audit --kind synthetic`

## Results (measured on synthetic input)

- **Rows:** 16/16 sheet rows reached the expected state and reason.
- **Totals:** 16 attempts: PASS 7, REVIEW 6 (+1 unlisted file), RETAKE 4. 14 slots: 7 resolved, 7 unresolved. The retake history `right r2: a1:RETAKE > a2:PASS` is recorded.
- **Station replay:** 14 cycles through the existing `InspectionStation`, all accepted, verdict REVIEW only (no detector is connected). Times are simulation seconds.
- **Repeatability:** pairwise MAE on the aligned ROI is 1.19–1.86 Y for the baseline (no policy; recipe means) and 1.18–1.19 for PASS-only. These are synthetic numbers. The duplicate file (MAE 0 against its source) and the mild-blur image enter only the baseline.
- **Design finding, kept as-is:**
  - The first synthetic expectation said heavy blur (σ4) would be REVIEW for low sharpness. Under the fixed protocol it was RETAKE, because alignment failed and RETAKE takes precedence. The protocol was not changed.
  - The synthetic set was corrected instead: σ8 is expected RETAKE and σ1.5 is expected REVIEW. Both were checked with margins (inlier ratio 0.06 vs 0.79).

## Browser check

`report.html` was opened in Microsoft Edge (headless) and the screenshots were inspected.
- **Desktop, 1400 px:** banner, slot history, both repeatability scopes, spread table, per-capture cards with clip overlay and alignment difference image: OK.
- **390 px:** the wide tables scroll inside their containers. The text is still cut at the right edge, even after adding `overflow-wrap:anywhere`. This may be headless Edge rendering wider than the screenshot, but that has not been verified. Mobile layout is recorded as **unverified**.
- `report.html` is not in this return, because the return format is text-only. It holds only synthetic images.

## Tests

- `tests/test_phone_capture.py`: 6 passed.
- Full suite on the branch: 684 passed, 4 skipped (at `a8eb190`). The report change in `b756110` was re-checked with the end-to-end test.
