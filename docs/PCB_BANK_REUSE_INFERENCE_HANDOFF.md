# Actual-bank reuse integration handoff

This is an engineering integration path on `exp/pcb-full-producer-integration`.
Publication is not independent design approval or full-cohort authorization.
The GPU operator reviews the actual diff and makes an integration GO/NO_GO before
one bounded run. Independent reviews have not yet been supplied to this CPU task.

## Fixed scope

`scripts/run_pcb_reuse_inference.py` requires `--run-id`, `--bank-run`,
`--data-root`. Default is preflight only; `--execute` requires live CUDA.
There is no CPU fallback, full scope, selection/shape/seed override or resume.
Static PREFLIGHT_PASS does not confirm live CUDA; that check is execute-only.

The explicit bank source is the reviewed real fit run:
`outputs/pcb-fit-bank/pcb-real-fit-bank-20261029-163524`.
It must contain PROTOCOL.json, status.json, resources.json, stage_times.csv,
fit_progress.json, fit_rgb_receipts.json and bank/{status.json,bank.npy,
selected_indices.npy}. Metadata-only ZIPs do not supply the bank.

The pinned bank.npy digest is
`19c3bb03a6b84475bfdc36602d05b975c57c387da81f0713c5da86b8d2f1278e`;
the selected-index logical digest is
`480f53ec4fbe355a3a5948e6a895dfdd63058eb903b8e108613a8e3a63afb402`.
N27132672/K262144/D1024 float32, seed11, native224/maxstride192 and the current
model/layer/patch/normalization/checkpoint contracts are unchanged. Admission
binds the reviewed fit metadata and actual NPY bytes/shape/counts/chunked finite
values. This is a fixed reviewed-bank identity, not a signed remote attestation
or a registry of arbitrary training runs.

The fit865f26a/dirty=true provenance stays unchanged. A newer inference commit
is allowed when common frozen source/checkpoint/reference bytes match. The new
run has its own source commit/dirty/input receipts. Old remote JSON paths are
not opened: bank/data/checkpoints must be explicitly supplied in this checkout.

The three inference parents are the pre-fixed frozen smoke selection without
the fit parent:

- calibration-normal: pcb2/Data/Images/Normal/0000.JPG
- test-normal: pcb2/Data/Images/Normal/0011.JPG
- test-anomaly: pcb2/Data/Images/Anomaly/000.JPG

Each has48 native tiles. Clean/Bicubic-x4/SwinIR-x4 produce432 detector queries,
9 native float32 maps and9 raw board scores,2 native test RGB references and6
uint8 produced-tile RGB spools. Raw tile maps merge by overlap mean; board score
is max of original tile scores. GT never enters inference. Produced RGB is
transformed once and shared between prediction/spooling; mutation is rejected.

Loading/binding the bank once is allowed. `adapter.bind_bank` internally calls
the upstream scorer's fit to construct a CPU exact IndexFlatL2/four-worker index.
This is not re-extracting normal-fit images or building a new patch bank. The
integration never calls feature_chunks/save_bank or reads fit RGB.

## Explicit external-bank contract

The bank is referenced, never copied or rewritten. The output records its nine
source digests and fit provenance; readers require an explicit `bank_run` path
again rather than following the recorded location. This avoids an unnecessary
1GiB copy but makes the integration dependent on the separately retained bank.
For a later portable/full artifact, a verified immutable copy may be considered
with explicit disk accounting and peer review; it is not silently implemented here.

The old synthetic producer/reader and full `board.load_raw_run` guard are intact.
They must not accept this small integration as a180-normal calibration cohort.
`load_integration(...,bank_run=...)` validates this distinct scope, supplied
map/RGB hashes/shape/dtype and map finiteness sequentially. `IntegrationRGBSpool`
offers reference(parent)/tiles(parent,variant) for the existing assemble_rgb
and eventual quality callbacks. It never runs a restorer. Future full-cohort
admission and process orchestration remain a separate task.

Successful actual status is
`BANK_REUSE_INTEGRATION_COMPLETE_NOT_FULL_APPROVAL`, kind
`reviewed_bank_reuse_integration_not_full_pilot`.
CPU injection uses `INJECTED_REUSE_COMPLETE_NOT_GPU_EVIDENCE` and is rejected by
the production reader. Every run keeps bank_created_this_run=false and
full_cohort_inference_complete/full_pilot_approved=false; calibration/thresholds/
quality/detection metrics remain null. No synthetic result becomes a PCB result.

## Resource and lifecycle policy

The inference-specific planning scenario is approximately8.687914GiB available
RAM including the unchanged2GiB reserve, and1.161637GiB free disk including the
existing1GiB disk reserve. It includes three bank-residency/copy/index payloads,
two784x262144 distance-array scenarios, query/finite/index workspace, a native
board's map/RGB/spool buffers, CPU model/runtime allowance2GiB and metadata64MiB.
Existing bank storage is not counted as new output. The prior fit6.2044GiB plan
is not reused as an inference plan.

These are explicit scenarios with overlapping quantities, not measured peaks or
upper bounds. Extra FAISS/BLAS/page-cache/allocator/VRAM effects may exceed them.
Fresh guards run before mapping/scanning the bank and before model setup. No
app/OS/pagefile/thread/FAISS setting is changed to pass a guard.

One board/variant is processed at a time; no full map stack is retained. The
spool closes on success/error, the adapter closes its index/scorer/model, bank
mmaps close, and transform/model variables clear. Failure tracebacks or allocator
caches can persist until this dedicated CLI process exits; no self-attested
process-exit/VRAM-leak conclusion is made. Failed output is preserved and cannot
be overwritten/resumed. A completed original bank remains read-only and reusable.

Recorder child calls are disjoint and CUDA synchronized. Outer time includes
calls plus loading/hash checks/assembly/writes/cleanup after the execution timer
begins; preflight and validation before that timer are separate. Never add outer
and child times or compare them as matched workloads to the22-minute fit.
The final resources/CSV/status serialization happens after the outer timer ends;
shell launch-to-exit wall time is a separate measurement if the operator records it.
Sampled RSS, OS lifetime peak, PyTorch CUDA allocated/reserved counters, output
bytes and drive-wide free-space changes have distinct meanings.

## Existing GPU checkout commands

Preserve the existing branch/worktree/venv/data/checkpoints/results. Fetch and
compare the exact full commit reported by CPU delivery before switching safely.
New checkouts do not inherit any of those large/private inputs.

```powershell
git fetch origin exp/pcb-full-producer-integration
$pcbCommit = (git rev-parse origin/exp/pcb-full-producer-integration).Trim()
git merge-base --is-ancestor 865f26aabf4598354e1b8fb4605dc9ff09a7e810 $pcbCommit
git cat-file -e "${pcbCommit}:scripts/run_pcb_reuse_inference.py"
git cat-file -e "${pcbCommit}:docs/PCB_BANK_REUSE_INFERENCE_HANDOFF.md"
git switch --detach $pcbCommit
$pcbOldLfsSkip = [Environment]::GetEnvironmentVariable('GIT_LFS_SKIP_SMUDGE','Process')
try {
    $env:GIT_LFS_SKIP_SMUDGE = '1'
    git -c core.autocrlf=true submodule update --init -- third_party/SwinIR third_party/patchcore-inspection
    if ($LASTEXITCODE -ne 0) { throw 'Pinned model-source initialization failed' }
} finally {
    [Environment]::SetEnvironmentVariable('GIT_LFS_SKIP_SMUDGE',$pcbOldLfsSkip,'Process')
}
$pcbPython = (Resolve-Path '.venv/Scripts/python.exe').Path
$pcbData = (Resolve-Path 'data/external/VisA').Path
$pcbBank = (Resolve-Path 'outputs/pcb-fit-bank/pcb-real-fit-bank-20261029-163524').Path
& $pcbPython scripts/run_pcb_reuse_inference.py --help
$pcbCheck = 'pcb-reuse-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $pcbPython scripts/run_pcb_reuse_inference.py --run-id $pcbCheck --bank-run $pcbBank --data-root $pcbData --device cuda
```

Check every exit code and the saved plan/bank/source contract. Supply actual
existing checkpoint paths using --backbone-checkpoint/--swinir-checkpoint or
PATCHCORE_BACKBONE_CHECKPOINT/SWINIR_X4_CHECKPOINT if defaults differ; use those
same options in preflight and execute. No checkpoint download occurs in this CLI.

Only after independent integration GO and actual PREFLIGHT_PASS, execute once
with a new ID. It makes its own fresh preflight and resource checks:

```powershell
$pcbRun = 'pcb-reuse-integration-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $pcbPython scripts/run_pcb_reuse_inference.py --run-id $pcbRun --bank-run $pcbBank --data-root $pcbData --device cuda --execute
Write-Output "Exit code: $LASTEXITCODE"
```

## Verify and return

Under outputs/pcb-reuse-inference/run-id, inspect PROTOCOL/status/resources and
stage_times.csv. Confirm bank bind1/query432, maps9,reference2/tile-RGB6, source
bank hash unchanged, exact sample/variant/coordinates and direct payload checks.
Keep maps/RGB/bank privately. No source bank copy or new bank is created.

Return only the new integration metadata, commands/environment/GO_NO_GO and
SHA256SUMS with original subdirectories. Put source-fit metadata references in
the report; do not flatten status.json files. Arrays/data/weights/venv/private
notes are excluded from Git/metadata ZIP. A receiver without those payloads
cannot independently validate their contents. Do not invoke the older resource
reviewer on this new kind or label the artifact full-pilot-raw.

The next decision is based on independent design review and this actual
integration: full inference/calibration180/test200 with preserved produced RGB,
then separate normal-only calibration, quality and exact evaluation. The earlier
native rehearsal succeeded for its version/scenario; do not repeatedly call it
unexecuted. Retain current resource/version/disk/full-execution gates. This
delivery does not approve or execute that full experiment.
