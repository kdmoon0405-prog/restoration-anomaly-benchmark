from __future__ import annotations

import csv
from enum import Enum
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from sr_anomaly import bank_domain_study as study
from scripts import analyze_bank_domain_study as analyzer
from scripts import run_bank_domain_study as runner


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _artifact_manifest(path: Path) -> dict:
    result = {"file": path.name, "sha256": study.sha256_file(path)}
    if path.suffix == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            result["arrays"] = {name: list(archive[name].shape) for name in archive.files}
    return result


def _make_complete_run(root: Path) -> Path:
    run_dir = root / "run-hazelnut-seed11"
    run_dir.mkdir(parents=True)
    samples = ["hazelnut/test/crack/000.png", "hazelnut/test/good/000.png"]
    calibration = ["hazelnut/train/good/000.png"]
    masks = np.zeros((2, 224, 224), dtype=bool)
    masks[0, 20:25, 20:25] = True
    bank_hashes = {"clean": "a" * 64, "swinir_restored": "b" * 64}
    artifacts = []
    for bank, bank_hash in bank_hashes.items():
        raw_path = run_dir / f"raw_{bank}.npz"
        np.savez_compressed(
            raw_path,
            calibration_samples=np.asarray(calibration),
            test_samples=np.asarray(samples),
            query_domains=np.asarray(study.QUERY_DOMAINS),
            bank_sha256=np.asarray(bank_hash),
            query_input_sha256=np.asarray(["1" * 64, "2" * 64]),
            query_bicubic_sha256=np.asarray(["3" * 64, "4" * 64]),
            query_swinir_sha256=np.asarray(["5" * 64, "6" * 64]),
            calibration_scores=np.ones((1, 2), dtype=np.float64),
            calibration_maps=np.ones((1, 2, 224, 224), dtype=np.float32),
            test_scores=np.ones((2, 2), dtype=np.float64),
            test_maps=np.ones((2, 2, 224, 224), dtype=np.float32),
        )
        artifacts.append(_artifact_manifest(raw_path))

    masks_path = run_dir / "test_masks_for_local_analysis.npz"
    np.savez_compressed(masks_path, samples=np.asarray(samples), masks=masks)
    artifacts.append(_artifact_manifest(masks_path))

    summary_rows = []
    per_image_rows = []
    prediction_rows = []
    cell_values = {
        ("clean", "bicubic_x4"): (0.40, 0.20),
        ("clean", "swinir_x4"): (0.42, 0.25),
        ("swinir_restored", "bicubic_x4"): (0.45, 0.30),
        ("swinir_restored", "swinir_x4"): (0.50, 0.35),
    }
    for bank in study.BANK_DOMAINS:
        for query in study.QUERY_DOMAINS:
            pooled, anomalous_per_image = cell_values[(bank, query)]
            summary_rows.append({
                "category": "hazelnut", "seed": 11, "bank_domain": bank, "query_domain": query,
                "fit_count": 1, "calibration_count": 1, "test_count": 2,
                "image_auroc": 0.9, "image_f1": 0.8, "pixel_auroc": 0.9,
                "pooled_aupro_at_0_3": pooled, "pixel_f1": 0.7,
                "image_threshold": 1.0, "pixel_threshold": 1.0,
            })
            per_image_rows.extend([
                {
                    "sample": samples[0], "label": 1, "normalized_score": 2.0,
                    "per_image_aupro": anomalous_per_image, "category": "hazelnut", "seed": 11,
                    "bank_domain": bank, "query_domain": query, "defect_type": "crack",
                },
                {
                    "sample": samples[1], "label": 0, "normalized_score": 0.0,
                    "per_image_aupro": "", "category": "hazelnut", "seed": 11,
                    "bank_domain": bank, "query_domain": query, "defect_type": "good",
                },
            ])
            prediction_rows.extend([
                {"bank_domain": bank, "query_domain": query, "sample": samples[0]},
                {"bank_domain": bank, "query_domain": query, "sample": samples[1]},
            ])

    for name, rows in (
        ("summary.csv", summary_rows),
        ("per_image.csv", per_image_rows),
        ("query_quality.csv", [
            {"sample": samples[0], "psnr_bicubic": 20.0, "ssim_bicubic": 0.5,
             "psnr_swinir": 22.0, "ssim_swinir": 0.6, "swinir_seconds": 0.1},
            {"sample": samples[1], "psnr_bicubic": 21.0, "ssim_bicubic": 0.6,
             "psnr_swinir": 23.0, "ssim_swinir": 0.7, "swinir_seconds": 0.1},
        ]),
    ):
        path = run_dir / name
        _write_csv(path, rows)
        artifacts.append(_artifact_manifest(path))

    state = {
        "schema_version": study.SCHEMA_VERSION,
        "status": "COMPLETE",
        "scope": "full-category-bank-domain-study",
        "run_id": "fixture",
        "category": "hazelnut",
        "seed": 11,
        "seeds_frozen": list(study.SEEDS),
        "bank_domains": list(study.BANK_DOMAINS),
        "query_domains": list(study.QUERY_DOMAINS),
        "fit_paths": ["hazelnut/train/good/001.png"],
        "calibration_paths": calibration,
        "test_samples": samples,
        "train_input_sha256": {"hazelnut/train/good/001.png": "7" * 64},
        "test_input_sha256": {samples[0]: "8" * 64, samples[1]: "9" * 64},
        "test_mask_paths": {samples[0]: "hazelnut/ground_truth/crack/000_mask.png", samples[1]: None},
        "test_mask_sha256": {samples[0]: "a" * 64, samples[1]: None},
        "fit_count": 1,
        "calibration_count": 1,
        "test_count": 2,
        "bank_hashes": bank_hashes,
        "calibration_by_cell": {
            f"{bank}/{query}": {
                "calibration_count": 1,
                "image": {"median": 1.0, "scale": 1.0, "method": "unit_fallback"},
                "pixel": {"median": 1.0, "scale": 1.0, "method": "unit_fallback"},
                "image_threshold": 0.0,
                "pixel_threshold": 0.0,
            }
            for bank in study.BANK_DOMAINS for query in study.QUERY_DOMAINS
        },
        "runtime": [
            {"bank_domain": bank, "fit_seconds": 1.0, "query_inference_seconds": 2.0,
             "torch_cuda_peak_allocated_bytes": 100, "torch_cuda_peak_reserved_bytes": 200,
             "bank_bytes": 300, "bank_sha256": bank_hashes[bank]}
            for bank in study.BANK_DOMAINS
        ],
        "resource_plan": {"free_disk_before_run_bytes": 1_000},
        "resource_snapshot_before_fit": {"disk_free_bytes": 900, "gpu_free_bytes_before_fit": 800},
        "resource_snapshot_after": {"available_ram_bytes": 700, "disk_free_bytes": 600},
        "available_ram_before_each_bank_bytes": {bank: 500 for bank in study.BANK_DOMAINS},
        "prediction_rows": prediction_rows,
        "artifacts": artifacts,
    }
    input_hashes = {
        **state["train_input_sha256"],
        **state["test_input_sha256"],
        **{f"mask:{sample}": digest for sample, digest in state["test_mask_sha256"].items() if digest},
    }
    state["input_inventory_sha256"] = hashlib.sha256(
        json.dumps(input_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    study.write_status(run_dir, state)
    return run_dir


def test_calibration_uses_only_normal_finite_data_and_evaluation_marks_no_normal_aupro():
    labels = np.zeros(3, dtype=np.uint8)
    scores = np.asarray([0.1, 0.2, 0.4])
    maps = np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
    calibration = study.fit_cell_calibration(labels, scores, maps, quantile=0.9)
    assert calibration["calibration_count"] == 3
    assert calibration["normalization"] == "existing_median_iqr_std_then_unit"

    test_masks = np.zeros((2, 4, 4), dtype=bool)
    test_masks[1, 1:3, 1:3] = True
    metrics, rows = study.evaluate_cell(
        np.asarray([0, 1]), np.asarray([0.1, 2.0]), test_masks,
        np.stack([np.zeros((4, 4)), np.ones((4, 4))]), calibration, ["normal", "defect"],
    )
    assert metrics["localization"]["au_pro"] is not None
    assert rows[0]["per_image_aupro"] is None
    assert rows[1]["per_image_aupro"] is not None


@pytest.mark.parametrize(
    "labels,scores,maps",
    [
        (np.asarray([0, 1]), np.asarray([0.1, 0.2]), np.zeros((2, 2, 2))),
        (np.asarray([0, 0]), np.asarray([0.1]), np.zeros((2, 2, 2))),
        (np.asarray([0, 0]), np.asarray([0.1, np.nan]), np.zeros((2, 2, 2))),
        (np.asarray([0, 0]), np.asarray([0.1, 0.2]), np.full((2, 2, 2), np.inf)),
    ],
)
def test_calibration_rejects_anomaly_mismatch_and_nonfinite(labels, scores, maps):
    with pytest.raises(ValueError):
        study.fit_cell_calibration(labels, scores, maps)


def test_query_pair_identity_and_artifact_path_guards():
    identity = {
        "samples": ["cat/test/a.png"],
        "query_input_sha256": ["a" * 64],
        "query_domains": list(study.QUERY_DOMAINS),
        "query_domain_sha256": {"bicubic_x4": ["b" * 64], "swinir_x4": ["c" * 64]},
    }
    study.validate_pair_identity(identity, dict(identity))
    different = dict(identity, query_input_sha256=["d" * 64])
    with pytest.raises(ValueError, match="query_input_sha256"):
        study.validate_pair_identity(identity, different)
    for unsafe in ("../outside", "C:/outside", "folder\\outside", "/rooted", "bad\0path"):
        with pytest.raises(ValueError):
            study.safe_artifact_path(Path.cwd(), unsafe)


def test_memory_and_disk_plans_keep_fixed_bank_and_reserve():
    plan = study.bank_fit_plan(10, patches_per_image=784, dimension=1024, batch_size=8)
    assert plan["fit_vectors"] == 7_840
    assert plan["bank_bytes"] == 7_840 * 1024 * 4
    study.check_fit_ram(plan, available_bytes=plan["required_available_ram_bytes"])
    with pytest.raises(MemoryError, match="BANK_FIT_BLOCKED_MEMORY"):
        study.check_fit_ram(plan, available_bytes=plan["required_available_ram_bytes"] - 1)

    disk = study.output_disk_plan(3, 4, image_size=224, reserve_bytes=1_000)
    study.check_output_disk(disk, free_bytes=disk["required_free_bytes"])
    with pytest.raises(OSError, match="BANK_STUDY_BLOCKED_DISK"):
        study.check_output_disk(disk, free_bytes=disk["required_free_bytes"] - 1)


def test_complete_run_verifies_order_and_payload_hashes(tmp_path):
    run_dir = tmp_path / "complete"
    run_dir.mkdir()
    expected = study.expected_condition_order(["cat/test/good/1.png"])
    payload = run_dir / "raw.npz"
    np.savez_compressed(payload, value=np.asarray([1.0]))
    state = {
        "schema_version": study.SCHEMA_VERSION,
        "status": "COMPLETE",
        "prediction_rows": [
            {"bank_domain": bank, "query_domain": query, "sample": sample}
            for bank, query, sample in expected
        ],
        "artifacts": [{"file": payload.name, "sha256": study.sha256_file(payload)}],
    }
    study.write_status(run_dir, state)
    assert study.verify_complete_run(run_dir, expected)["status"] == "COMPLETE"
    with pytest.raises(ValueError, match="order"):
        study.verify_complete_run(run_dir, list(reversed(expected)))
    payload.write_bytes(payload.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="changed"):
        study.verify_complete_run(run_dir, expected)


def test_tiny_saved_run_analyzes_bank_and_query_effects_separately(tmp_path):
    run_dir = _make_complete_run(tmp_path)
    output = analyzer.analyze([run_dir], tmp_path / "analysis")
    pooled = list(csv.DictReader((output / "pooled_metric_contrasts.csv").open(encoding="utf-8")))
    assert len(pooled) == 4
    assert {row["contrast_type"] for row in pooled} == {"bank_domain", "query_domain"}
    assert len(list(csv.DictReader((output / "per_image_mean_bootstrap.csv").open(encoding="utf-8")))) == 4
    assert len(list(csv.DictReader((output / "normal_calibration_summary.csv").open(encoding="utf-8")))) == 4
    assert len(list(csv.DictReader((output / "runtime_resources.csv").open(encoding="utf-8")))) == 2
    quality = list(csv.DictReader((output / "query_quality_summary.csv").open(encoding="utf-8")))
    assert len(quality) == 1
    assert quality[0]["quality_computed_once_per_test_sample"] == "True"
    metadata = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
    assert "per-image CI is not a pooled metric CI" in metadata["pooled_aupro_confidence_interval"]


def test_analyzer_rejects_normal_per_image_aupro(tmp_path):
    run_dir = _make_complete_run(tmp_path)
    per_image_path = run_dir / "per_image.csv"
    rows = list(csv.DictReader(per_image_path.open(encoding="utf-8")))
    rows[1]["per_image_aupro"] = "0.2"
    _write_csv(per_image_path, rows)
    state_path = run_dir / "status.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for artifact in state["artifacts"]:
        if artifact["file"] == per_image_path.name:
            artifact["sha256"] = study.sha256_file(per_image_path)
    study.write_status(run_dir, state)
    with pytest.raises(ValueError, match="Normal samples"):
        analyzer._load_run(run_dir)


def test_fake_runner_e2e_preserves_failed_run_and_recovers_without_overwrite(monkeypatch, tmp_path):
    import torch as real_torch
    from PIL import Image
    from torchvision import transforms as tv_transforms
    from torchvision.transforms import InterpolationMode

    data_root = tmp_path / "MVTecAD"
    category = data_root / "hazelnut"
    for folder in (category / "train" / "good", category / "test" / "good",
                   category / "test" / "crack", category / "ground_truth" / "crack"):
        folder.mkdir(parents=True)
    license_path = data_root / "LICENSE.txt"
    license_path.write_text("fixture license text", encoding="utf-8")
    receipt = {
        "dataset": "MVTec AD",
        "source_url": runner.OFFICIAL_MVTEC_AD_URL,
        "categories": ["hazelnut", "screw"],
        "archive_sha256": "a" * 64,
        "license_file": "LICENSE.txt",
        "license_sha256": study.sha256_file(license_path),
    }
    (data_root / "dataset_provenance.json").write_text(json.dumps(receipt), encoding="utf-8")
    for index in range(5):
        pixels = np.full((250, 250, 3), 80 + index * 10, dtype=np.uint8)
        Image.fromarray(pixels, "RGB").save(category / "train" / "good" / f"{index:03}.png")
    Image.fromarray(np.full((250, 250, 3), 95, dtype=np.uint8), "RGB").save(
        category / "test" / "good" / "good.png"
    )
    defect = np.full((250, 250, 3), 100, dtype=np.uint8)
    defect[80:130, 80:130] = 240
    Image.fromarray(defect, "RGB").save(category / "test" / "crack" / "defect.png")
    mask = np.zeros((250, 250), dtype=np.uint8)
    mask[80:130, 80:130] = 255
    Image.fromarray(mask, "L").save(category / "ground_truth" / "crack" / "defect_mask.png")

    class DatasetSplit(Enum):
        TRAIN = "train"

    class FakeMVTecDataset:
        def __init__(self, source, classname, resize, imagesize, split):
            files = sorted((Path(source) / classname / split.value / "good").glob("*.png"))
            self.data_to_iterate = [(classname, "good", str(path), None) for path in files]

        def __len__(self):
            return len(self.data_to_iterate)

    fake_mvtec = SimpleNamespace(
        MVTecDataset=FakeMVTecDataset,
        DatasetSplit=DatasetSplit,
        IMAGENET_MEAN=[0.485, 0.456, 0.406],
        IMAGENET_STD=[0.229, 0.224, 0.225],
    )

    class FakeCuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def manual_seed_all(seed):
            return None

        @staticmethod
        def reset_peak_memory_stats(device):
            return None

        @staticmethod
        def synchronize(device):
            return None

        @staticmethod
        def get_device_name(device):
            return "fake-device-for-CPU-test"

        @staticmethod
        def mem_get_info(device):
            return 4 * 1024**3, 6 * 1024**3

        @staticmethod
        def max_memory_allocated(device):
            return 0

        @staticmethod
        def max_memory_reserved(device):
            return 0

        @staticmethod
        def empty_cache():
            return None

    torch_proxy = SimpleNamespace(
        __version__=real_torch.__version__,
        version=SimpleNamespace(cuda="fake-cuda-for-test"),
        cuda=FakeCuda,
        device=real_torch.device,
        manual_seed=real_torch.manual_seed,
        zeros=real_torch.zeros,
        set_num_threads=real_torch.set_num_threads,
        get_num_threads=real_torch.get_num_threads,
        utils=real_torch.utils,
    )
    monkeypatch.setattr(
        runner.branch_b,
        "_official_imports",
        lambda: (torch_proxy, tv_transforms, InterpolationMode, None, None, None, None, fake_mvtec),
    )
    monkeypatch.setattr(runner.branch_b, "resolve_device", lambda requested, available: "cuda")

    class FakeRestorer:
        def __init__(self, *args, **kwargs):
            pass

        def restore(self, image):
            enlarged = np.asarray(image.resize((224, 224), Image.Resampling.BICUBIC), dtype=np.uint16)
            return Image.fromarray(np.minimum(enlarged + 3, 255).astype(np.uint8), "RGB")

    class FakePatchCore:
        def __init__(self):
            self.anomaly_scorer = SimpleNamespace(
                detection_features=np.empty((0, 1024), dtype=np.float32),
                nn_method=SimpleNamespace(reset_index=lambda: None),
            )

        def fit(self, loader):
            means = []
            count = 0
            for batch in loader:
                assert np.all(batch["is_anomaly"].numpy() == 0)
                means.extend(batch["image"].mean(dim=(1, 2, 3)).numpy().tolist())
                count += int(batch["image"].shape[0])
            assert count > 0
            self.bank_mean = float(np.mean(means))
            self.anomaly_scorer.detection_features = np.full(
                (count * 784, 1024), self.bank_mean, dtype=np.float32
            )

    monkeypatch.setattr(study, "available_ram_bytes", lambda: 32 * 1024**3)
    monkeypatch.setattr(runner, "SwinIRLightweight", FakeRestorer)
    monkeypatch.setattr(runner, "_new_patchcore", lambda *args, **kwargs: FakePatchCore())

    def fake_predict(model, tensor, image):
        values = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
        return float(values.mean() + model.bank_mean), values * (1.0 + model.bank_mean)

    monkeypatch.setattr(runner.branch_b, "_predict", fake_predict)
    checkpoint = tmp_path / "synthetic-swinir.pth"
    backbone_checkpoint = tmp_path / "synthetic-backbone.pth"
    checkpoint.write_bytes(b"synthetic-swinir-not-a-model")
    backbone_checkpoint.write_bytes(b"synthetic-backbone-not-a-model")
    monkeypatch.setattr(runner, "EXPECTED_SWINIR_SHA256", study.sha256_file(checkpoint))
    monkeypatch.setattr(runner, "EXPECTED_WIDERESNET_SHA256", study.sha256_file(backbone_checkpoint))

    def fake_command(args, **kwargs):
        if args[0] == "nvidia-smi":
            return "synthetic GPU, synthetic driver, 0 MiB"
        if "status" in args:
            return "?? synthetic-test-fixture\n"
        if any("patchcore-inspection" in str(arg) for arg in args):
            return runner.EXPECTED_PATCHCORE_COMMIT
        return "e" * 40

    monkeypatch.setattr(runner.branch_b, "subprocess", SimpleNamespace(check_output=fake_command))
    base_args = {
        "category": "hazelnut", "seed": 11, "capsule_history_receipt": None,
        "data_root": data_root, "output_root": tmp_path / "outputs",
        "dataset_provenance": data_root / "dataset_provenance.json",
        "backbone_checkpoint": backbone_checkpoint,
        "swinir_checkpoint": checkpoint, "device": "cuda",
    }
    args = SimpleNamespace(**base_args, run_id="fake-failed")
    original_predict = runner.branch_b._predict
    monkeypatch.setattr(runner.branch_b, "_predict", lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("fixture inference failure")
    ))
    with pytest.raises(RuntimeError, match="fixture inference failure"):
        runner.run(args)
    failed_dir = tmp_path / "outputs" / "fake-failed" / "hazelnut" / "seed11"
    failed_state = json.loads((failed_dir / "status.json").read_text(encoding="utf-8"))
    assert failed_state["status"] == "FAILED"
    assert "fixture inference failure" in failed_state["error"]

    monkeypatch.setattr(runner.branch_b, "_predict", original_predict)
    recovered_args = SimpleNamespace(**base_args, run_id="fake-recovered")
    recovered_dir = runner.run(recovered_args)
    recovered_state = json.loads((recovered_dir / "status.json").read_text(encoding="utf-8"))
    assert recovered_state["status"] == "COMPLETE"
    assert len(recovered_state["prediction_rows"]) == 8
    assert recovered_state["bank_hashes"]["clean"] != recovered_state["bank_hashes"]["swinir_restored"]
    analyzed = analyzer.analyze([recovered_dir], tmp_path / "fake-analysis")
    assert (analyzed / "pooled_metric_contrasts.csv").is_file()
    assert failed_state["status"] == "FAILED"
