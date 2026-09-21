# SurgClean extension plan

Status: design only. SurgClean data and its official restoration checkpoint are not present under `data/external/` on this machine as of 2026-09-21. No SurgClean result has been produced.

## Role and question

SurgClean is a later surgical-domain extension, not a replacement for the MVTec anomaly-localization study. It must not be evaluated with MVTec masks, PatchCore AU-PRO, or the Hazelnut regression taxonomy as if those labels existed.

The narrow question is:

> Under one surgical degradation, does a gain under the dataset's frozen restoration-quality protocol agree with preservation of a separately defined task/feature signal?

## Entry gate

Do not start the pilot until all of the following are locally available and recorded:

- the dataset release, license/terms, directory structure, and official train/test or evaluation protocol;
- the official model code and one official restoration checkpoint for the selected task;
- the names and sample counts of the available severity levels;
- a defensible downstream label or a feature-preservation measure fixed without viewing pilot outcomes.

Adjacent clean frames are described as unaligned. Raw pixelwise PSNR/SSIM must therefore not be used as the primary conclusion unless the official protocol supplies aligned targets or a fixed alignment/evaluation procedure. Do not silently treat adjacent frames as registered pairs.

## First pilot only

- Task: Desmoke.
- Severity: two levels that already exist in the official dataset. Record their exact official names before loading outcomes.
- Restoration: one official model/checkpoint matched to Desmoke.
- Data: use the official split or evaluation list in full for those two levels; do not select visually favorable frames.
- Seed: fixed only where sampling is unavoidable; prefer the complete official subset.

The pilot matrix is therefore `2 severity levels × 1 restoration model`, comparing degraded input with restored output. Defog, desplash, other models, and cross-products are out of scope for the first pilot.

## Measurements to freeze before execution

1. Restoration quality: use the official SurgClean evaluation protocol. If it has no valid full-reference metric for unaligned frames, report the protocol's supported measure and do not invent an aligned PSNR/SSIM result after seeing outputs.
2. Information preservation: choose one frozen, reproducible signal with a clear unit and reference. A feature encoder is acceptable only if its checkpoint, preprocessing, spatial aggregation, and reference comparison are fixed in advance and relevant to surgical imagery. Without task labels, call this *feature preservation*, not downstream task accuracy.
3. Runtime and provenance: record dataset subset, severity, checkpoint hash, source revision, device, preprocessing, and per-image outputs.

Report paired per-image degraded-versus-restored changes and their joint distribution. The primary analysis asks whether restoration-quality improvement and feature-preservation change agree in sign; it does not tune a threshold or choose the best-looking severity.

## Decision gate

- Continue to a second SurgClean task only if the first pilot exposes a repeatable disagreement that cannot be explained by unaligned references or an unsuitable feature measure.
- Stop if the official protocol/checkpoint is unavailable, the feature signal lacks a defensible reference, or conclusions require selecting thresholds from the same evaluation frames.
- Keep all SurgClean claims separate from MVTec localization conclusions. No Capsule result or MVTec method selection is affected by this extension.

## Expected future artifacts

When the entry gate is satisfied, add a small config, one adapter for the verified folder structure, paired per-image CSV/JSON, and a concise result note. Keep the raw dataset, restored frames, and checkpoints outside normal Git history.
