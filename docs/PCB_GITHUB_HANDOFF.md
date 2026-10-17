# PCB GPU smoke publication handoff

2026-10-17. Delivery branch: `exp/pcb-tiled-gpu-handoff`.

## Source and publication boundary

This branch publishes a text/code snapshot of local `79a1c0f`, based on the already
published `4742200`. Local commits such as `7167cd1` are historical source references,
not commits that the recipient needs to fetch. Use this delivery branch's actual
commit and file hashes for new execution records.

The original unpublished history was not pushed because it contains two qualitative
PNG panels with licensed dataset RGB. Those panels are excluded here. Dataset files,
weights, raw prediction arrays, local-only research journals, virtual environments
and browser screenshots are not included. Historical reports and their hashes are
preserved, not regenerated. A report may reference an intentionally local-only image.

Read `PCB_FULL_FOV_PROTOCOL_V0.6.md`, `PCB_BOARD_LIFECYCLE_HANDOFF.md`, and
`PCB_TILED_GPU_HANDOFF.md` in that order. The v0.5 handoff's publication status is
historical; this document records the new publication boundary. No research rule,
bank setting, geometry, calibration rule or metric is changed by this delivery.
The evaluator, quality metrics and geometry-audit-bound legacy files have explicit
checkout rules so Windows autocrlf does not invalidate their recorded byte hashes.
The legacy fusion runner preserves its original mixed line endings verbatim; the
other newly pinned files use explicit LF or CRLF matching the audit. Their code and
research semantics are unchanged. Some pinned PatchCore audit hashes also bind CRLF
checkout bytes, so initialize new submodules with the explicit setting below.

## Receive without touching existing work

From the teammate's existing clone, preserve notebook edits and untracked submodule
files. Use a separate new worktree rather than resetting or cleaning that clone:

```powershell
git fetch origin
git worktree add -b pcb-tiled-gpu-smoke-local ../restoration-anomaly-pcb-smoke origin/exp/pcb-tiled-gpu-handoff
Set-Location ../restoration-anomaly-pcb-smoke
git -c core.autocrlf=true submodule update --init --recursive
git rev-parse HEAD
```

The destination and local branch must be unused; if either exists, inspect it or
choose a new name, never overwrite it. This new worktree does not inherit `.venv`,
datasets or checkpoints. Use the established CUDA environment and actual local input
paths described in the GPU handoff. Do not commit those inputs or environment files.
The commands below assume the CUDA environment's Python is active as `python`.

```powershell
python -m pytest -q
python scripts/smoke_test.py
python -c "import torch; print(torch.__version__, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
$checkId = 'pcb-tiled-cuda-preflight-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/run_pcb_tiled_patchcore.py --run-id $checkId --scope model-smoke --device cuda
```

Set `VISA_ROOT`, `PATCHCORE_BACKBONE_CHECKPOINT` and `SWINIR_X4_CHECKPOINT` to
existing local inputs before preflight when the default locations do not apply.
Do not bypass missing files, pinned checkpoint hashes, split or resource checks.
Only after reviewing exit code 0 and `PREFLIGHT_PASS`, run the limited raw smoke:

```powershell
$smokeId = 'pcb-tiled-cuda-raw-smoke-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
python scripts/run_pcb_tiled_patchcore.py --run-id $smokeId --scope model-smoke --device cuda --execute
```

Return the preflight report, raw smoke status/bank/predictions, source and checkpoint
hashes, command/exit status and observed RAM/VRAM if measured, as listed in the GPU
handoff. Large arrays must be transferred privately, not added to public Git history.
The smoke uses 1 fit / 1 calibration / 2 test boards and must produce 9 finite native
board maps. It does not establish PCB research metrics or full-pilot readiness.

## Gates that remain closed

Real GPU smoke has not been reviewed. Full native evaluation memory is not validated
on the GPU operator's host, and a full producer/orchestrator is not enabled. CPU
synthetic lifecycle checks do not resolve these gates. Do not run a full pilot,
reuse the smoke bank/calibration as full results, or infer CPU/CUDA parity from this
publication. No model inference was needed to publish this branch.

## Delivery verification

The separate publication worktree passed `python -m pytest -q --tb=short`:
242 passed, 1 skipped (the optional MVTec-data integration test; real data is not
distributed). `scripts/smoke_test.py` passed with 2 result rows. All 18 distinct
code-file hashes bound by the native geometry and board lifecycle protocols match
the delivery checkout. `git diff --cached --check` passed. The original local
branch and source worktree were preserved. No GPU/model inference was run.
