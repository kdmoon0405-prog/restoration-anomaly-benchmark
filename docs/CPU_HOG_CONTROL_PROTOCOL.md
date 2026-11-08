# CPU HOG-kNN restoration 대조 실험

2026-11-08에 실제 test 계산 전 설정을 고정했다. CPU에서 실행 가능한 특징 기반 대조군으로 x4 열화와 고정 sharpening의 효과를 측정한다. 이미 연구한 Hazelnut/Screw를 사용하는 exploratory 추가 family다.

HOG는 scikit-image 구현을 사용한다. Orientations9, cell8×8, block2×2, L2-Hys와 sqrt transform으로 canonical224 영상에서27×27개의36차원 descriptor를 얻는다. 동일 normal fit pool의 descriptor ordinal 중 최대4096개를 seed11로 균일 비복원 추출한다. Scikit-learn NearestNeighbors의 exact Euclidean1NN으로 patch distance를 계산한다.

Patch 중심은 pixel-index7.5+8r,7.5+8c다. Bilinear interpolation과 nearest boundary extension으로224×224 score map을 만든다. Image score는 descriptor distance의 최대값이다.

공식 normal train을 기존 split helper로80/20 fit/calibration 분리한다. 입력은 Pillow short-edge256 bilinear resize 후 center224 crop이고 GT에는 동일 좌표의 nearest resize/crop을 적용한다.

비교는 Clean, Pillow Bicubic x4, Bicubic x4 후 UnsharpMask radius1/percent100/threshold0의 세 조건이다. 파라미터는 config에 고정한다. 모든 조건은 같은 clean-normal HOG bank를 사용한다.

Variant별 정상 calibration score/map에 기존 median/IQR normalization과 fallback을 fit한다. Image/pixel threshold는 normalized normal calibration의 quantile0.99다. Test GT는 prediction 생성 이후 evaluation 준비 단계에서 읽는다.

Dataset primary는 기존 evaluator의 pooled AU-PRO@0.3이다. Pixel/Image AUROC와 normal-calibrated F1, PSNR/SSIM, per-anomaly AU-PRO를 함께 기록한다. 각 category의 official test 전체를 포함한다.

Inference와 evaluation을 별도 process로 실행해 model과 metric buffer의 생존 구간을 분리한다. 입력과 canonical RGB receipt, bank/선택 ordinal, 설정·source hash, 시간·OS process memory를 저장한다. 새 CPU 모델의 resource 계획은 작은 descriptor bank와224 map payload를 기준으로 계산한다.

HOG-kNN의 결과는 이 feature family와 두 category의 범위에서 해석한다. 기존 PatchCore/SwinIR 평가와 별도 표에 제시하고 새로운 특징·고정 전처리의 관측 효과를 기술한다. 프로토콜 변경은 별도 config와 기록으로 구분한다.

## 고정 seed 반복과 집계

Seed11 결과를 확인한 뒤 반복 변동을 점검하기 위해23/37을 추가했다. 추가 실행 전에 두 설정을 기록하고 다른 파라미터는 동일하게 유지한다. 두 category 모두 세 seed의 공식 test 전체를 평가한다. 이미 탐색한 category의 추가 분석이다.

Pooled AU-PRO는 seed별 point estimate와 세 seed의 평균·범위로 제시한다. Per-image AU-PRO 차이는 seed별 paired bootstrap2000회/seed11과, 같은 영상의 세 seed 차이를 먼저 평균한 뒤 영상 단위 bootstrap으로 보고한다. 후자의 CI는 고정된 세 fit에 조건부인 영상 변동이며 bank 추정의 전체 불확실성을 포함하지 않는다. 동일 영상의 세 seed를 독립 표본으로 늘리지 않는다.

Sharp−Bicubic을 고정 비교로 사용한다. Quality는 동일 sample/variant의 RGB hash·PSNR·SSIM을 seed 간 대조한 뒤 한 번만 집계한다. Normal per-image AU-PRO는 해당 없음이다. Candidate/seed 선택은 수행하지 않는다.

현재 v1의 per_image_inference.csv detector_seconds는 predict 시작부터 normalization과 quality 계산이 끝나는 구간이다. 순수 detector latency로 해석하지 않는다. Fit/inference/evaluation process 경과와 OS lifetime peak working set은 별도 기록한다.

## 고정 SwinIR 조건 추가

HOG의 Clean/Bicubic/Unsharp 결과를 본 뒤, 기존 SwinIR-S x4 checkpoint를 사용하는 네 번째 query 조건을 추가한다. 2026-11-08의 정상 calibration3장 CPU 실행에서 query당 약1초와 process peak447,848,448bytes를 관측했다. 추가 test 계산 전에 checkpoint SHA09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e, canonical224→Pillow Bicubic LR56→SwinIR224, CPU4threads를 고정한다.

세 seed의 calibration/test union만 한 번 복원해 같은 RGB를 재사용한다. 기존 여섯 clean-normal HOG bank와 각 split을 유지하고 새 variant의 normal calibration을 별도로 fit한다. SwinIR−Bicubic을 고정 비교로 전체 category/seed를 보고한다. 새 restore 조건의 결과로 checkpoint/threshold/seed를 선택하지 않는다. Cache 생성에는 GT를 전달하지 않고 GT는 detector prediction 저장 이후 평가 준비에만 사용한다.
