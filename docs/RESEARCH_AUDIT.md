# Research and reproducibility audit

Audit date: 2026-09-22

Audited baseline: `b896e17` on `exp/hazelnut-analysis`

Scope: the frozen Hazelnut analyses, Branch A/B runners, cross-category analysis, reporting, device parity, and the planned Screw run. No model fit, restoration inference, metric recomputation, or new experiment was performed.

## Current design assessment

The current question is narrow enough for a graduation project: under a fixed x4 degradation/restoration condition, measure whether SwinIR changes PatchCore localization, then describe the images that regress. Hazelnut is the development category, Screw is the prespecified cross-category stress test, and Capsule remains the single untouched final validation category.

The saved Hazelnut result supports a category-specific observation only. Relative to Bicubic x4, SwinIR-S x4 changed pooled AU-PRO@0.3 from 0.8189099069 to 0.8434611914 and Pixel AUROC from 0.9839332526 to 0.9850919109. Of 70 anomalous images, 30 had lower per-image AU-PRO: 14 suppression patterns and 16 geometry candidates. These labels are post-hoc map-score patterns, not demonstrated causal mechanisms.

The five-point scalar-fusion feasibility analysis did not improve its prespecified primary metric. Alpha 0.00, restored-only, remained best. Fine weight search and adaptive gating are therefore not justified by the saved Hazelnut evidence. The per-image screening oracle has only 0.0036547778 mean AU-PRO headroom over restored-only, while the whole-map post-hoc selection result is worse on pooled AU-PRO. That oracle is GT-assisted and non-deployable.

## Research consistency review

The status records the issue found at the audited baseline. “Fixed” means the working tree contains the correction described here.

| Item | Status | Evidence and reason | Action |
|---|---|---|---|
| Primary metric matches the research question | OK | `EXPERIMENT_PROTOCOL_V0.2.md` fixes pooled AU-PRO@0.3; the analysis uses the shared `area_under_per_region_overlap()` implementation. | Keep fixed. |
| Hazelnut, Screw, and Capsule roles are consistent | stale | The protocol and decision log were consistent, but the GPU handoff still led with an old Bottle plan. | Fixed the current handoff and README sequence; retained Bottle text as historical. |
| Test-label leakage | OK | Branch A has no calibration/F1 threshold. Branch B calibration uses normal training images only. GT masks are used for post-hoc evaluation/taxonomy. | Do not tune on Screw or Capsule. |
| F1 threshold source | OK | Branch A records null F1/threshold; Branch B records calibration-derived thresholds. | Keep Branch A and Branch B claims separate. |
| Pooled and per-image metric distinction | OK | Pooled AU-PRO is the selection metric; per-image AU-PRO is used for paired regression descriptions. | Preserve the naming in tables and prose. |
| Causal terminology | stale | Earlier notes could be read as if feature-distance analysis established a cause. It did not. | Fixed the decision log: suppression/geometry are descriptive patterns only. |
| ROI-mean oracle interpretation | stale | The historical ROI-mean artifact is not a localization upper bound. | Current docs point to the proper GT-assisted post-hoc oracle; keep the old file historical. |
| “Strong failure” terminology | stale | Some progress/artifact text still presented 14 cases as the main regression set. The frozen taxonomy has 30 localization regressions. | Fixed current prose; `strong_failure_cases.csv` remains a named historical artifact. |
| Bootstrap interpretation | OK | Paired bootstrap is applied to paired image deltas and reported with its seed/resample count. | Do not interpret the selected qualitative cases as a population estimate. |
| AU-PRO implementation detail | OK | `max_fpr=0.3`, 200 thresholds, and the same implementation are reused across analyses. | Keep unchanged for Screw and Capsule. |
| Branch A/B comparability | OK | They answer different questions and use different training/calibration designs. Results are not silently pooled. | Report branch names with every result. |
| Screw rules frozen before seeing results | OK | Taxonomy, case ranking, metrics, and tie handling are already implemented and tested without Screw results. | Run the generic analyzer unchanged. |
| CPU/CUDA parity role | OK | Device parity checks execution consistency only; timing is kept separate from research metrics. | Use the configurable tolerance report after a CUDA smoke run. |
| Capsule as untouched final validation | risky | Repository records say Capsule is untouched, but this cannot prove that no team member inspected or tuned on it elsewhere. | Obtain one team confirmation before the final run and record it in the decision log. |

## Code and artifact correctness

| Item | Status | Evidence and reason | Action |
|---|---|---|---|
| Dataset ordering and pairing | OK | The dataset adapter sorts paths; predictions, labels, masks, and `test_paths` are validated for equal length and shape. | No change. |
| Branch B split replay | risky | `--split-json` previously accepted overlapping, duplicate, out-of-range, or differently ordered paths. | Fixed with index, count, disjointness, path-order, seed/category, and incompatible-limit checks. |
| Checkpoint identity before expensive work | risky | SwinIR SHA256 was recorded only after the run, so a wrong checkpoint could waste the entire run. | Fixed: validate the frozen x4 hash before fit/inference and reuse that digest in metadata. |
| PatchCore source identity | OK | The exact legacy source commit is checked. FAISS remains CPU `IndexFlatL2` exact search. | No change. |
| Cross-category configuration drift | risky | The generic analyzer previously accepted any superficially compatible legacy run. | Fixed: require the frozen source commit, seed, detector/preprocessing, SwinIR identity/hash, no calibration, and exact variants. |
| Reporting source consistency | risky | The reporter could combine a `summary.csv` with a disagreeing `results.json`. | Fixed: verify stored summary metrics and stored deltas before aggregation. |
| Device parity source consistency | risky | Two internally inconsistent runs could otherwise pass cross-device comparison. | Fixed: each run's `summary.csv` must first match its own `results.json`. |
| Labels and masks in parity checks | OK | Exact equality is required; scores/maps use reported configurable tolerance plus raw max/mean differences. | No change. |
| Output overwrite protection | OK | Long-run scripts reject existing non-empty output targets. | Preflight also checks this before Screw. |
| Stored Hazelnut prediction identity | OK | The three saved NPZ SHA256 values match `analysis/hazelnut/ARTIFACTS.md`. | Keep large raw artifacts external/ignored and retain hashes. |
| Reporting source portability | risky | The cross-category summary used by reporting existed only under ignored `outputs/`. | Fixed by promoting the already-generated JSON, unchanged, to `analysis/hazelnut/cross_category_summary.json`. |
| Windows/Linux paths | OK | Runtime paths use `pathlib`; CLI examples avoid hard-coded user paths. Stored source paths may use Windows separators as historical metadata. | No change. |

No numerical research semantics were changed. The code changes are input/provenance guards, fail-fast checkpoint validation, read-only preflight, and documentation corrections. Existing Hazelnut predictions and metrics were not regenerated.

## Performance audit

No additional performance refactor is warranted before the Screw run.

- PatchCore feature extraction and SwinIR run on the selected device; FAISS exact search stays on CPU by design.
- CUDA synchronization around measured sections is required for valid timing and should not be removed.
- Hashing the checkpoint is an integrity cost outside the research metric. It now occurs once and fails early.
- Repeated labels/masks in each NPZ consume space, but changing the artifact schema now would add migration and parity risk for little experimental benefit.
- Float conversions in evaluation are small compared with backbone inference and do not justify a pre-experiment rewrite.

## Reproducibility status

Pinned or recorded:

- branch and source commit;
- PatchCore source commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`;
- SwinIR submodule commit and x4 checkpoint SHA256;
- category, seed, paths, split, detector/preprocessing settings, variants, device metadata, and runtime;
- exact Hazelnut NPZ hashes and tracked derived summaries;
- fixed AU-PRO implementation and taxonomy;
- synthetic tests for split validation, artifact consistency, parity, and preflight.

Still external or unverified:

- a durable team-visible storage location for the large Hazelnut NPZ files is not recorded in the repository;
- the original Jihyuk notebook's mask-resize behavior has not been independently reconstructed, although this repository freezes nearest-neighbor mask resizing;
- real NVIDIA execution and CPU/CUDA numerical parity have not yet been observed;
- no Screw memory bank or Screw result artifact exists yet.

## GPU and Screw readiness

The repository, local Screw data, legacy PatchCore source, and SwinIR x4 checkpoint are ready for the frozen full run. The read-only preflight verifies actual dataset/mask counts instead of assuming them. The local dataset currently contains 320 normal training images and 160 test images: 41 normal and 119 anomalous across `manipulated_front`, `scratch_head`, `scratch_neck`, `thread_side`, and `thread_top`.

Local status is **BLOCKED for execution** because CUDA is unavailable on this machine. This is not a research-design blocker. The Screw model directory and output directory are absent, which is expected before fitting. On a clean NVIDIA checkout, run the preflight in `GPU_HANDOFF.md`; proceed only if it reports ready.

Frozen Screw rules:

- Branch A, seed 11, full train/test, no calibration or F1 threshold;
- exact PatchCore source and fixed detector/preprocessing settings;
- Bicubic x4 versus SwinIR-S x4 with the pinned checkpoint;
- pooled AU-PRO@0.3 primary; Pixel AUROC, Image AUROC, PSNR, and SSIM secondary;
- the Hazelnut regression taxonomy and deterministic selected-case rule unchanged;
- no fusion, threshold tuning, model selection, or new magnitude cutoff after seeing Screw;
- Screw is a stress test, not a development set.

## Claim boundaries

Supported now:

- on the frozen Hazelnut run, SwinIR improves average pooled localization and image quality relative to Bicubic x4;
- that average coexists with 30/70 anomalous-image localization regressions;
- the saved five-point scalar fusion grid does not improve its primary metric over restored-only;
- the 30 regressions can be reproducibly partitioned into 14 suppression patterns and 16 geometry candidates under the frozen definitions.

Not supported now:

- that restoration generally improves anomaly detection across categories or datasets;
- that SwinIR caused feature-space suppression or geometric distortion in a mechanistic sense;
- that defect size, morphology, or defect type is a general predictor of regression;
- that a deployable oracle/gating method improves the result;
- that selected qualitative or NN-distance cases estimate population effects;
- that Capsule confirms the conclusion, or that SurgClean is directly comparable to MVTec AD.

## Information-value rule for remaining work

1. Run Screw once under the frozen Branch A specification. Its value is whether the Hazelnut aggregate/regression pattern transfers to a different category.
2. Apply the already-frozen generic analysis. Do not change thresholds or taxonomy after observing Screw.
3. If Screw agrees, freeze the report and use Capsule once for final confirmation. If it disagrees, report category dependence and examine only the prespecified subtype summaries; do not tune a new method on Screw.
4. Use SurgClean only after its dataset-license, task-definition, mask, and split gates pass. Report it as a separate-domain extension.
5. Do not add Grid or more Hazelnut searches unless Screw exposes a specific unresolved repeated-texture mechanism that the current categories cannot test.

The next high-value GPU work is therefore one preflight, one full Screw Branch A run, the frozen cross-category analysis, and a CUDA smoke parity report. More Hazelnut threshold, weight, or selected-case searches have lower information value and increase post-hoc flexibility.
