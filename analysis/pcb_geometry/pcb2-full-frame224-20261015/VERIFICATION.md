# CPU geometry verification

Completed 2026-10-16 KST. Audit rules/code were frozen on 2026-10-15 at
`2026-10-15T14:56:43.801213+00:00`; the run directory retains its original date.
Base: `53b5e21d99249a37cbb1aafb887e0b89bacbac10`, branch `exp/profiling-results-demo`.

## Result and actual visual inspection

`BLOCKED_GEOMETRY`: 1,101 input images checked, 100 actual anomalous masks;
no dimension/alignment errors and no entirely empty target anomaly masks.
Original-resolution 8-connected IDs: 324 total, 305 represented, 19 lost across
9 images. Lost original areas: 1–28 source pixels. Full FOV is not tiny-component preservation.

Both PNGs were directly opened with the image-viewing tool, not only checked by HTTP/DOM:

- `figures/geometry_examples.png`: original full board, anisotropic 224 image/GT,
  source-region detail for two loss cases and one no-loss control. Global GT/image alignment
  and full-board extent are visible. Neighboring components in source zooms are not the selected ID.
- `figures/component_sampling_details.png`: explicitly isolates the selected original ID
  (green), other GT (gray), and exact NEAREST source sample centers (cyan).
  `071.JPG` ID 5 has 20 source pixels/0 target samples;
  `077.JPG` ID 5 has 17/0. Control `000.JPG` ID 1 has 1,853/61.
  These are separate pixel units, not retention ratios or physical-defect counts.

The companion renderer checks selected input hashes and saved source-area/target-sample counts.
It was added after the audit to clarify the existing fixed examples; it does not change the
executed audit code, geometry, input selection, CSV/JSON results or predictions.
RGB-bearing figures are local-only and ignored by Git. See `FIGURE_MANIFEST.json` for hashes.

## Verification

- Python 3.11.16 existing environment: **143 passed**, 51.53 s; CPU smoke passed (2 rows).
- Separate no-Torch/no-FAISS Python 3.11.16 environment: **142 passed, 1 existing torch-only skip**,
  34.41 s; CPU smoke passed (2 rows).
- New focused tests: **6 passed**. Synthetic audit verifies manifest/split/hash guards,
  expected lost component, immutable source inputs, and existing-output rejection.
- Original preprocessing, runner, metrics, stored research results and bank configuration are unchanged.
- All 1,201 actual input file hashes (1,101 RGB + 100 GT), protocol/source hashes and the
  INPUTS.csv hash were rechecked after the audit; all match. Protected prior scientific paths have no diff.
- No degradation, model fit/inference, calibration, anomaly metric or new performance benchmark ran.

Protocol SHA256: `43fbc034f5e2606a035e2a6cb0822ebc7abffe285255fe394702bd2765a3b8fa`.
INPUTS.csv SHA256: `944eb87bde1c8e0b16bf57bf596a74a7036419a50395d4172f5821c9168e9184`.
Source code hashes are in `PROTOCOL.json`; input RGB/mask hashes are in `INPUTS.csv`.
These frozen bytes are protected from Git newline conversion where hashed.

## Reproduce without model execution

From the repository root, PowerShell (a fresh output ID is mandatory):

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_test.py
$pcbRun = 'pcb2-full-frame224-replay-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/prepare_pcb_geometry.py --run-id $pcbRun
.venv\Scripts\python.exe scripts/render_pcb_geometry_ids.py --audit "analysis/pcb_geometry/$pcbRun"
git diff --check
```

Default input is repository-relative `data/external/VisA`; `--data-root` may specify another
VisA root without editing code. Existing output directories are never overwritten.
No GPU pilot is ready: see `docs/PCB_FULL_FOV_PROTOCOL_V0.1.md` prerequisites.
