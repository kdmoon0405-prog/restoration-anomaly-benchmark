"""Read saved PCB and realistic-degradation rows without loading model/map arrays."""
from collections import defaultdict
from pathlib import Path
import json

import numpy as np
from scipy.stats import spearmanr

from .analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json
from .analysis_statistics import paired_bootstrap_mean_delta
from .evaluation import binary_f1, binary_roc_auc
from .fusion import normalize


def test_rows(rows):
    result = {}
    for row in rows:
        if row.get("split", "test") != "test":
            continue
        sample, label = row["sample"], int(row["label"])
        if sample in result or label not in (0, 1):
            raise ValueError("Duplicate sample or invalid label")
        value = row.get("per_image_aupro", "")
        if label == 0 and value != "":
            raise ValueError("Normal AU-PRO must be N/A")
        if label and (not np.isfinite(float(value)) or not 0 <= float(value) <= 1):
            raise ValueError("Invalid per-image AU-PRO")
        result[sample] = row
    return result


def paired_summary(reference, candidate, *, repeats=2000, seed=11):
    reference, candidate = test_rows(reference), test_rows(candidate)
    if set(reference) != set(candidate):
        raise ValueError("Paired sample identities differ")
    deltas, gaps = [], []
    for sample in sorted(reference):
        a, b = reference[sample], candidate[sample]
        if int(a["label"]) != int(b["label"]):
            raise ValueError("Paired labels differ")
        if int(a["label"]):
            deltas.append(float(b["per_image_aupro"]) - float(a["per_image_aupro"]))
            gaps.append(float(b["roi_bg_gap"]) - float(a["roi_bg_gap"]))
    values, gap = np.asarray(deltas), np.asarray(gaps)
    if not values.size:
        raise ValueError("Anomalous paired images required")
    boot = paired_bootstrap_mean_delta(values, repeats, np.random.default_rng(seed))
    return dict(anomaly_images=len(values), mean_delta=float(values.mean()), median_delta=float(np.median(values)),
        ci95_low=boot["ci95"][0], ci95_high=boot["ci95"][1], improvement=int((values > 0).sum()),
        tie=int((values == 0).sum()), regression=int((values < 0).sum()),
        suppression=int(((values < 0) & (gap < 0)).sum()),
        geometry_candidate=int(((values < 0) & (gap >= 0)).sum()),
        ci_estimand="posthoc_mean_per_image_delta_conditional_on_fixed_fit", pooled_ci_computed=False)


def operating_point(rows, threshold, field):
    selected = list(test_rows(rows).values())
    labels = np.asarray([int(r["label"]) for r in selected])
    scores = np.asarray([float(r[field]) for r in selected])
    if not np.isfinite(scores).all() or set(labels) != {0, 1}:
        raise ValueError("Finite scores and both classes required")
    predicted = scores >= threshold
    tp = int(((labels == 1) & predicted).sum())
    fn = int(((labels == 1) & ~predicted).sum())
    fp = int(((labels == 0) & predicted).sum())
    tn = int(((labels == 0) & ~predicted).sum())
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, image_auroc=binary_roc_auc(labels, scores),
        image_f1=binary_f1(labels, predicted), miss_rate=fn / (tp + fn), false_alarm_rate=fp / (fp + tn),
        fixed_threshold=float(threshold), score_normal_median=float(np.median(scores[labels == 0])),
        score_anomaly_median=float(np.median(scores[labels == 1])))


def exact_ranking(rows):
    ordered = sorted(rows, key=lambda r: (-float(r["au_pro"]), r["restorer"]))
    best, second = ordered[:2]
    score = float(best["au_pro"])
    return dict(winners="|".join(r["restorer"] for r in ordered if float(r["au_pro"]) == score),
        best_aupro=score, runner_up=second["restorer"], runner_up_aupro=float(second["au_pro"]),
        margin=score - float(second["au_pro"]),
        same_when_rounded_3dp=round(score, 3) == round(float(second["au_pro"]), 3))


def analyze(package, output, *, repeats=2000, seed=11):
    package = Path(package)
    out = new_output(Path(output), [package])
    sources, new_conditions = {}, []
    def read_csv(name):
        path = relative_source(package, name)
        sources[name] = digest(path)
        return csv_rows(path)
    def read_meta(name):
        path = relative_source(package, name)
        sources[name] = digest(path)
        return read_json(path)
    pcb_protocol = read_meta("pcb/raw-run/PROTOCOL.json")
    pcb_summary = {r["variant"]: r for r in read_csv("repo-results/pcb_full_cohort/derived/summary.csv")}
    pcb_points, pcb_images = [], {}
    for variant in ("clean", "bicubic_x4", "swinir_x4"):
        rows = read_csv(f"pcb/postprocess/perboard-{variant}/per_board.csv")
        if len(test_rows(rows)) != 200 or sum(int(r["label"]) for r in rows) != 100:
            raise ValueError("PCB cohort differs from 200/100 anomaly boards")
        calibration = read_meta(f"pcb/postprocess/calibration/{variant}.json")
        point = operating_point(rows, calibration["image_threshold"], "normalized_image_score")
        for metric in ("image_auroc", "image_f1"):
            if not np.isclose(point[metric], float(pcb_summary[variant][metric]), atol=1e-12, rtol=1e-12):
                raise ValueError("PCB saved scores/summary disagree: " + metric)
        pcb_images[variant] = rows
        pcb_points.append(dict(variant=variant, **point))
        new_conditions.append(dict(pcb_summary[variant], dataset="VisA", category="pcb2", seed=pcb_protocol["spec"]["seed"],
            train_count=sum(p["split"] == "fit" for p in pcb_protocol["parents"]),
            test_count=len(rows), n_anomaly=sum(int(r["label"]) for r in rows), study_family="pcb_native_full_cohort_v0_6",
            protocol_id=sources["pcb/raw-run/PROTOCOL.json"], source_artifact="pcb/postprocess",
            psnr=pcb_summary[variant]["mean_psnr"], ssim=pcb_summary[variant]["mean_ssim"]))
    pcb_pairs = [dict(reference=a, candidate=b, **paired_summary(pcb_images[a], pcb_images[b], repeats=repeats, seed=seed))
                 for a, b in (("bicubic_x4", "swinir_x4"), ("clean", "swinir_x4"), ("clean", "bicubic_x4"))]
    summary = read_csv("repo-results/realistic_degradation/derived/summary_56.csv")
    identities = [(r["category"], r["condition"], r["restorer"]) for r in summary]
    if len(summary) != 56 or len(set(identities)) != 56:
        raise ValueError("Missing or duplicate realistic conditions")
    groups, realistic_pairs, realistic_points, protocols = defaultdict(list), [], [], {}
    image_rows = {}
    for category in ("hazelnut", "screw"):
        protocols[category] = read_meta(f"realistic/{category}-v1/PROTOCOL.json")
    expected = {(cat, cond, restorer) for cat, protocol in protocols.items()
                for cond in protocol["conditions"] for restorer in protocol["restorers"]}
    if set(identities) != expected:
        raise ValueError("Realistic grid differs from recorded protocols")
    for row in summary:
        category, condition, restorer = (row[k] for k in ("category", "condition", "restorer"))
        base = f"realistic/{category}-v1"
        receipt = read_meta(f"{base}/units/{condition}__{restorer}.json")
        name = f"{base}/units/{condition}__{restorer}.csv"
        rows = read_csv(name)
        if receipt["protocol_sha256"] != sources[f"{base}/PROTOCOL.json"]:
            raise ValueError("Realistic protocol binding differs")
        if receipt["files"][f"units/{condition}__{restorer}.csv"] != sources[name]:
            raise ValueError("Realistic per-image CSV differs")
        tests = list(test_rows(rows).values())
        expected_labels = {r["sample"]: int(r["label"]) for r in protocols[category]["test"]}
        if {r["sample"]: int(r["label"]) for r in tests} != expected_labels:
            raise ValueError("Realistic test identities differ from protocol")
        if len(tests) != (110 if category == "hazelnut" else 160):
            raise ValueError("Realistic test cohort differs")
        for metric in ("image_auroc", "image_f1", "pixel_auroc", "au_pro"):
            if float(row[metric]) != receipt["metrics"][metric]:
                raise ValueError("Realistic summary/receipt differ")
        normalized = normalize(np.asarray([float(r["image_score"]) for r in tests]), receipt["calibration"]["image"])
        test_scores = [dict(r, normalized_image_score=score) for r, score in zip(tests, normalized, strict=True)]
        point = operating_point(test_scores, receipt["calibration"]["image_threshold"], "normalized_image_score")
        for metric in ("image_auroc", "image_f1"):
            if not np.isclose(point[metric], float(row[metric]), atol=1e-12, rtol=1e-12):
                raise ValueError("Realistic saved scores/metric differ")
        realistic_points.append(dict(category=category, condition=condition, restorer=restorer, **point))
        image_rows[category, condition, restorer] = tests
        groups[category, condition].append(row)
        new_conditions.append(dict(row, dataset="MVTecAD", study_family=protocols[category]["family"],
            protocol_id=sources[f"{base}/PROTOCOL.json"], seed=protocols[category]["split_seed"],
            variant=condition + "/" + restorer, train_count=len(protocols[category]["fit_paths"]),
            test_count=len(tests), n_anomaly=sum(int(r["label"]) for r in tests),
            psnr=row["mean_psnr"], ssim=row["mean_ssim"], lpips=row["mean_lpips"], source_artifact=name))
    rankings = []
    for (category, condition), rows in sorted(groups.items()):
        rankings.append(dict(category=category, condition=condition, **exact_ranking(rows)))
        for row in rows:
            if row["restorer"] == "bicubic_x4":
                continue
            realistic_pairs.append(dict(category=category, condition=condition, restorer=row["restorer"],
                **paired_summary(image_rows[category, condition, "bicubic_x4"],
                                 image_rows[category, condition, row["restorer"]], repeats=repeats, seed=seed)))
    correlations = []
    for category in ("both", "hazelnut", "screw"):
        selected = [r for r in summary if category == "both" or r["category"] == category]
        for metric in ("mean_psnr", "mean_ssim", "mean_lpips"):
            value = spearmanr([float(r[metric]) for r in selected], [float(r["au_pro"]) for r in selected]).statistic
            correlations.append(dict(category=category, metric=metric, conditions=len(selected),
                spearman=float(value), scope="descriptive_dependent_condition_rows_no_p_value"))
    endpoint = read_meta("screw-endpoint/restoration_objective_screw/derived/analysis_summary.json")
    for row in endpoint["aggregate_methods"]:
        new_conditions.append(dict(row, dataset="MVTecAD", study_family="restoration_objective_screw_matlab",
            protocol_id=endpoint["manifest_sha256"], category="screw", seed="", train_count="",
            n_anomaly=endpoint["anomalous_images"], psnr=row["mean_psnr"], ssim=row["mean_ssim"], lpips=row["mean_lpips"],
            source_artifact="screw-endpoint/restoration_objective_screw/derived/analysis_summary.json"))
    tables = dict(pcb_operating_points=pcb_points, pcb_paired_localization=pcb_pairs,
        realistic_operating_points=realistic_points, realistic_paired_summary=realistic_pairs,
        realistic_exact_rankings=rankings, quality_condition_correlations=correlations,
        new_master_conditions=new_conditions)
    for name, rows in tables.items():
        write_csv(out / (name + ".csv"), rows)
    receipt = dict(status="COMPLETE", kind="saved_gpu_return_row_analysis", bootstrap_repeats=repeats,
        bootstrap_seed=seed, analysis_source_sha256=digest(Path(__file__)), sources=sources,
        pcb_boards=200, realistic_conditions=56, new_master_rows=len(new_conditions),
        supplemental_ci="posthoc mean per-image differences conditional on fixed fits; not pooled metric CI",
        raw_prediction_arrays_supplied=False, pooled_metrics_recomputed=False,
        saved_score_classification_recomputed_for_consistency=True,
        tables={name + ".csv": digest(out / (name + ".csv")) for name in tables})
    write_json(out / "analysis_manifest.json", receipt)
    return receipt
