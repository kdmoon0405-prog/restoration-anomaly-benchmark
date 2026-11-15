# 포스터 원고 초안 — 주형 담당 부분 (2026-11-15)

- **용도:** A0 세로(약 841 × 1189 mm) 포스터에 옮겨 넣을 편집용 본문, 표, 그림 목록이다. 공식 양식 파일은 받지 못했다. 팀 번호 위치와 3번 구성 배치는 양식을 받은 뒤 맞춘다.
- **작성 모델:** Claude Fable 5.2. 수치는 모두 반환된 CSV/JSON에서 가져왔고 출처를 표마다 적었다.
- **규칙:** family가 다른 수치는 한 평균으로 합치지 않는다. 같은 영상의 반복은 독립 표본으로 세지 않는다. 미도착·미측정 항목은 그렇게 적는다.

## 패널 A. 연구 질문

1. ×4 복원으로 화질이 좋아지면 산업용 이상 탐지도 같이 좋아지는가?
2. 촬영 조건을 관리하면 검사 입력과 판정이 어떻게 달라지는가?

## 패널 B. 주장 1 — 복원 화질과 탐지는 같이 움직이지 않는다

**본문 (약 60자 × 3줄)**

Hazelnut에서 SwinIR ×4는 Bicubic보다 평균 localization이 높지만, 이상 영상 70장 중 30장은 오히려 나빠졌다. LR 입력에 노이즈가 있으면 순위가 바뀌어 SwinIR이 Bicubic보다 낮아진다.

**표 B1. Hazelnut, noise가 없는 ×4 (family `historical_recovery`, 이상 70장)**

| 복원 | pooled AU-PRO@0.3 | 영상별 변화 (SwinIR − Bicubic) |
| --- | --- | --- |
| Bicubic ×4 | 0.819 | — |
| SwinIR ×4 | 0.843 | 나빠짐 30 / 70 (suppression 14, geometry candidate 16), 같거나 좋아짐 40 / 70 |

출처: master `historical_recovery`, `analysis/hazelnut/cross_category_summary.json`. "geometry candidate"는 분류 이름이고 원인을 확정한 것이 아니다.

**표 B2. LR 노이즈가 있을 때 SwinIR − Bicubic pooled AU-PRO (family `realistic_lr_degradation_v1` / `realistic_lr_noise_v2`)**

| 카테고리 | σ5 (v1 / seed 23 / seed 37) | σ15 (v1 / seed 23 / seed 37) |
| --- | --- | --- |
| Hazelnut (이상 70장) | −0.040 / −0.019 / −0.031 | −0.046 / −0.077 / −0.079 |
| Screw (이상 119장) | −0.011 / −0.002 / −0.011 | −0.037 / −0.044 / −0.046 |

- RealESRNet / RealESRGAN − SwinIR은 새 noise draw 16개 비교에서 모두 양수다(σ5 +0.03~+0.09, σ15 +0.14~+0.25).
- Screw σ5는 방향이 확정되지 않았다. CPU 분석에서 영상별 평균 차이의 95 % 구간이 0을 포함한다.
- 세 값은 같은 영상을 노이즈만 다시 뽑아 측정한 것이다. bank와 split seed는 11 하나다.

출처: `handoff/returns/juhyung/realistic-noise-v2-*`, CPU `analysis/noise_repeatability_20261111/REVIEW.md`.

**그림 B (후보):** 표 B2를 막대 6쌍으로 그린 그림. CPU가 만든 pooled point + per-image CI 그림을 재사용한다.

## 패널 C. 주장 2 — ×4 뒤 Screw는 "어디가 이상한지"보다 "이상한지 아닌지"가 무너진다

**본문**

Screw는 ×4 왕복 뒤 이미지 판정(AUROC)이 0.98에서 0.48–0.68로 떨어진다. 화소 단위 localization(AU-PRO)도 낮아지지만 0.80–0.86에 머문다. 이미지 점수를 만드는 집계 규칙을 5가지로 바꿔도 회복되지 않았다.

**표 C1. Screw, family `historical_recovery` (test 160장: 정상 41, 이상 119)**

| 입력 | image AUROC | pooled AU-PRO@0.3 |
| --- | --- | --- |
| clean | 0.984 | 0.957 |
| Bicubic ×4 | 0.480 | 0.801 |
| SwinIR ×4 | 0.679 | 0.856 |

**표 C2. 집계 규칙별 image AUROC (같은 저장 map의 재집계)**

| 입력 | 원본 점수 | map max | 상위 0.1 % | 상위 0.5 % | 상위 1 % |
| --- | --- | --- | --- | --- | --- |
| clean | 0.984 | 0.983 | 0.984 | 0.984 | 0.983 |
| Bicubic ×4 | 0.480 | 0.453 | 0.450 | 0.440 | 0.435 |
| SwinIR ×4 | 0.679 | 0.634 | 0.626 | 0.603 | 0.583 |

- realistic family 40 unit(Hazelnut, Screw)에서도 Screw는 모든 규칙에서 0.41–0.68이었다(200 cell).
- 이 표는 새 추론이 아니라 저장된 예측의 재평가다. 독립 실험 수에 더하지 않는다.
- ×4가 map을 바꾸는 원인(참조 bank의 domain, 표현, 정보 손실)은 미확정이다. bank-domain 대조(지혁)는 미도착이다.

출처: `image-score-aggregation-20261111-*`, `image-score-aggregation-clean-control-20261112`, CPU `handoff/cpu_reviews/20261112/`.

## 패널 D. PCB 전체 기판 (요약 한 줄과 표)

Native 224 tiling으로 GT 연결요소 324개를 모두 보존한 채 전체 cohort(test 200: 정상 100, 이상 100)를 평가했다.

| 입력 | image AUROC | pooled AU-PRO@0.3 |
| --- | --- | --- |
| clean | 0.971 | 0.952 |
| Bicubic ×4 | 0.968 | 0.939 |
| SwinIR ×4 | 0.954 | 0.944 |

SwinIR은 localization이 Bicubic보다 높고 이미지 판정은 낮다. 고정 threshold F1 차이를 기준점 하나로 설명한 과거 해석은 철회했다.

출처: master `pcb_native_full_cohort_v0_6`.

## 패널 E. 실물 촬영 — recipe, 품질 정책, 재촬영 (development 결과)

**본문**

스마트폰 1대와 책상 조명으로 그래픽카드 뒷면 1개를 찍어, 촬영 recipe → 정렬 → 입력 품질 → 기준 사진 차이 검사 → 최대 1회 재촬영을 연결했다. 조명을 바꿔도 24장 모두 정렬됐다. 화면 전체에 고정 포화 규칙을 쓰면 배경과 원래 밝은 납땜 때문에 대부분의 사진을 거부한다. 관찰 영역 안에서 기준 사진 대비 변화만 보면 거부가 줄어든다.

**표 E1. 입력 품질 판정 (사진 24장)**

| 정책 | PASS | REVIEW | RETAKE |
| --- | --- | --- | --- |
| v0.1, 화면 전체 | 3 | 3 | 18 |
| v0.1, 관찰 영역 | 3 | 6 | 15 |
| v0.2, 관찰 영역 + 기준 사진 대비 | 15 | 9 | 0 |

사람의 판독 기록이 없어 어느 정책이 더 맞는지는 판정하지 않았다(NA).

**표 E2. 촬영·검사 조건 비교 (최초 cycle 16개 전부가 분모)**

| 조건 | 사진 수 | 모사 이물 3 cycle 중 NG | 정상 기판 13 cycle 중 NG | 정상 13 cycle 중 NG 또는 REVIEW |
| --- | --- | --- | --- | --- |
| C0 고정 촬영, 직접 검사 | 16 | 3 | 2 | 2 |
| C1 ×4 왕복 후 검사 (Bicubic / SwinIR) | 16 | 3 / 3 | 0 / 0 | 0 / 0 |
| C2 품질 정책 v0.1 + 재촬영 | 23 | 0 (3건 모두 REVIEW) | 0 | 9 |
| C2 품질 정책 v0.2 + 재촬영 | 19 | 3 | 1 | 7 |
| C3 항상 두 조명 | 14 (9 cycle은 사진 없음) | 3 | 1 (사진이 있는 4 cycle 중) | 1 |

- 모사 이물은 분홍색 조각 1종, 1위치, 반복 3회다. 전기적 결함이 아니다.
- 방법을 이 세션의 사진을 본 뒤 정했으므로 독립 평가가 아니다. 탐지 성능으로 읽지 않는다.
- C1은 실물 사진에 ×4 왕복을 가한 별도 family다. 기존 benchmark의 ×4 결과와 합치지 않는다.
- 시간은 소프트웨어 처리 시간만 쟀다(24장 전체 147초). 실제 촬영 시간, mm 분해능, lux는 미측정이다.

**그림 E (후보, 비공개 원본에서 골라 넣을 것)**

1. 같은 cycle의 원본(관찰 영역 노란 상자) / 차이 map / 판정 — `foreign-1`의 L0와 L1.
2. 화면 전체 포화 overlay(L0 사진, 배경이 빨갛게 표시됨)와 관찰 영역만 본 경우의 대비.
3. 재촬영 이력 한 줄: `lowlight-3`: 첫 촬영 REVIEW(어두움) → L1 재촬영 PASS → OK, 사진 2장.

**시연 순서와 재현 명령**

```powershell
$py = '.venv\Scripts\python.exe'
# 1) 합성 입력으로 전체 흐름 확인 (사진 없이 가능)
& $py -m pytest -q tests/test_phone_station.py
# 2) 실제 사진 폴더(사진 + capture_sheet.csv)와 recipe/plan으로 비교 실행
& $py scripts/run_phone_station_compare.py --input <사진 폴더> --recipe <recipe.json> --plan <plan.json> --output <새 폴더> --kind real --assets-root <checkpoint가 있는 checkout> --device cuda
# 3) 출력 폴더의 report.html을 브라우저로 연다 (사진 축소본 포함, 비공개)
```

## 한계 (포스터 하단 공통)

- bank/split seed는 11 하나다. 학습 seed 일반화는 검증하지 않았다.
- 선택 사례 그림(9사례 등)은 예시이고 전체 추정이 아니다.
- CPU는 raw map 배열을 받지 않았다. scalar 검산(CPU)과 raw map 재현 검증(GPU)은 별개다.
