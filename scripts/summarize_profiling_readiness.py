"""Report existing timing/inventory artifacts only; never load a model or dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def planning_estimate(protocol, summary, category):
    """Explicit linear bank-size planning reference, not measured PCB throughput."""
    fit = len(protocol["model_spec"]["train_paths"])
    ratio = category["proposed_fit"] / fit
    bank = summary["bank_memory"]
    patches = bank["ntotal"] / fit
    vectors = round(patches * category["proposed_fit"])
    stats = summary["statistics"]["instrumented/degraded"]
    residual = stats["detector_total_seconds"]["mean"] - stats["faiss_search_seconds"]["mean"]
    detector = residual + stats["faiss_search_seconds"]["mean"] * ratio
    images = category["proposed_calibration"] + category["test_normal"] + category["test_anomaly"]
    sr = summary["statistics"]["instrumented/restored"]["sr_seconds"]["mean"]
    embed_reference = category["proposed_fit"] * stats["backbone_embedding_seconds"]["mean"]
    return {"planning_only": True, "bank_size_ratio": ratio, "vectors": vectors,
            "float32_vector_bytes": vectors * bank["dimensions"] * 4,
            "calibration_plus_test_images": images, "detector_passes_per_image": 3,
            "detector_seconds_reference": detector,
            "fit_batch1_embedding_reference_seconds": embed_reference,
            "calibration_test_seconds_reference": images * (3 * detector + sr),
            "note": "Linear FAISS scaling from instrumented CPU means, clean/degraded/restored paths; excludes decoding, bank building, calibration/evaluation/IO and memory pressure. Not PCB or GPU measurements. Batch1 fit embedding reference is not batch8 fit throughput."}


def generate(folder):
    protocol, summary = read(folder / "PROTOCOL.json"), read(folder / "summary.json")
    manifest, parity = read(folder / "INPUT_MANIFEST.json"), read(folder / "ANCHOR_PARITY.json")
    inventory, plan = read(folder / "PCB_INVENTORY.json"), read(folder / "EXECUTION_PLAN.json")
    if hashlib.sha256((folder / "PROTOCOL.json").read_bytes()).hexdigest() != manifest["protocol_sha256"]:
        raise ValueError("Frozen profiling protocol hash mismatch")
    checks = parity["checks"]
    if not checks or not parity["all_passed"] or not all(row["passed"] for row in checks):
        raise ValueError("Missing/failed saved-anchor parity; do not publish successful profile")
    code = Path(__file__).with_name("profile_patchcore_stages.py")
    if hashlib.sha256(code.read_bytes()).hexdigest() != protocol["code_sha256"]:
        raise ValueError("Profiler changed since execution; preserve execution source before reporting")
    table = ["| Phase / path | Stage | N / unique / repeats | Mean s | Median s | Min..max s |",
             "| --- | --- | --- | ---: | ---: | ---: |"]
    for phase, stats in summary["statistics"].items():
        for key, values in stats.items():
            if not isinstance(values, dict):
                continue
            n = f"{stats['observations']} / {stats['unique_samples']} / {stats['repeats']}"
            table.append(f"| {phase} | {key} | {n} | {values['mean']:.6f} | {values['median']:.6f} | {values['min']:.6f}..{values['max']:.6f} |")
    instrumented = summary["statistics"]["instrumented/degraded"]
    hardware_path = folder / "HOST_RESOURCES.json"
    hardware = read(hardware_path) if hardware_path.exists() else {}
    cpu = hardware.get("cpu_name", "not recorded")
    faiss_share = instrumented["faiss_search_seconds"]["mean"] / instrumented["detector_total_seconds"]["mean"]
    max_map = max(row["map_max_abs_difference"] for row in checks)
    max_score = max(row["score_abs_difference"] for row in checks)
    simulation = summary["cost_simulation"]
    cost_rows = ["| Hypothetical SR call fraction p | Always SR s | Conditional s | Savings s |",
                 "| ---: | ---: | ---: | ---: |"]
    for row in simulation["rows"]:
        cost_rows.append(f"| {row['p']:.2f} | {row['always_sr_seconds']:.6f} | {row['conditional_seconds']:.6f} | {row['savings_seconds']:.6f} |")
    report = f"""# Frozen Branch B stage profiling

This is timing/development tooling, not a new research result. The negative map-gating feasibility, full110 B/B-uncertain, prior partial pilot10, scientific metrics and source artifacts are unchanged. No candidate/weight/threshold search, fit, recalibration or new model was performed.

## Execution and provenance

- Protocol stored before model loading/inference: [PROTOCOL.json](PROTOCOL.json); input hashes: [INPUT_MANIFEST.json](INPUT_MANIFEST.json).
- Original PatchCore source `{protocol['source_commit']}`; bank `{protocol['bank']}`; original SwinIR checkpoint and preprocessing recorded in protocol. The frozen-bank loader has no fit fallback. Existing cached backbone/checkpoint only; downloads blocked.
- Actual device `{protocol['actual_device']}`; CUDA available `{protocol['cuda_available']}`; Torch threads {protocol['torch_threads']}, CPU FAISS threads {protocol['faiss_threads']}, batch {protocol['batch_size']}. CUDA was not exercised. CPU: {cpu}; see optional [HOST_RESOURCES.json](HOST_RESOURCES.json) for post-run OS inventory, not a runtime resource trace. This was not an isolated benchmark host.
- {len(protocol['cohort'])} unique images/path: original pilot10 filenames, not a newly selected performance subset. Fixed warmup uses {len(protocol['warmup_samples'])} images on both paths. Instrumented repeats {plan['actual_repeats']}; separate original/uninstrumented repeat 1. Repeats are repeated timings, not additional independent samples.
- Preparation {summary['preparation_seconds']:.3f} s; bank/model load {summary['load_seconds']:.3f} s; warmup {summary['warmup_seconds']:.3f} s. Measured inference-phase wall {summary['inference_wall_seconds']:.3f} s versus {protocol['budget_seconds']} s budget. This wall clock conservatively includes anchor checks and intermediate CSV writes, despite the protocol's intended exclusion of writes. File IO was not separately timed. It is not pure model time.
- {len(checks)} normalized saved-anchor comparisons, all passed: map max absolute difference {max_map}, score max difference {max_score}. Includes warmup, instrumented and uninstrumented calls. Raw scores/maps are normalized with the existing calibration solely for parity; no new dataset metric is calculated. `evaluation_seconds=0` means no research metric evaluation, not zero parity-check cost.

## Measured stages

{chr(10).join(table)}

Code: `scripts/profile_patchcore_stages.py::instrument/run_pair`, original `PatchCore._embed/_predict`, CPU `anomaly_scorer.nn_method.run`, `patch_maker.unpatch_scores/score`, and `anomaly_segmentor.convert_to_segmentation`.

Backbone+embedding uses the original `_embed(detach=False)`, then the original per-row detach/CPU/NumPy conversion. On CPU there is no measured GPU-to-CPU transfer; the field names preserve the future CUDA boundary. FAISS remains CPU exact IndexFlatL2. Score/map postprocessing is the non-overlapping sum of the original three functions. Detector glue is parent minus child times, including input placement/packing/scorer reduction/reshape and hook overhead. Parent detector/E2E times must NOT be added to child stages. SR timing includes its adapter conversion, not an invented separate internal transfer measurement. CUDA helper synchronization is implemented but unvalidated on hardware here.

RGB decode/canonical/degradation preprocessing is shared once per image pair and attributed to both path latencies. Do not sum this twice to reconstruct wall time. E2E excludes parity checks/writes/load/warmup. The later uninstrumented pass is slower and the repeats drift; the data do NOT identify instrumentation overhead or its causal direction. No cause (thermal, contention, memory) was measured. No production FPS/p95/speedup claim follows.

FAISS is {100*faiss_share:.2f}% of instrumented degraded detector mean time. CPU index float32 vector storage estimate: {summary['bank_memory']['float32_vector_storage_estimate_bytes']:,} bytes ({summary['bank_memory']['ntotal']:,} x {summary['bank_memory']['dimensions']}); this is not process peak RSS. Peak CPU RSS was not recorded. CUDA peak allocated/reserved are null because CUDA was unavailable, not zero GPU memory.

## Conditional SR cost simulation only

Use the separate original end-to-end pass, with raw/restored detector+tensor preprocessing and SR from the same phase. Shared RGB preprocessing is excluded. `T_always = T_SR + T_det_rest`; `T_conditional = T_det_raw + p*(T_SR + T_det_rest)`. No trigger was executed or accuracy/safety equivalence established.

{chr(10).join(cost_rows)}

Strictly faster under this model requires `p < {simulation['break_even_call_fraction']:.6f}` ({100*simulation['break_even_call_fraction']:.2f}%). This is a hypothetical break-even, NOT measured savings or an available deployable gate. The observed negative map-gating result is not reversed by a cost simulation. The historical full110 3563.561 s wall clock covers different scope/variants and is not a per-image timing reference here.

Only two potential future optimization studies are identified, not implemented: (1) bank/coreset size versus accuracy/localization validation, because CPU exact search dominates; (2) exact-search batching/cache/memory benchmark with prediction parity, without changing search semantics. GPU backbone timing alone cannot establish an end-to-end gain while FAISS remains on CPU.

## Read-only demo and next boundary

See [demo instructions](../../../demo_results/README.md) and [DEMO_VERIFICATION.md](DEMO_VERIFICATION.md). Uses existing 110-image maps/CSV only, historical RGB on 10 verified filenames, unavailable otherwise. Candidate maps have no new RGB/image-quality metrics. Normal per-image AU-PRO is null; GT is evaluation overlay only. Browser screen verification remains unavailable without a connected browser.

See [PCB_READINESS.md](PCB_READINESS.md). PCB recommendation is file/split readiness only, not independent validation or permission to run a new experiment. No PCB/GPU inference occurred. At most: inspect the local demo, confirm teammate PCB prior usage, and separately authorize/freeze a baseline-transfer study if desired. Capsule remains untouched.
"""
    (folder / "REPORT.md").write_text(report, encoding="utf-8")
    chosen = next((row for row in inventory.get("categories", []) if row["category"] == inventory.get("recommended_category")), None)
    rows = ["| Category | Train normal | Test normal/anomaly | Total | Proposed fit/cal | Complete | Invalid/misaligned/cropped-empty masks | Local traces |",
            "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |"]
    for row in inventory.get("categories", []):
        if not row.get("raw_complete"):
            rows.append(f"| {row['category']} | unavailable | | | | no | | |")
            continue
        rows.append(f"| {row['category']} | {row['train_normal']} | {row['test_normal']}/{row['test_anomaly']} | {row['total_images']} | {row['proposed_fit']}/{row['proposed_calibration']} | yes | {row['raw_mask_invalid_count']}/{row['mask_dimension_mismatch_count']}/{row['canonical_mask_empty_count']} | {len(row['execution_traces'])} |")
    pcb = "# VisA PCB readiness only\n\n" + "\n".join(rows) + "\n\n"
    estimates = None
    if chosen:
        estimates = planning_estimate(protocol, summary, chosen)
        pcb += f"""Recommend **{chosen['category']}** using the rule saved before the file audit in [PCB_SELECTION_RULE.json](PCB_SELECTION_RULE.json): complete official category with no observed local execution trace, minimum train+test count, lexical tie. This is not performance-based selection. [PCB_INVENTORY.json](PCB_INVENTORY.json) is the actual file/mask audit. Official `data/external/VisA/split_csv/1cls.csv` and `VisASplitCSV` are used; all training labels are normal, split paths disjoint, all listed images/masks readable. Image dimensions: {', '.join(chosen['sizes'])}. Mask dimensions/nonempty checks and nearest-resize/crop survival passed; pixel-level human semantic alignment was not established.

Local trace search covered category fields in results/metadata/split JSON under local outputs/checkpoints. No trace was observed, but the search is not proof about Git history, alternate schemas, other folders or teammate machines. **Ask both GPU operators about prior PCB use before calling it untouched or independent validation.** No test performance was inspected or computed.

## Ready / still missing

- Ready: raw data, official split CSV, test GT paths, existing VisA adapter, reusable x4 geometry and cached SwinIR/backbone checkpoints. Proposed official-training split: {chosen['proposed_fit']} fit / {chosen['proposed_calibration']} normal calibration, fixed seed {protocol['seed']} and ratio {protocol['model_spec']['train_ratio']}; test {chosen['test_normal']+chosen['test_anomaly']}. These are planning counts, not a fitted PCB bank or measured experiment.
- Still missing: teammate usage confirmation; a frozen standalone PCB protocol/manifest; actual PCB normal bank and normal-calibration artifacts; adapter wiring into the MVTec-specific runner; hardware smoke/runtime/peak-memory measurement. The generic data adapter exists, but the current frozen runner cannot simply be given `--category pcb2`. Do not offer an untested execution command.
- Recommended question for a separately authorized study: does fixed Bicubic-x4 versus SwinIR-S-x4 quality/localization behavior transfer to PCB, with the same PatchCore and post-hoc strict-sign taxonomy? Start with Clean/Bicubic/SwinIR baselines, not failed map gates. Fit only PCB normal training data; calibrate only held-out PCB normal training data. Test GT is evaluation only. No threshold/weight tuning after test inspection; do not reuse Hazelnut's fitted bank/normalization thresholds as PCB calibration. Primary metric remains pooled AU-PRO@0.3 if that protocol is approved. No result is asserted here; Capsule stays untouched.

## Planning estimates, not measurements

Same 224 canonical / 56 LR / x4 restoration geometry, WRN50-2 layers and original patch settings. Current bank has {summary['bank_memory']['ntotal']:,} vectors for {len(protocol['model_spec']['train_paths'])} fit images. Assuming unchanged patch count and no coreset, proposed PCB bank: {estimates['vectors']:,} vectors of dimension {summary['bank_memory']['dimensions']}; float32 vectors alone {estimates['float32_vector_bytes']:,} bytes ({estimates['float32_vector_bytes']/2**30:.3f} GiB), {estimates['bank_size_ratio']:.3f}x current vector storage. Index/feature-array copies, Python/Torch/model buffers and image queues need extra CPU RAM; this is not peak RSS/VRAM. Actual GPU VRAM is unknown; no GPU allocation was measured.

Rough CPU reference from instrumented means only: `T_detector = current non-FAISS mean + current FAISS mean * (PCB_fit/current_fit)` = {estimates['detector_seconds_reference']:.3f} s/image/path. For {estimates['calibration_plus_test_images']} calibration+test images, three detector paths (clean/degraded/restored) plus one SR/image gives about {estimates['calibration_test_seconds_reference']/3600:.2f} h, excluding decode, bank build, calibration/evaluation and IO. Fit embedding batch1-equivalent reference {estimates['fit_batch1_embedding_reference_seconds']:.1f} s is NOT batch8 fit throughput or full fitting time. This is a simple linear bank-size extrapolation, not a measured PCB duration or confidence interval; cache/memory pressure and the observed timing drift may invalidate it. It must not be converted into a GPU speedup estimate. GPU runtime/VRAM requires separately authorized actual-hardware smoke before budgeting a full run.
"""
    else:
        pcb += "No eligible complete category; do not plan execution. See inventory blockers.\n"
    (folder / "PCB_READINESS.md").write_text(pcb, encoding="utf-8")
    (folder / "RESOURCE_ESTIMATES.json").write_text(json.dumps(estimates, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    generate(args.input)
    print("Saved-artifact REPORT.md / PCB_READINESS.md / RESOURCE_ESTIMATES.json generated; no inference")


if __name__ == "__main__":
    main()
