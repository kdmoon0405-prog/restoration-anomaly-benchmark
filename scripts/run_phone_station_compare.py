"""Compare capture/inspection conditions C0-C3 on a phone capture folder (docs/DESIGN_DECISION_PHONE_V0.2.md).

C0 fixed capture + direct golden-reference inspection; C1 same capture after an x4 round trip (Bicubic / SwinIR);
C2 quality policy (v0.1 with ROI / v0.2 ref_roi) with at most one retake under the pre-specified alternate light;
C3 always two fixed lights, OR-combined. Every initial cycle stays in the denominator.

No learned detector. report.html embeds downscaled photos (private); CSV/JSON hold no pixels.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from datetime import datetime
import html
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import phone_capture as pc  # noqa: E402
from sr_anomaly import phone_station as ps  # noqa: E402
from sr_anomaly.analysis_io import csv_rows, new_output, read_json, write_csv, write_json  # noqa: E402
from sr_anomaly.inspection_station import InspectionStation  # noqa: E402
from sr_anomaly.pcb_board_analysis import _budget  # noqa: E402

DECISION_V3 = "docs/DESIGN_DECISION_PHONE_V0.3.md"
CODE = ("scripts/run_phone_station_compare.py", "src/sr_anomaly/phone_station.py", "src/sr_anomaly/phone_capture.py",
        "src/sr_anomaly/inspection_station.py", ps.DECISION, DECISION_V3, pc.PROTOCOL)
CONDITIONS = ("C0_direct", "C1_bicubic_x4", "C1_swinir_x4", "C2_policy_v0.1_roi", "C2_policy_v0.2", "C2_policy_v0.3",
              "C3_two_lights")
OPERATING = "C2_policy_v0.3"  # the station's operating path; the other conditions are comparisons on the same cycles
MAX_CAPTURES = 2


def source_state(root=ROOT) -> dict:
    def git(*a):
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()
    tracked = git("status", "--porcelain", "--untracked-files=no")
    untracked = [x for x in git("status", "--porcelain").splitlines() if x.startswith("??")]
    return dict(source_commit=git("rev-parse", "HEAD"), source_branch=git("rev-parse", "--abbrev-ref", "HEAD"),
                tracked_worktree_dirty=bool(tracked), source_worktree_dirty=bool(tracked) or bool(untracked))


def load_plan(path: Path, files: set[str]) -> dict:
    plan = read_json(path)
    for key in ("references", "calibration", "cycles", "first_light", "alternate_light"):
        if key not in plan:
            raise ValueError(f"plan missing {key}")
    lights = (plan["first_light"], plan["alternate_light"])
    for group in ("references", "calibration"):
        if set(plan[group]) != set(lights):
            raise ValueError(f"plan {group} must name both lights")
    used = list(plan["references"].values()) + list(plan["calibration"].values())
    ids = set()
    for c in plan["cycles"]:
        if c["cycle_id"] in ids or not c.get("first") or c.get("label") not in ("normal", "simulated_defect"):
            raise ValueError(f"bad cycle {c}")
        ids.add(c["cycle_id"])
        used += [c["first"]] + ([c["alternate"]] if c.get("alternate") else [])
    missing = sorted(set(used) - files)
    if missing:
        raise ValueError(f"plan names files not in the sheet: {missing}")
    return plan


def prepare(folder: Path, recipe: dict, *, guard=_budget) -> dict:
    """Decode, register to the anchor, verify the ROI, compute quality and both policies for every sheet row."""
    rows = csv_rows(folder / "capture_sheet.csv", ("file", "part_id", "session_id", "recipe_id", "repeat_id"))
    files = sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in pc.IMAGE_SUFFIXES)
    captures, unlisted = pc.parse_sheet(rows, files)
    by_file, sha_first, work = {}, {}, {}
    for c in captures:
        c["missing"] = not c["invalid_reasons"] and not (folder / c["file"]).is_file()
        if c["invalid_reasons"] or c["missing"]:
            continue
        c["sha256"] = pc.sha256_file(folder / c["file"])
        if c["sha256"] in sha_first:
            c["duplicate_of"] = sha_first[c["sha256"]]
        sha_first.setdefault(c["sha256"], c["row"])
        t0 = time.perf_counter()
        try:
            with Image.open(folder / c["file"]) as probe:
                w, h = probe.size
            guard(int(w) * int(h) * 3 * 4 + pc.WORK_LONG_SIDE ** 2 * 8 * 16 + 64 * 1024 ** 2, None)
            rgb, exif = pc.decode(folder / c["file"])
        except MemoryError as e:
            c["unreadable"], c["error"] = True, f"BLOCKED_MEMORY: {e}"
            continue
        except (ValueError, OSError) as e:
            c["unreadable"], c["error"] = True, str(e)
            continue
        c.update({f"exif_{k}": v for k, v in exif.items()})
        c["width"], c["height"] = int(rgb.shape[1]), int(rgb.shape[0])
        work[c["file"]], c["work_scale"] = pc.working(rgb)
        c["seconds_decode"] = time.perf_counter() - t0
        by_file.setdefault(c["file"], c)
    anchor_file = recipe["anchor"]
    if anchor_file not in work:
        raise ValueError("recipe anchor is missing or unreadable")
    anchor = work[anchor_file]
    box = pc.roi_box(anchor.shape, recipe["roi"])
    anchor_y = pc.luma(anchor)
    aligned = {}
    for c in captures:
        f = c.get("file")
        if f not in work or by_file.get(f) is not c:
            continue
        t0 = time.perf_counter()
        m = work[f]
        a = ps.identity_alignment(anchor.shape, box) if f == anchor_file else pc.align(anchor_y, pc.luma(m))
        c["alignment"] = a
        c["roi_check"] = ps.roi_alignment_check(a, box, m.shape)
        c["resolution_mismatch"] = (c["width"], c["height"]) != (by_file[anchor_file]["width"], by_file[anchor_file]["height"])
        c["setup_moved"] = pc.setup_moved(a)
        try:
            if a["success"]:
                q_rgb, q_mask = pc.crop_to_mask(m, pc.project_roi_mask(a["matrix"], box, anchor.shape, m.shape))
                c["quality_basis"] = "projected_roi_unwarped"
                warped, valid = pc.warp_to_reference(m, a["matrix"], anchor.shape)
                aligned[f] = (warped, valid)
                c.update(ps.reference_relative_metrics(m, a["matrix"], anchor, box, valid))
            else:
                x0, y0, x1, y1 = box
                q_rgb = m[y0:min(y1, m.shape[0]), x0:min(x1, m.shape[1])]
                q_mask = np.ones(q_rgb.shape[:2], bool)
                c["quality_basis"] = "reference_box_unaligned"
            c.update(pc.quality(q_rgb, q_mask))
            c["sharpness_norm"] = ps.sharpness_norm(c)
        except ValueError as e:
            c["roi_check"] = dict(c["roi_check"], verified=False, failure=str(e))
        c["seconds_register_quality"] = time.perf_counter() - t0
    ref_norm = by_file[anchor_file].get("sharpness_norm")
    sharp = [c["sharpness_tenengrad"] for c in captures if c.get("sharpness_tenengrad") is not None]
    median = float(np.median(sharp)) if len(sharp) >= pc.T["sharpness_min_set"] else None
    for c in captures:
        if c["invalid_reasons"]:
            c["state_v01"], c["reasons_v01"] = "REVIEW", ["invalid_row", *c["invalid_reasons"]]
            c["state_v02"], c["reasons_v02"] = c["state_v01"], c["reasons_v01"]
            continue
        a = c.get("alignment") or {}
        c["alignment_success"] = bool(a.get("success"))
        c["rotation_deg"], c["scale_deviation"] = a.get("rotation_deg", math.nan), a.get("scale_deviation", math.nan)
        c["state_v01"], c["reasons_v01"] = pc.policy(c, median)
        if c.get("sharpness_norm") is not None and ref_norm:
            c["sharpness_ratio"] = c["sharpness_norm"] / ref_norm
        ok = c.get("roi_check", {}).get("verified") and "new_clip_high" in c and "sharpness_ratio" in c
        if c.get("missing") or c.get("unreadable") or ok:
            c["state_v02"], c["reasons_v02"] = ps.policy_v02(c, recipe)
        else:
            c["state_v02"], c["reasons_v02"] = "RETAKE", [c.get("roi_check", {}).get("failure") or "alignment_failed"]
    return dict(captures=captures, unlisted=unlisted, by_file=by_file, work=work, aligned=aligned, anchor=anchor, box=box,
                recipe=recipe, sheet_rows=rows, v03={}, v03_refs={})


def quality_v03(ctx, plan, file, light) -> tuple[str, list[str], dict]:
    """Policy v0.3 for a capture expected under `light`: same-light reference for sharpness and new clipping."""
    key = (file, light)
    if key in ctx["v03"]:
        return ctx["v03"][key]
    c = ctx["by_file"].get(file)
    if c is None:
        listed = next((x for x in ctx["captures"] if x.get("file") == file), {})
        out = ("RETAKE", ["unreadable" if listed.get("unreadable") else "missing_file"], {})
        ctx["v03"][key] = out
        return out
    metrics = {}
    extra = dict(c)
    ref_file = plan["references"][light]
    ref = ctx["by_file"].get(ref_file)
    if not (c.get("roi_check") or {}).get("verified") or file not in ctx["aligned"]:
        pass  # policy_v03 reports the registration reason
    elif ref is None or ref_file not in ctx["aligned"] or not ref.get("sharpness_tenengrad"):
        extra["reference_unavailable"] = True
    else:
        if light not in ctx["v03_refs"]:
            ctx["v03_refs"][light] = ps.reference_clip_in_anchor(ctx["work"][ref_file], ref["alignment"]["matrix"], ctx["anchor"].shape)
        ref_high, ref_low = ctx["v03_refs"][light]
        clip = ps.new_clip_fractions(ctx["work"][file], c["alignment"]["matrix"], ref_high, ref_low, ctx["box"], ctx["aligned"][file][1])
        metrics = dict(new_clip_high_v03=clip["new_clip_high"], new_clip_low_v03=clip["new_clip_low"],
                       sharpness_ratio_v03=c["sharpness_tenengrad"] / ref["sharpness_tenengrad"], reference_file_v03=ref_file)
        extra.update(metrics)
    state, reasons = ps.policy_v03(extra, ctx["recipe"])
    ctx["v03"][key] = (state, reasons, metrics)
    return ctx["v03"][key]


class Inspector:
    """Golden-reference inspection per image variant and light, with normal-only calibration."""

    def __init__(self, ctx, plan, restorers):
        self.ctx, self.plan, self.restorers = ctx, plan, restorers
        self.cache, self.calibration, self.seconds = {"original": dict(ctx["aligned"])}, {}, Counter()

    def view(self, variant, file):
        store = self.cache.setdefault(variant, {})
        if file not in store:
            c = self.ctx["by_file"].get(file)
            if c is None or file not in self.ctx["aligned"]:
                return None
            t0 = time.perf_counter()
            restored = self.restorers[variant](self.ctx["work"][file])
            store[file] = pc.warp_to_reference(restored, c["alignment"]["matrix"], self.ctx["anchor"].shape)
            self.seconds[f"restore_{variant}"] += time.perf_counter() - t0
        return store[file]

    def calibrate(self, variant, light):
        key = (variant, light)
        if key not in self.calibration:
            ref, cal = self.view(variant, self.plan["references"][light]), self.view(variant, self.plan["calibration"][light])
            if ref is None or cal is None:
                self.calibration[key] = None
            else:
                mask = ps.inspection_mask(self.ctx["anchor"].shape, self.ctx["box"], ref[1], cal[1])
                self.calibration[key] = dict(ps.gr_calibrate(ps.difference_map(cal[0], ref[0]), mask), light=light,
                                             variant=variant, reference=self.plan["references"][light],
                                             calibration=self.plan["calibration"][light])
        return self.calibration[key]

    def inspect(self, variant, file, light, keep_map=False):
        if variant != "original" and variant not in self.restorers:
            return dict(verdict="PENDING", note=f"restorer {variant} not available")
        test, cal = self.view(variant, file), self.calibrate(variant, light)
        if test is None or cal is None:
            return dict(verdict="ERROR", note="not registered to the anchor")
        t0 = time.perf_counter()
        ref = self.view(variant, self.plan["references"][light])
        diff = ps.difference_map(test[0], ref[0])
        mask = ps.inspection_mask(self.ctx["anchor"].shape, self.ctx["box"], ref[1], test[1])
        out = ps.gr_inspect(diff, mask, cal)
        out.update(tau=cal["tau"], base_score=cal["base_score"], light=light, variant=variant, file=file,
                   location_match=ps.location_match(out["centroid_xy"], self.plan.get("annotation_xy")))
        self.seconds["inspect"] += time.perf_counter() - t0
        if keep_map:
            out["_diff"], out["_mask"] = diff, mask
        return out


def run_cycle(cycle, condition, ctx, inspector, plan) -> dict:
    first, alt = cycle["first"], cycle.get("alternate")
    L0, L1 = plan["first_light"], plan["alternate_light"]
    row = dict(cycle_id=cycle["cycle_id"], kind=cycle.get("kind", ""), label=cycle["label"], condition=condition,
               first_file=first, alternate_file=alt or "", final_state="", captures_used=1, retake_requested=False,
               first_quality_state="", first_quality_reasons="", second_quality_state="", second_quality_reasons="",
               inspected=[], note=cycle.get("note", ""))

    def finish(results, state=None):
        results = [r for r in results if r]
        row["inspected"] = results
        if state is None:
            verdicts = [r["verdict"] for r in results]
            state = ("ERROR" if "ERROR" in verdicts else "PENDING" if "PENDING" in verdicts
                     else "NG" if "NG" in verdicts else "OK")
        row["final_state"] = state
        return row

    if condition == "C0_direct":
        return finish([inspector.inspect("original", first, L0)])
    if condition.startswith("C1_"):
        return finish([inspector.inspect(condition[3:], first, L0)])
    if condition == "C3_two_lights":
        if not alt:
            row["captures_used"], row["note"] = 0, (row["note"] + "; alternate light not captured").strip("; ")
            return finish([], "NA")
        row["captures_used"] = 2
        return finish([inspector.inspect("original", first, L0), inspector.inspect("original", alt, L1)])
    key = {"C2_policy_v0.1_roi": "v01", "C2_policy_v0.2": "v02", "C2_policy_v0.3": "v03"}[condition]

    def quality(file, light):
        if key == "v03":
            state, reasons, _ = quality_v03(ctx, plan, file, light)
            return state, ";".join(reasons)
        c = ctx["by_file"].get(file, {})
        return c.get(f"state_{key}", "RETAKE"), ";".join(c.get(f"reasons_{key}", ["missing_file"]))
    row["first_quality_state"], row["first_quality_reasons"] = quality(first, L0)
    if row["first_quality_state"] == "PASS":
        return finish([inspector.inspect("original", first, L0)])
    row["retake_requested"] = True
    if not alt:
        row["note"] = (row["note"] + "; retake_unavailable").strip("; ")
        return finish([], "REVIEW")
    row["captures_used"] = 2
    row["second_quality_state"], row["second_quality_reasons"] = quality(alt, L1)
    if row["second_quality_state"] == "PASS":
        return finish([inspector.inspect("original", alt, L1)])
    return finish([], "REVIEW")


def summarize(rows) -> list[dict]:
    out = []
    for cond in dict.fromkeys(r["condition"] for r in rows):
        rs = [r for r in rows if r["condition"] == cond]
        sim = [r for r in rs if r["label"] == "simulated_defect"]
        heldout = [r for r in rs if r["kind"] == "normal"]
        normal = [r for r in rs if r["label"] == "normal"]
        states = Counter(r["final_state"] for r in rs)
        located = sum(any(i.get("verdict") == "NG" and i.get("location_match") for i in r["inspected"]) for r in sim)
        out.append(dict(condition=cond, cycles=len(rs), OK=states["OK"], NG=states["NG"], REVIEW=states["REVIEW"],
                        ERROR=states["ERROR"], NA=states["NA"], PENDING=states["PENDING"],
                        captures_total=sum(r["captures_used"] for r in rs),
                        retakes_requested=sum(r["retake_requested"] for r in rs),
                        simulated_cycles=len(sim), simulated_final_OK=sum(r["final_state"] == "OK" for r in sim),
                        simulated_final_NG=sum(r["final_state"] == "NG" for r in sim), simulated_NG_at_annotation=located,
                        simulated_REVIEW_or_other=sum(r["final_state"] not in ("OK", "NG") for r in sim),
                        heldout_normal_cycles=len(heldout), heldout_normal_final_NG=sum(r["final_state"] == "NG" for r in heldout),
                        all_normal_cycles=len(normal), all_normal_final_NG=sum(r["final_state"] == "NG" for r in normal),
                        all_normal_final_NG_or_REVIEW=sum(r["final_state"] in ("NG", "REVIEW") for r in normal),
                        human_legibility_records=0))
    return out


def final_reason(row) -> str:
    """One readable reason for the final state of a cycle row."""
    if row["final_state"] == "REVIEW":
        tail = "retake_unavailable" if "retake_unavailable" in row["note"] else f"second capture {row['second_quality_state']}: {row['second_quality_reasons']}"
        return f"first capture {row['first_quality_state']}: {row['first_quality_reasons']}; {tail}"
    if row["final_state"] in ("OK", "NG"):
        parts = [f"{i.get('light')} reference: largest difference blob {i.get('score')} px vs limit {int(i.get('limit'))}" for i in row["inspected"]]
        lead = f"first capture {row['first_quality_state']} ({row['first_quality_reasons']}), alternate light used; " if row["retake_requested"] else ""
        return lead + "; ".join(parts)
    notes = "; ".join(i.get("note", "") for i in row["inspected"] if i.get("note"))
    return notes or row["note"] or row["final_state"]


def station_replay(cycle_rows, output: Path) -> dict:
    """Replay the operating-path cycles through the existing controller: one cycle, quality alert, at most one retake."""
    clock = iter(float(i) / 10 for i in range(10 ** 6))
    station = InspectionStation(timeout_seconds=5.0, clock=lambda: next(clock), clock_kind="simulation_seconds")
    log = []

    def send(msg):
        log.append(dict(kind="controller", command=msg, response=station.handle(msg)))
        return log[-1]["response"]
    send(dict(request_id="connect", command="connect"))
    for r in cycle_rows:
        cid = r["cycle_id"]
        send(dict(request_id=f"{cid}-start", command="start", cycle_id=cid, part_id=r["part_id"], recipe_id=r["recipe_id"],
                  image_ref=r["first_sha256"] or "unhashed"))
        log.append(dict(kind="station_event", cycle_id=cid, event="quality_checked", state=r["first_quality_state"],
                        reasons=r["first_quality_reasons"], capture=1))
        if r["retake_requested"]:
            log.append(dict(kind="station_event", cycle_id=cid, event="retake_requested", light=r["retake_light"],
                            available=bool(r["alternate_file"]), capture_budget=MAX_CAPTURES))
            if r["alternate_file"]:
                log.append(dict(kind="station_event", cycle_id=cid, event="quality_checked", state=r["second_quality_state"],
                                reasons=r["second_quality_reasons"], capture=2))
        verdict = r["final_state"] if r["final_state"] in ("OK", "NG", "REVIEW") else "ERROR"
        msg = dict(request_id=f"{cid}-complete", command="complete", cycle_id=cid, verdict=verdict,
                   result_source=f"{ps.GR_VERSION}; {ps.POLICY_V3}; captures={r['captures_used']}")
        if verdict == "ERROR":
            msg["error"] = r["final_state"]
        else:
            msg["prediction_ref"] = f"phone_station:{r['final_state']}:captures={r['captures_used']}"
        send(msg)
        send(dict(request_id=f"{cid}-ack", command="acknowledge", cycle_id=cid))
    with open(output / "station_events.jsonl", "w", encoding="utf-8") as f:
        for e in log:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    controller = [e for e in log if e["kind"] == "controller"]
    return dict(cycles=len(cycle_rows), commands=len(controller), all_accepted=all(e["response"]["accepted"] for e in controller),
                max_captures_per_cycle=max((r["captures_used"] for r in cycle_rows), default=0),
                verdicts=dict(Counter(station.cycles[r["cycle_id"]]["verdict"] for r in cycle_rows)))


# ---------------------------------------------------------------- report
def _uri(img: Image.Image, size=420) -> str:
    img = img.copy()
    img.thumbnail((size, size))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _panel(rgb, box, result=None, annotation=None) -> str:
    img = Image.fromarray(rgb)
    d = ImageDraw.Draw(img)
    d.rectangle(box, outline=(255, 220, 0), width=3)
    if result and result.get("bbox") and result.get("verdict") == "NG":
        b = result["bbox"]
        d.rectangle([b[0] - 6, b[1] - 6, b[2] + 6, b[3] + 6], outline=(255, 40, 40), width=3)
    return _uri(img)


def _diff_panel(result, box) -> str:
    d = np.clip(result["_diff"] / (3 * result["tau"]), 0, 1)
    d[~result["_mask"]] *= 0.25
    g = (d * 255).astype(np.uint8)
    img = Image.fromarray(np.stack([g, g, g], -1))
    if result.get("bbox") and result["verdict"] == "NG":
        b = result["bbox"]
        ImageDraw.Draw(img).rectangle([b[0] - 6, b[1] - 6, b[2] + 6, b[3] + 6], outline=(255, 40, 40), width=3)
    x0, y0, x1, y1 = box
    return _uri(img.crop((max(x0 - 20, 0), max(y0 - 20, 0), x1 + 20, y1 + 20)))


def _fmt(v):
    if v is None or v == "" or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def _table(rows, cols):
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(_fmt(r.get(c)))}</td>" for c in cols) + "</tr>" for r in rows)
    return f'<div class="wrap"><table><tr>{head}</tr>{body}</table></div>'


def render(manifest, summary, cycle_table, cards, station_rows) -> str:
    banner = ("SYNTHETIC test input — not a real capture and not a research result" if manifest["kind"] == "synthetic"
              else "Real photos, DEVELOPMENT session — one object, repeats are not independent parts; not a detection benchmark")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phone station comparison</title><style>
:root{{--bg:#f6f7f9;--fg:#17202b;--card:#fff;--muted:#526174;--line:#dde1e6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14181d;--fg:#e6e9ed;--card:#1d232a;--muted:#9aa6b3;--line:#323a44}}}}
body{{font:15px system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:16px;max-width:1500px;overflow-wrap:anywhere}}
.note{{background:#fff4d7;color:#3b2a00;padding:12px;border-left:4px solid #a57910}}.card{{background:var(--card);padding:12px;margin:12px 0}}
.imgs{{display:flex;flex-wrap:wrap;gap:10px}}figure{{margin:0;max-width:420px}}img{{max-width:100%;display:block}}figcaption,.muted{{color:var(--muted);font-size:13px}}
.wrap{{max-width:100%;overflow-x:auto}}table{{border-collapse:collapse;background:var(--card);margin:8px 0}}td,th{{padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:left}}
</style></head><body><h1>Phone station comparison (C0–C3)</h1>
<p class="note">{html.escape(banner)}. Decision {html.escape(manifest.get('decision_v3') or manifest['decision'])} (operating path v0.3; v0.1/v0.2 are comparison conditions; v0.2 design {html.escape(manifest['decision'])}) · source {html.escape(manifest['source_commit'][:10])}.
Golden-reference difference only; no learned detector. Simulated surface object, not an electrical defect. Times are software
seconds on this PC, not capture or equipment time. Yellow box = observation ROI, red box = largest difference blob when NG.</p>
<h2>Station result (operating path {html.escape(OPERATING)}: quality policy, at most one alternate-light input)</h2>
{_table(station_rows, ['cycle_id', 'kind', 'label', 'final_state', 'photos_used', 'reason'])}
<p class="muted">photos_used counts logical uses of stored photos in this offline run; capture time was not measured here.
Quality PASS means the input can be inspected; it is not the final OK.</p>
<h2>Summary by condition (all initial cycles in the denominator)</h2>
{_table(summary, ['condition', 'cycles', 'OK', 'NG', 'REVIEW', 'ERROR', 'NA', 'PENDING', 'captures_total', 'retakes_requested', 'simulated_cycles', 'simulated_final_NG', 'simulated_NG_at_annotation', 'simulated_final_OK', 'heldout_normal_cycles', 'heldout_normal_final_NG', 'all_normal_cycles', 'all_normal_final_NG', 'all_normal_final_NG_or_REVIEW'])}
<h2>Cycles</h2>{''.join(cards)}
<h2>All cycle × condition rows</h2>{_table(cycle_table, ['cycle_id', 'kind', 'label', 'condition', 'final_state', 'captures_used', 'retake_requested', 'first_quality_state', 'first_quality_reasons', 'second_quality_state', 'second_quality_reasons', 'scores', 'limits', 'note'])}
<p class="muted">CSV: cycles.csv, summary.csv, captures_quality.csv, inspections.csv · manifest.json · station_events.jsonl</p>
</body></html>"""


def compare(folder: Path, recipe_path: Path, plan_path: Path | None, output: Path, *, kind: str, restorers=None, guard=_budget,
            root=ROOT) -> dict:
    folder = Path(folder).resolve()
    if not (folder / "capture_sheet.csv").is_file():
        raise FileNotFoundError("capture_sheet.csv missing in the input folder")
    recipe = ps.load_recipe(recipe_path)          # recipe/plan problems stop the run before anything is written
    sheet = csv_rows(folder / "capture_sheet.csv", ("file", "part_id", "session_id", "recipe_id", "repeat_id"))
    listed = {r["file"].strip() for r in sheet if r.get("file")}
    if recipe["anchor"] not in listed:
        raise ValueError(f"recipe anchor {recipe['anchor']!r} is not in the capture sheet")
    if plan_path is None:
        plan = ps.plan_from_sheet(sheet, "L0", recipe["retake_light"])
    else:
        plan, plan_file = load_plan(plan_path, listed), Path(plan_path)
    restorers = restorers or {}
    output = new_output(output, inputs=[folder])  # refuses an existing directory: earlier results are never overwritten
    if plan_path is None:
        plan_file = output / "plan.from_sheet.json"
        write_json(plan_file, plan)
        plan = load_plan(plan_file, listed)
    t_all = time.perf_counter()
    ctx = prepare(folder, recipe, guard=guard)
    inspector = Inspector(ctx, plan, restorers)
    rows = [run_cycle(cycle, cond, ctx, inspector, plan) for cycle in plan["cycles"] for cond in CONDITIONS]
    summary = summarize(rows)

    inspections, table = [], []
    for r in rows:
        for i in r["inspected"]:
            inspections.append(dict(cycle_id=r["cycle_id"], condition=r["condition"], file=i.get("file", ""), light=i.get("light", ""),
                                    variant=i.get("variant", ""), verdict=i["verdict"], score=i.get("score"), limit=i.get("limit"),
                                    tau=i.get("tau"), base_score=i.get("base_score"), roi_valid_pixels=i.get("roi_valid_pixels"),
                                    centroid_x=(i.get("centroid_xy") or [None, None])[0], centroid_y=(i.get("centroid_xy") or [None, None])[1],
                                    location_match=i.get("location_match"), note=i.get("note", "")))
        table.append({**{k: v for k, v in r.items() if k != "inspected"},
                      "scores": "/".join(_fmt(i.get("score")) for i in r["inspected"]),
                      "limits": "/".join(_fmt(i.get("limit")) for i in r["inspected"])})
    qfields = ["row", "file", "part_id", "session_id", "recipe_id", "repeat_id", "attempt", "label_status", "sha256", "width", "height",
               "work_scale", "quality_basis", "alignment_success", "align_inliers", "align_inlier_ratio", "align_reproj_median_px",
               "rotation_deg", "scale_deviation", "perspective_term", "align_translation_fraction", "roi_inliers", "roi_inlier_bbox_fraction",
               "projected_coverage", "roi_verified", "roi_failure", "luma_mean", "clip_high_fraction", "clip_low_fraction",
               "reference_clip_high", "reference_clip_low", "new_clip_high", "new_clip_low", "sharpness_tenengrad", "sharpness_norm",
               "sharpness_ratio", "setup_moved", "state_v01", "reasons_v01", "state_v02", "reasons_v02", "seconds_decode",
               "seconds_register_quality", "error"]
    qrows = []
    for c in ctx["captures"]:
        a, k = c.get("alignment") or {}, c.get("roi_check") or {}
        qrows.append({**{f: c.get(f) for f in qfields}, "align_inliers": a.get("inliers"), "align_inlier_ratio": a.get("inlier_ratio"),
                      "align_reproj_median_px": a.get("reproj_median_px"), "align_translation_fraction": a.get("translation_fraction"),
                      "perspective_term": ps.perspective_term(a.get("matrix"), ctx["anchor"].shape) if a.get("success") else None,
                      "roi_inliers": k.get("roi_inliers"), "roi_inlier_bbox_fraction": k.get("roi_inlier_bbox_fraction"),
                      "projected_coverage": k.get("projected_coverage"), "roi_verified": k.get("verified"), "roi_failure": k.get("failure"),
                      "reasons_v01": ";".join(c.get("reasons_v01", [])), "reasons_v02": ";".join(c.get("reasons_v02", []))})
    write_csv(output / "captures_quality.csv", qrows, fields=qfields)
    write_csv(output / "cycles.csv", table)
    write_csv(output / "summary.csv", summary)
    group_of = {c["cycle_id"]: c.get("capture_group") or "" for c in plan["cycles"]}
    if any(group_of.values()):  # e.g. base32_v2 / micro18_challenge are analysed separately, never pooled
        by_group = []
        for g in dict.fromkeys(group_of.values()):
            by_group += [dict(capture_group=g, **s) for s in summarize([r for r in rows if group_of[r["cycle_id"]] == g])]
        write_csv(output / "summary_by_group.csv", by_group)
    write_csv(output / "inspections.csv", inspections)
    calib = [{k: v for k, v in c.items()} for c in inspector.calibration.values() if c]
    write_csv(output / "gr_calibration.csv", calib)

    c2 = [r for r in rows if r["condition"] == OPERATING]
    first = next(iter(ctx["by_file"].values()))
    replay_rows = [dict(r, part_id=first["part_id"], recipe_id=recipe["recipe_id"], retake_light=recipe["retake_light"],
                        first_sha256=ctx["by_file"].get(r["first_file"], {}).get("sha256")) for r in c2]
    station = station_replay(replay_rows, output)
    seconds_by_cycle = {c["cycle_id"]: c.get("capture_seconds", "") for c in plan["cycles"]}
    station_rows = [dict(cycle_id=r["cycle_id"], capture_group=group_of.get(r["cycle_id"], ""), kind=r["kind"], label=r["label"],
                         final_state=r["final_state"],
                         photos_used=r["captures_used"], retake_requested=r["retake_requested"], reason=final_reason(r),
                         first_file=r["first_file"], alternate_file=r["alternate_file"],
                         first_quality_state=r["first_quality_state"], second_quality_state=r["second_quality_state"],
                         capture_seconds_measured=seconds_by_cycle.get(r["cycle_id"], ""), policy=ps.POLICY_V3,
                         inspection=ps.GR_VERSION) for r in c2]
    write_csv(output / "station_result.csv", station_rows)
    v03_rows = []
    for c in ctx["captures"]:
        if c.get("file") in ctx["by_file"] and ctx["by_file"][c["file"]] is c:
            for light in (plan["first_light"], plan["alternate_light"]):
                state, reasons, m = quality_v03(ctx, plan, c["file"], light)
                v03_rows.append(dict(file=c["file"], recipe_id=c["recipe_id"], repeat_id=c["repeat_id"], expected_light=light,
                                     state_v03=state, reasons_v03=";".join(reasons), sharpness_ratio_v03=m.get("sharpness_ratio_v03"),
                                     new_clip_high_v03=m.get("new_clip_high_v03"), new_clip_low_v03=m.get("new_clip_low_v03"),
                                     reference_file=m.get("reference_file_v03")))
    write_csv(output / "captures_quality_v03.csv", v03_rows)

    seconds_before_panels = {k: float(v) for k, v in inspector.seconds.items()}  # comparison work only
    t_panels = time.perf_counter()
    cards = []
    for cycle in plan["cycles"]:
        mine = {r["condition"]: r for r in rows if r["cycle_id"] == cycle["cycle_id"]}
        figs = []
        for label, f, light in (("first capture", cycle["first"], plan["first_light"]),
                                ("alternate light", cycle.get("alternate"), plan["alternate_light"])):
            if not f:
                figs.append(f'<p class="muted">{label}: not captured.</p>')
                continue
            if f not in ctx["aligned"]:
                figs.append(f'<p class="muted">{label}: not registered to the anchor.</p>')
                continue
            res = inspector.inspect("original", f, light, keep_map=True)
            figs.append(f'<figure><img src="{_panel(ctx["aligned"][f][0], ctx["box"], res)}" alt="{label}">'
                        f'<figcaption>{label} ({html.escape(light)} reference), aligned · {res["verdict"]} · score {_fmt(res.get("score"))} / limit {_fmt(res.get("limit"))}</figcaption></figure>')
            figs.append(f'<figure><img src="{_diff_panel(res, ctx["box"])}" alt="difference"><figcaption>difference map, ROI crop (white = 3×τ)</figcaption></figure>')
        states = [dict(condition=k, final_state=v["final_state"], captures_used=v["captures_used"],
                       quality=(v["first_quality_state"] + (" → " + v["second_quality_state"] if v["second_quality_state"] else "")),
                       reasons=v["first_quality_reasons"]) for k, v in mine.items()]
        cards.append(f'<section class="card"><p><b>{html.escape(cycle["cycle_id"])}</b> · {html.escape(cycle.get("kind", ""))} · label '
                     f'{html.escape(cycle["label"])} <span class="muted">{html.escape(cycle.get("note", ""))}</span></p>'
                     f'<div class="imgs">{"".join(figs)}</div>{_table(states, ["condition", "final_state", "captures_used", "quality", "reasons"])}</section>')

    seconds_panels = time.perf_counter() - t_panels
    manifest = dict(kind=kind, decision=ps.DECISION, policy_version=ps.POLICY_VERSION, gr_version=ps.GR_VERSION,
                    created=datetime.now().astimezone().isoformat(timespec="seconds"), **source_state(root),
                    code_sha256={p: pc.sha256_file(root / p) for p in CODE}, recipe=recipe,
                    recipe_sha256=pc.sha256_file(recipe_path), plan_sha256=pc.sha256_file(plan_file), plan=plan,
                    plan_source="capture_sheet.csv" if plan_path is None else "plan file", operating_condition=OPERATING,
                    policy_v3=ps.POLICY_V3, decision_v3=DECISION_V3,
                    thresholds=dict(v01=pc.T, v02=ps.V2, golden_reference=ps.GR), conditions=list(CONDITIONS),
                    restorers=sorted(restorers), restoration_family="phone_x4_roundtrip (x0.25 then x4; not the benchmark x4 family)",
                    input=dict(capture_sheet_sha256=pc.sha256_file(folder / "capture_sheet.csv"),
                               files={c["file"]: c["sha256"] for c in ctx["captures"] if c.get("sha256")}),
                    session_role="development (methods fixed after a v0.1 audit of the same session; not an independent evaluation)",
                    software_seconds=dict(total_before_report=time.perf_counter() - t_all,
                                          decode=float(sum(c.get("seconds_decode") or 0 for c in ctx["captures"])),
                                          register_and_quality=float(sum(c.get("seconds_register_quality") or 0 for c in ctx["captures"])),
                                          **seconds_before_panels, report_panels=seconds_panels),
                    physical_capture_time=("from capture_sheet capture_seconds where filled" if any(seconds_by_cycle.values())
                                           else "not measured"),
                    station_replay=dict(station, kind="software_replay; simulation_seconds"),
                    summary=summary, research_metrics=None, report_contains_pixels=True)
    t_report = time.perf_counter()
    (output / "report.html").write_text(render(manifest, summary, table, cards, station_rows), encoding="utf-8")
    manifest["software_seconds"]["report_html_write"] = time.perf_counter() - t_report
    manifest["software_seconds"]["total"] = time.perf_counter() - t_all
    write_json(output / "manifest.json", manifest)
    return manifest


def real_restorers(assets_root: Path, device: str) -> dict:
    from sr_anomaly.real_models import SwinIRLightweight, matlab_bicubic_resize
    assets_root = Path(assets_root)
    basicsr = assets_root / "third_party" / "BasicSR"
    swinir = SwinIRLightweight(assets_root / "third_party/SwinIR",
                               assets_root / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth",
                               device=device, scale=4, tile=64, tile_overlap=0).restore
    down = lambda img: matlab_bicubic_resize(img, 0.25, basicsr)  # noqa: E731
    return {"bicubic_x4": lambda rgb: ps.x4_roundtrip(rgb, down, lambda lr: matlab_bicubic_resize(lr, 4.0, basicsr)),
            "swinir_x4": lambda rgb: ps.x4_roundtrip(rgb, down, swinir)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--recipe", type=Path, required=True)
    p.add_argument("--plan", type=Path, help="run plan JSON; omit to build it from capture_sheet station_role/cycle_id/light")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--kind", choices=("real", "synthetic"), required=True)
    p.add_argument("--assets-root", type=Path, help="checkout holding third_party/BasicSR, third_party/SwinIR and checkpoints/swinir")
    p.add_argument("--device", default="cuda")
    a = p.parse_args(argv)
    try:
        restorers = real_restorers(a.assets_root, a.device) if a.assets_root else {}
        m = compare(a.input, a.recipe, a.plan, a.output, kind=a.kind, restorers=restorers)
    except (ValueError, FileNotFoundError, FileExistsError) as e:
        print(f"STATION RUN STOPPED: {type(e).__name__}: {e}")  # nothing was overwritten
        return 2
    print(json.dumps({"operating_condition": OPERATING, "station_result": str(Path(a.output) / "station_result.csv"),
                      "report": str(Path(a.output) / "report.html"), "summary": m["summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
