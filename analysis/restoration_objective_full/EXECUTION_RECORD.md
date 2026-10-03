# Full Hazelnut restoration-endpoint (full110) execution record

Executed directly in this checkout on 2026-10-02 on the NVIDIA machine, from preregistration commit `fddad881276da120ffcce1362ce062f85ea4759a` on `exp/restoration-objective-study`. No code change preceded this run; the working tree was clean (only the pre-existing personal `experiment.ipynb` and an untracked `third_party/SwinIR` file were present, both unrelated to this experiment).

## Command

```powershell
.venv\Scripts\python.exe -X utf8 scripts\run_restoration_objective_pilot.py --cohort full110 --device cuda --with-lpips --output-dir outputs\restoration-objective\hazelnut-full110-gpu
```

Preceded by the required preflight, both passed:

```powershell
.venv\Scripts\python.exe -X utf8 scripts\create_restoration_objective_manifest.py --cohort full110 --check   # Validated 110 frozen images
.venv\Scripts\python.exe -m pytest -q                                                                          # 121 passed
```

## Frozen execution provenance (from the saved `results.json`)

| Field | Recorded value |
| --- | --- |
| Source commit | `fddad881276da120ffcce1362ce062f85ea4759a` |
| Cohort / manifest SHA-256 | `full110` / `2ddb62748c750b3e4fae2b4b0b0cb4f3c354fd02faac74c95117afe1b3e116cc` |
| Device | requested=`cuda`, actual=`cuda`, available=`true`, GPU=`NVIDIA GeForce MX570 A` |
| Python / PyTorch / torch CUDA build / cuDNN | `3.11.2` / `2.14.0+cu126` / `12.6` / `91002` |
| LPIPS package version | `0.1.4` |
| PatchCore | source `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`; `fit_performed=false`; 391 normal train paths; CPU exact FAISS |
| Frozen bank SHA-256 | `patchcore_params.pkl`=`7c2728899e9e4aeca619d5c6f24ad47456c1603cc16e4c846a80f002c6ddc8b4`; `nnscorer_search_index.faiss`=`e665e08ac3d108ae095566df7baf7e966561333fdf50a6d85c6f5d77bfc3f9b4` |
| BasicSR / SwinIR / ESRGAN source commits | `8d56e3a045f9fb3e1d8872f92ee4a4f07f886b0a` / `6545850fbf8df298df73d81f3e8cba638787c8bd` / `73e9b634cf987f5996ac2dd33f4050922398a921` |
| SwinIR / RRDB-PSNR / RRDB-ESRGAN checkpoint SHA-256 | `09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e` / `f372b59f22929e1bc83fa58d78215c96f976de3b2eaeee736da1b348913da6cc` / `65fece06e1ccb48853242aa972bdf00ad07a7dd8938d2dcbdf4221b59f6372ce` |
| `sample_count` / normal / anomaly | `110` / `40` / `70` (all four variants) |
| F1 / threshold | null for all variants (no calibration performed) |

All of the above were independently re-verified against the local submodules/checkpoints/bank (not only trusted from the JSON): submodule `rev-parse` for all four, `Get-FileHash`/`sha256sum` for all three checkpoints and both bank artifacts, and a fresh `sha256sum` of the manifest.

## Output artifact hashes (independently recomputed, not only read from `results.json`)

| File | SHA-256 (recomputed == recorded) |
| --- | --- |
| `summary.csv` | `f5ddf2b69a5501ae98aba4a60f5bb3d5f994d5b7fdebabd8b3bcfb331fbf2789` |
| `per_image.csv` | `2072af5d43ef40f99538ed0d51c58ed363085fc285a0bf24b365b478f66df2f9` |
| `regression_taxonomy.csv` | `bee99e80c022b347fbe353816ee1d99636771232502b662b3bac6a65accda7a1` |
| `objective_pair_per_image.csv` | `0cb552dd6d55de65634b768f1de5ec5081d2cce6139c9c5601ddfde802d4a5c6` |
| `bicubic_x4_predictions.npz` | `7612b5d523e2e91af5dbdbf6604ebe7f6f3484eb6fcb8b79c55bedbbfe0c5ead` |
| `swinir_x4_predictions.npz` | `879e78f9d96d1e061a5bcaadefb51f54bfe149f03f0c97129ff5b92cbbefde8d` |
| `rrdb_psnr_x4_predictions.npz` | `324b4e56652ac9cb01263334d42f9c3f61f1bf80e79614b87f6866502db32c2d` |
| `rrdb_esrgan_x4_predictions.npz` | `a8a758cec21e3737b5376553cf806c6375682a46aa5cc49aa6477b3287cfc2b7` |

All 8 matched the `artifact_sha256` block recorded by the runner. All four NPZs additionally hold matching labels/masks across variants, finite scores/maps, and shapes `(110,)`/`(110,224,224)`.

## Runtime

End-to-end `wall_clock_seconds` (main entry through setup, inference, evaluation, file writes, and artifact hashing): **3563.561 s (~59.4 minutes)**.

Saved per-variant stage seconds (mean restoration + mean detector, ×110 images):

| Variant | Mean restoration s | Mean detector s | ×110 subtotal |
| --- | ---: | ---: | ---: |
| bicubic_x4 | 0.0000 | 7.2490 | 797.4 |
| swinir_x4 | 0.3724 | 7.4804 | 863.6 |
| rrdb_psnr_x4 | 0.1466 | 7.1459 | 802.2 |
| rrdb_esrgan_x4 | 0.1427 | 7.3167 | 820.8 |
| **Sum of timed stages** | | | **3284.0** |

The full110 timed-stage sum is approximately `3283.923 s`, compared with `342.224 s` for pilot25 under the same timing scope: approximately `9.596×`. The image-count ratio is `4.4×`, so the per-image timed-stage cost is approximately `2.181×` higher. The current records do not establish why that per-image cost increased. Dividing full110 wall-clock time (`3563.561 s`) by pilot25 timed-stage time gives approximately `10.413×`, but these are different timing scopes and that ratio is not evidence of performance scaling.

## Analysis step

```powershell
.venv\Scripts\python.exe -X utf8 scripts\analyze_restoration_endpoint_full.py --run-dir outputs\restoration-objective\hazelnut-full110-gpu --output-dir analysis\restoration_objective_full\derived
```

Ran once against the completed, verified run above; performed no model fitting, restoration inference, or checkpoint/threshold selection, per the frozen protocol. Final case: **B (B-uncertain)**; see `FULL_RESULT.md`.

## Path redaction note

`analysis/restoration_objective_full/derived/analysis_summary.json` as produced by the analysis script contained one personal local absolute path in its `source_run` field. The raw script output's SHA-256 was `e2d9ff443530e50dd91b50547f90015bfec18118eeab00367f59a7ae08416fb2`. The tracked copy has only that one string replaced with the relative path `outputs/restoration-objective/hazelnut-full110-gpu`; no other field, number, or key was changed, and this new hash is not presented as the raw script output's hash.

## Storage

The source ZIP equivalent (raw NPZs, all RGB images, model bank, checkpoints, LPIPS weights, dataset) stays local under `outputs/restoration-objective/hazelnut-full110-gpu/` and `checkpoints/`; none of it is Git-tracked. Only this record, `FULL_RESULT.md`, and the small derived CSV/JSON/PNG files under `analysis/restoration_objective_full/derived/` are candidates for commit.
