# CPU 정상 bank와 query domain 비교

2026-11-08의 HOG24조건 결과를 본 뒤 추가한 탐색 실험이다. 기존 clean-normal bank에서 관측한 낮은 열화 영상 성능에 정상 bank/input domain 차이가 얼마나 관여하는지 비교한다. 이 문서는 새 bank 결과 계산 전에 작성했다.

Hazelnut·Screw, seed11/23/37, 기존 fit/calibration/test 경로와 HOG 설정을 사용한다. 같은 정상 fit 영상의 같은 global patch ordinal4096개를 각 domain에 적용한다. Bank dimension36, float32, exact Euclidean1NN을 유지한다.

Bank는 clean, Bicubic-x4 정상 영상, SwinIR-x4 정상 영상의 세 조건이다. Query는 Bicubic-x4와 SwinIR-x4다. 총36개 category/seed/bank/query 조건 가운데 기존 clean-bank12조건은 저장 결과를 재사용하고24조건을 새로 계산한다. Clean·SwinIR bank의2×2는 기존 bank-domain 분석기를 사용하고, Bicubic bank는 matched-degradation 대조군으로 함께 보고한다.

Primary는 각 조건의 dataset pooled AU-PRO@0.3이다. Pixel/Image AUROC, normal-calibrated F1, per-image AU-PRO와 ROI/background gap을 보조 지표로 기록한다. 기존 exact evaluator의4-connectivity,200thresholds,max_fpr0.3을 사용한다.

각 bank/query의 정상 calibration에 median/IQR와 기존 fallback, quantile0.99를 fit한다. Test GT는 모든 query prediction 저장 이후 평가 입력으로 읽는다. Bank fit에는 지정된 정상 fit RGB만 사용한다. Test 성능으로 bank·checkpoint·seed·threshold를 재선택하지 않는다.

같은 query의 RGB hash·PSNR·SSIM은 bank와 무관하게 동일해야 한다. SwinIR RGB614장을 byte-검증하여 새 cache에 복사하고, 추가 정상 fit367장만 같은 checkpoint로 복원한다. 전체 cache981장의 생성·재사용 개수와 시간을 구분한다. 원본 cache와 bank는 보존한다.

비교는 같은 query에서 bank를 바꾼 delta, 같은 bank에서 query를 바꾼 delta, matched-SwinIR 대 matched-Bicubic의 전체 pipeline delta다. 모든 seed/category를 보고한다. Paired bootstrap은 기존2,000회/seed11 helper를 재사용한다. 같은 영상의 세 seed 값을 독립 표본으로 늘리지 않는다. Pooled metric의 seed별 차이와 image-unit CI를 구분한다.

출력은 신규 raw bank/query artifacts, 기존5파일 bank-domain 계약의 여섯 결과 묶음, 전체36조건 표, clean-bank anchor 비교, 두 개 정도의 수치 그림이다. 기존12조건의 재사용을 새 독립 실험으로 세지 않는다. Master에는 신규24조건만 더한다.

이 HOG 비교는 이미 탐색한 두 category와 현재 특징 구현의 범위다. Bank/query 효과는 이 조건에서의 관측 차이로 보고한다. Capsule은 이번 실험에 포함하지 않는다.

## 2026-11-09 고정 용량 혼합 bank 추가

위 36조건에서 정상 bank와 query domain 일치 효과를 확인한 뒤, 하나의 bank로 두 query를 지원하는 탐색 후보를 추가한다. 아래 규칙은 혼합 bank 결과 계산 전에 고정했다.

같은 정상 fit 영상의 기존 global patch ordinal 4,096개를 유지한다. Bicubic feature 2,048개와 SwinIR feature 2,048개를 합쳐 총 용량을 유지한다. 각 ordinal은 둘 중 한 domain의 feature 하나만 제공한다. Study seed와 상수 20261109를 SeedSequence에 넣은 permutation의 앞 절반에 Bicubic을 배정하고 나머지에 SwinIR을 배정한다. Feature를 산술 평균하거나 prediction을 fusion하지 않는다. 50:50 이외의 비율은 탐색하지 않는다.

각 query별 정상 calibration은 기존 규칙대로 별도 fit한다. 따라서 query 종류를 알 필요 없는 단일 calibration으로 해석하지 않는다. 신규 12조건을 더하면 전체 표는 48조건이며, 재사용 clean-bank 12조건과 신규 36조건을 구분한다. Master table에는 신규 36조건만 더한다. 두 category는 이미 개발에 사용했으므로 이 추가 후보의 결과도 탐색 결과다. Capsule은 계속 보존한다.
