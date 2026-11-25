# 주형 공간 분석 반환의 CPU 재현

검토 대상은 handoff/juhyung의 반환 commit 52b4c23e61f5dd06e438604f533a9c03ea500328이다. Native-spatial 및 diagnosis-addendum의 두 receipt와 파일 6개를 검증했다. 분석 source 두 파일의 SHA는 1e6c6bcd0e59ed91c6c3e6eb0e078f8d75b8bf39와 일치한다.

분석 결과와 범위는 analysis/pcb_spatial_return_20261110/REVIEW.md, per_case_review.csv, gradient_units.csv, review.json에 있다. selected_descriptors.png는 scalar CSV에서 생성한 그림이다. 원격 RGB/GT case PNG의 로컬 직접 확인 수는 0개다.

아래 명령은 원본 research_code 아래 outputs/pcb-spatial-return-review-20261110 worktree에서 실행한다. 기존 Python 환경을 명시적으로 재사용하고, 원격 반환을 별도 source-only worktree로 받는다. 새 출력 경로는 실행마다 바꾼다.

```powershell
$py = (Resolve-Path '../../.venv/Scripts/python.exe').Path
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
git fetch origin refs/heads/handoff/juhyung:refs/remotes/origin/handoff/juhyung
$received = Join-Path (Split-Path (Get-Location).Path -Parent) "juhyung-spatial-return-$tag"
git worktree add --detach $received 52b4c23e61f5dd06e438604f533a9c03ea500328
& $py scripts/review_pcb_spatial_return.py --spatial-run "$received/handoff/returns/juhyung/native-spatial-20261110-152518" --addendum-run "$received/handoff/returns/juhyung/diagnosis-addendum-20261110" --metadata-root "$received/handoff/metadata" --analysis-source-commit 1e6c6bcd0e59ed91c6c3e6eb0e078f8d75b8bf39 --output "outputs/spatial-return-replay-$tag"
$taskTemp = Join-Path ([IO.Path]::GetTempPath()) ('pcb-spatial-return-' + [guid]::NewGuid().ToString('N'))
& $py -m pytest -q tests/test_pcb_spatial_return_review.py tests/test_pcb_selected_spatial.py tests/test_score_diagnosis.py --basetemp $taskTemp
& $py scripts/smoke_test.py
git diff --check
```

관련17tests와 CPU smoke2행이 통과했다.

CSV 산술의 수치 일치 검사는 abs_tol=1e-6, rel_tol=1e-7을 사용한다. 기존 taxonomy와 selection은 원래 정의를 유지한다. Raw gradient 환산에는 기존 normal-calibration pixel scale을 사용한다. Seam/non-seam 비율은 positive affine 변환에 불변이다.
