# GPU 후속 반환과 CPU 연결 검토

2026-11-10에 diagnosis-batch-20261109.zip, pcb-native-maps-20261109.zip과 지혁의 ac93134 patch를 검토했다. 원본 결과와 source patch는 별도 경로에 보존했다. 분석 수치는 analysis/gpu_followup_20261110/에 저장했다.

## 전달 범위와 직접 확인

진단 ZIP의 명시27개 파일 hash가 일치했다. Map ZIP의 최상위 manifest가 지정한51개 파일도 일치했고,27개 native array를 받았다. 내부에 동봉된 과거 bank-source manifest는 미전달 원본10개를 나열하고 있어 historical receipt로 구분했다. 최상위 전달 manifest의 검증 범위를 해당 원본들까지 확대하지 않았다.

27개 map은 고정 selection CSV와 SHA가 일치했다. Local에서 한 map씩 read-only mmap을 열고65536-float chunk로1070×1404/float32/finite를 확인했다. 이 검사는 배열 무결성 범위다. Frozen metadata를 사용하는9case 공간 분석은 고정2GiB 여유를 포함한 약2.39GiB 메모리 기준에 미달해 BLOCKED_MEMORY로 종료했다. GT pixel decode와 공간 descriptor 생성은 다음 실행에 남아 있다. 가드는 유지했다.

## Batch 실험의 정합성

제공된 timing44call을12pass로 재집계했고3조건 summary의 mean/min/max와 일치했다. Warmup1회와 measured3회를 구분했다. Batch4의 검색 speedup은1.498988이다. 이는6개 고정 tile의 같은 호스트 측정이다. Remainder 때문에 batch4 pass는4tile call과2tile call로 구성된다.

Raw query·distance array는 미전달이므로 distance parity는 원격 CSV 기록 범위다. 기록된 distance allclose 실패와 최대 약1.14e-5 차이를 보존했다. Image score 차이0과 map 차이 약4.6e-6도 그6tile 범위다. Exact IndexFlatL2 알고리즘과 bitwise equality를 구분한다.17시간 절감과98% 검색 비중은 small-sample 외삽이며 full cohort 실측값으로 사용하지 않는다.

## Image-score 해석 보완

새 진단 CSV의200board×3variant score와 label을 기존 반환600개 scalar row에 대조해 일치를 확인했다. 기존 normalized threshold를 raw threshold로 환산한 판정도 모두 같았다. 양의 affine median/IQR 변환은 rank와 해당 normal-quantile 판정을 보존한다. Raw score 분포 변화와 정규화 연산 자체를 구분해 해석한다.

정상100장에서는 같은 false-positive 수를 만드는 threshold가 구간을 이룬다. 그 구간의 threshold에 따라 TPR도 달라진다.

| test FP | Bicubic TPR 범위 | SwinIR TPR 범위 |
|---|---|---|
|1/100|0.55~0.57|0.39~0.57|
|3/100|0.62~0.82|0.59~0.70|

전달된 matched-FPR 표의0.57 등은 각 구간의 낙관적인 끝점이다. 같은 empirical FPR의 한 점으로 F1 하락의 대부분을 calibration에 귀속시키기에는 근거가 부족하다. 이 표와 그림은 post-hoc 진단이며 기존 q0.99 threshold와 결과를 유지한다. 구간은 threshold plateau의 TPR 범위다.

Flip25개 사례의 map peak-in-GT 비율은 보조 관측이다. 일부 peak가 GT 안에 있다는 관측과 per-image AU-PRO regression은 함께 발생할 수 있다. Overlap-mean map의 argmax tile proxy와 실제 tile-image-score argmax도 구분한다. 실제 tile score 재계산은 원격의1board×2variant 범위다.

Matched-bank 대조군은 query를 고정하고 정상 reference를 바꾸는 실험으로 적합하다. 회복은 reference-domain 효과에 맞는 증거가 된다. 미회복만으로 정보 소실을 확정하기에는 backbone 표현, bank support와 score 집계 같은 설명이 남는다.

## Endpoint provenance 보강

원본 Screw endpoint results.json과 bank metadata에서 seed11, 동일한 normal train320경로, fit_performed=false를 확인했다. 네 variant의 저장 AU-PRO/Pixel AUROC/Image AUROC/PSNR/SSIM을 기존 표와 대조했다. 이 값들을 유지하면서 seed/train count만 채운 별도 master를 만들었다.133조건/9protocol groups가 유지됐다. 원본 bank array/index bytes는 검토 자료에 포함되지 않았다.

## 지혁 코드와 입력 전달

원본 patch SHA는 b7da13d666709ffe300a879f48e64c8a87a9224545b9c44ae966503edfff92c7다. 알려진83ef04e 기반의 격리 checkout에만 적용했다. Public5c4ddd8에서도 apply --check가 통과했다. 기존 CPU analyzer는 보존했다.

초기 targeted test는10pass/1fail이었다. Fake E2E가 실제 checkpoint, Git/NVIDIA metadata와 host RAM에 의존했다. 작은 checkpoint와 해당 test expected SHA, metadata stub, RAM getter로 fixture를 격리한 후11pass를 확인했다. Production model/metric/guard는 동일하다. 수정은 별도 portability patch로 전달한다.

IdentitySampler는 legacy PatchCore 설정과 맞고 category/seed 안에서 두 bank의 capacity와 ordinal이 같다. HOG4096 또는 PCB262144 cap을 새로 적용하지 않는다. 다음 실행 전에 source SHA/dirty provenance, per-image ROI-background gap과 CPU scalar export mapping을 정리한다. 실행 측 동명 analyzer는 CPU consumer와 구분해 이름을 정한다.

필요한 Hazelnut/Screw만 private ZIP으로 재포장했다. Hazelnut391/40/70, Screw320/41/119이며 anomaly mask는70/119개다. 새 directory에서1177개 전달 파일을 검증했다. License/readme/출처를 포함했고 archive SHA는 새 private transfer ZIP의 checksum이다. 원래 publisher archive checksum은 미확인으로 보존했다. MVTec의 공식 license는 CC BY-NC-SA4.0이며 비상업 연구 조건을 따라 전달한다. [MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)

## 재현과 다음 실행

```powershell
$py = '..\..\.venv\Scripts\python.exe'
$original = (Resolve-Path '..\..').Path
$diagnosis = Join-Path $original 'outputs/gpu-followup-review-20261110/artifacts/diagnosis-batch-20261109/diagnosis-batch-20261109'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
& $py scripts/analyze_score_diagnosis.py --diagnosis $diagnosis --output "outputs/score-plateau-$tag"
& $py scripts/build_research_master_table.py --catalog configs/research_reporting_gpu_followup_20261110.json --output "outputs/master-followup-$tag"
& $py scripts/simulate_inspection_station.py --output "outputs/station-$tag"
& $py scripts/smoke_test.py
```

다음 GPU 임무는 주형32GB 호스트의9case 공간 분석과32조건 noise-realization 반복, 지혁의 실제 bank-domain24조건과 matched Bicubic4조건이다. CPU는 그 반환을 기존 family별로 통합한다. 실제 bank-domain 성능은 현재0/24다. Synthetic/controller replay와 기존 연구 조건을 별도 표로 유지한다.

최종 CPU 전체 pytest는674passed/3skipped다. 기존 subprocess RAM 전제조건2개와 checkout의 optional MVTec fixture1개가 skip됐다. Receiver/controller/spatial 관련28개와 score/receiver5개 검증도 통과했다. CPU smoke2행과 diff 검사를 확인했다. Receiver 임시 폴더 권한 오류와 편집 중 들여쓰기 오류는 수정 후 재검증했다. Science plot은 직접 열어 끝점·label·단위를 확인했다.
