# Noise 반복 분석과 두 담당자 후속 전달

CPU 결과는 analysis/noise_repeatability_20261111/REVIEW.md와 master/에 있다. 주형의4run32조건을80개 공개 파일 receipt로 확인했다. 관련27tests와 CPU smoke2행을 통과했다. 새 그림은 직접 열어 pooled point와 per-image CI,70/119의 고유 영상 수를 확인했다. 기존133개 entry를 보존하며 master165행/13groups를 생성했다.

## 재현

아래 명령은 research_code/outputs/noise-return-review-20261111의 source worktree에서 실행한다. 기존 Python 환경을 명시적으로 재사용한다. 별도 반환 worktree에는 공개 텍스트가 있으며 dataset과raw prediction은 이 분석의 입력이 아니다.

```powershell
$py = (Resolve-Path '../../.venv/Scripts/python.exe').Path
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
git fetch origin refs/heads/handoff/juhyung:refs/remotes/origin/handoff/juhyung refs/heads/exp/realistic-noise-v2-juhyung:refs/remotes/origin/exp/realistic-noise-v2-juhyung
$received = Join-Path (Split-Path (Get-Location).Path -Parent) "noise-return-$tag"
git worktree add --detach $received ba4672ddb29bf0a5252ae4ee05253db70048dba0
& $py scripts/analyze_noise_repeatability.py --runs "$received/handoff/returns/juhyung" --references analysis/noise_repeatability_20261111/references --output "outputs/noise-replay-$tag"
& $py scripts/build_research_master_table.py --catalog configs/research_reporting_noise_20261111.json --output "outputs/noise-master-$tag"
$taskTemp = Join-Path ([IO.Path]::GetTempPath()) ('noise-review-' + [guid]::NewGuid().ToString('N'))
& $py -m pytest -q tests/test_noise_repeatability.py tests/test_research_delivery_reporting.py tests/test_pcb_spatial_return_review.py --basetemp $taskTemp
& $py scripts/smoke_test.py
git diff --check
```

## 경로 공개 사본

Hazelnut 두 원본 protocol의 v1_bank_dir가 사용자 절대경로였다. public_protocols/의 사본에서 이 필드만 repository 상대경로로 바꿨다. protocol_exports.json은 공급된 파일의 hash, unit들이 참조한 실행 protocol hash, 새 공개 사본 hash를 구분한다. 다른 JSON 값은 동일하다. 향후 배포에는 이 공개 사본을 참조하고, 실제 resume와 실행 provenance에는 원래 보관한 원본을 사용한다. 이미 push된 경로는 Git 이력에 남는다.

## 담당자 전달

docs/followup_20261111/의 PROMPT_JUHYUNG.md, PROMPT_JIHYUK.md, PROMPT_CPU.md를 각 역할에 전달한다. 주형은 완료32조건을 바탕으로 저장 map의 image-score aggregation을 비교하고, 지혁은 이미 받은 dataset과 오프라인 코드를 이용해 bank-domain24+4를 진행한다.

지혁용 private 전달물은 원본 research_code/outputs/JIHYUK_OFFLINE_HANDOFF_20261111-v2.zip이다. 동봉 HANDOFF.json과 SHA256SUMS.txt가 실제 공개 tip과 각 파일의 digest를 기록한다. Bundle의 prerequisite는83ef04e6a55f12f7d7cb6d6bfd69bebab98793d9, tip은61c2170dec726e76be4a4dbd488a84f893a6db16이다. 새 수신 저장소에서17tests와 CPU smoke2행을 확인했다. 원본 CPU venv를 재사용한 검증이며 지혁 PC의 실제 CUDA 재개는 반환을 기다린다.

이전 자연어 전달문의 clean/restored query 표현을 실제 코드에 맞게 정정한다. Bank는 clean/swinir_restored, query는 bicubic_x4/swinir_x4다. CPU consumer와 지혁의 원본 protocol은 이미 이 정의를 사용한다. Bicubic-bank extension은 두 category seed11에서 Bicubic/SwinIR query를 각각 평가하는 신규4조건이다. Matched Bicubic 대조는 동일 Bicubic query에서 기존 clean-bank와 새 Bicubic-bank를 비교한다.

## 설계 결정 기록

공개 PROGRESS/RUN_RECORD에는 수행 사실·결과·source·실패/재개를 기록한다. 각 담당자는 ignored outputs/private-decisions/에 검증 가능한 문제·근거·대안·선택 이유·변경 전후·남은 질문을 별도 작성해 사용자에게 private 텍스트로 전달한다. 중앙 CPU는 담당자·날짜·run-id/source를 붙여 원본 notes/RESEARCH_EVOLUTION_LOCAL.md에 통합한다. 이 private 노트는 Git 관리 밖에 둔다. 이번에 빠진 두 담당자의 과거 결정도 해당 기록에 있는 사실 범위에서 소급 요약한다.
