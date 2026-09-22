from __future__ import annotations

import csv
import json

import numpy as np
from PIL import Image

from scripts.render_saved_map_cases import render_cases


def test_saved_map_renderer_needs_no_model_inference(tmp_path) -> None:
    run, data, output = tmp_path / "run", tmp_path / "data", tmp_path / "out"
    run.mkdir()
    sample = "screw/test/thread/001.png"
    source = data / sample
    source.parent.mkdir(parents=True)
    Image.new("RGB", (64, 64), "gray").save(source)
    (run / "results.json").write_text(json.dumps({"test_paths": [sample]}))
    labels = np.array([1], dtype=np.uint8)
    masks = np.zeros((1, 224, 224), dtype=np.uint8)
    masks[:, 50:80, 50:80] = 1
    for name, value in (("bicubic_x4", 0.2), ("swinir_x4", 0.4)):
        np.savez_compressed(run / f"{name}_predictions.npz", labels=labels, masks=masks,
                            scores=np.array([value]), maps=np.full((1, 224, 224), value))
    manifest = tmp_path / "selected.csv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "sample", "defect_type", "regression_type", "delta_aupro",
            "delta_pixel_auroc", "delta_roi_bg_gap", "selection_reason",
        ))
        writer.writeheader()
        writer.writerow({"sample": sample, "defect_type": "thread", "regression_type": "suppression",
                         "delta_aupro": -0.1, "delta_pixel_auroc": -0.01,
                         "delta_roi_bg_gap": -0.2, "selection_reason": "suppression_examples"})
    assert render_cases(run, data, manifest, output) == 1
    assert len(list(output.glob("*.png"))) == 1
    assert "No PatchCore or SwinIR inference" in (output / "README.md").read_text(encoding="utf-8")
