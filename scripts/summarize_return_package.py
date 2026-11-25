"""Derived tables/figures for the return package (read-only over existing outputs; no model, no GT reload).

Realistic degradation (hazelnut-v1, screw-v1) -> analysis/realistic_degradation/derived/
PCB full cohort postprocess (pcb-full-cohort-20261101-a) -> analysis/pcb_full_cohort/derived/
Refuses to write into an existing derived directory.
"""
from pathlib import Path
import csv
import json
import math

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "outputs/realistic-degradation"
PCB_RAW = ROOT / "outputs/pcb-full-cohort/pcb-full-cohort-20261101-a"
PCB_POST = ROOT / "outputs/pcb-full-postprocess/pcb-full-cohort-20261101-a"
CATEGORIES = ("hazelnut", "screw")
CONDITIONS = ("none", "noise_s5", "noise_s15", "blur_s0.8", "blur_s1.6", "jpeg_q90", "jpeg_q50")
RESTORERS = ("bicubic_x4", "swinir_x4", "realesrnet_x4plus", "realesrgan_x4plus")
COLORS = {"bicubic_x4": "#7f7f7f", "swinir_x4": "#1f77b4", "realesrnet_x4plus": "#2ca02c", "realesrgan_x4plus": "#d62728",
          "clean": "#000000"}


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def realistic(out):
    summary, per_image = [], {}
    for cat in CATEGORIES:
        base = REAL / f"{cat}-v1"
        summary += read_csv(base / "summary.csv")
        for c in CONDITIONS:
            for r in RESTORERS:
                rows = [x for x in read_csv(base / "units" / f"{c}__{r}.csv") if x["split"] == "test"]
                receipt = json.loads((base / "units" / f"{c}__{r}.json").read_text(encoding="utf-8"))
                per_image[cat, c, r] = (rows, receipt)
    write_csv(out / "summary_56.csv", summary)

    # Unit-level delta vs bicubic (same category/condition) + paired per-anomaly-image AU-PRO delta.
    deltas, cases, dist = [], [], {}
    for cat in CATEGORIES:
        for c in CONDITIONS:
            ref_rows, ref = per_image[cat, c, "bicubic_x4"]
            ref_map = {x["sample"]: x for x in ref_rows if x["label"] == "1"}
            for r in RESTORERS[1:]:
                rows, rec = per_image[cat, c, r]
                paired = [(x["sample"], x["defect_type"], f(x["per_image_aupro"]) - f(ref_map[x["sample"]]["per_image_aupro"]))
                          for x in rows if x["label"] == "1"]
                d = np.array([p[2] for p in paired])
                dist.setdefault((cat, r), []).extend(d.tolist())
                deltas.append(dict(category=cat, condition=c, restorer=r,
                                   au_pro=rec["metrics"]["au_pro"], au_pro_bicubic=ref["metrics"]["au_pro"],
                                   delta_au_pro=rec["metrics"]["au_pro"] - ref["metrics"]["au_pro"],
                                   delta_pixel_auroc=rec["metrics"]["pixel_auroc"] - ref["metrics"]["pixel_auroc"],
                                   delta_image_auroc=rec["metrics"]["image_auroc"] - ref["metrics"]["image_auroc"],
                                   delta_psnr=rec["means"]["psnr"] - ref["means"]["psnr"],
                                   delta_lpips=rec["means"]["lpips"] - ref["means"]["lpips"],
                                   n_anomaly_images=len(d), per_image_delta_mean=float(d.mean()),
                                   per_image_delta_median=float(np.median(d)),
                                   n_better=int((d > 0).sum()), n_worse=int((d < 0).sum()), n_tie=int((d == 0).sum())))
                for s, t, v in paired:
                    cases.append(dict(category=cat, condition=c, restorer=r, sample=s, defect_type=t,
                                      per_image_aupro_bicubic=f(ref_map[s]["per_image_aupro"]), delta_vs_bicubic=v))
    write_csv(out / "delta_vs_bicubic.csv", deltas)
    # Success / regression cases: 5 largest gains and 5 largest losses per category x restorer (over all conditions).
    picked = []
    for cat in CATEGORIES:
        for r in RESTORERS[1:]:
            group = sorted((x for x in cases if x["category"] == cat and x["restorer"] == r), key=lambda x: x["delta_vs_bicubic"])
            picked += [dict(kind="regression", **x) for x in group[:5]] + [dict(kind="success", **x) for x in group[::-1][:5]]
    write_csv(out / "success_regression_cases.csv", picked)

    # Per-defect-type table.
    per_defect = []
    for (cat, c, r), (rows, _) in per_image.items():
        for t in sorted({x["defect_type"] for x in rows if x["label"] == "1"}):
            v = np.array([f(x["per_image_aupro"]) for x in rows if x["label"] == "1" and x["defect_type"] == t])
            per_defect.append(dict(category=cat, condition=c, restorer=r, defect_type=t, n=len(v),
                                   mean_per_image_aupro=float(np.nanmean(v)), median_per_image_aupro=float(np.nanmedian(v))))
    write_csv(out / "per_defect_type.csv", per_defect)

    # Runtime table.
    runtime = [dict(category=cat, condition=c, restorer=r, **{f"{k}_seconds": v for k, v in rec["timing_seconds"].items()},
                    images=rec["images"]["calibration"] + rec["images"]["test"], au_pro=rec["metrics"]["au_pro"])
               for (cat, c, r), (_, rec) in per_image.items()]
    write_csv(out / "runtime.csv", runtime)

    # Figures.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, key, label in zip(axes, ("mean_psnr", "mean_lpips"), ("mean PSNR (dB)", "mean LPIPS (lower = closer)")):
        for row in summary:
            ax.scatter(f(row[key]), f(row["au_pro"]), color=COLORS[row["restorer"]],
                       marker="o" if row["category"] == "hazelnut" else "^", s=36, alpha=.85)
        ax.set_xlabel(label); ax.set_ylabel("pooled AU-PRO@0.3"); ax.grid(alpha=.3)
    handles = [plt.Line2D([], [], color=COLORS[r], marker="s", ls="", label=r) for r in RESTORERS]
    handles += [plt.Line2D([], [], color="k", marker=m, ls="", label=c) for m, c in (("o", "hazelnut"), ("^", "screw"))]
    axes[1].legend(handles=handles, fontsize=8, loc="lower left")
    fig.suptitle("Realistic degradation: restoration quality vs localization (56 units, descriptive)")
    fig.tight_layout(); fig.savefig(out / "quality_detection_scatter.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.2))
    keys = [(cat, r) for cat in CATEGORIES for r in RESTORERS[1:]]
    ax.boxplot([dist[k] for k in keys], showfliers=False)
    ax.set_xticks(range(1, len(keys) + 1), [f"{c}\n{r.replace('_x4plus', '').replace('_x4', '')}" for c, r in keys], fontsize=8)
    ax.axhline(0, color="k", lw=.8); ax.set_ylabel("per-image AU-PRO delta vs Bicubic")
    ax.set_title("Paired per-anomaly-image delta, pooled over 7 conditions (outliers hidden)")
    ax.grid(axis="y", alpha=.3); fig.tight_layout(); fig.savefig(out / "delta_distribution.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.4))
    for row in runtime:
        ax.scatter(row["restore_seconds"] / row["images"], row["au_pro"], color=COLORS[row["restorer"]],
                   marker="o" if row["category"] == "hazelnut" else "^", s=36, alpha=.85)
    ax.set_xscale("log"); ax.set_xlabel("restore seconds per image (log; MX570 A, CUDA)"); ax.set_ylabel("pooled AU-PRO@0.3")
    ax.legend(handles=handles, fontsize=8); ax.grid(alpha=.3); ax.set_title("Runtime vs localization (descriptive)")
    fig.tight_layout(); fig.savefig(out / "runtime_performance.png", dpi=130); plt.close(fig)
    return dict(units=len(summary))


def pcb(out):
    rows = []
    for v in ("clean", "bicubic_x4", "swinir_x4"):
        status = json.loads((PCB_POST / f"evaluate-{v}" / "status.json").read_text(encoding="utf-8"))
        record = json.loads((PCB_POST / f"evaluate-{v}.record.json").read_text(encoding="utf-8"))
        rows.append(dict(variant=v, **status["metrics"]["classification"], **status["metrics"]["localization"],
                         evaluate_seconds=record["elapsed_seconds"], evaluate_peak_rss_bytes=record["process_memory"]["sampled_peak_rss_bytes"]))
    quality = json.loads((PCB_POST / "quality" / "status.json").read_text(encoding="utf-8"))["rows"]
    for row in rows:
        q = [x for x in quality if x["variant"] == row["variant"]]
        row["mean_psnr"] = float(np.mean([f(x["psnr"]) for x in q])) if row["variant"] != "clean" else None
        row["mean_ssim"] = float(np.mean([f(x["ssim"]) for x in q]))
        row["quality_rows"] = len(q)
    write_csv(out / "summary.csv", rows)

    boards = {v: {x["sample"]: x for x in read_csv(PCB_POST / f"perboard-{v}" / "per_board.csv")} for v in ("clean", "bicubic_x4", "swinir_x4")}
    qmap = {(x["sample"], x["variant"]): x for x in quality}
    merged = []
    for s, c in boards["clean"].items():
        row = dict(sample=s, label=int(c["label"]))
        for v in boards:
            b = boards[v][s]
            row[f"score_{v}"] = f(b["normalized_image_score"])
            row[f"per_image_aupro_{v}"] = f(b.get("per_image_aupro"))
            row[f"roi_bg_gap_{v}"] = f(b.get("roi_bg_gap"))
            if v != "clean" and (s, v) in qmap:
                row[f"psnr_{v}"] = f(qmap[s, v]["psnr"]); row[f"ssim_{v}"] = f(qmap[s, v]["ssim"])
        row["defect_area_ratio"] = f(c.get("defect_area_ratio")); row["region_count"] = c.get("region_count")
        merged.append(row)
    write_csv(out / "per_board_merged.csv", merged)

    bad = [r for r in merged if r["label"] == 1]
    pairs = (("swinir_x4", "bicubic_x4"), ("swinir_x4", "clean"), ("bicubic_x4", "clean"))
    dist_rows, dist = [], {}
    for a, b in pairs:
        d = np.array([r[f"per_image_aupro_{a}"] - r[f"per_image_aupro_{b}"] for r in bad])
        dist[a, b] = d
        dist_rows.append(dict(comparison=f"{a}-{b}", n=len(d), mean=float(d.mean()), median=float(np.median(d)),
                              q10=float(np.quantile(d, .1)), q90=float(np.quantile(d, .9)),
                              n_better=int((d > 0).sum()), n_worse=int((d < 0).sum()), n_tie=int((d == 0).sum())))
    write_csv(out / "delta_distribution.csv", dist_rows)

    # Defect-size terciles stand in for defect type (no PCB defect-type labels are bound in this pipeline).
    area = np.array([r["defect_area_ratio"] for r in bad]); edges = np.quantile(area, [1 / 3, 2 / 3])
    terc = []
    for i, name in enumerate(("small", "medium", "large")):
        members = [r for r, a in zip(bad, area) if (a <= edges[0] if i == 0 else a > edges[1] if i == 2 else edges[0] < a <= edges[1])]
        terc.append(dict(defect_area_tercile=name, n=len(members),
                         area_ratio_min=min(r["defect_area_ratio"] for r in members), area_ratio_max=max(r["defect_area_ratio"] for r in members),
                         **{f"mean_per_image_aupro_{v}": float(np.mean([r[f"per_image_aupro_{v}"] for r in members])) for v in boards}))
    write_csv(out / "per_defect_size_tercile.csv", terc)

    order = sorted(bad, key=lambda r: r["per_image_aupro_swinir_x4"] - r["per_image_aupro_bicubic_x4"])
    cases = [dict(kind=k, sample=r["sample"], delta_swinir_minus_bicubic=r["per_image_aupro_swinir_x4"] - r["per_image_aupro_bicubic_x4"],
                  **{f"per_image_aupro_{v}": r[f"per_image_aupro_{v}"] for v in boards}, defect_area_ratio=r["defect_area_ratio"])
             for k, group in (("regression", order[:10]), ("success", order[::-1][:10])) for r in group]
    write_csv(out / "success_regression_cases.csv", cases)

    # Runtime from raw-run sessions (excluding nothing: all sessions summed; 002/003 flagged as sleep-affected).
    stages, sessions = {}, []
    for p in sorted((PCB_RAW / "sessions").glob("[0-9][0-9][0-9].json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        sessions.append(dict(session=s["session"], start=s["start_time"], end=s["end_time"], outer_elapsed_seconds=s["outer_elapsed_seconds"],
                             completed_units=len(s["completed_units"]), skipped_verified_units=s["skipped_verified_units"],
                             peak_rss_bytes=s["process_memory"]["sampled_peak_rss_bytes"], source_commit=s["source_commit"],
                             source_worktree_dirty=s["source_worktree_dirty"], gpu=s["gpu_name"],
                             note_sleep_affected=s["session"] in (2, 3)))
        for k, v in s["stage_aggregate"].items():
            agg = stages.setdefault(k, dict(stage=k, calls=0, sum_elapsed_seconds=0.0))
            agg["calls"] += v["calls"]; agg["sum_elapsed_seconds"] += v["sum_elapsed_seconds"]
    write_csv(out / "raw_sessions.csv", sessions)
    total = sum(v["sum_elapsed_seconds"] for v in stages.values())
    for v in stages.values():
        v["share_of_staged_time"] = v["sum_elapsed_seconds"] / total
    write_csv(out / "raw_stage_times.csv", sorted(stages.values(), key=lambda v: -v["sum_elapsed_seconds"]))

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.boxplot([dist[p] for p in pairs], showfliers=True)
    ax.set_xticks([1, 2, 3], [f"{a}\n- {b}" for a, b in pairs], fontsize=8); ax.axhline(0, color="k", lw=.8)
    ax.set_ylabel("per-board AU-PRO delta (100 anomalous boards)"); ax.grid(axis="y", alpha=.3)
    ax.set_title("PCB full cohort: paired per-board delta (descriptive)")
    fig.tight_layout(); fig.savefig(out / "delta_distribution.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    for v in ("bicubic_x4", "swinir_x4"):
        ax.scatter([r[f"psnr_{v}"] for r in bad], [r[f"per_image_aupro_{v}"] for r in bad], s=14, alpha=.7, color=COLORS[v], label=v)
    ax.set_xlabel("board PSNR vs clean (dB)"); ax.set_ylabel("per-board AU-PRO@0.3"); ax.legend(); ax.grid(alpha=.3)
    ax.set_title("PCB: restoration quality vs per-board localization")
    fig.tight_layout(); fig.savefig(out / "quality_detection_scatter.png", dpi=130); plt.close(fig)
    return dict(boards=len(merged))


def main():
    outs = {"realistic": ROOT / "analysis/realistic_degradation/derived", "pcb": ROOT / "analysis/pcb_full_cohort/derived"}
    for p in outs.values():
        p.mkdir(parents=True, exist_ok=False)
    print(json.dumps({"realistic": realistic(outs["realistic"]), "pcb": pcb(outs["pcb"])}))


if __name__ == "__main__":
    main()
