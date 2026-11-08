"""CPU research on existing maps and normal-calibrated operating points."""
from __future__ import annotations

from collections import defaultdict
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import time
import zipfile

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.stats import binomtest, spearmanr

from .analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json
from .analysis_statistics import paired_bootstrap_mean_delta
from .evaluation import connected_components
from .pcb_native_memory import available_ram, process_memory

VARIANTS = ("clean", "bicubic_x4", "swinir_x4")


def spatial_profile(anomaly_map, mask, fractions):
    """Exact top-k support with deterministic row-major handling of equal scores."""
    values = np.asarray(anomaly_map, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    if values.ndim != 2 or values.shape != mask.shape or not np.isfinite(values).all():
        raise ValueError("Expected a finite 2D map aligned with its mask")
    if not fractions or any(not 0 < f <= 1 for f in fractions):
        raise ValueError("Area fractions must be in (0,1]")
    order = np.argsort(-values.ravel(), kind="stable")
    gt_labels = connected_components(mask, connectivity=1)
    gt_sizes = np.bincount(gt_labels.ravel())[1:]
    distance = distance_transform_edt(~mask) if mask.any() else None
    diagonal = float(np.hypot(*mask.shape))
    result = []
    for fraction in fractions:
        k = max(1, math.ceil(float(fraction) * values.size))
        selected = order[:k]
        alert = np.zeros(values.shape, dtype=bool)
        alert.ravel()[selected] = True
        alert_labels = connected_components(alert, connectivity=1)
        alert_sizes = np.bincount(alert_labels.ravel())[1:]
        hits = int(mask.ravel()[selected].sum())
        region_hits = np.bincount(gt_labels.ravel()[selected], minlength=len(gt_sizes) + 1)[1:]
        cutoff = float(values.ravel()[order[k - 1]])
        ties = values.ravel() == cutoff
        selected_ties = int(ties[selected].sum())
        tie_count = int(ties.sum())
        mean_distance = float(distance.ravel()[selected].mean()) if distance is not None else None
        peak_distance = float(distance.ravel()[order[0]]) if distance is not None else None
        result.append(dict(area_fraction=float(fraction), top_k=k, actual_area_fraction=k / values.size,
            defect_area_pixels=int(mask.sum()), gt_region_count=len(gt_sizes),
            gt_pixel_recall=hits / int(mask.sum()) if mask.any() else None,
            selected_pixel_precision=hits / k,
            mean_gt_region_overlap=float(np.mean(region_hits / gt_sizes)) if len(gt_sizes) else None,
            gt_region_any_hit_rate=float(np.mean(region_hits > 0)) if len(gt_sizes) else None,
            alert_component_count=len(alert_sizes), largest_alert_component_fraction=int(alert_sizes.max()) / k,
            mean_selected_gt_distance_pixels=mean_distance,
            mean_selected_gt_distance_diagonal=mean_distance / diagonal if mean_distance is not None else None,
            peak_gt_distance_pixels=peak_distance,
            peak_gt_distance_diagonal=peak_distance / diagonal if peak_distance is not None else None,
            boundary_tie_count=tie_count, boundary_tie_crosses_budget=tie_count > selected_ties))
    return result


def _load_predictions(path):
    with np.load(path, allow_pickle=False) as source:
        if not {"maps", "masks", "labels", "scores"} <= set(source.files):
            raise ValueError("Missing prediction fields")
        result = {name: source[name] for name in ("maps", "masks", "labels", "scores")}
    if (result["maps"].shape != result["masks"].shape or result["maps"].ndim != 3
            or result["labels"].shape != (len(result["maps"]),)
            or result["scores"].shape != result["labels"].shape
            or not np.isfinite(result["maps"]).all() or not np.isfinite(result["scores"]).all()
            or not np.isin(result["labels"], (0, 1)).all()):
        raise ValueError("Invalid prediction shape, label or finite values")
    if np.any(result["masks"][result["labels"] == 0]):
        raise ValueError("Normal images have nonempty masks")
    return result


def _budget_guard(paths, reserve):
    payload = 0
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            payload = max(payload, sum(i.file_size for i in archive.infolist()))
    required = reserve + 3 * payload
    available = available_ram()
    if available < required:
        raise MemoryError(f"CPU map analysis requires {required} bytes; available {available}")
    return dict(reserve_bytes=reserve, largest_uncompressed_prediction_bytes=payload,
                required_available_bytes=required, available_before_bytes=available)


def _bootstrap(values, settings, salt):
    stable = int(hashlib.sha256(salt.encode()).hexdigest()[:16], 16)
    rng = np.random.default_rng(np.random.SeedSequence([settings["bootstrap_seed"], stable]))
    return paired_bootstrap_mean_delta(np.asarray(values), settings["bootstrap_repeats"], rng)


def paired_budget_effects(rows, settings):
    paired = {}
    for row in rows:
        if row["label"] == 1:
            key = row["category"], row["sample"], row["area_fraction"]
            paired.setdefault(key, {})[row["variant"]] = row
    metrics = ("gt_pixel_recall", "mean_gt_region_overlap", "gt_region_any_hit_rate",
               "alert_component_count", "mean_selected_gt_distance_diagonal")
    grouped, deltas = defaultdict(list), []
    for (category, sample, fraction), branches in sorted(paired.items()):
        bic, swin = branches["bicubic_x4"], branches["swinir_x4"]
        row = dict(category=category, sample=sample, defect_type=bic["defect_type"], area_fraction=fraction)
        for metric in metrics:
            row["delta_" + metric] = swin[metric] - bic[metric]
        deltas.append(row)
        grouped[category, fraction].append(row)
    summary = []
    for (category, fraction), group in sorted(grouped.items()):
        for metric in metrics:
            values = [r["delta_" + metric] for r in group]
            boot = _bootstrap(values, settings, f"{category}/{fraction}/{metric}")
            summary.append(dict(category=category, area_fraction=fraction, metric=metric,
                comparison="swinir_x4_minus_bicubic_x4", n_anomaly_images=boot["n"],
                mean_delta=boot["estimate"], ci95_low=boot["ci95"][0], ci95_high=boot["ci95"][1],
                median_delta=float(np.median(values)), min_delta=float(np.min(values)),
                max_delta=float(np.max(values)), decrease_count=int(np.sum(np.asarray(values) < 0)),
                increase_count=int(np.sum(np.asarray(values) > 0)),
                ci_unit="paired anomalous image within category"))
    return summary, deltas


def operating_point(labels, scores, threshold, confidence=0.95):
    labels, scores = np.asarray(labels), np.asarray(scores)
    if labels.shape != scores.shape or labels.ndim != 1 or not np.isfinite(scores).all():
        raise ValueError("Invalid operating-point inputs")
    if not np.isin(labels, (0, 1)).all() or not math.isfinite(float(threshold)):
        raise ValueError("Operating point requires binary labels and finite threshold")
    predicted = scores >= threshold
    normal, anomaly = labels == 0, labels == 1
    fp, tp = int(predicted[normal].sum()), int(predicted[anomaly].sum())
    result = dict(image_threshold=float(threshold), normal_count=int(normal.sum()),
        anomaly_count=int(anomaly.sum()), fp=fp, tn=int(normal.sum()) - fp,
        tp=tp, fn=int(anomaly.sum()) - tp)
    for name, count, n in (("normal_image_fpr", fp, int(normal.sum())),
                            ("anomaly_image_sensitivity", tp, int(anomaly.sum()))):
        interval = binomtest(count, n).proportion_ci(confidence_level=confidence, method="exact") if n else None
        result[name] = count / n if n else None
        result[name + "_ci95_low"] = float(interval.low) if interval else None
        result[name + "_ci95_high"] = float(interval.high) if interval else None
    return result


def analyze_calibrated_run(directory, output, settings):
    result = read_json(directory / "results.json")
    calibration = result["fusion_calibration"]
    if calibration["quantile"] != 0.99 or result["model_spec"]["train_ratio"] != 0.8:
        raise ValueError("Expected the stored normal-only Branch B calibration")
    train = result["model_spec"]["train_paths"]
    cal = result["model_spec"]["calibration_paths"]
    paths = result["test_paths"]
    if set(train) & set(cal) or (set(train) | set(cal)) & set(paths):
        raise ValueError("Fit/calibration/test paths overlap")
    methods = ("clean_reference", "degraded_only", "restored_only", "mean_0.5_0.5", "max")
    summary, per_image, predictions = [], [], {}
    baseline_masks = baseline_labels = None
    for method in methods:
        name = method + "_predictions.npz"
        data = _load_predictions(directory / name)
        if baseline_labels is None:
            baseline_labels, baseline_masks = data["labels"].copy(), data["masks"].copy()
        elif not np.array_equal(data["labels"], baseline_labels) or not np.array_equal(data["masks"], baseline_masks):
            raise ValueError("Branch B maps/labels are unpaired")
        if len(paths) != len(data["labels"]):
            raise ValueError("Branch B test path count differs")
        if method == "clean_reference":
            threshold = result["clean_calibration"]["image_threshold"]
            pixel_threshold = result["clean_calibration"]["pixel_threshold"]
        else:
            threshold = calibration["image_thresholds"][method]
            pixel_threshold = calibration["pixel_thresholds"][method]
        stored = result["methods"][method]["evaluation"]["classification"]["image_threshold"]
        if not math.isclose(threshold, stored, abs_tol=1e-12):
            raise ValueError("Stored method threshold disagrees with calibration")
        stored_pixel = result["methods"][method]["evaluation"]["localization"]["pixel_threshold"]
        if not math.isclose(pixel_threshold, stored_pixel, abs_tol=1e-12):
            raise ValueError("Stored pixel threshold disagrees with calibration")
        row = dict(method=method, **operating_point(data["labels"], data["scores"], threshold,
                                                   settings["confidence_level"]))
        row["pixel_threshold"] = pixel_threshold
        predictions[method] = (data["scores"] >= threshold).astype(np.int8)
        for i, sample in enumerate(paths):
            mask, alert = data["masks"][i].astype(bool), data["maps"][i] >= pixel_threshold
            per_image.append(dict(method=method, sample=sample, label=int(data["labels"][i]),
                image_predicted_anomaly=int(predictions[method][i]), image_score=float(data["scores"][i]),
                image_threshold=threshold, pixel_threshold=pixel_threshold,
                false_positive_area_fraction=float(alert[~mask].mean()) if (~mask).any() else None,
                gt_pixel_recall=float(alert[mask].mean()) if mask.any() else None,
                predicted_area_fraction=float(alert.mean())))
        own = [r for r in per_image if r["method"] == method]
        for metric, label in (("false_positive_area_fraction", 0), ("gt_pixel_recall", 1)):
            values = [r[metric] for r in own if r["label"] == label]
            boot = _bootstrap(values, settings, method + metric)
            row["mean_" + metric] = boot["estimate"]
            row[metric + "_mean_ci95_low"], row[metric + "_mean_ci95_high"] = boot["ci95"]
        summary.append(row)
        del data
        gc.collect()
    paired = []
    reference = predictions["degraded_only"]
    for method in methods:
        if method == "degraded_only":
            continue
        for label, metric in ((0, "normal_image_fpr"), (1, "anomaly_image_sensitivity")):
            selected = baseline_labels == label
            a, b = reference[selected], predictions[method][selected]
            values = b - a
            boot = _bootstrap(values, settings, "paired/" + method + "/" + metric)
            paired.append(dict(method=method, reference="degraded_only", metric=metric,
                n_images=len(values), mean_delta=boot["estimate"],
                ci95_low=boot["ci95"][0], ci95_high=boot["ci95"][1],
                reference_alert_candidate_clear=int(np.sum((a == 1) & (b == 0))),
                reference_clear_candidate_alert=int(np.sum((a == 0) & (b == 1))),
                ci_unit="paired test image within label group"))
    alpha = 1 - settings["confidence_level"]
    planning = dict(target_fpr=0.01, confidence=settings["confidence_level"],
        interval="exact two-sided binomial",
        zero_false_alarm_normal_count_required=math.ceil(math.log(alpha / 2) / math.log(0.99)),
        assumptions="Independent representative normal images and frozen model/threshold")
    write_csv(output / "operating_points.csv", summary)
    write_csv(output / "operating_per_image.csv", per_image)
    write_csv(output / "paired_operating_effects.csv", paired)
    write_json(output / "normal_fpr_sample_plan.json", planning)
    source_files = [directory / "results.json", directory / "split.json"]
    source_files += [directory / (m + "_predictions.npz") for m in methods]
    return dict(methods=len(summary), test_count=len(paths), normal_calibration_count=len(cal),
                sources=[dict(file=str(p), sha256=digest(p)) for p in source_files],
                zero_false_alarm_normal_count_required=planning["zero_false_alarm_normal_count_required"])


def run_saved_research(artifact_root, output, config, *, campaign_status=None):
    artifact_root = Path(artifact_root).resolve()
    settings = read_json(Path(config))
    if (settings["schema_version"] != 1 or settings["gt_connectivity"] != 1
            or settings["budget_rounding"] != "ceil"
            or settings["score_ties"] != "stable_descending_row_major"):
        raise ValueError("Unsupported spatial protocol")
    directories = [relative_source(artifact_root, r["directory"]) for r in settings["runs"]]
    prediction_paths = [p / (v + "_predictions.npz") for p in directories for v in VARIANTS]
    calibrated = relative_source(artifact_root, settings["calibrated_run"])
    prediction_paths += [calibrated / (v + "_predictions.npz") for v in
                        ("clean_reference", "degraded_only", "restored_only", "mean_0.5_0.5", "max")]
    guard = _budget_guard(prediction_paths, settings["reserve_ram_bytes"])
    out = new_output(Path(output), directories)
    status = dict(kind=settings["analysis_family"], status="RUNNING", worker_pid=os.getpid(),
        settings=settings, config_sha256=digest(Path(config)), ram_guard=guard,
        model_inference_executed=False, sources=[])
    write_json(out / "status.json", status)
    if campaign_status:
        write_json(Path(campaign_status), dict(status="RUNNING", stage="saved_research",
            worker_pid=os.getpid(), output=str(out), completed=[]))
    started = time.perf_counter()
    rows, quality_rows, memory_rows = [], {}, []
    try:
        for spec, directory in zip(settings["runs"], directories, strict=True):
            metadata = read_json(directory / "results.json")
            paths = metadata["test_paths"]
            if metadata["model_spec"]["category"] != spec["category"] or len(paths) != len(set(paths)):
                raise ValueError("Source category or unique sample identity differs")
            quality_rows.update({(spec["category"], r["sample"], r["variant"]): r
                                 for r in csv_rows(directory / "per_image.csv")})
            reference_labels = reference_masks = None
            for variant in VARIANTS:
                file = directory / (variant + "_predictions.npz")
                data = _load_predictions(file)
                if len(data["maps"]) != len(paths):
                    raise ValueError("Source test_paths do not align with predictions")
                if reference_masks is None:
                    reference_masks, reference_labels = data["masks"].copy(), data["labels"].copy()
                elif not np.array_equal(reference_masks, data["masks"]) or not np.array_equal(reference_labels, data["labels"]):
                    raise ValueError("Source variants are not paired")
                for i, sample in enumerate(paths):
                    if int(data["labels"][i]) == 1 and not data["masks"][i].any():
                        raise ValueError("Anomalous source mask is empty")
                    for row in spatial_profile(data["maps"][i], data["masks"][i], settings["area_fractions"]):
                        rows.append(dict(category=spec["category"], sample=sample,
                            defect_type=Path(sample).parent.name, label=int(data["labels"][i]), variant=variant, **row))
                memory_rows.append(dict(category=spec["category"], variant=variant, **process_memory(),
                                        available_ram_bytes=available_ram()))
                status["sources"].append(dict(file=str(file), sha256=digest(file)))
                del data
                gc.collect()
            status["sources"].append(dict(file=str(directory / "results.json"), sha256=digest(directory / "results.json")))
            status["sources"].append(dict(file=str(directory / "per_image.csv"), sha256=digest(directory / "per_image.csv")))
            del reference_masks, reference_labels
            gc.collect()
        effects, paired = paired_budget_effects(rows, settings)
        summary = []
        groups = defaultdict(list)
        for row in rows:
            groups[row["category"], row["variant"], row["area_fraction"], row["label"]].append(row)
        for (category, variant, fraction, label), group in sorted(groups.items()):
            record = dict(category=category, variant=variant, area_fraction=fraction, label=label, n_images=len(group))
            for metric in ("gt_pixel_recall", "mean_gt_region_overlap", "gt_region_any_hit_rate",
                           "alert_component_count", "largest_alert_component_fraction",
                           "mean_selected_gt_distance_diagonal"):
                values = [r[metric] for r in group if r[metric] is not None]
                record["mean_" + metric] = float(np.mean(values)) if values else None
            record["budget_boundary_tie_images"] = sum(r["boundary_tie_crosses_budget"] for r in group)
            summary.append(record)
        associations = []
        for category in (r["category"] for r in settings["runs"]):
            own = [r for r in paired if r["category"] == category
                   and r["area_fraction"] == settings["qualitative_area_fraction"]]
            for metric in ("psnr", "ssim"):
                x, y = [], []
                for row in own:
                    a = quality_rows[category, row["sample"], "bicubic_x4"].get(metric, "")
                    b = quality_rows[category, row["sample"], "swinir_x4"].get(metric, "")
                    if a != "" and b != "" and math.isfinite(float(a)) and math.isfinite(float(b)):
                        x.append(float(b) - float(a))
                        y.append(row["delta_gt_pixel_recall"])
                rho = float(spearmanr(x, y).statistic) if len(x) > 2 and len(set(x)) > 1 and len(set(y)) > 1 else None
                associations.append(dict(category=category, quality_delta=metric,
                    response="delta_gt_pixel_recall", area_fraction=settings["qualitative_area_fraction"],
                    n_paired_anomaly_images=len(x), spearman_rho=rho, scope="exploratory association"))
        write_csv(out / "per_image_budget.csv", rows)
        write_csv(out / "spatial_summary.csv", summary)
        write_csv(out / "paired_budget_effects.csv", effects)
        write_csv(out / "per_image_budget_deltas.csv", paired)
        write_csv(out / "quality_association.csv", associations)
        write_csv(out / "memory_snapshots.csv", memory_rows)
        status["operating_analysis"] = analyze_calibrated_run(calibrated, out, settings)
        status["sources"].append(dict(file=str(calibrated / "results.json"), sha256=digest(calibrated / "results.json")))
        status.update(status="COMPLETE", elapsed_seconds=time.perf_counter() - started,
            total_images=sum(len(read_json(p / "results.json")["test_paths"]) for p in directories),
            source_methods=len(VARIANTS), budget_rows=len(rows),
            code_sha256={p.name: digest(p) for p in (Path(__file__), Path(__file__).with_name("analysis_statistics.py"))})
        write_json(out / "status.json", status)
        if campaign_status:
            write_json(Path(campaign_status), dict(status="SAVED_RESEARCH_COMPLETE", stage="cpu_baseline_readiness",
                worker_pid=None, completed=["spatial_budget_analysis", "normal_calibrated_operating_points"],
                saved_output=str(out), next_action="CPU detector/control baseline readiness and figures"))
        return status
    except BaseException as error:
        status.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        write_json(out / "status.json", status)
        if campaign_status:
            write_json(Path(campaign_status), dict(status="FAILED", worker_pid=None, output=str(out),
                                                  error=status["error"]))
        raise
