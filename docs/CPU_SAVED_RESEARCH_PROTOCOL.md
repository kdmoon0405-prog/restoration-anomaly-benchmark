# CPU 저장 prediction 확장 분석

2026-11-08에 새 계산 전 설정을 고정했다. Hazelnut과 Screw의 기존 연구 결과를 본 뒤 추가한 exploratory supplementary 분석이다. 이번 분석은 검사 면적과 기존 정상 calibration 운영 지점에서 복원의 효과를 평가한다.

## 고정 면적의 이상 맵 평가

기존 Branch A의 Clean/Bicubic-x4/SwinIR-x4 전체 test prediction을 사용한다. Hazelnut110장과 Screw160장의 공식 test 전체를 포함한다.

상위 이상 점수 영역은 영상 면적의0.1/0.5/1/2/5%다. 선택 pixel 수는 ceil(fraction×H×W)이고 동일 점수는 row-major 순서의 stable sort로 처리한다. Budget 경계의 tie 수와 tie가 경계를 가로지르는지를 함께 기록한다.

Anomaly image마다 GT pixel recall/precision, 4-connected GT 영역별 overlap의 평균, GT 영역 any-hit 비율을 계산한다. GT 영역은 영상 annotation의 연결요소이며 물리적 결함 개수와 구분한다. 정상 영상에서는 alert 영역의 조각 수와 크기를 기록한다.

공간 진단은 peak에서 가장 가까운 GT pixel까지의 거리, 선택된 alert pixel의 평균 GT 거리, 선택 영역의 연결요소 수와 가장 큰 요소의 비율이다. 거리는 canonical224 좌표의 pixel과 영상 대각선 대비 비율로 기록한다.

SwinIR−Bicubic의 paired 차이를 모든 budget에서 보고한다. Bootstrap은 기존 per-image paired helper의2000회/seed11을 사용한다. Confidence interval의 표본 단위는 같은 category의 anomaly image다.

PSNR/SSIM gain과1% budget의 pixel-recall gain 관계는 source CSV와 paired join으로 계산한다. Spearman 계수는 exploratory association으로 제시한다. 사례 그림은 category별 paired delta 최저1장과 최고1장을 lexical tie-break로 고른다.

## 기존 calibration threshold에서의 운영 성능

Branch B Hazelnut313fit/78normal-calibration/110test를 사용한다. 저장된 정상 calibration quantile0.99의 image/pixel threshold를 그대로 적용한다. Clean reference, degraded-only, restored-only, mean0.5/0.5, max의 다섯 조건을 함께 보고한다.

Image 지표는 FP/FN/TP/TN, normal FPR, anomaly sensitivity, exact95% binomial interval이다. Paired 변화는 degraded-only를 기준으로 동일 이미지의 오류/정탐 indicator 차이를 계산한다.

Pixel 지표는 normal 영상의 false-positive 면적 비율과 anomaly 영상의 GT pixel recall이다. CI는 영상 단위 paired bootstrap으로 구한다. Pixel 수를 독립 표본 수로 늘리지 않는다.

정상 표본 수에 따른 오탐률 해석을 위해 관측 오탐0건일 때 exact two-sided95% interval의 상한과 목표FPR1%를 만족하는 필요 표본 수를 계산한다. 이는 독립적이고 대표적인 정상 표본과 고정된 detector/threshold를 가정한 표본 설계 계산이다.

## 실행과 결과

실행 설정은 configs/cpu_saved_research.json이다. Source prediction/metadata/CSV digest와 코드·설정 digest를 결과에 저장한다. 큰 배열은 한 variant씩 처리하고 실제 가용 RAM을 확인한다.

표는 per_image_budget.csv, spatial_summary.csv, paired_budget_effects.csv, quality_association.csv, operating_points.csv, operating_per_image.csv와 paired_operating_effects.csv다. 그림은 전체 표를 근거로 만들고 GT/맵 사례는 local output에 보존한다.

Historical pooled AU-PRO는 source 결과의 참조 값으로 유지한다. 새 예산별 지표와 운영 성능은 각각 별도 열과 표로 보고한다. 이번 계산으로 탐지 맵·bank·checkpoint를 선택하지 않는다.
