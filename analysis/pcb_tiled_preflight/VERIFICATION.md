# Tiled adapter CPU verification, 2026-10-16

Status: CPU_ADAPTER_TEST_PASS / REAL_MODEL_SMOKE_NOT_RUN / NOT_READY_FOR_FULL_PILOT.
Actual PCB bank/calibration NOT_CREATED. No real dataset RGB/GT content, model fit/inference,
FAISS index/search, SR/degradation experiment or anomaly metric execution occurred.
Existing negative gating/full110 B/B-uncertain and protected scientific files are unchanged.

## Evidence

- Full pytest:228 passed in88.31s. New tests20 total, including4 actual vendored-postprocessing
  tests with fabricated backbone features and fake distances. No pretrained model forward.
- No-Torch/FAISS environment:16 passed,4 skipped in32.47s for the new files. Missing optional
  runtimes skip only those4 vendored-postprocessing tests; core runner/preflight tests still pass.
- Existing CPU smoke in both environments:pass,2 result rows each, temporary generated inputs only.
- CLI --help inspected; no --execute invocation. git diff --check passes.
- Fake raw runner saves9 board maps (one cal/two test ×3 variants), exact source-coordinate
  reference equality, identical predictions after test-label changes and unchanged bank hashes.
  No GT parameter/model input, no thresholds/quality/anomaly metrics. Wrong index SHA fails
  before extraction; manifest tampering/checkpoint/device/resource/source/overwrite guards tested.
- Real vendored PatchMaker central patch values establish y/x order. Actual _embed layer
  alignment/preprocessing/aggregation checked against singleton batches. Actual _predict map
  upsample/Gaussian smoothing runs with fake distances, without FAISS. Image score stays original
  tile max, not smoothed-map max. Normalization exactly matches existing torchvision transform.

## Actual path/hash-only preflight

Final code/source hashes rechecked against both saved reports. Metadata includes pre-commit HEAD
0c5c101 and dirty=true; exact new executed source hashes identify this code, not HEAD alone.
No RGB/GT content is opened. Official split CSV and local checkpoint bytes are hashed only.

| scope | status / exit | fit/cal/test tiles | bank payload |
|---|---|---|---|
| model-smoke | PREFLIGHT_PASS /0 |48 /48 /96 |154140672 bytes (147MiB) |
| full-pilot | PREFLIGHT_BLOCKED /2 |34608 /8640 /9600 |1073741824 bytes (1GiB) |

- `pcb2-tiled-adapter-smoke-20261016/preflight.json`
  SHA256244266f78c0f80d381df6abb1098157887e8c85cb908421a6817864391f9346d.
- `pcb2-tiled-adapter-full-20261016/preflight.json`
  SHA256f8375f824241fe9c3786dad02789da3a2607eefbd458bce276a3669099c7708a.

Smoke visible bank/scorer/index+chunk/board scenario507021656 bytes; minimum saved payload
208523808 bytes, NOT total RAM/VRAM/disk requirement. Full corresponding scenario3265825112 bytes;
available RAM snapshot3190980608 bytes. These are calculated payloads and transient available-RAM
readings, not peak-memory/runtime benchmarks. Other applications/test processes can affect RAM.

Full test pixels300456000. Unchanged Pixel AUROC visible simultaneous lower-bound scenario39P
=11717784000 bytes (~10.91GiB), excluding sort/unique workspace, model/index, page cache and other
caller arrays. AU-PRO region masks are a separate scenario. No metric was computed to obtain this.
Full also blocks unconditionally pending native evaluation lifecycle and board calibration/quality
proposal approval/full orchestration. No full --execute command is considered runnable.

Earlier mid-implementation preflight snapshots were moved unchanged to ignored outputs/
`pcb2-adapter-cpu-preflight-20261016-draft/` and `pcb2-adapter-full-preflight-20261016-draft/`.
Before/after hashes matched; they were not overwritten or substituted for final evidence.

## Implementation and limits

Added pcb_tiled_models.py, pcb_tiled_runner.py, run_pcb_tiled_patchcore.py, two test files,
protocol v0.5 and GPU handoff. Pure CPU tests/preflight never instantiate a real backbone/restorer.
Existing third-party/Branch A/B/bank/geometry/evaluation/fusion/results files have no diff.
Model smoke implementation uses one subset clean-fit bank and raw maps only; full calibration,
quality reporting and native evaluation are deliberately not enabled, not silently completed.
No real CUDA/checkpoint load/backbone feature values/map parity/latency/peak RAM/VRAM is verified.

AST-only Graphify update completed without API/semantic extraction. It warned that5 .m files
have no extractor and pyproject.toml produced no nodes; generated community names are not a
complete semantic review. No LLM relabel or plugin/hook setting change was performed.

## Reproduce, PowerShell from research_code

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_test.py
$checkRun = 'pcb-tiled-cpu-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/run_pcb_tiled_patchcore.py --run-id $checkRun --scope model-smoke --device cpu --data-root data/external/VisA
$fullRun = 'pcb-tiled-full-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/run_pcb_tiled_patchcore.py --run-id $fullRun --scope full-pilot --device cpu --data-root data/external/VisA
# Expected full preflight exit2; this is not a test failure or inference invocation.
git diff --check
```

GPU commands and artifact-return checklist: docs/PCB_TILED_GPU_HANDOFF.md. No push/main merge/deploy.
