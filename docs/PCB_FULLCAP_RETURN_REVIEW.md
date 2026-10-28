# Reviewing full-cap synthetic resource returns

2026-10-28. This is a read-only checker for the separate engineering-probe kind.
It never creates models, loads arrays or imports Torch/FAISS runtimes. The old
limited-smoke checker retains its original scope. No new GPU return was available
when this checker was developed; CPU fixtures are synthetic metadata only.

## Inputs and provenance

Required run files: `PROTOCOL.json`, `status.json`, `resources.json`,
`stage_times.csv`. Use an explicit `--reference-run` pointing to the locally
supplied original limited-smoke metadata. The run's recorded remote absolute
reference/checkpoint paths are never followed. Omitting the reference produces
a rejected review with a clear reason, rather than weaker reference verification.
Preserve original bytes and dirty flags when copying the metadata between hosts.

The three artifact hash links are verified against `status.json`; the status
file itself has a computed receipt hash, without claiming an externally trusted
digest. All four computed hashes are recorded separately.

The reference needs the five files in the probe's `REFERENCE_FILES`, including
`raw/status.json`; include `raw/bank/status.json` when available. Missing raw
arrays remain listed as not supplied. An absent synthetic payload is expected
after successful producer cleanup: its reported SHA is not a locally verified
file/content hash. A present payload contradicts the successful cleanup contract.
Checkpoint hashes are compared as metadata against the pinned values; weights
and datasets are not opened. Extra source/reference paths are rejected before
the existing limited checker can follow them.

The execution commit must exist locally and match the reviewed canonical bound
sources. Actual file bytes are separately compared with the recorded bindings,
including the existing Windows line-ending rules. Checker commit and execution
commit are reported separately; unrelated later checker commits are permitted
when those execution-source bindings still match. No frozen hash is regenerated.

## Checks and meaning

The checker verifies fixed `(262144,1024)`/seed/chunk/query scope, source and
reference bindings, artifact hash links, six ordered query records, and the
producer's sixteen ordered stage calls. It reuses the existing recorder summary
and numeric/CUDA helpers. Timing serialization tolerance is the existing `1e-9`,
not a scientific selection threshold. Failed/preflight-only artifacts, malformed
metadata and CPU/injected fixture evidence cannot pass as CUDA full-cap evidence.

A passing classification is `REPORTED_CUDA_SYNTHETIC_FULLCAP_PROBE`, with
`CONSISTENCY_VERIFIED_NOT_FULL_APPROVAL`. It means internally consistent reported
resource metadata for this synthetic input. Independent remote execution,
synthetic-array contents and checkpoint-file verification remain false. Actual
PCB bank creation, full-bank validation and full-pilot approval remain false.

Outer and child times, sampled RSS and OS lifetime peak are separate values.
CUDA counters are PyTorch cumulative counters; drive-wide free-space change is
distinct from output payload before cleanup. Resource planning scenarios and
preflight snapshots are estimates/observations, not measured safe upper bounds.
Snapshots recorded after a guard are not assumed to be the guard's exact inputs.
No speedup, production throughput, anomaly metric or research comparison table
is produced.

## Commands

From this implementation checkout, explicitly reuse the original Python:

```powershell
$pcbPython = (Resolve-Path '../../.venv/Scripts/python.exe').Path
$testTmp = Join-Path ([IO.Path]::GetTempPath()) ('sr-fullcap-review-' + [guid]::NewGuid().ToString('N'))
& $pcbPython -m pytest -q tests/test_pcb_fullcap_review.py tests/test_pcb_fullcap_probe.py tests/test_pcb_resource_review.py --basetemp $testTmp
```

When the new return actually arrives, set `PCB_FULLCAP_RETURN` to its `probe`
directory and `PCB_LIMITED_REFERENCE` to the explicitly transferred `reference`
directory. Both must exist locally; the code does not rewrite remote paths.

```powershell
$out = 'analysis/pcb_fullcap_review/' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $pcbPython scripts/review_pcb_fullcap_probe.py --run "$env:PCB_FULLCAP_RETURN" --reference-run "$env:PCB_LIMITED_REFERENCE" --output $out
```

Exit 0 means a scope-limited consistency pass; exit 2 writes a rejection.
Both write fresh `review.json` and `REVIEW.md`; existing outputs and input/output
overlap are refused. Never relabel CPU test metadata as a real GPU return.

Next gates remain actual normal-fit feature/selection validation, real full
producer integration, current RAM/disk budgets and separate final execution
approval. This tool does not enable that executor or change scientific settings.
