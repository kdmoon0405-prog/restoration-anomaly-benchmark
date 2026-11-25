# Run record — final delivery (2026-11-15 ~ 11-16)

## Models

| part | model |
| --- | --- |
| Design v0.3, evaluation plan, implementation, real-photo runs, figures, poster, FINAL_REPORT / FINAL_REVIEW / DEMO_GUIDE text, decisions D-20261115-10..17 | Claude Fable 5.2 (`claude-fable-5-2`, Claude Code) |
| After 2026-11-16 12:10 KST: writing the notes into PROGRESS and the private note, this RUN_RECORD, RECEIPT.json, the return bundles, the commit of the poster scripts, push | Claude Opus 5.5 (`claude-opus-5-5`), switched by the user, who asked for the switch to be recorded |

The model names come from the Claude Code session settings at each step.

## Environment

Windows 11, GPU host, `.venv` Python 3.11.2, GPU NVIDIA GeForce MX570 A. PowerPoint 16.0 (COM) for the poster; Edge headless for screenshots. Nothing was installed.

## Sources

| item | commit / file |
| --- | --- |
| Phone code: design fixed before implementation | `exp/phone-lighting-juhyung@a031195` |
| Phone code: final path | `6748c95`, then `7b868a3` (timing split only) |
| Poster and figure scripts | `59db971` (`tools/poster_20261116/`) |
| CPU review read | `handoff/juhyung@8ddde87` (analysis), `492aa6a` (delegation) |
| Previous returns | `7b2c894` (development run), `5794b2d`, `0a3cfdf` |
| Private packet | `outputs/private-inbox/fable-final-handoff-private-20261115/`, six files matching `INPUT_RECEIPT.json` |

## Inputs (private, unchanged)

- 24 JPEG, `outputs/phone-captures/20261115/`, plus `capture_sheet.csv`. SHA-256 values are in `station_run/manifest.json`, re-checked 2026-11-16.
- 6 example PNG, `outputs/phone-captures/gpu-examples-20261113/`, matching `INPUT_RECEIPT.json`.
- Official template `(공통)포스터A0양식_2026.pptx`, SHA-256 `dd8a794f…ed27ed`, unchanged. The poster was built from a copy.

## Commands and status

| step | command | status |
| --- | --- | --- |
| Final station run | `run_phone_station_compare.py --input outputs/phone-captures/20261115 --recipe outputs/phone-station-20261115-inputs/recipe.json --plan outputs/phone-station-20261115-inputs/plan.json --output outputs/phone-station-20261116-final --kind real --assets-root . --device cuda` | COMPLETE at `7b868a3`, 423 s on battery. Copied to `station_run/` |
| Earlier final-path run | same, output `outputs/phone-station-20261115-final` at `6748c95` | COMPLETE. Identical states, scores and photo uses to `7b868a3` (112 rows). Its time (633 s) overlapped the full test run |
| Registration range | `characterize_phone_registration.py --output outputs/final-delivery-20261115/registration_range/run` | COMPLETE (synthetic), at `59db971` (same code as `7b868a3`) |
| Figures | `PYTHONPATH=<phone>/src python outputs/final-delivery-20261115/poster_work/make_figures.py` | COMPLETE, 7 PNG and `figure_sources.json` |
| Poster | `make_poster_spec.py`, then `build_poster.ps1` | COMPLETE: one page, 841 × 1189 mm, 31 shapes, 0 overlaps, 0 outside the page |
| UNO | `replay_phone_station_uno.py --events station_run/station_events.jsonl --fake` | fake serial: 57 frames. Hardware not connected or tested |

## Checks

| check | source | result | log |
| --- | --- | --- | --- |
| Full pytest | `6748c95` | 696 passed, 4 skipped, 793.8 s | `logs/pytest_full_6748c95.txt` |
| Phone-related pytest (station, capture, inspection station, team return) | `7b868a3` | 49 passed, 339.1 s | `logs/pytest_phone_related_7b868a3.txt` |
| CPU smoke | `7b868a3` | passed, 2 result rows, exit 0 | `logs/cpu_smoke_7b868a3.txt` |
| CPU smoke (earlier) | `5839caa` | passed, 2 result rows (reported to the user; no log file was kept) | — |
| Full pytest (earlier) | `5839caa` | 692 passed, 4 skipped | session output only |

The full suite was not re-run at `7b868a3` or `59db971`.
- `7b868a3` changed one timing block and one test line.
- `59db971` only adds files under `tools/`.

## What this run does not contain

New evaluation photos, human legibility records, measured capture time, UNO hardware, and the bank-domain return (owned by another member). See `FINAL_REPORT.md` §9.
