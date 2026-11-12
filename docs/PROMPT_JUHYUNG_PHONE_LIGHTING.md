# 촬영 도구 구현 세부계약

최신 실행 순서와 일정은 handoff/NEXT_TASK.md 및 docs/PHONE_LIGHTING_POSTER_PLAN_20261112.md를 따른다. 이 문서는 구현 세부계약이다.

현재 저장소에서 설계 검토와 구현을 이어서 수행한다. 12월 초 최종 산출물을 목표로 하며, 새 장비 구매 없이 스마트폰과 책상 조명·사용 가능한 플래시로 촬영한다. 실제 part 수량과 결함 여부는 아직 확인 전이다. 본 지시는 촬영 전 소프트웨어 준비와 기존 저장 결과 대조를 승인한다. 새 사진을 가정한 성능 수치는 만들지 않는다.

## 먼저 확인할 완료 상태

기존 40unit×5집계 규칙은 200cell 완료됐고 CPU에서 scalar와 불확실성을 검토 중이다. 9사례 PNG3장과 private 결정 기록도 CPU에 도착했다. 해당 작업을 반복하지 않는다. 지혁은 bank-domain 실행을 맡고 CPU는 반환 분석·master 통합을 맡는다. 기존 연구 source·원본·bank·protocol·개인 변경은 보존한다.

기준 문서는 docs/PHONE_LIGHTING_PILOT_DRAFT.md다. Source 위치가 handoff와 다르면 공개 feature branch의 정확한 commit을 기록하고, 실행·문서 전달 경로를 정리한다.

## A. 독립 설계 검토와 범위 선택

현재 실행 환경에서 실제 사용할 모델명을 기록한다. Fable5.2를 사용할 수 있으면 설계 검토에 사용하되 기존 결과 CSV·source와 대조한다. 다음 후보를 필요한 입력, 개발량, 12월 초 시연 가능성, 검증 가능한 주장으로 비교한다.

- 단일 영상의 조명 보정과 입력 품질 관리
- 여러 조명 영상의 정렬·반응 변화 분석과 고정 recipe 선택
- Photometric stereo 확장

주력 하나와 최소 baseline을 선택하고, 선택 근거·반례·성공 기준·남은 질문을 문서화한다. 사용자가 추가 구매를 원하지 않는 조건을 유지한다. 일정상 구현 가능한 범위에서 계속 진행한다. 다른 담당자의 bank-domain source와 CPU consumer를 동시에 재작성하지 않는다.

## B. 촬영 전 CPU 소프트웨어 구현

phone_* 별도 모듈과 스크립트로 입력 manifest, EXIF/파일 hash, part/session/recipe/repeat 식별자와 동일 실물 grouping을 구현한다. 사소한 카메라 기울기와 조명 변화를 분리해 기록한다. 입력 누락·해상도 차이·잘못된 ID·동일 파일 중복을 검출한다.

기존 OpenCV/NumPy/이미지 입출력을 재사용해 고정 ROI의 품질 지표와 정렬 상태를 산출한다. 과노출·암부·gradient 선명도·정렬 잔차의 정의와 단위를 코드 작성 전에 명시한다. 합성 입력으로 밝기, clipping, blur, shift, 정상 종료와 실패 상태를 테스트한다. Synthetic 결과에는 그 출처를 표시한다.

작은 로컬 결과 화면/리포트는 기존 viewer와 제어 계약을 먼저 검토해 확장한다. 원본/보정 영상, 품질 overlay, recipe, 판정/REVIEW, 재촬영 이력, CSV를 연결한다. RGB와 누락 map의 상태를 정확히 표시한다. 화면이 있으면 실제 브라우저에서 열어 스크린샷을 확인한다. 타이머의 software replay와 실물 지연을 구분한다.

실제 사진이 없어도 코드·synthetic E2E·촬영 안내·반환 schema까지 마친다. WAITING 하나만 남기며 종료하지 않는다.

## C. 기존 저장 자료로 가능한 대조

Clean(non-x4) Hazelnut/Screw 원본 score/map의 존재와 bank·split·geometry 연결을 한 번 확인한다. 일치하는 저장 자료가 있으면 기존 v0.1을 보존하고 clean aggregation control을 별도 v0.2 scope로 먼저 고정해 같은 다섯 규칙을 평가한다. 원래 결과와 family가 다르면 그 차이를 유지해 보고한다. 자료가 없으면 재추론을 자동 추가하지 않고 B의 독립 구현을 마친다.

CPU가 제공하는 새 통계와 주형의 원인 가설을 대조한다. 점수 집계와 bank/query domain 차이, 조명 조건의 영향을 분리한 주장–근거 표 초안을 작성한다. Matched-bank 미회복만으로 정보 소실을 확정하지 않는다.

## D. 사진 도착 이후의 실행 계약

첫 입력은 같은 기판 세 조명×세 반복의 9장이다. 고정 카메라/부품에서 조명을 변경한다. 기울기는 별도 축이다. 추가 자료가 오면 동일 part/session을 기준으로 development와 평가를 구분한다. 확인된 실제 결함과 모사 결함을 구별한다.

실물용 bank/calibration과 알고리즘 비교 후보를 development에서 고정한다. 정상/결함 입력이 충분한 범위에서 오검·미검·재촬영·REVIEW를 모두 포함해 평가한다. 촬영이 부족한 경우 동일 물체 반복성 실험의 결과와 한계를 완성한다. 실측 전 성능·처리량·높이 계측값을 채우지 않는다.

## E. 전달과 마무리

작업을 기능 단위로 commit하고 targeted CPU 테스트·smoke·diff 검사를 수행한다. 공개 코드·schema·익명 수치/문서는 feature branch와 handoff/juhyung으로 전달한다. RGB/GT 그림·raw 배열·실제 private 결정 기록은 기존 비공개 경로를 유지한다. Protocol·source commit·완료 범위·재현 명령을 반환한다.

Private 결정 기록에는 실제로 확인한 문제, 검토한 대안, 선택 이유, 측정 근거, 수정 전후와 남은 질문을 기록한다. 당시 기록과 사후 해석을 구분하고 ignored/untracked인지 확인한다. 이 파일은 사용자에게 비공개로 보내 중앙 notes/RESEARCH_EVOLUTION_LOCAL.md에 통합할 수 있게 한다.
