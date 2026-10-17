# Frozen Branch B stage profiling

This is timing/development tooling, not a new research result. The negative map-gating feasibility, full110 B/B-uncertain, prior partial pilot10, scientific metrics and source artifacts are unchanged. No candidate/weight/threshold search, fit, recalibration or new model was performed.

## Execution and provenance

- Protocol stored before model loading/inference: [PROTOCOL.json](PROTOCOL.json); input hashes: [INPUT_MANIFEST.json](INPUT_MANIFEST.json).
- Original PatchCore source `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`; bank `checkpoints/fusion-patchcore/hazelnut-seed11-train313`; original SwinIR checkpoint and preprocessing recorded in protocol. The frozen-bank loader has no fit fallback. Existing cached backbone/checkpoint only; downloads blocked.
- Actual device `cpu`; CUDA available `False`; Torch threads 4, CPU FAISS threads 4, batch 1. CUDA was not exercised. CPU: Intel(R) Core(TM) Ultra 5 125H; see optional [HOST_RESOURCES.json](HOST_RESOURCES.json) for post-run OS inventory, not a runtime resource trace. This was not an isolated benchmark host.
- 10 unique images/path: original pilot10 filenames, not a newly selected performance subset. Fixed warmup uses 2 images on both paths. Instrumented repeats 2; separate original/uninstrumented repeat 1. Repeats are repeated timings, not additional independent samples.
- Preparation 21.217 s; bank/model load 7.969 s; warmup 23.374 s. Measured inference-phase wall 701.134 s versus 900 s budget. This wall clock conservatively includes anchor checks and intermediate CSV writes, despite the protocol's intended exclusion of writes. File IO was not separately timed. It is not pure model time.
- 64 normalized saved-anchor comparisons, all passed: map max absolute difference 0.0, score max difference 0.0. Includes warmup, instrumented and uninstrumented calls. Raw scores/maps are normalized with the existing calibration solely for parity; no new dataset metric is calculated. `evaluation_seconds=0` means no research metric evaluation, not zero parity-check cost.

## Measured stages

| Phase / path | Stage | N / unique / repeats | Mean s | Median s | Min..max s |
| --- | --- | --- | ---: | ---: | ---: |
| instrumented/degraded | image_preprocessing_seconds | 20 / 10 / 2 | 0.098707 | 0.091404 | 0.042456..0.203769 |
| instrumented/degraded | sr_seconds | 20 / 10 / 2 | 0.000000 | 0.000000 | 0.000000..0.000000 |
| instrumented/degraded | tensor_preprocessing_seconds | 20 / 10 / 2 | 0.005361 | 0.002047 | 0.001010..0.046141 |
| instrumented/degraded | backbone_embedding_seconds | 20 / 10 / 2 | 0.722982 | 0.529756 | 0.354524..1.640303 |
| instrumented/degraded | feature_detach_cpu_numpy_seconds | 20 / 10 / 2 | 0.011181 | 0.011277 | 0.003114..0.025579 |
| instrumented/degraded | faiss_search_seconds | 20 / 10 / 2 | 8.001780 | 5.361587 | 4.492007..18.841655 |
| instrumented/degraded | score_map_postprocessing_seconds | 20 / 10 / 2 | 0.004623 | 0.004715 | 0.001555..0.010840 |
| instrumented/degraded | detector_glue_seconds | 20 / 10 / 2 | 0.009081 | 0.007975 | 0.005315..0.030555 |
| instrumented/degraded | detector_total_seconds | 20 / 10 / 2 | 8.749647 | 5.944436 | 5.018870..20.031417 |
| instrumented/degraded | end_to_end_seconds | 20 / 10 / 2 | 8.854309 | 6.037217 | 5.097926..20.127781 |
| instrumented/restored | image_preprocessing_seconds | 20 / 10 / 2 | 0.098707 | 0.091404 | 0.042456..0.203769 |
| instrumented/restored | sr_seconds | 20 / 10 / 2 | 1.276684 | 1.326358 | 0.492010..2.098510 |
| instrumented/restored | tensor_preprocessing_seconds | 20 / 10 / 2 | 0.001719 | 0.001624 | 0.000958..0.004003 |
| instrumented/restored | backbone_embedding_seconds | 20 / 10 / 2 | 0.743846 | 0.523164 | 0.387336..2.821506 |
| instrumented/restored | feature_detach_cpu_numpy_seconds | 20 / 10 / 2 | 0.008891 | 0.010383 | 0.003038..0.014741 |
| instrumented/restored | faiss_search_seconds | 20 / 10 / 2 | 7.539598 | 5.145503 | 4.423372..14.685631 |
| instrumented/restored | score_map_postprocessing_seconds | 20 / 10 / 2 | 0.005027 | 0.004628 | 0.001628..0.009346 |
| instrumented/restored | detector_glue_seconds | 20 / 10 / 2 | 0.007703 | 0.007787 | 0.004241..0.015179 |
| instrumented/restored | detector_total_seconds | 20 / 10 / 2 | 8.305065 | 5.689218 | 4.953888..17.194350 |
| instrumented/restored | end_to_end_seconds | 20 / 10 / 2 | 9.682190 | 7.064753 | 6.323270..18.634239 |
| end_to_end/degraded | image_preprocessing_seconds | 10 / 10 / 1 | 0.117840 | 0.123809 | 0.061569..0.207594 |
| end_to_end/degraded | sr_seconds | 10 / 10 / 1 | 0.000000 | 0.000000 | 0.000000..0.000000 |
| end_to_end/degraded | tensor_preprocessing_seconds | 10 / 10 / 1 | 0.004811 | 0.002728 | 0.000923..0.021978 |
| end_to_end/degraded | detector_total_seconds | 10 / 10 / 1 | 14.354897 | 14.013607 | 6.250859..30.637708 |
| end_to_end/degraded | end_to_end_seconds | 10 / 10 / 1 | 14.478164 | 14.174856 | 6.313636..30.748736 |
| end_to_end/restored | image_preprocessing_seconds | 10 / 10 / 1 | 0.117840 | 0.123809 | 0.061569..0.207594 |
| end_to_end/restored | sr_seconds | 10 / 10 / 1 | 1.712624 | 1.701293 | 0.446976..3.037026 |
| end_to_end/restored | tensor_preprocessing_seconds | 10 / 10 / 1 | 0.004666 | 0.001863 | 0.001124..0.027771 |
| end_to_end/restored | detector_total_seconds | 10 / 10 / 1 | 14.691641 | 13.006149 | 7.218585..31.427274 |
| end_to_end/restored | end_to_end_seconds | 10 / 10 / 1 | 16.526787 | 14.054223 | 8.086463..34.298473 |

Code: `scripts/profile_patchcore_stages.py::instrument/run_pair`, original `PatchCore._embed/_predict`, CPU `anomaly_scorer.nn_method.run`, `patch_maker.unpatch_scores/score`, and `anomaly_segmentor.convert_to_segmentation`.

Backbone+embedding uses the original `_embed(detach=False)`, then the original per-row detach/CPU/NumPy conversion. On CPU there is no measured GPU-to-CPU transfer; the field names preserve the future CUDA boundary. FAISS remains CPU exact IndexFlatL2. Score/map postprocessing is the non-overlapping sum of the original three functions. Detector glue is parent minus child times, including input placement/packing/scorer reduction/reshape and hook overhead. Parent detector/E2E times must NOT be added to child stages. SR timing includes its adapter conversion, not an invented separate internal transfer measurement. CUDA helper synchronization is implemented but unvalidated on hardware here.

RGB decode/canonical/degradation preprocessing is shared once per image pair and attributed to both path latencies. Do not sum this twice to reconstruct wall time. E2E excludes parity checks/writes/load/warmup. The later uninstrumented pass is slower and the repeats drift; the data do NOT identify instrumentation overhead or its causal direction. No cause (thermal, contention, memory) was measured. No production FPS/p95/speedup claim follows.

FAISS is 91.45% of instrumented degraded detector mean time. CPU index float32 vector storage estimate: 1,005,125,632 bytes (245,392 x 1024); this is not process peak RSS. Peak CPU RSS was not recorded. CUDA peak allocated/reserved are null because CUDA was unavailable, not zero GPU memory.

## Conditional SR cost simulation only

Use the separate original end-to-end pass, with raw/restored detector+tensor preprocessing and SR from the same phase. Shared RGB preprocessing is excluded. `T_always = T_SR + T_det_rest`; `T_conditional = T_det_raw + p*(T_SR + T_det_rest)`. No trigger was executed or accuracy/safety equivalence established.

| Hypothetical SR call fraction p | Always SR s | Conditional s | Savings s |
| ---: | ---: | ---: | ---: |
| 0.00 | 16.408931 | 14.359708 | 2.049223 |
| 0.25 | 16.408931 | 18.461941 | -2.053009 |
| 0.50 | 16.408931 | 22.564174 | -6.155242 |
| 0.75 | 16.408931 | 26.666407 | -10.257475 |
| 1.00 | 16.408931 | 30.768639 | -14.359708 |

Strictly faster under this model requires `p < 0.124885` (12.49%). This is a hypothetical break-even, NOT measured savings or an available deployable gate. The observed negative map-gating result is not reversed by a cost simulation. The historical full110 3563.561 s wall clock covers different scope/variants and is not a per-image timing reference here.

Only two potential future optimization studies are identified, not implemented: (1) bank/coreset size versus accuracy/localization validation, because CPU exact search dominates; (2) exact-search batching/cache/memory benchmark with prediction parity, without changing search semantics. GPU backbone timing alone cannot establish an end-to-end gain while FAISS remains on CPU.

## Read-only demo and next boundary

See [demo instructions](../../../demo_results/README.md) and [DEMO_VERIFICATION.md](DEMO_VERIFICATION.md). Uses existing 110-image maps/CSV only, historical RGB on 10 verified filenames, unavailable otherwise. Candidate maps have no new RGB/image-quality metrics. Normal per-image AU-PRO is null; GT is evaluation overlay only. Browser screen verification remains unavailable without a connected browser.

See [PCB_READINESS.md](PCB_READINESS.md). PCB recommendation is file/split readiness only, not independent validation or permission to run a new experiment. No PCB/GPU inference occurred. At most: inspect the local demo, confirm teammate PCB prior usage, and separately authorize/freeze a baseline-transfer study if desired. Capsule remains untouched.
