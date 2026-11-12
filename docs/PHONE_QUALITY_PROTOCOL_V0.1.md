# Phone capture quality / alignment protocol v0.1 (fixed before any real photo, 2026-11-12)

This protocol covers the `phone_*` local tool. Formulas, units and thresholds are fixed here **before** any real photo is seen.
- Synthetic tests check only that each rule fires as intended. They are not used to tune values.
- If a real photo shows that a rule is wrong, the fix goes into a new version (v0.2), and v0.1 results are kept.
- Nothing here is a detection metric. Lighting changes are not expressed in lux, because no light meter is used.

## 1. Input contract

A capture folder holds the image files plus `capture_sheet.csv` (UTF-8). It has one row per capture attempt.

| column | required | meaning |
| --- | --- | --- |
| `file` | yes | file name inside the folder (no sub-paths) |
| `part_id`, `session_id`, `recipe_id` | yes | `[A-Za-z0-9_-]{1,64}`. The same physical object always has the same `part_id`. |
| `repeat_id` | yes | integer ≥ 1 |
| `attempt` | no (default 1) | integer ≥ 1. A retake of the same slot has a higher attempt number. |
| `label_status` | no (default `unknown`) | one of `normal`, `real_defect`, `simulated_defect`, `unknown` |
| `light_position`, `flash`, `ae_af_locked`, `hdr`, `notes` | no | free text, as recorded by the user |
| `reference` | no | `1` marks the alignment reference of its part/session (at most one) |
| `roi_x0, roi_y0, roi_x1, roi_y1` | no | ROI as fractions (0–1) of the reference image; the first value given for a part/session is used |

- **Slot:** (part, session, recipe, repeat). Its final state is the state of its highest attempt. All attempts are kept in the history and the denominators.
- **Reference:** the row with `reference=1`; otherwise the first sheet row of that part/session whose file decodes.
- **ROI:** if none is given, the whole frame is used, and `roi_default_full_frame` is recorded.

## 2. Decoding and working image

- **Decoding:** PIL, then `ImageOps.exif_transpose` (the displayed orientation), then RGB uint8. The EXIF orientation tag is recorded.
- **Working image:** resized with Lanczos so the long side is 1024 px, then fixed. The scale factor is recorded so residuals can be converted back to full-resolution pixels.
- **EXIF:** Make, Model, DateTime(Original), ExposureTime, FNumber, ISO, FocalLength, Flash and WhiteBalance are copied as text.
  - GPS is reported only as `gps_present` (true/false). Coordinates are never written.
- **File SHA-256:** computed on the original bytes.

## 3. Quality metrics

All metrics are computed inside the ROI on the **aligned** working image, i.e. warped into the reference frame. If alignment fails, they use the unaligned ROI and say so. Y is code-value luma, 0–255, without linearization; it is not photometric luminance.

| metric | formula | unit |
| --- | --- | --- |
| `luma_mean`, `luma_p01`, `luma_p99` | Y = 0.2126 R + 0.7152 G + 0.0722 B; mean and 1st/99th percentile | code value 0–255 |
| `clip_high_fraction` | fraction of ROI pixels where any channel ≥ 250 | 0–1 |
| `clip_low_fraction` | fraction of ROI pixels where all channels ≤ 5 | 0–1 |
| `sharpness_tenengrad` | mean(gx² + gy²), gx and gy from `scipy.ndimage.sobel` on Y/255 | (Y/255)² per px, relative |
| `noise_sigma` | Immerkær (1996): √(π/2)/6 · mean\|Y ∗ M\|, M = [[1,−2,1],[−2,4,−2],[1,−2,1]], over valid interior pixels | code value; reported only |
| `rg_ratio`, `bg_ratio` | mean R / mean G, mean B / mean G | ratio; reported only |

Pre-data amendment (2026-11-12, before any real photo; recorded in Git history): the noise estimator was `skimage.restoration.estimate_sigma` (fixed at `e6462ef`). It needs PyWavelets, which is not installed, and nothing is installed for this tool. The amendment replaces it with Immerkær. It is report-only and has no threshold, and no other value changed.

Sharpness and noise also depend on texture, so they are compared only within a part/session, never across objects.

## 4. Alignment (reference → image)

- **Method:** at working resolution, ORB (`skimage.feature.ORB`, 1000 keypoints, fast threshold 0.05) on Y/255; `match_descriptors` with cross-check; `ransac` with `ProjectiveTransform` (min_samples 4, residual threshold 2.0 px, 2000 trials, fixed rng 0).
- **Success** requires all of:
  - inliers ≥ 30
  - inlier ratio ≥ 0.25
  - median inlier reprojection error ≤ 1.5 working px
- **Reported:**
  - inliers, ratio and median error, in working px and in full-res px
  - homography decomposed into translation (fraction of working width), rotation (degrees) and scale deviation (|s − 1|)
- **Camera moved** (`setup_moved`): translation > 0.02, or rotation > 1.0°, or scale deviation > 0.02. This keeps a camera or tilt change separate from a lighting change.
- **Repeatability:** pairwise mean absolute Y difference (0–255) on the aligned ROI between repeats of the same recipe. Pixels outside the warped frame are excluded.

## 5. Capture policy (fixed)

**RETAKE** if any of:
- `missing_file`: a sheet row has no file
- `unreadable`
- `alignment_failed`
- `clip_high_fraction` > 0.01
- `clip_low_fraction` > 0.01

**REVIEW** if not RETAKE and any of:
- `luma_mean` outside [40, 215]
- `sharpness_tenengrad` < 0.5 × the median of the readable images of the same part/session; only applied when that set has ≥ 3 images
- `duplicate_of` (same SHA-256 as an earlier row; the first stays)
- `resolution_mismatch` with the reference
- `setup_moved`
- `invalid_row` (bad ID or value; the row is not analysed)
- `unlisted_file` (an image in the folder that is not in the sheet; listed, not analysed)

**PASS** otherwise.

Each REVIEW/RETAKE row records all of its reasons.

## 6. Baseline and what is compared

- **Baseline:** "no policy", i.e. every readable capture is accepted.
- **Policy:** the states above.
- **Reported for both:**
  - slot and attempt counts
  - per-recipe repeatability (pairwise MAE; quality metric ranges)
  - between-recipe vs within-recipe spread of each metric
- REVIEW/RETAKE captures stay in the denominators.
- Same-object repeats are never counted as independent parts.
- PSNR/SSIM between physically different lighting shots are not treated as restoration ground truth and are not computed.

## 7. Station replay

Each attempt is replayed through the existing `sr_anomaly.inspection_station.InspectionStation`:
- start: `part_id`; `cycle_id = <session>-<recipe>-r<repeat>-a<attempt>`; `recipe_id`; `image_ref` = file SHA-256
- complete: always `REVIEW`, because no detector is connected yet; `prediction_ref = phone_quality:<state>`; `result_source = phone_quality_v0.1; detector=not_connected`

The output kind is `software_replay_of_capture_audit`. Times are simulator values, not physical latency.

## 8. Outputs

New output directory per run:
- `manifest.json`: inputs, file SHA-256, source state, protocol SHA-256, synthetic or real
- `captures.csv`: one row per attempt with all metrics, states and reasons
- `slots.csv`
- `repeatability.csv`
- `recipe_summary.csv`
- `station_events.jsonl`, `station_cycles.csv`
- `report.html`: thumbnails with clipping overlay and alignment difference, tables, history

`report.html` embeds downscaled photos, so it is private unless the user decides otherwise. The CSV/JSON files contain no image content.
