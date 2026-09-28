from pathlib import Path
import json

import numpy as np
from PIL import Image
import pytest

from sr_anomaly.objective_study import build_pilot_manifest, load_pilot_manifest, regression_type, write_pilot_manifest
from sr_anomaly.real_models import ESRGANRRDBX4, matlab_bicubic_resize
from scripts import run_restoration_objective_pilot as pilot


def _paint(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), (value, value, value)).save(path)


def test_manifest_is_lexical_stratified_and_checksum_bound(tmp_path: Path) -> None:
    root = tmp_path / "MVTecAD"
    for defect in ("good", "crack", "cut", "hole", "print"):
        for index in range(6):
            _paint(root / "hazelnut" / "test" / defect / f"{index:03d}.png", index)
            if defect != "good":
                mask = root / "hazelnut" / "ground_truth" / defect / f"{index:03d}_mask.png"
                mask.parent.mkdir(parents=True, exist_ok=True)
                Image.new("L", (16, 16), 255).save(mask)
    rows = build_pilot_manifest(root)
    manifest = tmp_path / "pilot.csv"
    write_pilot_manifest(rows, manifest)
    loaded = load_pilot_manifest(manifest, root)
    assert len(loaded) == 25
    assert [row["sample"] for row in loaded if row["stratum"] == "crack"][-1].endswith("004.png")
    rows[0]["sample"] = "hazelnut/test/good/005.png"
    write_pilot_manifest(rows, manifest)
    with pytest.raises(ValueError, match="selection"):
        load_pilot_manifest(manifest, root)
    write_pilot_manifest(build_pilot_manifest(root), manifest)
    _paint(root / loaded[0]["sample"], 99)
    with pytest.raises(ValueError, match="missing or changed"):
        load_pilot_manifest(manifest, root)


def test_taxonomy_is_unchanged() -> None:
    assert regression_type(-0.1, -0.1) == "suppression"
    assert regression_type(-0.1, 0.0) == "geometry_candidate"
    assert regression_type(0.0, -1.0) == "improvement_or_tie"


def test_frozen_manifest_hash_rejects_replacement(tmp_path: Path) -> None:
    manifest = tmp_path / "pilot.csv"
    manifest.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        pilot._require_file_hash(manifest, pilot.EXPECTED_MANIFEST_SHA256, "frozen pilot manifest")


def test_official_wrappers_accept_synthetic_sources(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    rrdb = tmp_path / "esrgan"
    rrdb.mkdir()
    (rrdb / "RRDBNet_arch.py").write_text(
        "import torch.nn as nn\n"
        "import torch.nn.functional as F\n"
        "class RRDBNet(nn.Module):\n"
        " def __init__(self,*args,**kwargs): super().__init__(); self.bias=nn.Parameter(__import__('torch').zeros(1))\n"
        " def forward(self,x): return F.interpolate(x+self.bias.view(1,1,1,1),scale_factor=4,mode='nearest')\n",
        encoding="utf-8",
    )
    checkpoint = tmp_path / "rrdb.pth"
    torch.save({"bias": torch.zeros(1)}, checkpoint)
    model = ESRGANRRDBX4(rrdb, checkpoint, "synthetic_rrdb")
    assert model.restore(Image.new("RGB", (4, 3), "gray")).size == (16, 12)

    basicsr = tmp_path / "basicsr-repo" / "basicsr" / "utils"
    basicsr.mkdir(parents=True)
    (basicsr / "matlab_functions.py").write_text(
        "import numpy as np\n"
        "def imresize(img,scale,antialiasing=True):\n"
        " h,w=img.shape[:2]; return np.resize(img,(int(np.ceil(h*scale)),int(np.ceil(w*scale)),3))\n",
        encoding="utf-8",
    )
    resized = matlab_bicubic_resize(Image.new("RGB", (8, 8), "white"), 0.25, tmp_path / "basicsr-repo")
    assert resized.size == (2, 2)
    assert np.asarray(resized).dtype == np.uint8


def test_pilot_reuses_only_the_frozen_391_image_bank(tmp_path: Path, monkeypatch) -> None:
    model_dir = tmp_path / "bank"
    model_dir.mkdir()
    artifacts = (model_dir / "patchcore_params.pkl", model_dir / "nnscorer_search_index.faiss")
    for index, path in enumerate(artifacts):
        path.write_bytes(f"artifact-{index}".encode())
    monkeypatch.setattr(pilot, "EXPECTED_BANK_SHA256", {path.name: pilot._checksum(path) for path in artifacts})
    spec = {
        "implementation": "amazon-science/patchcore-inspection",
        "source_commit": pilot.EXPECTED_PATCHCORE_COMMIT,
        "category": "hazelnut",
        "seed": 11,
        "train_paths": [f"hazelnut/train/good/{index:03d}.png" for index in range(391)],
        **pilot.FROZEN_PATCHCORE_SETTINGS,
    }
    (model_dir / "metadata.json").write_text(json.dumps({
        "spec": spec,
        "artifact_sha256": {path.name: pilot._checksum(path) for path in artifacts},
    }), encoding="utf-8")

    class FakeModel:
        loaded = False

        def load_from_path(self, *_args, **_kwargs):
            self.loaded = True

    model = FakeModel()

    class FakePatchcore:
        @staticmethod
        def PatchCore(_device):
            return model

    class FakeCommon:
        @staticmethod
        def FaissNN(*_args):
            return "cpu-faiss"

    loaded, loaded_spec, _ = pilot._load_frozen_detector(model_dir, "cpu", FakeCommon, FakePatchcore)
    assert loaded is model and model.loaded and len(loaded_spec["train_paths"]) == 391
    spec["category"] = "screw"
    (model_dir / "metadata.json").write_text(json.dumps({
        "spec": spec,
        "artifact_sha256": {path.name: pilot._checksum(path) for path in artifacts},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen Hazelnut"):
        pilot._load_frozen_detector(model_dir, "cpu", FakeCommon, FakePatchcore)
