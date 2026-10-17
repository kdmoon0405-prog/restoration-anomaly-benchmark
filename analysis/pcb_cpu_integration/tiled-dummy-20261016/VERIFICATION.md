# Tiled synthetic CPU integration verification

2026-10-16 KST; base `5cb2c1e`, branch `exp/profiling-results-demo`.
Execution rules/code frozen at `2026-10-16T08:19:24.576772+00:00` before the dry-run.

## Executed scope

Connected generated parent RGB -> native geometry tiles -> injected dummy feature callback
-> bounded-bank builder -> injected dummy tile maps/scores -> board mean map/max tile score
-> NPY/metadata persistence -> one-map-at-a-time checked reload.

Two fit-normal parents, one normal calibration parent, two test parents. Toy patch grid2×2,
D4, K17, seed11, tile feature batch2; not the real planned D1024/K262144 configuration.
Expected/observed fit vectors **32/32**, stored17, bank272 bytes, selected index136 bytes.
Six parent/variant maps (`dummy_a`, `dummy_b`) reloaded exactly. Independent recomputation
from individual dummy tile outputs matches every saved map and scalar score.
Score is max original tile IMAGE score, not max assembled map; the demo's scores are deliberately
different from map maxima. No quality/detection metric is generated.

Status: **synthetic integration PASS**, actual PCB bank/calibration **NOT_CREATED**,
pilot **NOT_READY_FOR_PILOT**. No real dataset RGB/GT, feature, model, FAISS index, degradation,
restoration, normalization/calibration/threshold or anomaly metric was read/executed/computed.
Old geometry/bank verification was not rerun; only metadata hashes were checked.

## New test evidence

- Full pytest **208 passed**,21.23 s.
- Focused new tests **21 passed**, also **21 passed** in the separate no-Torch/no-FAISS
  Python3.11 environment. Both CPU smokes passed (2 rows each).
- Hand-check336×224, two overlapping224 tiles: values2/6 -> overlap4; edge values remain2/6.
  Tile scores-10/-3 give board score-3, not map maximum6.
- Reverse arrival order gives identical canonical reduction; non-square corners and shared
  mutable callback buffer snapshotting are checked.
- Missing/duplicate/unknown/bool tile IDs, wrong coordinates/sample/variant/shape/dtype,
  nonfinite maps/scores, bool scores and zero coverage are rejected.
- Feature chunks at batch1/3/8 match a tiny independently assembled parent/tile/patch-y/x
  reference and produce identical selected bank values. Fit generator rejects non-fit parents.
- Original/inverted/absent synthetic GT produces identical map hashes/scores and bank values.
- Cal/test predictor receives read-only mmap bank; attempted update fails the overall run.
  Before/after bank/index/status hashes are identical on successful execution.
- Reload preserves sample/variant/label/split/shape/value and source/selection provenance;
  corrupt map, failed run and overwrite attempts are rejected.

Code/prior-budget/root-status/bank/map hashes were checked after execution. Protected previous
geometry, bounded-bank, runners, calibration/metrics, third-party code and research artifacts
have no diff. git diff --check passed. No dependencies added. AST-only Graphify update completed.

## Memory interpretation

Array bounds only, NOT measured RSS/VRAM/runtime:

- v0.3 production-plan bank1 GiB / selected indices2 MiB / feature chunk≤32 MiB remain theoretical.
- Native1404×1070 scenario with48 tiles: owned map snapshots9,633,792 bytes; float64 board
  accumulator12,018,240; uint32 coverage6,009,120; float32 output6,009,120; RGB4,506,840.
- Map snapshots/accumulator/count/output coexist within assembly; feature batch phase differs.
  Tile list plus `np.stack` RGB batch can briefly coexist. Callback/model memory is separate.
- Verification re-computes one board reference; reload mmaps and creates a finite-check bool
  buffer. No dataset map stack is built; consumer retention and OS page cache are outside the bound.
- Existing evaluator float64/sort/region-mask arrays remain unresolved. mmap does not remove them.

## Metadata and remaining prerequisites

PROTOCOL SHA256: `5b689843a25b4ad9d7a940c9a1111a29c63547926670d57291ceca92bb42f9eb`.
Payload status SHA256: `b5ceead784abdfcb805ef87d32d5c94566d7053513c5b1fcbfc7d5be58de2909`.
Small JSON/CSV reports are here; maps, synthetic bank/status are local-only under
`outputs/pcb-cpu-integration/tiled-dummy-20261016/`. No RGB/GT arrays were saved.

Real `_embed` wrapper and patch shape/order proof, normalization/calibration stage/formula,
180-normal usage, tile-wise x4/boundaries, quality overlap accounting, native evaluation memory,
checkpoint/device smoke remain pending. Existing robust median/IQR/std/unit helpers were read
but never called. Fusion-coupled calibration cannot simply substitute for this no-fusion board plan.
See `docs/PCB_FULL_FOV_PROTOCOL_V0.4.md`. Negative gating/full110 B/B-uncertain stay unchanged.

## Reproduce (PowerShell, repository root)

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_test.py
$integrationRun = 'tiled-cpu-replay-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python.exe scripts/check_tiled_cpu_integration.py --run-id $integrationRun
git diff --check
```

Existing report/payload directories are rejected. The command generates dummy inputs only
and cannot load an actual model or launch a PCB experiment.
