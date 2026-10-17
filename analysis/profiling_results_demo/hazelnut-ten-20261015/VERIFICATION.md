# Verification record, 2026-10-15

- Existing Python 3.11.16 environment: `python -m pytest -q` = **135 passed, 47.65 s**.
- Separate editable `[dev]` Python 3.11.16 environment without Torch/FAISS: **134 passed, 1 existing torch-only skip, 46.92 s**. No GPU requirement for these tests.
- `python scripts/smoke_test.py`: **passed, 2 result rows**, in both environments. Synthetic temporary inputs only.
- New deterministic tests cover conditional-cost algebra, timer/instrumentation detach/shape behavior and restoration after exceptions, bank-size resource extrapolation, shared map scale, null normal AU-PRO, no candidate image quality, GT-independent gates, missing-artifact API/export blocking, read-only methods/Host guard, and readiness selection count/completeness/lexical ties.
- Actual profiling: 64 saved-anchor comparisons passed, all map/score maximum absolute differences 0.0. Protocol SHA and all 30 input/source SHA256 values verified unchanged after profiling/demo/testing. Report generation rechecks protocol and executed profiler hashes.
- Protected scientific code and historical analysis directories have no Git diff. Existing raw predictions/calibration/bank/checkpoints were read only. No full110, Screw, Capsule or PCB experiment was executed; no map-gate candidate inference or new metric/calibration was added.
- Actual HTTP/PNG/CSV verification and the browser-screen limitation: [DEMO_VERIFICATION.md](DEMO_VERIFICATION.md). Inline JavaScript passed Node syntax validation; no unexpected Japanese text was found in the HTML.
- `graphify update .` completed AST-only in the parent project. It reported unsupported MATLAB files and stale community labels; no semantic/API-cost relabeling was run. Graph artifacts are not part of the research commit.
- Working/index `git diff --check` passed before the local commit. Frozen protocol and profiler Git-index bytes match the execution hashes. No push, main merge, PR, deployment or Actions rerun is included.

Reproduction from the repository root (PowerShell):

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts/smoke_test.py
.venv\Scripts\python scripts/summarize_profiling_readiness.py --input analysis/profiling_results_demo/hazelnut-ten-20261015
.venv\Scripts\python scripts/serve_results_demo.py --port 8765
```

Open `http://127.0.0.1:8765`; Ctrl+C stops the local service. This reproduction uses saved data only. Do not rerun the profiler to read existing results. A separately authorized timing replay needs the exact local bank/data/checkpoints and a new unique run-id; it cannot recreate these measured durations exactly.
