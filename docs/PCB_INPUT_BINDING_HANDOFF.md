# Frozen PCB input callbacks and CPU file audit

2026-10-20. These are input checks, not model inference or a new scientific
protocol. Frozen native geometry, parent split, bank and v0.6 rules are unchanged.

`pcb_input_binding.FrozenPCBInputs(root, data_root)` validates the existing
geometry inventory and official VisA CSV. Construction decodes no RGB/GT.
The supplied Parent must exactly match the frozen path/split/label/native size.

- `.rgb(parent)` verifies the compressed file hash, then decodes those same
  bytes through BytesIO into native uint8 RGB. There is no resize, padding or
  EXIF transpose. A changed file between verification and a second path open
  cannot silently enter the decoder because there is no second path open.
- `.evaluation_mask(parent)` is test-only and reuses the existing hash-checked
  native binary-GT implementation. Normal test parents get explicit zero masks
  without a GT file. Fit/calibration parents are rejected before GT I/O.
- Separate RGB/GT receipts record source and decoded/binary checksums, shapes
  and identity. No GT callback goes into the new model-resource smoke.

The real producer is still blocked. File callbacks are exercised through the
existing generated-data fake producer/calibration/quality/evaluator in tests;
this is not actual PCB training or a full PCB result.

## Audit modes

`scripts/check_pcb_input_binding.py` always uses unique ignored output paths
under outputs/pcb-input-binding/. Existing output and source/output overlap are
refused. Source/protocol/receipt hashes and dirty-source truth are retained.

Default: frozen metadata/official CSV only, PREFLIGHT_PASS does not imply decoded
inputs. Explicit `--execute --hashes-only` streams all file hashes with the
existing bounded hasher; it allocates no native image/mask arrays and reports
FILE_HASHES_VALIDATED_DECODE_PENDING_NOT_FULL_APPROVAL.

Explicit `--execute` without hashes-only verifies RGB sequentially, then test GT
in its separate evaluation-input phase. Before each board it checks a 64-bytes-
per-native-pixel technical array plan plus the unchanged2GiB reserve. This is a
single-board plan, not the full180/200 evaluator's20.42GiB prerequisite and not
an RSS upper bound. No guard is lowered when RAM is insufficient. Completion is
INPUT_BINDING_VALIDATED_NOT_FULL_APPROVAL, never full-pilot authorization.

No per-image dataset exclusion, dilation, crop, degradation, model or anomaly
metric is run. Four-connected GT region counts only verify evaluator input
structure; they are not physical defect counts or detection performance.

## Local worktree reproduction

From the current code worktree, reuse the original environment/data explicitly:

```powershell
$py = (Resolve-Path ../../.venv/Scripts/python.exe).Path
$visa = (Resolve-Path ../../data/external/VisA).Path
$run = 'pcb2-input-hashes-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $py scripts/check_pcb_input_binding.py --run-id $run --data-root $visa --execute --hashes-only
$run = 'pcb2-input-decode-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $py scripts/check_pcb_input_binding.py --run-id $run --data-root $visa --execute
$temp = Join-Path ([IO.Path]::GetTempPath()) ('sr-pcb-tests-' + [guid]::NewGuid().ToString('N'))
& $py -m pytest -q --basetemp $temp
& $py scripts/smoke_test.py
```

A regular clone should use its activated Python and actual VISA_ROOT instead.
New worktrees do not inherit data, checkpoints or .venv. OS-temp test directories
avoid placing high-frequency synthetic writes inside OneDrive; this does not
prove production file replacement is immune to external file locks.

Model/index RSS/VRAM evidence is the next separate gate. See
PCB_MODEL_RESOURCE_SMOKE.md. Its default is preflight-only; even explicit execute
is the old37632-vector limited smoke, never the262144-bank full pilot. This task
does not publish the new code or authorize an actual GPU/full experiment.
