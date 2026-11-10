# 담당자별 전달과 결과 반환

공개 저장소의 handoff/juhyung과 handoff/jihyuk을 각각 한 사람의 전달 창구로 사용한다. 두 브랜치의 공통 분석 기반은 7d5c177b67f1476c4f6ad98937cc2bcac38a93af다. 담당자는 handoff/START_HERE.md에서 본인 입력과 실행 source를 확인한다. 실행 source와 분석 source의 commit은 따로 기록한다.

## 자료 구분

Git에는 코드, 테스트, 실행 지시, 공개 가능한 JSON/CSV/보고서와 파일 해시를 저장한다. Dataset RGB/GT, checkpoint, bank, raw prediction, RGB/GT 그림, private note는 기존 비공개 저장 위치에 보존한다. 브랜치는 공개 범위를 분리하지 않는다. Raw 배열이 필요한 분석에는 기존 비공개 전달 또는 보유 호스트에서 실행한 파생 결과를 이용한다.

## 작업 수신

기존 GPU worker가 실행 중인 checkout은 유지한다. 아래 명령은 기존 GPU repository root에서 수행한다. Source 전용 worktree는 데이터, 환경, 가중치를 포함하지 않으므로 원래 위치를 명시적으로 사용한다. GitHub 접속이 차단된 호스트는 기존 offline bundle 전달 경로를 유지한다.

```powershell
git fetch origin
git show origin/handoff/juhyung:handoff/START_HERE.md
# 지혁은 origin/handoff/jihyuk의 같은 파일을 읽는다.
```

## 결과 반환

담당자는 본인 브랜치에만 push한다. 변경한 실행 코드는 기존 feature branch에 보존하고 그 commit을 보고서에 기록한다. 반환 브랜치에는 고유 run-id 아래의 공개 가능한 텍스트 결과를 추가한다. 완료, partial, failed 상태를 그대로 기록한다. 단계가 끝날 때마다 반환할 수 있다.

본인의 깨끗한 전달 worktree에서 아래 도구를 사용한다. --source는 실제 완료 output directory로 지정한다. --include는 존재하는 공개 결과만 명시한다. 아래 예는 결과 파일 이름이 summary.csv와 REPORT.md인 경우다.

```powershell
& $py scripts/prepare_team_return.py --owner juhyung --run-id $runId --source $completedOutput --include summary.csv REPORT.md
git add -- "handoff/returns/juhyung/$runId"
git diff --cached --stat
git diff --cached --check
git diff --cached
git commit -m "Return completed analysis metadata"
git push origin HEAD:handoff/juhyung
```

지혁은 owner와 경로 및 push 대상 모두 jihyuk으로 지정한다. $py는 보존한 기존 환경의 Python 절대 경로다. $runId와 $completedOutput은 실제 실행에서 기록된 값이다. 기존 반환 경로는 덮어쓰지 않는다. 도구는 명시한 UTF-8 텍스트를 byte 그대로 복사하고 RECEIPT.json에 해시를 기록한다. 이는 CPU 검토가 끝났다는 판정과 구분된다. Sender는 staged diff에서 개인 정보, credential, private note의 포함 여부를 직접 확인한다.

Push가 non-fast-forward로 거부되면 원격 새 commit을 먼저 확인한다. Force push와 사용자 변경 삭제는 사용하지 않는다. 두 사람이 같은 브랜치를 동시에 수정하지 않도록 CPU 담당자는 전달 갱신 전에 remote tip을 확인한다.

## CPU 검토

```powershell
git fetch origin
git log --oneline origin/handoff/juhyung -5
git log --oneline origin/handoff/jihyuk -5
git ls-tree -r --name-only origin/handoff/juhyung handoff/returns/
git ls-tree -r --name-only origin/handoff/jihyuk handoff/returns/
```

CPU 담당자는 새 receipt의 파일 해시와 source 연결부터 확인하고 family별 기존 분석기에 연결한다. 같은 반환을 중복 실험으로 세지 않는다. Pooled AU-PRO와 per-image 평균을 구분하고, 미수신 raw array의 검증 범위를 따로 남긴다.

현재 독립 CPU queue는 완료됐고, 실제 9사례 공간 분석은 가용 RAM 기준을 충족할 때 진행한다. 다음 연구 통합은 두 담당자의 새 저장 결과를 대상으로 한다. 실물 검사 장치 작업은 별도의 부품과 I/O 사양을 확보한 뒤 진행한다.
