# DESIGN_DECISION — 최종 스테이션 설계와 품질 정책 v0.3 (2026-11-15 고정)

- **작성 모델:** Claude Fable 5.2 (`claude-fable-5-2`, Claude Code).
- **읽은 문맥:** Opus 5.5 초안 v0, Fable 5.2 초안 v1과 재검토, `DESIGN_DECISION_PHONE_V0.2.md`, CPU의 `analysis/phone_station_return_20261115/REVIEW.md`와 `docs/PHONE_STATION_REVIEW_NEXT_20261115.md`, 2026-11-15 development 세션의 전체 결과. 독립 설계가 아니다.
- **작성 순서:** 이 문서(설계 마무리) → 구현 → 실행 → 자체 검토(`FINAL_REVIEW.md`).
- v0.1과 v0.2의 규칙과 결과는 그대로 보존한다. 이 문서는 그 위에 최종 운영 경로와 수정안 하나를 더한다.

## 1. 최종 방법 (운영 경로)

입력 폴더(사진 + `capture_sheet.csv`)와 recipe를 받아 cycle마다 다음 순서로 처리한다.

1. **입력 확인:** 기록표의 part/session/recipe, 파일 유무, SHA-256, 중복.
2. **정렬:** anchor 사진에 homography를 맞춘다. 관찰 ROI 안의 inlier 수와 분포, ROI 투영 coverage로 검증한다.
3. **입력 품질:** 정책 v0.3으로 PASS / REVIEW / RETAKE를 정한다.
4. **검사:** PASS인 사진을 같은 조명의 참조와 비교한다(golden-reference v0.1).
5. **대체 입력:** 첫 사진이 PASS가 아니면 사전 지정한 대체 조명 사진을 1회 요청한다. 한 cycle의 사진은 최대 2장이다.
6. **최종 상태와 이력:** OK / NG / REVIEW / ERROR와 이유를 CSV와 HTML에 남긴다.

운영 경로는 조건 `C2_policy_v0.3`이다. 나머지 조건은 같은 cycle에 대한 비교군이다.

## 2. 비교군

| 조건 | 내용 | 역할 |
| --- | --- | --- |
| C0 | 첫 사진 1장을 품질 정책 없이 직접 검사 | 우선 대조군 |
| C3 | 두 조명 사진을 항상 검사하고 하나라도 NG면 NG | 우선 대조군 |
| C2 v0.3 | 품질 정책 + 조건부 대체 입력 | 운영 경로 |
| C2 v0.2, C2 v0.1(ROI) | 이전 정책 | ablation |
| C1 Bicubic / SwinIR | ×0.25 축소 후 ×4 복원한 영상으로 C0와 같은 검사 | `phone_x4_roundtrip` family |

## 3. 입출력

- **입력:** 사진 폴더, `capture_sheet.csv`, `recipe.json`. 실행 계획(`plan.json`)은 파일로 주거나, 기록표의 `station_role` / `cycle_id` / `light` 열에서 자동으로 만든다.
- **출력 (새 폴더에만 쓴다. 기존 폴더가 있으면 거부한다):**
  - `station_result.csv`: cycle별 운영 경로의 최종 상태, 이유, 사진 수
  - `cycles.csv`, `summary.csv`, `inspections.csv`, `captures_quality.csv`, `gr_calibration.csv`
  - `manifest.json`: source, recipe, plan, 임계값, 입력 SHA-256, 시간
  - `station_events.jsonl`: 기존 `InspectionStation` 재생 기록
  - `report.html`: 사진 축소본, ROI, 차이 지도, 판정, 이력 (비공개)

## 4. 상태 전이와 실패 시 동작

| 상황 | 품질 상태 | cycle의 최종 상태 |
| --- | --- | --- |
| 첫 사진 PASS, 검사 통과 / 차이 발견 | PASS | OK / NG (사진 1장) |
| 첫 사진이 PASS가 아님, 대체 사진 PASS | REVIEW 또는 RETAKE → PASS | 대체 사진의 검사 결과 OK / NG (사진 2장) |
| 첫 사진과 대체 사진 모두 PASS가 아님 | → REVIEW 또는 RETAKE | REVIEW (미해결, 사진 2장) |
| 대체 사진이 없음 | REVIEW 또는 RETAKE | REVIEW, `retake_unavailable` (사진 1장) |
| 정렬 실패, 배경에만 맞은 정렬, ROI가 화면 밖 | RETAKE와 그 이유 | 위 규칙을 따른다. C0에서는 ERROR |
| 파일 없음, 읽기 실패 | RETAKE (`missing_file`, `unreadable`) | 위 규칙을 따른다. C0에서는 ERROR |
| recipe나 plan이 잘못됨, anchor를 읽을 수 없음, 출력 폴더가 이미 있음 | — | 실행 전체를 중단하고 이유를 출력한다(종료 코드 2). 아무것도 덮어쓰지 않는다 |

품질 상태 PASS는 "검사할 수 있는 입력"이라는 뜻이다. 최종 상태 OK와 다르다.

## 5. 관찰 가능한 범위

- 2D 표면의 변화만 본다. 기준 사진과 달라진 곳을 찾는 것이고, 결함의 종류나 전기적 상태를 판정하지 않는다.
- 조명마다 참조 1장과 정상 보정 1장이 필요하다.
- 정렬이 받아들이는 자세 범위는 합성 시험으로 측정해 `docs/PHONE_REGISTRATION_RANGE.md`에 적는다.
- mm 분해능, lux, 실제 촬영 시간은 측정하지 않았다.

## 6. 품질 정책 v0.3 (수정안 1개)

**문제.** v0.2는 선명도를 밝기 제곱으로 나눠 anchor(L0)와 비교했다. 이 정규화는 어두운 사진에서 과보정된다(L1 2.9–3.1배, L2 3.6–3.8배).

**development 입력에서 확인한 근거.** 실제 사진에 같은 디지털 흐림(Gaussian σ = 1.0 계산용 px)을 가했다.

| 사진 | v0.2 비율 (기준 0.5) | 같은 조명 참조 대비 원래 Tenengrad 비율 |
| --- | --- | --- |
| L0 반복 3 + 흐림 | 0.24 → REVIEW | — |
| L1 반복 3 + 흐림 | 0.75 → **통과** | 0.26 |
| L1 반복 3 (흐림 없음) | 2.88 | 1.01 |

v0.2는 L0에서 잡는 흐림을 L1에서는 놓친다. 대체 조명으로 다시 찍은 사진이 흐려도 통과한다는 뜻이다.

**후보와 선택**

| 후보 | 판단 |
| --- | --- |
| A. v0.2 유지, 사용 범위만 설명 | 기각. 위 표의 구멍이 운영 경로(대체 사진)에 걸린다 |
| B. 밝기 지수를 다시 맞춤 | 기각. L1과 L2에서 필요한 지수가 다르다(약 0.5와 1.2). 조명 방향이 실제 gradient를 바꾸기 때문이다 |
| **C. 같은 조명의 참조와 비교** | **선택.** 정규화가 필요 없다. 검사가 이미 조명별 참조를 쓴다 |

**v0.3 규칙.** v0.2와 다른 점은 두 가지뿐이다.

- `sharpness_ratio` = 사진의 Tenengrad ÷ **그 사진이 찍혀야 할 조명의 참조** Tenengrad. 둘 다 warp 전 화소, 투영 ROI에서 계산한다. 0.5 미만이면 REVIEW(`low_sharpness_vs_same_light_reference`).
- `new_clip_high`, `new_clip_low`도 같은 조명의 참조와 비교한다.
- 첫 사진은 첫 조명(L0)의 참조와, 대체 사진은 대체 조명(L1)의 참조와 비교한다.
- 그 밖의 값(0.01, ROI 평균 Y 40, 자세 허용 범위, 정렬 검증)은 v0.2와 같다.
- 참조를 쓸 수 없으면 RETAKE(`reference_unavailable`)다.

**한계.**
- 저조도처럼 recipe에 없는 조명으로 찍힌 첫 사진은 L0 참조와 비교되므로 "어둡다"와 "선명도 낮음"이 함께 표시된다. 두 이유를 구분하지 못한다.
- 사람의 판독 기록이 없다. v0.1 / v0.2 / v0.3 중 어느 것이 사람 판단에 가까운지 순위를 매기지 않는다.
- 근거는 디지털 흐림이다. 실제 초점 흐림을 L1에서 찍은 사진은 없다.

**이 수정이 실패했다고 볼 조건.** 새 평가 세션에서 초점이 맞은 L1 사진이 `low_sharpness_vs_same_light_reference`로 보류되거나, 흐리게 찍은 대체 사진이 PASS가 되는 경우.

## 7. 고정 순서

1. 이 문서와 `docs/PHONE_EVAL_SESSION_PLAN_V1.md`를 commit한다.
2. 그 뒤에 v0.3을 구현하고 2026-11-15 development 세션에 다시 실행한다. 그 결과도 development 결과다.
3. 새 평가 세션에는 이 문서의 규칙과 임계값을 그대로 쓴다. 바꾸려면 새 버전으로 남긴다.
