"""Same-position evidence for the simulated objects of a phone evaluation run (post-hoc, evaluation only).

For every photo of the annotated cases (large object P1-P3, small object M1-M3 x clear / low light / blur, L0 and L1)
this writes what the inspection saw at the object position:
- full-resolution crop (no processing) and the working-resolution crop in the photo's own frame
- the artificial x4 round trip (x0.25, then Bicubic or SwinIR x4) used by condition C1
- golden-reference difference maps (original / Bicubic / SwinIR) against the run's L0 reference, with the run's
  own normal-calibration threshold tau; the largest blob verdict as in the station; and the blob that touches the
  object position (area, whether the station's largest blob lies within the location radius)

Annotations (object_annotations.json) are object centres marked after the method was run; they are not pixel GT and
are used only for this location check. Registration, calibration and thresholds are the run's fixed method; nothing
here changes a verdict. Photos and outputs are private.
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
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import phone_capture as pc  # noqa: E402
from sr_anomaly import phone_station as ps  # noqa: E402

FULL_HALF = 120   # full-resolution crop half size (px)
WORK_HALF = 40    # working-resolution crop half size (px)
COND_KO = {"clear": "선명", "lowlight": "저조도", "blur": "흐림"}


def apply(matrix, xy):
    v = np.asarray(matrix, dtype=np.float64) @ np.array([xy[0], xy[1], 1.0])
    return float(v[0] / v[2]), float(v[1] / v[2])


def crop(arr, cx, cy, half):
    h, w = arr.shape[:2]
    x0, y0 = int(round(cx)) - half, int(round(cy)) - half
    out = np.zeros((2 * half, 2 * half) + arr.shape[2:], arr.dtype)
    xs0, ys0, xs1, ys1 = max(x0, 0), max(y0, 0), min(x0 + 2 * half, w), min(y0 + 2 * half, h)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0] = arr[ys0:ys1, xs0:xs1]
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--photos", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--assets-root", type=Path, required=True)
    p.add_argument("--device", default="cuda")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--same-light", action="store_true",
                   help="development variant: register and compare each photo to the reference/calibration of its expected light")
    a = p.parse_args(argv)
    out = a.output
    out.mkdir(parents=True, exist_ok=False)
    (out / "png").mkdir()
    m = json.loads((a.run / "manifest.json").read_text(encoding="utf-8"))
    recipe = m["recipe"]
    plan = json.loads((a.run / "plan.from_sheet.json").read_text(encoding="utf-8")) if (a.run / "plan.from_sheet.json").is_file() else m["plan"]
    ann = json.loads(a.annotations.read_text(encoding="utf-8"))["cases"]
    anchor_full, _ = pc.decode(a.photos / recipe["anchor"])
    anchor, _ = pc.working(anchor_full)
    ay = pc.luma(anchor)
    box = pc.roi_box(anchor.shape, recipe["roi"])

    sys.path.insert(0, str(a.assets_root / "src"))
    from sr_anomaly.real_models import SwinIRLightweight, matlab_bicubic_resize
    basicsr = a.assets_root / "third_party" / "BasicSR"
    swinir = SwinIRLightweight(a.assets_root / "third_party/SwinIR", a.assets_root / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth",
                               device=a.device, scale=4, tile=64, tile_overlap=0).restore
    down = lambda img: matlab_bicubic_resize(img, 0.25, basicsr)  # noqa: E731
    variants = {"original": lambda rgb: rgb,
                "bicubic_x4": lambda rgb: ps.x4_roundtrip(rgb, down, lambda lr: matlab_bicubic_resize(lr, 4.0, basicsr)),
                "swinir_x4": lambda rgb: ps.x4_roundtrip(rgb, down, swinir)}

    sheet = {r["file"]: r for r in csv.DictReader(open(a.photos / "capture_sheet.csv", encoding="utf-8"))}
    lights = ["L0", "L1"] if a.same_light else ["L0"]
    ref_y = {lt: pc.luma(pc.working(pc.decode(a.photos / plan["references"][lt])[0])[0]) for lt in lights}

    def light_of(name):
        lt = sheet.get(name, {}).get("light", "L0")
        return lt if lt in ref_y else "L0"

    def load(name):
        full, _ = pc.decode(a.photos / name)
        work, scale = pc.working(full)
        lt = light_of(name)
        if name == plan["references"].get(lt) or (not a.same_light and name == recipe["anchor"]):
            al = dict(success=True, matrix=np.eye(3).tolist(), inlier_ratio=1.0)
        else:
            al = pc.align(ref_y[lt] if a.same_light else ay, pc.luma(work))
        return dict(full=full, work=work, scale=scale, al=al, light=lt)

    calib, ref_w = {}, {}
    for lt in lights:
        ref, cal = load(plan["references"][lt]), load(plan["calibration"][lt])
        for v, fn in variants.items():
            rw = pc.warp_to_reference(fn(ref["work"]), ref["al"]["matrix"], anchor.shape)
            cw = pc.warp_to_reference(fn(cal["work"]), cal["al"]["matrix"], anchor.shape)
            ref_w[v, lt] = rw
            calib[v, lt] = ps.gr_calibrate(ps.difference_map(cw[0], rw[0]), ps.inspection_mask(anchor.shape, box, rw[1], cw[1]))

    case_of = {}
    for c in plan["cycles"]:
        key = next((k for k in ann if c["cycle_id"].startswith(k)), None)
        if key:
            cond = next((s for s in ("clear", "lowlight", "blur") if s in c["cycle_id"]), "clear")
            for role in ("first", "alternate"):
                if c.get(role):
                    case_of[c[role]] = dict(case=key, cycle_id=c["cycle_id"], role=role, condition=cond, label=c.get("label"))
    rows, per_case = [], {}
    for name, info in case_of.items():
        d = load(name)
        an = ann[info["case"]]
        ox, oy = an["xy_full"][0] * d["scale"], an["xy_full"][1] * d["scale"]   # working, photo's own frame
        row = dict(file=name, **info, registered=bool(d["al"]["success"]), inlier_ratio=round(float(d["al"].get("inlier_ratio", np.nan)), 4),
                   object_work_xy=f"{ox:.1f},{oy:.1f}")
        maps = {}
        if d["al"]["success"]:
            inv = np.linalg.inv(np.asarray(d["al"]["matrix"], dtype=np.float64))
            axy = apply(inv, (ox, oy)) if name != recipe["anchor"] else (ox, oy)
            # station convention (warp_to_reference): matrix maps the anchor frame to the photo frame
            row["object_anchor_xy"] = f"{axy[0]:.1f},{axy[1]:.1f}"
            row["compared_to_light"] = d["light"]
            for v, fn in variants.items():
                cv = calib[v, d["light"]]
                tw = pc.warp_to_reference(fn(d["work"]), d["al"]["matrix"], anchor.shape)
                diff = ps.difference_map(tw[0], ref_w[v, d["light"]][0])
                mask = ps.inspection_mask(anchor.shape, box, ref_w[v, d["light"]][1], tw[1])
                res = ps.gr_inspect(diff, mask, cv)
                lab, _ = ndimage.label((diff > cv["tau"]) & mask, structure=np.ones((3, 3), int))
                yy, xx = np.ogrid[:diff.shape[0], :diff.shape[1]]
                near = (xx - axy[0]) ** 2 + (yy - axy[1]) ** 2 <= 6 ** 2
                ids = np.unique(lab[near & (lab > 0)])
                obj_area = int(max((lab == k).sum() for k in ids)) if len(ids) else 0
                row[f"{v}_verdict"] = res["verdict"]
                row[f"{v}_largest_blob"] = res["score"]
                row[f"{v}_location_match"] = ps.location_match(res["centroid_xy"], axy)
                row[f"{v}_object_blob_area"] = obj_area
                row[f"{v}_object_max_diff_over_tau"] = round(float(diff[near].max() / cv["tau"]), 3)
                maps[v] = (diff, cv["tau"], axy, mask)
        rows.append(row)
        per_case.setdefault((info["cycle_id"], info["condition"]), {})[info["role"]] = (name, d, row, maps, (ox, oy))

    for (case, cond), roles in sorted(per_case.items()):
        fig, axes = plt.subplots(len(roles), 7, figsize=(24, 4.1 * len(roles)), squeeze=False,
                                 gridspec_kw={"wspace": 0.05, "hspace": 0.35})
        for r, role in enumerate(("first", "alternate")):
            if role not in roles:
                continue
            name, d, row, maps, (ox, oy) = roles[role]
            ax = axes[r if len(roles) > 1 else 0]
            full_c = crop(d["full"], ox / d["scale"], oy / d["scale"], FULL_HALF)
            work_c = crop(d["work"], ox, oy, WORK_HALF)
            lr = np.asarray(down(Image.fromarray(d["work"])))
            lr_c = np.kron(crop(lr, ox / 4, oy / 4, WORK_HALF // 4), np.ones((4, 4, 1), np.uint8))
            bic_c = crop(variants["bicubic_x4"](d["work"]), ox, oy, WORK_HALF)
            swi_c = crop(variants["swinir_x4"](d["work"]), ox, oy, WORK_HALF)
            light = "L1 대체" if role == "alternate" else "첫 사진"
            panels = [(f"{light} 원본 해상도\n{name}", full_c), ("검사 해상도 (긴 변 1024)", work_c), ("×0.25 입력 (최근접)", lr_c),
                      ("Bicubic ×4", bic_c), ("SwinIR ×4", swi_c)]
            for k, (t, im) in enumerate(panels):
                ax[k].imshow(im, interpolation="nearest")
                ax[k].set_title(t, fontsize=12, loc="left")
                ax[k].axis("off")
            for k, v in enumerate(("original", "swinir_x4")):
                axk = ax[5 + k]
                axk.axis("off")
                if v not in maps:
                    axk.text(0.02, 0.5, f"정렬 실패\n(inlier 비율 {row['inlier_ratio']})\n→ 검사하지 않음", fontsize=14, transform=axk.transAxes)
                    continue
                diff, tau, axy, mask = maps[v]
                dc = crop(diff, axy[0], axy[1], WORK_HALF)
                axk.imshow(dc, cmap="viridis", vmin=0, vmax=max(2 * tau, float(dc.max())), interpolation="nearest")
                axk.contour(dc > tau, levels=[0.5], colors="#ff3030", linewidths=1.4)
                axk.plot([WORK_HALF], [WORK_HALF], marker="+", color="white", ms=14, mew=2)
                lab = {"original": "원본", "swinir_x4": "SwinIR ×4"}[v]
                axk.set_title(f"차이 ({lab}) 빨강=τ 초과\n물체 {row[f'{v}_object_blob_area']} px · 최대 {row[f'{v}_largest_blob']} px {row[f'{v}_verdict']}", fontsize=12, loc="left")
        mode = "개발 변형: 같은 조명 참조로 정렬·비교" if a.same_light else "고정 방법 v0.3: L0 anchor 정렬, L0 참조와 비교"
        fig.suptitle(f"{case} · {COND_KO[cond]} · {mode} · + = 사후 위치 표시(GT 아님) · 판정 한계 25 px · τ는 이 세션의 참조·정상 보정으로만 정함",
                     fontsize=14, x=0.01, ha="left")
        fig.savefig(out / "png" / f"{case}.png", dpi=100, bbox_inches="tight")
        plt.close(fig)
    with open(out / "object_cases.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)
    (out / "manifest.json").write_text(json.dumps(dict(kind="phone_eval_object_cases", run=str(a.run), annotations=str(a.annotations),
                                                       same_light=a.same_light,
                                                       calibration={f"{v}/{lt}": c for (v, lt), c in calib.items()}, gr=ps.GR), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(dict(photos=len(rows), figures=len(per_case))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
