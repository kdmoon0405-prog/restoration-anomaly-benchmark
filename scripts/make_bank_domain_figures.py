"""Same query RGB, two normal banks: clean-bank vs SwinIR-restored-bank PatchCore maps at the same defect location.

Reads one completed bank-domain producer run (status.json, raw_clean.npz, raw_swinir_restored.npz,
test_masks_for_local_analysis.npz, per_image.csv). Maps are shown after each cell's own normal-calibration
normalization (median/IQR), so the two banks share one colour range. The query RGB (Bicubic x4 or SwinIR x4 of the
56 px input) is regenerated (on the producer's device) with the producer's own function and accepted only if its SHA-256 equals the hash the
producer recorded. Case selection uses the fixed taxonomy on delta = (restored bank - clean bank) per-image AU-PRO for
the same query; it is a post-hoc illustration, not a performance estimate. GT is used only after inference.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gal = load_module("defect_zoom_gallery", HERE / "make_defect_zoom_gallery.py")
plt = gal.plt
BANK_LABEL = {"clean": "정상 원본 bank", "swinir_restored": "SwinIR 복원 정상 bank"}
QUERY_LABEL = {"bicubic_x4": "Bicubic ×4", "swinir_x4": "SwinIR ×4"}


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True, help="producer run dir <run-id>/<category>/seed<N>")
    p.add_argument("--bank-repo", type=Path, required=True, help="bank-domain checkout (runner, SwinIR, src)")
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--swinir-checkpoint", type=Path, required=True)
    p.add_argument("--queries", nargs="+", default=["swinir_x4", "bicubic_x4"])
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--device", default="cuda", help="SwinIR device; must match the producer device for the RGB hash check")
    a = p.parse_args(argv)
    out = a.output
    out.mkdir(parents=True, exist_ok=False)
    (out / "png").mkdir()
    state = json.loads((a.run / "status.json").read_text(encoding="utf-8"))
    if state.get("status") != "COMPLETE":
        raise SystemExit(f"run is {state.get('status')}, not COMPLETE")
    category, seed = state["category"], int(state["seed"])
    tests = list(state["test_samples"])
    raw = {b: np.load(a.run / f"raw_{b}.npz") for b in ("clean", "swinir_restored")}
    for b in raw:
        if [str(s) for s in raw[b]["test_samples"]] != tests:
            raise ValueError("test order differs")
    qidx = {str(q): i for i, q in enumerate(raw["clean"]["query_domains"])}
    mz = np.load(a.run / "test_masks_for_local_analysis.npz")
    masks = mz["masks"].astype(bool)
    prod = rows(a.run / "per_image.csv")
    sys.path.insert(0, str(a.bank_repo / "src"))
    from sr_anomaly.fusion import normalize
    runner = load_module("bank_runner", a.bank_repo / "scripts" / "run_bank_domain_study.py")
    import torchvision.transforms as T
    resize, crop = T.Resize(256, interpolation=T.InterpolationMode.BILINEAR), T.CenterCrop(224)
    restorer = runner.SwinIRLightweight(a.bank_repo / "third_party" / "SwinIR", a.swinir_checkpoint.resolve(),
                                        device=a.device, scale=4, tile=56, tile_overlap=0)
    index, counts = [], {}
    for query in a.queries:
        qi = qidx[query]
        norm = {b: normalize(raw[b]["test_maps"][:, qi], state["calibration_by_cell"][f"{b}/{query}"]["pixel"]) for b in raw}
        per = {b: {r["sample"]: r for r in prod if r["bank_domain"] == b and r["query_domain"] == query} for b in raw}
        items = []
        for i, s in enumerate(tests):
            if not masks[i].any():
                continue
            gap = {b: float(norm[b][i][masks[i]].mean() - norm[b][i][~masks[i]].mean()) for b in raw}
            au = {b: float(per[b][s]["per_image_aupro"]) for b in raw}
            d, g = au["swinir_restored"] - au["clean"], gap["swinir_restored"] - gap["clean"]
            items.append(dict(i=i, sample=s, defect_type=per["clean"][s]["defect_type"], delta_aupro=d, delta_gap=g,
                              taxonomy=gal.classify(d, g), aupro_clean_bank=au["clean"], aupro_restored_bank=au["swinir_restored"]))
        counts[query] = {c: sum(x["taxonomy"] == c for x in items) for c in ("improvement", "suppression", "geometry_candidate")}
        counts[query]["anomalies"] = len(items)
        chosen = []
        for cls in ("improvement", "suppression", "geometry_candidate"):
            pool = [x for x in items if x["taxonomy"] == cls]
            if pool:
                chosen.append(dict(max(pool, key=lambda x: x["delta_aupro"]) if cls == "improvement" else
                                   min(pool, key=lambda x: x["delta_aupro"]), case_class=cls))
            else:
                index.append(dict(category=category, seed=seed, query=query, case_class=cls, sample="", note="no case of this class"))
        chosen.append(dict(min(items, key=lambda x: abs(x["delta_aupro"])), case_class="small_change"))
        for c in chosen:
            i, s = c["i"], c["sample"]
            clean, bic, swi, _ = runner._query_variants(a.data_root / s, restorer, resize, crop)
            qimg = {"bicubic_x4": bic, "swinir_x4": swi}[query]
            if runner._rgb_sha(qimg) != state["query_rgb_sha256"][s][query]:
                raise ValueError(f"{s}: regenerated {query} RGB differs from the producer hash")
            x0, y0, x1, y1 = gal.crop_box(masks[i])
            sl = (slice(y0, y1), slice(x0, x1))
            up = lambda arr: gal.zoom_to(arr, gal.DISPLAY)  # noqa: E731
            gtc = up(masks[i][sl])
            vmin = float(min(norm[b][i][sl].min() for b in raw))
            vmax = float(max(norm[b][i][sl].max() for b in raw))
            fig, ax = plt.subplots(1, 5, figsize=(19.5, 5.0), gridspec_kw={"wspace": 0.05})
            gal.panel(ax[0], up(np.asarray(clean)[sl]), "원본 (224 기준)", contour=gtc)
            gal.panel(ax[1], up(np.asarray(qimg)[sl]), f"검사 입력: {QUERY_LABEL[query]} (두 bank 공통)", contour=gtc)
            gal.panel(ax[2], gtc.astype(float), "GT 결함 영역", cmap="gray", vmin=0, vmax=1)
            for k, b in enumerate(("clean", "swinir_restored")):
                gal.panel(ax[3 + k], up(norm[b][i][sl]), f"{BANK_LABEL[b]}\n영상별 AU-PRO {c['aupro_clean_bank' if b == 'clean' else 'aupro_restored_bank']:.3f}",
                          contour=gtc, cmap="viridis", vmin=vmin, vmax=vmax)
            name = f"{category}_seed{seed}_{query}_{c['case_class']}.png"
            fig.suptitle(f"{category} · {s.split('/', 2)[-1]} · 분류 {c['case_class']} · ΔAU-PRO(복원 bank - 원본 bank) {c['delta_aupro']:+.3f} · Δgap {c['delta_gap']:+.2f}",
                         fontsize=13, x=0.01, ha="left")
            fig.text(0.01, 0.01, f"crop x{x0}-{x1} y{y0}-{y1} of 224 · 지도는 각 cell의 정상 보정 median/IQR로 정규화, 색 범위 {vmin:.1f}–{vmax:.1f} 공통 · "
                     f"seed {seed} · 사후 선택 예시이며 성능 추정이 아니다", fontsize=10, color="#555")
            fig.subplots_adjust(left=0.01, right=0.99, top=0.8, bottom=0.08)
            fig.savefig(out / "png" / name, dpi=110)
            plt.close(fig)
            index.append(dict(category=category, seed=seed, query=query, case_class=c["case_class"], sample=s,
                              defect_type=c["defect_type"], delta_aupro=round(c["delta_aupro"], 6), delta_gap=round(c["delta_gap"], 6),
                              aupro_clean_bank=round(c["aupro_clean_bank"], 6), aupro_restored_bank=round(c["aupro_restored_bank"], 6),
                              crop=f"{x0},{y0},{x1},{y1}", png=f"png/{name}", query_rgb_sha256=state["query_rgb_sha256"][s][query]))
    with open(out / "index.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in index for k in r)))
        w.writeheader()
        w.writerows(index)
    manifest = dict(kind="bank_domain_same_query_figures", run_id=state["run_id"], category=category, seed=seed,
                    run_status_sha256=sha256((a.run / "status.json").read_bytes()).hexdigest(),
                    producer_source_commit=state.get("source_commit"), taxonomy_counts=counts,
                    selection_rule="per query: improvement = max delta; suppression / geometry = min delta; small_change = min |delta|; "
                                   "delta = swinir_restored bank - clean bank per-image AU-PRO; gap on cell-normalized maps",
                    files={r["png"]: sha256((out / r["png"]).read_bytes()).hexdigest() for r in index if r.get("png")})
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
