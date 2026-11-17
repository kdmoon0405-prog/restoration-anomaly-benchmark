"""Same-location zoom comparison of original / degraded input / Bicubic x4 / SwinIR x4 with GT and inspection maps.

Uses the stored realistic-degradation v1 runs (outputs/realistic-degradation/<cat>-v1): restored RGB PNGs, unit npz maps
and per-image CSVs. Nothing is re-run except (a) the degraded LR input, regenerated deterministically and checked by
re-making the stored Bicubic output byte-for-byte, and (b) clean-input maps for the selected samples only, predicted on
CPU with the stored v1 bank (load-only). Case selection uses the existing taxonomy on SwinIR - Bicubic per-image AU-PRO
and ROI-background gap; it is a post-hoc selection for illustration, not a performance estimate.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import html
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy import ndimage

CLASSES = ("improvement", "suppression", "geometry_candidate", "small_change")
CROP = 64          # canonical 224-frame pixels
ZOOM = 4           # display magnification (nearest)


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def digest(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def classify(d_aupro: float, d_gap: float) -> str:
    """Existing fixed taxonomy (docs/EXPERIMENT_PROTOCOL_V0.2): regression if delta per-image AU-PRO < 0; suppression if
    also delta ROI-background gap < 0, otherwise geometry_candidate; improvement/tie otherwise."""
    if d_aupro < 0:
        return "suppression" if d_gap < 0 else "geometry_candidate"
    return "improvement"


def select_cases(run: Path, condition: str) -> tuple[list[dict], dict]:
    """Fixed rule per class: improvement = largest delta; suppression / geometry_candidate = most negative delta;
    small_change = smallest |delta| over all anomalies. delta = SwinIR - Bicubic per-image AU-PRO (same condition)."""
    bic = {r["sample"]: r for r in rows(run / f"units/{condition}__bicubic_x4.csv") if r["split"] == "test" and r["label"] == "1"}
    swi = {r["sample"]: r for r in rows(run / f"units/{condition}__swinir_x4.csv") if r["split"] == "test" and r["label"] == "1"}
    items = []
    for s in bic:
        d = float(swi[s]["per_image_aupro"]) - float(bic[s]["per_image_aupro"])
        g = float(swi[s]["roi_bg_gap"]) - float(bic[s]["roi_bg_gap"])
        items.append(dict(sample=s, defect_type=bic[s]["defect_type"], delta_aupro=d, delta_gap=g, taxonomy=classify(d, g),
                          aupro_bicubic=float(bic[s]["per_image_aupro"]), aupro_swinir=float(swi[s]["per_image_aupro"]),
                          defect_area_ratio=float(bic[s]["defect_area_ratio"])))
    counts = {c: sum(i["taxonomy"] == c for i in items) for c in ("improvement", "suppression", "geometry_candidate")}
    chosen = []
    for cls in CLASSES:
        if cls == "small_change":
            pool = items
            pick = min(pool, key=lambda i: (abs(i["delta_aupro"]), i["sample"])) if pool else None
        else:
            pool = [i for i in items if i["taxonomy"] == cls]
            if not pool:
                pick = None
            elif cls == "improvement":
                pick = max(pool, key=lambda i: (i["delta_aupro"], i["sample"]))
            else:
                pick = min(pool, key=lambda i: (i["delta_aupro"], i["sample"]))
        chosen.append(dict(selection_class=cls, **(pick or {}), available=pick is not None))
    return chosen, dict(anomalies=len(items), **counts)


def gt_mask(data_root: Path, sample: str, resize_mask, crop, canonical) -> np.ndarray:
    parts = sample.split("/")
    mask_path = data_root / parts[0] / "ground_truth" / parts[2] / (Path(parts[3]).stem + "_mask.png")
    with Image.open(mask_path) as m:
        return np.asarray(canonical(m.convert("L"), resize_mask, crop)) > 0


def crop_box(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    cy, cx = (int(round(ys.mean())), int(round(xs.mean()))) if ys.size else (112, 112)
    x0 = min(max(cx - CROP // 2, 0), 224 - CROP)
    y0 = min(max(cy - CROP // 2, 0), 224 - CROP)
    return x0, y0, x0 + CROP, y0 + CROP


def panel(ax, img, title, contour=None, cmap=None, vmin=None, vmax=None):
    ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    if contour is not None and contour.any():
        ax.contour(contour.astype(float), levels=[0.5], colors="#ff3030", linewidths=1.6)
    ax.set_title(title, fontsize=11, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, required=True, help="GPU checkout (outputs/, data/, third_party/, scripts/)")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--conditions", nargs="+", default=["none", "blur_s1.6", "noise_s15"])
    p.add_argument("--categories", nargs="+", default=["hazelnut", "screw"])
    a = p.parse_args(argv)
    repo = a.repo.resolve()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "png").mkdir()
    sys.path.insert(0, str(repo / "src"))
    sys.path.insert(0, str(repo / "scripts"))
    from sr_anomaly import realistic_degradation as rd
    from sr_anomaly.real_models import matlab_bicubic_resize
    import run_realistic_degradation as rrd
    from run_legacy_patchcore import _canonical, _faiss_staging, _official_imports
    torch, transforms, InterpolationMode, backbones, common, patchcore, sampler, mvtec = _official_imports()
    torch.set_num_threads(4)
    resize_image = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    resize_mask = transforms.Resize(256, interpolation=InterpolationMode.NEAREST)
    crop = transforms.CenterCrop(224)
    to_tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])
    basicsr = repo / "third_party" / "BasicSR"
    data = repo / "data" / "external" / "MVTecAD"
    index, manifest = [], dict(kind="post-hoc illustration of stored predictions", selection_rule=select_cases.__doc__,
                               taxonomy_rule=classify.__doc__, crop_px=CROP, zoom=ZOOM, canonical="resize 256 bilinear + center crop 224",
                               sources={}, clean_map="CPU predict with the stored v1 bank (load-only), selected samples only",
                               class_counts={}, lr_check={})
    for cat in a.categories:
        run = repo / f"outputs/realistic-degradation/{cat}-v1"
        selected = {cond: select_cases(run, cond) for cond in a.conditions}
        samples = sorted({c["sample"] for cond in selected for c in selected[cond][0] if c["available"]})
        # clean maps for the selected samples (stored v1 bank, CPU, load-only)
        model, meta = rrd._bank(run, torch.device("cpu"), torch, common, patchcore, sampler, backbones, None, to_tensor)
        clean_maps = {}
        for s in samples:
            with Image.open(data / s) as src:
                img = _canonical(src.convert("RGB"), resize_image, crop)
            scores, maps = model.predict(to_tensor(img).unsqueeze(0))
            clean_maps[s] = np.asarray(maps[0], np.float32)
        np.savez_compressed(out / f"clean_maps_{cat}.npz", samples=np.asarray(samples), maps=np.stack([clean_maps[s] for s in samples]))
        manifest["sources"][cat] = dict(run=f"outputs/realistic-degradation/{cat}-v1", bank_sha256=meta["artifact_sha256"])
        for cond in a.conditions:
            chosen, counts = selected[cond]
            manifest["class_counts"][f"{cat}/{cond}"] = counts
            npz = {r: np.load(run / f"units/{cond}__{r}.npz") for r in ("bicubic_x4", "swinir_x4")}
            order = [r["sample"] for r in rows(run / f"units/{cond}__bicubic_x4.csv") if r["split"] == "test"]
            for c in chosen:
                rec = dict(category=cat, condition=cond, selection_class=c["selection_class"], available=c["available"])
                if not c["available"]:
                    index.append(rec)
                    continue
                s = c["sample"]
                with Image.open(data / s) as src:
                    original_size = src.size
                    clean = _canonical(src.convert("RGB"), resize_image, crop)
                lr = np.asarray(matlab_bicubic_resize(clean, 0.25, basicsr))
                degraded = rd.degrade(lr, cond, rd.sample_seed(cat, s, cond))
                stored = {r: run / f"images/{cond}/{r}/{s.replace('/', '__')}.png" for r in ("bicubic_x4", "swinir_x4")}
                remade = np.asarray(matlab_bicubic_resize(Image.fromarray(degraded, "RGB"), 4.0, basicsr))
                lr_ok = bool(np.array_equal(remade, np.asarray(Image.open(stored["bicubic_x4"]).convert("RGB"))))
                manifest["lr_check"][f"{cat}/{cond}/{s}"] = lr_ok
                bic = np.asarray(Image.open(stored["bicubic_x4"]).convert("RGB"))
                swi = np.asarray(Image.open(stored["swinir_x4"]).convert("RGB"))
                gt = gt_mask(data, s, resize_mask, crop, _canonical)
                i = order.index(s)
                maps = {"clean": clean_maps[s], "bicubic_x4": npz["bicubic_x4"]["test_maps"][i], "swinir_x4": npz["swinir_x4"]["test_maps"][i]}
                x0, y0, x1, y1 = crop_box(gt)
                sl = (slice(y0, y1), slice(x0, x1))
                vmax = float(max(m[sl].max() for m in maps.values()))
                vmin = float(min(m[sl].min() for m in maps.values()))
                up = lambda arr: np.kron(arr, np.ones((ZOOM, ZOOM) + ((1,) if arr.ndim == 3 else ()), dtype=arr.dtype))  # noqa: E731
                lr_disp = np.kron(degraded, np.ones((4, 4, 1), np.uint8))  # 56 -> 224 nearest, same frame
                fig, axes = plt.subplots(2, 4, figsize=(15.5, 8.6))
                panel(axes[0, 0], up(np.asarray(clean)[sl]), "원본 (canonical 224)")
                panel(axes[0, 1], up(lr_disp[sl]), f"열화 입력 56px ({cond}), 최근접 표시")
                panel(axes[0, 2], up(bic[sl]), "Bicubic ×4")
                panel(axes[0, 3], up(swi[sl]), "SwinIR ×4")
                gtc = np.kron(gt[sl], np.ones((ZOOM, ZOOM), bool))
                panel(axes[1, 0], up(np.asarray(clean)[sl]), "GT (빨간 윤곽)", contour=gtc)
                for k, (name, label) in enumerate((("clean", "검사 지도: 원본 입력"), ("bicubic_x4", "검사 지도: Bicubic"),
                                                    ("swinir_x4", "검사 지도: SwinIR"))):
                    panel(axes[1, 1 + k], np.kron(maps[name][sl], np.ones((ZOOM, ZOOM))), label, contour=gtc, cmap="viridis",
                          vmin=vmin, vmax=vmax)
                fig.suptitle(f"{cat} · {s} · {cond} · {c['selection_class']} (사후 선정) · per-image AU-PRO Bicubic "
                             f"{c['aupro_bicubic']:.3f} → SwinIR {c['aupro_swinir']:.3f} (Δ {c['delta_aupro']:+.3f})", fontsize=12, x=0.01, ha="left")
                fig.text(0.01, 0.005, f"crop x{x0}-{x1} y{y0}-{y1} of 224 (원본 {original_size[0]}×{original_size[1]}에서 resize 256 + center crop), "
                         f"표시 {ZOOM}배 최근접 · 지도 색 범위 {vmin:.2f}–{vmax:.2f} (세 지도 공통, PatchCore 거리) · v1 bank seed 11",
                         fontsize=9, color="#555")
                fig.tight_layout(rect=(0, 0.02, 1, 0.95))
                name = f"{cat}__{cond}__{c['selection_class']}__{Path(s).parent.name}_{Path(s).stem}.png"
                fig.savefig(out / "png" / name, dpi=150)
                plt.close(fig)
                rec.update(sample=s, defect_type=c["defect_type"], png=f"png/{name}", crop_x0=x0, crop_y0=y0, crop_x1=x1, crop_y1=y1,
                           crop_frame="canonical_224", original_size=f"{original_size[0]}x{original_size[1]}", display_zoom=ZOOM,
                           degraded_lr_size="56x56", map_range_min=vmin, map_range_max=vmax, lr_regenerated_matches_stored_bicubic=lr_ok,
                           aupro_bicubic=c["aupro_bicubic"], aupro_swinir=c["aupro_swinir"], delta_aupro=c["delta_aupro"],
                           delta_roi_bg_gap=c["delta_gap"], taxonomy=c["taxonomy"], defect_area_ratio=c["defect_area_ratio"],
                           gt_area_in_crop_px=int(gt[sl].sum()), stored_bicubic_sha256=digest(stored["bicubic_x4"]),
                           stored_swinir_sha256=digest(stored["swinir_x4"]), unit_npz_bicubic_sha256=digest(run / f"units/{cond}__bicubic_x4.npz"),
                           unit_npz_swinir_sha256=digest(run / f"units/{cond}__swinir_x4.npz"))
                index.append(rec)
    fields = list(dict.fromkeys(k for r in index for k in r))
    with open(out / "index.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(index)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    cards = []
    for r in index:
        if not r["available"]:
            cards.append(f'<section><h3>{html.escape(r["category"])} · {html.escape(r["condition"])} · {html.escape(r["selection_class"])}</h3>'
                         f'<p class="muted">이 조건에는 해당 분류의 사례가 없다.</p></section>')
            continue
        cards.append(f'<section><h3>{html.escape(r["category"])} · {html.escape(r["condition"])} · {html.escape(r["selection_class"])} · '
                     f'{html.escape(r["sample"])}</h3><p class="muted">per-image AU-PRO Bicubic {r["aupro_bicubic"]:.3f} → SwinIR '
                     f'{r["aupro_swinir"]:.3f} (Δ {r["delta_aupro"]:+.3f}), ROI–배경 차 Δ {r["delta_roi_bg_gap"]:+.3f} · crop x{r["crop_x0"]}–{r["crop_x1"]} '
                     f'y{r["crop_y0"]}–{r["crop_y1"]} · 열화 입력 재생성 확인 {"일치" if r["lr_regenerated_matches_stored_bicubic"] else "불일치"}</p>'
                     f'<a href="{r["png"]}"><img src="{r["png"]}" alt="{html.escape(r["sample"])}" loading="lazy"></a></section>')
    counts = "".join(f"<li>{html.escape(k)}: 이상 {v['anomalies']}장 — 개선/동일 {v['improvement']}, 억제 {v['suppression']}, "
                     f"형상 변화 후보 {v['geometry_candidate']}</li>" for k, v in manifest["class_counts"].items())
    (out / "gallery.html").write_text(f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Defect zoom gallery</title><style>
:root{{--bg:#f6f7f9;--fg:#17202b;--card:#fff;--muted:#526174}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14181d;--fg:#e6e9ed;--card:#1d232a;--muted:#9aa6b3}}}}
body{{font:15px system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:16px;max-width:1500px;overflow-wrap:anywhere}}
section{{background:var(--card);padding:12px;margin:14px 0}}img{{max-width:100%;display:block}}.muted{{color:var(--muted);font-size:13px}}
.note{{background:#fff4d7;color:#3b2a00;padding:12px;border-left:4px solid #a57910}}h3{{font-size:16px;margin:0 0 6px}}
</style></head><body><h1>같은 결함 위치의 원본 · 열화 입력 · Bicubic · SwinIR 확대 비교</h1>
<p class="note">저장된 realistic-degradation v1 결과(Hazelnut, Screw; bank/split seed 11)에서 만든 사후 그림이다. 사례는 기존 분류 규칙
(SwinIR − Bicubic 영상별 AU-PRO와 ROI–배경 차의 부호)으로 분류마다 1장을 고정 규칙으로 골랐다. 선정 사례로 전체 성능을 추정하지 않는다.
검사 지도는 같은 사례 안에서 세 지도에 같은 색 범위를 쓴다. 원본 입력의 지도는 같은 v1 bank로 선정 사례만 CPU에서 계산했다.</p>
<h2>분류별 사례 수 (이상 영상 전체)</h2><ul>{counts}</ul>{''.join(cards)}
<p class="muted">index.csv: 사례별 image ID, crop 좌표, 크기, 배율, 열화 조건, 저장 파일 SHA-256 · manifest.json: 선정 규칙과 출처</p></body></html>""",
                                      encoding="utf-8")
    print(json.dumps(dict(cases=sum(r["available"] for r in index), missing=[(r["category"], r["condition"], r["selection_class"]) for r in index if not r["available"]],
                          lr_all_match=all(manifest["lr_check"].values()), counts=manifest["class_counts"]), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
