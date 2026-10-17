import csv
import json

import numpy as np
from PIL import Image
import pytest

from scripts.prepare_pcb_geometry import audit, partitions_for, sha
from sr_anomaly.dataset import VisASplitCSV
from sr_anomaly.fusion import split_train_calibration


def make_official_fixture(tmp_path):
    data, reference = tmp_path / "visa", tmp_path / "reference"
    (data / "split_csv").mkdir(parents=True)
    reference.mkdir()
    rows = []
    for index in range(8):
        split = "train" if index < 5 else "test"
        anomalous = index >= 6
        path = f"pcb2/{index:03d}.png"
        mask_path = f"pcb2/{index:03d}-mask.png" if anomalous else ""
        (data / path).parent.mkdir(exist_ok=True)
        Image.new("RGB", (448, 224), (index * 29, index * 17, 20)).save(data / path)
        if anomalous:
            mask = np.zeros((224, 448), dtype=np.uint8)
            mask[30:40, 30:40] = 1
            if index == 7:
                mask[100, 100] = 1
            Image.fromarray(mask).save(data / mask_path)
        rows.append(["pcb2", split, "anomaly" if anomalous else "normal", path, mask_path])
    official = data / "split_csv/1cls.csv"
    with official.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["object", "split", "label", "image", "mask"])
        writer.writerows(rows)
    train = VisASplitCSV(data, official, "train", "pcb2").samples()
    fit, cal = split_train_calibration(len(train), .8, 11)
    groups = {"fit": [train[i] for i in fit], "calibration": [train[i] for i in cal],
              "test": VisASplitCSV(data, official, "test", "pcb2").samples()}
    prior = {"official_csv_sha256": sha(official), "seed": 11, "ratio": .8,
             "partition_paths": {name: [s.relative_path.as_posix() for s in items] for name, items in groups.items()},
             "composition": {name: {"normal": sum(s.metadata["label"] == 0 for s in items),
                                     "anomaly": sum(s.metadata["label"] == 1 for s in items)} for name, items in groups.items()}}
    (reference / "PCB_SPLIT_AUDIT.json").write_text(json.dumps(prior), encoding="utf-8")
    with (reference / "PCB_CROP_AUDIT.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["lost_defect_pixels", "components_fully_removed"])
        writer.writeheader()
        writer.writerow({"lost_defect_pixels": 0, "components_fully_removed": 0})
    return data, reference, prior


def test_cpu_audit_tracks_source_aliasing_and_preserves_inputs(tmp_path):
    data, reference, prior = make_official_fixture(tmp_path)
    original = {p.relative_to(data).as_posix(): sha(p) for p in data.rglob("*") if p.is_file()}
    out = tmp_path / "audit"
    result = audit(data, out, reference)
    assert result["status"] == "BLOCKED_GEOMETRY"
    assert result["all_input_images_geometry_checked"] == 8 and result["anomalous_gt_checked"] == 2
    assert result["empty_target_anomaly_images"] == 0 and result["lost_source_components"] == 1
    manifest = json.loads((out / "MANIFEST.json").read_text())
    assert manifest["protocol_sha256"] == sha(out / "PROTOCOL.json")
    assert manifest["inputs_csv_sha256"] == sha(out / "INPUTS.csv")
    assert manifest["partitions"] == prior["composition"]
    assert not manifest["pcb_bank"]["reuse_hazelnut_bank"]
    with (out / "INPUTS.csv").open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    assert len(records) == 8 and {r["partition"] for r in records} == {"fit", "calibration", "test"}
    assert (out / "figures/geometry_examples.png").is_file()
    assert {p.relative_to(data).as_posix(): sha(p) for p in data.rglob("*") if p.is_file()} == original
    with pytest.raises(FileExistsError):
        audit(data, out, reference)


def test_split_reference_change_is_rejected(tmp_path):
    data, reference, prior = make_official_fixture(tmp_path)
    prior["partition_paths"]["fit"].reverse()
    with pytest.raises(ValueError, match="paths changed"):
        partitions_for(data, prior)
    prior["official_csv_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="split/seed/ratio"):
        partitions_for(data, prior)
