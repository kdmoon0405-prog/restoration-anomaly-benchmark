# Hazelnut restoration-endpoint pilot execution record

Recorded: 2026-09-29, on receipt of the artifact. The original execution timestamp and exact shell invocation are not embedded in the artifact.

## Source and validation

- Executor identified in the handoff: 심주형 (Shim Juhyung). Source ZIP: `hazelnut-pilot25-gpu.zip`, SHA-256 `cab69ad9b9ad4b54177ff8cdb575fdb5244f13aa68a68006cc83fe4a222e0d46`.
- Run ID: `hazelnut-pilot25-gpu`; dataset/category: MVTec AD Hazelnut. The raw ZIP and extracted folder are kept locally beside `research_code/` under DesignProject; the executor/team should retain another archive copy. These locations are not part of Git.
- The archive contains 179 files, including 170 image files, four prediction NPZs, and five small CSV/JSON files. Every file in the supplied extracted folder matches the same ZIP entry byte-for-byte; there are no missing, mismatched, or extra files.
- Source `results.json` SHA-256: `c1c3189604916665639db57568a4be4b078bdb9a000cf839cc3cedf2464669b8`. The tracked copy has only two executor-local absolute path values (`manifest`, `detector.model_dir`) changed to repository-relative paths. Its SHA-256 is `1d71d4e435be3a953b8f78fbad5fd1a28b0644105d88f54fa0305ae366e2352b`. No metric, setting, count, or source hash was changed. The four tracked CSVs are byte-identical to the ZIP. All raw/tracked hashes are in [`results/RAW_ARTIFACT_HASHES.csv`](results/RAW_ARTIFACT_HASHES.csv).
- Saved CSV rows: summary 4 variants; per-image 25×4=100; Bicubic-relative taxonomy 20×3=60; direct endpoint pair 25. Each of four NPZs has 25 labels/scores and 25×224×224 masks/maps. Labels and masks match exactly across all four variants; scores/maps are finite. Per-image scores, summary means, endpoint deltas, and taxonomy signs agree with the saved text outputs.

## Frozen execution provenance

| Field | Recorded value / evidence |
| --- | --- |
| Branch | `exp/restoration-objective-study` (handoff; not embedded in JSON) |
| Runner source commit | `95d097799c10135a982dbddf91f97b71e3ca29e6` (`results.json`) |
| Device | requested=`cuda`, actual=`cuda`, available=`true`, `NVIDIA GeForce MX570 A` (`results.json`) |
| PyTorch / CUDA build version | Not recorded in the received runner artifact; not inferred from GPU name |
| PatchCore | source `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`; `fit_performed=false`; 391 normal train paths; CPU exact FAISS |
| Frozen bank SHA-256 | `patchcore_params.pkl`: `7c2728899e9e4aeca619d5c6f24ad47456c1603cc16e4c846a80f002c6ddc8b4`; `nnscorer_search_index.faiss`: `e665e08ac3d108ae095566df7baf7e966561333fdf50a6d85c6f5d77bfc3f9b4` |
| Manifest SHA-256 | `4d3b23548b5add0f067bec44330062870cde00a1521b9680198744f32bbf3603` (matches the tracked 25-image manifest) |
| BasicSR / SwinIR / ESRGAN source commits | `8d56e3a045f9fb3e1d8872f92ee4a4f07f886b0a` / `6545850fbf8df298df73d81f3e8cba638787c8bd` / `73e9b634cf987f5996ac2dd33f4050922398a921` |
| SwinIR / RRDB-PSNR / RRDB-ESRGAN checkpoint SHA-256 | `09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e` / `f372b59f22929e1bc83fa58d78215c96f976de3b2eaeee736da1b348913da6cc` / `65fece06e1ccb48853242aa972bdf00ad07a7dd8938d2dcbdf4221b59f6372ce` |

The local archived 391-normal bank files independently hash to the same two values. The ZIP does not contain the GPU machine's bank, so actual reuse is supported by the committed runner's fail-fast hash checks plus its saved metadata, rather than by rehashing that remote file here. The artifact records no source dirty-tree flag. The handoff reports no code, model, checkpoint, manifest, or experiment-parameter change after the initial checkout repair; that incident cannot be independently reconstructed from the final ZIP.

## Command and runtime

The original shell command was not preserved. This is the equivalent portable runner invocation consistent with recorded `cuda` and LPIPS output, **not a claim that the executor typed these exact bytes**:

```powershell
.venv\Scripts\python -X utf8 scripts\run_restoration_objective_pilot.py --device cuda --with-lpips --output-dir outputs\restoration-objective\hazelnut-pilot25-gpu
```

Saved per-image stage times summed across 25 images (restoration + detector):

| Variant | Recorded stage seconds |
| --- | ---: |
| Bicubic x4 | 79.31884129950777 |
| SwinIR-S x4 | 88.2367541998392 |
| RRDB-PSNR x4 | 87.01114970038178 |
| RRDB-ESRGAN x4 | 87.65748440031894 |
| **Sum** | **342.2242296000477** |

These are sums of runner stage fields, not end-to-end wall time; they exclude setup, model/bank loading, LPIPS computation, file writing, and transfer. The handoff separately reports about 57 seconds for the first AlexNet LPIPS weight download; the saved artifact has no independent download-timing field.

## Reported checkout incident

The teammate reports an initial `FileNotFoundError: BasicSR MATLAB resize implementation not found` after an interrupted `git submodule update` left the BasicSR working-tree checkout incomplete. They repaired that submodule locally with `git reset --hard HEAD` inside BasicSR and reran the unchanged pinned source. This was a checkout repair, not a research-protocol revision. The final artifact records the pinned BasicSR source commit; the first failed attempt and repair command are handoff information, not independently proven by the final ZIP.

The source ZIP, four raw NPZs, all RGB images, model bank, checkpoints, LPIPS weights, and dataset stay in the local/team archive. None is Git-tracked. No new inference or tuning was run while recording these results.
