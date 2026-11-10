# 심주형 전달 브랜치

작업 지시와 필요한 8개 metadata가 이 브랜치의 handoff/에 있다. 별도 metadata ZIP을 받을 필요 없이 Git으로 받는다. 기존 GPU 환경, VisA와 raw run은 본인 PC에서 재사용한다. 분석 기반은 7d5c177b67f1476c4f6ad98937cc2bcac38a93af다. 실행 source는 본인의 기존 exp/pcb-full-cohort-juhyung 계열을 보존한다.

## 1. 기존 checkout을 유지하고 전달 worktree를 만든다

아래는 기존 GPU repository root에서 실행한다. 현재 worker가 있으면 그 checkout의 branch를 바꾸지 않는다. 새 폴더가 이미 있으면 새 이름을 사용한다.

```powershell
$gpuRoot = (Get-Location).Path
$py = Join-Path $gpuRoot '.venv/Scripts/python.exe'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
git fetch origin
$delivery = Join-Path (Split-Path $gpuRoot -Parent) "juhyung-handoff-$tag"
git worktree add --detach $delivery origin/handoff/juhyung
git -C $delivery switch -c "return-juhyung-$tag"
git -C $delivery -c core.autocrlf=false submodule update --init -- third_party/patchcore-inspection third_party/SwinIR
```

데이터·venv·가중치는 새 worktree에 포함되지 않으므로 아래 명시적 경로를 유지한다. handoff/INPUT_FILES.json의 해시는 Git에 있는 8개 원본 metadata의 bytes를 가리킨다.

## 2. 저장 map 9사례 공간 분석을 먼저 완료한다

```powershell
$raw = Join-Path $gpuRoot 'outputs/pcb-full-cohort/pcb-full-cohort-20261101-a'
$data = Join-Path $gpuRoot 'data/external/VisA'
$result = Join-Path $gpuRoot "outputs/native-spatial-$tag"
& $py "$delivery/scripts/analyze_pcb_selected_maps.py" --maps-root $raw --metadata-root "$delivery/handoff/metadata" --data-root $data --output $result
```

보관 위치가 다르면 같은 run-id의 실제 경로만 지정한다. Model/FAISS 생성과 재추론은 필요 없다. 고정 RAM guard를 유지한다. 선택 suppression 3, geometry_candidate 3, success_control 3의 총 27개 map을 사용한다. Descriptor의 수식은 docs/PCB_SELECTED_SPATIAL_ANALYSIS_V0.1.md를 따른다. GT는 post-hoc 분석과 그림에만 사용하고 같은 sample의 map에는 같은 color scale을 쓴다. PNG를 직접 열어 확인한다. 선택 사례의 관측은 전체 population 추정과 구분한다.

## 3. 기존 진단 해석과 noise 반복을 이어간다

CPU의 docs/GPU_FOLLOWUP_REVIEW_20261110.md와 analysis/gpu_followup_20261110/을 읽고 별도 정정 addendum을 남긴다. 같은 empirical FPR에도 threshold plateau의 TPR 범위가 있으므로 단일 matched-FPR 값으로 원인을 확정하지 않는다. Positive affine normalization은 rank와 정상 quantile 판정을 보존한다. Peak-in-GT와 localization 전반의 평가는 구분한다. Matched-bank의 회복 여부만으로 정보 소실 원인을 확정하지 않는다.

이후 기존 GPU 실행 source와 환경에서 versioned realistic noise v2 driver를 구현하고 관련 fake/deterministic 테스트 후 실행한다. 기존 v1 결과와 코드는 보존한다. 고정 추가 queue는 Hazelnut/Screw × LR Gaussian noise sigma 5/15 × noise-seed 23/37 × Bicubic/SwinIR/RealESRNet/RealESRGAN의 32조건이다. 단위와 삽입 위치는 기존 v1 LR noise 정의를 유지한다. Split/bank seed 11과 noise seed를 별도로 기록한다.

Bank bytes, fit/calibration/test 경로, 224→56→224 geometry, checkpoint와 원래 exact FAISS family A를 고정한다. 같은 sample/noise-seed의 LR bytes는 네 restorer에 공유한다. GT는 열화·복원·calibration·선택에 전달하지 않는다. 각 condition/restorer의 정상 calibration은 기존 robust/q0.99다. Primary contrast는 SwinIR−Bicubic, supplementary는 ESRNet/GAN−SwinIR다. Primary pooled AU-PRO@0.3와 per-image delta를 구분한다. 같은 이미지의 seed 반복을 독립 표본으로 늘리지 않는다. JPEG/blur의 결정적 조건을 noise seed만 바꿔 추가 반복으로 세지 않는다.

한 category/noise-seed가 끝날 때마다 반환하고 남은 queue를 계속한다. 지원되는 resume만 사용하고 partial/failed 기록은 보존한다. 기존 source에 없는 flags를 가정해 호출하지 않는다. 실행 코드 변경은 본인의 feature branch에 commit하고 정확한 source commit/dirty 상태를 결과에 기록한다.

## 4. 결과를 이 브랜치로 반환한다

handoff/returns/juhyung/ 아래에 고유 run-id별 공개 CSV/JSON/보고서를 추가한다. 실제 결과 파일 이름을 확인해 --include에 지정한다. 상세 명령은 docs/TEAM_BRANCH_WORKFLOW.md에 있다. 반환 worktree의 commit을 다음 대상으로 push한다.

```powershell
git -C $delivery push origin HEAD:handoff/juhyung
```

CSV/JSON/report에는 완료 상태, source commit, source hashes, condition/split/calibration 출처, 실제 측정과 추정의 구분을 담는다. RECEIPT.json은 prepare_team_return.py가 생성하며 CPU 검토 전 상태를 유지한다. Raw arrays/bank/weights/RGB·GT PNG는 비공개로 보존한다. 필요한 private artifact의 파일명·shape·dtype·hash와 별도 전달 여부를 보고서에 기록한다. 이 브랜치에 원본 private 데이터를 추가하지 않는다.
