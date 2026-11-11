"""Synthetic tests for image-score aggregation (no model, bank, dataset or GT)."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from sr_anomaly import image_score_aggregation as agg
from sr_anomaly.evaluation import classification_metrics
from sr_anomaly.fusion import normalize, quantile_threshold, robust_params

SPEC = importlib.util.spec_from_file_location("run_agg", Path(__file__).resolve().parents[1] / "scripts/run_image_score_aggregation.py")
run_agg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_agg)


def test_fixed_k_and_unit_plan():
    assert [agg.top_k(f, 224, 224) for f in ("0.001", "0.005", "0.01")] == [51, 251, 502]
    assert agg.top_k("0.001", 10, 10) == 1 and agg.top_k("0.01", 10, 10) == 1 and agg.top_k("0.5", 2, 3) == 3
    plan = agg.unit_plan()
    assert len(plan) == 40 and len({u["unit_id"] for u in plan}) == 40
    assert sum(u["family"] == "realistic_lr_v1" for u in plan) == 8 and {u["condition"] for u in plan if u["noise_seed"]} == {"noise_s5", "noise_s15"}
    assert len(plan) * len(agg.RULES) == 200


def test_rules_on_known_maps_and_original_is_not_map_max():
    maps = np.zeros((2, 10, 10), np.float32)
    maps[0].flat[:3] = [5, 3, 1]
    maps[1].flat[:2] = [2, 2]
    stored = np.array([9.0, -1.0])
    assert np.array_equal(agg.aggregate("original", maps, stored), stored)
    assert np.array_equal(agg.aggregate("map_max", maps, stored), [5.0, 2.0])
    assert np.array_equal(agg.aggregate("top1pct_mean", maps, stored), [5.0, 2.0])  # k=1 on 100 pixels
    big = np.arange(2 * 224 * 224, dtype=np.float32).reshape(2, 224, 224)
    top = agg.aggregate("top0.5pct_mean", big, np.zeros(2))
    assert top.dtype == np.float64 and top[0] == np.sort(big[0].ravel().astype(np.float64))[-251:].mean()
    with pytest.raises(ValueError):
        agg.aggregate("median", maps, stored)


def test_evaluate_rule_uses_runner_ops():
    rng = np.random.default_rng(0)
    cal, test = rng.normal(size=40), rng.normal(size=30) + np.r_[np.zeros(15), np.ones(15)]
    labels = np.r_[np.zeros(15, int), np.ones(15, int)]
    r = agg.evaluate_rule(cal, test, labels)
    p = robust_params(cal)
    thr = quantile_threshold(normalize(cal, p), 0.99)
    assert r["params"] == p and r["threshold"] == thr
    assert r["metrics"]["image_auroc"] == classification_metrics(labels, normalize(test, p), thr)["image_auroc"]
    assert r["metrics"]["image_false_alarm_rate_test_normal"] == float((normalize(test, p) >= thr)[labels == 0].mean())


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _make_unit(root, spec, seed):
    """Synthetic stored unit laid out like the realistic runners (receipt metrics from the same functions)."""
    rng = np.random.default_rng(seed)
    run = root / spec["run_dir"]
    (run / "units").mkdir(parents=True, exist_ok=True)
    (run / "PROTOCOL.json").write_text('{"synthetic": true}\r\n', encoding="utf-8")
    nc, nt = 12, 10
    cal_maps = rng.random((nc, 16, 16), dtype=np.float32)
    test_maps = rng.random((nt, 16, 16), dtype=np.float32)
    test_maps[5:, 3:6, 3:6] += 2
    cal_scores = cal_maps.reshape(nc, -1).max(1).astype(np.float64) + rng.normal(0, .1, nc)  # differs from map max
    test_scores = test_maps.reshape(nt, -1).max(1).astype(np.float64) + rng.normal(0, .1, nt)
    labels = np.r_[np.zeros(5, int), np.ones(5, int)]
    stem = run / "units" / spec["unit"]
    np.savez(stem.with_suffix(".npz"), calibration_maps=cal_maps, test_maps=test_maps,
             calibration_scores=cal_scores, test_scores=test_scores)
    rows = [dict(sample=f"c/{i}.png", split="calibration", label=0, image_score=float(s), defect_type="") for i, s in enumerate(cal_scores)]
    rows += [dict(sample=f"t/{i}.png", split="test", label=int(l), image_score=float(s), defect_type="good" if not l else "crack")
             for i, (s, l) in enumerate(zip(test_scores, labels))]
    run_agg.write_csv(stem.with_suffix(".csv"), rows)
    image, pixel = robust_params(cal_scores), robust_params(cal_maps.astype(np.float64))
    it = quantile_threshold(normalize(cal_scores, image), 0.99)
    pt = quantile_threshold(normalize(cal_maps.astype(np.float64), pixel), 0.99)
    z = normalize(test_scores, image)
    metrics = {**classification_metrics(labels, z, it), "au_pro": 0.5, "pixel_auroc": 0.9,
               "image_false_alarm_rate_test_normal": float((z >= it)[labels == 0].mean()),
               "image_miss_rate_test_anomaly": float((~(z >= it))[labels == 1].mean())}
    receipt = {"unit": spec["unit"], "condition": spec["condition"], "restorer": spec["restorer"],
               "protocol_sha256": _sha(run / "PROTOCOL.json"),
               "files": {f"units/{spec['unit']}.npz": _sha(stem.with_suffix(".npz")), f"units/{spec['unit']}.csv": _sha(stem.with_suffix(".csv"))},
               "metrics": metrics, "calibration": {"image": image, "pixel": pixel, "image_threshold": it, "pixel_threshold": pt}}
    if spec["noise_seed"] is not None:
        receipt.update(noise_seed=spec["noise_seed"], split_seed=11)
    stem.with_suffix(".json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return stem


def _plan():
    return [u for u in agg.unit_plan() if u["category"] == "screw" and u["restorer"] in ("bicubic_x4", "swinir_x4")
            and u["condition"] in ("none", "noise_s5") and u["noise_seed"] in (None, 23)]


def test_fake_run_anchors_rules_resume_and_blocks(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    plan = _plan()
    assert len(plan) == 4
    stems = [_make_unit(data, u, i) for i, u in enumerate(plan)]
    before = {p: _sha(p) for s in stems for p in (s.with_suffix(".npz"), s.with_suffix(".csv"), s.with_suffix(".json"))}

    def guard(required, budget):
        if required <= 0:
            raise ValueError
        if guard.block == required:
            raise MemoryError("BLOCKED_MEMORY: synthetic")
    guard.block = None
    s = run_agg.run(data, out, units=plan, guard=guard, log=lambda m: None)
    assert s["units_complete"] == 4 and s["cells_in_output"] == 20
    assert all(_sha(p) == h for p, h in before.items())  # inputs untouched
    rows = list(csv.DictReader(open(out / "summary.csv", encoding="utf-8")))
    assert len(rows) == 20 and {r["rule"] for r in rows} == set(agg.RULES)
    rec = json.loads((out / "units" / f"{plan[0]['unit_id']}.json").read_text())
    assert rec["anchor_a_original"] == "EXACT" and all(rec["anchor_b_map_payload"].values())
    assert rec["original_vs_map_max"]["exactly_equal"] == 0
    assert rec["source_public_record"].startswith("exp/pcb-full-cohort-juhyung@4c2fc40")
    per = list(csv.DictReader(open(out / "units" / f"{plan[0]['unit_id']}.csv", encoding="utf-8")))
    assert len(per) == 22 * 5 and {"raw_score", "threshold", "source_npz_sha256", "label", "split"} <= set(per[0])
    # Resume skips verified units; a tampered result refuses resume.
    s2 = run_agg.run(data, out, units=plan, guard=guard, log=lambda m: None)
    assert set(s2["units"].values()) == {"SKIPPED_VERIFIED"}
    (out / "units" / f"{plan[1]['unit_id']}.csv").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="resume refused"):
        run_agg.run(data, out, units=plan, guard=guard, log=lambda m: None)


def test_blocked_unit_is_recorded_and_others_continue(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    plan = _plan()
    for i, u in enumerate(plan):
        _make_unit(data, u, i)
    calls = []

    def guard(required, budget):
        calls.append(required)
        if len(calls) == 2:
            raise MemoryError("BLOCKED_MEMORY: synthetic")
    s = run_agg.run(data, out, units=plan, guard=guard, log=lambda m: None)
    assert s["units"][plan[1]["unit_id"]].startswith("BLOCKED_MEMORY") and s["units_complete"] == 3
    assert calls[0] == agg.payload_plan_bytes(12, 10, 16, 16)


def test_anchor_mismatch_and_payload_tamper_stop(tmp_path):
    data = tmp_path / "data"
    plan = _plan()[:1]
    stem = _make_unit(data, plan[0], 0)
    receipt = json.loads(stem.with_suffix(".json").read_text())
    receipt["metrics"]["image_auroc"] += 1e-12
    stem.with_suffix(".json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(run_agg.AnchorMismatch, match="original-score anchor"):
        run_agg.run(data, tmp_path / "o1", units=plan, guard=lambda r, b: None, log=lambda m: None)
    receipt["metrics"]["image_auroc"] -= 1e-12
    receipt["calibration"]["pixel_threshold"] += 1e-9
    stem.with_suffix(".json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(run_agg.AnchorMismatch, match="map-payload anchor"):
        run_agg.run(data, tmp_path / "o2", units=plan, guard=lambda r, b: None, log=lambda m: None)
    with open(stem.with_suffix(".npz"), "r+b") as f:
        f.seek(200); f.write(b"\x01")
    with pytest.raises(ValueError, match="payload SHA"):
        run_agg.run(data, tmp_path / "o3", units=plan, guard=lambda r, b: None, log=lambda m: None)


def test_missing_input_is_recorded(tmp_path):
    plan = _plan()[:2]
    _make_unit(tmp_path / "data", plan[0], 0)
    s = run_agg.run(tmp_path / "data", tmp_path / "out", units=plan, guard=lambda r, b: None, log=lambda m: None)
    assert s["units"][plan[1]["unit_id"]].startswith("MISSING_INPUT") and s["units_complete"] == 1


def test_summarize_keeps_all_units_and_contrasts(tmp_path):
    spec = importlib.util.spec_from_file_location("summ", Path(__file__).resolve().parents[1] / "scripts/summarize_image_score_aggregation.py")
    summ = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summ)
    data, out = tmp_path / "data", tmp_path / "out"
    plan = _plan()
    for i, u in enumerate(plan):
        _make_unit(data, u, i)
    run_agg.run(data, out, units=plan, guard=lambda r, b: None, log=lambda m: None)
    by_rule, contrasts = summ.derive(summ.load(out / "summary.csv"))
    assert len(by_rule) == 4 and len(contrasts) == 2 and all(c["primary"] == 1 for c in contrasts)
    assert all(r["image_auroc_delta_vs_original__map_max"] == float(r["image_auroc__map_max"]) - float(r["image_auroc__original"]) for r in by_rule)
