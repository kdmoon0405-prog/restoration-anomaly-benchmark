# 심주형 후속 작업

현재 restoration-anomaly-benchmark에서 이어서 실제 작업하라. 기존9사례·addendum·noise v2의32조건은 완료돼 CPU가 반환80파일을 검증했다. 새 CPU 검토는 exp/noise-repeatability-analysis의 docs/NOISE_REPEATABILITY_REVIEW_20261111.md와 analysis/noise_repeatability_20261111/REVIEW.md를 읽는다. 현재 source·worker·사용자 변경을 보존한다.

1. handoff/returns/juhyung/protocol-public-views-20261111/의 Hazelnut 상대경로 사본과 hash 연결을 확인한다. CPU가 이미 준비한 동일 사본은 재생성하지 않는다. 원본 실행 PROTOCOL과 unit의 original protocol SHA를 보존한다. 향후 공개 exporter는 상대경로 사본과 원본 SHA를 함께 저장하도록 보완한다. 과거 commit에 들어간 경로는 이력에 남는다는 점을 기록한다.

case-00/04/06의 RGB/GT PNG3개와 해당 hash를 사용자에게 private로 전달한다. CPU는 아직 원격 사례 그림을 직접 보지 못했다.

2. 다음은 저장 map을 이용한 image-score aggregation 대조 실험이다. Source feature branch를 별도로 만들고 작은 synthetic 테스트와 실제 저장 결과 분석까지 진행한다. 실제 모델 재학습·재추론은 필요하지 않다. 목적은 ×4 이후 Screw 이미지 판정 저하에 map의 image-score 집계가 얼마나 관여하는지 확인하는 것이다. Pixel map과 기존 pooled AU-PRO는 고정 reference로 유지한다.

실제 test label을 이용한 새 비교 전에 IMAGE_SCORE_AGGREGATION_V0.1.md에 다음5규칙을 고정하고 commit한다.
- 저장된 original image score.
- 저장된 후처리 map의 max.
- 저장 map 상위0.1% 평균.
- 저장 map 상위0.5% 평균.
- 저장 map 상위1% 평균.

상위k는 ceil(fraction*H*W)로 정하고 모든 image에 같은 규칙을 적용한다. Original score와 map max는 서로 다른 anchor로 검증한다. 원래 image score가 후처리 map max와 같다고 가정하지 않는다. GT나 defect area로k·영역·rule을 정하지 않는다.

범위는 Hazelnut/Screw의 기존 realistic v1 none4restorer와 v2 noise_s5/noise_s15 × noise23/37 ×4restorer다. Category당20개 저장 unit, 총40unit×5rule의 최대200개 image-score 평가 cell이다. 같은 원본 prediction을 재사용한 평가임을 명시한다. 이전32조건을 새로운 inference로 다시 세지 않는다.

3. 각 unit/rule의 정상 calibration만 사용해 기존 robust 통계와 q0.99 threshold를 fit한다. Image AUROC가 이 sub-study의 primary, F1·test-normal FPR·anomaly miss rate는 supplementary다. Existing evaluation 함수와 score 비교 연산을 재사용한다. Original-score anchor는 원래 unit의 저장 image metric/threshold와 맞아야 한다. 해당 anchor의 불일치는 원인을 해결한 후 나머지 분석을 이어간다. Test label은 평가에만 사용하고 test 결과로k·threshold를 재선택하지 않는다.

4. 한 unit씩 readonly로 열고 처리해 해제한다. 실제 NPZ schema와 shape/dtype를 먼저 확인하고 기존 메모리 guard에 실제 payload를 넣는다. Raw bank/model/FAISS를 만들거나 로드하지 않는다. 원본 array·hash를 수정하지 않는다. 모든5규칙과 모든 완료 unit을 보고하고 좋은 cell만 고르지 않는다. Bootstrap CI는 CPU가 공통 분석할 수 있도록 sample/label/calibration-or-test/rule/raw-score/threshold와 원본unit SHA를 반환한다. 같은 image의 noise 반복은 묶어서 해석한다.

5. 공개 코드·테스트·CSV·보고서는 실행 feature source commit과 함께 handoff/juhyung으로 반환한다. RGB/GT/원본array는 본인 local에 보존한다. 범위 누락이나 resource 차단이 있으면 해당 unit과 이유를 명시하고 독립 가능한 unit을 진행한다.

6. 설계·수정 과정은 본인 outputs/private-decisions/juhyung-20261111.private.md에 작성한다. git check-ignore와 git ls-files로 private 상태를 확인한다. 문제와 실제 근거, 검토한 대안, 선택 이유, 구현 수정 전후, 관측과 가설, 남은 질문을 run-id/source/CSV 위치와 함께 기록한다. 이 private 텍스트는 사용자에게 비공개로 전달해 중앙 notes/RESEARCH_EVOLUTION_LOCAL.md에 통합한다. 공개 PROGRESS/RUN_RECORD에는 수행 사실과 결과를 기록한다.

소스·예산·실행 순서의 구체적인 판단은 직접 수행하고 근거를 남긴다. 계획만 제시하고 멈추지 말고 위의 유한한 저장 결과 분석 queue를 완료하라.

과거 결정은 당시 남긴 기록으로 확인 가능한 부분을 소급 정리한다. 당시 기록과 현재의 사후 해석을 구분하고 확인되지 않는 이유를 채워 넣지 않는다.
