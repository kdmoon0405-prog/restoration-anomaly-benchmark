# 현업 대응 설계 한 페이지 — 정지 촬영형 수동 입력 스테이션 (2026-11-15)

- **작성 모델:** Claude Fable 5.2 (`claude-fable-5-2`, Claude Code).
- **읽은 문맥:** 이전 Opus 5.5 초안 v0, Fable 5.2 초안 v1과 재검토, CPU의 `docs/INDUSTRIAL_CAPTURE_COMPARISON_20261113.md`. 독립 설계가 아니다.
- **구현 대상:** 정지된 기판을 고정 카메라로 찍는 수동 입력 스테이션. 추가 구매는 없다.
- 평가 기준과 수식은 `docs/DESIGN_DECISION_PHONE_V0.2.md`에 고정한다.

## 현장 요소와 이번 구현의 대응

| 현장 요소 (업체 공개 자료) | 이번 구현 | 구현 상태 |
| --- | --- | --- |
| 품목별 recipe (촬영 위치, FOV, 광원, 허용 범위) | `recipe.json`: part/view, anchor 사진, 관찰 ROI, 계산용 크기와 보간, 카메라·조명 기록, 자세 허용 범위, 정책 버전 | 구현 |
| 위치 맞춤 (fiducial, 기구 고정) | anchor 사진에 homography 정렬. 관찰 ROI 안의 inlier와 투영 coverage로 검증 | 구현 (소프트웨어 정렬만. 기구 고정 없음) |
| 다단·다방향 조명 | 책상 조명 2조건: L0 기준, L1 왼쪽 낮은 측면 | 구현 (수동 이동. 조명 재현 오차 있음) |
| 촬영 trigger (전기 신호, encoder, strobe) | 사람이 셔터를 누른다. 소프트웨어 이벤트로 cycle을 구분한다 | **미구현.** simulation 시간만 있다 |
| 입력 품질 확인과 재촬영 | 품질 정책 → 사전 지정한 대체 조명으로 최대 1회 재촬영 | 구현 (재촬영은 이미 찍어 둔 사진으로 replay) |
| 검사 (2D/3D AOI) | 정렬 후 기준 사진과의 차이를 보는 2D golden-reference baseline | 구현 (2D 표면만. 높이·체적·숨은 접합부는 범위 밖) |
| 판정과 배출 (PLC, actuator) | 기존 `InspectionStation` fake controller의 OK/NG/REVIEW/ERROR | simulation |
| 추적성 (cycle 이력) | cycle별 원본 SHA, recipe, 정책 버전, 촬영 수, 최종 상태 CSV | 구현 |
| false call / escape 관리 | 확인된 라벨이 있는 범위에서만 분모와 함께 보고 | 모사 이물 1종, 1위치뿐 |

## 측정하지 않은 것

- mm 분해능(pixel/mm), 조도(lux), 물리 trigger 지연, 실제 작업 시간. 모두 미측정이다.
- 공장별 허용 미검 수준과 takt. 미확인이므로 공통 합격 숫자를 만들지 않는다.
- 전기적 정상/불량. 미확인이다.

## 비교 조건 (CPU 문서의 C0–C3)

| 조건 | 촬영 | 처리 |
| --- | --- | --- |
| C0 | L0 1장 | 직접 검사 |
| C1 | 같은 L0 1장 | ×4 축소 후 고정 복원(SwinIR) → 같은 검사. 대조로 Bicubic 복원도 둔다 |
| C2 | L0 1장, 필요하면 L1 1장 | 품질 정책(v0.1 / v0.2) → 조건부 재촬영 → 검사 |
| C3 | L0와 L1 항상 2장 | 조명별 검사 후 결합 |

## UNO 상태 표시 (문서 초안만)

보유 UNO의 내장 LED로 READY(꺼짐), 재촬영 요청(느린 점멸), REVIEW(빠른 점멸)를 표시하는 안이다. 기존 `InspectionStation` 상태를 그대로 쓴다. 연결 가능 여부와 실제 구동은 미확인이고, 기본 실험과 포스터를 늦추지 않기 위해 이번에는 구현하지 않는다.
