# CPU 연구 결과와 재현

2026-11-08에 저장 PatchCore 예측의 검사 면적 분석과 실제 HOG-kNN 대조 실험을 수행했다. Hazelnut·Screw는 기존에 탐색한 category다. 새 결과의 범위는 이 두 category의 추가 탐색으로 둔다.

## 고정 검사 면적에서의 SwinIR 효과

Branch A의 기존 Hazelnut110장·Screw160장, 세 variant, 다섯 면적을 분석했다. 4,050개 image/variant/budget 행을 만들었다. 상위 점수 pixel 수는 ceil(영상 면적×budget)이고 동일 점수는 row-major stable sort로 처리했다.

영상 면적1%에서 SwinIR−Bicubic의 anomaly-image 평균 GT pixel recall 차이는 다음과 같다. CI는 anomaly image 단위 paired bootstrap2,000회다.

| Category | Anomaly 영상 | Recall 차이, %p | Pointwise95% CI, %p | 감소 / 증가 |
|---|---:|---:|---:|---:|
| Hazelnut | 70 | −0.116 | [−1.496, +1.254] | 33 / 22 |
| Screw | 119 | +24.309 | [+18.370, +29.975] | 16 / 71 |

결함 종류별1% budget의 평균 차이도 전체 subtype에 대해 계산했다. 사후 탐색이며 각 CI는 pointwise interval이다.

| Category / defect | n | Recall 차이, %p | Pointwise95% CI, %p |
|---|---:|---:|---:|
| Hazelnut / crack | 18 | +0.361 | [−0.931, +1.749] |
| Hazelnut / cut | 17 | +1.142 | [−3.909, +6.280] |
| Hazelnut / hole | 18 | −1.015 | [−1.945, −0.163] |
| Hazelnut / print | 17 | −0.928 | [−2.944, +0.619] |
| Screw / manipulated_front | 24 | +10.753 | [+4.423, +18.146] |
| Screw / scratch_head | 24 | +45.142 | [+29.785, +59.316] |
| Screw / scratch_neck | 25 | +51.067 | [+38.992, +62.014] |
| Screw / thread_side | 23 | +5.745 | [+1.294, +10.930] |
| Screw / thread_top | 23 | +6.196 | [−5.593, +17.859] |

Screw의 평균 개선은 scratch_head·scratch_neck에서 크게 관측됐다. Thread_top은 평균이 양수인 가운데23장 중10장에서 recall이 감소했다. 사례 그림은 category별 delta 최저·최고 영상을 lexical tie-break로 선택했다.

PSNR 증가와1% recall 증가의 Spearman 계수는 Hazelnut+0.153, Screw−0.004였다. SSIM의 해당 계수는−0.059, −0.022였다. 이 값은 같은 category 안의 영상별 association point estimate다.

## 화질 개선과 탐지 저하가 함께 나온 CPU 대조군

Scikit-image HOG와 scikit-learn exact1NN을 사용했다. Clean-normal descriptor bank는4096×36 float32다. Split seed11/23/37, 두 category, Clean/Bicubic-x4/Unsharp-x4의18조건을 평가했다. 각 category/seed는 fit/calibration을 분리했으며 calibration과 test는 세 variant에서 같은 clean-normal bank를 사용한다.

Unsharp는 radius1/percent100/threshold0으로 고정했다. Seed11을 본 뒤23/37 반복을 추가했고 다른 설정을 유지했다. 실제 test prediction2,430건과 category/seed별 bank6개를 생성했다. 고유 test 영상은270장이다.

| Category | 평균 PSNR 차이, dB | 평균 SSIM 차이 | 평균 pooled AU-PRO 차이 | 세 seed의 pooled 차이 범위 |
|---|---:|---:|---:|---:|
| Hazelnut | +0.165996 | +0.001227 | −0.003956 | [−0.004527, −0.003648] |
| Screw | +0.266404 | +0.001824 | −0.026889 | [−0.030332, −0.023820] |

차이는 Unsharp−Bicubic이다. 세 seed 모두 PSNR·SSIM 증가와 pooled AU-PRO 감소를 함께 보였다. Clean bank를 사용하는 이 HOG detector는 Bicubic query에서도 절대 성능이 낮았다. Seed11의 Clean/Bicubic pooled AU-PRO는 Hazelnut0.6406/0.0101, Screw0.7333/0.0696이다. 전체 절대값은 표와 그림에 보존했다.

같은 영상의 세 seed delta를 먼저 평균한 뒤 영상 단위 bootstrap을 적용했다. Anomaly image 단위는 Hazelnut70장과 Screw119장이다. Conditional mean per-image AU-PRO delta는 각각−0.005914, −0.028949였고95% CI는[−0.008519, −0.003658], [−0.039120, −0.020028]이었다. 이는 고정된 세 fit에 조건부인 영상 변동이다. Bank 추정의 전체 불확실성은 별도 검토가 필요하다.

## 학습된 SwinIR을 사용한 네 번째 조건

기존 checkpoint의 SwinIR-S x4로 calibration/test의 고유 RGB614장을 CPU에서 복원했다. 344장은 정상 calibration union이고270장은 test다. 복원 cache를 한 번 만든 뒤 같은 여섯 HOG bank/split을 재사용하고 variant 전용 normal calibration을 fit했다.

| Category | PSNR 차이, dB | SSIM 차이 | 평균 pooled AU-PRO 차이 | 세 seed의 pooled 차이 범위 |
|---|---:|---:|---:|---:|
| Hazelnut | +2.313490 | +0.022492 | +0.072742 | [+0.069091, +0.077322] |
| Screw | +2.437519 | +0.016426 | +0.133538 | [+0.128212, +0.138100] |

차이는 SwinIR−Bicubic이다. SwinIR의 pooled AU-PRO 증가는 두 category의 세 seed에서 모두 관측됐다. Seed11의 SwinIR pooled AU-PRO는 Hazelnut0.081954, Screw0.197795다. Clean query와의 간격은 전체 절대값 그림에 표시했다.

Anomaly image의 세 seed 평균 delta에 대한 conditional mean per-image AU-PRO 차이는 Hazelnut+0.086868, Screw+0.138900이다. 영상 단위95% CI는[+0.064743, +0.111737], [+0.108706, +0.171353]이다. Seed별 regression count는 Hazelnut4/2/1장, Screw19/19/27장이다. Pooled 개선과 sample-level regression을 함께 기록했다.

이번 CPU 묶음은 최종24조건, 실제 test prediction3,240건, 고유 test 영상270장이다. Quality는1,080개 sample/variant 단위로 한 번씩 집계했다. 기존10조건과 함께 만든 master에는34행과4개의 protocol group이 있다. 같은 영상의 반복과 같은 조건의 재집계를 독립 실험 수로 늘리지 않았다.

HOG의 sharpening 조건과 학습된 SwinIR 조건은 모두 PSNR·SSIM이 증가했으며 localization 변화의 방향이 달랐다. SwinIR 내 영상별 PSNR gain과 per-image AU-PRO gain의 Spearman 계수는 Hazelnut+0.163, Screw−0.130이다. 이 비교는 현재 HOG feature family와 이미 탐색한 category의 범위에 둔다. 기존 PatchCore family는 별도 표에 유지했다.

동일 sample/query RGB hash와 quality를 seed 간 대조해810개 image/variant quality 행을 한 번씩 집계했다. Normal 영상의 per-image AU-PRO는 해당 없음으로 유지했다. Normalized map의 ROI/background gap taxonomy는 사후 map 패턴으로 기록했다.

## 기존 정상 calibration threshold에서의 운영 지점

Hazelnut Branch B313fit/78normal-calibration/110test의 저장된 quantile0.99 threshold를 사용했다. 각 method의 threshold는 과거 정상 calibration 값이다.

| Method | TP / 70 | FN | FP / 40 |
|---|---:|---:|---:|
| Clean | 70 | 0 | 0 |
| Degraded | 65 | 5 | 0 |
| Restored | 65 | 5 | 0 |
| Mean0.5/0.5 | 67 | 3 | 0 |
| Max | 66 | 4 | 0 |

Mean fusion은 degraded의 미탐3장을 추가 탐지했고 탐지1장을 놓쳤다. Sensitivity 차이는+2.857%p, paired95% CI는[−2.857, +8.571]%p다. 정상40장의 오탐0건에 대한 exact two-sided95% FPR 상한은8.810%다. 목표1%를 같은 방식의 zero-error interval로 점검하려면 독립적이고 대표적인 정상 영상368장이 필요하다.

기존 pooled AU-PRO primary와 negative fusion/gating 판정은 유지한다. 이번 운영 지점과 면적별 recall은 별도 supplementary 결과다. Test label/GT로 threshold·alpha·checkpoint를 재선택하지 않았다.

## 자원과 검증 범위

CPU HOG inference/evaluation은 category·seed별 별도 process로 실행했다. 여섯 run에서 관측된 가장 큰 단일 process OS lifetime peak working set은421,830,656bytes(402.289MiB)였다. 서로 다른 process peak를 합하지 않았다.

Seed11 두 category의 orchestration elapsed는294.918s, seed23/37 네 category/seed run의 연속 elapsed는853.220s였다. 후자는 회귀 테스트와 일부 구간을 동시에 실행했다. 환경 간 속도 비교에는 사용하지 않는다. Fit은 inference elapsed에 포함된다. v1 per-image detector_seconds에는 normalization·quality 계산도 포함된다.

SwinIR cache의 모델 생성부터614장의 RGB·quality 저장까지의 경과는553.736s였고, 해당 process의 OS lifetime peak working set은457,326,592bytes(436.141MiB)였다. 이는 이 실행에서의 관측값이다. Cache 생성과 여섯 bank의 추가 추론·평가를 포함한 orchestration status 경과는970.326s였다. 이 두 시간을 더하지 않는다. 추가 SwinIR variant의 detector_seconds는 HOG predict 구간만 측정한다.

전체 pytest623pass/3skip(269.50s), 기존 CPU smoke2행을 확인했다. Skip 두 건은 unchanged2GiB reserve를 포함한 실제 RAM 사전조건, 한 건은 코드 worktree에 optional MVTec 데이터가 없는 조건이다. 초기 임시 폴더 ACL 및 빈 submodule 오류는 해결했고 실패 로그도 보존했다. Source 초기화 중 LFS 예제 파일 자동 수신을 중단한 뒤 process-local skip으로 마무리했다. 그 예제 bank는 이 연구에 사용하지 않았다.

Source가 추가·수정된 작업 트리에서 실행했으므로 실행 당시 source_worktree_dirty는true다. 실행 당시 base HEAD와 실제 source/data digest를 receipt에 보존했다. 공개 commit은 이후 전달한 구현 버전으로 구분한다. 공개 수치 CSV는 UTF-8/LF로 내보냈고 원본 run CSV bytes는 local에 보존했다.

GT는 HOG query prediction 이후 evaluation 준비 단계에서 읽었다. 원본 inventory와 RGB/GT receipt, canonical cache, bank·prediction digest와 환경 버전을 local output에 보존했다. Capsule test는 이번 실험에서 사용하지 않았다. 기존 PatchCore/SwinIR source와 연구 결과도 보존했다.

새 공간 지표·HOG 대조군의 설정과 seed 반복은 exploratory protocol에 기록했다. 이 범위에서 관측한 quality–detection 차이를 기존 PatchCore나 다른 category의 효과로 확장하려면 해당 실험이 필요하다.

## 재현 명령

현재 구현 worktree에서 원본 interpreter와 artifact를 재사용한 PowerShell 명령이다. 실행마다 새 output 폴더를 사용한다.

```powershell
$artifacts = (Resolve-Path '../..').Path
$python = Join-Path $artifacts '.venv/Scripts/python.exe'
$campaign = Join-Path $artifacts ('outputs/cpu-research-replay-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
& $python scripts/run_cpu_saved_research.py --artifact-root $artifacts --output "$campaign/spatial"
& $python scripts/plot_cpu_saved_research.py --run "$campaign/spatial" --artifact-root $artifacts
& $python scripts/analyze_inspection_defects.py --run "$campaign/spatial" --output "$campaign/defects"

foreach ($seed in @(11,23,37)) {
  $config = if ($seed -eq 11) { 'configs/cpu_hog_control.json' } else { "configs/cpu_hog_control_seed$seed.json" }
  & $python scripts/run_cpu_hog_control.py --stage full --config $config --data-root "$artifacts/data/external/MVTecAD" --input-manifest "$artifacts/outputs/mvtec-team-inputs-20261101/input_manifest.json" --output "$campaign/hog-$seed"
  if ($LASTEXITCODE -ne 0) { throw "CPU control failed for seed $seed" }
}
& $python scripts/analyze_cpu_controls.py --run "$campaign/hog-11/hazelnut-seed11" --run "$campaign/hog-11/screw-seed11" --run "$campaign/hog-23/hazelnut-seed23" --run "$campaign/hog-23/screw-seed23" --run "$campaign/hog-37/hazelnut-seed37" --run "$campaign/hog-37/screw-seed37" --output "$campaign/hog-analysis"
& $python scripts/plot_cpu_controls.py --run "$campaign/hog-analysis"

$temporary = Join-Path ([IO.Path]::GetTempPath()) ('cpu-tests-' + [guid]::NewGuid().ToString('N'))
& $python -m pytest -q --basetemp $temporary
& $python scripts/smoke_test.py
git diff --check
```

새 checkout에서는 사용자가 선택한 Python3.11 환경에 `.[dev,cpu-research]` 의존성을 설치한다. 위 worktree용 interpreter·data·저장 prediction은 checkout에 포함되지 않는다. 고정 submodule을 초기화하면 기존 upstream 호환 테스트를 함께 실행할 수 있다.

공개 가능한 수치 표는 `analysis/cpu_research_20261108/`에 둔다. RGB/GT/map 사례·bank·raw prediction·개인 노트는 local output에서 관리한다. 새로운 GPU 반환이 도착하면 기존 bank-domain 분석과 통합 reporting 계약으로 연결한다.

### SwinIR cache와 bank 재사용 재현

앞의 세 seed HOG 실행이 완료된 같은 `$campaign`을 사용한다. 기존 CPU 환경의 Torch·timm과 원본 SwinIR checkpoint가 필요하다. 새 source 초기화에는 process-local LFS skip을 사용한다.

```powershell
$env:GIT_LFS_SKIP_SMUDGE = '1'
git submodule update --init -- third_party/SwinIR third_party/patchcore-inspection
$references = foreach ($seed in @(11,23,37)) {
  foreach ($category in @('hazelnut','screw')) {
    Join-Path $campaign "hog-$seed/$category-seed$seed"
  }
}
$cache = Join-Path $campaign 'swinir-cache'
$cacheArgs = @('scripts/run_cpu_restoration_control.py','--stage','cache','--repository','third_party/SwinIR','--checkpoint',"$artifacts/checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth",'--output',$cache)
foreach ($reference in $references) { $cacheArgs += @('--reference',$reference) }
& $python @cacheArgs
if ($LASTEXITCODE -ne 0) { throw 'CPU restoration cache failed' }

$analysisArgs = @('scripts/analyze_cpu_controls.py','--include-swinir','--output',"$campaign/hog-four-condition-analysis")
foreach ($reference in $references) {
  $name = Split-Path $reference -Leaf
  $query = Join-Path $campaign "swinir-hog/$name"
  & $python scripts/run_cpu_restoration_control.py --stage infer --reference $reference --cache $cache --output $query
  if ($LASTEXITCODE -ne 0) { throw "CPU bank query failed for $name" }
  & $python scripts/run_cpu_restoration_control.py --stage evaluate --output $query
  if ($LASTEXITCODE -ne 0) { throw "CPU evaluation failed for $name" }
  $analysisArgs += @('--run',$reference,'--run',$query)
}
& $python @analysisArgs
& $python scripts/plot_cpu_controls.py --run "$campaign/hog-four-condition-analysis"
```

Cache가 중단됐다면 동일 source·reference·checkpoint·output에 `--resume`를 추가한다. 완료된 PNG는 hash 검증 후 재사용한다. 불완전 inference output은 별도로 보존하고 새 output을 사용한다. 자동 재개는 먼저 worker PID를 확인해 같은 job을 중복 실행하지 않는다.

수치 표와 코드의 hash 재현을 위해 새 CPU source와 공개 CSV의 LF 규칙을 추가했다. 원본 run의 CSV는 보존했다. 공개 표를 연결한 master 재생성 명령은 다음과 같다.

```powershell
& $python scripts/build_research_master_table.py --catalog configs/research_reporting_cpu_20261108.json --root . --output "$campaign/master"
```
