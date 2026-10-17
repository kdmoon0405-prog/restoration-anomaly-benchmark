# PCB full-FOV 224 draft geometry

Status: **BLOCKED_GEOMETRY**. One pre-fixed draft, not a method search. No model, degradation, fitting, calibration or anomaly metric was executed.

Official split: {'fit': {'normal': 721, 'anomaly': 0}, 'calibration': {'normal': 180, 'anomaly': 0}, 'test': {'normal': 100, 'anomaly': 100}}. Exact reference paths and CSV SHA matched; no partition overlap. Byte-identical groups: 0 (not a perceptual duplicate check). INPUTS.csv stores all 1101 portable paths, labels, source sizes and input/mask hashes; MANIFEST.json references its hash and coordinate metadata. PCB bank/calibration for this geometry do not exist. Teammate past use is unconfirmed.

## Geometry and actual checks

`pcb_full_frame_224_bilinear_nearest_v0_1`: entire source field resized directly to 224x224, RGB bilinear, binary GT nearest. No crop/padding. Non-square images are anisotropically transformed. Metadata records edge and pixel-center affine/inverse coordinates. Future x4 is 224->56->224, NOT executed here.

- Input image transforms checked: 1101; anomalous GT checked: 100.
- Input/size/alignment errors: 0.
- Empty target anomaly masks: 0.
- Original-resolution 8-connected GT components: 324; represented 305, lost 19 across 9 images.
- Lost component original areas: min 1, max 28 source pixels. No arbitrary small-defect cutoff was used.

Original GT IDs are resized with the SAME nearest sampler; IDs>0 must exactly match transformed binary GT. These are connected regions in annotation, not physical defect counts. Target connected-component counts alone are not an ID survival check because regions can merge/split. Source areas and target sample counts have different units; no cross-resolution pixel-count retention ratio is reported. Presence does not prove shape/fidelity preservation.

Historical crop audit has 9 images losing GT pixels and 4 resized-GT components lost across 3 images. Its reference is the resized 335x256 raster, while this audit references ORIGINAL component IDs. These numbers are NOT a before/after improvement comparison. Old CSV and scientific results are unchanged.

## Boundary

Full FOV is not preservation of every small annotation. The frozen rule blocks any original component disappearing, any empty/full anomalous mask or alignment error. This is a structural guard, not an anomaly-performance threshold. If blocked, no pilot is authorized: describe higher-resolution full-FOV or coverage-defined tiling as future options only; do not search resolutions, drop cases, dilate GT or change sampling to force a pass. If the guard passes, a separately frozen VisA runner/bank/calibration/checkpoint/hardware plan is still required before an actual pilot. Capsule/negative gates/full110 B/B-uncertain stay unchanged.

Figures are local-only under figures/. The selection rule was stored before audit: two maximum lost-source-area examples and one lexical no-loss control, with lexical/ID ties. Green contours are GT; source zooms are explanatory only, not adaptive model inputs. They are not population estimates.

Reproduce CPU audit from repository root with a NEW run-id:

```powershell
.venv\Scripts\python scripts/prepare_pcb_geometry.py --run-id pcb2-full-frame224-replay
.venv\Scripts\python -m pytest -q tests/test_pcb_geometry.py
```

Existing output is never overwritten. Protocol/input/source hashes are preserved. No alternative geometry or GPU command is generated automatically.
