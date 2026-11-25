"""Fake/deterministic tests for realistic noise v2 (no model, checkpoint, bank or dataset)."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from sr_anomaly import realistic_degradation as v1
from sr_anomaly import realistic_noise_v2 as v2

SPEC = importlib.util.spec_from_file_location("run_v2", Path(__file__).resolve().parents[1] / "scripts/run_realistic_noise_v2.py")
run_v2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_v2)


def test_fixed_queue_is_32_units():
    q = v2.queue()
    assert len(q) == 32
    assert {(x["category"], x["noise_seed"]) for x in q} == {("hazelnut", 23), ("hazelnut", 37), ("screw", 23), ("screw", 37)}
    assert v2.conditions() == ("noise_s5", "noise_s15") and v2.RESTORERS == v1.RESTORERS


def test_seed_is_deterministic_seed_specific_and_distinct_from_v1():
    a = v2.sample_seed("screw", "screw/test/good/000.png", "noise_s5", 23)
    assert a == v2.sample_seed("screw", "screw/test/good/000.png", "noise_s5", 23)
    assert a != v2.sample_seed("screw", "screw/test/good/000.png", "noise_s5", 37)
    assert a != v1.sample_seed("screw", "screw/test/good/000.png", "noise_s5")
    with pytest.raises(ValueError):
        v2.sample_seed("screw", "x", "noise_s5", 11)
    with pytest.raises(ValueError):
        v2.degrade(np.zeros((4, 4, 3), np.uint8), "blur_s0.8", 1)


def test_noise_keeps_v1_units_and_insertion():
    lr = np.random.default_rng(1).integers(0, 256, (56, 56, 3), dtype=np.uint8)
    seed = v2.sample_seed("hazelnut", "h/x.png", "noise_s15", 37)
    expected = np.clip(np.rint(lr.astype(np.float64) + np.random.default_rng(seed).normal(0.0, 15.0, lr.shape)), 0, 255).astype(np.uint8)
    assert np.array_equal(v2.degrade(lr, "noise_s15", seed), expected)


def _fake(tmp_path, order):
    rng = np.random.default_rng(0)
    cal = {f"c/{i}.png": Image.fromarray(rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)) for i in range(4)}
    test = {f"t/{i}.png": Image.fromarray(rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)) for i in range(4)}
    meta = [dict(sample=s, label=int(i >= 2), defect_type="good" if i < 2 else "crack") for i, s in enumerate(test)]
    lr = {k: np.asarray(v.resize((56, 56), Image.BICUBIC)) for k, v in (cal | test).items()}
    seen = {}

    def restorer(name, method):
        def restore(img):
            seen.setdefault(name, []).append(hashlib.sha256(np.asarray(img).tobytes()).hexdigest())
            return img.resize((224, 224), method)
        return restore
    restorers = {"bicubic_x4": restorer("bicubic_x4", Image.BICUBIC), "swinir_x4": restorer("swinir_x4", Image.BILINEAR),
                 "realesrnet_x4plus": restorer("realesrnet_x4plus", Image.NEAREST), "realesrgan_x4plus": restorer("realesrgan_x4plus", Image.LANCZOS)}

    def predict(img):
        a = np.asarray(img, np.float32).mean(-1) / 255.0
        return float(a.max()), a

    def load_masks():
        order.append("masks")
        m = np.zeros((4, 224, 224), bool); m[2:, 10:20, 10:20] = True
        return m

    def unit_metrics(rc, rt, cm, tm, masks):
        order.append("metrics")
        return {"au_pro": float(tm[masks].mean())}, {"image_threshold": 0.0}

    def checksum(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    def write_csv(path, rows):
        fields = list(dict.fromkeys(k for r in rows for k in r))
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

    kw = dict(output=tmp_path, category="hazelnut", noise_seed=23, protocol_sha="p", calibration_clean=cal, test_clean=test,
              test_meta=meta, lr=lr, restorers=restorers, predict=predict, quality=lambda a, b: {"psnr": 1.0}, load_masks=load_masks,
              unit_metrics=unit_metrics, per_image_metrics=lambda m, x: {"per_image_aupro": float(x[m].mean())},
              checksum=checksum, write_csv=write_csv, log=lambda s: None)
    return kw, seen


def test_fake_end_to_end_shares_lr_resumes_and_detects_tamper(tmp_path):
    order = []
    kw, seen = _fake(tmp_path, order)
    s = run_v2.run_units(**kw, max_units=3)
    assert len(s["units_run"]) == 3 and order[:2] == ["masks", "metrics"]
    s = run_v2.run_units(**kw)  # resume
    assert len(s["units_skipped"]) == 3 and len(s["units_run"]) == 5
    receipts = [json.loads(p.read_text()) for p in sorted((tmp_path / "units").glob("*.json"))]
    assert len(receipts) == 8
    for c in v2.conditions():
        hashes = [r["degraded_lr_sha256"] for r in receipts if r["condition"] == c]
        assert all(h == hashes[0] for h in hashes)  # identical LR bytes for all four restorers
    assert seen["bicubic_x4"][:8] == seen["swinir_x4"][:8]
    assert all(r["noise_seed"] == 23 and r["split_seed"] == 11 for r in receipts)
    s = run_v2.run_units(**kw)
    assert len(s["units_skipped"]) == 8 and not s["units_run"]
    (tmp_path / "units" / "noise_s5__bicubic_x4.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="resume refused"):
        run_v2.run_units(**kw)
