# 주형에게 넘기는 bank-domain 실행과 사진 결과물 작업

2026-11-17 사용자 승인. 지혁이 담당하던 미완료 bank-domain 24+4 실행을 주형에게 넘긴다. 최종 목적은 열화된 입력에서 복원이 결함과 검사에 미치는 영향을 사진과 수치로 확인하는 것이다. 실시간 시연과 UNO 실물의 준비 상태에 관계없이 아래 소프트웨어·사진 결과물을 끝까지 완성한다. 기존 Fable 5.2 환경과 현재 작업을 이어가고 실제 사용 모델을 기록한다.

## 시작과 소스 보존

먼저 현재 branch/HEAD, 미반영 변경, 실행 중 worker, 이미 완료한 조건과 캐시를 확인한다. 지혁의 실행 산출물이 있으면 source·입력·split·checkpoint·query 계약을 대조해 재사용한다. 새 실행은 빠진 조건만 한다. 동시 worker의 파일을 덮어쓰거나 기존 실행을 임의로 종료하지 않는다.

현재 phone 실행 source는 7b868a3, 포스터 생성 source는 59db971, CPU 검토는 a350b07이다. 이 handoff branch는 지시·분석 전달 경로이며 실행 source와 같은 것으로 가정하지 않는다. 주형의 기존 실행 checkout을 보존하고 별도 bank 실행 branch/worktree에서 통합한다.

지혁 producer의 원본은 ac93134에서 만들어진 패치다. 그 commit 객체의 수신 여부에 의존하지 않고 아래 공개 파일을 이용한다.

- handoff/code/bank-domain-study-ac93134.patch
- handoff/code/jihyuk-fixture-portability.patch
- docs/BANK_DOMAIN_ANALYSIS_HANDOFF.md

두 패치는 origin/handoff/jihyuk@d8dcceb에서 바이트 그대로 복사했다. PATCH_SOURCES.json에 원본 ref·경로·SHA-256이 있다. 실제 적용 전에 patch의 base와 현재 코드를 확인한다.

주의할 충돌은 scripts/analyze_bank_domain_study.py다. phone 쪽에는 CPU 반환 분석기가 있고 producer 패치에도 같은 이름의 분석기가 있다. 두 구현의 진입점과 호출자를 읽고 CPU 분석 경로를 유지한다. 별도 실행 checkout에 producer를 적용하는 방법 등으로 해결하고 변경 범위를 기록한다. 소스 전용 worktree에는 vendor와 checkpoint가 자동 준비되지 않는다. 기존 초기화된 실행 환경·vendor·로컬 checkpoint를 재사용한다.

기존 runner의 주요 인자는 --data-root, --dataset-provenance, --category, --seed, --swinir-checkpoint, --backbone-checkpoint, --device, --output-root, --run-id다. 실제 --help와 코드에서 확인한다. 존재하지 않는 --assets-root 또는 --root 인자를 전제로 실행문을 만들지 않는다.

## 먼저 반환할 사진 결과

새 모델 학습 없이 기존 저장 결과와 선정 사례를 먼저 활용한다. RGB가 저장되지 않았다면 기존에 고정한 소수 사례만 동일 checkpoint·열화 설정으로 처리해 RGB를 내보낸다. 예전 전체 실험을 다시 돌리는 이유로 삼지 않는다.

- 개선, 결함 억제, 형상 변화, 변화가 작은 사례를 기존 분류에서 정한다. 해당 종류가 없는 경우 없다고 기록한다. 보기 좋은 사진만 골라 전체 결과를 대표시키지 않는다.
- 같은 결함 좌표의 원본 RGB, 열화 입력, Bicubic, SwinIR을 같은 crop·크기로 배치한다. crop 좌표와 확대 배율, dataset/image ID, 실제 source·checkpoint·열화 조건을 보존한다.
- 대응 GT와 clean/Bicubic/SwinIR 검사 지도를 넣는다. 같은 사례 안에서는 같은 색 범위와 표시 기준을 사용한다. 원본부터 존재한 작은 결함을 복원 결과에서 직접 확인할 수 있는 확대 패널을 만든다.
- 실제 스마트폰 사진은 기준/L0/L1, 저조도와 대체 조명, 모사 이물의 확대 그림을 만든다. artificial x4 복원 비교와 실제 촬영 조건을 각각 명시한다. 사람이 붙인 위치 상자를 검증된 결함 GT로 표기하지 않는다.
- bank 비교 그림에서는 동일 query RGB와 같은 좌표를 유지하고 bank만 바꾼다. query 복원을 함께 바꾼 표는 별도 대조로 표시한다.

사진 묶음은 image ID·crop·조건을 담은 인덱스와 열리는 HTML 갤러리, 고해상도 PNG로 반환한다. 보고서의 그림 번호와 연결하고 실제 브라우저·포스터 확대 상태를 열어 확인한다. 첫 사진 묶음을 만든 뒤 아래 bank 실행을 이어간다.

## 실제 PatchCore bank-domain 실험

기존 CPU HOG/kNN 실험은 별도 대조 결과다. 실제 PatchCore GPU 반환 24개 기본 조건과 4개 확장 조건을 완성한다.

기본 조건은 category 2개(hazelnut/screw), seed 3개(11/23/37), normal bank 2종(clean/swinir_restored), query 2종(bicubic_x4/swinir_x4)의 곱이다. 먼저 두 category의 seed 11에서 4조건씩 완성하고, seed 23/37, 확장 조건 순서로 진행한다.

확장은 category 2개 × seed 11 × bicubic normal bank × query 2종의 4조건이다. 같은 protocol의 기존 seed 11 clean-bank/bicubic-query 기준은 재사용한다. query-clean arm을 추가하지 않는다.

고정 계약을 유지한다.

- fit/calibration은 normal train에서만 분리한다. hazelnut 391장을 313 fit/78 cal, screw 320장을 256 fit/64 cal로 사용한다. PCB의 180장 calibration을 가져오지 않는다.
- bank 사이에 query 순서·RGB/hash·test identity·split을 맞춘다. 모든 patch를 사용하는 IdentitySampler, WRN50-2 layer2/layer3, 224 center canonical 입력, embedding 1024차원, 이미지당 784 patch, CPU exact FAISS를 보존한다.
- bank 수와 patch 선택 계약을 맞추고 cell별 normal calibration median/IQR와 q0.99를 기록한다. test GT로 bank, threshold, 운영 crop 또는 방법을 선택하지 않는다. 결과 설명용 확대 crop은 사후 시각화로 명시한다.
- pinned PatchCore/backbone/SwinIR 체크포인트와 dataset provenance를 기록한다. 기존 데이터·캐시를 우선 사용한다. 자산 경로는 실제 환경에서 찾고 해시를 대조한다.
- 기존 RAM 계획(3×bank+chunk+2 GiB), disk/map lifecycle, bank 순차 실행을 유지한다. 메모리 제한에 걸리면 실제 부족량과 다음 가능한 단위를 반환한다. guard를 낮춰 완료 처리하지 않는다.

Primary는 pooled AU-PRO@0.3이다. image/pixel AUROC, per-image AU-PRO, ROI-background gap과 화질 지표를 함께 내보낸다. pooled point와 paired per-image mean bootstrap CI를 구분한다. seed별로 같은 test 이미지가 반복되므로 독립 표본으로 더하지 않는다.

## 반환 계약과 구현 확인

다섯 파일 export와 실제 source_provenance, ROI-background gap 연결을 먼저 확인한다. 누락되면 기존 코드를 재사용해 연결하고 관련 작은 회귀검사를 수행한다. 원본 producer 패치가 최신 CPU 반환 계약까지 구현했다고 가정하지 않는다.

필수 파일은 bank_domain_manifest.json, config.json, provenance.json, summary.csv, per_image.csv다. Manifest의 kind는 bank_domain_study_results, schema_version은 1이다. COMPLETE/PARTIAL/FAILED/PREFLIGHT_PASS 상태와 model_predictions/synthetic_fixture 증거 종류를 정확히 기록한다. 나머지 네 파일의 bytes/SHA-256, source/checkpoint/input/split/test/query/bank hash, fit/cal disjoint 여부와 test-GT 선택 미사용을 연결한다.

첫 완료 단위부터 반환한다. 미완료 condition은 빈 성능 수치로 채우지 않는다. 확장 4조건은 기본 24조건과 분리된 family로 기록한다. 기존 CPU consumer가 읽을 수 있는지 테스트하고 신규 export가 기존 consumer/legacy callers를 깨지 않게 한다.

원본 사진, RGB/GT, raw map, dataset, bank, checkpoint, 사진이 들어간 HTML/PPTX/PDF, 실제 private 결정 원문은 공개 Git에 올리지 않는다. 코드와 허용된 scalar metadata만 공개하고 사진·private 산출물은 비공개 파일로 직접 반환한다. 이전 완료 결과를 중복 반환한 경우 같은 해시임을 명시한다.

## 현재 보고서·포스터 수정

docs/PHONE_FINAL_CPU_FEEDBACK_20261117.md와 docs/PHOTO_RESULT_GOAL_REVIEW_20261117.md를 반영한다.

pooled/평균 AU-PRO, family별 seed, 중심 보정/화면 이동 원근 결과, 147/423초의 혼재 조건을 정정한다. HTML banner는 저장 결과에서 다시 렌더하거나 사본의 문구만 정정한다. 팀 정보는 확인된 값만 넣고 제출 전 미확정 항목을 담당자가 확정하도록 반환 요약 첫 부분에 적는다.

새 32장 촬영은 사람이 실제로 진행해야 한다. 촬영 전에 참조·보정·평가 역할을 분리하고 사람 판독표와 시간 기록을 준비한다. L1 흐림을 점검하려면 흐림 2 cycle 중 하나의 대체 L1도 흐리게 찍도록 계획을 먼저 버전 관리한다. 현재 개발 사진을 새 평가 세션으로 다시 이름 붙이지 않는다.

## 마감과 완료 기준

A0 PDF는 2026-12-01 23:59 KST까지 제출한다. 실제 발표일은 미확인이다. 핵심 실험 11월23일, 포스터 초안 27일, 최종 검토 29일을 목표로 한다.

먼저 사진 결과와 bank 실험을 마무리한다. 가이드의 ANN 검색 변경, 자동 drift calibration, 조명 피드백 보드, XY scanner는 별도 채택 시 구현할 확장안으로 남긴다. 실물 장비의 부재로 현재 사진·보고서 작업을 중단하지 않는다.

각 완료 단위에서 source/모델·입력·실행 범위·숫자·그림·한계를 PROGRESS에 기록하고, 근거가 있는 결정·수정·남은 질문을 실제 private 노트에 추가한다. 공개 진행 사본만으로 private 노트 반환을 완료 처리하지 않는다. 자체 검토는 사용 모델과 검토 범위를 적고 실제로 고친 뒤 마지막 diff와 산출물을 다시 확인한다.

최종 반환에는 사진 갤러리와 PNG, 24+4 결과 및 누락 조건표, 수정 보고서와 A0 PPTX/PDF, 재현 가능한 실행 기록, 실제 private 노트를 넣는다. 새 촬영·사람 판독·실물 검증이 남으면 각각 남았다고 적는다. 계획서나 그림 후보 목록에서 멈추지 않고 현재 환경에서 실행 가능한 결과물을 완성한다.
