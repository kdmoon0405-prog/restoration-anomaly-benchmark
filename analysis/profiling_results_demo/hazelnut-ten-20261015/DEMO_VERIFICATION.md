# Local results demo verification

2026-10-15, loopback HTTP only. Inputs are the unchanged Branch B baseline and negative map-gating analysis. No model import, fitting, inference, calibration, new research metric or result rewrite occurs in the viewer.

Passed against actual saved artifacts:

- Catalog: all 110 samples and six methods, including normals, not just selected explanatory cases. Final live check exercised all 660 sample/variant API responses; all 240 normal responses had null per-image AU-PRO, baseline quality was present, and all variants shared each sample's map scale.
- Normal per-image AU-PRO is JSON null; GT is not a gate input.
- All ten PNG kinds (six methods, discrepancy, two gates, GT) decode at 224x224. Comparison maps use the same sample-level min/max. GT overlay changes rendering only.
- Verified historical pilot10 RGB is available for exactly ten of the 110 samples; other samples return unavailable/404, without inference. Baseline RGB is never labeled candidate RGB.
- Exported summary CSV bytes equal the stored source. Negative feasibility and limitations remain visible.
- Invalid sample/panel returns 400, missing RGB 404, POST 405. Synthetic tests cover untrusted Host 403 and missing required inputs blocking sample/panel/export with 503.
- HTML is served as UTF-8. JavaScript syntax is checked separately; this is not a browser interaction test.

Not verified: page layout, dropdown/GT-toggle interactions in an actual browser, print layout or screenshot appearance. The computer-use connector reported no available browsers, so no screen capture/visual pass is claimed. Manual follow-up: run the command in [demo README](../../../demo_results/README.md), open the local URL, try normal/anomalous samples and each variant, toggle GT, check missing RGB messages, and save a screenshot if appropriate. No external hosting or browser installation was performed.

The service is read-only but is not a production security boundary. Bind stays 127.0.0.1. Raw images, predictions, weights and bank files remain ignored and local; do not publish screenshots/data without reviewing dataset terms and privacy.
