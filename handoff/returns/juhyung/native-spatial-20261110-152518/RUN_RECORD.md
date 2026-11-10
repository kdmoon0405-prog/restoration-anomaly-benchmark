# Run record — native-spatial-20261110-152518 (status COMPLETE)

- **What:** exploratory spatial descriptors for the fixed 9 selected PCB anomaly boards × {clean, bicubic_x4, swinir_x4} = 27 native maps. These are selected cases, not a population estimate.
- **Analysis source:** `handoff/juhyung@1e6c6bcd0e59ed91c6c3e6eb0e078f8d75b8bf39`. It ran from a clean delivery worktree `juhyung-handoff-20261110-152518` (branch `return-juhyung-20261110-152518`).
  - Submodules: `patchcore-inspection@fcaa92f`, `SwinIR@6545850`, initialized with the documented CRLF/LFS-skip command.
  - Script/module SHA-256 are in `manifest.json` `source_sha256`.
- **Python:** the existing GPU host venv `restoration-anomaly-benchmark/.venv`, Python 3.11.2.
- **Command:** `analyze_pcb_selected_maps.py --maps-root <gpuRoot>/outputs/pcb-full-cohort/pcb-full-cohort-20261101-a --metadata-root <delivery>/handoff/metadata --data-root <gpuRoot>/data/external/VisA --output <gpuRoot>/outputs/native-spatial-20261110-152518`
- **Inputs:**
  - 8 metadata files from `handoff/metadata/`: SHA-256 and bytes verified against `handoff/INPUT_FILES.json` (8/8).
  - 27 raw maps from the original raw run: 1070×1404 float32, SHA-256 per `input_receipts.json`.
  - VisA RGB/GT from the existing local path.
  - Raw-run provenance: `source_commit` `54cf3c7`, `source_worktree_dirty=true`, recorded as-is.
- **Memory:** the fixed `_budget` guard was kept and passed on this host. The plan was 0.42 GB per board plus the 2 GiB reserve, with about 20 GB available. This is a plan, not a measured peak. The earlier CPU-host attempt was BLOCKED_MEMORY.
- **Timing:** 15:26:08–15:26:35 KST (27 s), 2026-11-10.
- **GT use:** post-hoc descriptors and figures only. No threshold, model or selection change.
- **Figures:** the PNGs were opened and checked (cases 00, 04, 06). Each has one shared normalized colour scale per sample, GT components and fixed tile-boundary adjacency.
- **Interpretation:** see `analysis/image_score_diagnosis/ADDENDUM_20261110.md` §E on `exp/realistic-noise-v2-juhyung@40d57dd`. It is also returned as run `diagnosis-addendum-20261110`.

## Private artifacts (kept local, not in this return)

The case PNGs contain RGB and GT, so they are not delivered. They are available on request through the private channel.

| file | size / mode | SHA-256 |
| --- | --- | --- |
| case-00.png | 2080×1120 RGBA | ead46c262eb7ff46f8b4ea4caa7e0d9c9bc4da407ccb8475b8183af7cb699b08 |
| case-01.png | 2080×1120 RGBA | c11b2cde4e80d08c43a5493d38e653a7cfb7d840d7082fb2983d4fdd803f2d72 |
| case-02.png | 2080×1120 RGBA | f76fd72415f03a6f1f5fc4e262a414e16aa110633c035d3453123e31b05ef37f |
| case-03.png | 2080×1120 RGBA | 316ea11e4f6ff698b4592834b8db62d79f1bf284d71f850f6cc4fede0571d34d |
| case-04.png | 2080×1120 RGBA | 8b6f6263f91ab8e8bb9f35a0417eedff9245b1dcd7c80f59a142b6f46160d78a |
| case-05.png | 2080×1120 RGBA | f42652def7700046be6f909f39a09b131bb1b5a7f339535cfa4769a3e9b22272 |
| case-06.png | 2080×1120 RGBA | e6902c3dc99b5a2034e1b283fd3b45dd458b659c6c587e26a565b75e90e5d0e8 |
| case-07.png | 2080×1120 RGBA | 474ba86602e219cfd10f257876b2d5170cfb1d7f8e7a5519d59e0b6277e9c778 |
| case-08.png | 2080×1120 RGBA | 9c2742774af9dbd3f429994182b89643e7fafc47b8750675acbeee8cad5abef3 |

The raw maps were delivered on 2026-11-09 in `pcb-native-maps-20261109.zip` (SHA-256 `e0bad0bef94092699b26c3a5c5dcbd354be9c2621babf720084bea7f0a5fad70`).
