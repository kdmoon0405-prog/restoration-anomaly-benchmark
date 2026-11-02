"""Tiny generated CSV/JSON artifacts; these are never model prediction evidence."""
from pathlib import Path

from sr_anomaly.analysis_io import digest, read_json, write_csv, write_json
from sr_anomaly.bank_domain_analysis import BANKS, QUERIES


def refresh(directory):
    directory = Path(directory)
    manifest = read_json(directory / "bank_domain_manifest.json")
    manifest["files"] = {n: digest(directory / n) for n in
                         ("summary.csv", "per_image.csv", "config.json", "provenance.json")}
    write_json(directory / "bank_domain_manifest.json", manifest)


def make_run(directory, *, seed=11, category="synthetic_category", geometry="synthetic224"):
    directory = Path(directory)
    directory.mkdir(parents=True)
    config = dict(study_family="synthetic_bank_domain_v1", category=category, seed=seed,
        protocol=dict(dataset="synthetic", geometry_id=geometry, degradation_id="synthetic_x4",
            detector_id="fake", restorer_id="fake", calibration_source="normal_calibration_only",
            bank_spec=dict(dimension=4, sampler="fake_same_selection"),
            checkpoints_sha256=dict(backbone="1" * 64, swinir="2" * 64),
            metric_definition=dict(primary="pooled_aupro", max_fpr=0.3, num_thresholds=200, connectivity=4)))
    provenance = dict(source_commit="d" * 40, source_worktree_dirty=False,
        normal_fit_calibration_disjoint=True, test_gt_used_for_selection=False,
        input_manifest_sha256="a" * 64, split_manifest_sha256="3" * 64, test_manifest_sha256="b" * 64,
        query_manifest_sha256="e" * 64, bank_manifest_sha256={b: "f" * 64 for b in BANKS},
        bank_vector_counts={b: 8 for b in BANKS},
        code_sha256={"src/fake.py": "c" * 64})
    write_json(directory / "config.json", config)
    write_json(directory / "provenance.json", provenance)
    summaries, images = [], []
    values = {
        ("clean", "bicubic_x4"): (0.71, (0.60, 0.80), (1.0, 1.0)),
        ("clean", "swinir_x4"): (0.73, (0.70, 0.75), (1.2, 0.8)),
        ("swinir_restored", "bicubic_x4"): (0.72, (0.65, 0.78), (1.1, 0.9)),
        ("swinir_restored", "swinir_x4"): (0.76, (0.80, 0.72), (1.3, 0.85))}
    for bank in BANKS:
        for query in QUERIES:
            q = QUERIES.index(query)
            pooled, pro, gap = values[bank, query]
            summaries.append(dict(bank_domain=bank, query_domain=query, n_test=3, n_anomaly=2,
                pooled_aupro=pooled, pixel_auroc=0.90 + 0.01 * q,
                image_auroc=0.85, mean_psnr=30 + 2 * q, mean_ssim=0.9 + 0.02 * q))
            for i, sample in enumerate(("test/good/0.png", "test/crack/0.png", "test/cut/0.png")):
                images.append(dict(sample=sample, defect_type=("good", "crack", "cut")[i],
                    label=int(i > 0), bank_domain=bank, query_domain=query,
                    per_image_aupro="" if not i else pro[i - 1], roi_bg_gap="" if not i else gap[i - 1],
                    psnr=30 + 2 * q, ssim=0.9 + 0.02 * q))
    write_csv(directory / "summary.csv", summaries)
    write_csv(directory / "per_image.csv", list(reversed(images)))  # Order-independent pairing.
    write_json(directory / "bank_domain_manifest.json", dict(schema_version=1,
        kind="bank_domain_study_results", status="COMPLETE", evidence_kind="synthetic_fixture"))
    refresh(directory)
    return directory
