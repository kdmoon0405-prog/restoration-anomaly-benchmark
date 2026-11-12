# PROGRESS — juhyung (GPU host)

이 파일은 주형 작업의 공개용 진행 기록이다. 최신 항목이 위에 온다. 각 반환에는 그 시점의 사본이 `PROGRESS.md`로 들어간다.
- 경로는 repository 기준 상대경로로 쓴다.
- 실행 모델/환경: 항목마다 적는다. 따로 적지 않은 2026-11-12 14:20 이전 항목은 Claude Opus 5.5 (`claude-opus-5-5`)다. 공통 환경은 Claude Code, Windows 11, GPU host `.venv` Python 3.11.2.
- 2026-11-12 이전 기록은 각 run의 RUN_RECORD/REPORT와 `handoff/returns/juhyung/*`에 있다.

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
