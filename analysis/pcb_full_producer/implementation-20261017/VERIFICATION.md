# CPU streaming producer verification

2026-10-17 KST. Local `exp/pcb-full-producer-integration`, base public bb22cf8.
Original exp/profiling-results-demo/79a1c0f and its pre-existing PROGRESS edits
were preserved. No push, model/FAISS/SR execution, native arrays/GT, full bank,
actual calibration, tuning or full pilot was performed.

## Executed evidence

Final standalone run, ignored/local-only:
`outputs/pcb-full-producer/pcb-producer-synthetic-20261017-final/`

- Status SYNTHETIC_INTEGRATION_PASS_NOT_FULL_APPROVAL; full approval false.
- Generated336x224 fixture:2 normal fit,2 normal calibration,2 test boards.
  Synthetic grid2x2/D4/K7, not native model settings. Each board has2 RGB tiles.
- One factory, one bank bind:16 observed/validated vectors,7 retained; maximum
  observed chunk8 vectors. Same bank file hashes before/after all predictions.
- 12 finite float32 maps, each224x336. Independent unit references match board
  maps/scores exactly and check canonical RGB tile/overlap assembly equality.
- Transform callback8 calls per named variant (24 total); quality callback makes
  ZERO transform calls. No actual restoration model is involved.
- Seven sequential workers exited0. Owned fake model/index/scorer feature
  weak references released. No worker imported Torch/FAISS/PatchCore.
- Largest INDIVIDUAL OS process-lifetime peak working set109326336 bytes
  (104.26MiB), not simultaneous machine/native/VRAM peak. Startup/imports included
  by the OS high-water; worker elapsed and parent launch-to-exit times are separate.
- Consumed lossless RGB files2258944 bytes including NPY headers were removed
  after all workers/artifacts validated. Worker failure tests preserve prior RGB.
  Raw maps/bank/quality/calibration/evaluation files remain SYNTHETIC local evidence.
- All14 frozen executable source hashes match final implementation checkout.
  Historical run records bb22cf8 and dirty=true because it predates the local
  implementation commit; those fields are not rewritten after committing.

Final full pytest: **294 passed,1 skipped**,165.61s. Skip is optional MVTec-data
integration. Log: `outputs/producer-full-pytest-final.log`.
Separate no-Torch/FAISS Python3.11 environment: **14 new tests passed**,62.07s;
log `outputs/producer-notorch-final.log`. Existing CPU smoke passed with2 rows.
Diff check passed; existing runner, adapters, geometry, bank builder, calibration,
evaluation/fusion and full execution guard have no diff against bb22cf8.

Tests cover shared bank/order/batch invariance, test-label/GT non-use in production
and calibration, exact reference outputs, RGB reuse/quality, invalid split/order/
shape/checksum/missing/incomplete artifacts, low RAM/disk, early index mismatch,
partial mmap closure, failed/timed-out worker status, success cleanup, no overwrite,
and the old/new real-execution blocks before any real factory.

Development failures retained in ignored logs: failure-injection initially also
intercepted Git metadata probes; constrained it to owned stage launches. Windows
cp949 could not decode an error JSON containing a Korean path; tests now explicitly
read UTF-8. A test helper retained closed NumPy mmap arrays and pytest attempted
their repr, causing a Windows access violation; helper now retains mmap handles
only, not closed array objects. Final tests pass without disabling validations.
No such crash is claimed to be a native workload measurement or model failure.

## Remaining resource/execution gates

Native metadata only:721/180/200 parents;34608/8640/9600 tiles;27132672 fit
vectors; unchanged K262144/D1024/seed11/chunk8192. No native payload allocated.

Disk payload: raw maps6.380GiB + RGB spool4.877GiB + normalized files6.716GiB
+ bank1GiB + indices =18.975GiB before cleanup,14.098GiB after RGB cleanup.
Original dataset/checkpoints, headers/logs/free-space margins and failed runs
are additional. Earlier memory rehearsal's4.36GiB disk gate is a different scope.

Producer visible RAM scenarios: build2.012GiB; prediction3.038GiB. These exclude
actual model/activations/FAISS scratch/OS/runtime/selection/page cache. Existing
calibration/evaluation envelopes remain about6.09/18.42GiB; normalization uses
the existing32Bmax planning guard; quality adds a7,225,344-byte tile tensor to its
existing envelope. None of these estimates is a proven upper bound or measured
native peak. Full metadata plan includes frozen498756960-byte4-connected-region
mask payload without reading GT.

Teammate native-memory execution/review is still pending; actual model RSS/VRAM,
full producer disk budget, real hash-audited RGB/GT factory wiring and explicit
full-execution review remain separate. Existing CUDA raw smoke and its dirty=true
provenance are untouched. No synthetic success unlocks the full runner.

## Reproduction

See `docs/PCB_FULL_PRODUCER_HANDOFF.md` for interpreter/worktree details.

```powershell
python -m pytest -q
$run = 'pcb-producer-synthetic-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_full_producer.py --run-id $run
python scripts/smoke_test.py
git diff --check
```

Each run ID must be new. Under the restricted local sandbox, pytest used a unique
workspace-local outputs/ --basetemp; full regression used approved normal Git/MSYS
execution. Generated arrays/RGB/metrics/logs are ignored, never public results.
