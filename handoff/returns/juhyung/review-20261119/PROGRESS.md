# PROGRESS — juhyung (GPU host)

이 파일은 주형 작업의 공개용 진행 기록이다. 최신 항목이 위에 온다. 각 반환에는 그 시점의 사본이 `PROGRESS.md`로 들어간다.
- 경로는 repository 기준 상대경로로 쓴다.
- 실행 모델/환경: 항목마다 적는다. 따로 적지 않은 2026-11-12 14:20 이전 항목은 Claude Opus 5.5 (`claude-opus-5-5`)다. 공통 환경은 Claude Code, Windows 11, GPU host `.venv` Python 3.11.2.
- 2026-11-12 이전 기록은 각 run의 RUN_RECORD/REPORT와 `handoff/returns/juhyung/*`에 있다.

## 2026-11-19 00:20 – 01:45 KST · 새 촬영 50장 평가, 전체 검토(Fable 대기), 갤러리·보고서·포스터 갱신

- **실행 모델:** Claude Opus 5.5 (`claude-opus-5-5`). 요청 모델 Fable 5.2는 실제 연결이 확인되지 않아 Fable 의존 검토는 대기다.
- **새 촬영 세션(2026-11-18, 50장, 계획 v2) — 고정 방법 v0.3:**
  - 기본 14 cycle은 OK 4 / NG 6 / REVIEW 4. 정상 평가 4/4 OK, 큰 이물 6/6 NG(위치 일치).
  - 작은 이물 9 cycle은 NG 2 / REVIEW 7.
  - L1 사진 25장이 L0 기준에 정렬되지 않아 대체 조명과 C3(23/23 ERROR)가 동작하지 않았다.
- **개발 변형(같은 조명 참조 정렬, 결과를 본 뒤 정함):** 정렬 16/49 → 41/49. 기본 OK 7 / NG 6 / REVIEW 1, 작은 이물 NG 9.
  - 가장 큰 덩어리가 물체에 있는 경우는 3/9다.
  - CLAHE 대안은 13/49로 기각했다.
  - 다음 세션에서 다시 평가해야 한다.
- **PCB 운영점:** 저장 점수로 TP/FP를 재현했다. Bicubic → SwinIR에서 이상 25장이 검출→미검, 8장이 미검→검출이다.
- **정정:** 기준선 0.984는 정상 320장 bank의 참고값이다. Hazelnut은 방향·크기 불확실이다. 교차 확인은 seed 11 원본 bank 4셀이다.
- **코드:** `exp/phone-lighting-juhyung@3e1a9c6`, `@f73bab4`. phone 관련 시험 19 passed.
- **남은 입력:** 사진-행 대응 확인, 사람 판독표, 촬영 시간, 이물 정보, 팀 정보, 지혁의 Bicubic bank 지도·기존 24조건, Fable 재검토.

## 2026-11-17 16:40 – 22:30 KST · 사진 결과, 정상 bank 비교, 포스터 갱신 — 받은 입력 범위 COMPLETE, 사람 입력 대기

- **실행 모델:** Claude Opus 5.5 (`claude-opus-5-5`, Claude Code). 지시가 요청한 Fable 5.2가 아니다.
- **지시:** 비공개 `PROMPT_JUHYUNG_END_TO_END_20261117.md`, 이어서 추가 수신 `juhyung-bank-results-followup-private-20261117`(지혁 24+4 완료 보고, 중복 실행 대신 회수·통합).
- **코드 (공개 branch):**
  - `exp/bank-domain-juhyung`: `b94a189`(지혁 패치 2개), `2796dc6`/`45c9a65`(CPU consumer 5파일 export), `c60dd80`(Bicubic bank 확장 runner, 미실행).
  - `exp/phone-lighting-juhyung`: `87c78ed`(촬영 계획 v2), `3632df1`(같은 위치 확대 그림), `10ca115`(HTML 첫 줄 v0.3, bank 지도 그림), `9aa54cd`/`b3dc3c7`/`74dc9fa`(결과 갤러리, 선정 사례 그림).
- **실행:**
  - 기본 bank run 3개 COMPLETE(Hazelnut seed 11/23, Screw seed 11, MX570 A). Screw seed 23은 세션 종료로 정지했고, 추가 지시에 따라 재개하지 않았다.
  - 지혁 seed 11 원본 bank 셀과 대조: Bicubic 입력 화질 비트 일치, pooled 차이 ≤0.0004.
- **결과 (Screw ×4, seed 11):** image AUROC는 원본 bank 0.481(Bicubic) / 0.672(SwinIR), SwinIR 복원 bank·SwinIR 입력 0.916, Bicubic bank·Bicubic 입력 0.934(지혁 수신), Bicubic bank·SwinIR 입력 0.726(지혁 수신).
  - 영상별 AU-PRO(SwinIR bank − 원본 bank, SwinIR 입력): Screw +0.076 [95% CI 0.057, 0.097], Hazelnut seed 11/23 모두 CI가 0을 포함한다.
  - 기전과 일반화는 주장하지 않는다.
- **검증:** bank producer 11 passed, CPU consumer 24 passed, phone station/capture 19 passed. 전체 pytest는 다시 돌리지 않았다.
- **정정:** pooled AU-PRO 용어, family별 seed, 원근 2종, 147/423/633 s 조건, HTML 첫 줄.
- **남은 사람 입력:** 새 평가 촬영 50장과 판독표·촬영 시간, 지혁 원래 24조건 반환과 Bicubic bank 지도, 포스터 팀 정보, UNO.

## 2026-11-15 21:30 – 11-16 12:10 KST · 최종 시제품, 시연, 보고서, A0 포스터 검토본 — 받은 입력 범위 COMPLETE

- **실행 모델:** Claude Fable 5.2 (`claude-fable-5-2`, Claude Code). 이전 Opus/Fable 문서와 CPU 검토(`handoff/juhyung@8ddde87`, `492aa6a`)를 읽은 상태다.
- **지시:** 비공개 묶음의 `PROMPT_FABLE_FINAL.md`. 받은 파일 6개의 SHA-256이 `INPUT_RECEIPT.json`과 일치했다.
- **이전 기록 보완:** 반환 `7b2c894` 이후 `exp/phone-lighting-juhyung@5839caa`에서 CPU smoke를 실행했고 통과했다(2 result rows). 그때의 로그 파일은 저장하지 않았다. 최종 commit `7b868a3`에서 다시 실행해 로그를 남겼다.
- **설계 고정 (구현 전):** `a031195` — `docs/DESIGN_DECISION_PHONE_V0.3.md`, `docs/PHONE_EVAL_SESSION_PLAN_V1.md`, 기록표·판독표 양식.
- **구현:** `6748c95`, `7b868a3`
  - 품질 정책 v0.3: 선명도와 새 포화를 같은 조명의 참조와 비교한다. v0.1, v0.2는 보존했다.
  - 운영 경로 `C2_policy_v0.3`의 cycle별 결과표(`station_result.csv`)와 결과 화면 상단 표.
  - 기록표의 `station_role` / `cycle_id` / `light` 열에서 실행 계획을 만든다. 참조·보정 사진의 재사용은 거부한다.
  - recipe·계획·출력 폴더 문제는 아무것도 쓰지 않고 종료 코드 2로 멈춘다.
  - 정렬 범위 합성 측정(원근 포함)과 `docs/PHONE_REGISTRATION_RANGE.md`.
  - UNO 상태 표시의 fake serial 경로, 스케치, 재생 CLI.
- **검증:**
  - 전체 pytest `6748c95`: 696 passed, 4 skipped (793.8 s).
  - `7b868a3`: phone 관련 테스트 49 passed (339 s), CPU smoke passed(2 result rows).
  - 로그는 run-id `final-delivery-20261115`의 `logs/`에 있다.
- **실측 결과 (development 세션 24장, run `phone-station-20261116-final`, `7b868a3`):**
  - 기존 여섯 조건의 판정·점수·사진 수가 `5839caa` 실행과 96행 모두 같다.
  - 정책 v0.3: PASS 15 / REVIEW 9 / RETAKE 0. v0.2와 같다.
  - 운영 경로 16 cycle: OK 6, NG 4, REVIEW 6, 사진 사용 19회. 모사 이물 3/3 NG, 정상 NG 1/13.
  - 두 조명 사진이 있는 7 cycle: C2 v0.3 사진 10회, C3 14회. CPU 재집계와 같다.
  - 소프트웨어 시간: 전원 연결 147 s(`5839caa`, 6조건), 배터리 동작 423 s(`7b868a3`, 7조건). 실제 촬영 시간은 미측정이다.
- **v0.3의 근거 (development):** 실제 사진에 같은 디지털 흐림을 가하면 v0.2 비율이 L0에서 0.24, L1에서 0.75(통과)다. 같은 조명 참조 대비는 0.26이다.
- **정렬 범위 (합성):** 회전 5°, 배율 ±10 %, 이동 20 %, 기울기 5°까지 수용. 기울기 10–30°는 REVIEW, 40° 이상은 RETAKE.
- **산출물:** `outputs/final-delivery-20261115/` — FINAL_REPORT, FINAL_REVIEW, DEMO_GUIDE, RUN_RECORD, RECEIPT, 포스터 PPTX/PDF와 그림 7개, 실행 결과 사본. 사진이 든 파일은 비공개다.
- **자체 검토:** 같은 모델의 자체 검토다. 찾은 문제 10건과 조치는 FINAL_REVIEW에 있다.
- **미측정/미수신:** 새 평가 세션, 사람 판독, 실제 촬영 시간, UNO 실물, 지혁의 bank-domain 결과, 포스터의 팀 번호·저자·소속.
- **모델 전환:** 2026-11-16 12:10 KST 이후 기록 반영, RUN_RECORD/RECEIPT 작성, 반환은 사용자 요청에 따라 Claude Opus 5.5가 했다.
- **다음:** 새 촬영 32장과 판독표가 오면 고정된 계획으로 한 번 실행하고 보고서와 포스터를 갱신한다.

## 2026-11-15 15:46–16:40 KST · 현업 촬영 recipe와 재촬영 검사 시연 (실제 사진, development 세션) — COMPLETE (받은 입력 범위)

- **실행 모델:** Claude Fable 5.2 (`claude-fable-5-2`). 이전 Opus/Fable 초안과 CPU 비교군 문서를 읽은 상태다.
- **지시:** `docs/PROMPT_JUHYUNG_INDUSTRIAL_CAPTURE_20261113.md` (`handoff/juhyung@e76d28f`).
- **입력 (비공개):**
  - 사용자가 2026-11-15에 찍은 그래픽카드 뒷면 24장(JPEG). 조건은 L0/L1/L2 × 3회, 초점 흐림 3, 모사 이물 6(L0 3, L1 3), 흰 배경 3, 기울임 3이다.
  - CPU가 보낸 예시 6장(PNG). `INPUT_RECEIPT.json`의 SHA-256 6개가 모두 일치했다.
  - AE/AF 잠금, HDR, 사람의 판독 기록은 unknown이다.
- **수행 순서:**
  1. v0.1 audit를 24장에 1회 실행했다(`aa2f7fa`).
  2. 설계를 고정했다(`e00eca6`, 16:18): `docs/INDUSTRIAL_STATION_DESIGN_20261115.md`, `docs/DESIGN_DECISION_PHONE_V0.2.md`.
  3. 구현과 합성 테스트를 했다(`5839caa`): `src/sr_anomaly/phone_station.py`, `scripts/run_phone_station_compare.py`, `tests/test_phone_station.py`.
  4. 실제 사진에 C0–C3 비교를 실행했다(`5839caa`, 16:29–16:31). run-id `phone-station-dev-20261115`.
- **사전 수정 1건:** 합성 테스트에서 처음 고정한 검사 판정 규칙이 정상 반복 10장 중 6장을 NG로 냈다. 실제 사진에 검사를 돌리기 전에 τ = 2 × q0.999, 최소 넓이 25 px로 바꾸고 문서에 기록했다.
- **검증:** 새 합성 테스트 7개 pass. 전체 suite 692 pass / 4 skip. 결과 화면은 Edge headless로 데스크톱 화면을 확인했다.
- **실측 결과 (모두 development 결과):**
  - 정렬: 24장 모두 성공. 조명이 달라도 재투영 오차 중앙값 0.46–0.75 px.
  - v0.1(화면 전체): PASS 3 / REVIEW 3 / RETAKE 18. L0의 포화는 책상 배경에서 났다.
  - 같은 ROI에서 v0.1: PASS 3 / REVIEW 6 / RETAKE 15. v0.2: PASS 15 / REVIEW 9 / RETAKE 0.
  - 16 cycle 비교: 모사 이물 3 cycle은 C0, C1(Bicubic, SwinIR), C2 v0.2, C3에서 3/3 NG이고 위치도 일치했다. C2 v0.1은 3 cycle 모두 검사에 도달하지 못했다(REVIEW).
  - 정상 기판의 오검: C0 2/13(저조도 1, 흰 배경 1), C1 0/13, C2 v0.2 1/13, C3 1/4.
  - 촬영 수: C0 16, C2 v0.1 23, C2 v0.2 19, C3 14(대체 조명 사진이 없는 9 cycle은 NA).
  - 예시 6장: 기준 후보 6번 외 5장은 정렬 검증을 통과하지 못해 RETAKE다.
- **미측정/NA:** 사람의 판독 기록이 없어 품질 정책의 과잉 거부·과잉 허용 비율은 NA다. mm, lux, 실제 촬영 시간, 전기적 상태는 미측정이다.
- **한계:** 이물 1종 1위치의 반복 3회, held-out 정상 1 cycle, 조명당 정상 calibration 1장이다. 탐지 성능으로 쓰지 않는다. 방법은 이 세션의 v0.1 audit를 본 뒤 정했으므로 독립 평가가 아니다.
- **다음:** 고정된 방법으로 새 촬영 세션을 평가한다. 사람의 판독 기록을 받는다. 포스터 원고 초안(`POSTER_DRAFT_JUHYUNG_20261115.md`)을 양식에 옮긴다.
- **차단 항목:** 평가용 새 촬영 세션 없음. 공식 A0 양식 미수신. 지혁의 bank-domain 결과 미도착. UNO 연결 미확인(문서 초안만).

## 2026-11-12 · Fable 5.2 재검토와 재현 확인 — COMPLETE

- **실행 모델:** Claude Fable 5.2 (`claude-fable-5-2`). 같은 날 앞선 항목들은 설정 실수로 Opus 5.5가 수행했고, 사용자가 모델을 바꿔 재실행을 요청했다.
- **다시 작성:** `docs/DESIGN_DRAFT_FABLE52_20261112_v1.md`, `docs/DESIGN_REVIEW_FABLE52_20261112.md` (`exp/phone-lighting-juhyung@aa2f7fa`).
  - 초안 v1은 기존 초안과 근거가 문맥에 있어 독립 초안이 아니다.
  - 기존 초안 v0과 검토는 보존했다.
- **주장 수정:** C1을 noise 입력으로 좁혔다. C2의 "localization 유지" 표현을 AU-PRO 저하 수치로 바꿨다. C3은 실제 사진이 오기 전에는 포스터 주장으로 쓰지 않는다.
- **구현 수정 (실제 사진을 보기 전):**
  - 품질 지표를 warp하지 않은 화소에서 계산한다. 실측 근거: 0.25–0.5 px 보간만으로 선명도 0.79–0.73×, noise 0.45–0.29×. 임계값은 그대로다.
  - 촬영 안내서에 JPEG 설정을 넣었다. 이 환경은 HEIC/RAW를 읽지 못한다.
- **검증:**
  - phone 테스트 7 pass, station 테스트 17 pass. 전체 suite는 이 수정 뒤 다시 돌리지 않았다.
  - synthetic 시연 재실행 run-id `fable52-rereview-20261112`: 16/16 기대 상태, 이전 실행과 판정 변화 없음.
  - v0.2 clean control 재현: `summary.csv`가 바이트 단위로 동일하다. 새 결과로 집계하지 않는다.
- **미검증:** 조명 방향이 다를 때 금속 반사면의 정렬 성공 여부. 모바일 화면.
- **다음:** 사진 9장(JPEG) 도착 시 audit 1회.

## 2026-11-12 13:41–14:20 KST · 스마트폰 촬영 품질/정렬 도구 (사진 없이 가능한 범위) — COMPLETE

- **Protocol:** `docs/PHONE_QUALITY_PROTOCOL_V0.1.md`를 `e6462ef`에서 코드 작성 전에 고정했다. 수식, 단위, 임계값(clip 1 %, luma [40,215], sharpness 0.5×, 정렬 inlier 30 / 0.25 / 1.5 px, 이동 2 % / 1° / 2 %)이 들어 있다.
  - 실제 사진을 보기 전에 한 번 수정했다. noise 추정을 Immerkær로 바꿨다. PyWavelets가 설치되어 있지 않아서다. 이 지표는 보고만 하고 임계값은 없다.
- **코드:** `exp/phone-lighting-juhyung@a8eb190`, `b756110`
  - `src/sr_anomaly/phone_capture.py`
  - `scripts/run_phone_capture_audit.py`
  - `scripts/make_phone_synthetic_set.py`
  - 촬영 안내 `docs/PHONE_CAPTURE_GUIDE_20261112.md`와 기록표 양식
- **환경:** OpenCV가 없어서 scikit-image/SciPy/PIL로 구현했다. 새 설치는 없다.
- **재사용:** 기존 `InspectionStation` 계약으로 software replay를 한다. 탐지기가 연결되지 않았으므로 판정은 항상 REVIEW다.
- **검증:**
  - 새 테스트 6개 pass, branch 전체 684 pass / 4 skip
  - synthetic E2E run-id `phone-synthetic-demo-20261112`: 16/16 행이 기대 상태
  - Edge headless로 데스크톱 화면을 확인했다. 모바일 레이아웃은 미검증이다.
- **실측/추정 구분:** 모든 수치는 synthetic이다. 실제 촬영, 물리 지연, lux는 없다.
- **다음:** 사진 9장이 도착하면 audit를 한 번 실행한다.
- **차단 항목:** 사진 미도착. 실물 결함 수량 미확인. 지혁의 bank-domain 결과 미도착.

## 2026-11-12 13:37–13:38 KST · 집계 v0.2 clean control — COMPLETE

- **목적:** v0.1에서 ×4 이후 Screw 이미지 판정 저하가 5개 집계 규칙 모두에서 나타났다. 같은 규칙을 clean(×4 없음) 저장 예측에 적용해 비교한다.
- **Scope:** `docs/IMAGE_SCORE_AGGREGATION_V0.2_CLEAN_CONTROL.md`를 `exp/image-score-aggregation-juhyung@ba2d4de`에서 비교 전에 고정했다.
  - 입력: `outputs/legacy-patchcore/screw-full320-test160`, family `historical_recovery`, seed 11, train-320 bank, calibration 없음
  - 3 unit × 5 규칙 = 15 cell
- **실행:**
  - source `f66eb67` (clean)
  - run-id `image-score-aggregation-clean-control-20261112`
  - 명령: `run_image_score_aggregation_clean_control.py --data-root <GPU checkout> --output outputs/image-score-aggregation-clean-control-20261112 --reference-test-csv outputs/realistic-degradation/screw-v1/units/none__swinir_x4.csv`
- **검증:**
  - anchor A(원본 AUROC)와 B(pixel AUROC payload)가 3/3 모두 정확히 일치했다.
  - test 160장의 순서와 라벨이 realistic Screw와 같다.
  - guard plan은 286 MiB(계획값)이고 통과했다.
  - 테스트: 해당 파일 12 pass.
- **실측 결과 (image AUROC):**
  - clean: 규칙 전체 0.983–0.984
  - Bicubic: 0.435–0.480
  - SwinIR: 0.583–0.679
  - ×4에서는 모든 규칙이 원본 점수보다 낮거나 같다.
  - F1/FPR/미검률은 calibration이 없어 정의되지 않는다.
- **해석 범위:** 이 family에서는 clean과 ×4의 차이가 규칙 선택과 무관하게 나타난다. ×4가 map을 바꾸는 원인은 미확정이다.
- **다음:** phone 도구 구현.

## 2026-11-12 13:31–13:35 KST · 독립 초안과 설계 검토 — COMPLETE

- **초안:** `docs/INDEPENDENT_DRAFT_JUHYUNG_20261112_v0.md` (SHA-256 `efd6a608…6e06`)
  - 근거 문서와 phone 문서를 읽기 전에 저장했다.
  - 실제 모델은 Claude Opus 5.5이고 Fable 5.2가 아니다.
- **검토:** `docs/DESIGN_REVIEW_JUHYUNG_20261112.md`, `exp/phone-lighting-juhyung@bc62f06`
  - master 165/8/13, taxonomy 30/14/16/40, PCB 지표, 집계와 noise 수치를 실제 CSV/JSON에서 검산했다. 모두 일치했다.
  - 위험 지점 5개를 점검했다.
  - 핵심 주장 C1–C3과, 주력 구현(phone 품질/정렬 도구) 및 baseline(품질 정책 없음)을 고정했다.
- **환경 확인:** venv에 OpenCV가 없다. scikit-image 0.26이 있어서 정렬과 품질 계산은 skimage/NumPy/PIL로 한다. 새 설치는 없다.
