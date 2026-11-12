# 손지혁 오프라인 수신과 GPU 실행 재개

현재 ac931349ba0f3db795a5400534b3a79d2bdc4f44 checkout과 기존 CUDA 환경·사용자 변경을 보존하면서 실제 작업하라. 최종 전달물은 JIHYUK_OFFLINE_HANDOFF_20261111-v2.zip이다. 동봉 HANDOFF.json과 SHA256SUMS.txt로 파일·bundle의 digest를 검증한다. 동봉 README_OFFLINE.md부터 읽는다. Bundle은 public83ef04e를 prerequisite로 하며 handoff/jihyuk@61c2170을 포함한다. CPU의 새 수신 저장소에서17tests와 smoke2행을 확인했다.

1. README의 bundle verify/fetch와 별도 source-only worktree 명령을 실행한다. GitHub 접속이 없어도 이 단계는 가능하다. 최소61c2170 포함과 START_HERE.md·수신기·receipt·workflow·patch의 존재를 확인한다. 이미 받은813040630B MVTec ZIP을 재사용하고 receive_category_transfer.py로 새 data directory에 안전하게 설치한다. 이 수신이 archive/file hash를 검증하므로 같은 파일을 다시 반복 조사하지 않는다.

2. 실제 모델 실행은 초기화된 vendor code와 checkpoint가 있는 기존 feature checkout에서 진행한다. Source-only 전달 worktree는 입력 수신기·문서·CPU 계약을 제공한다. 네트워크가 필요한 새 submodule 초기화를 이 오프라인 단계의 실행 차단으로 만들지 않는다. 기존 ac source patch는 재적용하지 않는다. Portability patch는 apply --check 및 reverse --check로 적용 여부를 확인한다.

3. 이전 전달 문장의 clean/restored query 표현은 다음 실제 protocol로 정정한다.
- Bank는 clean, swinir_restored 두 종류다.
- Query는 bicubic_x4, swinir_x4 두 종류다.
- CPU consumer의 BANKS/QUERIES와 원본 BANK_DOMAIN_STUDY.md가 이 정의를 사용한다.

4. source provenance·ROI gap·다섯 파일 export 연결을 완료한다. 실행 측 analyzer 이름과 CPU consumer 이름을 구분한다. 관련 fake 테스트를 새 OS temp에서 실행한다. 테스트 fixture만 tiny checkpoint/metadata/RAM probe로 격리하고 production bank/geometry/checkpoint/memory guard는 유지한다.

5. Hazelnut seed11과 Screw seed11의4셀을 먼저 실제 실행해 반환한다. 같은 query RGB·split·calibration/test identity를 두 bank에 공유한다. fit/calibration에는 정상 train만 사용하고 각 cell의 robust/q0.99는 해당 정상 calibration에서 정한다. Test GT는 저장prediction 이후 평가에만 사용한다. 기존 all-patch IdentitySampler와 source protocol을 유지한다. Actual source commit,dirty,feature/code/checkpoint/query SHA와 memory/runtime 범위를 기록한다.

6. 성공한 category부터 seed23/37을 이어 총24조건을 완료한다. Sequential bank/model 처리와 기존 RAM/disk guard를 지킨다. 완료 artifact를 중복 실행하지 않는다. Partial/failed와 지원되는 resume 범위를 보존한다.

7. 이후 두 category의 seed11에서 Bicubic normal-fit bank를 추가하고 query bicubic_x4와 swinir_x4에 각각 평가한다. 신규4조건이다. 같은 seed11 clean-bank/bicubic-query baseline은 앞서 완료한 동일-protocol 저장 결과를 재사용한다. 동일 Bicubic query를 고정하고 clean-bank와 Bicubic-bank를 비교하는 것이 matched-domain 대조다. Query-clean을 새로 만들지 않는다. 기존4셀 계약은 유지하고 extension은 별도 family/schema로 내보낸다. 회복 여부만으로 정보 소실 원인을 확정하지 않는다.

8. GitHub443 문제는 짧게 병행 진단한다. 기본 Codex 실행 제한과 실제 OS 네트워크 문제를 구분하고, 도구가 지원하는 네트워크 허용 실행에서 read-only ls-remote를 확인한다. 공개 repo 존재와 CPU 쪽 접속은 확인됐다. Proxy를 기록할 때 credential은 가린다. 계속 차단돼도 오프라인 입력 설치·테스트·GPU queue를 진행한다. 공개 가능한 결과는 연결되면 handoff/jihyuk으로 push하고, 계속 차단되면 완료 CSV/JSON/보고서만 작은 private 반환물로 전달한다.

9. 설계·수정 과정은 outputs/private-decisions/jihyuk-20261111.private.md에 기록한다. git check-ignore와 git ls-files로 private 상태를 확인한다. 문제·관측근거·대안·선택이유·변경전후·남은 질문을 source/run-id와 함께 쓴다. 이 텍스트는 사용자에게 비공개 전달해 중앙 notes/RESEARCH_EVOLUTION_LOCAL.md에 통합한다. 공개 PROGRESS/RUN_RECORD에는 수행 사실과 결과를 기록한다.

현재 가능한 실행을 실제로 진행하고 category/seed가 끝날 때마다 반환한다. 같은 누락 자료의 반복 보고로 종료하지 않는다.

과거 결정은 당시 남긴 기록으로 확인 가능한 부분을 소급 정리한다. 당시 기록과 현재의 사후 해석을 구분하고 확인되지 않는 이유를 채워 넣지 않는다.


## 2026-11-12 수행·결정 기록 반환 보완

기존 고정 bank-domain24+4 실험을 설계담당자의 검토와 함께 계속 진행한다. Source·split·calibration·sampler 기준과 자원 guard는 기존 계약을 따른다. PROGRESS.md에 실제 수행·결과·실패·수정·검증을 기록하고,ignored/untracked private RESEARCH_EVOLUTION_LOCAL.md에 대안·근거·선택 이유·수정 전후·남은 질문을 기록한다.

각 완료단위 결과와 함께 공개 PROGRESS 및 비공개 결정 노트 증분/전체본을 각각의 경로로 반환한다. 대응 run-id/commit과 마지막 결정 ID를 알려 CPU의 중앙 비공개 노트에 통합할 수 있게 한다. 상세 계약과 작성 항목은 handoff/RECORDING_AND_RETURN.md를 따른다. 포스터 발표는12월1일이다.
