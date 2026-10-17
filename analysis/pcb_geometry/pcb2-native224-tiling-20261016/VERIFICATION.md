# Native tiling CPU verification

2026-10-16 KST, base `195df54`, branch `exp/profiling-results-demo`.
Execution rules/code frozen at `2026-10-16T07:12:03.302858+00:00` before image inspection.

## Actual geometry evidence

- All 1,101 parent images: exact RGB and GT/implicit-background reconstruction.
- 100 official anomaly GT files; 1,001 normals without official masks are explicitly distinguished.
- 48 native 224 tiles per 1404×1070 image, max stride 192, rational round-half-up.
- X starts: 0,169,337,506,674,843,1011,1180.
- Y starts: 0,169,338,508,677,846.
- Every source pixel is covered 1–4 times. Zero input/alignment/reconstruction errors.
- 324 original 8-connected annotation IDs preserved, 0 lost; all 19 prior lost IDs recovered
  with exact original source area. These are not physical-defect counts.
- Fit/calibration/test tiles 34,608/8,640/9,600; parent split 721/180/200 remains separate.

Verdict: **GEOMETRY_IDENTITY_PASS**, **NOT_READY_FOR_PILOT**.
No RGB degradation, fit, inference, calibration, FAISS experiment or anomaly metric was executed.

## Figures directly opened and reviewed

Opened original `figures/tiling_overview.png` and `component_reassembly.png` with the actual
image-viewing tool. Coverage, RGB extent and source/reassembled component shapes agree.
Some original long titles were clipped; a separate renderer generated readable copies under
`figure_review/figures/`, and BOTH revised PNGs were directly opened again.
The original audit code, protocol, CSV/JSON and original PNGs were not overwritten.

Revised overview: normal 0011.JPG and anomalous 071.JPG; cyan tile boundaries, complete
coverage color scale 1–4 and full-source reconstructed RGB, difference zero.
Revised details: 071 ID5 (20 source pixels), 077 ID5 (17), 000 ID1 (1,853), with original and
reassembled selected-ID shapes matching. Source zooms are explanatory only. No global RGB/GT
resampling or boundary trimming occurs. RGB-bearing PNGs are ignored/local-only.
Original and revised figure manifests separately record hashes and the revision renderer hash.

## Resource interpretation

Saved reference uses Wideresnet50 layer2/3, embedding D=1024, IdentitySampler/no coreset,
CPU exact FAISS. 245,392/313 = 784 patch vectors per 224 input. No bank was loaded/reused.
New fit: 27,132,672 vectors, 111,135,424,512 bytes = 103.503 GiB index vector payload.
Current fit can have original concatenation, scorer feature copy and index payload together:
310.509 GiB vector-only scenario, NOT measured RSS/VRAM. Other allocations are excluded.
Current host physical RAM read with Win32_ComputerSystem is 15.53 GiB; no model allocation
was attempted. GPU alone does not address this CPU index payload. Bank settings were not changed.

Native test map float32 payload is 1.119 GiB/method, 3.358 GiB for three methods;
one float64 conversion or int64 sort/rank array is 2.239 GiB. Existing AU-PRO keeps full-image
boolean masks for 332 FOUR-connected regions (0.465 GiB), distinct from the structural
8-connected ID taxonomy. Only masks were counted for resource planning, no metric was computed.
Do not add overlapping scenarios as independent allocations or interpret them as timing measurements.

## Tests and provenance

Full pytest: **154 passed**. New focused tests: **11 passed**, also in the separate no-Torch/no-FAISS
Python 3.11 environment. CPU smoke passed (2 rows). New tests cover extraction/reconstruction,
rounding, boundaries/small input/invalid coordinates, resource arithmetic, synthetic full audit,
frozen-input mismatch, figure revision and overwrite rejection.

All 1,201 original RGB/GT hashes were rechecked after execution. Frozen source/protocol/input/layout
hashes match. Protected old preprocessing, runners, metrics and prior results have no diff.
No new dependency, bank setting, coreset or metric was introduced. Prior negative gating and
full110 B/B-uncertain are unchanged. Graph maintenance is AST-only, not model analysis.

Protocol SHA256: `b14b59a28e77607b352b81c6a79a15e9bb6c153e395efefa8a547b25b9cf22b5`.
INPUTS SHA256: `0b4d45229d51aa633d91bb8919a71f5c4d9ea9e0827160fcc6ea0551b360a296`.
Layout SHA256: `9264b9f89181d8507e79c3dd0a6f8ffb5af0bb80a851e04f4c325ff11f2a5e73`.

## Reproduction (PowerShell, repository root)

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_test.py
$pcbRun = 'pcb2-native224-tiling-replay-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/prepare_pcb_tiling.py --run-id $pcbRun
.venv\Scripts\python.exe scripts/render_pcb_tiling_review.py --audit "analysis/pcb_geometry/$pcbRun"
git diff --check
```

Default input `data/external/VisA`; `--data-root` permits another root without code edits.
Existing audit and figure-revision directories are rejected rather than overwritten.
Next prerequisites are in `docs/PCB_FULL_FOV_PROTOCOL_V0.2.md`: resource feasibility,
map merger/board score/calibration/tile-wise x4, runner and checkpoint/device smoke.
No full pilot is authorized by this verification.
