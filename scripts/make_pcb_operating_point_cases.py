"""PCB (VisA pcb2, native full board) operating-point decision changes, with the stored RGB, GT and maps.

Reads the stored full-cohort results only: per-board normalized image scores (per_board.csv for clean / bicubic_x4 /
swinir_x4), the fixed thresholds of each variant (normal-calibration q0.99, pcb_operating_points.csv), the stored
native maps (units_manifest.csv -> predictions/*.npy) and the VisA image/mask files. Writes the 2x2 decision-change
table Bicubic -> SwinIR for anomalies and normals, and figures for selected cases.
Case choice (post-hoc illustration; GT/labels used after inference): the TP->FN case among the earlier 9 selected
native-map cases (036) plus the TP->FN case with the largest Bicubic margin that clean also detects, the FN->TP case
with the largest SwinIR margin, and the FP->TN normal with the largest Bicubic margin. Maps share one colour range per
case (raw PatchCore distance); the image decision uses the normalized score against each variant's own threshold.
No restored RGB is stored for the full board, so the image panel is the original board photo.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})
import numpy as np
from PIL import Image

V = ("clean", "bicubic_x4", "swinir_x4")
V_KO = {"clean": "원본 입력", "bicubic_x4": "Bicubic ×4", "swinir_x4": "SwinIR ×4"}


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort", type=Path, required=True, help="outputs/pcb-full-cohort/<run>")
    p.add_argument("--postprocess", type=Path, required=True, help="outputs/pcb-full-postprocess/<run>")
    p.add_argument("--operating-points", type=Path, required=True)
    p.add_argument("--data-root", type=Path, required=True, help="VisA root")
    p.add_argument("--earlier-cases", type=Path, help="selected_native_map_cases.csv of the earlier 9 cases")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    out = a.output
    out.mkdir(parents=True, exist_ok=False)
    thr = {r["variant"]: float(r["fixed_threshold"]) for r in rows(a.operating_points)}
    s = {}
    for v in V:
        for r in rows(a.postprocess / f"perboard-{v}" / "per_board.csv"):
            s.setdefault(r["sample"], {"label": int(r["label"])})[v] = float(r["normalized_image_score"])
    for d in s.values():
        for v in V:
            d[v + "_pos"] = d[v] >= thr[v]
    table = []
    for lab, name in ((1, "anomaly"), (0, "normal")):
        for b in (True, False):
            for w in (True, False):
                table.append(dict(label=name, bicubic_positive=b, swinir_positive=w,
                                  images=sum(1 for d in s.values() if d["label"] == lab and d["bicubic_x4_pos"] == b and d["swinir_x4_pos"] == w)))
    with open(out / "decision_changes_bicubic_to_swinir.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    units = {(r["sample"], r["variant"]): r for r in rows(a.cohort / "units_manifest.csv") if r["split"] == "test"}
    earlier = {r["sample"] for r in rows(a.earlier_cases)} if a.earlier_cases else set()
    tp_fn = [k for k, d in s.items() if d["label"] and d["bicubic_x4_pos"] and not d["swinir_x4_pos"]]
    fn_tp = [k for k, d in s.items() if d["label"] and not d["bicubic_x4_pos"] and d["swinir_x4_pos"]]
    fp_tn = [k for k, d in s.items() if not d["label"] and d["bicubic_x4_pos"] and not d["swinir_x4_pos"]]
    picks = []
    reuse = sorted(k for k in tp_fn if k in earlier)
    if reuse:
        picks.append(("TP→FN (기존 9사례)", reuse[0]))
    both = [k for k in tp_fn if s[k]["clean_pos"] and k not in reuse[:1]]
    if both:
        picks.append(("TP→FN (원본 입력은 검출)", max(both, key=lambda k: s[k]["bicubic_x4"] - thr["bicubic_x4"])))
    if fn_tp:
        picks.append(("FN→TP", max(fn_tp, key=lambda k: s[k]["swinir_x4"] - thr["swinir_x4"])))
    if fp_tn:
        picks.append(("FP→TN (정상)", max(fp_tn, key=lambda k: s[k]["bicubic_x4"] - thr["bicubic_x4"])))
    index = []
    for title, k in picks:
        maps = {}
        for v in V:
            u = units[(k, v)]
            arr = np.load(a.cohort / u["file"], allow_pickle=False)
            if sha256((a.cohort / u["file"]).read_bytes()).hexdigest() != u["sha256"]:
                raise ValueError(f"{u['file']} hash differs from units_manifest")
            maps[v] = arr
        rgb = np.asarray(Image.open(a.data_root / k).convert("RGB"))
        mask_path = a.data_root / k.replace("/Images/", "/Masks/").replace(".JPG", ".png")
        gt = (np.asarray(Image.open(mask_path).convert("L")) > 0) if s[k]["label"] else np.zeros(rgb.shape[:2], bool)
        if gt.any():
            ys, xs = np.nonzero(gt)
            cy, cx = (ys.min() + ys.max()) // 2, (xs.min() + xs.max()) // 2
            half = int(max(80, 0.75 * max(np.ptp(ys), np.ptp(xs))))
        else:
            cy, cx = np.unravel_index(np.argmax(maps["bicubic_x4"]), maps["bicubic_x4"].shape)
            half = 120
        y0, y1 = max(cy - half, 0), min(cy + half, rgb.shape[0])
        x0, x1 = max(cx - half, 0), min(cx + half, rgb.shape[1])
        sl = (slice(y0, y1), slice(x0, x1))
        vmax = float(max(m[sl].max() for m in maps.values()))
        fig, ax = plt.subplots(1, 5, figsize=(21, 4.9), gridspec_kw={"wspace": 0.05})
        ax[0].imshow(rgb[sl])
        ax[0].set_title("원본 기판 사진 (확대)", fontsize=13, loc="left")
        ax[1].imshow(gt[sl], cmap="gray", vmin=0, vmax=1)
        ax[1].set_title("GT 결함 영역" if s[k]["label"] else "정상 영상 (GT 없음)", fontsize=13, loc="left")
        for i, v in enumerate(V):
            ax[2 + i].imshow(maps[v][sl], cmap="viridis", vmin=0, vmax=vmax)
            if gt.any():
                ax[2 + i].contour(gt[sl].astype(float), levels=[0.5], colors="#ff3030", linewidths=1.3)
            dec = "이상 판정" if s[k][v + "_pos"] else "정상 판정"
            ax[2 + i].set_title(f"{V_KO[v]} 지도\n점수 {s[k][v]:.2f} / 임계 {thr[v]:.2f} → {dec}", fontsize=13, loc="left")
        for x in ax:
            x.set_xticks([])
            x.set_yticks([])
        fig.suptitle(f"PCB · {title} · {k.split('/')[-1]} · 임계값은 변형별 정상 보정 q0.99 · 지도 색 범위 공통(원시 거리)",
                     fontsize=14, x=0.01, ha="left")
        name = f"pcb_{k.split('/')[-2].lower()}_{k.split('/')[-1].split('.')[0]}.png"
        fig.savefig(out / name, dpi=100, bbox_inches="tight")
        plt.close(fig)
        index.append(dict(case=title, sample=k, png=name, label=s[k]["label"], crop=f"{x0},{y0},{x1},{y1}",
                          **{f"score_{v}": round(s[k][v], 4) for v in V}, **{f"threshold_{v}": round(thr[v], 4) for v in V},
                          **{f"map_{v}": units[(k, v)]["file"] for v in V}))
    with open(out / "index.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index[0]))
        w.writeheader()
        w.writerows(index)
    (out / "manifest.json").write_text(json.dumps(dict(
        kind="pcb_operating_point_cases", thresholds=thr, n_images=len(s), counts=dict(TP_to_FN=len(tp_fn), FN_to_TP=len(fn_tp), FP_to_TN=len(fp_tn)),
        selection_rule=__doc__.split("Case choice")[1].split(".")[0],
        files={f.name: sha256(f.read_bytes()).hexdigest() for f in sorted(out.glob("*")) if f.name != "manifest.json"}), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(cases=[i["sample"] for i in index], TP_to_FN=len(tp_fn), FN_to_TP=len(fn_tp), FP_to_TN=len(fp_tn))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
