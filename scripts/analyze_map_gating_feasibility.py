"""Exploratory Branch B map gates using saved predictions only; never fit/infer."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import file_digest
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from time import perf_counter

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.analyze_fusion_weights import _load_prediction, _metrics, _per_image_aupro
from scripts.analyze_hazelnut_failures import _bootstrap_mean_delta, _canonical_transform
from scripts.render_saved_map_cases import save_panels
from sr_anomaly.evaluation import evaluate_predictions
from sr_anomaly.fusion import METHODS, fuse_pair
from sr_anomaly.map_gating import gated_maps

CANDIDATES = ("candidate_1", "candidate_2")
TAUS = (0.005, 0.01, 0.02)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as handle:
        return file_digest(handle, "sha256").hexdigest()


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_predictions(predictions, paths):
    reference = predictions["restored_only"]
    labels, masks = reference["labels"], reference["masks"]
    if (labels.ndim != 1 or masks.ndim != 3 or len(paths) != len(labels)
            or len(set(paths)) != len(paths) or masks.shape[0] != len(labels)
            or not np.isin(labels, [0, 1]).all() or set(labels) != {0, 1}
            or not np.isin(masks, [0, 1]).all()):
        raise ValueError("Unique paths, binary labels/masks, and matching [N,H,W] arrays required")
    for sample in paths:
        parts = PurePosixPath(sample).parts
        if "\\" in sample or PurePosixPath(sample).is_absolute() or ".." in parts or ":" in sample:
            raise ValueError("Test sample paths must be portable relative paths")
    if np.any(masks[labels == 0]):
        raise ValueError("Normal test images must have empty GT masks; analysis stopped")
    for mask in masks[labels == 1]:
        if not mask.any() or mask.all():
            raise ValueError("Anomalous masks must contain both defect and background pixels")
    for name in METHODS:
        item = predictions[name]
        if (not np.array_equal(item["labels"], labels) or not np.array_equal(item["masks"], masks)
                or item["scores"].shape != labels.shape or item["maps"].shape != masks.shape
                or not np.isfinite(item["scores"]).all() or not np.isfinite(item["maps"]).all()):
            raise ValueError(f"Unpaired, misshaped, or non-finite anchor: {name}")
        for key in ("scores", "maps"):
            expected = fuse_pair(predictions["degraded_only"][key], reference[key], name)
            if not np.allclose(expected, item[key], rtol=1e-10, atol=1e-9):
                raise ValueError(f"Normalized endpoint anchor parity failed: {name} {key}")


def prepare_inputs(run_dir, bank_dir):
    result, split, bank = (read_json(path) for path in
                           (run_dir / "results.json", run_dir / "split.json", bank_dir / "metadata.json"))
    spec = result["model_spec"]
    calibration = result["fusion_calibration"]
    if (spec != bank["spec"] or spec["category"] != "hazelnut" or spec["seed"] != 11
            or spec["source_commit"] != "fcaa92f124fb1ad74a7acf56726decd4b27cbcad"
            or len(spec["train_paths"]) != 313 or len(spec["calibration_paths"]) != 78
            or split["train_paths"] != spec["train_paths"] or split["calibration_paths"] != spec["calibration_paths"]
            or set(spec["train_paths"]) & set(spec["calibration_paths"])
            or len(result["test_paths"]) != 110
            or calibration["normalization"] != "robust_median_iqr_per_variant"
            or calibration["quantile"] != 0.99):
        raise ValueError("Expected identical pinned Hazelnut 313-fit/78-normal-calibration/110-test Branch B")
    predictions = {name: _load_prediction(run_dir / f"{name}_predictions.npz") for name in METHODS}
    validate_predictions(predictions, result["test_paths"])
    labels = predictions["restored_only"]["labels"]
    if (int((labels == 0).sum()), int((labels == 1).sum()), predictions["restored_only"]["maps"].shape[1:]) != (40, 70, (224, 224)):
        raise ValueError("Expected 40 normal/70 anomalous images and 224x224 stored map coordinates")
    with (run_dir / "per_image.csv").open(encoding="utf-8", newline="") as handle:
        samples = list(csv.DictReader(handle))
    if ([row["sample"] for row in samples] != result["test_paths"]
            or [int(row["label"]) for row in samples] != labels.tolist()):
        raise ValueError("Saved CSV sample ordering/labels disagree with NPZ and results metadata")
    pilot = read_json(ROOT / "analysis/partial_restoration_feasibility/PROTOCOL.json")["inputs"]
    if spec != pilot["model_spec"] or calibration != pilot["fusion_calibration"]:
        raise ValueError("Branch B metadata disagrees with the historical source identity ledger")
    ledger = {key.replace("\\", "/"): value for key, value in pilot["source_sha256"].items()}
    if result["restoration"]["checkpoint_sha256"] != ledger["checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth"]:
        raise ValueError("Checkpoint provenance disagrees with the existing ledger")
    source_files = [run_dir / name for name in ("results.json", "split.json", "summary.csv", "per_image.csv")]
    source_files += [run_dir / f"{name}_predictions.npz" for name in METHODS]
    source_files += [bank_dir / "metadata.json"]
    source_files += [ROOT / path for path in ("src/sr_anomaly/fusion.py", "src/sr_anomaly/evaluation.py", "scripts/run_fusion_patchcore.py")]
    identities = []
    for path in source_files:
        ref, actual = relative(path), digest(path)
        expected = ledger.get(ref)
        if expected is not None and actual != expected:
            raise ValueError(f"Historical input hash mismatch: {ref}")
        identities.append({"path": ref, "bytes": path.stat().st_size, "sha256": actual,
                           "matches_existing_pilot_ledger": actual == expected if expected else None})
    calibration_files = sorted(path.name for path in run_dir.glob("*calibration*predictions*.npz"))
    return result, predictions, {"source_files": identities, "bank_spec_matches": True,
                                "bank_artifact_sha256_from_ledger": bank["artifact_sha256"],
                                "bank_bytes_rehashed": False, "checkpoint_bytes_rehashed": False,
                                "checkpoint_sha256_from_results": result["restoration"]["checkpoint_sha256"],
                                "calibration_prediction_files": calibration_files,
                                "normalization_status": "already normalized; source runner fuse_test_maps writes robust-normalized arrays"}


def anchor_evaluations(predictions, result):
    evaluations, checks = {}, {}
    calibration = result["fusion_calibration"]
    for method in METHODS:
        item = predictions[method]
        evaluation = evaluate_predictions(item["labels"], item["scores"], item["masks"], item["maps"],
                                          image_threshold=calibration["image_thresholds"][method],
                                          pixel_threshold=calibration["pixel_thresholds"][method])
        saved = result["methods"][method]["evaluation"]
        differences = []
        for section in ("classification", "localization"):
            for key, expected in saved[section].items():
                if expected is not None:
                    actual = evaluation[section][key]
                    if not np.isclose(actual, expected, rtol=1e-10, atol=1e-9):
                        raise ValueError(f"Saved evaluation anchor mismatch: {method}/{key}")
                    differences.append(abs(float(actual) - float(expected)))
        evaluations[method] = evaluation
        checks[method] = {"passed": True, "max_abs_metric_difference": max(differences)}
    # A second stored table is checked, not overwritten.
    with (Path(result["_run_dir"]) / "summary.csv").open(encoding="utf-8", newline="") as handle:
        summary = {row["method"]: row for row in csv.DictReader(handle)}
    for method, evaluation in evaluations.items():
        for field, key in (("image_auroc", "image_auroc"), ("pixel_auroc", "pixel_auroc"), ("au_pro", "pooled_au_pro")):
            if not np.isclose(float(summary[method][field]), _metrics(evaluation)[key], rtol=1e-10, atol=1e-9):
                raise ValueError(f"Summary CSV anchor mismatch: {method}/{field}")
    return evaluations, checks


def analyze(predictions, paths, evaluations, tau_deg, tau_rest):
    restored = predictions["restored_only"]
    candidate_maps = gated_maps(predictions["degraded_only"]["maps"], restored["maps"], tau_deg, tau_rest)
    labels, masks = restored["labels"], restored["masks"]
    maps = {name: predictions[name]["maps"] for name in METHODS} | candidate_maps
    per_image = []
    per_aupro = {name: {} for name in maps}
    for name, arrays in maps.items():
        for index in np.flatnonzero(labels == 1):
            per_aupro[name][index] = _per_image_aupro(masks[index], arrays[index])
    summaries = []
    for name, arrays in maps.items():
        if name in CANDIDATES:
            # Image scores are unchanged; no candidate thresholds or F1 are derived.
            evaluations[name] = evaluate_predictions(labels, restored["scores"], masks, arrays)
        deltas = np.array([value - per_aupro["restored_only"][index] for index, value in per_aupro[name].items()])
        ci = _bootstrap_mean_delta(deltas, 5000, np.random.default_rng(2026))
        normal_rates = np.mean(arrays[labels == 0] > tau_rest, axis=(1, 2))
        item = {"method": name, **_metrics(evaluations[name]),
                "delta_pooled_aupro_vs_restored": _metrics(evaluations[name])["pooled_au_pro"] - _metrics(evaluations["restored_only"])["pooled_au_pro"],
                "mean_per_image_aupro": float(np.mean(list(per_aupro[name].values()))),
                "mean_delta_vs_restored": float(deltas.mean()), "median_delta_vs_restored": float(np.median(deltas)),
                "q25_delta_vs_restored": float(np.quantile(deltas, 0.25)), "q75_delta_vs_restored": float(np.quantile(deltas, 0.75)),
                "minimum_delta_vs_restored": float(deltas.min()), "maximum_delta_vs_restored": float(deltas.max()),
                "improved_count": int((deltas > 0).sum()), "regressed_count": int((deltas < 0).sum()), "tie_count": int((deltas == 0).sum()),
                "mean_delta_ci95_low": ci["ci95"][0], "mean_delta_ci95_high": ci["ci95"][1],
                **{f"loss_gt_{tau:g}_vs_restored": int((deltas < -tau).sum()) for tau in TAUS},
                "normal_common_threshold_exceed_rate": float(normal_rates.mean()),
                "normal_exceed_rate_median": float(np.median(normal_rates)), "normal_exceed_rate_max": float(normal_rates.max()),
                "candidate_pixel_f1": None, "candidate_fixed_fpr": None}
        summaries.append(item)
        for index, sample in enumerate(paths):
            per_image.append({"sample": sample, "label": int(labels[index]), "defect_type": PurePosixPath(sample).parts[-2],
                              "method": name, "per_image_aupro": per_aupro[name].get(index),
                              "delta_aupro_vs_restored": per_aupro[name][index] - per_aupro["restored_only"][index] if labels[index] else None,
                              "delta_aupro_vs_degraded": per_aupro[name][index] - per_aupro["degraded_only"][index] if labels[index] else None,
                              "normal_common_threshold_exceed_rate": float((arrays[index] > tau_rest).mean()) if not labels[index] else None})
    return summaries, per_image, candidate_maps


def select_candidate(rows):
    indexed = {row["method"]: row for row in rows}
    eligible = [name for name in CANDIDATES if all(indexed[name]["pooled_au_pro"] > indexed[anchor]["pooled_au_pro"]
                                                 for anchor in ("restored_only", "max"))]
    return max(eligible, key=lambda name: (indexed[name]["pooled_au_pro"], name == "candidate_1")) if eligible else None


def render_examples(paths, predictions, candidate_maps, rows, data_root, output):
    # Post-hoc qualitative extremes are explanatory, not population estimates.
    controls = [row for row in rows if row["method"] == "candidate_1" and row["label"] == 1]
    ordered = sorted(controls, key=lambda row: (row["delta_aupro_vs_restored"], row["sample"]))
    selected = [ordered[0], sorted(controls, key=lambda row: (-row["delta_aupro_vs_restored"], row["sample"]))[0]]
    references = {name: predictions[name]["maps"] for name in ("degraded_only", "restored_only")} | candidate_maps
    canonical = _canonical_transform()
    output.mkdir()
    for number, row in enumerate(selected, 1):
        index = paths.index(row["sample"])
        with Image.open(data_root / row["sample"]) as image:
            clean = np.asarray(canonical(image.convert("RGB")))
        maps = [values[index] for values in references.values()]
        panels = [("Clean reference (not a method)", clean, None), ("GT (evaluation only)", predictions["restored_only"]["masks"][index], "gray")]
        panels += [(name + " normalized map", values[index], "viridis") for name, values in references.items()]
        save_panels(panels, output / f"case-{number}.png",
                    f"Exploratory post-hoc case: {row['sample']} | candidate_1 delta AU-PRO={row['delta_aupro_vs_restored']:+.6f}",
                    float(min(values.min() for values in maps)), float(max(values.max() for values in maps)))
    return [row["sample"] for row in selected]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "outputs/fusion-patchcore/hazelnut-313x78-test110")
    parser.add_argument("--bank-dir", type=Path, default=ROOT / "checkpoints/fusion-patchcore/hazelnut-seed11-train313")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/external/MVTecAD")
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("hazelnut-branchb-%Y%m%dT%H%M%SZ"))
    parser.add_argument("--timing-repeats", type=int, default=20)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.run_id) or args.run_id in {".", ".."} or args.timing_repeats < 1:
        parser.error("Safe unique run-id and positive timing repeats required")
    output = ROOT / "analysis/map_gating_feasibility" / args.run_id
    raw = ROOT / "outputs/map-gating-feasibility" / args.run_id
    if output.exists() or raw.exists():
        raise FileExistsError("Run directories already exist; never overwrite, choose a new run-id")
    result, predictions, identities = prepare_inputs(args.run_dir, args.bank_dir)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    calibration = result["fusion_calibration"]
    tau_deg, tau_rest = (calibration["pixel_thresholds"][method] for method in ("degraded_only", "restored_only"))
    protocol = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "base_commit": base,
                "scope": "Separate exploratory Hazelnut development feasibility, not preregistration or independent validation",
                "source_run": relative(args.run_dir), "split": {"fit": 313, "calibration_normal": 78, "test": 110},
                "cohort": result["test_paths"], "model_spec": result["model_spec"], "calibration": calibration,
                "map_coordinates": "stored normalized 224x224 anomaly maps; not probabilities or 28x28 feature gates",
                "candidates": {"candidate_1": "A_rest + 1[A_deg>tau_deg]*max(A_deg-A_rest,0)",
                               "candidate_2": "A_rest + 1[A_deg>tau_deg AND A_rest<=tau_rest]*max(A_deg-A_rest,0)"},
                "image_scores": "unchanged restored scores for both candidates", "gt_use": "evaluation only; never gating/thresholds",
                "primary": "full normal+anomalous cohort pooled AU-PRO@0.3; existing 200 thresholds",
                "secondary": "pixel AUROC; paired anomaly-image AU-PRO distribution and mean CI; common-threshold normal diagnostics",
                "loss_magnitudes": list(TAUS), "bootstrap": {"seed": 2026, "repeats": 5000, "estimand": "mean paired anomalous-image AU-PRO delta vs restored_only; not pooled CI"},
                "candidate_f1_fixed_fpr": "not evaluated; no candidate normal recalibration or operating-point validation",
                "normal_diagnostic": "strict map>existing restored pixel threshold; per-normal-image and pooled equal-area rates; not calibrated candidate FPR",
                "selection": "strictly exceed both restored_only and max pooled AU-PRO; larger pooled wins; exact tie candidate_1; otherwise stop",
                "tradeoff": "normal diagnostic increase or losses at existing 0.005/0.01/0.02 bands preclude an improvement-confirmed claim",
                "qualitative_selection": "candidate_1 minimum/maximum delta vs restored, lexical sample ties; post-hoc explanatory only",
                "timing": {"repeats": args.timing_repeats, "scope": "both gated_maps candidates jointly; CPU function only, including validation/allocation, excluding IO/metrics; not inference or system FPS"},
                "no_inference_fit_recalibration": True,
                "schema_adaptation_before_evaluation": "NPZ lacks sample paths/normalization flag: use hashed results/per_image ordering and source runner/anchor algebra; do not normalize again"}
    output.mkdir(parents=True)
    write_json(output / "PROTOCOL.json", protocol)
    protocol_hash = digest(output / "PROTOCOL.json")
    identities.update({"protocol_sha256": protocol_hash, "base_commit": base,
                       "code_sha256": {relative(ROOT / path): digest(ROOT / path) for path in
                                       ("scripts/analyze_map_gating_feasibility.py", "src/sr_anomaly/map_gating.py", "src/sr_anomaly/fusion.py",
                                        "src/sr_anomaly/evaluation.py", "scripts/analyze_fusion_weights.py", "scripts/analyze_hazelnut_failures.py", "scripts/render_saved_map_cases.py", "scripts/run_fusion_patchcore.py")}})
    write_json(output / "INPUT_MANIFEST.json", identities)
    print(f"Frozen before evaluation: {relative(output / 'PROTOCOL.json')} SHA256={protocol_hash}", flush=True)
    result["_run_dir"] = str(args.run_dir)
    evaluations, anchor_checks = anchor_evaluations(predictions, result)
    summaries, per_image, candidate_maps = analyze(predictions, result["test_paths"], evaluations, tau_deg, tau_rest)
    timing = []
    for _ in range(args.timing_repeats):
        started = perf_counter()
        timed = gated_maps(predictions["degraded_only"]["maps"], predictions["restored_only"]["maps"], tau_deg, tau_rest)
        timing.append(perf_counter() - started)
        del timed
    raw.mkdir(parents=True)
    for name, maps in candidate_maps.items():
        reference = predictions["restored_only"]
        np.savez_compressed(raw / f"{name}_predictions.npz", **{**reference, "maps": maps})
    write_json(raw / "results.json", {"test_paths": result["test_paths"], "analysis": relative(output),
                                     "protocol_sha256": protocol_hash, "source_manifest": relative(output / "INPUT_MANIFEST.json"),
                                     "image_scores": "unchanged restored_only", "map_status": "normalized, not probabilities"})
    write_csv(output / "summary.csv", summaries)
    write_csv(output / "per_image.csv", per_image)
    samples = render_examples(result["test_paths"], predictions, candidate_maps, per_image, args.data_root, output / "figures")
    selected = select_candidate(summaries)
    indexed = {row["method"]: row for row in summaries}
    tradeoff = selected is not None and (indexed[selected]["normal_common_threshold_exceed_rate"] > indexed["restored_only"]["normal_common_threshold_exceed_rate"]
                                        or any(indexed[selected][f"loss_gt_{tau:g}_vs_restored"] > 0 for tau in TAUS))
    interpretation = "음성 feasibility: 두 primary anchor를 모두 넘는 후보 없음; 추가 탐색 없이 종료" if selected is None else (
        "상충 결과: primary 조건 충족하지만 정상 경보 진단/감소 크기 비용이 있어 개선 확인으로 표현하지 않음" if tradeoff else
        "개발자료의 후속 검증 후보일 뿐: 작은 효과/mean CI와 독립 검증 부재를 함께 보고; 성공·안전·일반화 주장 없음")
    columns = ("method", "pooled_au_pro", "pixel_auroc", "mean_delta_vs_restored", "mean_delta_ci95_low", "mean_delta_ci95_high",
               "regressed_count", "loss_gt_0.01_vs_restored", "normal_common_threshold_exceed_rate")
    table = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    table += ["| " + " | ".join(str(row[key]) if isinstance(row[key], (int, str)) else f"{row[key]:.9f}" for key in columns) + " |" for row in summaries]
    report = ["# Branch B map-gating feasibility", "", "별도 Hazelnut 개발자료의 탐색적 후속 분석. 기존 연구 종료 기록과 full110 B/B-uncertain은 변경하지 않았다.", "",
              f"Protocol frozen before evaluation: `{protocol['frozen_at_utc']}`, SHA256 `{protocol_hash}`. Source/code identities: INPUT_MANIFEST.json; base commit `{base}`.", "",
              *table, "", f"선택 후보: `{selected}`. 판정: {interpretation}.", "",
              f"All four saved anchor arrays/evaluations/summary passed; metric differences: `{anchor_checks}`.", "",
              "CI는 70장 anomaly의 restored 대비 mean paired per-image delta에만 적용한다. Pooled AU-PRO의 CI가 아니다. Normal per-image AU-PRO는 빈칸이다.", "",
              "Candidate image scores는 restored_only와 동일하다. Image AUROC 개선을 주장하지 않는다. Calibration metadata만 있으며 실제 정상 calibration predictions는 이 source run에 없다. Candidate F1/고정 FPR은 계산하지 않았다. 정상 test threshold 초과는 공통 restored threshold의 진단이며 새 후보의 calibrated FPR이 아니다.", "",
              f"CPU fusion 함수 두 후보 공동 처리: {len(timing)} repeats, mean {np.mean(timing):.6f} s, median {np.median(timing):.6f} s, min {min(timing):.6f} s, max {max(timing):.6f} s. 검증/할당 포함, 읽기·metric·NPZ 저장 제외. 모델 추론 절감이나 전체 FPS가 아니다.", "",
              f"표시 사례는 사후 설명용 극값이며 population estimate가 아니다: `{samples}`. 4 maps share one scale per sample. Raw candidate NPZ: `{relative(raw)}`; source files never overwritten.", "",
              "두 고정 후보 이외 weight/threshold/dilation/smoothing/feature/FFT 탐색은 하지 않았다. 이 결과는 이미지 복원, feature preservation 또는 결함 삭제 방어 mechanism의 입증이 아니다. GT는 evaluation에만 사용했다.", "",
              "다음 검토는 독립 category 한 개의 frozen protocol, 별도 FAISS/backbone timing 측정, read-only 결과 탐색 데모로 제한한다. 새 실행은 이번 작업에 포함하지 않는다.", ""]
    (output / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"analysis": relative(output), "selected_candidate": selected, "interpretation": interpretation}, ensure_ascii=False))


if __name__ == "__main__":
    main()
