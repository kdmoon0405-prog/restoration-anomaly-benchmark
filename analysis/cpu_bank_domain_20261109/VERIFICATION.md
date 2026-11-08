# CPU bank-domain 검증 기록

2026-11-09. 원본 연구 checkout과 GPU 실행 source를 보존한 별도 branch의 CPU 연구다.

- 신규 조건 36개, 새 test prediction 4,860건 완료. 48조건 표 중 clean-bank 12개는 저장 anchor 재사용이다.
- Bank12개 fit, 고정 50:50 bank6개 구성. 모두 기존 selected patch ordinal과 용량4096을 유지했다.
- 전체 pytest: 643 passed, 1 skipped, 310.98s. 새 OS temp와 기존 Python 환경을 사용했다.
- 최종 analysis/export 관련 pytest: 6 passed, 5.25s. 기존 CPU smoke: 2행 통과.
- Generic reporting/혼합 bank 관련 19 passed 이전 검증도 보존했다. 초기 fixture 폴더 누락 2실패는 수정 후 통과했다.
- Numeric table6개, PNG2개와 master70행/5groups의 저장 hash를 검증했다. UTF-8/LF와 사용자 절대 경로 제외를 확인했다.
- Runtime에 기록된 source10개가 현재 bytes와 일치한다. 기존 HOG/evaluation/fusion/metrics/dataset5개는 b247500과 일치한다.
- 두 PNG를 이미지로 직접 확인했다. 첫 CI 제목의 reference를 명확히 바꿨고 첫 render/public package는 outputs의 비공개 원본으로 보존했다.
- 새 protocol/result/progress 문서의 숨은 문자 검사 결과는 각0건이다.

GT는 prediction 생성이 끝난 후 evaluation에서만 사용했다. 고정 fit에 조건부인 per-image CI를 pooled CI로 표시하지 않았다. Runtime source commit은 b247500, dirty=true이며 이 실행 상태를 나중의 공개 commit으로 바꾸지 않는다.

Dataset/RGB/GT/raw prediction/bank/checkpoint/개인 노트는 공개하지 않는다. 원격 GPU 실행이나 full PCB pilot을 검증·승인한 작업이 아니다. 수신 checkout 검사는 공개 후 원본 PROGRESS와 로컬 campaign 기록에 남긴다.
