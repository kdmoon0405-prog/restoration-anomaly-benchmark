"""Pre-selected bank-domain cases: same RGB, GT and the 2 banks x 2 queries inspection maps at one location.

Case list: analysis/jihyuk_bicubic_bank_return_20261117/selected_visual_cases.csv (selected by CPU review after receipt
from Jihyuk's bicubic-bank per-image table; post-hoc illustration, not an evaluation sample). Maps come from Juhyung's
independent re-run of the base protocol (clean and swinir_restored banks, seed 11), because the received ZIPs contain
no raw maps; bicubic-bank maps are therefore absent and the bicubic-bank per-image AU-PRO values are quoted from the
received table. Query RGB is regenerated (on the producer's device) with the producer function and must match the producer's recorded hash.
Maps are shown after each cell's own normal-calibration median/IQR normalization with one shared colour range.
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
from PIL import Image

HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gal = load_module("defect_zoom_gallery", HERE / "make_defect_zoom_gallery.py")
plt = gal.plt
REASON_KO = {"largest_decrease": "최대 감소", "largest_increase": "최대 증가", "closest_to_zero": "변화가 가장 작음"}


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--runs", type=Path, required=True, help="directory with <category>/seed11 producer runs")
    p.add_argument("--received", type=Path, required=True, help="directory with the two received extension folders")
    p.add_argument("--bank-repo", type=Path, required=True)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--swinir-checkpoint", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--device", default="cuda", help="SwinIR device; must match the producer device for the RGB hash check")
    a = p.parse_args(argv)
    out = a.output
    out.mkdir(parents=True, exist_ok=False)
    (out / "png").mkdir()
    sys.path.insert(0, str(a.bank_repo / "src"))
    from sr_anomaly.fusion import normalize
    runner = load_module("bank_runner", a.bank_repo / "scripts" / "run_bank_domain_study.py")
    import torchvision.transforms as T
    resize, crop = T.Resize(256, interpolation=T.InterpolationMode.BILINEAR), T.CenterCrop(224)
    restorer = runner.SwinIRLightweight(a.bank_repo / "third_party" / "SwinIR", a.swinir_checkpoint.resolve(),
                                        device=a.device, scale=4, tile=56, tile_overlap=0)
    index, cache = [], {}
    for case in rows(a.cases):
        cat, seed, s = case["category"], int(case["seed"]), case["sample"]
        if (cat, seed) not in cache:
            run = a.runs / cat / f"seed{seed}"
            state = json.loads((run / "status.json").read_text(encoding="utf-8"))
            if state["status"] != "COMPLETE":
                raise SystemExit(f"{run} not COMPLETE")
            raw = {b: np.load(run / f"raw_{b}.npz") for b in ("clean", "swinir_restored")}
            mz = np.load(run / "test_masks_for_local_analysis.npz")
            per = {(r["bank_domain"], r["query_domain"], r["sample"]): r for r in rows(run / "per_image.csv")}
            rec = next(d for d in a.received.iterdir() if d.is_dir() and f"_{cat.upper()}_SEED{seed}_" in d.name)
            ext = {(r["query_domain"], r["sample"]): r for r in rows(rec / "extension_per_image.csv")}
            cache[cat, seed] = (run, state, raw, mz, per, ext, rec)
        run, state, raw, mz, per, ext, rec = cache[cat, seed]
        tests = [str(x) for x in mz["samples"]]
        i = tests.index(s)
        mask = mz["masks"][i].astype(bool)
        qd = [str(q) for q in raw["clean"]["query_domains"]]
        maps = {}
        for b in raw:
            for qi, q in enumerate(qd):
                maps[b, q] = normalize(raw[b]["test_maps"][i, qi], state["calibration_by_cell"][f"{b}/{q}"]["pixel"])
        clean, bic, swi, _ = runner._query_variants(a.data_root / s, restorer, resize, crop)
        for q, img in (("bicubic_x4", bic), ("swinir_x4", swi)):
            if runner._rgb_sha(img) != state["query_rgb_sha256"][s][q]:
                raise ValueError(f"{s}: regenerated {q} differs from the producer hash")
        low = clean.resize((56, 56), Image.Resampling.BICUBIC)
        x0, y0, x1, y1 = gal.crop_box(mask)
        sl = (slice(y0, y1), slice(x0, x1))
        up = lambda arr: gal.zoom_to(arr, gal.DISPLAY)  # noqa: E731
        gtc = up(mask[sl])
        vmin = float(min(m[sl].min() for m in maps.values()))
        vmax = float(max(m[sl].max() for m in maps.values()))
        fig, ax = plt.subplots(2, 5, figsize=(19.5, 9.6), gridspec_kw={"hspace": 0.32, "wspace": 0.05})
        lr_disp = np.kron(np.asarray(low), np.ones((4, 4, 1), np.uint8))
        gal.panel(ax[0, 0], up(np.asarray(clean)[sl]), "원본 (224 기준)", contour=gtc)
        gal.panel(ax[0, 1], up(lr_disp[sl]), "열화 입력 56 px (최근접 표시)", contour=gtc)
        gal.panel(ax[0, 2], up(np.asarray(bic)[sl]), "Bicubic ×4 검사 입력", contour=gtc)
        gal.panel(ax[0, 3], up(np.asarray(swi)[sl]), "SwinIR ×4 검사 입력", contour=gtc)
        gal.panel(ax[0, 4], gtc.astype(float), "GT 결함 영역", cmap="gray", vmin=0, vmax=1)
        bank_ko = {"clean": "원본 bank", "swinir_restored": "SwinIR 복원 bank"}
        q_ko = {"bicubic_x4": "Bicubic 입력", "swinir_x4": "SwinIR 입력"}
        for k, (b, q) in enumerate([("clean", "bicubic_x4"), ("clean", "swinir_x4"), ("swinir_restored", "bicubic_x4"), ("swinir_restored", "swinir_x4")]):
            au = float(per[b, q, s]["per_image_aupro"])
            gal.panel(ax[1, k], up(maps[b, q][sl]), f"{bank_ko[b]} · {q_ko[q]}\n영상별 AU-PRO {au:.3f}", contour=gtc, cmap="viridis", vmin=vmin, vmax=vmax)
        eb, es = float(ext["bicubic_x4", s]["per_image_aupro"]), float(ext["swinir_x4", s]["per_image_aupro"])
        ax[1, 4].axis("off")
        ax[1, 4].text(0, 0.95, "Bicubic 복원 bank (지혁 수신값)\n지도는 수신 자료에 없음\n\n"
                      f"Bicubic 입력: {eb:.3f}\nSwinIR 입력: {es:.3f}\nSwinIR - Bicubic: {es - eb:+.3f}",
                      va="top", fontsize=13, transform=ax[1, 4].transAxes)
        name = f"{cat}_seed{seed}_{case['selection_reason']}_{Path(s).parent.name}_{Path(s).stem}.png"
        fig.suptitle(f"{cat} · {s.split('/', 2)[-1]} · {REASON_KO.get(case['selection_reason'], case['selection_reason'])} "
                     f"(Bicubic bank에서 SwinIR - Bicubic 입력의 영상별 AU-PRO, 수신 후 사후 선정)", fontsize=14, x=0.01, ha="left")
        fig.text(0.01, 0.01, f"crop x{x0}-{x1} y{y0}-{y1} of 224 · 지도: 주형 재실행(seed {seed}) 각 cell 정상 보정 median/IQR 정규화, 공통 색 범위 {vmin:.1f}–{vmax:.1f} · "
                 "검사 입력 RGB는 producer 해시와 일치 확인 · 설명용 예시이며 성능 추정이 아니다", fontsize=10, color="#555")
        fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.05)
        fig.savefig(out / "png" / name, dpi=110)
        plt.close(fig)
        (out / "arrays").mkdir(exist_ok=True)
        np.savez_compressed(out / "arrays" / name.replace(".png", ".npz"), original=np.asarray(clean)[sl], lr56=lr_disp[sl],
                            bicubic_x4=np.asarray(bic)[sl], swinir_x4=np.asarray(swi)[sl], gt=mask[sl],
                            **{f"map__{b}__{q}": maps[b, q][sl].astype(np.float32) for (b, q) in maps},
                            vmin=np.float32(vmin), vmax=np.float32(vmax))
        index.append(dict(category=cat, seed=seed, sample=s, selection_reason=case["selection_reason"], png=f"png/{name}",
                          crop=f"{x0},{y0},{x1},{y1}", map_vmin=round(vmin, 4), map_vmax=round(vmax, 4),
                          **{f"aupro_{b}_bank_{q}": round(float(per[b, q, s]["per_image_aupro"]), 6) for b in raw for q in qd},
                          aupro_bicubic_bank_bicubic_x4_received=eb, aupro_bicubic_bank_swinir_x4_received=es,
                          query_bicubic_sha256=state["query_rgb_sha256"][s]["bicubic_x4"], query_swinir_sha256=state["query_rgb_sha256"][s]["swinir_x4"],
                          maps_source_run=state["run_id"], received_folder=rec.name))
    with open(out / "index.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index[0]))
        w.writeheader()
        w.writerows(index)
    manifest = dict(kind="selected_bank_cases", cases_csv_sha256=sha256(a.cases.read_bytes()).hexdigest(),
                    files={**{r["png"]: sha256((out / r["png"]).read_bytes()).hexdigest() for r in index},
                           **{f"arrays/{f.name}": sha256(f.read_bytes()).hexdigest() for f in sorted((out / "arrays").glob("*.npz"))}},
                    note="maps from Juhyung's re-run (clean/swinir_restored banks); bicubic-bank values quoted from Jihyuk's received table")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(cases=len(index)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
