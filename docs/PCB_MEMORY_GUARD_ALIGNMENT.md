# Board/rehearsal memory guard alignment

2026-10-18. Technical correction after review of the completed native synthetic
postprocessing rehearsal. No scientific protocol or full-execution permission changes.

## Corrected accounting

The rehearsal and board wrappers now share one guard in pcb_board_analysis.
Before allocation, available RAM must cover the total phase envelope plus the
unchanged 2 GiB OS/runtime reserve. After the evaluator's float64 map stack and
bool mask stack have been filled, the second check uses:

```text
total_cap_requirement = phase_envelope + 2 GiB
remaining_available_requirement = phase_envelope - known_live_arrays + 2 GiB
known_live_arrays = maps.nbytes + masks.nbytes
```

The old board wrapper compared the entire envelope with remaining available RAM
again, double-budgeting these arrays. Its missing reserve is also corrected for
calibration, normalization, quality and producer callers. The optional RAM cap is
always a TOTAL envelope-plus-reserve cap; live bytes never reduce it. Only owned
arrays already counted in the plan qualify for subtraction, not process RSS,
mmap address space, another process's peak or an unknown workspace. Invalid byte
counts, live bytes exceeding the plan and invalid availability probes are rejected.
NumPy integer counts are promoted to Python integers before arithmetic.

Small synthetic checker caps are now explicitly 3 GiB total: the same 1 GiB
payload allowance plus the fixed 2 GiB reserve. Both checker protocols record
these values and cap semantics. This is not a native budget override and the
current-available-RAM check still applies to every allocation phase.

The native numbers remain unchanged: evaluation envelope 19,776,013,920 bytes,
reserve 2,147,483,648 bytes, pre-allocation requirement 21,923,497,568 bytes.
For 200 native 1404x1070 boards, the already-filled arrays are 2,704,104,000 bytes.
The second check includes the original four-connected region-mask payload in
the total envelope and requires the unallocated remainder plus the same reserve.
Exact available/cap equality passes; one byte less blocks. No actual native
allocation or new measurement was performed to test these arithmetic boundaries.

## CPU checks and limits

Boundary tests cover both entry points, invalid inputs, native byte-count
arithmetic without native allocations, and a small board evaluation at the exact
post-allocation boundary (including failure before the evaluator when one byte
short). Existing tests retain checkerboard-region explosion blocking and exact
metric equality against evaluate_predictions. Metrics, region connectivity,
threshold rules, normal calibration, bank, seed and geometry are unchanged.

Verified locally: full pytest326 passed/1 optional-data skip(186.46s), focused
tests68 passed, no-Torch/FAISS boundary/producer tests46 passed(74.21s), existing
CPU smoke passed(2 rows), protected science/model/geometry/protocol diff unchanged.
An initial sandboxed full run was interrupted after stalling; the completed full
run used normal execution permissions, without changing Git/OS settings or tests.
Ignored logs: outputs/memory-guard-full-verified.log,
outputs/memory-guard-focused.log, outputs/memory-guard-notorch.log,
outputs/memory-guard-cpu-smoke.log. These small tests are not native peak measurements.

PowerShell from the repository with its normal test environment activated:

```powershell
$testTemp = 'outputs/pytest-budget-' + [guid]::NewGuid().ToString('N')
python -m pytest -q tests/test_pcb_memory_budget.py tests/test_pcb_board_analysis.py tests/test_pcb_native_memory.py --basetemp $testTemp
$producerRun = 'pcb-producer-budget-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/check_pcb_full_producer.py --run-id $producerRun
python scripts/smoke_test.py
git diff --check
```

The producer command runs only small fake-model processes, not PCB model
inference. Test logs and generated arrays remain in ignored outputs. Historical
protocols, source hashes, ZIPs and results are not overwritten. New runs bind the
intentionally changed sources; the old native completion remains evidence for
its recorded bb22cf8/dirty=true revision, not a run of this new revision.

Accepted native rehearsal measurements do not establish real-model/FAISS/index
or VRAM peaks, nor a universal RAM bound. Real input/checkpoint/GT callback
binding, model/index resource evidence, producer disk budget and explicit final
approval remain separate prerequisites. Both real-producer and full-pilot blocks
remain enabled. The local 15.53 GiB host is not authorized for native180/200.
