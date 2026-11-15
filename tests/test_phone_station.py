"""Synthetic tests for recipe/ROI registration checks, quality policy v0.2, golden-reference inspection and the
C0-C3 comparison runner (no real photos, no learned detector, fake restorer)."""
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest
from skimage.transform import AffineTransform, warp

from sr_anomaly import phone_capture as pc
from sr_anomaly import phone_station as ps

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


synth = _load("phone_synth_station", "scripts/make_phone_synthetic_set.py")
runner = _load("phone_station_compare", "scripts/run_phone_station_compare.py")
ROI = [0.1, 0.1, 0.9, 0.9]
RECIPE = dict(recipe_id="synthetic-recipe", part_id="P1", view="synthetic", anchor="L0_1.png", roi=ROI, work_long_side=1024,
              interpolation="lanczos", lighting={"L0": "front", "L1": "left"}, camera={"model": "synthetic"},
              pose_tolerance={"rotation_deg": 5.0, "scale_deviation": 0.10}, retake_light="L1", policy_version=ps.POLICY_VERSION)


@pytest.fixture(scope="module")
def base():
    synth.W, synth.H = 800, 600
    return synth.board(11)


def _transform(img, *, rotation=0.0, scale=1.0, shift=(0, 0)):
    h, w = img.shape[:2]
    centre = np.array([w / 2, h / 2])
    t = (AffineTransform(translation=-centre) + AffineTransform(rotation=np.deg2rad(rotation), scale=scale)
         + AffineTransform(translation=centre + np.array(shift)))
    return np.clip(warp(img, t.inverse, order=1, mode="edge", preserve_range=True), 0, 255).astype(np.uint8)


def _blob(img, xy=(430, 300), radius=11, colour=(235, 120, 160)):
    out = img.copy()
    yy, xx = np.ogrid[:img.shape[0], :img.shape[1]]
    out[(xx - xy[0]) ** 2 + (yy - xy[1]) ** 2 <= radius ** 2] = colour
    return out


def test_recipe_validation(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(RECIPE), encoding="utf-8")
    assert ps.load_recipe(p)["roi"] == ROI
    for bad in ({**RECIPE, "roi": [0.5, 0, 0.4, 1]}, {k: v for k, v in RECIPE.items() if k != "anchor"},
                {**RECIPE, "pose_tolerance": {"rotation_deg": 0, "scale_deviation": 0.1}}, {**RECIPE, "work_long_side": 512}):
        p.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            ps.load_recipe(p)


def test_roi_checks_separate_pose_lost_fov_background_only_and_failure(base):
    ref = synth.lit(base, "front", noise_seed=1)
    ref_y = pc.luma(ref)
    box = pc.roi_box(ref.shape, ROI)

    def check(img):
        a = pc.align(ref_y, pc.luma(img))
        return a, ps.roi_alignment_check(a, box, img.shape)
    a, c = check(synth.lit(base, "left", noise_seed=2))                     # lighting change only
    assert c["verified"] and abs(a["rotation_deg"]) < 0.5 and c["projected_coverage"] == 1.0
    a, c = check(_transform(synth.lit(base, "front", noise_seed=3), rotation=3, scale=1.04))
    assert c["verified"] and a["rotation_deg"] == pytest.approx(3, abs=0.3) and a["scale_deviation"] == pytest.approx(0.04, abs=0.01)
    a, c = check(_transform(synth.lit(base, "front", noise_seed=4), rotation=12))
    assert a["success"] and abs(a["rotation_deg"]) > 5                      # registered, but outside the recipe pose
    a, c = check(_transform(synth.lit(base, "front", noise_seed=5), shift=(260, 0)))
    assert a["success"] and not c["verified"] and c["failure"] == "roi_outside_frame" and c["projected_coverage"] < 0.98
    swapped = synth.lit(base, "front", noise_seed=6)
    x0, y0, x1, y1 = box
    swapped[y0:y1, x0:x1] = synth.lit(synth.board(99), "front", noise_seed=7)[y0:y1, x0:x1]  # background matches, part differs
    a, c = check(swapped)
    assert not c["verified"] and c["failure"] in ("alignment_unverified_in_roi", "alignment_below_threshold", "too_few_matches", "ransac_failed")
    a, c = check(synth.lit(synth.board(99), "front", noise_seed=8))
    assert not a["success"] and not c["verified"]
    ident = ps.identity_alignment(ref.shape, box)
    assert ps.roi_alignment_check(ident, box, ref.shape)["verified"] and ident["is_anchor"]


def _capture(ref, img, recipe=RECIPE):
    box = pc.roi_box(ref.shape, ROI)
    a = pc.align(pc.luma(ref), pc.luma(img))
    c = dict(roi_check=ps.roi_alignment_check(a, box, img.shape), rotation_deg=a["rotation_deg"], scale_deviation=a["scale_deviation"])
    warped, valid = pc.warp_to_reference(img, a["matrix"], ref.shape)
    c.update(ps.reference_relative_metrics(img, a["matrix"], ref, box, valid))
    q = pc.quality(*pc.crop_to_mask(img, pc.project_roi_mask(a["matrix"], box, ref.shape, img.shape)))
    qr = pc.quality(ref[box[1]:box[3], box[0]:box[2]])
    c.update(q, sharpness_ratio=ps.sharpness_norm(q) / ps.sharpness_norm(qr))
    return c, q


def test_policy_v02_separates_material_from_new_clipping(base):
    material = base.copy()
    material[200:330, 250:420] = 0          # black part: about 9 % of the ROI is clipped low in the reference too
    material[340:400, 300:420] = 255        # bright silkscreen/solder: clipped high in the reference too
    ref = synth.lit(material, "front", noise_seed=1)
    same, q = _capture(ref, synth.lit(material, "front", noise_seed=2))
    assert q["clip_low_fraction"] > 0.01 and q["clip_high_fraction"] > 0.01          # v0.1 absolute rule would retake
    assert pc.policy(dict(invalid_reasons=[], alignment_success=True, **q), None)[0] == "RETAKE"
    assert same["new_clip_low"] < 0.002 and same["new_clip_high"] < 0.002 and ps.policy_v02(same, RECIPE) == ("PASS", [])
    glare = synth.lit(material, "front", noise_seed=3)
    glare[420:500, 450:600] = 255           # new reflection: 4 % of the ROI, not in the reference
    c, _ = _capture(ref, glare)
    assert c["new_clip_high"] > 0.02 and ps.policy_v02(c, RECIPE) == ("RETAKE", ["new_clip_high"])
    dim = np.clip(synth.lit(material, "front", noise_seed=4) * 0.3, 0, 255).astype(np.uint8)
    c, _ = _capture(ref, dim)
    state, reasons = ps.policy_v02(c, RECIPE)
    assert "roi_too_dark" in reasons and "low_sharpness_vs_reference" not in reasons   # dark is not reported as blur
    blur = np.asarray(Image.fromarray(synth.lit(material, "front", noise_seed=5)).filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(1.2)))
    c, _ = _capture(ref, blur)
    assert ps.policy_v02(c, RECIPE) == ("REVIEW", ["low_sharpness_vs_reference"])
    c, _ = _capture(ref, _transform(synth.lit(material, "front", noise_seed=6), rotation=9))
    assert "outside_recipe_pose" in ps.policy_v02(c, RECIPE)[1]
    assert ps.policy_v02(dict(missing=True), RECIPE) == ("RETAKE", ["missing_file"])
    assert ps.policy_v02(dict(roi_check=dict(verified=False, failure="roi_outside_frame")), RECIPE) == ("RETAKE", ["roi_outside_frame"])


def test_golden_reference_flags_injected_object_not_a_normal_repeat(base):
    ref, cal, normal = (synth.lit(base, "front", noise_seed=s) for s in (1, 2, 3))
    box = pc.roi_box(ref.shape, ROI)
    mask = ps.inspection_mask(ref.shape, box)
    calibration = ps.gr_calibrate(ps.difference_map(cal, ref), mask)
    ok = ps.gr_inspect(ps.difference_map(normal, ref), mask, calibration)
    ng = ps.gr_inspect(ps.difference_map(_blob(normal), ref), mask, calibration)
    assert ok["verdict"] == "OK" and ng["verdict"] == "NG" and ng["score"] > 5 * ok["limit"] == 5 * ps.GR["min_area"]
    # Normal repeats stay OK under the amplitude margin (the first rule, 2 x one calibration blob area, failed 6/10 here).
    assert all(ps.gr_inspect(ps.difference_map(synth.lit(base, "front", noise_seed=s), ref), mask, calibration)["verdict"] == "OK"
               for s in range(4, 10))
    assert calibration["tau"] == pytest.approx(ps.GR["tau_factor"] * calibration["normal_quantile"])
    assert ps.location_match(ng["centroid_xy"], [430, 300]) is True and ps.location_match(ng["centroid_xy"], [100, 100]) is False
    assert ps.location_match(None, [1, 1]) is None
    with pytest.raises(ValueError):
        ps.gr_calibrate(np.zeros((50, 50)), np.zeros((50, 50), bool))


def test_x4_roundtrip_contract():
    rgb = np.zeros((64, 80, 3), np.uint8)
    down = lambda im: im.resize((im.width // 4, im.height // 4), Image.BICUBIC)  # noqa: E731
    up = lambda im: im.resize((im.width * 4, im.height * 4), Image.BICUBIC)      # noqa: E731
    assert ps.x4_roundtrip(rgb, down, up).shape == rgb.shape
    with pytest.raises(ValueError):
        ps.x4_roundtrip(np.zeros((62, 80, 3), np.uint8), down, up)
    with pytest.raises(ValueError):
        ps.x4_roundtrip(rgb, down, lambda im: im)


def _station_folder(folder, base):
    folder.mkdir()
    images = {}
    seed = 0
    for light, pos in (("L0", "front"), ("L1", "left")):
        for k in (1, 2, 3):
            seed += 1
            images[f"{light}_{k}.png"] = (synth.lit(base, pos, noise_seed=seed), light, k, "unknown")
    images["F0_1.png"] = (_blob(synth.lit(base, "front", noise_seed=20)), "F0", 1, "simulated_defect")
    images["F1_1.png"] = (_blob(synth.lit(base, "left", noise_seed=21)), "F1", 1, "simulated_defect")
    glare = synth.lit(base, "front", noise_seed=22)
    glare[150:260, 150:330] = 255
    images["GLARE_1.png"] = (glare, "GLARE", 1, "unknown")
    images["TILT_1.png"] = (_transform(synth.lit(base, "front", noise_seed=23), rotation=12), "TILT", 1, "unknown")
    images["LOST_1.png"] = (_transform(synth.lit(base, "front", noise_seed=24), shift=(260, 0)), "LOST", 1, "unknown")
    rows = []
    for name, (arr, recipe_id, k, label) in images.items():
        Image.fromarray(arr).save(folder / name)
        rows.append(dict(file=name, part_id="P1", session_id="S1", recipe_id=recipe_id, repeat_id=k, attempt=1, label_status=label))
    rows.append(dict(file="GONE_1.png", part_id="P1", session_id="S1", recipe_id="GONE", repeat_id=1, attempt=1, label_status="unknown"))
    with open(folder / "capture_sheet.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    plan = dict(first_light="L0", alternate_light="L1", references={"L0": "L0_1.png", "L1": "L1_1.png"},
                calibration={"L0": "L0_2.png", "L1": "L1_2.png"}, annotation_xy=[430, 300],
                cycles=[dict(cycle_id="normal-3", kind="normal", label="normal", first="L0_3.png", alternate="L1_3.png"),
                        dict(cycle_id="foreign-1", kind="foreign", label="simulated_defect", first="F0_1.png", alternate="F1_1.png"),
                        dict(cycle_id="glare-1", kind="glare", label="normal", first="GLARE_1.png", alternate="L1_3.png"),
                        dict(cycle_id="tilt-1", kind="tilt", label="normal", first="TILT_1.png", alternate=None),
                        dict(cycle_id="lost-1", kind="lost_fov", label="normal", first="LOST_1.png", alternate=None),
                        dict(cycle_id="gone-1", kind="missing", label="normal", first="GONE_1.png", alternate="L1_3.png")])
    return plan


def test_compare_runner_end_to_end_with_fake_restorer(tmp_path, base):
    plan = _station_folder(tmp_path / "in", base)
    (tmp_path / "recipe.json").write_text(json.dumps(RECIPE), encoding="utf-8")
    (tmp_path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    down = lambda im: im.resize((im.width // 4, im.height // 4), Image.BICUBIC)  # noqa: E731
    fake = {"bicubic_x4": lambda rgb: ps.x4_roundtrip(rgb, down, lambda im: im.resize((im.width * 4, im.height * 4), Image.BICUBIC))}
    m = runner.compare(tmp_path / "in", tmp_path / "recipe.json", tmp_path / "plan.json", tmp_path / "out", kind="synthetic",
                       restorers=fake, guard=lambda r, b: None)
    rows = list(csv.DictReader(open(tmp_path / "out/cycles.csv", encoding="utf-8")))
    cell = {(r["cycle_id"], r["condition"]): r for r in rows}
    assert len(rows) == 6 * len(runner.CONDITIONS)                                  # every cycle x condition kept
    assert all(int(r["captures_used"]) <= runner.MAX_CAPTURES for r in rows)
    assert cell["foreign-1", "C0_direct"]["final_state"] == "NG" and cell["normal-3", "C0_direct"]["final_state"] == "OK"
    assert cell["foreign-1", "C3_two_lights"]["final_state"] == "NG" and cell["foreign-1", "C3_two_lights"]["captures_used"] == "2"
    assert cell["foreign-1", "C1_swinir_x4"]["final_state"] == "PENDING"            # restorer not supplied -> pending, not dropped
    assert cell["foreign-1", "C1_bicubic_x4"]["final_state"] in ("NG", "OK")
    g = cell["glare-1", "C2_policy_v0.2"]
    assert g["first_quality_state"] == "RETAKE" and "new_clip_high" in g["first_quality_reasons"] and g["retake_requested"] == "True"
    assert g["captures_used"] == "2" and g["second_quality_state"] == "PASS" and g["final_state"] == "OK"
    t = cell["tilt-1", "C2_policy_v0.2"]
    assert t["final_state"] == "REVIEW" and "retake_unavailable" in t["note"] and t["captures_used"] == "1"
    assert cell["tilt-1", "C3_two_lights"]["final_state"] == "NA"
    assert "roi_outside_frame" in cell["lost-1", "C2_policy_v0.2"]["first_quality_reasons"]
    assert cell["gone-1", "C0_direct"]["final_state"] == "ERROR"                    # missing input is an error, not a pass
    assert cell["gone-1", "C2_policy_v0.2"]["first_quality_reasons"] == "missing_file" and cell["gone-1", "C2_policy_v0.2"]["final_state"] == "OK"
    s = {r["condition"]: r for r in csv.DictReader(open(tmp_path / "out/summary.csv", encoding="utf-8"))}
    assert s["C0_direct"]["cycles"] == "6" and s["C0_direct"]["simulated_final_NG"] == "1" and s["C0_direct"]["simulated_NG_at_annotation"] == "1"
    assert s["C2_policy_v0.2"]["retakes_requested"] == "4" and s["C3_two_lights"]["NA"] == "2"
    assert m["station_replay"]["all_accepted"] and m["station_replay"]["max_captures_per_cycle"] == 2
    assert m["kind"] == "synthetic" and m["research_metrics"] is None and "development" in m["session_role"]
    report = (tmp_path / "out/report.html").read_text(encoding="utf-8")
    assert "SYNTHETIC test input" in report and "retake_unavailable" in report
    events = [json.loads(x) for x in open(tmp_path / "out/station_events.jsonl", encoding="utf-8")]
    assert any(e.get("event") == "retake_requested" and e["capture_budget"] == 2 for e in events)
    with pytest.raises(FileExistsError):
        runner.compare(tmp_path / "in", tmp_path / "recipe.json", tmp_path / "plan.json", tmp_path / "out", kind="synthetic")


def test_plan_validation(tmp_path, base):
    plan = _station_folder(tmp_path / "in", base)
    files = {r["file"] for r in csv.DictReader(open(tmp_path / "in/capture_sheet.csv", encoding="utf-8"))}
    for bad in ({**plan, "references": {"L0": "L0_1.png"}}, {**plan, "cycles": plan["cycles"] + [plan["cycles"][0]]},
                {**plan, "cycles": [dict(cycle_id="x", label="normal", first="nope.png")]},
                {**plan, "cycles": [dict(cycle_id="x", label="true_defect", first="L0_3.png")]}):
        (tmp_path / "p.json").write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            runner.load_plan(tmp_path / "p.json", files)
