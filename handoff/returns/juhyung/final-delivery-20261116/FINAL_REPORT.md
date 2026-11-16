# 최종 보고서 — 스마트폰 기반 PCB 외관검사 시제품과 기존 SR/PatchCore 연구 정리

- **작성:** Claude Fable 5.2 (`claude-fable-5-2`, Claude Code), 2026-11-15 ~ 11-16.
- **지시:** `PROMPT_FABLE_FINAL.md` (비공개 전달 묶음, SHA-256 `5e01dc1c…8a58`).
- **상태:** 받은 입력(사진 24장, 예시 6장)으로 할 수 있는 범위는 완료했다. 새 평가 촬영, 사람 판독, UNO 실물은 외부 입력을 기다린다(§9).
- 경로는 모두 GPU checkout(`restoration-anomaly-benchmark`) 기준 상대경로다.
- **모델 전환 기록:** 2026-11-16 12:10 KST 이후의 마무리 작업(PROGRESS·비공개 노트 반영, `RUN_RECORD.md`, `RECEIPT.json`, 반환 묶음 작성, commit/push)은 사용자 요청에 따라 **Claude Opus 5.5 (`claude-opus-5-5`)**가 수행했다. 설계, 구현, 실행, 그림, 포스터, 이 문서들의 본문은 Fable 5.2가 작성했다.

## 1. 목적

1. ×4 초해상도 복원이 PatchCore 이상 탐지에 주는 효과와 실패 조건을 정리한다(기존 결과 재사용).
2. 생산라인의 고정 촬영 recipe와 검사 흐름을 본뜬 스마트폰 검사 시제품을 만든다. 입력 폴더와 촬영 기록을 넣으면 정렬, 품질 판단, 검사, 조건부 대체 입력, 최종 판정과 이력까지 이어진다.
3. 촬영·처리 조건 C0–C3를 같은 사례에서 비교한다.

## 2. 최종 설계

설계 문서는 `exp/phone-lighting-juhyung`의 `docs/`에 있다.

| 문서 | 내용 |
| --- | --- |
| `INDUSTRIAL_STATION_DESIGN_20261115.md` | 현장 요소와 구현의 대응 1쪽 |
| `DESIGN_DECISION_PHONE_V0.2.md` | recipe, 정렬 검증, 품질 정책 v0.2, golden-reference 검사, C0–C3 규칙 |
| `DESIGN_DECISION_PHONE_V0.3.md` | 최종 운영 경로, 상태 전이, 실패 시 동작, 품질 정책 v0.3 |
| `PHONE_REGISTRATION_RANGE.md` | 정렬이 받아들이는 자세 범위(합성 측정) |
| `PHONE_EVAL_SESSION_PLAN_V1.md` | 새 평가 촬영 계획과 기록표 |

**운영 경로 (조건 `C2_policy_v0.3`)**

1. 입력 확인: 기록표, 파일, SHA-256, 중복.
2. 정렬: anchor 사진에 homography. 관찰 영역 안의 inlier와 투영 coverage로 검증.
3. 입력 품질(v0.3): 관찰 영역 안에서 같은 조명의 참조 사진과 비교한다. PASS / REVIEW / RETAKE.
4. 검사: 같은 조명의 참조와의 국소 정규화 차이. 차이 덩어리가 25 px 이상이면 NG.
5. 첫 사진이 PASS가 아니면 대체 조명(L1) 사진을 1회 요청한다. cycle당 사진은 최대 2장이다.
6. 최종 OK / NG / REVIEW / ERROR와 이유, 사진 수를 CSV와 HTML에 남긴다.

**이번에 정한 것**

- **품질 정책 v0.3 (수정안 1개):** v0.2의 밝기 정규화 선명도는 같은 흐림을 L0에서는 잡고(비율 0.24) L1에서는 놓쳤다(0.75, 기준 0.5). 같은 조명의 참조와 비교하면 0.26으로 잡힌다. 근거는 실제 사진에 디지털 흐림을 가한 development 확인이다. v0.1과 v0.2는 그대로 보존했다.
- **원근 전용 임계값은 추가하지 않았다.** 합성 측정에서 기존 자세 허용 범위가 10° 이상의 기울기를 REVIEW로 보냈다.
- **사람 판독 기록이 없으므로** v0.1 / v0.2 / v0.3 중 어느 정책이 더 정확한지 순위를 매기지 않았다.

## 3. 구현

| 구성 | 파일 (`exp/phone-lighting-juhyung@7b868a3`) |
| --- | --- |
| 입력표, EXIF, 품질 지표, 정렬 | `src/sr_anomaly/phone_capture.py` |
| recipe, 정렬 검증, 정책 v0.2 / v0.3, 검사, 기록표 → 실행 계획 | `src/sr_anomaly/phone_station.py` |
| 실행 진입점 (운영 경로 + 비교군 + 보고서) | `scripts/run_phone_station_compare.py` |
| v0.1 audit | `scripts/run_phone_capture_audit.py` |
| 정렬 범위 측정 | `scripts/characterize_phone_registration.py` |
| UNO 상태 표시 (fake serial) | `src/sr_anomaly/phone_uno.py`, `scripts/replay_phone_station_uno.py`, `docs/examples/phone_station_status_led/` |
| 기존 제어 계약 (재사용) | `src/sr_anomaly/inspection_station.py` |

- **실패 처리:** 정렬 실패, 관찰 영역 소실, 누락 파일, 대체 입력 없음은 cycle의 최종 상태와 이유로 남는다. recipe나 실행 계획이 잘못됐거나 출력 폴더가 이미 있으면 아무것도 쓰지 않고 종료 코드 2로 멈춘다.
- **덮어쓰기 방지:** 출력은 새 폴더에만 쓴다. 입력 폴더는 읽기만 한다(테스트에서 바이트 비교로 확인).
- **검사:** 전체 테스트 696 passed, 4 skipped (`6748c95`). 그 뒤 시간 기록만 바꾼 `7b868a3`에서 관련 테스트와 CPU smoke를 다시 돌렸다. 결과는 `RUN_RECORD.md`와 `logs/`에 있다.

## 4. 실험의 구분

| 구분 | 입력 | 성격 |
| --- | --- | --- |
| 기존 benchmark | MVTec AD Hazelnut·Screw, VisA PCB. 예측 조건 165개, 13 protocol group | 완료된 결과의 재사용. 새 추론 없음 |
| 집계 대조 | 저장 map 40 unit × 5 규칙, clean control 15 cell | 같은 예측의 재평가 |
| 실물 development 세션 | 그래픽카드 뒷면 1개, 사진 24장 (2026-11-15) | 방법을 이 세션을 본 뒤 정했다. 독립 평가가 아니다 |
| 예시 6장 | 자세·배율·부분 시야가 섞인 사진 | 정렬 거절 동작 확인용 |
| 합성 시험 | 기판 무늬 합성 영상 | 구현과 정렬 범위 확인. 실물 성능이 아니다 |
| 새 평가 세션 | 계획만 고정 | **미수신** |

## 5. 기존 SR/PatchCore 결과 (포스터 패널 ①)

| 주장 | 수치 | 출처 |
| --- | --- | --- |
| 평균은 좋아져도 영상별로는 나빠진다 | Hazelnut pooled AU-PRO: Bicubic 0.819 → SwinIR 0.843. 이상 70장 중 30장 저하 (suppression 14, geometry candidate 16) | master `historical_recovery`, `analysis/hazelnut/cross_category_summary.json` |
| LR에 노이즈가 있으면 순위가 바뀐다 | SwinIR − Bicubic, σ15: Hazelnut −0.046 / −0.077 / −0.079, Screw −0.037 / −0.044 / −0.046 (v1 / seed 23 / seed 37). RealESRGAN − SwinIR은 모두 양수 | `handoff/returns/juhyung/realistic-noise-v2-*` |
| ×4 뒤 Screw의 이미지 판정이 무너진다 | image AUROC clean 0.984 → Bicubic 0.480 / SwinIR 0.679. AU-PRO 0.957 → 0.801 / 0.856 | `image-score-aggregation-clean-control-20261112` |
| 집계 규칙으로 회복되지 않는다 | ×4에서 5개 규칙 모두 0.43–0.68. clean은 0.983–0.984 | 같은 반환, `image-score-aggregation-20261111-*` |
| PCB 전체 기판 | image AUROC clean 0.971 / Bicubic 0.968 / SwinIR 0.954, AU-PRO 0.952 / 0.939 / 0.944 | master `pcb_native_full_cohort_v0_6` |

- Screw σ5는 방향이 확정되지 않았다.
- 세 노이즈 값은 같은 영상을 노이즈만 다시 뽑아 잰 것이다. bank/split seed는 11 하나다.
- ×4가 map을 바꾸는 원인은 미확정이다. 지혁의 bank-domain 24+4 결과는 아직 도착하지 않았다.

## 6. 실물 development 세션 결과

실행: `outputs/phone-station-20261116-final` (source `7b868a3`, clean). 사본은 `station_run/`에 있다. 이전 실행(`5839caa`, `6748c95`)과 기존 여섯 조건의 판정·점수·사진 수가 모두 같다(96행 일치).

### 6.1 입력 품질 (사진 24장)

| 정책 | PASS | REVIEW | RETAKE |
| --- | --- | --- | --- |
| v0.1, 화면 전체 | 3 | 3 | 18 |
| v0.1, 관찰 영역 | 3 | 6 | 15 |
| v0.2 (anchor 대비) | 15 | 9 | 0 |
| v0.3 (같은 조명 참조 대비) | 15 | 9 | 0 |

- v0.2와 v0.3의 REVIEW 9장은 저조도 3, 초점 흐림 3, 기울임 3이다.
- 정렬은 24장 모두 성공했다. 재투영 오차 중앙값 0.46–0.75 계산용 px.
- 사람의 판독 기록이 없다. 과잉 거부·과잉 허용 비율은 NA다.

### 6.2 조건 비교 — 전체 16 cycle (모든 최초 cycle이 분모)

| 조건 | OK | NG | REVIEW | NA | 사진 사용 수 | 모사 이물 3건 중 NG | 정상 13건 중 NG |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C0 직접 검사 | 11 | 5 | 0 | 0 | 16 | 3 | 2 |
| C3 항상 두 조명 | 3 | 4 | 0 | 9 | 14 | 3 | 1 |
| C2 v0.3 (운영 경로) | 6 | 4 | 6 | 0 | 19 | 3 | 1 |
| C2 v0.2 | 6 | 4 | 6 | 0 | 19 | 3 | 1 |
| C2 v0.1 (관찰 영역) | 4 | 0 | 12 | 0 | 23 | 0 (3건 REVIEW) | 0 |
| C1 Bicubic ×4 | 13 | 3 | 0 | 0 | 16 | 3 | 0 |
| C1 SwinIR ×4 | 13 | 3 | 0 | 0 | 16 | 3 | 0 |

- C3의 NA 9건은 흐림·흰 배경·기울임 cycle에 두 번째 조명 사진이 없어서다. 그래서 C3의 정상 NG 1건은 판정이 나온 정상 4건 중 1건이다.
- "사진 사용 수"는 저장된 사진의 논리적 사용 횟수다. 재촬영을 실제로 한 것이 아니라 미리 찍은 사진을 재생했다.

### 6.3 같은 사례로 맞춘 비교 (CPU 검토의 사후 진단 묶음)

| 묶음 | 조건 | OK | NG | 사진 사용 수 | 정상 라벨 NG | 모사 이물 NG |
| --- | --- | --- | --- | --- | --- | --- |
| 두 조명 사진이 있는 7 cycle | C0 | 3 | 4 | 7 | 1 / 4 | 3 / 3 |
| | C3 | 3 | 4 | 14 | 1 / 4 | 3 / 3 |
| | C2 v0.3 | 4 | 3 | 10 | 0 / 4 | 3 / 3 |
| 참조·보정 재사용 2건을 뺀 5 cycle | C3 | 1 | 4 | 10 | 1 / 2 | 3 / 3 |
| | C2 v0.3 | 2 | 3 | 6 | 0 / 2 | 3 / 3 |

- 7건과 5건은 방법 선택에 쓰지 않은 사후 진단이다. 한 보드·한 세션의 반복이고, 5건에도 `normal-3`과 `lowlight-3`이 같은 대체 사진을 공유한다.
- C2 v0.3의 수치는 v0.2와 같다(CPU 검토의 `cohort_summary.csv`와 일치).

### 6.4 C1 (×4 왕복 뒤 검사)

- Bicubic과 SwinIR의 최종 판정은 16 cycle 모두 같다.
- 정상 NG가 0건인 것은 왕복이 차이 지도를 평활해서다. 이물 점수도 165 → 117–130으로 함께 낮아졌다. SwinIR 고유의 이득은 확인되지 않았다.
- `phone_x4_roundtrip`은 계산용 영상을 ×0.25로 줄였다가 ×4로 되돌린 조건이고, 참조·보정 사진에도 같은 처리를 했다. 기존 benchmark의 ×4 조건과 합치지 않는다.

### 6.5 예시 6장과 정렬 범위

- 예시 6장: 기준 후보(6번) 외 5장은 정렬 임계값 미달로 RETAKE다. 보정 완료로 처리하지 않았다.
- 합성 측정(`docs/PHONE_REGISTRATION_RANGE.md`): 평면 회전 5°, 배율 ±10 %, 이동 20 %, 기울기 5°까지 그대로 검사한다. 기울기 10–30°는 정렬은 되지만 REVIEW, 40° 이상은 RETAKE다.

## 7. 시간

| 항목 | 값 | 조건 |
| --- | --- | --- |
| 소프트웨어 전체 (24장, 6조건, 보고서) | 147 s | `5839caa`, 전원 연결 |
| 소프트웨어 전체 (24장, 7조건, 보고서) | 423 s | `7b868a3`, **배터리 동작** (CPU 제한) |
| ├ 읽기·축소 | 46 s (장당 1.9 s) | 〃 |
| ├ 정렬 + 품질 | 229 s (장당 9.5 s) | 〃 |
| ├ 검사 (비교군 전체) | 83 s | 〃 |
| ├ 복원 Bicubic / SwinIR | 6 s / 19 s | 〃, GPU MX570 A |
| └ 보고서 그림 | 23 s | 〃 |
| 스테이션 재생 | simulation_seconds | 물리 시간이 아니다 |
| 실제 촬영·준비 시간 | **미측정** | 참고: 파일 이름의 촬영 시각으로는 조명 3조건 × 3회 9장이 63초 사이에 찍혔다. 통제된 측정이 아니다 |

같은 PC에서도 전원 상태에 따라 3배 가까이 달라졌다. 이 값으로 장비 처리량을 계산하지 않는다.

## 8. 그림과 포스터

- `poster_final.pptx` (편집형, 공식 양식 3번 구성), `poster_final.pdf`, `poster_figures/` (그림 7개와 `figure_sources.json`).
- 그림은 저장된 CSV/JSON과 비공개 사진에서 `poster_work/make_figures.py`로 그렸다. 사진 그림의 점수는 저장된 `inspections.csv`와 같은지 스크립트에서 확인한다.
- **포스터에 남은 확인 항목:** 팀 번호(`Team No_??`), 저자·지도교수, 소속·연구실. 확인된 자료가 없어 자리만 잡아 두었다. 제목도 확정이 필요하다.
- 포스터에는 실제 사진이 들어 있으므로 비공개 검토 산출물이다.

## 9. 실제로 남은 항목 (외부 입력 대기)

| 항목 | 필요한 것 | 준비된 것 |
| --- | --- | --- |
| 독립 평가 | 새 촬영 세션 32장 (`docs/PHONE_EVAL_SESSION_PLAN_V1.md`) | 계획, 기록표 양식, 실행 명령 |
| 품질 정책의 정확도 | 사람 판독표 (사진별 잘 보임 / 판독 어려움 / 불확실) | 양식 `docs/phone_human_legibility_template.csv` |
| 실제 촬영 시간 | 기록표의 `capture_seconds` | 기록 칸과 보고 경로 |
| UNO 상태 표시 | UNO 연결, pyserial 설치 | fake serial 경로, 스케치, 연결 가이드 |
| bank-domain 근거 | 지혁의 24+4 반환 | — |
| 포스터 확정 정보 | 팀 번호, 저자, 소속, 제목 | 자리 표시 |

## 10. 한계

- 보드 1개, 세션 1개, 모사 이물 1종 1위치의 반복 3회다. 공장의 오탐률·미검률·처리량을 추정하지 않는다.
- 조명당 정상 보정 사진은 1장이다. 검사 임계값의 통계적 근거가 약하고, 정상 오검 2건의 점수(28, 30)는 한계 25 바로 위다.
- v0.3의 근거는 디지털 흐림이다. L1에서 실제로 흐리게 찍은 사진은 없다.
- 2D 표면 변화만 본다. 전기적 상태, 높이·체적, mm 분해능, lux는 측정하지 않았다.
