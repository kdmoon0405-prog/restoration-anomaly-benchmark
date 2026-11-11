# 저장 map image-score 집계 반환 검토

2026-11-11 CPU 검토. 공개 반환 handoff/juhyung@0ad6d07의 Hazelnut·Screw 각20unit, 총200cell을 확인했다. 두 반환46+46파일과 경로 정정 보고서1파일의 공급 SHA/크기를 확인했다. 원본·정규화 점수 CSV에서 정상 calibration 통계, q0.99 threshold, 판정과 Image AUROC/F1/FPR/미검률을 기존 함수로 재계산했다. 저장 summary200행과 일치했다. 같은 영상 cohort와 세션별 실행 source6파일의 Git/CRLF checkout byte 연결도 확인했다.

## 집계 방식과 Screw의 image 성능

| category | original AUROC 범위 | top1% AUROC 범위 | top1%−original 범위 | top1% 감소 unit |
| --- | --- | --- | --- | --- |
| Hazelnut | 0.7804~0.9982 | 0.8086~0.9979 | −0.0207~+0.0282 | 10/20 |
| Screw | 0.4107~0.6790 | 0.4319~0.6323 | −0.0953~+0.0473 | 14/20 |

Screw의 map max/top0.1%/top0.5%는 각각15/20unit에서 original보다 낮았다. 다섯 집계 방식에서 낮은 image AUROC가 유지됐다. 이번 비교는 집계 방식 변경의 효과를 검토한 결과이며, bank/query domain이나 representation의 기전은 별도 대조가 필요하다. Hazelnut의 변화도 unit별로 양·음이 섞였다.

## 불확실성 분석

각 unit에서 정상·결함 영상 ID를 각각 복원추출하고, 같은 인덱스를 다섯 규칙에 적용했다. 기존 binary_roc_auc를 재사용했으며 2,000회, seed11의 paired stratified bootstrap으로160개 rule−original 차이의95% 구간을 계산했다. 계획은 analysis_plan.json에 실행 전에 기록했다. 기존 결과를 확인한 뒤 추가한 post-hoc 불확실성 분석이다.

구간은 관측된 bank·split·noise draw에서의 unit별 Image AUROC 차이에 대한 pointwise 구간이다. 여러 비교를 고려한 확증적 유의성 선언이나 test 기반 규칙 선택에는 사용하지 않았다. 같은 영상이 여러 unit에 재사용되므로200cell을 독립 표본으로 합치지 않는다. 기존 master165개의 prediction 조건 수는 유지하며, 이200행은 별도 readout ablation이다. Pixel AUROC와 AU-PRO는 공급된 reference를 유지했다.

## 확인 범위

원본 score 규칙의 scalar 검산은40/40통과했다. 실제 map/NPZ40개는 이번에 수신되지 않았다. Map calibration anchor와 NPZ hash 검증은 주형의 실행 기록에 보고된 범위이며 이 PC의 payload 재검증과 구분했다. GPU 실행 시각과 tracked/worktree dirty 기록은 공급된 그대로 유지했다. Public session argv의 상대경로 사본과 원본 SHA도 구분한다.

Private 사례 ZIP은3PNG 내부 해시를 확인한 뒤 직접 열었다. 사례는047/006/050이며 GT·경계 위치와 비교 map의 공통 color scale을 확인했다. RGB/GT 그림과 실제 private 결정 원문은 원본 checkout의 ignored outputs에 보관했다. 선택3사례는9사례의 시각적 보충 범위다.

다음은 지혁의 matched bank-domain 대조와, 추가 구매 없이 촬영할 스마트폰 조명 변화 파일럿의 준비다. Phone 촬영·전처리·bank·calibration은 별도 family로 기록한다. 설계 초안과 담당자 작업은 docs/PHONE_LIGHTING_PILOT_DRAFT.md 및 docs/PROMPT_JUHYUNG_PHONE_LIGHTING.md에 있다.

## 재현

구현 checkout에서 기존 Python 환경을 명시적으로 사용한다. --returns는 두category의 원본 receipt/CSV/JSON 폴더를 포함하는 로컬 경로이며 기존 output을 보존하기 위해 새 output 이름을 사용한다.

```powershell
& ../../.venv/Scripts/python.exe scripts/analyze_image_score_return.py --returns ../image-score-return-review-20261111/received --output outputs/aggregation-replay-20261111
```
