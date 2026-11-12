# Fable 설계·전체 근거 검토·실험을 이어가는 작업

2026-11-12 지시. 포스터 발표일은12월1일로 확정됐다. 목표는 관련 실험을 무한히 늘리는 것이 아니라,검증된 연구 결과와 보유 스마트폰의 실물 촬영 도구를11월말까지 완성하는 것이다. 사용자 추가 구매 예산은0원이다. 기존 작업·bank·데이터·결과와 사용자 변경을 보존한다.

상위 연구 질문은 복원 화질과 이상 탐지의 관계,그리고 촬영 조건 관리가 검사 결과에 미치는 영향을 검증하는 것이다.

## 진행 원칙과 기록

기준이 고정된 실험·구현은 Fable 설계 검토와 함께 계속 진행한다. 설계 전체가 끝날 때까지 기존 queue를 대기시키지 않는다. 새로운 방법의 첫 test 비교 전에는 그 실험의 질문·대조군·분할·지표·선택 기준을 짧게 고정한다. 자원 guard 안에서 승인된 범위의 선택과 실행을 자율적으로 이어간다.

handoff/RECORDING_AND_RETURN.md를 따른다. PROGRESS.md에는 수행 사실·결과·실패·검증·다음 작업을,비공개 RESEARCH_EVOLUTION_LOCAL.md에는 대안·근거·선택 이유·수정 전후·남은 질문을 기록한다. 완료단위 결과와 함께 두 기록도 각각 공개/비공개 경로로 반환한다.

## 1. Fable5.2 독립 초안

실제 사용 모델명을 기록한다. 먼저 상위 연구 질문,12월1일 마감,스마트폰/책상 조명/플래시·추가구매0원 조건을 바탕으로 독립 설계 초안을 작성한다. 입력조건,필요한 실물,algorithm후보,최소baseline,측정할값,실패조건,최종화면과 마감까지의 범위를 정한다. 짧은 초안을 저장하고 다음 단계로 진행한다. 전체 연구의 과거 결론을 먼저 모방하는 방식으로 작성하지 않는다.

## 2. 기존 연구 전체를 근거와 대조

docs/FABLE_RESEARCH_EVIDENCE_REVIEW_20261112.md를 읽고 필요한 실제 CSV·JSON·code를 확인한다. Master165조건/8families/13protocol groups,고정taxonomy,PCB native/geometry·resource,실사형56+noise32,readout200cell,CPU/GPU controls를 검토한다. 기존negative gating/full110 B/B-uncertain과 공개 정정도 유지한다.

선택사례의 인과해석,같은영상반복의 표본수,프로토콜 혼합,normalcalibration/testGT와 raw 미수신 범위를 점검한다. 독립 초안과 전체 근거 검토 후 설계의 수정 전후·이유를 기록한다. 핵심 주장2~3개,주력 구현 하나와 baseline을 고정해 새 방법의 평가를 시작한다. 기존 기준의 실험과 독립 구현은 검토 중에도 계속한다. 이 승인된 범위 안의 구현 선택은 자율적으로 진행한다.

## 3. 사진 없이 완료할 구현

기존 docs/PROMPT_JUHYUNG_PHONE_LIGHTING.md의 A/B와 최신 docs/PHONE_LIGHTING_POSTER_PLAN_20261112.md를 따른다. phone_* 별도영역에 manifest/EXIF/hash·part/session/recipe grouping,정렬·ROI·품질지표,리포트/CSV와 기존viewer 연결을 구현한다. 지표 수식·단위·threshold의 결정 데이터를 먼저 명시한다.

Synthetic 밝기/clipping/blur/shift와 누락입력·정렬실패·재촬영/REVIEW·중복 파일을 테스트한다. 폴더 입력부터 실제 실행 가능한 결과 화면을 만들고 브라우저에서 확인한다. Synthetic과 software replay를 실제 촬영·물리 latency와 구분한다. 사진 대기 중에도 이 단계와 포스터 근거 정리를 완료한다.

## 4. 저장 자료 대조와 사진 연결

기존 source와 맞는 stored clean map control이 있으면 별도scope를 먼저 고정해 같은집계규칙을 적용할 수 있다. 기존40unit/200cell은 반복하지 않는다. 지혁은 bank-domain24+4와 producer를 맡고 CPU는 master/통계 consumer를 맡는다. 두 담당자의 같은 script를 재작성하지 않는다.

첫 사진은 기판 부위 또는 보유USB-A커넥터의3조명×3반복9장이다. 실제 수량·결함상태는 아직 미확인이다. 사진이 도착하면 품질/정렬 audit를 한 번 수행하고 고정된 방법으로 진행한다. 실제 정상/결함과 part/session 분리를 고려해 탐지평가 가능 범위를 정한다. 입력이 부족하면 동일물체의 조명변화·반복성까지 완성한다. Test결과로 방법·threshold·checkpoint를 재선택하지 않는다.

## 5. Poster와 시연 묶음

기존 결과의 핵심그림,효과크기·반복·한계 표,source연결,실물/소프트웨어 화면,짧은 재현 명령과 시연 영상을 준비한다. 확정된 poster template/규격이 없으면 편집 가능한 본문·그림 원고를 먼저 만든다. 새 연구 수치를 만들거나 미도착 실험을 완료로 집계하지 않는다. 11월23일까지 핵심실험을 정리하고11월27일poster초안을 완성한다.

## 6. 전달과 기록

설계·근거 검토와 함께 기준이 고정된 실험·코드·테스트·그림·발표 원고의 유한한 queue를 계속 진행한다. 짧은 작업은 category/session 단위,긴 작업은 검증 가능한 완료단위로 반환한다. Source/환경/입력/protocol/결과·재현 명령을 연결한다. 기존 메모리 guard와 실제 측정·추정·미측정의 구분을 유지한다.

Code·공개 schema/수치·문서는 feature branch와 handoff/juhyung으로 전달한다. RGB/GT/raw array·실제 private 결정 기록은 기존 비공개 범위를 유지한다. Private 기록에는 근거가 있는 대안·선택 이유·수정 사항·남은 질문을 남기고 당시 기록과 사후 해석을 구분한다. Git ignored/untracked 확인 후 사용자에게 비공개로 반환한다.

각 완료단위의 반환에 공개 PROGRESS와 비공개 결정 노트의 갱신도 포함한다. 세부 작성·반환 계약은 handoff/RECORDING_AND_RETURN.md다.


## CPU 후속 검토 완료 (2026-11-12)

5794b2d까지4반환/34파일과clean-control15cell을CPU에서검산했다. Phone source aa2f7fa의24tests가로컬에서도통과했고synthetic E2E 보고서를브라우저에서열어데스크톱/모바일PNG로확인했다. 세부범위·한계는 handoff/cpu_reviews/20261112/REVIEW.md를따른다. 기존작업을반복하지않는다.

다음작은UI수정은본문이모바일viewport에맞도록하고긴표에만가로scroll을두는것이다. 현재390px화면은안내문/표가잘린다. 대표원본/품질overlay와짧은요약을첫화면에서볼수있는구성도검토한다. Desktop시연/실사진수신과병행할수있으며CPU가phone실행source를수정하지않았다. 실제사진은최신JPEG가이드로받는다.

Fable재검토초안은기존문맥을본상태였다는원격기록을그대로유지한다. 새private결정원문은아직CPU에미수신이다. 다음완료단위에서공개PROGRESS와비공개결정노트의갱신도반환한다.
