"""Poster figures from stored CSV/JSON and the private photos. Every number is read from a file; see figure_sources.json.

Run from the GPU checkout root with PYTHONPATH pointing at the phone worktree src.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
from PIL import Image, ImageDraw

from sr_anomaly import phone_capture as pc
from sr_anomaly import phone_station as ps

ROOT = Path(".").resolve()
OUT = ROOT / "outputs/final-delivery-20261115/poster_figures"
RUN = ROOT / "outputs/phone-station-20261116-final"
PHOTOS = ROOT / "outputs/phone-captures/20261115"
HANDOFF = ROOT.parent / "juhyung-handoff-20261110-152518"
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 20, "axes.titlesize": 22,
                     "axes.labelsize": 20, "xtick.labelsize": 18, "ytick.labelsize": 18, "legend.fontsize": 17,
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 200, "savefig.bbox": "tight"})
BLUE, ORANGE, GREEN, RED, GREY, GOLD = "#35608f", "#d9822b", "#3c8d5a", "#c0392b", "#8a94a0", "#b8860b"
SOURCES = {}


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def git_show(ref_path):
    return subprocess.run(["git", "show", ref_path], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def save(fig, name, sources):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name)
    plt.close(fig)
    SOURCES[name] = sources


# ------------------------------------------------------------------ B. benchmark: Hazelnut regression + noise contrasts
def fig_benchmark():
    summary = json.loads(git_show("57235a2:analysis/hazelnut/cross_category_summary.json"))
    master = list(csv.DictReader(git_show("57235a2:analysis/noise_repeatability_20261111/master/master_results.csv").splitlines()))
    hist = {r["variant"]: float(r["pooled_aupro"]) for r in master if r["study_family"] == "historical_recovery" and r["category"] == "hazelnut"}
    fig, (a, b) = plt.subplots(1, 2, figsize=(17, 5.6), gridspec_kw={"width_ratios": [1, 1.45], "wspace": 0.3})
    parts = [("나빠짐\nsuppression", summary["suppression_count"], RED), ("나빠짐\ngeometry\ncandidate", summary["geometry_candidate_count"], ORANGE),
             ("같거나 좋아짐", summary["improvement_or_tie_count"], GREEN)]
    left = 0
    for label, n, colour in parts:
        a.barh([0.25], [n], left=left, color=colour, height=0.6)
        a.text(left + n / 2, 0.25, str(n), ha="center", va="center", color="white", fontsize=26, fontweight="bold")
        a.barh([-9], [0], color=colour, label=f"{n}장: " + label.replace("\n", " "))
        left += n
    a.set_xlim(0, summary["total_anomalous_images"])
    a.set_yticks([])
    a.set_xlabel(f"Hazelnut 이상 영상 {summary['total_anomalous_images']}장 (영상별 AU-PRO 변화)")
    a.set_title(f"평균은 개선 (pooled AU-PRO {hist['bicubic_x4']:.3f} → {hist['swinir_x4']:.3f})\n그러나 {summary['localization_regression_count']}장은 나빠짐", loc="left")
    a.set_ylim(-0.75, 0.62)
    a.legend(loc="lower left", frameon=False, fontsize=17, borderaxespad=0.2)

    def pooled(path):
        return {(r["condition"], r["restorer"]): float(r["au_pro"]) for r in rows(path)}
    x, labels = 0, []
    for cat in ("hazelnut", "screw"):
        runs = [("v1", pooled(ROOT / f"outputs/realistic-degradation/{cat}-v1/summary.csv")),
                ("seed 23", pooled(ROOT / f"outputs/realistic-noise-v2/{cat}-noise23/summary.csv")),
                ("seed 37", pooled(ROOT / f"outputs/realistic-noise-v2/{cat}-noise37/summary.csv"))]
        for cond, sigma in (("noise_s5", "σ5"), ("noise_s15", "σ15")):
            d1 = [s[cond, "swinir_x4"] - s[cond, "bicubic_x4"] for _, s in runs]
            d2 = [s[cond, "realesrgan_x4plus"] - s[cond, "swinir_x4"] for _, s in runs]
            b.scatter([x - 0.16] * 3, d1, s=170, color=BLUE, zorder=3, label="SwinIR - Bicubic" if x == 0 else None)
            b.scatter([x + 0.16] * 3, d2, s=170, color=ORANGE, marker="s", zorder=3, label="RealESRGAN - SwinIR" if x == 0 else None)
            b.plot([x - 0.16] * 2, [min(d1), max(d1)], color=BLUE, lw=3)
            b.plot([x + 0.16] * 2, [min(d2), max(d2)], color=ORANGE, lw=3)
            labels.append(f"{cat.capitalize()}\n{sigma}")
            x += 1
    b.axhline(0, color="black", lw=1.2)
    b.set_xticks(range(4), labels)
    b.set_ylabel("AU-PRO 차이 (pooled)")
    b.set_title("LR 입력에 노이즈가 있으면 순위가 바뀐다\n(점 3개 = 같은 영상에 노이즈만 다시 뽑은 3회)", loc="left")
    b.legend(frameon=False, loc="upper left")
    save(fig, "fig_B_benchmark.png", ["57235a2:analysis/hazelnut/cross_category_summary.json",
                                      "57235a2:analysis/noise_repeatability_20261111/master/master_results.csv (historical_recovery)",
                                      "outputs/realistic-degradation/<cat>-v1/summary.csv", "outputs/realistic-noise-v2/<cat>-noise{23,37}/summary.csv"])


# ------------------------------------------------------------------ C. Screw image decision vs aggregation rule
def fig_screw():
    s = rows(ROOT / "outputs/image-score-aggregation-clean-control-20261112/summary.csv")
    rules = ["original", "map_max", "top0.1pct_mean", "top0.5pct_mean", "top1pct_mean"]
    names = ["원본\n점수", "map\nmax", "상위\n0.1%", "상위\n0.5%", "상위\n1%"]
    fig, ax = plt.subplots(figsize=(9.2, 6.4))
    for i, (variant, label, colour) in enumerate((("clean", "clean", GREEN), ("bicubic_x4", "Bicubic ×4", GREY), ("swinir_x4", "SwinIR ×4", BLUE))):
        v = [float(next(r for r in s if r["variant"] == variant and r["rule"] == rule)["image_auroc"]) for rule in rules]
        aupro = float(next(r for r in s if r["variant"] == variant)["reference_au_pro"])
        ax.bar(np.arange(5) + (i - 1) * 0.27, v, 0.26, color=colour, label=f"{label} (AU-PRO {aupro:.3f})")
    ax.axhline(0.5, color="black", ls="--", lw=1.4, label="우연 수준 0.5")
    ax.set_xticks(range(5), names)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("image AUROC")
    ax.set_title("Screw: ×4 뒤 이미지 판정이 무너지고,\n집계 규칙을 바꿔도 회복되지 않는다", loc="left")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.46, -0.2), ncol=2, columnspacing=1.2, handletextpad=0.5)
    fig.tight_layout()
    save(fig, "fig_C_screw_aggregation.png", ["outputs/image-score-aggregation-clean-control-20261112/summary.csv (returned as image-score-aggregation-clean-control-20261112)"])


# ------------------------------------------------------------------ METHODS: station flow
def fig_flow():
    fig, ax = plt.subplots(figsize=(12.4, 7.6))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 7.95)
    ax.axis("off")

    def box(x, y, w, h, text, colour, tc="white", fs=16):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.1", fc=colour, ec="none"))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc, fontsize=fs, linespacing=1.3)

    def arrow(p, q, text=None, colour="#333333", rad=0.0, at=None):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=24, lw=2.6, color=colour, connectionstyle=f"arc3,rad={rad}"))
        if text:
            x, y = at or ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            ax.text(x, y, text, ha="center", va="center", fontsize=15, color=colour)
    box(0.1, 6.0, 2.75, 1.4, "① 촬영\nrecipe, 첫 조명 L0", BLUE)
    box(3.25, 6.0, 2.75, 1.4, "② 정렬\n관찰 영역 검증", BLUE)
    box(6.4, 6.0, 2.75, 1.4, "③ 입력 품질\n같은 조명 참조 대비", BLUE)
    box(9.55, 6.0, 2.75, 1.4, "④ 검사\n기준 사진과의 차이", BLUE)
    arrow((2.85, 6.7), (3.25, 6.7))
    arrow((6.0, 6.7), (6.4, 6.7))
    arrow((9.15, 6.7), (9.55, 6.7))
    ax.text(9.35, 7.52, "PASS", ha="center", va="bottom", fontsize=15, color=GREEN)
    box(6.4, 3.7, 2.75, 1.4, "⑤ 대체 조명 L1\n최대 1회 (총 2장)", ORANGE)
    arrow((7.78, 6.0), (7.78, 5.1), "PASS 아님", ORANGE, at=(8.75, 5.55))
    arrow((6.4, 4.6), (4.63, 6.0), "②③ 다시", ORANGE, rad=-0.2, at=(4.75, 5.0))
    box(9.55, 3.7, 2.75, 1.4, "OK / NG\n차이 25 px 이상이면 NG", GREEN, fs=14)
    arrow((10.93, 6.0), (10.93, 5.1))
    box(6.4, 1.75, 2.75, 1.2, "REVIEW\n미해결, 대체 사진 없음", RED, fs=15)
    arrow((7.78, 3.7), (7.78, 2.95), "두 번째도 PASS 아님", RED, at=(9.35, 3.32))
    box(0.1, 0.15, 12.2, 1.0, "⑥ 이력: cycle, 원본 SHA-256, recipe, 정책 버전, 사진 수, 최종 상태와 이유 (CSV / HTML)", "#e8ecf1", tc="#17202b")
    arrow((7.78, 1.75), (7.78, 1.15))
    arrow((10.93, 3.7), (10.93, 1.15))
    box(0.1, 2.3, 5.2, 2.2, "비교군 (같은 cycle에 적용)\nC0 직접 검사\nC1 ×4 복원 후 검사\nC3 항상 두 조명", "#f4f0e4", tc="#17202b")
    save(fig, "fig_M_station_flow.png", ["docs/DESIGN_DECISION_PHONE_V0.3.md §1, §4"])


# ------------------------------------------------------------------ E. real photos (private)
def _work(name):
    return pc.working(pc.decode(PHOTOS / name)[0])[0]


def _draw_box(img, box, colour, width=5):
    ImageDraw.Draw(img).rectangle(list(box), outline=colour, width=width)
    return img


def fig_photos():
    manifest = json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))
    plan, recipe = manifest["plan"], manifest["recipe"]
    anchor = _work(recipe["anchor"])
    box = pc.roi_box(anchor.shape, recipe["roi"])
    anchor_y = pc.luma(anchor)

    def aligned(name):
        if name == recipe["anchor"]:
            return anchor, np.ones(anchor.shape[:2], bool)
        m = _work(name)
        a = pc.align(anchor_y, pc.luma(m))
        return pc.warp_to_reference(m, a["matrix"], anchor.shape)
    cyc = {c["cycle_id"]: c for c in plan["cycles"]}
    panels = []
    x0, y0, x1, y1 = box
    crop = (x0 - 12, y0 - 12, x1 + 12, y1 + 12)
    for light, key in (("L0", "first"), ("L1", "alternate")):
        ref, rv = aligned(plan["references"][light])
        cal, cv = aligned(plan["calibration"][light])
        test, tv = aligned(cyc["foreign-1"][key])
        calib = ps.gr_calibrate(ps.difference_map(cal, ref), ps.inspection_mask(anchor.shape, box, rv, cv))
        diff = ps.difference_map(test, ref)
        res = ps.gr_inspect(diff, ps.inspection_mask(anchor.shape, box, rv, tv), calib)
        b = res["bbox"]
        red = (b[0] - 10, b[1] - 10, b[2] + 10, b[3] + 10)
        photo = _draw_box(_draw_box(Image.fromarray(test), box, (255, 220, 0)), red, (255, 40, 40))
        g = (np.clip(diff / (3 * calib["tau"]), 0, 1) * 255).astype(np.uint8)
        dmap = _draw_box(Image.fromarray(np.stack([g, g, g], -1)), red, (255, 40, 40))
        panels.append((photo.crop(crop), dmap.crop(crop), light, res))
    fig, axes = plt.subplots(1, 5, figsize=(22, 4.9), gridspec_kw={"width_ratios": [1.33, 1, 1, 1, 1]})
    axes[0].imshow(_draw_box(Image.fromarray(anchor), box, (255, 220, 0), 7))
    axes[0].set_title("기준 사진과 관찰 영역(노란 상자)", loc="left", fontsize=19)
    titles = []
    for i, (photo, dmap, light, res) in enumerate(panels):
        axes[1 + 2 * i].imshow(photo)
        axes[1 + 2 * i].set_title(f"모사 이물, {light} 조명", loc="left", fontsize=19)
        axes[2 + 2 * i].imshow(dmap)
        axes[2 + 2 * i].set_title(f"차이 지도 {res['score']} px → NG", loc="left", fontsize=19)
        titles.append((light, res["score"]))
    for ax in axes:
        ax.axis("off")
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig_E1_real_photos.png", ["private photos outputs/phone-captures/20261115 (cycle foreign-1, references and calibration from manifest.plan)",
                                         f"recomputed scores {titles}; stored in outputs/phone-station-20261116-final/inspections.csv"])
    stored = {(r["file"], r["light"]): r["score"] for r in rows(RUN / "inspections.csv") if r["condition"] == "C3_two_lights" and r["cycle_id"] == "foreign-1"}
    assert [str(s) for _, s in titles] == [stored[cyc["foreign-1"]["first"], "L0"], stored[cyc["foreign-1"]["alternate"], "L1"]], (titles, stored)

    # quality example: full-frame clipping vs ROI, and the low-light retake pair
    first = _work(cyc["normal-3"]["first"])
    overlay = (first.astype(np.float64) * 0.55).astype(np.uint8)
    high = (first >= pc.CLIP_HIGH).any(-1)
    overlay[high] = (255, 40, 40)
    q = {r["file"]: r for r in rows(RUN / "captures_quality.csv")}
    full = {r["file"]: r for r in rows(ROOT / "outputs/phone-audit-20261115-v01-dev/captures.csv")}
    low, alt = _work(cyc["lowlight-3"]["first"]), _work(cyc["lowlight-3"]["alternate"])
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.6))
    axes[0].imshow(_draw_box(Image.fromarray(overlay), box, (255, 220, 0), 7))
    f, r = cyc["normal-3"]["first"], q[cyc["normal-3"]["first"]]
    axes[0].set_title(f"포화(빨강)는 배경에 있다\n화면 전체 {float(full[f]['clip_high_fraction']) * 100:.1f}%, 관찰 영역 새 포화 {float(r['new_clip_high']) * 100:.1f}%", loc="left", fontsize=18)
    axes[1].imshow(_draw_box(Image.fromarray(low), box, (255, 220, 0), 7))
    axes[1].set_title(f"첫 입력: 저조도 (평균 Y {float(q[cyc['lowlight-3']['first']]['luma_mean']):.0f})\n품질 REVIEW → 대체 조명 요청", loc="left", fontsize=18)
    axes[2].imshow(_draw_box(Image.fromarray(alt), box, (255, 220, 0), 7))
    axes[2].set_title("대체 조명 L1: 품질 PASS\n검사 OK (사진 2장 사용)", loc="left", fontsize=18)
    for ax in axes:
        ax.axis("off")
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig_E2_quality_and_retake.png", ["private photos (cycles normal-3, lowlight-3)", "outputs/phone-audit-20261115-v01-dev/captures.csv",
                                                "outputs/phone-station-20261116-final/captures_quality.csv, station_result.csv"])


# ------------------------------------------------------------------ E. quality states and C0-C3 comparison
def fig_quality_states():
    full = rows(ROOT / "outputs/phone-audit-20261115-v01-dev/captures.csv")
    q = rows(RUN / "captures_quality.csv")
    v3 = rows(RUN / "captures_quality_v03.csv")
    light_of = {r["file"]: ("L1" if r["recipe_id"] in ("L1", "F1") else "L0") for r in q}
    series = [("v0.1\n화면 전체", [r["state"] for r in full if r["row"]]), ("v0.1\n관찰 영역", [r["state_v01"] for r in q]),
              ("v0.2\n기준 사진 대비", [r["state_v02"] for r in q]),
              ("v0.3\n같은 조명 참조", [r["state_v03"] for r in v3 if r["expected_light"] == light_of[r["file"]]])]
    fig, ax = plt.subplots(figsize=(8.6, 6.0))
    bottom = np.zeros(len(series))
    for state, colour in (("PASS", GREEN), ("REVIEW", GOLD), ("RETAKE", RED)):
        counts = np.array([s.count(state) for _, s in series])
        ax.bar(range(len(series)), counts, bottom=bottom, color=colour, label=state, width=0.62)
        for i, (c, b0) in enumerate(zip(counts, bottom)):
            if c:
                ax.text(i, b0 + c / 2, str(c), ha="center", va="center", color="white", fontsize=22, fontweight="bold")
        bottom += counts
    assert all(len(s) == 24 for _, s in series), [len(s) for _, s in series]
    ax.set_xticks(range(len(series)), [n for n, _ in series])
    ax.set_ylabel("사진 수 (24장)")
    ax.set_title("입력 품질 판정 (같은 사진 24장)\n사람 판독 기록이 없어 정책의 정확도 순위는 NA", loc="left")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    fig.tight_layout()
    save(fig, "fig_E3_quality_states.png", ["outputs/phone-audit-20261115-v01-dev/captures.csv", "outputs/phone-station-20261116-final/captures_quality.csv",
                                           "outputs/phone-station-20261116-final/captures_quality_v03.csv"])
    return {n.replace("\n", " "): {st: s.count(st) for st in ("PASS", "REVIEW", "RETAKE")} for n, s in series}


def fig_conditions():
    cyc = rows(RUN / "cycles.csv")
    membership = rows(HANDOFF / "analysis/phone_station_return_20261115/cohort_membership.csv")
    paired = {r["cycle_id"] for r in membership if r["paired_available"] == "True"}
    conds = [("C0_direct", "C0"), ("C3_two_lights", "C3"), ("C2_policy_v0.3", "C2\nv0.3"),
             ("C2_policy_v0.2", "C2\nv0.2"), ("C1_bicubic_x4", "C1\nBicubic"), ("C1_swinir_x4", "C1\nSwinIR")]
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 6.0), sharey=False, gridspec_kw={"wspace": 0.24})
    out = {}
    for ax, (title, subset) in zip(axes, ((f"두 조명 사진이 있는 {len(paired)} cycle", paired),
                                          ("전체 16 cycle (C3 9건 NA)", {r["cycle_id"] for r in cyc}))):
        bottom = np.zeros(len(conds))
        for state, colour in (("OK", GREEN), ("NG", RED), ("REVIEW", GOLD), ("NA", "#c9ced6")):
            counts = np.array([sum(r["final_state"] == state for r in cyc if r["condition"] == c and r["cycle_id"] in subset) for c, _ in conds])
            ax.bar(range(len(conds)), counts, bottom=bottom, color=colour, label=state, width=0.66)
            for i, (c, b0) in enumerate(zip(counts, bottom)):
                if c:
                    ax.text(i, b0 + c / 2, str(c), ha="center", va="center", color="white" if state != "NA" else "#333", fontsize=20, fontweight="bold")
            bottom += counts
        uses = [sum(int(r["captures_used"]) for r in cyc if r["condition"] == c and r["cycle_id"] in subset) for c, _ in conds]
        for i, u in enumerate(uses):
            ax.text(i, bottom[i] + bottom.max() * 0.02, f"{u}장", ha="center", va="bottom", fontsize=19, color=BLUE, fontweight="bold")
        ax.set_ylim(0, bottom.max() * 1.14)
        ax.set_yticks(range(0, int(bottom.max()) + 1, 1 if bottom.max() <= 8 else 4))
        ax.set_xticks(range(len(conds)), [n for _, n in conds], fontsize=16)
        ax.set_title(title, loc="left")
        ax.set_ylabel("cycle 수")
        out[title] = dict(zip([c for c, _ in conds], uses))
    axes[0].legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(1.1, -0.2))
    fig.text(0.5, 0.94, "막대 위 파란 숫자 = 사진 사용 수 (논리적 사용 횟수)", ha="center", fontsize=18, color=BLUE)
    fig.subplots_adjust(top=0.82)
    save(fig, "fig_E4_conditions.png", ["outputs/phone-station-20261116-final/cycles.csv",
                                        "handoff/juhyung@8ddde87:analysis/phone_station_return_20261115/cohort_membership.csv (paired_available)"])
    return out, sorted(paired)


if __name__ == "__main__":
    which = sys.argv[1:] or ["benchmark", "screw", "flow", "photos", "states", "conditions"]
    info = {}
    if "benchmark" in which:
        fig_benchmark()
    if "screw" in which:
        fig_screw()
    if "flow" in which:
        fig_flow()
    if "photos" in which:
        fig_photos()
    if "states" in which:
        info["quality_states"] = fig_quality_states()
    if "conditions" in which:
        info["photo_uses"], info["paired_cycles"] = fig_conditions()
    (OUT / "figure_sources.json").write_text(json.dumps(dict(sources=SOURCES, checks=info), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False))
