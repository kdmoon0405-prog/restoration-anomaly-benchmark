# Screw selected-case NN-distance execution record

Base commit: `9f78e9c6c1a295e29bd832112ca41156a39f070e` (`exp/hazelnut-analysis`)
Work branch: `exp/screw-selected-nn`

## Environment

- GPU: `NVIDIA GeForce MX570 A`
- CUDA (driver): 12.6
- PyTorch: `2.14.0+cu126`
- PatchCore source commit: `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`
- SwinIR x4 checkpoint SHA256: `09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e`

## Command

```powershell
.venv\Scripts\python.exe -X utf8 scripts\analyze_patchcore_nn_selected.py --run-dir outputs\legacy-patchcore\screw-full320-test160 --model-dir checkpoints\legacy-patchcore\screw-seed11-train320 --data-root data\external\MVTecAD --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --selected-cases analysis\screw\selected_mechanism_cases.csv --output-dir analysis\screw --device cuda
```

## Fix applied before this ran on CUDA

`scripts/analyze_patchcore_nn_selected.py` called `model._embed()` directly with an image tensor that was never moved to the resolved device. `PatchCore._embed` does not move its input internally (unlike the public `PatchCore.predict`, which does), so `--device cuda` failed with a device-mismatch `RuntimeError` on the first case. Fixed by moving the tensor to `device` at the call site before `_patch_distances`. No change to model architecture, preprocessing, thresholds, or case selection.

## Selected sample list

Source: `analysis/screw/selected_mechanism_cases.csv` (3 suppression + 3 success control; no geometry candidates in the frozen Screw taxonomy).

- suppression: `screw/test/thread_side/019.png`
- suppression: `screw/test/thread_side/010.png`
- suppression: `screw/test/scratch_head/005.png`
- success_control: `screw/test/manipulated_front/023.png`
- success_control: `screw/test/scratch_neck/000.png`
- success_control: `screw/test/scratch_neck/006.png`

## Runtime

Per-case, per-variant wall time (backbone + SwinIR + FAISS exact search on the 320-image bank):

| Sample | bicubic_x4 | swinir_x4 |
| --- | ---: | ---: |
| thread_side/019 | 3.0s | 2.8s |
| thread_side/010 | 2.3s | 2.3s |
| scratch_head/005 | 2.6s | 2.3s |
| manipulated_front/023 | 2.4s | 2.2s |
| scratch_neck/000 | 2.6s | 2.8s |
| scratch_neck/006 | 3.0s | 2.7s |

Total measured inference time: 31.9s across 6 cases x 2 variants. Peak VRAM was not separately profiled for this selected-case run (no profiler was attached, to avoid changing the measured environment); the full 320-train/160-test Screw run on the same GPU used well under the 4096 MiB budget (see `outputs/legacy-patchcore/screw-full320-test160/results.json`).

## Map validation (Phase 4)

Each recomputed Bicubic/SwinIR anomaly map was compared against its stored `screw-full320-test160` NPZ map before any distance was recorded. All 6 cases x 2 variants (12 checks) passed with max absolute error `0.0` (script tolerance: `rtol=1e-5, atol=1e-4`).
