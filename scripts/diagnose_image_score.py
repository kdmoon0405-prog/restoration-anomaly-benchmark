"""Post-hoc image-score diagnosis from SAVED predictions only (no model, no re-inference, no reselection).

pcb   : PCB full raw run + frozen v0.6 calibration. Board score = max of original tile image scores (not map max).
        Reports calibration tail / q0.99, test score distributions, confusion, matched-FPR TPR, calibration-only
        threshold sensitivity, score<->map linkage over all 1140 maps, map-argmax tile proxy and (post-hoc GT) whether
        the anomaly-board map peak lies inside the defect.
screw : historical PIL, MATLAB endpoint and realistic-none families; score distributions and map-peak-in-GT rates.

Test labels/GT are used only for post-hoc description. Nothing here changes a threshold, bank or method.
Outputs refuse to overwrite.
"""
from pathlib import Path
import argparse
import csv
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.fusion import normalize, quantile_threshold, robust_params  # noqa: E402
from sr_anomaly.evaluation import binary_roc_auc  # noqa: E402

VARIANTS = ("clean", "bicubic_x4", "swinir_x4")
FPRS = (0.01, 0.02, 0.03, 0.05, 0.10)


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "x", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def confusion(labels, scores, threshold):
    pred = scores >= threshold
    tp = int((pred & (labels == 1)).sum()); fn = int((~pred & (labels == 1)).sum())
    fp = int((pred & (labels == 0)).sum()); tn = int((~pred & (labels == 0)).sum())
    f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, f1=f1)


def tpr_at_fpr(labels, scores, fpr):
    """Post-hoc ranking view: threshold = the k-th highest test-normal score with k = floor(fpr * n_normal)."""
    normal = np.sort(scores[labels == 0])[::-1]
    k = int(np.floor(fpr * len(normal)))
    thr = normal[k] if k < len(normal) else -np.inf  # strictly above the (k+1)-th highest normal
    pred = scores > thr
    return float(pred[labels == 1].mean()), int(pred[labels == 0].sum())


def summary(values):
    v = np.asarray(values, float)
    return dict(n=len(v), min=v.min(), q10=np.quantile(v, .1), median=np.median(v), q90=np.quantile(v, .9), max=v.max())


def pcb(args):
    from sr_anomaly import pcb_board_analysis as board
    from sr_anomaly import pcb_full_cohort as full
    from sr_anomaly.pcb_tiling import tile_boxes
    raw = ROOT / "outputs/pcb-full-cohort/pcb-full-cohort-20261101-a"
    cal = ROOT / "outputs/pcb-full-postprocess/pcb-full-cohort-20261101-a/calibration"
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    state, parents = board.load_raw_run(raw)
    params = {v: json.loads((cal / f"{v}.json").read_text(encoding="utf-8")) for v in VARIANTS}
    rows = state["rows"]
    # 1) linkage: manifest index <-> file <-> sample/variant order (plan: parent-major, VARIANTS-minor).
    plan = [(p.sample, v) for p in parents if p.split != "fit" for v in VARIANTS]
    link = dict(rows=len(rows), plan=len(plan),
                order_matches_plan=[(r["sample"], r["variant"]) for r in rows] == plan,
                file_index_matches=all(r["file"] == f"predictions/{i:04d}.npy" for i, r in enumerate(rows)))
    # 2) calibration tail, thresholds, test distributions.
    report, dist, sens, matched = {}, [], [], []
    norm = {}
    for v in VARIANTS:
        c = np.array([r["score"] for r in rows if r["split"] == "calibration" and r["variant"] == v])
        p = robust_params(c)
        cn = normalize(c, p)
        thr = quantile_threshold(cn, .99)
        t = [r for r in rows if r["split"] == "test" and r["variant"] == v]
        lab = np.array([r["label"] for r in t]); s = normalize(np.array([r["score"] for r in t]), p)
        norm[v] = {r["sample"]: x for r, x in zip(t, s)}
        top = np.sort(cn)[::-1]
        report[v] = dict(reconstructed_threshold=thr, stored_threshold=params[v]["image_threshold"],
                         threshold_match=bool(np.isclose(thr, params[v]["image_threshold"], rtol=0, atol=1e-12)),
                         image_median_raw=p["median"], image_scale_raw=p["scale"],
                         calibration_top5_normalized=top[:5].tolist(), calibration_above_threshold=int((cn >= thr).sum()),
                         q99_interpolation="np.quantile linear: 0.99*(180-1)=177.21 -> between 3rd and 2nd highest",
                         threshold_minus_3rd_highest=float(thr - top[2]), top1_minus_threshold=float(top[0] - thr),
                         auroc=binary_roc_auc(lab, s), **confusion(lab, s, thr),
                         test_normal_above_calibration_max=int((s[lab == 0] > top[0]).sum()))
        for split, vals in (("calibration_normal", cn), ("test_normal", s[lab == 0]), ("test_anomaly", s[lab == 1])):
            dist.append(dict(variant=v, group=split, **summary(vals)))
        for name, alt in (("q0.99_frozen", thr), ("q0.98", quantile_threshold(cn, .98)), ("q0.995", quantile_threshold(cn, .995)),
                          ("calibration_max", top[0]), ("q0.99_drop_top1", quantile_threshold(top[1:], .99)),
                          ("q0.99_raw_then_normalize", float(normalize(np.array([np.quantile(c, .99)]), p)[0]))):
            sens.append(dict(variant=v, threshold_rule=name, threshold=float(alt), diagnostic_only=True, **confusion(lab, s, alt)))
        for f in FPRS:
            tpr, nfp = tpr_at_fpr(lab, s, f)
            matched.append(dict(variant=v, test_fpr_target=f, test_normals_flagged=nfp, tpr=tpr, post_hoc_ranking_view=True))
    (out / "pcb_threshold_report.json").write_text(json.dumps(dict(linkage=link, variants=report), indent=1, default=float), encoding="utf-8")
    write_csv(out / "pcb_score_distribution.csv", dist)
    write_csv(out / "pcb_threshold_sensitivity_diagnostic.csv", sens)
    write_csv(out / "pcb_matched_fpr_tpr.csv", matched)

    # 3) per-map pass: score vs map max, argmax tile proxy, post-hoc peak-in-GT for anomaly boards.
    inputs = full.fit.binding.FrozenPCBInputs(ROOT, args.data_root) if args.data_root else None
    inventory = {p.sample: p for p in parents}
    per_map = []
    for i, r in enumerate(rows):
        m = np.load(raw / r["file"], mmap_mode="r")
        m = np.asarray(m)
        boxes = tile_boxes(tuple(r["size_wh"]))
        tile_max = np.array([m[y0:y1, x0:x1].max() for x0, y0, x1, y1 in boxes])
        y, x = np.unravel_index(int(np.argmax(m)), m.shape)
        containing = [t for t, (x0, y0, x1, y1) in enumerate(boxes) if x0 <= x < x1 and y0 <= y < y1]
        row = dict(index=i, sample=r["sample"], split=r["split"], label=r["label"], variant=r["variant"], raw_score=r["score"],
                   normalized_score=norm[r["variant"]].get(r["sample"]) if r["split"] == "test" else
                   float(normalize(np.array([r["score"]]), params[r["variant"]]["image"])[0]),
                   map_max=float(m.max()), map_mean=float(m.mean()), map_p999=float(np.quantile(m, .999)),
                   argmax_y=int(y), argmax_x=int(x), argmax_tile_proxy=int(np.argmax(tile_max)), argmax_tiles_containing=";".join(map(str, containing)),
                   score_minus_map_max=float(r["score"] - m.max()))
        if inputs is not None and r["label"] == 1:
            gt = inputs.evaluation_mask(inventory[r["sample"]]).astype(bool)
            row.update(peak_in_gt=bool(gt[y, x]), max_in_gt=float(m[gt].max()), max_outside_gt=float(m[~gt].max()),
                       gt_tile_ids=";".join(str(t) for t, (x0, y0, x1, y1) in enumerate(boxes) if gt[y0:y1, x0:x1].any()))
            row["argmax_tile_overlaps_gt"] = str(row["argmax_tile_proxy"]) in row["gt_tile_ids"].split(";")
        per_map.append(row)
        del m
    write_csv(out / "pcb_per_map.csv", per_map)

    # 4) summaries over per-map rows.
    agg = []
    for v in VARIANTS:
        for split, label in (("calibration", 0), ("test", 0), ("test", 1)):
            g = [x for x in per_map if x["variant"] == v and x["split"] == split and x["label"] == label]
            sc = np.array([x["raw_score"] for x in g]); mx = np.array([x["map_max"] for x in g])
            item = dict(variant=v, split=split, label=label, n=len(g), raw_score_median=float(np.median(sc)),
                        map_max_median=float(np.median(mx)), score_over_map_max_median=float(np.median(sc / mx)),
                        spearman_score_vs_map_max=float(np.corrcoef(np.argsort(np.argsort(sc)), np.argsort(np.argsort(mx)))[0, 1]),
                        border_tile_peak_fraction=float(np.mean([_border(x["argmax_tile_proxy"]) for x in g])))
            if label == 1 and "peak_in_gt" in g[0]:
                item.update(peak_in_gt_rate=float(np.mean([x["peak_in_gt"] for x in g])),
                            argmax_tile_overlaps_gt_rate=float(np.mean([x["argmax_tile_overlaps_gt"] for x in g])),
                            median_max_in_gt_minus_outside=float(np.median([x["max_in_gt"] - x["max_outside_gt"] for x in g])))
            agg.append(item)
    write_csv(out / "pcb_map_score_summary.csv", agg)
    # 5) per-anomaly-board flips at the frozen thresholds, with peak tile per variant.
    by = {(x["sample"], x["variant"]): x for x in per_map if x["split"] == "test"}
    flips = []
    for p in (p for p in parents if p.split == "test"):
        item = dict(sample=p.sample, label=p.label)
        for v in VARIANTS:
            x = by[p.sample, v]
            item[f"{v}_norm_score"] = x["normalized_score"]; item[f"{v}_pred"] = int(x["normalized_score"] >= report[v]["reconstructed_threshold"])
            item[f"{v}_peak_tile"] = x["argmax_tile_proxy"]
            if "peak_in_gt" in x:
                item[f"{v}_peak_in_gt"] = x["peak_in_gt"]
        item["peak_tile_same_all_variants"] = len({item[f"{v}_peak_tile"] for v in VARIANTS}) == 1
        flips.append(item)
    write_csv(out / "pcb_per_board_decisions.csv", flips)
    print(json.dumps(dict(linkage=link, thresholds={v: report[v]["threshold_match"] for v in VARIANTS})))


def _border(tile, cols=8, rows=6):
    r, c = divmod(tile, cols)
    return r in (0, rows - 1) or c in (0, cols - 1)


def screw(args):
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    legacy = ROOT / "outputs/legacy-patchcore/screw-full320-test160"
    endpoint = ROOT / "outputs/restoration-objective/screw-full160"
    real = ROOT / "outputs/realistic-degradation/screw-v1/units"
    ref = np.load(endpoint / "bicubic_x4_predictions.npz")
    masks, labels = ref["masks"], ref["labels"]
    order = [r["sample"] for r in csv.DictReader(open(endpoint / "per_image.csv", encoding="utf-8")) if r["variant"] == "bicubic_x4"]
    sources = [("historical_PIL", v, legacy / f"{v}_predictions.npz") for v in VARIANTS]
    sources += [("matlab_endpoint", v, endpoint / f"{v}_predictions.npz") for v in ("bicubic_x4", "swinir_x4", "rrdb_psnr_x4", "rrdb_esrgan_x4")]
    sources += [("realistic_none", v, real / f"none__{v}.npz") for v in ("bicubic_x4", "swinir_x4", "realesrnet_x4plus", "realesrgan_x4plus")]
    real_order = [r["sample"] for r in csv.DictReader(open(real / "none__bicubic_x4.csv", encoding="utf-8")) if r["split"] == "test"]
    legacy_order = [r["sample"] for r in csv.DictReader(open(legacy / "per_image.csv", encoding="utf-8")) if r["variant"] == "clean"]
    rows = []
    for family, v, path in sources:
        z = np.load(path)
        if family == "realistic_none":
            scores, maps, order_ok = z["test_scores"], z["test_maps"], real_order == order
        else:
            scores, maps = z["scores"], z["maps"]
            order_ok = bool(np.array_equal(z["labels"], labels) and np.array_equal(z["masks"], masks)) and (family != "historical_PIL" or legacy_order == order)
        if not order_ok:
            raise ValueError(f"sample order/GT mismatch for {family}/{v}")
        flat = maps.reshape(len(maps), -1)
        peak = flat.argmax(1)
        peak_in_gt = masks.reshape(len(masks), -1)[np.arange(len(masks)), peak]
        an = labels == 1
        rows.append(dict(family=family, variant=v, image_auroc=binary_roc_auc(labels, scores),
                         normal_score_median=float(np.median(scores[~an])), anomaly_score_median=float(np.median(scores[an])),
                         normal_score_iqr=float(np.subtract(*np.quantile(scores[~an], [.75, .25]))),
                         anomaly_minus_normal_median=float(np.median(scores[an]) - np.median(scores[~an])),
                         map_peak_in_gt_rate_anomalies=float(peak_in_gt[an].mean()),
                         spearman_score_vs_map_max=float(np.corrcoef(np.argsort(np.argsort(scores)), np.argsort(np.argsort(flat.max(1))))[0, 1]),
                         auroc_of_map_max=binary_roc_auc(labels, flat.max(1)), sample_order_and_gt_verified=True, source=str(path.relative_to(ROOT))))
    write_csv(out / "screw_family_score_diagnosis.csv", rows)
    print(json.dumps(rows, default=float)[:400])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", choices=("pcb", "screw"))
    ap.add_argument("--output", required=True)
    ap.add_argument("--data-root", type=Path, help="PCB only: VisA root for post-hoc GT (peak-in-defect)")
    a = ap.parse_args()
    (pcb if a.target == "pcb" else screw)(a)


if __name__ == "__main__":
    main()
