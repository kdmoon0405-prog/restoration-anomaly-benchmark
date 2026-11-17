"""One private HTML result gallery: real board photos, phone zoom, MVTec same-location zooms, and bank-domain figures.

Only copies or downsizes stored outputs; it computes no new result. Photo thumbnails are JPEG (long side 900 px) made
from the private development photos; the full-resolution files are not copied. Every copied/derived file is listed with
its SHA-256 and source in gallery_manifest.json. The output contains photos and is private.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import html
import json
from pathlib import Path
import shutil

from PIL import Image, ImageOps

KIND_KO = {"normal": "정상", "foreign": "모사 이물", "lowlight": "저조도", "blur": "초점 흐림", "background": "흰 배경",
           "tilt": "기울임"}
CLASS_KO = {"improvement": "개선", "suppression": "결함 억제", "geometry_candidate": "형상 변화 후보", "small_change": "변화가 작음"}
COND_KO = {"none": "추가 열화 없음", "blur_s1.6": "흐림 σ1.6", "noise_s15": "노이즈 σ15"}
CSS = """
:root{--bg:#fbfaf7;--fg:#1f1d1a;--muted:#6b645b;--line:#ddd6cc;--card:#fff;--accent:#8f6035}
@media (prefers-color-scheme:dark){:root{--bg:#1a1917;--fg:#ece7df;--muted:#a59d92;--line:#3a3631;--card:#24221f;--accent:#d39b62}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 "Malgun Gothic",system-ui,sans-serif}
main{max-width:1280px;margin:0 auto;padding:16px}
h1{font-size:26px;margin:8px 0 4px}h2{font-size:21px;margin:34px 0 8px;border-bottom:2px solid var(--accent);padding-bottom:4px}
h3{font-size:17px;margin:20px 0 6px}.muted{color:var(--muted)}.note{background:var(--card);border:1px solid var(--line);padding:10px 12px;border-radius:6px}
nav a{margin-right:14px;color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px}
figcaption{overflow-wrap:anywhere}figure img{width:100%;height:auto;display:block}figcaption{font-size:13px;margin-top:6px}
.wide figure{margin-bottom:14px}table{border-collapse:collapse;margin:8px 0;font-size:14px}
td,th{border:1px solid var(--line);padding:4px 8px;text-align:right}th:first-child,td:first-child{text-align:left}
.tag{display:inline-block;padding:0 6px;border-radius:4px;background:var(--line);font-size:12px;margin-right:4px}
"""


def digest(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--station-run", type=Path, required=True, help="station run (manifest.json, station_result.csv, captures_quality_v03.csv)")
    p.add_argument("--photos", type=Path, required=True)
    p.add_argument("--phone-zoom", type=Path, required=True, help="output of make_phone_zoom_figures.py")
    p.add_argument("--mvtec-zoom", type=Path, required=True, help="output of make_defect_zoom_gallery.py")
    p.add_argument("--bank-figures", type=Path, nargs="*", default=[], help="outputs of make_bank_domain_figures.py")
    p.add_argument("--bank-table", type=Path, help="CSV of bank-domain pooled results to show as a table")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    out = a.output
    out.mkdir(parents=True, exist_ok=False)
    files: dict[str, dict] = {}

    def copy(src: Path, rel: str) -> str:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        files[rel] = dict(sha256=digest(dst), source=str(src), source_sha256=digest(src), derivation="copy")
        return rel

    def thumb(src: Path, rel: str) -> str:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((900, 900), Image.Resampling.LANCZOS)
            im.save(dst, "JPEG", quality=88)
        files[rel] = dict(sha256=digest(dst), source=str(src), source_sha256=digest(src), derivation="jpeg long side 900")
        return rel

    m = json.loads((a.station_run / "manifest.json").read_text(encoding="utf-8"))
    plan = m["plan"]
    for name, expected in m["input"]["files"].items():
        if digest(a.photos / name) != expected:
            raise ValueError(f"photo {name} differs from the station manifest")
    result = {r["cycle_id"]: r for r in rows(a.station_run / "station_result.csv")}
    body = []
    body.append("<h1>열화 입력과 미세 결함: 사진 결과 모음</h1>")
    body.append('<p class="note">비공개 검토용. 실제 사진은 그래픽카드 뒷면 1개, development 세션 1회(2026-11-15, 24장)이다. 같은 물체의 반복이므로 독립 부품 표본이 아니다. '
                "MVTec AD 사례는 정해 둔 분류 규칙으로 사후 선택한 예시이며 전체 성능을 대표하지 않는다. 수치는 각 그림의 index.csv에 있다.</p>")
    body.append('<nav><a href="#photos">실제 기판 사진</a><a href="#phonezoom">같은 위치 확대(기판)</a><a href="#mvtec">MVTec 같은 결함 위치 확대</a>'
                '<a href="#bank">정상 bank 비교</a></nav>')
    # 1. photos
    body.append('<h2 id="photos">1. 실제 기판 사진 (정상 · 모사 이물 · 저조도 · 흐림 · 대체 조명)</h2>')
    body.append('<p class="muted">판정은 운영 경로 C2(품질 정책 v0.3 + 기준 사진 차이 검사)의 저장 결과다. 대체 조명 L1 사진은 첫 사진이 PASS가 아닐 때만 쓰인다.</p>')
    refs = [("기준 L0 (reference)", plan["references"]["L0"]), ("기준 L1 (reference)", plan["references"]["L1"]),
            ("정상 보정 L0", plan["calibration"]["L0"]), ("정상 보정 L1", plan["calibration"]["L1"])]
    body.append("<h3>기준·보정 사진</h3><div class=grid>")
    for title, f in refs:
        rel = thumb(a.photos / f, f"photos/{f}")
        body.append(f'<figure><img loading=lazy src="{rel}" alt="{html.escape(title)}"><figcaption>{html.escape(title)} · {html.escape(f)}</figcaption></figure>')
    body.append("</div>")
    for kind in ("normal", "foreign", "lowlight", "blur", "background", "tilt"):
        cyc = [c for c in plan["cycles"] if c["kind"] == kind]
        if not cyc:
            continue
        body.append(f"<h3>{KIND_KO[kind]} ({len(cyc)} cycle)</h3><div class=grid>")
        for c in cyc:
            r = result.get(c["cycle_id"], {})
            for role, f in (("첫 사진", c["first"]), ("대체 조명 L1", c.get("alternate"))):
                if not f:
                    continue
                rel = thumb(a.photos / f, f"photos/{f}") if f"photos/{f}" not in files else f"photos/{f}"
                used = role == "첫 사진" or r.get("photos_used") == "2"
                state = r.get("first_quality_state") if role == "첫 사진" else r.get("second_quality_state")
                cap = (f'<span class=tag>{html.escape(c["cycle_id"])}</span>{role} · {html.escape(f)}<br>'
                       f'품질 v0.3: {html.escape(state or "판정 안 함")}<br>')
                if role == "첫 사진":
                    cap += f'최종 {html.escape(r.get("final_state", "-"))} · 사진 {html.escape(r.get("photos_used", "-"))}장 · {html.escape(r.get("reason", ""))}'
                else:
                    cap += "운영 경로에서 사용됨" if used else "운영 경로에서 사용되지 않음 (첫 사진 PASS)"
                body.append(f'<figure><img loading=lazy src="{rel}" alt="{html.escape(f)}"><figcaption>{cap}</figcaption></figure>')
        body.append("</div>")
    # 2. phone zoom
    body.append('<h2 id="phonezoom">2. 기판 사진의 같은 위치 확대</h2><div class=wide>')
    rel = copy(a.phone_zoom / "phone_zoom_conditions.png", "phone_zoom/phone_zoom_conditions.png")
    copy(a.phone_zoom / "index.csv", "phone_zoom/index.csv")
    body.append(f'<figure><img loading=lazy src="{rel}" alt="기판 같은 위치 확대"><figcaption>A행: 실제 촬영 조건 원본 해상도 확대. B행: 검사 해상도와 인위적 ×4 왕복(C1)과 차이 지도. '
                "위치는 사후 위치 표시이며 GT가 아니다. 실제 저조도·흐림을 복원한 것이 아니다.</figcaption></figure></div>")
    # 3. MVTec zoom
    gm = json.loads((a.mvtec_zoom / "manifest.json").read_text(encoding="utf-8"))
    copy(a.mvtec_zoom / "index.csv", "mvtec_zoom/index.csv")
    body.append('<h2 id="mvtec">3. MVTec AD: 같은 결함 위치의 원본 / 열화 입력 / Bicubic / SwinIR과 GT·검사 지도</h2>')
    body.append(f'<p class="muted">선택 규칙: {html.escape(gm["selection_rule"])}<br>분류 규칙: {html.escape(gm["taxonomy_rule"])}</p>')
    body.append("<table><tr><th>category / 조건</th><th>이상 영상</th><th>개선</th><th>결함 억제</th><th>형상 변화 후보</th></tr>")
    for key, cnt in gm["class_counts"].items():
        cat, cond = key.split("/")
        body.append(f"<tr><td>{cat} · {COND_KO.get(cond, cond)}</td><td>{cnt['anomalies']}</td><td>{cnt['improvement']}</td><td>{cnt['suppression']}</td><td>{cnt['geometry_candidate']}</td></tr>")
    body.append("</table><p class=muted>SwinIR − Bicubic 영상별 AU-PRO 기준, realistic-degradation v1 (bank/split seed 11). 같은 영상의 분류 수이며 독립 표본 수가 아니다.</p><div class=wide>")
    for r in rows(a.mvtec_zoom / "index.csv"):
        key = f'{r["category"]} · {COND_KO.get(r["condition"], r["condition"])} · {CLASS_KO.get(r["selection_class"], r["selection_class"])}'
        if r["available"] != "True":
            body.append(f"<p class=muted>{html.escape(key)}: 해당 분류의 사례 없음</p>")
            continue
        rel = copy(a.mvtec_zoom / r["png"], "mvtec_zoom/" + r["png"])
        body.append(f'<figure><img loading=lazy src="{rel}" alt="{html.escape(key)}"><figcaption>{html.escape(key)} · {html.escape(r["sample"])} · '
                    f'영상별 AU-PRO Bicubic {float(r["aupro_bicubic"]):.3f} → SwinIR {float(r["aupro_swinir"]):.3f} (Δ {float(r["delta_aupro"]):+.3f})</figcaption></figure>')
    body.append("</div>")
    # 4. bank
    body.append('<h2 id="bank">4. 같은 검사 입력, 다른 정상 bank (PatchCore, 지혁 bank-domain 이관 실행)</h2>')
    if a.bank_table:
        t = rows(a.bank_table)
        copy(a.bank_table, "bank/" + a.bank_table.name)
        cols = list(t[0])
        body.append("<table><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cols) + "</tr>")
        for r in t:
            body.append("<tr>" + "".join(f"<td>{html.escape(r[c])}</td>" for c in cols) + "</tr>")
        body.append("</table>")
    if not a.bank_figures:
        body.append("<p class=muted>아직 완료된 실행이 없다.</p>")
    for d in a.bank_figures:
        bm = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        tag = f'{bm["category"]}_seed{bm["seed"]}'
        copy(d / "index.csv", f"bank/{tag}/index.csv")
        counts = " · ".join(f'{q}: 개선 {c["improvement"]}, 억제 {c["suppression"]}, 형상 {c["geometry_candidate"]} / {c["anomalies"]}' for q, c in bm["taxonomy_counts"].items())
        body.append(f"<h3>{bm['category']} seed {bm['seed']}</h3><p class=muted>복원 bank − 원본 bank 분류 수: {html.escape(counts)}</p><div class=wide>")
        for r in rows(d / "index.csv"):
            if not r.get("png"):
                body.append(f"<p class=muted>{html.escape(r['query'])} · {CLASS_KO.get(r['case_class'], r['case_class'])}: 해당 분류의 사례 없음</p>")
                continue
            rel = copy(d / r["png"], f"bank/{tag}/{r['png']}")
            body.append(f'<figure><img loading=lazy src="{rel}" alt="{html.escape(r["sample"])}"><figcaption>{html.escape(r["query"])} 입력 · '
                        f'{CLASS_KO.get(r["case_class"], r["case_class"])} · {html.escape(r["sample"])} · AU-PRO 원본 bank {float(r["aupro_clean_bank"]):.3f} → 복원 bank {float(r["aupro_restored_bank"]):.3f}</figcaption></figure>')
        body.append("</div>")
    page = f'<!doctype html><html lang=ko><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>사진 결과 모음</title><style>{CSS}</style></head><body><main>{"".join(body)}</main></body></html>'
    (out / "index.html").write_text(page, encoding="utf-8")
    manifest = dict(kind="private_result_gallery", contains_photos=True, station_manifest_sha256=digest(a.station_run / "manifest.json"),
                    index_html_sha256=digest(out / "index.html"), files=files)
    (out / "gallery_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(files=len(files), html=str(out / "index.html"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
