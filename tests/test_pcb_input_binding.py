from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from sr_anomaly import pcb_input_binding as binding
from sr_anomaly.tiled_cpu_pipeline import Parent


@pytest.fixture
def files(tmp_path, monkeypatch):
    from sr_anomaly import pcb_tiled_runner
    # These generated four-board fixtures are tiny; never authorizes native allocations.
    monkeypatch.setattr(pcb_tiled_runner, "available_ram", lambda: 64 * 1024**3)
    root, data = tmp_path / "repo", tmp_path / "data"
    directory = root / binding.GEOMETRY
    directory.mkdir(parents=True)
    (data / "split_csv").mkdir(parents=True)
    official = data / "split_csv/1cls.csv"
    official.write_bytes(b"synthetic fixture official CSV\n")
    protocol = {"official_csv_sha256": hashlib.sha256(official.read_bytes()).hexdigest()}
    (directory / "PROTOCOL.json").write_text(json.dumps(protocol), encoding="utf-8")
    for name in ("MANIFEST.json", "INPUTS.csv", "layouts.json"):
        (directory / name).write_text("synthetic fixture reference", encoding="utf-8")
    for name in binding.CODE:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic code hash fixture", encoding="utf-8")
    parents = tuple(Parent(name + ".png", split, label, (336, 224))
        for name, split, label in (("fit", "fit", 0), ("cal", "calibration", 0),
                                   ("normal", "test", 0), ("anomaly", "test", 1)))
    y, x = np.indices((224, 336))
    rgb = np.stack((x % 256, y % 256, (x + y) % 256), axis=-1).astype(np.uint8)
    mask = np.zeros((224, 336), np.uint8)
    mask[0, 0] = 17
    mask[40:42, 70:73] = 255
    Image.fromarray(mask).save(data / "gt.png")
    rows = []
    for p in parents:
        Image.fromarray(rgb).save(data / p.sample)
        rows.append(dict(sample=p.sample, image_sha256=binding.file_sha256(data / p.sample),
            mask="gt.png" if p.label else "", mask_sha256=binding.file_sha256(data / "gt.png") if p.label else ""))
    manifest = {"partitions": binding.PARTITIONS, "geometry_id": "synthetic-loader-unit-fixture"}
    # The existing inventory validator owns hash/split validation; isolate callbacks here.
    monkeypatch.setattr(binding, "load_inventory", lambda path: (parents, rows, manifest))
    monkeypatch.setattr(binding.subprocess, "check_output", lambda args, **kw: "fixture-source\n" if "rev-parse" in args else "")
    return root, data, parents, rows, rgb, mask, manifest


def test_constructor_and_default_preflight_never_decode_rgb_or_gt(files, monkeypatch):
    root, data, *_ = files
    monkeypatch.setattr(Image, "open", lambda *a, **k: pytest.fail("RGB/GT decoded in preflight"))
    state, output = binding.audit(root, "metadata", data)
    assert state["status"] == "PREFLIGHT_PASS" and not state["execute_requested"]
    assert not list(output.glob("*.csv"))
    assert not state["model_execution"] and not state["metrics_exported"] and not state["full_pilot_approved"]


def test_rgb_and_test_mask_are_native_exact_and_receipted(files):
    root, data, parents, _, rgb, mask, _ = files
    inputs = binding.FrozenPCBInputs(root, data)
    for parent in parents:
        assert np.array_equal(inputs.rgb(parent), rgb)
    assert inputs.gt_receipts == {}
    normal = inputs.evaluation_mask(parents[2])
    anomaly = inputs.evaluation_mask(parents[3])
    assert normal.dtype == bool and not normal.any()
    assert np.array_equal(anomaly, mask > 0)
    assert inputs.gt_receipts[parents[2].sample]["source"] == "implicit_zero_no_file"
    assert inputs.gt_receipts[parents[2].sample]["file_sha256"] is None
    assert inputs.gt_receipts[parents[3].sample]["file_sha256"] == binding.file_sha256(data / "gt.png")
    receipt = inputs.rgb_receipts[parents[0].sample]
    assert receipt["decoded_rgb_sha256"] == hashlib.sha256(rgb).hexdigest()
    assert receipt["coordinate_transform"] == "identity_no_exif_transpose"


@pytest.mark.parametrize("change", [dict(split="calibration"), dict(label=0), dict(size_wh=(224, 336)), dict(sample="unknown.png")])
def test_frozen_parent_identity_rejected_before_io(files, monkeypatch, change):
    root, data, parents, *_ = files
    inputs = binding.FrozenPCBInputs(root, data)
    monkeypatch.setattr(Path, "read_bytes", lambda *a: pytest.fail("Foreign parent reached IO"))
    for loader in (inputs.rgb, inputs.evaluation_mask):
        with pytest.raises(ValueError, match="Parent differs"):
            loader(replace(parents[3], **change))


def test_gt_is_never_accepted_for_fit_or_calibration(files, monkeypatch):
    root, data, parents, *_ = files
    inputs = binding.FrozenPCBInputs(root, data)
    monkeypatch.setattr(Path, "read_bytes", lambda *a: pytest.fail("GT read outside test phase"))
    for parent in parents[:2]:
        with pytest.raises(ValueError, match="test evaluation"):
            inputs.evaluation_mask(parent)
    assert inputs.gt_receipts == {}


@pytest.mark.parametrize("domain", ["rgb", "gt", "official", "metadata"])
def test_source_and_binding_mutation_rejected(files, domain):
    root, data, parents, *_ = files
    inputs = binding.FrozenPCBInputs(root, data)
    if domain == "rgb":
        (data / parents[0].sample).write_bytes(b"changed")
        call = lambda: inputs.rgb(parents[0])
    elif domain == "gt":
        (data / "gt.png").write_bytes(b"changed")
        call = lambda: inputs.evaluation_mask(parents[3])
    else:
        path = data / "split_csv/1cls.csv" if domain == "official" else root / binding.GEOMETRY / "INPUTS.csv"
        path.write_bytes(b"changed")
        call = inputs.verify_references
    with pytest.raises(ValueError, match="hash mismatch|metadata changed"):
        call()


def test_rgb_decodes_verified_snapshot_not_a_second_file_open(files, monkeypatch):
    root, data, parents, _, rgb, *_ = files
    inputs = binding.FrozenPCBInputs(root, data)
    original = Path.read_bytes
    target = data / parents[0].sample
    reads = []
    def changing(path):
        raw = original(path)
        if path == target:
            reads.append(True)
            path.write_bytes(b"different bytes after verified snapshot")
        return raw
    monkeypatch.setattr(Path, "read_bytes", changing)
    assert np.array_equal(inputs.rgb(parents[0]), rgb)
    assert len(reads) == 1


@pytest.mark.parametrize("domain", ["rgb", "gt_shape", "gt_empty"])
def test_native_shape_and_nonempty_anomaly_guards(files, domain):
    root, data, parents, rows, *_ = files
    if domain == "rgb":
        Image.fromarray(np.zeros((20, 30, 3), np.uint8)).save(data / parents[0].sample)
        rows[0]["image_sha256"] = binding.file_sha256(data / parents[0].sample)
    else:
        values = np.ones((20, 30), np.uint8) if domain == "gt_shape" else np.zeros((224, 336), np.uint8)
        Image.fromarray(values).save(data / "gt.png")
        rows[3]["mask_sha256"] = binding.file_sha256(data / "gt.png")
    inputs = binding.FrozenPCBInputs(root, data)
    with pytest.raises(ValueError, match="shape|Empty anomaly"):
        inputs.rgb(parents[0]) if domain == "rgb" else inputs.evaluation_mask(parents[3])


def test_unsafe_mask_path_and_wrong_partition_manifest_refused(files):
    root, data, _, rows, *_, manifest = files
    manifest["partitions"] = {}
    with pytest.raises(ValueError, match="721/180/200"):
        binding.FrozenPCBInputs(root, data)
    manifest["partitions"] = binding.PARTITIONS
    rows[3]["mask"] = "../outside.png"
    with pytest.raises(ValueError, match="Unsafe source"):
        binding.FrozenPCBInputs(root, data)


def test_audit_success_and_overwrite_failure_and_memory_gate(files, monkeypatch):
    root, data, *_ = files
    state, output = binding.audit(root, "complete", data, execute=True)
    assert state["status"] == "INPUT_BINDING_VALIDATED_NOT_FULL_APPROVAL"
    assert state["rgb_count"] == 4 and state["test_mask_count"] == 2 and state["actual_mask_files"] == 1
    assert state["four_connected_region_mask_payload_bytes"] == 2 * 224 * 336
    for name, digest in state["receipt_sha256"].items():
        assert binding.file_sha256(output / name) == digest
    with pytest.raises(FileExistsError):
        binding.audit(root, "complete", data, execute=True)
    def blocked(*a, **k):
        raise MemoryError("BLOCKED_MEMORY: test fixture")
    monkeypatch.setattr(binding, "_budget", blocked)
    with pytest.raises(MemoryError):
        binding.audit(root, "blocked", data, execute=True)
    failed = json.loads((root / "outputs/pcb-input-binding/blocked/status.json").read_text(encoding="utf-8"))
    assert failed["status"] == "BLOCKED_MEMORY" and not failed["full_pilot_approved"]


def test_bound_files_connect_existing_fake_producer_quality_and_evaluator(files, tmp_path):
    from scripts.check_pcb_board_pipeline import FakeAdapter
    from sr_anomaly import pcb_board_analysis as board
    from sr_anomaly import pcb_full_producer as producer

    root, data, *_ = files
    inputs = binding.FrozenPCBInputs(root, data)
    raw = tmp_path / "integration/raw"
    producer.produce(inputs.parents, inputs.rgb, lambda: (FakeAdapter(), lambda tile, v: tile.copy()), raw,
        provenance={"input_kind": "synthetic", "fixture": "generated_files_binding_only"},
        patch_shape=(2, 2), dimension=4, capacity=7)
    assert not inputs.gt_receipts  # Producer never received the GT callback.
    cal, norm, quality = tmp_path / "cal", tmp_path / "norm", tmp_path / "quality"
    board.fit_calibration(raw, cal)
    board.apply_calibration(raw, cal, norm)
    spool = producer.RGBSpool(raw)
    board.quality_report(inputs.parents, spool.reference, spool.tiles, quality, provenance={"input_kind": "synthetic"})
    assert not inputs.gt_receipts
    result = board.evaluate_variant(raw, cal, norm, "clean", inputs.evaluation_mask, tmp_path / "eval")
    assert result["status"] == "COMPLETE" and len(inputs.gt_receipts) == 2


def test_hash_only_audit_never_decodes_or_uses_array_budget(files, monkeypatch):
    root, data, *_ = files
    monkeypatch.setattr(Image, "open", lambda *a, **k: pytest.fail("Decode in hash-only audit"))
    monkeypatch.setattr(binding, "_budget", lambda *a, **k: pytest.fail("Native array budget in hash-only audit"))
    state, output = binding.audit(root, "hash-only", data, execute=True, hashes_only=True)
    assert state["status"] == "FILE_HASHES_VALIDATED_DECODE_PENDING_NOT_FULL_APPROVAL"
    assert not state["decode_validated"] and not state["full_pilot_approved"]
    assert state["rgb_hash_count"] == 4 and state["test_mask_hash_count"] == 2
    assert "four_connected_region_mask_payload_bytes" not in state
    assert "False" in (output / "gt_binding.csv").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="explicit execute"):
        binding.audit(root, "not-authorized", data, hashes_only=True)


def test_hash_only_rejects_changed_files_without_partial_success(files):
    root, data, parents, *_ = files
    (data / parents[0].sample).write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        binding.audit(root, "changed-hash", data, execute=True, hashes_only=True)
    state = json.loads((root / "outputs/pcb-input-binding/changed-hash/status.json").read_text(encoding="utf-8"))
    assert state["status"] == "FAILED" and not state["decode_validated"]


def test_cli_distinguishes_memory_gate_from_success(monkeypatch, capsys):
    from scripts import check_pcb_input_binding as cli
    def blocked(*a, **k):
        raise MemoryError("fixed reserve retained")
    monkeypatch.setattr(cli, "audit", blocked)
    assert cli.main(["--run-id", "unit", "--data-root", "unit-fixture", "--execute"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED_MEMORY"
    with pytest.raises(SystemExit):
        cli.main(["--run-id", "unit", "--data-root", "unit-fixture", "--hashes-only"])
