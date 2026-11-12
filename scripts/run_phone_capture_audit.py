"""Audit a phone capture folder (docs/PHONE_QUALITY_PROTOCOL_V0.1.md): manifest/EXIF/SHA, alignment, ROI quality,
PASS/REVIEW/RETAKE policy, repeatability vs a no-policy baseline, station software replay and a local HTML report.

No detector or model is run. report.html embeds downscaled photos (private by default); CSV/JSON hold no pixels.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
from datetime import datetime
import html
import io
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import phone_capture as pc  # noqa: E402
from sr_anomaly.analysis_io import csv_rows, new_output, write_csv, write_json  # noqa: E402
from sr_anomaly.inspection_station import InspectionStation  # noqa: E402
from sr_anomaly.pcb_board_analysis import _budget  # noqa: E402

CODE = ("scripts/run_phone_capture_audit.py", "src/sr_anomaly/phone_capture.py", "src/sr_anomaly/inspection_station.py",
        pc.PROTOCOL)
THUMB = 320
METRICS = ("luma_mean", "luma_p01", "luma_p99", "clip_high_fraction", "clip_low_fraction", "sharpness_tenengrad",
           "noise_sigma", "rg_ratio", "bg_ratio")


def source_state(root=ROOT) -> dict:
    def git(*a):
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()
    tracked = git("status", "--porcelain", "--untracked-files=no")
    untracked = [x for x in git("status", "--porcelain").splitlines() if x.startswith("??")]
    return dict(source_commit=git("rev-parse", "HEAD"), source_branch=git("rev-parse", "--abbrev-ref", "HEAD"),
                tracked_worktree_dirty=bool(tracked), source_worktree_dirty=bool(tracked) or bool(untracked))


def _png_uri(rgb: np.ndarray) -> str:
    img = Image.fromarray(rgb)
    img.thumbnail((THUMB, THUMB))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _clip_overlay(rgb: np.ndarray) -> np.ndarray:
    out = (rgb.astype(np.float64) * 0.5).astype(np.uint8)
    out[(rgb >= pc.CLIP_HIGH).any(-1)] = (255, 40, 40)
    out[(rgb <= pc.CLIP_LOW).all(-1)] = (40, 90, 255)
    return out


def _diff_image(a, va, b, vb) -> np.ndarray:
    d = np.abs(pc.luma(a) - pc.luma(b))
    d[~(va & vb)] = 0
    d = np.clip(d * 4, 0, 255).astype(np.uint8)  # x4 display gain, stated in the report
    return np.stack([d, d, d], -1)


def _fmt(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def audit(folder: Path, output: Path, *, kind: str, guard=_budget, root=ROOT) -> dict:
    folder = Path(folder).resolve()
    output = new_output(output, inputs=[folder])
    sheet_path = folder / "capture_sheet.csv"
    if not sheet_path.is_file():
        raise FileNotFoundError("capture_sheet.csv missing")
    rows = csv_rows(sheet_path, ("file", "part_id", "session_id", "recipe_id", "repeat_id"))
    files = sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in pc.IMAGE_SUFFIXES)
    captures, unlisted = pc.parse_sheet(rows, files)
    sha_first = {}
    for c in captures:
        path = folder / c.get("file", "")
        c["missing"] = not c["invalid_reasons"] and not path.is_file()
        if not c["invalid_reasons"] and not c["missing"]:
            c["sha256"] = pc.sha256_file(path)
            c["bytes"] = path.stat().st_size
            if c["sha256"] in sha_first:
                c["duplicate_of"] = sha_first[c["sha256"]]
            sha_first.setdefault(c["sha256"], c["row"])
    for u in unlisted:
        u["sha256"] = pc.sha256_file(folder / u["file"])

    groups = defaultdict(list)
    for c in captures:
        if not c["invalid_reasons"]:
            groups[(c["part_id"], c["session_id"])].append(c)
    work, aligned = {}, {}
    for key, members in groups.items():
        refs = [c for c in members if c.get("reference") == "1"]
        if len(refs) > 1:
            for c in refs[1:]:
                c["invalid_reasons"] = ["multiple_reference"]
        order = refs[:1] + [c for c in members if c not in refs[:1]]
        reference = None
        roi_fractions = next(((float(c["roi_x0"]), float(c["roi_y0"]), float(c["roi_x1"]), float(c["roi_y1"]))
                              for c in members if all(c.get(k) for k in ("roi_x0", "roi_y0", "roi_x1", "roi_y1"))), None)
        for c in order:
            if c["invalid_reasons"] or c["missing"]:
                continue
            try:
                with Image.open(folder / c["file"]) as probe:
                    w, h = probe.size
                guard(int(w) * int(h) * 3 * 4 + pc.WORK_LONG_SIDE ** 2 * 8 * 12 + 64 * 1024 ** 2, None)
                rgb, exif = pc.decode(folder / c["file"])
            except MemoryError as e:
                c["unreadable"], c["error"] = True, f"BLOCKED_MEMORY: {e}"
                continue
            except (ValueError, OSError) as e:
                c["unreadable"], c["error"] = True, str(e)
                continue
            c.update({f"exif_{k}": v for k, v in exif.items()})
            c["width"], c["height"] = int(rgb.shape[1]), int(rgb.shape[0])
            w_rgb, scale = pc.working(rgb)
            del rgb
            c["work_scale"] = scale
            work[c["row"]] = w_rgb
            if reference is None:
                reference = c
        if reference is None:
            continue
        ref_rgb = work[reference["row"]]
        box = pc.roi_box(ref_rgb.shape, roi_fractions or (0, 0, 1, 1))
        ref_y = pc.luma(ref_rgb)
        for c in members:
            if c["row"] not in work:
                continue
            c["reference_row"] = reference["row"]
            c["roi_box_working"] = list(box)
            c["roi_default_full_frame"] = roi_fractions is None
            c["resolution_mismatch"] = (c["width"], c["height"]) != (reference["width"], reference["height"])
            if c is reference:
                a = dict(success=True, inliers=None, inlier_ratio=None, reproj_median_px=0.0, matrix=np.eye(3).tolist(),
                         translation_fraction=0.0, rotation_deg=0.0, scale_deviation=0.0, failure=None, matches=None)
            else:
                a = pc.align(ref_y, pc.luma(work[c["row"]]))
            c["alignment_success"] = a["success"]
            c["alignment_failure"] = a["failure"]
            for k in ("inliers", "matches", "inlier_ratio", "reproj_median_px", "translation_fraction", "rotation_deg",
                      "scale_deviation"):
                c[f"align_{k}"] = a[k]
            if a["reproj_median_px"] is not None and not math.isnan(a["reproj_median_px"]) and c["work_scale"]:
                c["align_reproj_median_fullres_px"] = a["reproj_median_px"] / c["work_scale"]
            c["setup_moved"] = pc.setup_moved(a)
            x0, y0, x1, y1 = box
            if a["success"]:
                warped, valid = pc.warp_to_reference(work[c["row"]], a["matrix"], ref_rgb.shape)
                roi, vroi = warped[y0:y1, x0:x1], valid[y0:y1, x0:x1]
                c["quality_basis"] = "aligned_roi"
            else:
                m = work[c["row"]]
                roi = m[y0:min(y1, m.shape[0]), x0:min(x1, m.shape[1])]
                vroi = np.ones(roi.shape[:2], bool)
                c["quality_basis"] = "unaligned_roi"
            try:
                c.update(pc.quality(roi, vroi))
            except ValueError as e:
                c["alignment_success"], c["alignment_failure"] = False, str(e)
                continue
            c["_thumb"] = _png_uri(work[c["row"]])
            c["_clip"] = _png_uri(_clip_overlay(roi))
            if a["success"]:
                aligned[c["row"]] = (roi, vroi)
        ref_roi = aligned.get(reference["row"])
        for c in members:
            if ref_roi is not None and c["row"] in aligned and c is not reference:
                c["_diff"] = _png_uri(_diff_image(*aligned[c["row"]], *ref_roi))
    del work

    # policy
    sharp = defaultdict(list)
    for c in captures:
        if c.get("sharpness_tenengrad") is not None:
            sharp[(c["part_id"], c["session_id"])].append(c["sharpness_tenengrad"])
    for c in captures:
        values = sharp.get((c.get("part_id"), c.get("session_id")), [])
        median = float(np.median(values)) if len(values) >= pc.T["sharpness_min_set"] else None
        c["state"], c["reasons"] = pc.policy(c, median)
        c["session_sharpness_median"] = median

    # slots (latest attempt wins) and repeatability
    slots = defaultdict(list)
    for c in captures:
        if not c["invalid_reasons"]:
            slots[(c["part_id"], c["session_id"], c["recipe_id"], c["repeat_id"])].append(c)
    slot_rows, latest = [], []
    for key, attempts in sorted(slots.items()):
        attempts.sort(key=lambda c: c["attempt"])
        last = attempts[-1]
        latest.append(last)
        slot_rows.append(dict(part_id=key[0], session_id=key[1], recipe_id=key[2], repeat_id=key[3],
                              attempts=len(attempts), history=" > ".join(f"a{c['attempt']}:{c['state']}" for c in attempts),
                              final_state=last["state"], final_row=last["row"], resolved=last["state"] == "PASS"))
    rep_rows, recipe_rows = [], []
    for scope in ("baseline_no_policy", "policy_pass_only"):
        by_recipe = defaultdict(list)
        for c in latest:
            ok = c["row"] in aligned and (scope == "baseline_no_policy" or c["state"] == "PASS")
            by_recipe[(c["part_id"], c["session_id"], c["recipe_id"])].append((c, ok))
        for key, members in sorted(by_recipe.items()):
            used = [c for c, ok in members if ok]
            maes = pc.pairwise_mae([aligned[c["row"]] for c in used])
            row = dict(scope=scope, part_id=key[0], session_id=key[1], recipe_id=key[2], slots=len(members), used=len(used),
                       pairs=len(maes), pairwise_mae_mean=float(np.mean(maes)) if maes else None,
                       pairwise_mae_min=min(maes) if maes else None, pairwise_mae_max=max(maes) if maes else None)
            for m in ("luma_mean", "clip_high_fraction", "sharpness_tenengrad"):
                v = [c[m] for c in used if c.get(m) is not None]
                row[f"{m}_mean"] = float(np.mean(v)) if v else None
                row[f"{m}_range"] = float(max(v) - min(v)) if len(v) >= 2 else None
            rep_rows.append(row)
        per_session = defaultdict(list)
        for r in [r for r in rep_rows if r["scope"] == scope]:
            per_session[(r["part_id"], r["session_id"])].append(r)
        for key, rs in sorted(per_session.items()):
            for m in ("luma_mean", "clip_high_fraction", "sharpness_tenengrad"):
                means = [r[f"{m}_mean"] for r in rs if r[f"{m}_mean"] is not None]
                ranges = [r[f"{m}_range"] for r in rs if r[f"{m}_range"] is not None]
                recipe_rows.append(dict(scope=scope, part_id=key[0], session_id=key[1], metric=m, recipes=len(means),
                                        between_recipe_range=float(max(means) - min(means)) if len(means) >= 2 else None,
                                        mean_within_recipe_range=float(np.mean(ranges)) if ranges else None))

    # station software replay (existing controller contract; detector not connected -> REVIEW only)
    clock = iter(float(i) / 10 for i in range(10 ** 6))
    station = InspectionStation(timeout_seconds=5.0, clock=lambda: next(clock), clock_kind="simulation_seconds")
    events = [dict(command=dict(request_id="connect", command="connect"))]
    events[0]["response"] = station.handle(events[0]["command"])
    cycles = []
    for c in captures:
        if c["invalid_reasons"] or c.get("missing"):
            continue
        cid = f"{c['session_id']}-{c['recipe_id']}-r{c['repeat_id']}-a{c['attempt']}"
        msgs = [dict(request_id=f"{cid}-start", command="start", cycle_id=cid, part_id=c["part_id"], recipe_id=c["recipe_id"],
                     image_ref=c.get("sha256", "unhashed")),
                dict(request_id=f"{cid}-complete", command="complete", cycle_id=cid, verdict="REVIEW",
                     prediction_ref=f"phone_quality:{c['state']}", result_source="phone_quality_v0.1; detector=not_connected"),
                dict(request_id=f"{cid}-ack", command="acknowledge", cycle_id=cid)]
        for m in msgs:
            events.append(dict(command=m, response=station.handle(m)))
        cyc = station.cycles[cid]
        cycles.append(dict(cycle_id=cid, part_id=c["part_id"], recipe_id=c["recipe_id"], image_ref=cyc["image_ref"],
                           verdict=cyc["verdict"], prediction_ref=cyc["result"]["prediction_ref"],
                           started_at_seconds=cyc["started_at_seconds"], completed_at_seconds=cyc["completed_at_seconds"],
                           clock_kind=cyc["clock_kind"]))
    with open(output / "station_events.jsonl", "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    write_csv(output / "station_cycles.csv", cycles)

    # tables
    fields = ["row", "file", "part_id", "session_id", "recipe_id", "repeat_id", "attempt", "label_status", "light_position",
              "flash", "ae_af_locked", "hdr", "state", "reasons", "sha256", "bytes", "width", "height", "work_scale",
              "reference_row", "roi_default_full_frame", "roi_box_working", "quality_basis", "alignment_success",
              "alignment_failure", "align_inliers", "align_matches", "align_inlier_ratio", "align_reproj_median_px",
              "align_reproj_median_fullres_px", "align_translation_fraction", "align_rotation_deg", "align_scale_deviation",
              "setup_moved", "resolution_mismatch", "duplicate_of", *METRICS, "session_sharpness_median", "error"]
    exif_fields = sorted({k for c in captures for k in c if k.startswith("exif_")})
    table = [{k: (";".join(c[k]) if k == "reasons" else c.get(k)) for k in fields + exif_fields} for c in captures]
    table += [dict(file=u["file"], state="REVIEW", reasons="unlisted_file", sha256=u["sha256"]) for u in unlisted]
    write_csv(output / "captures.csv", table, fields=fields + exif_fields)
    write_csv(output / "slots.csv", slot_rows, fields=["part_id", "session_id", "recipe_id", "repeat_id", "attempts", "history",
                                                       "final_state", "final_row", "resolved"])
    write_csv(output / "repeatability.csv", rep_rows)
    write_csv(output / "recipe_summary.csv", recipe_rows)
    counts = {s: sum(c["state"] == s for c in captures) for s in ("PASS", "REVIEW", "RETAKE")}
    counts["REVIEW"] += len(unlisted)
    summary = dict(attempts=len(captures), unlisted_files=len(unlisted), states=counts, slots=len(slot_rows),
                   slots_resolved=sum(r["resolved"] for r in slot_rows), slots_unresolved=sum(not r["resolved"] for r in slot_rows),
                   station_cycles=len(cycles), station_verdicts=sorted({c["verdict"] for c in cycles}))
    manifest = dict(kind=kind, protocol=pc.PROTOCOL, protocol_sha256=pc.sha256_file(root / pc.PROTOCOL),
                    created=datetime.now().astimezone().isoformat(timespec="seconds"), **source_state(root),
                    code_sha256={p: pc.sha256_file(root / p) for p in CODE},
                    thresholds=pc.T, orb=pc.ORB, ransac=pc.RANSAC, work_long_side=pc.WORK_LONG_SIDE,
                    input=dict(capture_sheet_sha256=pc.sha256_file(sheet_path), image_files=len(files),
                               files={c["file"]: c["sha256"] for c in captures if c.get("sha256")}),
                    summary=summary, detector="not_connected", research_metrics=None,
                    station_replay="software_replay_of_capture_audit; simulation_seconds, not physical latency",
                    report_contains_pixels=True)
    write_json(output / "manifest.json", manifest)
    (output / "report.html").write_text(render(captures, unlisted, slot_rows, rep_rows, recipe_rows, manifest), encoding="utf-8")
    return manifest


def _table(rows, cols):
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(_fmt(r.get(c)))}</td>" for c in cols) + "</tr>" for r in rows)
    return f'<div class="wrap"><table><tr>{head}</tr>{body}</table></div>'


def render(captures, unlisted, slots, rep, recipe, manifest) -> str:
    s = manifest["summary"]
    banner = ("SYNTHETIC test input — not a real capture and not a research result" if manifest["kind"] == "synthetic"
              else "Real capture audit — quality/alignment only; no detector connected")
    cards = []
    for c in captures:
        badge = c["state"].lower()
        imgs = "".join(f'<figure><img src="{c[k]}" alt="{t}"><figcaption>{t}</figcaption></figure>'
                       for k, t in (("_thumb", "original (working res)"), ("_clip", "ROI clip overlay: red ≥250, blue ≤5"),
                                    ("_diff", "|ΔY| vs reference ×4 (aligned)")) if c.get(k))
        if not imgs:
            imgs = '<p class="muted">Unavailable: no decodable image for this row.</p>'
        info = (f"<b>{html.escape(str(c.get('file', '')))}</b> · {html.escape(str(c.get('part_id', '')))}/"
                f"{html.escape(str(c.get('session_id', '')))}/{html.escape(str(c.get('recipe_id', '')))} "
                f"r{html.escape(str(c.get('repeat_id', '')))} a{html.escape(str(c.get('attempt', '')))}")
        metrics = " · ".join(f"{m}={_fmt(c.get(m))}" for m in ("luma_mean", "clip_high_fraction", "clip_low_fraction",
                                                                 "sharpness_tenengrad", "align_inliers", "align_reproj_median_px")
                             if c.get(m) is not None)
        cards.append(f'<section class="card"><p>{info} <span class="badge {badge}">{c["state"]}</span> '
                     f'<span class="muted">{html.escape(";".join(c["reasons"]))}</span></p><div class="imgs">{imgs}</div>'
                     f'<p class="muted">{html.escape(metrics)}</p></section>')
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phone capture audit</title><style>
:root{{--bg:#f6f7f9;--fg:#17202b;--card:#fff;--muted:#526174;--line:#dde1e6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14181d;--fg:#e6e9ed;--card:#1d232a;--muted:#9aa6b3;--line:#323a44}}}}
body{{font:15px system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:16px;max-width:1500px;overflow-wrap:anywhere}}
h1,h2,p{{max-width:100%}}
.note{{background:#fff4d7;color:#3b2a00;padding:12px;border-left:4px solid #a57910}}.card{{background:var(--card);padding:12px;margin:12px 0}}
.imgs{{display:flex;flex-wrap:wrap;gap:10px}}figure{{margin:0;max-width:320px}}img{{max-width:100%;display:block}}figcaption,.muted{{color:var(--muted);font-size:13px}}
.badge{{padding:2px 8px;border-radius:4px;font-weight:600}}.pass{{background:#d9f2df;color:#0c4a1d}}.review{{background:#fff1c2;color:#5c4100}}.retake{{background:#ffd9d6;color:#6b0f08}}
.wrap{{max-width:100%;overflow-x:auto}}table{{border-collapse:collapse;background:var(--card);margin:8px 0}}td,th{{padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:left}}
</style></head><body>
<h1>Phone capture audit</h1><p class="note">{html.escape(banner)}. Protocol {html.escape(manifest['protocol'])} ·
source {html.escape(manifest['source_commit'][:10])} · thresholds fixed before photos. Station replay uses simulation seconds,
not physical latency. Luma is code-value Y (0–255), not lux.</p>
<p>Attempts {s['attempts']} · PASS {s['states']['PASS']} · REVIEW {s['states']['REVIEW']} · RETAKE {s['states']['RETAKE']} ·
unlisted files {s['unlisted_files']} · slots {s['slots']} (resolved {s['slots_resolved']}, unresolved {s['slots_unresolved']}) ·
station verdicts {', '.join(s['station_verdicts']) or '—'} (detector not connected)</p>
<h2>Slots and retake history</h2>{_table(slots, ['part_id', 'session_id', 'recipe_id', 'repeat_id', 'attempts', 'history', 'final_state'])}
<h2>Repeatability: no-policy baseline vs PASS-only</h2>
<p class="muted">Latest attempt per slot. Pairwise MAE = mean |ΔY| on the aligned ROI; only captures that aligned to the reference can
enter pairs, so 'used' ≤ 'slots' even without a policy. Repeats of one object are not independent parts.</p>{_table(rep, ['scope', 'part_id', 'session_id', 'recipe_id', 'slots', 'used', 'pairs', 'pairwise_mae_mean', 'pairwise_mae_max', 'luma_mean_mean', 'luma_mean_range', 'clip_high_fraction_mean', 'sharpness_tenengrad_mean', 'sharpness_tenengrad_range'])}
<h2>Between-recipe vs within-recipe spread</h2>{_table(recipe, ['scope', 'part_id', 'session_id', 'metric', 'recipes', 'between_recipe_range', 'mean_within_recipe_range'])}
<h2>Captures</h2>{''.join(cards)}
{('<h2>Unlisted files</h2>' + _table(unlisted, ['file', 'sha256'])) if unlisted else ''}
<p class="muted">CSV: captures.csv, slots.csv, repeatability.csv, recipe_summary.csv, station_cycles.csv · manifest.json</p>
</body></html>"""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True, help="folder with images + capture_sheet.csv")
    p.add_argument("--output", type=Path, required=True, help="new output directory")
    p.add_argument("--kind", choices=("real", "synthetic"), required=True)
    a = p.parse_args(argv)
    m = audit(a.input, a.output, kind=a.kind)
    print(json.dumps(m["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
