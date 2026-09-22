# Screw artifact provenance

Source archive: `screw-full320-test160.zip`

Archive SHA256: `DB6B7CAB2F356B4C48710E29A9C0D145957E9816BAB910AF50AB3F43A334B5D6`

Validated source run: `outputs/legacy-patchcore/screw-full320-test160/`

| File | SHA256 |
|---|---|
| `bicubic_x4_predictions.npz` | `00EAB7CF8F3119D7691FE958252666F7067C4281BC18BCEBF566B726933AB68B` |
| `clean_predictions.npz` | `C9046AA31A79D7EEDDBB0717D90BC0B15DFECD75FC982FF4D2DB901C350D8B52` |
| `per_image.csv` | `EE0C18322C76EFF528F90817FD3FD624EBECC21B084E4F33295BFC08DBEDC612` |
| `results.json` | `7991107A71863244379A832802EDD677FAA90B0D2833A2EC49BEE3E469803464` |
| `summary.csv` | `9F0087FDB538C4A5C2F9F271229492909405E6C524B919B8A14BA125C6E118AF` |
| `swinir_x4_predictions.npz` | `C020A02564543F64A5A7D323A91E52B59875E01D0C71F8CCA63A719940045258` |

The run records CUDA execution on `NVIDIA GeForce MX570 A`, 320 normal training images, 160 test images, seed 11, no calibration/F1 threshold, pinned PatchCore commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`, and SwinIR x4 checkpoint SHA256 `09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e`.

Validation passed for category/seed/device, the 320/160 path counts, empty calibration, null image/pixel F1 and thresholds, fixed detector/preprocessing settings, and all six required files. The three NPZ files each contain 160 labels/scores and 160x224x224 masks/maps. Labels and masks match exactly across variants; scores/maps are finite; `per_image.csv` contains one row per path/variant; and `summary.csv` agrees with `results.json` to stored precision.

The NPZ files remain ignored and are not committed. The small derived files under `analysis/screw/` are generated from these checksummed artifacts. The received archive does not contain the Screw PatchCore FAISS bank required for selected feature-distance analysis.
