# 손지혁 전달 브랜치

작업 지시, dataset receipt, 원본 실행 코드 patch와 테스트 portability patch가 handoff/에 있다. 코드와 문서는 Git으로 받는다. 현재 본인의 ac931349ba0f3db795a5400534b3a79d2bdc4f44 실행 source와 CUDA 환경을 보존한다. 이 전달 브랜치의 CPU 분석기는 실행 측 동명 분석기와 용도가 다르므로 덮어쓰지 않는다.

## 1. 전달 worktree와 입력을 준비한다

기존 GPU repository root에서 아래를 수행한다. Worker가 실행 중인 checkout은 바꾸지 않는다. 새 worktree는 source 전용이며 데이터와 환경은 원래 위치를 사용한다.

```powershell
$gpuRoot = (Get-Location).Path
$py = Join-Path $gpuRoot '.venv/Scripts/python.exe'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
git fetch origin
$delivery = Join-Path (Split-Path $gpuRoot -Parent) "jihyuk-handoff-$tag"
git worktree add --detach $delivery origin/handoff/jihyuk
git -C $delivery switch -c "return-jihyuk-$tag"
```

GitHub 443이 계속 막히면 해당 접속 문제를 기록하고 기존 offline bundle 경로로 코드만 받는다. 현재 GitHub 사용 가능 여부는 이 호스트에서 확인해야 한다.

Dataset ZIP만 최초 1회 별도 비공개로 받는다. 이름은 mvtec-hazelnut-screw-team-20261110.zip, 크기는 813040630bytes, SHA256은 635ced502743817e8ef8fe704b2bbd1634fe87f15edaef5e7d85e6d3b86a28b9다. 기존 repository root의 handoff-private/에 보관한 경우 다음과 같이 검증하고 새 directory에 받는다. 이미 검증된 입력이 있으면 재수신하지 않고 그 경로와 receipt를 재사용한다.

```powershell
$archive = Join-Path $gpuRoot 'handoff-private/mvtec-hazelnut-screw-team-20261110.zip'
$data = Join-Path $gpuRoot 'data/external/MVTecAD-team-20261110'
& $py "$delivery/scripts/receive_category_transfer.py" --archive $archive --receipt "$delivery/handoff/inputs/dataset_provenance.json" --output $data
```

Hazelnut은 정상 train391/test-normal40/test-anomaly70/mask70, Screw는320/41/119/119다. 라이선스와 원본 readme가 ZIP에 포함돼 있다. 이는 private team repack의 checksum이며 원 publisher archive checksum은 미확인이다. Receipt의 역할을 바꾸지 않는다. Dataset 파일은 Git에 추가하지 않는다.

## 2. 본인 실행 source의 작은 연결을 완료한다

handoff/code/bank-domain-study-ac93134.patch는 본인이 보낸 원본 코드의 보관본이다. 이미 ac93134가 있는 checkout에 다시 적용하지 않는다. handoff/code/jihyuk-fixture-portability.patch는 그 원본의 fake 테스트에만 적용하는 수정이다. 기존 실행 feature branch에서 apply --check를 먼저 수행하고 필요한 경우 적용한다. Production checkpoint SHA와 RAM guard는 유지한다.

Fake fixture는 tiny checkpoint/expected digest, Git/NVIDIA metadata stub와 RAM getter만 격리한다. CPU에서 이 수정으로 11tests가 통과했다. 본인 환경에서는 관련 테스트만 실행하고 전체 pytest 반복으로 GPU queue를 지연시키지 않는다.

첫 실제 실행 전에 다음 연결을 완료한다. Model, metric, geometry, split seed, bank 알고리즘은 고정한다.

- 실행 측 scripts/analyze_bank_domain_study.py를 analyze_bank_domain_execution.py 등으로 구분하고 호출·테스트·문서를 함께 맞춘다. CPU consumer는 docs/BANK_DOMAIN_ANALYSIS_HANDOFF.md를 따른다.
- Source commit, dirty flag, feature/transform/metric 경로 code SHA와 checkpoint SHA를 실제 실행에서 기록한다.
- Fit timing 직전에 CUDA synchronize를 넣어 factory 대기와 구분하고 기존 post-fit synchronize는 유지한다.
- Prediction 저장 뒤 evaluation의 per-image 행에 normalized ROI mean−background mean을 기록한다. 정상 per-image AU-PRO는 NA다. GT는 prediction/fit/calibration 입력으로 전달하지 않는다.
- CPU의 다섯 파일 export 계약에 맞추거나 현재 summary/per-image/config/provenance/quality의 정확한 mapping을 함께 제공한다. 과거 실행에 없던 source SHA를 수신 시점 코드로 채우지 않는다.

All-patch IdentitySampler와 paired capacity/ordinal을 유지한다. CPU HOG4096 또는 PCB262144 cap을 이 실험에 적용하지 않는다. Fresh RAM/disk guard를 bank마다 유지하고 동시에 두 bank/model을 보유하지 않는다. 변경 source는 별도 feature commit으로 보존하고 source commit을 결과에 기록한다.

## 3. 실제 queue를 진행한다

먼저 Hazelnut seed11과 Screw seed11의 clean/restored bank × clean/restored query 네 셀을 완료한다. 같은 category/seed의 정상 fit/calibration/test 경로와 query RGB를 공유하고 query SHA를 기록한다. 기본 checkpoint 경로가 다르면 실제 보관 파일의 SHA를 확인해 기존 CLI 인자로 전달한다. 현재 실행 feature checkout에서 다음 형식으로 실행한다.

```powershell
& $py scripts/run_bank_domain_study.py --category hazelnut --seed 11 --device cuda --data-root $data --dataset-provenance "$data/dataset_provenance.json" --run-id "hazelnut-s11-$tag"
& $py scripts/run_bank_domain_study.py --category screw --seed 11 --device cuda --data-root $data --dataset-provenance "$data/dataset_provenance.json" --run-id "screw-s11-$tag"
```

완료된 category/seed의 metadata를 먼저 반환한다. 이어 seed23/37을 동일 규칙으로 진행해 총24조건을 완료한다. 같은 condition의 중복 run은 독립 실험으로 세지 않는다. 지원되는 resume만 사용하고 실패/partial 상태는 보존한다.

이후 Bicubic normal-bank × clean/restored query를 두 category의 seed11에만 추가한다. 신규4조건을 별도 extension family/schema로 기록하고 기존 네 셀 계약은 유지한다. Matched-bank 회복 여부로 정보 소실의 원인을 확정하지 않는다. 같은 이미지의 세 seed를 독립210개 표본처럼 다루지 않는다. 이번 queue에는 Capsule/EfficientAD를 추가하지 않는다.

## 4. 이 브랜치로 결과를 반환한다

공개 CSV/JSON/보고서만 handoff/returns/jihyuk/의 고유 run-id 아래에 추가한다. prepare_team_return.py에 실제 존재하는 파일을 --include로 명시하고 staged diff를 검토한 뒤 다음으로 push한다. 상세 예시는 docs/TEAM_BRANCH_WORKFLOW.md에 있다.

```powershell
git -C $delivery push origin HEAD:handoff/jihyuk
```

Raw arrays/bank/checkpoint/dataset은 본인 PC에 보존한다. 보고서에는 원본 파일 위치의 역할과 SHA, 실제 측정과 추정, 미전달 배열 범위를 구분한다. 완료 상태와 반환 receipt는 CPU 검토 완료 판정과 구분한다.
