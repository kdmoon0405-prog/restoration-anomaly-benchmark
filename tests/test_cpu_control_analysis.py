import pytest

from sr_anomaly.analysis_io import digest, read_json, write_csv, write_json
from sr_anomaly.cpu_control_analysis import analyze_controls


def make_run(root, seed):
    root.mkdir()
    summary, images = [], []
    for variant, pro in (("clean", 0.9), ("bicubic_x4", 0.5), ("unsharp_x4", 0.45)):
        summary.append(dict(category="tiny", seed=seed, variant=variant,
            au_pro=pro, pixel_auroc=0.6, mean_psnr=30 if variant != "unsharp_x4" else 31,
            mean_ssim=0.8 if variant != "unsharp_x4" else 0.81))
        for label in (0, 1):
            images.append(dict(sample=f"test/{label}.png", label=label, variant=variant,
                per_image_aupro=pro if label else "", roi_bg_gap=pro if label else "",
                rgb_sha256=variant + str(label), psnr=30 if variant != "unsharp_x4" else 31,
                ssim=0.8 if variant != "unsharp_x4" else 0.81))
    write_csv(root / "summary.csv", summary)
    write_csv(root / "per_image.csv", images)
    state = dict(status="EVALUATED_COMPLETE", settings=dict(seed=seed, categories=["tiny"]),
        source_code_sha256="f" * 64, input_inventory_sha256="b" * 64,
        category="tiny", seed=seed, test_count=2,
        artifact_sha256={n: digest(root / n) for n in ("summary.csv", "per_image.csv")})
    write_json(root / "status.json", state)
    return root


def update_images(run, mutate):
    from sr_anomaly.analysis_io import csv_rows
    rows = csv_rows(run / "per_image.csv")
    mutate(rows)
    write_csv(run / "per_image.csv", rows)
    state = read_json(run / "status.json")
    state["artifact_sha256"]["per_image.csv"] = digest(run / "per_image.csv")
    write_json(run / "status.json", state)


def test_seed_dependency_and_quality_dedup(tmp_path):
    a, b = make_run(tmp_path / "a", 11), make_run(tmp_path / "b", 23)
    result = analyze_controls([b, a], tmp_path / "out", expected_seeds=(11, 23), repeats=20)
    assert result["quality_unique_rows"] == 6
    assert result["paired_anomaly_seed_rows"] == 2
    assert result["independent_anomaly_image_units"] == 1
    with pytest.raises(FileExistsError):
        analyze_controls([a, b], tmp_path / "out", expected_seeds=(11, 23), repeats=20)


def test_missing_and_duplicate_run(tmp_path):
    run = make_run(tmp_path / "a", 11)
    with pytest.raises(ValueError, match="matrix"):
        analyze_controls([run], tmp_path / "out", expected_seeds=(11, 23), repeats=20)
    with pytest.raises(ValueError, match="Duplicate"):
        analyze_controls([run, run], tmp_path / "out", expected_seeds=(11,), repeats=20)


def test_normal_aupro_guard(tmp_path):
    run = make_run(tmp_path / "a", 11)
    update_images(run, lambda rows: rows[0].update(per_image_aupro="0.2"))
    with pytest.raises(ValueError, match="Normal"):
        analyze_controls([run], tmp_path / "out", expected_seeds=(11,), repeats=20)


def test_query_identity_across_seeds(tmp_path):
    a, b = make_run(tmp_path / "a", 11), make_run(tmp_path / "b", 23)
    update_images(b, lambda rows: rows[0].update(rgb_sha256="changed"))
    with pytest.raises(ValueError, match="RGB"):
        analyze_controls([a, b], tmp_path / "out", expected_seeds=(11, 23), repeats=20)


def test_separate_fourth_condition_same_bank(tmp_path):
    from sr_anomaly.analysis_io import csv_rows
    base = make_run(tmp_path / "base", 11)
    extra = make_run(tmp_path / "extra", 11)
    for name in ("summary.csv", "per_image.csv"):
        rows = [dict(row, variant="swinir_x4") for row in csv_rows(extra / name)
                if row["variant"] == "unsharp_x4"]
        write_csv(extra / name, rows)
    state = read_json(extra / "status.json")
    state["artifact_sha256"] = {name: digest(extra / name) for name in ("summary.csv", "per_image.csv")}
    write_json(extra / "status.json", state)
    options = dict(expected_seeds=(11,), repeats=20, candidate="swinir_x4",
                   expected_variants=("clean", "bicubic_x4", "unsharp_x4", "swinir_x4"))
    result = analyze_controls([base, extra], tmp_path / "out", **options)
    assert result["quality_unique_rows"] == 8 and result["independent_anomaly_image_units"] == 1
    assert len(result["source_runs"]) == 2
    state["bank_sha256"] = "changed"
    write_json(extra / "status.json", state)
    with pytest.raises(ValueError, match="bank bytes"):
        analyze_controls([base, extra], tmp_path / "bad", **options)
