from pathlib import Path
import csv
import json

import numpy as np
import pytest

from scripts import analyze_restoration_endpoint_full as analysis


def test_bootstrap_is_paired_and_deterministic() -> None:
    deltas = np.array([-0.02, 0.01, 0.03, 0.04])
    first = analysis.bootstrap(deltas)
    assert first == analysis.bootstrap(deltas)
    assert first["estimate"] == pytest.approx(0.015)
    assert first["ci95"][0] <= first["estimate"] <= first["ci95"][1]
    assert (first["repeats"], first["seed"], first["n"]) == (5000, 2026, 4)


def test_wilson_intervals() -> None:
    low, high = analysis.wilson(5, 10)
    assert (low, high) == pytest.approx((0.236593090512564, 0.763406909487436))
    assert analysis.wilson(0, 10)[0] == pytest.approx(0)
    assert analysis.wilson(10, 10)[1] == pytest.approx(1)
    with pytest.raises(ValueError):
        analysis.wilson(11, 10)


def test_magnitude_grid_uses_strict_inequalities() -> None:
    deltas = np.array([-0.05, -0.02, -0.01, -0.005, 0.0, 0.01])
    assert analysis.TAUS == (0.0, 0.005, 0.01, 0.02, 0.05)
    assert [analysis.magnitude(deltas, tau)[0] for tau in analysis.TAUS] == [4, 3, 2, 1, 0]
    assert analysis.magnitude(deltas, 0.01)[1] == pytest.approx(2 / 6)


def test_endpoint_sign_counts() -> None:
    summary = analysis.sign_summary(np.array([-0.01, 0.0, 0.02, 0.04]))
    assert (summary["esrgan_wins"], summary["psnr_wins"], summary["ties"]) == (2, 1, 1)
    assert (summary["mean"], summary["median"], summary["min"], summary["max"]) == pytest.approx((0.0125, 0.01, -0.01, 0.04))


def test_pilot_overlap_partition_is_frozen() -> None:
    full = {f"image-{i:02d}" for i in range(70)}
    pilot = {f"image-{i:02d}" for i in range(20)}
    overlap, unseen = analysis.partition_anomalies(full, pilot, expected=True)
    assert (len(overlap), len(unseen)) == (20, 50)
    with pytest.raises(ValueError, match="70/20/50"):
        analysis.partition_anomalies(full, {"image-00"}, expected=True)


def test_taxonomy_base_rates_have_both_denominators() -> None:
    rows = [
        {"variant": "swinir_x4", "delta_per_image_aupro": "-0.1", "delta_roi_bg_gap": "-0.2"},
        {"variant": "swinir_x4", "delta_per_image_aupro": "-0.1", "delta_roi_bg_gap": "0.2"},
        {"variant": "swinir_x4", "delta_per_image_aupro": "0", "delta_roi_bg_gap": "-0.1"},
        {"variant": "swinir_x4", "delta_per_image_aupro": "0.1", "delta_roi_bg_gap": "0.1"},
    ]
    regression, non_regression = analysis.taxonomy_base_rates(rows, "swinir_x4")
    assert (regression["count"], regression["negative_gap_count"], regression["negative_gap_rate"]) == (2, 1, 0.5)
    assert (non_regression["count"], non_regression["negative_gap_count"], non_regression["negative_gap_rate"]) == (2, 1, 0.5)


def test_final_case_requires_unseen50_direction_and_describes_b() -> None:
    assert analysis.classify_case(0.01, 0.01, (0.001, 0.03), 0.01) == "A"
    assert analysis.classify_case(-0.01, -0.01, (-0.03, -0.001), -0.01) == "C"
    assert analysis.classify_case(0.01, 0.01, (0.001, 0.03), -0.01) == "B"
    assert analysis.classify_case(-0.01, -0.01, (-0.03, -0.001), 0.0) == "B"
    assert analysis.classify_case(0.01, 0.01, (-0.001, 0.03), 0.01) == "B"
    assert analysis.classify_case(0.01, -0.01, (-0.03, -0.001), 0.01) == "B"
    assert analysis.classify_case(0.0, 0.01, (0.001, 0.03), 0.01) == "B"
    assert analysis.b_description((-0.01, 0.01)) == "B-small"
    assert analysis.b_description((-0.010001, 0.01)) == "B-uncertain"
    assert analysis.b_description((-0.005, 0.010001)) == "B-uncertain"


def test_delta_distribution_near_zero_is_inclusive() -> None:
    result = analysis.delta_distribution(np.array([-0.02, -0.01, 0, 0.01, 0.03]))
    assert result["absolute_delta_le_0_01_count"] == 3
    assert result["absolute_delta_le_0_01_rate"] == 0.6
    assert (result["minimum"], result["q25"], result["median"], result["q75"], result["maximum"]) == pytest.approx((-0.02, -0.01, 0, 0.01, 0.03))


def test_all_test_partition_has_85_unseen_images() -> None:
    full = {f"sample-{i:03d}" for i in range(110)}
    pilot = {f"sample-{i:03d}" for i in range(25)}
    assert len(analysis.partition_test_images(full, pilot)) == 85
    with pytest.raises(ValueError, match="110/25/85"):
        analysis.partition_test_images(full, pilot | {"not-in-full"})


def test_baseline_terciles_are_23_23_24_with_lexical_ties() -> None:
    values = {f"sample-{i:03d}": 0.8 for i in reversed(range(70))}
    groups = analysis.baseline_terciles(values)
    assert [len(paths) for _, paths in groups] == [23, 23, 24]
    assert [path for _, paths in groups for path in paths] == sorted(values)
    values["sample-069"] = 0.1
    assert analysis.baseline_terciles(values)[0][1][0] == "sample-069"


def test_taxonomy_contingency_exposes_all_four_cells() -> None:
    rates = [{"variant": "model", "count": 3, "negative_gap_count": 2},
             {"variant": "model", "count": 5, "negative_gap_count": 4}]
    assert analysis.taxonomy_contingency(rates) == {
        "variant": "model", "regression_gap_negative": 2, "regression_gap_nonnegative": 1,
        "non_regression_gap_negative": 4, "non_regression_gap_nonnegative": 1,
    }


def test_overlap_metric_check_reports_mismatches() -> None:
    sample = "hazelnut/test/crack/000.png"
    row = {name: "1" for name in analysis.COMPARE_FIELDS}
    current = {(sample, variant): row.copy() for variant in analysis.VARIANTS}
    reference = {(sample, variant): row.copy() for variant in analysis.VARIANTS}
    assert analysis.overlap_check(current, reference, {sample})["passed"]
    current[(sample, "rrdb_psnr_x4")]["per_image_aupro"] = "1.01"
    report = analysis.overlap_check(current, reference, {sample})
    assert not report["passed"] and report["mismatch_count"] == 1


def test_saved_pilot_artifact_reproduction_without_inference() -> None:
    source = (analysis.ROOT / "scripts" / "analyze_restoration_endpoint_full.py").read_text(encoding="utf-8")
    assert "run_restoration_objective_pilot" not in source
    assert "detector.predict(" not in source and ".restore(" not in source
    run = analysis.ROOT / "analysis" / "restoration_objective_pilot" / "results"
    result, bootstrap, tables, _ = analysis.analyze(run)
    direct = result["direct_per_image_aupro"]
    assert (direct["count"], direct["esrgan_wins"], direct["psnr_wins"], direct["ties"]) == (20, 11, 9, 0)
    assert (direct["mean"], direct["median"], direct["min"], direct["max"]) == pytest.approx((
        0.005228730586261677, 0.00060070251796146, -0.026003721611708497, 0.0781594382510824,
    ))
    assert {row["variant"]: row["regression_count"] for row in tables["regression_intervals"]} == {
        "swinir_x4": 10, "rrdb_psnr_x4": 8, "rrdb_esrgan_x4": 5,
    }
    assert bootstrap == analysis.bootstrap(np.array([row["delta_per_image_aupro_esrgan_minus_psnr"]
        for row in analysis._read_csv(run / "objective_pair_per_image.csv", ("delta_per_image_aupro_esrgan_minus_psnr",))
        if row["label"] == "1"], dtype=float))
    assert result["localization_case"] is None
    assert result["sensitivity_status"].startswith("pilot validation; post-hoc")


def test_analysis_cli_writes_only_derived_files(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    run = analysis.ROOT / "analysis" / "restoration_objective_pilot" / "results"
    analysis.main(["--run-dir", str(run), "--output-dir", str(tmp_path / "derived")])
    names = {path.name for path in (tmp_path / "derived").iterdir()}
    assert {"analysis_summary.json", "endpoint_bootstrap.json", "regression_intervals.csv", "magnitude_sensitivity.csv",
            "endpoint_pair_sensitivity.csv", "taxonomy_base_rates.csv", "quality_localization.csv",
            "taxonomy_contingency.csv", "localization_delta_distribution.csv", "baseline_tercile_regression.csv",
            "per_image_aupro_waterfall.png", "regression_sensitivity.png", "quality_localization_psnr.png",
            "quality_localization_lpips.png"} == names
    assert not any(name.endswith(".npz") for name in names)


def test_synthetic_full_run_uses_all70_and_checks_pilot_overlap(tmp_path: Path) -> None:
    pilot_rows = analysis._unique(analysis._read_csv(analysis.PILOT_RESULTS / "per_image.csv", ("sample", "variant", *analysis.COMPARE_FIELDS)), ("sample", "variant"))
    manifest = analysis._manifest("restoration_objective_full")
    rows, taxonomy, pairs = [], [], []
    for sample in manifest:
        path, label = sample["sample"], sample["label"]
        for variant in analysis.VARIANTS:
            if (path, variant) in pilot_rows:
                row = pilot_rows[(path, variant)].copy()
            else:
                row = {"sample": path, "variant": variant, "label": label, "defect_type": sample["defect_type"],
                       **{field: "1" for field in analysis.COMPARE_FIELDS}}
                row["per_image_aupro"] = "0.5"
                row["roi_bg_gap"] = "1"
            rows.append(row)
        by_variant = {row["variant"]: row for row in rows[-4:]}
        direct = float(by_variant["rrdb_esrgan_x4"]["per_image_aupro"] or 0) - float(by_variant["rrdb_psnr_x4"]["per_image_aupro"] or 0)
        pairs.append({"sample": path, "label": label, "delta_per_image_aupro_esrgan_minus_psnr": direct if label == "1" else ""})
        if label == "1":
            baseline = by_variant["bicubic_x4"]
            for variant in analysis.LEARNED:
                current = by_variant[variant]
                delta = float(current["per_image_aupro"]) - float(baseline["per_image_aupro"])
                gap = float(current["roi_bg_gap"]) - float(baseline["roi_bg_gap"])
                taxonomy.append({"sample": path, "variant": variant, "regression_type":
                                 "improvement_or_tie" if delta >= 0 else "suppression" if gap < 0 else "geometry_candidate",
                                 "delta_per_image_aupro": delta, "delta_roi_bg_gap": gap})

    def write(name: str, values: list[dict]) -> None:
        with (tmp_path / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)

    write("per_image.csv", rows)
    write("regression_taxonomy.csv", taxonomy)
    write("objective_pair_per_image.csv", pairs)
    summary = [{"variant": variant, "test_count": 110, "normal_count": 40, "anomaly_count": 70,
                "mean_psnr": 35 if variant == "rrdb_esrgan_x4" else 40,
                "mean_lpips": 0.05 if variant == "rrdb_esrgan_x4" else 0.1,
                "au_pro": 0.82 if variant == "rrdb_esrgan_x4" else 0.8} for variant in analysis.VARIANTS]
    write("summary.csv", summary)
    (tmp_path / "results.json").write_text(json.dumps({"study": "restoration_objective_full", "sample_count": 110,
        "manifest_sha256": analysis.MANIFESTS["restoration_objective_full"][1],
        "variants": {row["variant"]: {metric: row[metric] for metric in ("au_pro", "mean_psnr", "mean_lpips")} for row in summary}}), encoding="utf-8")
    labels = np.asarray([int(row["label"]) for row in manifest])
    masks = np.zeros((110, 4, 4), dtype=bool)
    masks[labels == 1, 0, 0] = True
    keyed = analysis._unique(rows, ("sample", "variant"))
    for variant in analysis.VARIANTS:
        scores = np.asarray([float(keyed[(row["sample"], variant)]["image_score"]) for row in manifest])
        maps = np.broadcast_to(np.arange(16).reshape(1, 4, 4), masks.shape)
        np.savez(tmp_path / f"{variant}_predictions.npz", labels=labels, scores=scores, masks=masks, maps=maps)
    result, _, tables, _ = analysis.analyze(tmp_path)
    assert result["anomalous_images"] == 70
    assert result["pilot_overlap_reproducibility"]["passed"]
    assert result["pilot_overlap_reproducibility"]["samples"] == 20
    assert result["pilot_unseen_within_category"]["count"] == 50
    assert result["pilot_unseen_within_category"]["ties"] == 50
    assert result["quality_tradeoff_reproduced"]
    assert result["localization_case"] == "B"
    assert result["localization_b_description"] in ("B-small", "B-uncertain")
    assert len(tables["pilot_unseen_confirmation"]) == 4
    assert all((row["test_count"], row["normal_count"], row["anomaly_count"]) == (85, 35, 50) for row in tables["pilot_unseen_confirmation"])
    assert [row["image_count"] for row in tables["baseline_tercile_regression"][:3]] == [23, 23, 24]
    assert len(tables["magnitude_sensitivity"]) == 15
    invalid_labels = labels.copy()
    invalid_labels[0] = 1 - invalid_labels[0]
    np.savez(tmp_path / "swinir_x4_predictions.npz", labels=invalid_labels, scores=scores, masks=masks, maps=maps)
    with pytest.raises(ValueError, match="Invalid saved prediction"):
        analysis.analyze(tmp_path)
