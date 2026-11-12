# 설계 검토와 수정 설계 (주형, 2026-11-12)

## 0. 작성 경위

- **실제 작성 모델:** Claude Opus 5.5 (`claude-opus-5-5`, Claude Code). 지시의 "Fable 5.2"는 이 세션에서 쓰지 않았다.
- **독립 초안:** `INDEPENDENT_DRAFT_v0.md`, SHA-256 `efd6a608…6e06`. 2026-11-12 13:31 KST에 저장했고, 근거 문서와 phone 문서를 읽기 전이다.
  - 같은 세션에서 기존 결과를 다뤘기 때문에 완전히 독립된 초안은 아니다.
  - 원문은 아래 §4 표에 대조했고, 공개 반환 `design-review-20261112`에 포함한다.
- **확인한 근거:** 모두 실제 파일과 commit에서 확인했다. 문서 요약만 보고 쓰지 않았다.
  - `57235a2:analysis/noise_repeatability_20261111/master/master_results.csv`, `claim_evidence_index.csv`
  - `57235a2:analysis/image_score_return_20261111/paired_auc_intervals.csv`
  - `57235a2:analysis/hazelnut/cross_category_summary.json`
  - GPU 로컬 `outputs/legacy-patchcore/screw-full320-test160/`(results.json, per_image.csv, npz header)
  - 기존 반환 `handoff/returns/juhyung/*`

## 1. 근거 대조 (검산 결과)

| 항목 | 문서 요약 | 실제 파일에서 확인한 값 | 일치 |
| --- | --- | --- | --- |
| Master | 165 조건 / 8 families / 13 protocol groups | 165행, family별 56/36/32/24/6/4/4/3, protocol_id 13개 | ✓ |
| Hazelnut taxonomy | regression 30, suppression 14, geometry 16, improvement/tie 40 / 70 | `cross_category_summary.json` 30/14/16/40, 출처 run `legacy-patchcore/hazelnut-full391-test110-repro` | ✓ (GPU 로컬에 이 run 없음) |
| PCB native | AU-PRO clean 0.9517, Bicubic 0.9391, SwinIR 0.9440; AUROC Bicubic 0.9680, SwinIR 0.9544 | master 동일, clean AUROC 0.9714 | ✓ |
| Screw 이미지 판정 (historical) | — | clean 0.9842 → Bicubic 0.4800 / SwinIR 0.6786; AU-PRO 0.957 → 0.801 / 0.856 | 추가 확인 |
| 집계 200 cell | Screw 0.41–0.68, top1 % < original 14/20 | 내 반환과 동일. CPU CI 80개 중 0 미만 37, 0 초과 2 (Screw) | ✓ |
| Noise σ15 SwinIR − Bicubic | Hazelnut −0.077~−0.079, Screw −0.044~−0.046 | 내 반환과 동일 | ✓ |

## 2. 점검한 위험 지점

1. **선택 사례의 인과 해석:**
   - 9사례 PNG, Screw 선택 n3/n3, suppression/geometry 분류는 설명용이다.
   - "geometry candidate"는 기전을 확정한 이름이 아니다.
   - 포스터에서는 정량 주장을 cohort 수준 지표로만 한다. 선택 사례는 "예시"라고 표시한다.
2. **같은 영상 반복의 표본 수:**
   - noise draw 2회, v1 `none`, 집계 5규칙은 모두 같은 70/119/160장을 다시 평가한 것이다.
   - 표본 수는 고유 영상 수로 쓴다. 반복은 노이즈/규칙 민감도다.
3. **프로토콜 혼합:**
   - historical (PIL bicubic, train 320 bank, calibration 없음)
   - realistic v1 / noise v2 (MATLAB LR, fit/cal 분할, seed 11)
   - restoration_objective (MATLAB endpoint)
   - PCB native
   - CPU HOG

   이들은 bank, 입력, split이 다르다. 표와 그림에서는 family별 열로 나누고, 서로 다른 family를 하나의 평균으로 합치지 않는다.
4. **Calibration / test GT:**
   - 모든 threshold는 calibration 정상만으로 정했다.
   - historical family는 calibration이 없어 F1/FPR이 정의되지 않는다(null). 이 family에서는 AUROC만 비교한다.
   - GT는 사후 평가와 그림에만 쓴다.
5. **Raw 미수신 범위:**
   - CPU는 NPZ 40개와 9사례 원본 map을 받지 않았다.
   - CPU의 scalar 검산과 GPU의 raw-map anchor는 서로 다른 검증이다. 포스터 각주에 구분해 적는다.

## 3. 포스터 핵심 주장 (3개로 고정)

| ID | 주장 (범위 포함) | 근거 | 한계 |
| --- | --- | --- | --- |
| **C1** | 복원 화질이 좋아도 이상 탐지가 고르게 좋아지지는 않는다. 평균 localization 개선 아래에 영상별 regression이 있고, 입력 열화에 따라 복원기 순위가 바뀐다. | historical Hazelnut AU-PRO SwinIR 0.843 vs Bicubic 0.819, 그런데 70장 중 30장 regression. noise σ15에서 SwinIR − Bicubic은 4개 draw 모두 음수(−0.04~−0.08), RealESRNet/GAN − SwinIR은 16/16 양수. | 단일 bank/split seed. 같은 영상 반복. 기전 미확정. |
| **C2** | ×4 왕복 뒤 Screw의 이미지 판정은 거의 우연 수준으로 떨어지지만, pixel localization은 대부분 유지된다. 고정한 max/top-k 집계 규칙으로는 회복되지 않는다. | historical clean 0.984 → ×4 0.48/0.68. realistic 0.41–0.68. AU-PRO 0.80–0.86. 집계 200 cell, CPU CI. 이번 v0.2 clean control로 clean에서의 집계 민감도를 추가 확인한다. | bank-domain(지혁) 결과 미도착. matched bank 미회복만으로 정보 소실을 결론내지 않는다. |
| **C3** | 스마트폰 촬영에서 조명 위치(좌/정면/우) 관리와 품질 기반 재촬영 정책이 입력 품질과 반복성 지표에 미치는 영향을 정량화해 보여준다. | 이번에 구현하는 도구와 첫 9장. 사진 도착 전에는 synthetic E2E만 있다. | 동일 물체 반복이라 탐지 성능은 주장하지 않는다. lux 미측정. 실물 결함 수량 미확인. |

## 4. 독립 초안 대비 수정 사항

| 항목 | 초안 v0 | 수정 | 이유 |
| --- | --- | --- | --- |
| 조명 3조건 | 주변광 / 책상등 / 플래시 | 책상등 **좌 / 정면 / 우** × 3반복이 기본. 플래시와 주변광은 별도 recipe. | 팀 계획(`PHONE_LIGHTING_POSTER_PLAN_20261112.md`)의 첫 9장 정의를 따른다. 광원을 바꾸는 것보다 같은 광원의 방향만 바꾸는 편이 물리 해석이 단순하다. |
| 비관리 baseline | 손으로 들고 촬영 | 유지하되 선택 사항. 주력 baseline은 **"품질 정책 없음"(모든 사진을 그대로 수용)**. | 첫 9장만으로도 비교할 수 있는 baseline이어야 한다. |
| 정렬 라이브러리 | OpenCV ORB + ECC | **scikit-image** ORB + RANSAC homography와 phase correlation 보조 | venv에 OpenCV가 없다(`ModuleNotFoundError: cv2`). skimage 0.26이 있다. 구매 0원이고 환경을 바꾸지 않는다. |
| 검사 점수 안정성 | 사전학습 특징 거리 map | **연기.** 이번 범위에서는 "anomaly map 미수신" 상태만 표시한다. | phone용 정상 reference/bank는 별도 구성이 필요하고, 동일 물체 9장은 bank와 평가를 나눌 수 없다. 일정 안에서 품질/반복성을 먼저 완성한다. |
| 판정 상태 | OK/REVIEW/RETAKE | 품질 상태는 **PASS/REVIEW/RETAKE**. station replay에서 탐지기가 없으면 verdict는 항상 **REVIEW**(사유 기록)이고, OK/NG는 내지 않는다. | 기존 `InspectionStation` 계약은 OK/NG/REVIEW/ERROR다. 탐지기 없이 OK를 주면 근거 없는 판정이 된다. |
| Threshold | 사진을 보기 전에 고정 | 유지. 수식, 단위, 값을 `PHONE_QUALITY_PROTOCOL_V0.1.md`로 고정한다. | 지시 B. |
| Photometric stereo | 언급 없음 | 범위 밖(확장 후보). | 스마트폰 자동 처리와 조명 보정 근거가 부족하고 일정도 맞지 않는다. |

## 5. 주력 구현과 baseline (고정)

- **주력:** `phone_*` 로컬 검사 도구. 다음 순서로 동작한다.
  1. 폴더 입력
  2. manifest(EXIF, SHA, part/session/recipe/repeat)
  3. 고정 ROI 품질 지표
  4. 기준 사진 정렬과 잔차
  5. 반복성 지표
  6. PASS/REVIEW/RETAKE 정책
  7. HTML report와 CSV
  8. 기존 `InspectionStation`으로 software replay
- **Baseline:** 같은 입력에 품질 정책을 적용하지 않은 경우, 즉 모든 사진을 그대로 수용한 경우.
- **비교 지표:** 조건별 반복성(정렬 후 ROI MAE, 품질 지표의 범위)과 정책이 보류한 비율. 보류한 사진도 분모에 포함한다.
- **성공 기준 (사진 도착 전에 고정):**
  - synthetic E2E에서 주입한 결함(밝기, clipping, blur, shift, 누락, 중복, 정렬 실패)이 각각 의도한 상태로 판정된다.
  - 실제 9장에 대해 report가 끝까지 생성된다.
  - 성능 주장은 하지 않는다.
- **병행:** v0.2 clean aggregation control (`exp/image-score-aggregation-juhyung`). 저장된 historical Screw clean/Bicubic/SwinIR 3 unit × 5 규칙이다. 결과는 C2 보강에 쓴다.
