"""Zoomed views of the real phone photos at the simulated-object position (development session 2026-11-15).

Row A: real capture conditions at full camera resolution (no processing). Row B: what the inspection sees at working
resolution, and the artificial x4 round trip (x0.25 then Bicubic / SwinIR x4) used by condition C1, with the
golden-reference difference maps. The object position is the post-hoc annotation used only for location checks; it is
not a defect ground truth. Photos and outputs are private.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import phone_capture as pc  # noqa: E402
from sr_anomaly import phone_station as ps  # noqa: E402

FULL_HALF = 240     # full-resolution crop half size (px of the 4000x3000 photo)
WORK_HALF = 60      # working-resolution crop half size (px of the 1024-long-side image)


def project(matrix, xy):
    v = np.asarray(matrix, dtype=np.float64) @ np.array([xy[0], xy[1], 1.0])
    return v[0] / v[2], v[1] / v[2]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--photos", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True, help="station run directory (manifest.json with recipe and plan)")
    p.add_argument("--assets-root", type=Path, required=True, help="checkout with third_party/BasicSR, SwinIR and checkpoints/swinir")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--device", default="cpu")
    a = p.parse_args(argv)
    out = a.output
    out.mkdir(parents=True, exist_ok=False)
    m = json.loads((a.run / "manifest.json").read_text(encoding="utf-8"))
    recipe, plan = m["recipe"], m["plan"]
    cyc = {c["cycle_id"]: c for c in plan["cycles"]}
    anchor_full, _ = pc.decode(a.photos / recipe["anchor"])
    anchor, anchor_scale = pc.working(anchor_full)
    box = pc.roi_box(anchor.shape, recipe["roi"])
    ay = pc.luma(anchor)
    target = plan["annotation_xy"]  # anchor working px, post-hoc annotation

    def load(name):
        full, _ = pc.decode(a.photos / name)
        work, scale = pc.working(full)
        al = pc.align(ay, pc.luma(work)) if name != recipe["anchor"] else dict(success=True, matrix=np.eye(3).tolist())
        if not al["success"]:
            raise RuntimeError(f"{name}: not registered")
        x, y = project(al["matrix"], target)              # anchor working -> this photo's working coords
        return dict(full=full, work=work, scale=scale, matrix=al["matrix"], wx=x, wy=y, fx=x / scale, fy=y / scale)

    row_a = [("정상, L0 (normal-3)", cyc["normal-3"]["first"]), ("모사 이물, L0 (foreign-1)", cyc["foreign-1"]["first"]),
             ("모사 이물, L1 (foreign-1 대체)", cyc["foreign-1"]["alternate"]), ("저조도 첫 입력 (lowlight-3)", cyc["lowlight-3"]["first"]),
             ("저조도의 대체 L1 (lowlight-3)", cyc["lowlight-3"]["alternate"]), ("초점 흐림 첫 입력 (blur-1)", cyc["blur-1"]["first"])]
    loaded = {f: load(f) for _, f in row_a}
    index = []
    fig, axes = plt.subplots(2, 6, figsize=(24, 9.2), gridspec_kw={"hspace": 0.32, "wspace": 0.05})
    for k, (title, f) in enumerate(row_a):
        d = loaded[f]
        x0, y0 = int(round(d["fx"])) - FULL_HALF, int(round(d["fy"])) - FULL_HALF
        crop = d["full"][max(y0, 0):y0 + 2 * FULL_HALF, max(x0, 0):x0 + 2 * FULL_HALF]
        axes[0, k].imshow(crop)
        axes[0, k].set_title(title, fontsize=13, loc="left")
        axes[0, k].axis("off")
        index.append(dict(row="A_real_capture", panel=title, file=f, crop_frame="full_resolution",
                          x0=max(x0, 0), y0=max(y0, 0), size=2 * FULL_HALF, processing="none"))

    # Row B: working resolution and the artificial x4 round trip on the F0 (L0) photo, with difference maps
    sys.path.insert(0, str(a.assets_root / "src"))
    from sr_anomaly.real_models import SwinIRLightweight, matlab_bicubic_resize
    basicsr = a.assets_root / "third_party" / "BasicSR"
    swinir = SwinIRLightweight(a.assets_root / "third_party/SwinIR", a.assets_root / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth",
                               device=a.device, scale=4, tile=64, tile_overlap=0).restore
    down = lambda img: matlab_bicubic_resize(img, 0.25, basicsr)  # noqa: E731
    variants = {"original": lambda rgb: rgb,
                "bicubic_x4": lambda rgb: ps.x4_roundtrip(rgb, down, lambda lr: matlab_bicubic_resize(lr, 4.0, basicsr)),
                "swinir_x4": lambda rgb: ps.x4_roundtrip(rgb, down, swinir)}
    ref_l0, cal_l0, f0 = (load(plan["references"]["L0"]), load(plan["calibration"]["L0"]), loaded[cyc["foreign-1"]["first"]])
    tx, ty = int(round(target[0])), int(round(target[1]))
    sl = (slice(ty - WORK_HALF, ty + WORK_HALF), slice(tx - WORK_HALF, tx + WORK_HALF))
    results = {}
    for name, fn in variants.items():
        warped = {key: pc.warp_to_reference(fn(d["work"]), d["matrix"], anchor.shape) for key, d in
                  (("ref", ref_l0), ("cal", cal_l0), ("test", f0))}
        calib = ps.gr_calibrate(ps.difference_map(warped["cal"][0], warped["ref"][0]),
                                ps.inspection_mask(anchor.shape, box, warped["ref"][1], warped["cal"][1]))
        diff = ps.difference_map(warped["test"][0], warped["ref"][0])
        res = ps.gr_inspect(diff, ps.inspection_mask(anchor.shape, box, warped["ref"][1], warped["test"][1]), calib)
        results[name] = dict(rgb=warped["test"][0], diff=diff, tau=calib["tau"], score=res["score"], verdict=res["verdict"])
    lr = np.asarray(down(Image.fromarray(f0["work"])))
    lr_up = np.kron(lr, np.ones((4, 4, 1), np.uint8))
    lr_warp, _ = pc.warp_to_reference(lr_up[:f0["work"].shape[0], :f0["work"].shape[1]], f0["matrix"], anchor.shape)
    panels_b = [("검사 해상도 원본 (긴 변 1024)", results["original"]["rgb"][sl], None),
                ("×0.25 축소 입력 (최근접 표시)", lr_warp[sl], None),
                ("Bicubic ×4", results["bicubic_x4"]["rgb"][sl], None), ("SwinIR ×4", results["swinir_x4"]["rgb"][sl], None)]
    vmax = max(r["diff"][sl].max() for r in results.values())
    for k, (title, img, _) in enumerate(panels_b):
        axes[1, k].imshow(img, interpolation="nearest")
        axes[1, k].set_title(title, fontsize=13, loc="left")
        axes[1, k].axis("off")
    for k, name in enumerate(("original", "swinir_x4")):
        r = results[name]
        axes[1, 4 + k].imshow(r["diff"][sl], cmap="viridis", vmin=0, vmax=vmax, interpolation="nearest")
        label = {"original": "원본", "swinir_x4": "SwinIR ×4"}[name]
        axes[1, 4 + k].set_title(f"차이 지도 ({label}): {r['score']} px → {r['verdict']}", fontsize=13, loc="left")
        axes[1, 4 + k].axis("off")
    fig.text(0.01, 0.955, "A. 실제 촬영 조건 (원본 해상도 4000×3000에서 480×480 확대, 처리 없음) — 같은 위치는 사후 위치 표시를 정렬로 옮긴 것이며 GT가 아니다",
             fontsize=14, weight="bold")
    fig.text(0.01, 0.475, "B. 모사 이물 L0 사진의 검사 해상도와 인위적 ×4 왕복 (C1) — 실제 저조도·흐림의 복원이 아니다. 차이 지도 색 범위는 세 경로 공통",
             fontsize=14, weight="bold")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.91, bottom=0.02)
    fig.savefig(out / "phone_zoom_conditions.png", dpi=130)
    plt.close(fig)
    for name, r in results.items():
        index.append(dict(row="B_working_and_x4", panel=name, file=cyc["foreign-1"]["first"], crop_frame="anchor_working_1024",
                          x0=tx - WORK_HALF, y0=ty - WORK_HALF, size=2 * WORK_HALF, processing=name,
                          score_px=r["score"], verdict=r["verdict"], tau=r["tau"]))
    with open(out / "index.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in index for k in r)))
        w.writeheader()
        w.writerows(index)
    print(json.dumps({k: dict(score=v["score"], verdict=v["verdict"]) for k, v in results.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
