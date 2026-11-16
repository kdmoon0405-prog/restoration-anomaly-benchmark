"""Poster text and layout (points on the 2383.875 x 3370.375 pt A0 template slide 3) -> poster_spec.json."""
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
FIG = OUT / "poster_figures"
LX, LW = 69, 900          # left column
RX, RW = 1075, 1255       # right column
BODY = 26


def pic(name, file, left, top, width):
    w, h = Image.open(FIG / file).size
    return dict(type="picture", name=name, file=file, left=left, top=top, width=width, height=round(width * h / w, 1))


def text(name, left, top, width, height, lines, size=BODY, space_after=8, bold_first=False, color=None):
    return dict(type="text", name=name, left=left, top=top, width=width, height=height, lines=lines, size=size,
                space_after=space_after, bold_first=bold_first, color=color)


items = []
# ------------------------------------------------------------------ left column
items.append(text("bg_text", LX, 708, LW, 505, size=29, space_after=10, lines=[
    "• 저해상도 검사 영상을 초해상도(SR)로 복원하면 PSNR·SSIM 같은 화질 지표는 올라간다. 그러나 화질이 좋아진다고 이상 탐지도 좋아지는지는 따로 확인해야 한다.",
    "• 실제 외관검사 라인은 촬영 위치·조명·관찰 영역을 recipe로 고정하고, 입력 품질·오검·재검 부하를 함께 관리한다 (검사장비·산업용 카메라 업체 공개 자료 5건 검토).",
    "• 그래서 두 가지를 함께 본다: 복원이 탐지에 주는 효과와 실패 조건, 그리고 촬영 조건을 관리했을 때 검사 입력과 판정이 달라지는 정도.",
]))
items.append(text("obj_text", LX, 1322, LW, 412, size=29, space_after=10, lines=[
    "1. ×4 복원이 PatchCore 이상 탐지에 주는 효과와 실패 조건을 MVTec AD(Hazelnut, Screw)와 VisA(PCB)에서 정량화한다.",
    "2. 스마트폰 1대와 책상 조명만으로 촬영 recipe → 정렬 → 입력 품질 → 기준 사진 차이 검사 → 조건부 대체 촬영을 잇는 검사 시제품을 만든다 (추가 구매 0원).",
    "3. 촬영·처리 조건 C0–C3를 같은 사례에 적용해 판정, 보류, 사진 사용 수를 비교한다.",
]))
items.append(text("m_text1", LX, 1848, LW, 262, [
    "기존 benchmark",
    "• PatchCore(정상 영상 bank, exact 최근접 탐색), 224→56→224의 ×4 왕복. 복원: Bicubic, SwinIR, RealESRNet, RealESRGAN.",
    "• 지표: pooled AU-PRO@0.3(위치), image AUROC(이미지 판정). 예측 조건 165개, bank/split seed 11.",
    "스마트폰 검사 시제품 (운영 경로: 품질 정책 v0.3 + 최대 1회 대체 조명)",
], size=24, space_after=5, bold_first=True))
flow = pic("fig_flow", "fig_M_station_flow.png", LX, 2118, LW)
items.append(flow)
ty = flow["top"] + flow["height"] + 14
items.append(dict(type="table", name="cond_table", left=LX, top=ty, width=LW, height=330, size=22,
                  col_fractions=[0.16, 0.42, 0.42],
                  cells=[["조건", "촬영", "처리"],
                         ["C0", "첫 조명(L0) 1장", "품질 정책 없이 직접 검사"],
                         ["C1", "같은 1장", "×0.25 축소 후 ×4 복원(Bicubic / SwinIR) → 같은 검사"],
                         ["C2", "L0 1장, 필요하면 L1 1장", "품질 정책 → 조건부 대체 → 검사"],
                         ["C3", "L0와 L1 항상 2장", "조명별 검사, 하나라도 NG면 NG"]]))
items.append(text("m_text2", LX, ty + 345, LW, 3300 - (ty + 345), [
    "• 입력 품질: 관찰 영역 안에서, 같은 조명의 참조 사진에 없던 포화·암부(1% 초과)와 선명도 저하(0.5배 미만)만 센다.",
    "• 검사: 정렬 후 기준 사진과의 국소 정규화 차이. 정상 보정 사진으로 임계값을 정하고, 차이 덩어리가 25 px 이상이면 NG.",
    "• 실물 입력: 그래픽카드 뒷면 1개, 스마트폰 사진 24장(1세션). 모사 이물은 분홍 조각 1종·1위치.",
], size=23, space_after=5))

# ------------------------------------------------------------------ right column: results
items.append(text("r_head1", RX, 706, RW, 44, ["① 복원 화질과 이상 탐지 (MVTec AD · VisA, 저장된 예측 결과)"], size=30, bold_first=True, color=0x8F6035))
figb = pic("fig_B", "fig_B_benchmark.png", RX + 60, 756, RW - 120)
items.append(figb)
y = figb["top"] + figb["height"] + 12
figc = pic("fig_C", "fig_C_screw_aggregation.png", RX, y, 590)
items.append(figc)
items.append(text("r_text_c", RX + 615, y + 4, RW - 615, figc["height"], [
    "• Hazelnut(이상 70장): 평균 AU-PRO는 오르지만 30장은 영상별로 나빠졌다.",
    "• LR에 노이즈가 있으면 SwinIR이 Bicubic보다 낮다(σ15에서 AU-PRO 차이 -0.04 ~ -0.08). Screw σ5는 방향 미확정.",
    "• Screw(test 160장): image AUROC clean 0.984 → Bicubic 0.480 / SwinIR 0.679. AU-PRO도 0.957 → 0.801 / 0.856으로 낮아진다.",
    "• PCB 전체 기판(test 200장): image AUROC clean 0.971, Bicubic 0.968, SwinIR 0.954 / AU-PRO 0.952, 0.939, 0.944.",
], size=23, space_after=5))
y = figc["top"] + figc["height"] + 14
items.append(text("r_head2", RX, y, RW, 44, ["② 스마트폰 검사 시제품 (보드 1개 · 사진 24장 · development 결과)"], size=30, bold_first=True, color=0x8F6035))
e1 = pic("fig_E1", "fig_E1_real_photos.png", RX, y + 50, RW)
items.append(e1)
e2 = pic("fig_E2", "fig_E2_quality_and_retake.png", RX + 150, e1["top"] + e1["height"] + 8, RW - 300)
items.append(e2)
y = e2["top"] + e2["height"] + 12
e3 = pic("fig_E3", "fig_E3_quality_states.png", RX, y + 14, 470)
e4 = pic("fig_E4", "fig_E4_conditions.png", RX + 520, y, 715)
items += [e3, e4]
y = max(e3["top"] + e3["height"], e4["top"] + e4["height"]) + 8
items.append(text("r_note", RX, y, RW, 36, [
    "사진 수는 저장된 사진의 논리적 사용 횟수다. 실제 촬영 시간·mm 분해능·lux는 측정하지 않았다."], size=21, color=0x74614F))
DISC = y + 44
items.append(text("d_text", RX, DISC + 90, RW, 250, [
    "• 복원 화질과 탐지는 같이 움직이지 않는다. 평균 개선 아래에 영상별 저하가 있고, 입력에 노이즈가 있으면 복원기 순위가 바뀐다.",
    "• ×4 뒤 Screw의 이미지 판정 저하는 집계 규칙 5가지로 회복되지 않았다. 원인(참조 bank의 domain 등)은 미확정이다.",
    "• 화면 전체 고정 포화 규칙은 배경과 원래 밝은 납땜 때문에 24장 중 18장을 재촬영으로 보냈다. 관찰 영역에서 같은 조명 참조와 비교하면 0장이다.",
    "• 같은 7 cycle에서 C2는 사진 10장, C3는 14장을 썼고 모사 이물은 둘 다 3/3 NG였다. C1은 Bicubic과 SwinIR의 판정이 16 cycle 모두 같았다.",
], size=23, space_after=3))
CONC = DISC + 90 + 256
items.append(text("c_text", RX, CONC + 90, RW, 3302 - (CONC + 90), [
    "• SR 복원은 화질 지표만으로 채택할 수 없다. 탐지 지표와 입력 조건(노이즈)을 함께 확인해야 한다.",
    "• 구매 없이 스마트폰과 책상 조명으로, 촬영 recipe부터 판정·이력까지 이어지는 검사 시제품을 만들었다.",
    "• 한계: 보드 1개·세션 1개·모사 이물 1종 1위치의 development 결과다. 독립 평가 세션, 사람 판독 기록, 실제 촬영 시간은 아직 없다.",
], size=23, space_after=3))

spec = dict(template_slide=3, font="맑은 고딕", figure_dir=str(FIG), output_dir=str(OUT),
            moves=[dict(name="Group 35", left=RX, top=609, width=RW), dict(name="Group 38", left=RX, top=DISC, width=RW),
                   dict(name="Group 42", left=RX, top=CONC, width=RW)],
            replace_text=[dict(starts_with="연구제목",
                               lines=["복원 화질이 좋아지면 이상 탐지도 좋아지는가",
                                      "×4 초해상도 복원의 효과·실패 조건과 스마트폰 촬영 검사 시제품",
                                      "[저자 · 지도교수 확인 필요]", "[소속 · 연구실 확인 필요]"], sizes=[66, 46, 36, 36]),
                          dict(starts_with="Team No_", lines=["Team No_??"], sizes=[71.6])],
            items=items)
(HERE / "poster_spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(dict(DISC=DISC, CONC=CONC, flow_bottom=flow["top"] + flow["height"], table_top=ty,
                      bottoms={i["name"]: round(i["top"] + i["height"]) for i in items}), ensure_ascii=False))
