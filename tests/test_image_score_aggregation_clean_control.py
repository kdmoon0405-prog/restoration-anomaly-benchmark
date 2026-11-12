"""Synthetic tests for the v0.2 clean aggregation control (no model, bank or dataset)."""
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from sr_anomaly import image_score_aggregation as agg
from sr_anomaly.evaluation import binary_roc_auc, classification_metrics

SPEC = importlib.util.spec_from_file_location("clean_ctl", Path(__file__).resolve().parents[1] / "scripts/run_image_score_aggregation_clean_control.py")
ctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ctl)


def _legacy(root, tamper=None):
    run = root / ctl.RUN_DIR
    run.mkdir(parents=True)
    rng = np.random.default_rng(3)
    n = 12
    labels = np.r_[np.zeros(5, int), np.ones(7, int)]
    rows, variants = [], {}
    for v in ctl.VARIANTS:
        maps = rng.random((n, 16, 16), dtype=np.float32)
        masks = np.zeros((n, 16, 16), bool)
        masks[5:, 2:5, 2:5] = True
        maps[masks] += 1.5
        scores = maps.reshape(n, -1).max(1).astype(np.float64) + rng.normal(0, .05, n)
        np.savez(run / f"{v}_predictions.npz", labels=labels, scores=scores, masks=masks, maps=maps)
        variants[v] = {"evaluation": {"classification": {"image_auroc": classification_metrics(labels, scores)["image_auroc"]},
                                      "localization": {"pixel_auroc": binary_roc_auc(masks.ravel(), maps.astype(np.float64).ravel()),
                                                       "au_pro": 0.5}}}
        rows += [dict(sample=f"screw/test/x/{i:03d}.png", label=int(l), variant=v, image_score=float(s)) for i, (s, l) in enumerate(zip(scores, labels))]
    if tamper:
        tamper(variants)
    (run / "results.json").write_text(json.dumps({"variants": variants, "calibration": {"paths": []}}), encoding="utf-8")
    with open(run / "per_image.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ref = root / "ref.csv"
    with open(ref, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sample", "split"])
        w.writeheader()
        w.writerows([dict(sample=f"screw/test/x/{i:03d}.png", split="test") for i in range(n)])
    return ref


def test_clean_control_runs_all_rules_with_exact_anchors(tmp_path):
    ref = _legacy(tmp_path / "data")
    s = ctl.run(tmp_path / "data", tmp_path / "out", guard=lambda r, b: None, reference_csv=ref, log=lambda m: None)
    assert s["units_complete"] == 3 and s["cells"] == 15
    rows = list(csv.DictReader(open(tmp_path / "out/summary.csv", encoding="utf-8")))
    assert {r["rule"] for r in rows} == set(agg.RULES) and all(r["image_f1"] == "" for r in rows)
    rec = json.loads((tmp_path / "out/units/screw__historical_recovery__clean.json").read_text())
    assert rec["anchor_a_original_auroc"] == rec["anchor_b_pixel_auroc"] == "EXACT" and rec["counts"]["calibration"] == 0
    assert len(list(csv.DictReader(open(tmp_path / "out/units/screw__historical_recovery__clean.csv", encoding="utf-8")))) == 12 * 5
    with pytest.raises(FileExistsError):
        ctl.run(tmp_path / "data", tmp_path / "out", guard=lambda r, b: None)


@pytest.mark.parametrize("field", ["classification", "localization"])
def test_anchor_mismatch_stops(tmp_path, field):
    key = "image_auroc" if field == "classification" else "pixel_auroc"

    def tamper(variants):
        variants["bicubic_x4"]["evaluation"][field][key] += 1e-12
    _legacy(tmp_path / "data", tamper)
    with pytest.raises(ctl.AnchorMismatch):
        ctl.run(tmp_path / "data", tmp_path / "out", guard=lambda r, b: None, log=lambda m: None)


def test_order_mismatch_and_memory_block(tmp_path):
    ref = _legacy(tmp_path / "data")
    rows = list(csv.DictReader(open(ref, encoding="utf-8")))
    rows[0], rows[1] = rows[1], rows[0]
    with open(ref, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sample", "split"])
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(ValueError, match="test order"):
        ctl.run(tmp_path / "data", tmp_path / "o1", guard=lambda r, b: None, reference_csv=ref, log=lambda m: None)

    def guard(r, b):
        raise MemoryError("BLOCKED_MEMORY: synthetic")
    s = ctl.run(tmp_path / "data", tmp_path / "o2", guard=guard, log=lambda m: None)
    assert s["units_complete"] == 0 and all(v.startswith("BLOCKED_MEMORY") for v in s["units"].values())
