# Realistic noise v2 반복 결과의 CPU 검토

반환 branch handoff/juhyung@ba4672ddb29bf0a5252ae4ee05253db70048dba0의 4개 run, 공개 텍스트80파일을 receipt와 대조했다. 기존 v1의 split·입력·checkpoint·vendor revision과 고정 bank/split seed11을 확인했다. Actor source는40d57dd85f3e2d8600b8b2c5c00eb91aa00570eb이며 10개 관련 code의 Git blob 또는 CRLF checkout bytes가 기록 SHA와 일치한다. Tracked dirty는4개모두false, 전체dirty는4개모두true로 기록됐다.

## SwinIR과 Bicubic의 반복 비교

| Category | LR noise sigma | pooled delta seed23 | pooled delta seed37 | 두 draw 평균 per-image delta | 이미지 bootstrap 95% CI | 고유 anomaly 영상 |
| --- | --- | --- | --- | --- | --- | --- |
| hazelnut | 5 | -0.018677 | -0.030986 | -0.027456 | [-0.045220, -0.010556] | 70 |
| hazelnut | 15 | -0.076840 | -0.078543 | -0.094729 | [-0.124034, -0.067120] | 70 |
| screw | 5 | -0.002139 | -0.011167 | +0.003534 | [-0.009651, +0.017825] | 119 |
| screw | 15 | -0.044120 | -0.045764 | -0.051606 | [-0.065134, -0.038401] | 119 |

σ15에서 SwinIR−Bicubic의 pooled AU-PRO 차이는 새 noise draw4개 모두 음수다. 기존 v1 anchor도 같은 방향이다. Hazelnut σ5에서도 두 새 draw의 차이가 음수다. Screw σ5는 pooled 차이가 -0.002139와 -0.011167이고, per-image 평균은 +0.003534이며 CI가0을 포함한다. 이 조건에서는 pooled 지표와 per-image 평균의 방향이 다르다.

RealESRNet과 RealESRGAN의 SwinIR 대비 pooled 차이는 새16contrast 모두 양수다. 새 draw23/37 사이 primary delta의 최대 변동폭은0.012309이고, secondary contrast까지 포함하면 최대0.045570이다. 기존 v1은 별도 historical_anchors.csv에 연결했고 v2 CI에는 포함하지 않았다.

Bootstrap은 기존 paired_bootstrap_mean_delta를2000회, resampling seed11로 재사용했다. 같은 영상의 두 noise draw delta를 먼저 평균한 뒤70개 또는119개 영상 ID를 재표집한다. 이 CI는 고정 bank·split·관측된 두 noise draw에서의 per-image 평균 차이에 대한 보조 추정이다. Pooled AU-PRO의 CI는 계산하지 않았다. 조건 간 같은 영상의 의존성과 여러 contrast의 CI를 고려해 전체 모델 우위나 학습 seed 일반화로 확대하지 않는다.

## 검증과 source coverage

4restorer가 공유하는 LR hash가 각 sample/condition에서 일치했다. Noise23/37 비교에서 Hazelnut376/376, Screw448/448의 LR hash가 달랐다. 같은 category의 bank metadata hash와 fit/calibration/test 경로는 두 draw에서 일치했다. 모든 unit의 정상 calibration image score로 robust 통계와 q0.99 threshold를 검산했고, stored unit JSON·summary·per-image quality 평균의 일치를 확인했다.

Raw NPZ32개와 bank payload는 이번 반환에 포함되지 않았다. Pixel AUROC와 pooled AU-PRO는 저장 JSON의 point estimate를 사용했다. 실제 원격 추론·GT mask·raw map을 이 PC에서 재실행하거나 직접 관찰한 범위는 제외해 기록했다. Hazelnut23의 첫7unit은 중단 전 session 기록이 없고, 이후 session000은7개를 검증해 skip하고1개를 완료한 기록이다. 완료8unit의 파일 연결은 검증됐다. Runtime 비교에는 이 session 차이를 사용하지 않는다.

Master는165조건/13protocol groups다. 과거133개 entry의 ID와 모든 기존 값이 동일하며, 신규32개에는 bank/split seed11과 noise seed23/37을 별도 필드로 넣었다. 재사용 영상은 Hazelnut110장, Screw160장이고 신규 독립 cohort로 집계하지 않는다.

## 공개 경로와 재현

Hazelnut 두 protocol에서 v1_bank_dir 한 필드에 로컬 절대경로가 있었다. public_protocols/에는 해당 값만 repository 상대경로로 바꾼 사본을 작성했다. 다른 JSON 값은 동일하다. protocol_exports.json은 공급된 원본 SHA, 실행 unit이 참조한 protocol SHA, 공개 사본 SHA와 변경 필드를 구분한다. Screw는 이미 상대경로 사본을 받았으므로 실행 원본의 byte SHA는 독립 재계산 범위에 포함하지 않았다.

기존 Git commit에 들어간 경로는 이력에 남는다. 새 공개 사본은 향후 참조와 배포를 위한 값이며, 실제 GPU 실행의 원본 protocol과 resume 기록은 원래 보관 위치에서 유지한다. 두 GPU 담당자의 설계 결정은 ignored private 텍스트로 받고, 원본 notes/RESEARCH_EVOLUTION_LOCAL.md에 근거·대안·수정 이유·남은 질문을 통합한다. 공개 PROGRESS에는 수행 사실과 결과를 기록한다.

재현 코드는 scripts/analyze_noise_repeatability.py, 계획은 configs/noise_repeatability_analysis.json이다. 전달 및 정확한 명령은 docs/NOISE_REPEATABILITY_REVIEW_20261111.md를 따른다. 관련27tests가 통과했다. Source 줄바꿈 검증과 Windows에서 POSIX 절대경로 인식 문제는 수정 후 재검증했다. Scalar 그림은 직접 열어 축·범례·CI와 N을 확인했다.
