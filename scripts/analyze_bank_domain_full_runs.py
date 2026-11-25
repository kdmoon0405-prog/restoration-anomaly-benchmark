"""Analyze only hash-verified complete 2x2 normal-bank domain study runs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zlib

import numpy as np

from sr_anomaly import bank_domain_study as study


BOOTSTRAP_DRAWS = 10_000


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: str, *, allow_blank: bool = False) -> float | None:
    if value == "" and allow_blank:
        return None
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"Non-finite value in CSV: {value!r}")
    return result


def _quality_float(value: str) -> float:
    result = float(value)
    # PSNR is +inf for an exact reconstruction; preserve that valid boundary case.
    if np.isnan(result) or np.isneginf(result):
        raise ValueError(f"Invalid quality value in CSV: {value!r}")
    return result


def _quality_mean(values: list[float]) -> float:
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def _quality_delta_mean(comparison: list[float], baseline: list[float]) -> float | None:
    deltas: list[float] = []
    for left, right in zip(baseline, comparison, strict=True):
        if np.isposinf(left) and np.isposinf(right):
            return None
        deltas.append(right - left)
    if np.isposinf(deltas).any() and np.isneginf(deltas).any():
        return None
    return float(np.mean(np.asarray(deltas, dtype=np.float64)))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty analysis table: {path.name}")
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def paired_mean_bootstrap_ci(
    deltas: list[float] | np.ndarray,
    *,
    seed: int,
    draws: int = BOOTSTRAP_DRAWS,
) -> dict[str, float | int]:
    values = np.asarray(deltas, dtype=np.float64).ravel()
    if values.size == 0 or not np.isfinite(values).all() or draws < 1:
        raise ValueError("Bootstrap requires finite paired deltas and positive draw count")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(draws, values.size))
    means = values[indices].mean(axis=1)
    lower, upper = np.quantile(means, [0.025, 0.975])
    return {
        "mean_delta": float(values.mean()),
        "ci_95_lower": float(lower),
        "ci_95_upper": float(upper),
        "anomalous_image_count": int(values.size),
        "bootstrap_draws": int(draws),
    }


def _load_run(run_dir: Path) -> dict:
    status_path = run_dir / "status.json"
    state = json.loads(status_path.read_text(encoding="utf-8"))
    samples = state.get("test_samples", [])
    study.verify_complete_run(run_dir, study.expected_condition_order(samples))
    required_input_hashes = {
        **state.get("train_input_sha256", {}),
        **state.get("test_input_sha256", {}),
        **{
            f"mask:{sample}": digest
            for sample, digest in state.get("test_mask_sha256", {}).items()
            if digest is not None
        },
    }
    inventory_sha = hashlib.sha256(
        json.dumps(required_input_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if inventory_sha != state.get("input_inventory_sha256"):
        raise ValueError(f"{run_dir}: dataset input inventory hash is missing or inconsistent")
    artifact_by_name = {item["file"]: item for item in state["artifacts"]}
    raw_identity: dict[str, dict] = {}
    raw_calibration_stats: dict[tuple[str, str], dict[str, float]] = {}
    for bank in study.BANK_DOMAINS:
        raw_name = f"raw_{bank}.npz"
        if raw_name not in artifact_by_name:
            raise ValueError(f"{run_dir}: missing raw prediction artifact {raw_name}")
        raw_path = study.safe_artifact_path(run_dir, raw_name)
        with np.load(raw_path, allow_pickle=False) as archive:
            actual_shapes = {name: list(archive[name].shape) for name in archive.files}
            if actual_shapes != artifact_by_name[raw_name].get("arrays"):
                raise ValueError(f"{run_dir}: raw array shapes differ from artifact manifest: {raw_name}")
            for name in archive.files:
                values = archive[name]
                if values.dtype.kind in "fiu" and not np.isfinite(values).all():
                    raise ValueError(f"{run_dir}: non-finite values in {raw_name}/{name}")
            if archive["test_samples"].astype(str).tolist() != samples:
                raise ValueError(f"{run_dir}: raw test sample inventory differs from status")
            if archive["query_domains"].astype(str).tolist() != list(study.QUERY_DOMAINS):
                raise ValueError(f"{run_dir}: raw query domain order differs from protocol")
            expected_calibration = state["calibration_paths"]
            if archive["calibration_samples"].astype(str).tolist() != expected_calibration:
                raise ValueError(f"{run_dir}: raw calibration inventory differs from status")
            if archive["test_scores"].shape != (len(samples), len(study.QUERY_DOMAINS)):
                raise ValueError(f"{run_dir}: unexpected test score shape")
            if archive["test_maps"].shape != (len(samples), len(study.QUERY_DOMAINS), 224, 224):
                raise ValueError(f"{run_dir}: unexpected test map shape")
            if archive["calibration_scores"].shape != (int(state["calibration_count"]), len(study.QUERY_DOMAINS)):
                raise ValueError(f"{run_dir}: unexpected calibration score shape")
            if archive["calibration_maps"].shape != (
                int(state["calibration_count"]), len(study.QUERY_DOMAINS), 224, 224
            ):
                raise ValueError(f"{run_dir}: unexpected calibration map shape")
            bank_hash = archive["bank_sha256"].astype(str).item()
            if bank_hash != state.get("bank_hashes", {}).get(bank):
                raise ValueError(f"{run_dir}: saved bank hash differs for {bank}")
            raw_identity[bank] = {
                "samples": samples,
                "query_input_sha256": archive["query_input_sha256"].astype(str).tolist(),
                "query_domains": archive["query_domains"].astype(str).tolist(),
                "query_domain_sha256": {
                    "bicubic_x4": archive["query_bicubic_sha256"].astype(str).tolist(),
                    "swinir_x4": archive["query_swinir_sha256"].astype(str).tolist(),
                },
            }
            for query_index, query in enumerate(study.QUERY_DOMAINS):
                scores = np.asarray(archive["calibration_scores"][:, query_index], dtype=np.float64)
                pixels = np.asarray(archive["calibration_maps"][:, query_index], dtype=np.float32)
                raw_calibration_stats[(bank, query)] = {
                    "score_mean": float(scores.mean()),
                    "score_median": float(np.median(scores)),
                    "score_std": float(scores.std()),
                    "score_q95": float(np.quantile(scores, 0.95)),
                    "pixel_mean": float(pixels.mean()),
                    "pixel_median": float(np.median(pixels)),
                    "pixel_std": float(pixels.std()),
                    "pixel_q95": float(np.quantile(pixels, 0.95)),
                }
    study.validate_pair_identity(raw_identity["clean"], raw_identity["swinir_restored"])
    summary = _read_csv(run_dir / "summary.csv")
    per_image = _read_csv(run_dir / "per_image.csv")
    quality = _read_csv(run_dir / "query_quality.csv")
    if len(summary) != 4:
        raise ValueError(f"{run_dir}: expected exactly four condition summary rows")
    summary_keys = {
        (row["bank_domain"], row["query_domain"]): row
        for row in summary
    }
    expected_keys = {(bank, query) for bank in study.BANK_DOMAINS for query in study.QUERY_DOMAINS}
    if set(summary_keys) != expected_keys:
        raise ValueError(f"{run_dir}: summary does not contain the frozen 2x2 conditions")
    sample_ids = list(samples)
    if len(quality) != len(sample_ids) or [row["sample"] for row in quality] != sample_ids:
        raise ValueError(f"{run_dir}: query quality must appear once in test sample order")
    rows_by_cell: dict[tuple[str, str], dict[str, dict[str, str]]] = {}
    for bank in study.BANK_DOMAINS:
        for query in study.QUERY_DOMAINS:
            cell_rows = [row for row in per_image
                         if row["bank_domain"] == bank and row["query_domain"] == query]
            if [row["sample"] for row in cell_rows] != sample_ids:
                raise ValueError(f"{run_dir}: per-image row order differs for {bank}/{query}")
            if any(row["label"] == "0" and row["per_image_aupro"] != "" for row in cell_rows):
                raise ValueError("Normal samples must not receive per-image AU-PRO values")
            if any(row["label"] == "1" and row["per_image_aupro"] == "" for row in cell_rows):
                raise ValueError("Anomalous samples are missing per-image AU-PRO")
            rows_by_cell[(bank, query)] = {row["sample"]: row for row in cell_rows}
    return {
        "path": run_dir.resolve(),
        "state": state,
        "summary": summary_keys,
        "per_image": rows_by_cell,
        "quality": quality,
        "samples": sample_ids,
        "raw_calibration_stats": raw_calibration_stats,
    }


def _calibration_rows(run: dict) -> list[dict]:
    state = run["state"]
    result = []
    for bank in study.BANK_DOMAINS:
        for query in study.QUERY_DOMAINS:
            cell = state["calibration_by_cell"][f"{bank}/{query}"]
            raw = run["raw_calibration_stats"][(bank, query)]
            result.append({
                "category": state["category"],
                "seed": int(state["seed"]),
                "bank_domain": bank,
                "query_domain": query,
                "calibration_count": int(cell["calibration_count"]),
                **raw,
                "image_normalization_median": cell["image"]["median"],
                "image_normalization_scale": cell["image"]["scale"],
                "image_normalization_fallback": cell["image"]["method"],
                "image_threshold": cell["image_threshold"],
                "pixel_normalization_median": cell["pixel"]["median"],
                "pixel_normalization_scale": cell["pixel"]["scale"],
                "pixel_normalization_fallback": cell["pixel"]["method"],
                "pixel_threshold": cell["pixel_threshold"],
            })
    return result


def _runtime_rows(run: dict) -> list[dict]:
    state = run["state"]
    after = state.get("resource_snapshot_after", {})
    before = state.get("resource_snapshot_before_fit", {})
    per_bank_ram = state.get("available_ram_before_each_bank_bytes", {})
    result = []
    for item in state.get("runtime", []):
        result.append({
            "category": state["category"],
            "seed": int(state["seed"]),
            **item,
            "available_ram_before_bank_bytes": per_bank_ram.get(item["bank_domain"]),
            "available_ram_after_run_bytes": after.get("available_ram_bytes"),
            "disk_free_before_run_bytes": state.get("resource_plan", {}).get("free_disk_before_run_bytes"),
            "disk_free_before_fit_bytes": before.get("disk_free_bytes"),
            "disk_free_after_run_bytes": after.get("disk_free_bytes"),
            "cuda_free_bytes_before_fit": before.get("gpu_free_bytes_before_fit"),
            "ram_plan_scenario_is_measured": False,
        })
    return result


def _contrast_rows(run: dict) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    state = run["state"]
    category = state["category"]
    seed = int(state["seed"])
    pooled_rows: list[dict] = []
    paired_rows: list[dict] = []
    bootstrap_rows: list[dict] = []
    defect_rows: list[dict] = []
    effects: list[tuple[str, str, str, str]] = []

    # Bank-domain contrasts hold the restored/bicubic query fixed.
    for query in study.QUERY_DOMAINS:
        effects.append(("bank_domain", "swinir_restored_minus_clean", query, "same_query"))
    # Query-domain contrasts hold the normal bank fixed.
    for bank in study.BANK_DOMAINS:
        effects.append(("query_domain", "swinir_x4_minus_bicubic_x4", bank, "same_bank"))

    for contrast_type, contrast_name, fixed_domain, pairing in effects:
        if contrast_type == "bank_domain":
            left_key = ("clean", fixed_domain)
            right_key = ("swinir_restored", fixed_domain)
            left_label, right_label = "clean", "swinir_restored"
            pooled_metric = "pooled_aupro_at_0_3"
        else:
            left_key = (fixed_domain, "bicubic_x4")
            right_key = (fixed_domain, "swinir_x4")
            left_label, right_label = "bicubic_x4", "swinir_x4"
            pooled_metric = "pooled_aupro_at_0_3"
        left_summary = run["summary"][left_key]
        right_summary = run["summary"][right_key]
        pooled_delta = _float(right_summary[pooled_metric]) - _float(left_summary[pooled_metric])
        pooled_rows.append({
            "category": category,
            "seed": seed,
            "contrast_type": contrast_type,
            "contrast": contrast_name,
            "fixed_domain": fixed_domain,
            "baseline": left_label,
            "comparison": right_label,
            "metric": "pooled_aupro_at_0_3",
            "baseline_value": _float(left_summary[pooled_metric]),
            "comparison_value": _float(right_summary[pooled_metric]),
            "delta": pooled_delta,
            "uncertainty": "point_estimate_only",
        })
        anomaly_deltas: list[float] = []
        defect_groups: dict[str, list[float]] = {}
        for sample in run["samples"]:
            left = run["per_image"][left_key][sample]
            right = run["per_image"][right_key][sample]
            if left["label"] != right["label"] or left["defect_type"] != right["defect_type"]:
                raise ValueError("Paired predictions disagree on sample label or defect type")
            if left["label"] == "0":
                continue
            delta = _float(right["per_image_aupro"]) - _float(left["per_image_aupro"])
            anomaly_deltas.append(delta)
            defect_groups.setdefault(left["defect_type"], []).append(delta)
            paired_rows.append({
                "category": category,
                "seed": seed,
                "contrast_type": contrast_type,
                "contrast": contrast_name,
                "fixed_domain": fixed_domain,
                "sample": sample,
                "defect_type": left["defect_type"],
                "baseline_per_image_aupro": _float(left["per_image_aupro"]),
                "comparison_per_image_aupro": _float(right["per_image_aupro"]),
                "delta": delta,
            })
        bootstrap_seed = (seed * 1_000_003 + zlib.crc32(
            f"{category}:{contrast_type}:{fixed_domain}".encode("utf-8")
        )) & 0xFFFFFFFF
        ci = paired_mean_bootstrap_ci(anomaly_deltas, seed=bootstrap_seed)
        bootstrap_rows.append({
            "category": category,
            "seed": seed,
            "contrast_type": contrast_type,
            "contrast": contrast_name,
            "fixed_domain": fixed_domain,
            "estimand": "mean_paired_per_anomalous_image_aupro_delta",
            **ci,
        })
        for defect_type, values in sorted(defect_groups.items()):
            array = np.asarray(values, dtype=np.float64)
            defect_rows.append({
                "category": category,
                "seed": seed,
                "contrast_type": contrast_type,
                "contrast": contrast_name,
                "fixed_domain": fixed_domain,
                "defect_type": defect_type,
                "anomalous_image_count": int(array.size),
                "mean_per_image_aupro_delta": float(array.mean()),
                "median_per_image_aupro_delta": float(np.median(array)),
                "negative_delta_count": int(np.count_nonzero(array < 0)),
                "zero_delta_count": int(np.count_nonzero(array == 0)),
                "positive_delta_count": int(np.count_nonzero(array > 0)),
            })
    return pooled_rows, paired_rows, bootstrap_rows, defect_rows


def analyze(run_dirs: list[Path], output_dir: Path) -> Path:
    if output_dir.exists():
        raise FileExistsError(f"Analysis output already exists and will not be overwritten: {output_dir}")
    runs = [_load_run(path) for path in run_dirs]
    identities = [(run["state"]["category"], int(run["state"]["seed"])) for run in runs]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate category/seed run supplied")
    by_category: dict[str, list[dict]] = {}
    for run in runs:
        by_category.setdefault(run["state"]["category"], []).append(run)
    for category, category_runs in by_category.items():
        reference = category_runs[0]["samples"]
        if any(run["samples"] != reference for run in category_runs[1:]):
            raise ValueError(f"{category}: test inventory/order differs across seeds")

    pooled_rows: list[dict] = []
    paired_rows: list[dict] = []
    bootstrap_rows: list[dict] = []
    defect_rows: list[dict] = []
    quality_rows: list[dict] = []
    calibration_rows: list[dict] = []
    runtime_rows: list[dict] = []
    for run in runs:
        pooled, paired, bootstrap, defect = _contrast_rows(run)
        pooled_rows.extend(pooled)
        paired_rows.extend(paired)
        bootstrap_rows.extend(bootstrap)
        defect_rows.extend(defect)
        calibration_rows.extend(_calibration_rows(run))
        runtime_rows.extend(_runtime_rows(run))
        quality = run["quality"]
        psnr_bicubic = [_quality_float(row["psnr_bicubic"]) for row in quality]
        psnr_swinir = [_quality_float(row["psnr_swinir"]) for row in quality]
        ssim_bicubic = [_quality_float(row["ssim_bicubic"]) for row in quality]
        ssim_swinir = [_quality_float(row["ssim_swinir"]) for row in quality]
        quality_rows.append({
            "category": run["state"]["category"],
            "seed": int(run["state"]["seed"]),
            "test_count": len(quality),
            "mean_psnr_bicubic": _quality_mean(psnr_bicubic),
            "mean_psnr_swinir": _quality_mean(psnr_swinir),
            "mean_psnr_swinir_minus_bicubic": _quality_delta_mean(psnr_swinir, psnr_bicubic),
            "mean_psnr_delta_unavailable_count": sum(
                np.isposinf(left) and np.isposinf(right)
                for left, right in zip(psnr_bicubic, psnr_swinir, strict=True)
            ),
            "mean_ssim_bicubic": _quality_mean(ssim_bicubic),
            "mean_ssim_swinir": _quality_mean(ssim_swinir),
            "mean_ssim_swinir_minus_bicubic": _quality_delta_mean(ssim_swinir, ssim_bicubic),
            "quality_computed_once_per_test_sample": True,
        })

    seed_summary: list[dict] = []
    grouping: dict[tuple[str, str, str], list[float]] = {}
    for row in pooled_rows:
        key = (row["category"], row["contrast_type"], row["contrast"] + ":" + row["fixed_domain"])
        grouping.setdefault(key, []).append(float(row["delta"]))
    for (category, contrast_type, condition), values in sorted(grouping.items()):
        array = np.asarray(values, dtype=np.float64)
        seed_summary.append({
            "category": category,
            "contrast_type": contrast_type,
            "contrast_and_fixed_domain": condition,
            "seed_count": int(array.size),
            "mean_pooled_aupro_delta_across_seeds": float(array.mean()),
            "sd_across_seeds_descriptive_only": float(array.std(ddof=1)) if array.size > 1 else None,
            "unit": "fixed_seed_run; repeated test images are not independent samples",
        })

    output_dir.mkdir(parents=True, exist_ok=False)
    for name, rows in (
        ("pooled_metric_contrasts.csv", pooled_rows),
        ("paired_anomalous_image_deltas.csv", paired_rows),
        ("per_image_mean_bootstrap.csv", bootstrap_rows),
        ("defect_type_descriptive.csv", defect_rows),
        ("normal_calibration_summary.csv", calibration_rows),
        ("runtime_resources.csv", runtime_rows),
        ("query_quality_summary.csv", quality_rows),
        ("seed_summary.csv", seed_summary),
    ):
        _write_csv(output_dir / name, rows)

    extremes: list[dict] = []
    grouped_pairs: dict[tuple[str, int, str, str, str], list[dict]] = {}
    for row in paired_rows:
        key = (row["category"], row["seed"], row["contrast_type"], row["contrast"], row["fixed_domain"])
        grouped_pairs.setdefault(key, []).append(row)
    for key, values in sorted(grouped_pairs.items()):
        values = sorted(values, key=lambda row: (float(row["delta"]), row["sample"]))
        for rank, row in enumerate(values[:5], 1):
            extremes.append({**row, "side": "most_negative", "rank": rank})
        for rank, row in enumerate(reversed(values[-5:]), 1):
            extremes.append({**row, "side": "most_positive", "rank": rank})
    _write_csv(output_dir / "per_image_extremes.csv", extremes)

    provenance = {
        "schema_version": 1,
        "input_runs": [
            {
                "run_dir": str(run["path"]),
                "run_id": run["state"].get("run_id"),
                "category": run["state"]["category"],
                "seed": run["state"]["seed"],
                "status": run["state"]["status"],
                "artifact_manifest": run["state"]["artifacts"],
            }
            for run in runs
        ],
        "fixed_seeds": list(study.SEEDS),
        "primary_metric": "pooled_aupro_at_0_3_point_estimate",
        "per_image_uncertainty": {
            "estimand": "mean paired per-anomalous-image AU-PRO delta",
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "confidence_interval": "percentile 95%",
        },
        "pooled_aupro_confidence_interval": "not computed; per-image CI is not a pooled metric CI",
        "contrast_separation": "bank-domain and query-domain deltas are reported in separate rows",
        "capsule_history_receipt": "required before Capsule execution; not established by this analyzer",
    }
    provenance_path = output_dir / "analysis.json"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                               encoding="utf-8")
    file_hashes = {
        path.name: study.sha256_file(path)
        for path in sorted(output_dir.iterdir()) if path.is_file()
    }
    (output_dir / "SHA256SUMS.json").write_text(
        json.dumps(file_hashes, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return output_dir


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True,
                        help="complete category/seed run directory; repeat per run")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = analyze(args.run_dir, args.output_dir)
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED_OR_FAILED", "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 1
    print(json.dumps({"status": "COMPLETE", "analysis_dir": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
