# 설계 후 전체 근거 검토를 위한 연구 인계

2026-11-12 작성. 12월1일 포스터 발표를 위한 검토 범위다. 먼저 NEXT_TASK의 독립 설계 초안을 저장한 뒤 이 문서를 읽고 수정안을 작성한다. Source of truth는 연결된 실제 CSV·JSON·코드이며 이 문서는 탐색용 요약이다.

## 목표와 현재 범위

연구 질문은 SR로 화질이 개선될 때 산업용 이상 탐지가 어떻게 달라지며, 일부 결함의 localization regression과 낮은 image-level 성능을 어떻게 설명·개선할 수 있는가이다. 기존 fixed x4 결과와 실제 촬영 조건 관리를 연결한다. 최종 산출물은 근거가 연결된 포스터·그림·정량표, 재현 코드, 보유 스마트폰으로 촬영한 소규모 검사 시연이다.

현재 master는165 prediction 조건,8 study families,13 protocol groups다. 같은 영상·bank·조건의 재평가와 중복 run을 독립 표본 수로 합치지 않는다. Image-score200cell은 별도 readout ablation이다.

| study_family | master 행 |
| --- | --- |
| cpu_hog_bank_domain_v1 | 36 |
| cpu_hog_knn_control_x4_v1 | 24 |
| endpoint_full110 | 4 |
| historical_recovery | 6 |
| pcb_native_full_cohort_v0_6 | 3 |
| realistic_lr_degradation_v1 | 56 |
| realistic_lr_noise_v2 | 32 |
| restoration_objective_screw_matlab | 4 |

원본 master와 claim-evidence index는 exp/image-score-return-analysis@57235a2의 analysis/noise_repeatability_20261111/master/에 있다. CPU HOG control과 GPU PatchCore 결과는 별도 family로 비교한다. PIL bicubic와 MATLAB-compatible endpoint, native PCB와 realistic/noise families의 입력·split·bank·metric 차이를 유지한다.

## 확인된 결과와 남은 질문

### 1. 고정 x4의 평균 개선과 개별 regression

Hazelnut fixed taxonomy는 localization delta per-image AU-PRO<0, suppression은 여기에 delta ROI-background gap<0, geometry candidate는 gap delta>=0을 적용한다. Hazelnut70anomaly 중 regression30,suppression14,geometry16,improvement/tie40이 기존 검증값이다. Geometry candidate라는 분류명은 원인 기전을 확정하지 않는다. Test GT는 post-hoc evaluation과 설명용이다.

Selected Screw feature-distance 사례의 suppression n3와 success n3에서 상대 defect-feature normalization과 일관된 양상을 관찰했다. 선택사례·n3/subtype의 범위를 유지한다. 기존 negative gating 및 full110 B/B-uncertain 판정은 유지한다.

### 2. PCB full-FOV와 engineering

Full-frame224 초안에서는324개 GT component 중19개가9영상에서 사라졌고, native224 tiling에서는324개와 이전19개ID가 모두 보존됐다. 이는 geometry 검증이다. 연결요소는 물리적 결함 개수와 구분한다. 과거 center crop/full-frame224와 native protocol은 별도 family다.

PCB native full cohort는 fit721/calibration180/test200이고, test는 normal100/anomaly100이다. Master의 pooled AU-PRO는 clean0.9516588113,Bicubic0.9391328783,SwinIR0.9439644285다. SwinIR의 pixel localization 이득과 image metric의 차이를 함께 보고한다. Image AUROC는 Bicubic0.9680,SwinIR0.9544였다. Fixed-threshold F1의 차이를 operating point 하나로 전부 설명한다는 과거 해석은 철회/정정됐다. 같은 FPR에서의 plateau 범위도 고려한다.

CPU exact FAISS가 포함된 탐지 단계의 비용이 컸다. 6tile query batching 연구에서batch4약1.50배는 제한된 계측값이며 float32 결과의 엄격한 allclose 실패도 기록됐다. 이를 full production 처리량이나 기존 exact family의 동일 결과로 확대하지 않는다. Poster의 engineering 증거는 geometry·메모리 lifecycle·실제 fit bank·전체 cohort와 계측 범위를 연결한다.

### 3. 실사형 열화와 반복

Realistic v1은 Hazelnut/Screw×7조건×4restorers의56조건이다. 추가 noise v2는 bank/splitseed11을 고정하고 noise draw23/37,σ5/15로32조건을 추가했다. 같은 noisy LR hash가restorers간 같고 두draw에서 달라진 것을 CPU에서 검토했다.

σ15의 SwinIR−Bicubic pooled delta는 추가 Hazelnut두draw에서 약−0.077~−0.079,Screw에서−0.044~−0.046이다. RealESRNet/RealESRGAN의 SwinIR 대비 pooled delta는 추가16contrast 모두 양수였다. Screwσ5의 영상별 mean delta CI에는0이 포함됐다. Noise 반복 CI는 각영상의 두draw를 평균한 뒤 고유영상ID70/119개를 재표집한 보조 추정이다. Pooled AU-PRO CI와 학습seed 일반화는 별도 검증 대상이다.

### 4. Image-score 집계 대조

40저장unit에 original/map max/top0.1%/top0.5%/top1%의5규칙을 사전 고정해200cell을 계산했다. CPU는 calibration·threshold·판정·Image AUROC/F1/FPR/미검률을 CSV에서 검산했다. Screw AUROC는 전체규칙 약0.41~0.68이고 top1%가14/20unit에서original보다 낮다. 집계 규칙 변경만으로 낮은 image 성능을 해소한 결과는 얻지 못했다.

CPU는 동일영상ID를 paired stratified bootstrap으로2,000회 재표집해160개 rule−original AUROC 구간을 추가했다. 이는 결과를 확인한 뒤 추가한 pointwise 불확실성 분석이다. 해당 구간으로 test 기반 규칙을 재선택하지 않는다. Raw NPZ40개는 이 반환에서 CPU에 미수신이다. CPU의 scalar 검산과 GPU의 raw-map anchor 검증을 구분한다.

### 5. 도착 전 자료

지혁의 GPU bank-domain24+4 결과는 아직 CPU에 미도착이다. Bank는 clean/swinir_restored,query는 bicubic_x4/swinir_x4다. Matched Bicubic-bank extension은 같은-protocol baseline과 비교한다. 결과가 오면 bank/query mismatch 가설을 검토한다. Matched-bank 미회복만으로 결함 정보 소실을 확정하지 않는다.

사용자는 스마트폰·책상 조명·가능한 플래시를 쓸 수 있으며 추가 구매를 원하지 않는다. 실제 촬영 대상·정상/결함 수량·사진은 아직 미확인이다. Phone 촬영 결과는 별도 family로 만든다.

## 필요한 범위만 확인할 공개 자료

- 57235a2의 analysis/noise_repeatability_20261111/master/master_results.csv와 claim_evidence_index.csv
- 57235a2의 analysis/noise_repeatability_20261111/REVIEW.md 및 analysis_plan.json
- 57235a2의 analysis/image_score_return_20261111/REVIEW.md,paired_auc_intervals.csv,analysis_plan.json
- exp/pcb-selected-spatial-review@30b420d의 analysis 및 docs 중 selected spatial review
- handoff/juhyung의 기존 handoff/returns/juhyung/ 각 run의 RECEIPT와 실제 source·metric CSV
- docs/EXPERIMENT_PROTOCOL_V0.2.md,docs/PCB_FULL_FOV_PROTOCOL_V0.6.md의 필요한 규칙

위경로가 현재 execution branch에 없으면 기존 checkout을 바꾸지 않고 git show 또는 별도 source-only worktree에서 읽는다. 원격 branch의 문서와 GPU execution branch/commit을 구분한다. 새로운 source checkout에 venv·dataset·weights가 자동 전달되지 않음을 고려한다. 전체 문서를 무작정 다시 읽지 않는다.

## 설계 검토에서 답할 항목

현재 근거로 주장 가능한 내용과 가설을 구분한다. 각각의 근거 CSV/JSON·source·sample 범위를 연결한다. 현재 설계에서 leakage,평가 단위,threshold/calibration,protocol혼합,선택사례의 일반화 오류가 생길 지점을 확인한다. 실험·테스트 개수 대신 연구 질문,효과 크기,반복과 한계를 기준으로 포스터 핵심 주장2~3개를 정한다.

그 뒤 독립 초안의 무엇을 유지·수정했는지와 이유를 기록하고,12월1일 이전에 완성할 주력 구현 하나와 비교 baseline을 고정한다. Test GT나 이미 본 test 성능으로 checkpoint/threshold/weight를 재선택하지 않는다.
