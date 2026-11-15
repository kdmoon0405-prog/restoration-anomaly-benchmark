# Run record — phone station on real photos, DEVELOPMENT session 2026-11-15 (status COMPLETE for the supplied input)

- **Model:** Claude Fable 5.2 (`claude-fable-5-2`, Claude Code). Earlier Opus/Fable drafts and the CPU comparison document were in context.
- **Input (private, not in Git):**
  - 24 JPEG photos of one graphics-card back side, taken by the user on 2026-11-15 (Galaxy Z Flip7, 4000×3000, EXIF 1/15 s, ISO 320, flash off). SHA-256 per file is in `manifest.json`.
  - Conditions from the user's report: L0 baseline / L1 left low side / L2 low light × 3 rounds, manual-focus blur × 3, simulated surface object (pink piece, about 7 mm, user-reported) under L0 × 3 and L1 × 3, white background × 3, camera tilt × 3. AE/AF lock, HDR and human legibility notes are unknown.
  - 6 earlier example PNGs from the CPU packet (`INPUT_RECEIPT.json`, all six SHA-256 verified).
- **Session role:** development. The methods were fixed after a v0.1 audit of this same session had been seen (disclosed in `docs/DESIGN_DECISION_PHONE_V0.2.md` §0). Nothing here is an independent evaluation, and one object's repeats are not independent parts.
- **Source:**
  - v0.1 audit: `exp/phone-lighting-juhyung@aa2f7fa` (clean).
  - Design fixed: `e00eca6` (16:18 KST). Pre-data amendment 1 and code: `5839caa`.
  - Station comparison: `5839caa` (clean), run 16:29–16:31 KST.
- **Commands:**
  - `run_phone_capture_audit.py --input outputs/phone-captures/20261115 --output outputs/phone-audit-20261115-v01-dev --kind real`
  - `run_phone_station_compare.py --input outputs/phone-captures/20261115 --recipe outputs/phone-station-20261115-inputs/recipe.json --plan outputs/phone-station-20261115-inputs/plan.json --output outputs/phone-station-20261115-dev --kind real --assets-root . --device cuda`
- **Tests:** `tests/test_phone_station.py` 7 passed. Full suite at `5839caa`: 692 passed, 4 skipped.

## 1. v0.1 audit, full frame (`v01_audit/`)

- All 24 photos decoded, and all 24 registered to the first L0 photo across lighting changes: inlier ratio 0.40–0.95, median reprojection error 0.46–0.75 working px.
- States: PASS 3 (L1), REVIEW 3 (F1), RETAKE 18.
- The L0 photos were RETAKE for high clipping (4.4–8.9 % of the frame). The clipping is on the desk background; the board covers about half of the frame width.
- Pairwise mean |ΔY| between repeats of one recipe: L0 12.3, L1 2.0, L2 1.2. The L0 lamp position was re-made each round and did not reproduce as closely.

## 2. Quality policies with the recipe ROI (`captures_quality.csv`)

ROI = PCB area of the anchor (x 0.12–0.61, y 0.31–0.70), 144,540 inspected working pixels.

| recipe | v0.1 with ROI | v0.2 `ref_roi` | note |
| --- | --- | --- | --- |
| L0 × 3 | RETAKE (clip_high) | PASS | ROI clipping 1.8–2.2 % is also in the anchor (1.81 %): bright solder and print. New clipping ≤ 0.3 %. |
| L1 × 3 | PASS | PASS | |
| L2 × 3 | REVIEW (luma, sharpness) | REVIEW (roi_too_dark) | ROI mean Y 23.6–24.6 |
| blur × 3 | RETAKE | REVIEW (low_sharpness_vs_reference) | sharpness ratio 0.19 |
| F0 × 3 | RETAKE (clip_high; setup_moved) | PASS | scale deviation 3.4–3.6 %, inside the recipe pose tolerance |
| F1 × 3 | REVIEW (setup_moved) | PASS | |
| white background × 3 | RETAKE (clip_high; setup_moved) | PASS | background change does not enter the ROI metrics |
| tilt × 3 | RETAKE | REVIEW (outside_recipe_pose) | rotation about 14° |
| **total** | PASS 3 / REVIEW 6 / RETAKE 15 | PASS 15 / REVIEW 9 / RETAKE 0 | |

- ROI checks: every photo had projected coverage 1.0, and every non-anchor photo had at least 67 inliers inside the ROI.
- **Limit of the normalized sharpness:** the ratio is 2.9–3.1 for L1 and 3.6–3.8 for L2. Dividing by brightness squared over-corrects in darker photos, so the ratio only works as a low-side blur flag and is not comparable across lighting.
- **No human legibility record exists.** The rates "legible input rejected" and "hard-to-read input accepted" are NA for both policies. Which policy is closer to a human reading is therefore not established.

## 3. Golden-reference inspection and C0–C3 (`summary.csv`, `cycles.csv`, `inspections.csv`)

- Calibration (normal only, one photo per light): τ = 1.615 at L0 and 0.533 at L1. The L0 threshold is three times higher because the L0 normal repeat differs more from its reference.
- 16 initial cycles: 1 held-out normal, 3 simulated-object repeats (one object, one position), 12 input-stress cycles on the normal board (low light 3, blur 3, white background 3, tilt 3).

| condition | OK | NG | REVIEW | NA | photos used | simulated object: final NG / 3 | normal-labelled cycles: final NG / 13 | NG or REVIEW / 13 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 direct | 11 | 5 | 0 | 0 | 16 | 3 | 2 | 2 |
| C1 Bicubic ×4 round trip | 13 | 3 | 0 | 0 | 16 | 3 | 0 | 0 |
| C1 SwinIR ×4 round trip | 13 | 3 | 0 | 0 | 16 | 3 | 0 | 0 |
| C2 policy v0.1 (ROI) | 4 | 0 | 12 | 0 | 23 | 0 (3 REVIEW) | 0 | 9 |
| C2 policy v0.2 | 6 | 4 | 6 | 0 | 19 | 3 | 1 | 7 |
| C3 two lights | 3 | 4 | 0 | 9 | 14 | 3 | 1 (of 4 with an alternate photo) | 1 |

- **Held-out normal cycle:** OK in every condition (score 0).
- **Simulated object:** every NG blob lies within 30 px of the post-hoc annotation.
  - Scores: 165 at L0 (limit 25), 1500–1515 at L1, 117–130 after the ×4 round trips.
  - The three L0 scores and centroids are identical. This was re-computed independently: the photos differ (pixels above τ 214 / 215 / 214), but the largest blob has the same shape in each.
- **False NG on the normal board:** `lowlight-3` (score 30) and `background-2` (score 28) under C0, both just above the 25 px limit.
  - C2 v0.2 removes the low-light one by sending it to a retake. It keeps the background one, which passes the quality policy.
  - C1 has none: the round trip smooths the difference map and also lowers the object score.
- **C2 v0.1:** never inspects the simulated-object cycles, because both photos are stopped by `setup_moved`. It requests a retake on all 16 cycles.
- **C2 v0.2:** requests 9 retakes. Only 3 had an alternate-light photo (low light); the other 6 (blur, tilt) end in REVIEW with `retake_unavailable`.
- **C3:** NA for the 9 cycles without an alternate-light photo.
- **`lowlight-1` and `lowlight-2`:** the retake photo is the L1 reference or calibration image, so its inspection is trivial.
- **Station replay:** 16 cycles of C2 v0.2 through the existing `InspectionStation`, 49 commands, all accepted, at most 2 photos per cycle. Simulation seconds only. `station_events.jsonl` stays local, because the return format has no `.jsonl`.
- **Software time on this PC:** 147 s for the whole run (24 photos, 6 conditions, report). Of that, golden-reference inspection took 74 s, the SwinIR round trips 16 s and the Bicubic round trips 7 s. Capture time and equipment throughput were not measured.

## 4. Six example photos (`examples_registration.csv`)

- Anchor candidate `example_06`, ROI x 0.31–0.91, y 0.27–0.67 (set on that photo only).
- The other five (perspective, 80–150° rotation, scale changes, partial field of view) did **not** pass registration (`alignment_below_threshold`) and are RETAKE. They are not treated as corrected.
- Whether a stronger registration method could align them was not tested.

## What this does not show

- No detection performance. One simulated object at one position, three repeats; one held-out normal cycle; normal calibration from one photo per light.
- No independent evaluation session. The thresholds were fixed before these runs, but the methods were designed after seeing a v0.1 audit and thumbnails of this session.
- mm resolution, lux, capture time and electrical state are not measured.
- C1 is a new family, `phone_x4_roundtrip` (×0.25 then ×4 on real photos, matched reference). It is not pooled with the benchmark ×4 results. No PSNR/SSIM was computed.

## Private (local, not returned)

| artifact | note |
| --- | --- |
| 24 photos, 6 example photos | SHA-256 in `manifest.json` / `INPUT_RECEIPT.json`. The 24 JPEGs carry GPS EXIF; the tool records only that it is present |
| `report.html` (both runs) | embeds downscaled photos |
| `station_events.jsonl` | no pixels; local only because of the return format |
