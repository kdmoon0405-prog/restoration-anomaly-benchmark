"""Synthetic tests for the phone capture audit (no real photos, no detector)."""
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from sr_anomaly import phone_capture as pc

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_mod = _load("phone_audit", "scripts/run_phone_capture_audit.py")
synth = _load("phone_synth", "scripts/make_phone_synthetic_set.py")


def test_quality_definitions_on_known_arrays():
    rgb = np.full((20, 20, 3), 100, np.uint8)
    rgb[:2, :, :] = 255          # 40 px clipped high (any channel >= 250)
    rgb[2:4, :, 0] = 3           # not low-clipped: G/B are 100
    rgb[4:5, :, :] = 2           # 20 px clipped low (all channels <= 5)
    q = pc.quality(rgb)
    assert q["clip_high_fraction"] == 40 / 400 and q["clip_low_fraction"] == 20 / 400
    flat = pc.quality(np.full((16, 16, 3), 120, np.uint8))
    assert flat["luma_mean"] == pytest.approx(120) and flat["sharpness_tenengrad"] == 0 and flat["noise_sigma"] == 0
    noisy = np.clip(128 + np.random.default_rng(0).normal(0, 10, (256, 256)), 0, 255)
    assert pc.noise_sigma_immerkaer(noisy, np.ones_like(noisy, bool)) == pytest.approx(10, rel=0.1)
    assert pc.roi_box((100, 200), (0.1, 0.2, 0.9, 0.8)) == (20, 20, 180, 80)
    with pytest.raises(ValueError):
        pc.roi_box((10, 10), (0.5, 0, 0.4, 1))


def test_sheet_validation_duplicates_and_unlisted():
    rows = [dict(file="a.jpg", part_id="P1", session_id="S1", recipe_id="front", repeat_id="1"),
            dict(file="b.jpg", part_id="P 1", session_id="S1", recipe_id="front", repeat_id="2"),
            dict(file="c.jpg", part_id="P1", session_id="S1", recipe_id="front", repeat_id="1"),
            dict(file="../d.jpg", part_id="P1", session_id="S1", recipe_id="front", repeat_id="0", label_status="bad")]
    caps, unlisted = pc.parse_sheet(rows, ["a.jpg", "b.jpg", "c.jpg", "z.jpg"])
    assert caps[0]["invalid_reasons"] == [] and caps[0]["attempt"] == 1
    assert "invalid_part_id" in caps[1]["invalid_reasons"]
    assert caps[2]["invalid_reasons"] == ["duplicate_slot_attempt_of_row_2"]
    assert {"invalid_repeat_id", "invalid_file_name", "invalid_label_status"} <= set(caps[3]["invalid_reasons"])
    assert [u["file"] for u in unlisted] == ["z.jpg"]


def test_policy_order_and_reasons():
    ok = dict(invalid_reasons=[], alignment_success=True, clip_high_fraction=0, clip_low_fraction=0, luma_mean=100,
              sharpness_tenengrad=1.0)
    assert pc.policy(ok, 1.0) == ("PASS", [])
    assert pc.policy({**ok, "missing": True}, 1.0) == ("RETAKE", ["missing_file"])
    assert pc.policy({**ok, "clip_high_fraction": 0.011, "luma_mean": 230}, 1.0) == ("RETAKE", ["clip_high", "luma_out_of_range"])
    assert pc.policy({**ok, "sharpness_tenengrad": 0.49}, 1.0) == ("REVIEW", ["low_sharpness"])
    assert pc.policy({**ok, "sharpness_tenengrad": 0.49}, None) == ("PASS", [])  # < 3 images: rule not applied
    assert pc.policy({**ok, "alignment_success": False}, 1.0)[0] == "RETAKE"
    assert pc.policy({**ok, "invalid_reasons": ["invalid_part_id"]}, 1.0) == ("REVIEW", ["invalid_row", "invalid_part_id"])


def test_alignment_recovers_shift_and_rejects_unrelated(monkeypatch):
    monkeypatch.setattr(synth, "W", 800)
    monkeypatch.setattr(synth, "H", 600)
    base = synth.board(11)
    ref = pc.luma(synth.lit(base, "front", noise_seed=1))
    moved = pc.luma(synth.shift(synth.lit(base, "left", noise_seed=2), 40))
    a = pc.align(ref, moved)
    assert a["success"] and a["translation_fraction"] == pytest.approx(40 / 800, abs=0.004) and pc.setup_moved(a)
    same = pc.align(ref, pc.luma(synth.lit(base, "right", noise_seed=3)))
    assert same["success"] and not pc.setup_moved(same)
    other = pc.align(ref, pc.luma(synth.lit(synth.board(99), "front", noise_seed=4)))
    assert not other["success"]


def test_synthetic_end_to_end_states_report_and_replay(tmp_path):
    # Default 1600x1200 synthetic set (its blur cases are defined for that size).
    spec = synth.make(tmp_path / "in")
    m = audit_mod.audit(tmp_path / "in", tmp_path / "out", kind="synthetic")
    rows = {r["row"]: r for r in csv.DictReader(open(tmp_path / "out/captures.csv", encoding="utf-8")) if r["row"]}
    for row, e in spec["rows"].items():
        assert rows[str(row)]["state"] == e["state"], (row, e, rows[str(row)]["reasons"])
        if e["reason"]:
            assert e["reason"] in rows[str(row)]["reasons"]
    assert m["kind"] == "synthetic" and m["summary"]["unlisted_files"] == 1 and m["summary"]["station_verdicts"] == ["REVIEW"]
    assert m["research_metrics"] is None and m["detector"] == "not_connected"
    slots = list(csv.DictReader(open(tmp_path / "out/slots.csv", encoding="utf-8")))
    retake = next(s for s in slots if s["recipe_id"] == "right" and s["repeat_id"] == "2")
    assert retake["history"] == "a1:RETAKE > a2:PASS" and retake["resolved"] == "True"
    rep = list(csv.DictReader(open(tmp_path / "out/repeatability.csv", encoding="utf-8")))
    assert {r["scope"] for r in rep} == {"baseline_no_policy", "policy_pass_only"}
    html = (tmp_path / "out/report.html").read_text(encoding="utf-8")
    assert "SYNTHETIC test input" in html and "detector not connected" in html
    events = [json.loads(x) for x in open(tmp_path / "out/station_events.jsonl", encoding="utf-8")]
    assert all(e["response"]["accepted"] for e in events)
    with pytest.raises(FileExistsError):
        audit_mod.audit(tmp_path / "in", tmp_path / "out", kind="synthetic")


def test_memory_block_marks_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(synth, "W", 400)
    monkeypatch.setattr(synth, "H", 300)
    synth.make(tmp_path / "in")

    def guard(required, budget):
        raise MemoryError("BLOCKED_MEMORY: synthetic")
    m = audit_mod.audit(tmp_path / "in", tmp_path / "out", kind="synthetic", guard=guard)
    rows = list(csv.DictReader(open(tmp_path / "out/captures.csv", encoding="utf-8")))
    assert m["summary"]["states"]["PASS"] == 0
    assert any("BLOCKED_MEMORY" in r["error"] for r in rows)
