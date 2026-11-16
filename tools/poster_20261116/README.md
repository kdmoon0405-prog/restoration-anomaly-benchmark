# A0 poster build (2026-11-16)

Scripts that produced `poster_final.pptx` / `.pdf` and `poster_figures/` in the private delivery `outputs/final-delivery-20261115/`.
They read stored CSV/JSON and the private photos from the GPU checkout; no data is stored here.

1. `make_figures.py` — run from the GPU checkout root with `PYTHONPATH=<phone worktree>/src`. Writes the seven figures and
   `figure_sources.json` (source of every number; the photo figure re-checks its scores against the stored `inspections.csv`).
2. `make_poster_spec.py` — text and layout in points on the official A0 template, slide 3 -> `poster_spec.json`.
3. `build_poster.ps1` — PowerPoint COM: opens a copy of the official template, keeps slide 3, places text, figures and the
   condition table, saves PPTX and PDF, and writes `poster_layout.json` for the overlap / out-of-page check.

The scripts expect to sit in `outputs/final-delivery-20261115/poster_work/` next to `template_copy.pptx` (a copy of the
official template, which is private and not in Git). Figures and text were written by Claude Fable 5.2; these files were
committed by Claude Opus 5.5 at the user's request.
