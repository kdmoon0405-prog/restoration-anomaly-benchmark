# CPU 정상 bank/query domain 실험 결과

2026-11-08~09. 기존 clean-bank 결과를 본 뒤 정상 bank 적응 효과를 분리한 탐색 실험이다. HOG/exact 1NN을 사용했고 PatchCore·PCB·GPU 실험 코드는 유지했다.

Hazelnut·Screw, seed 11/23/37, 정상 bank 4종과 query 2종을 비교했다. 전체 표 48조건 중 clean-bank 12조건은 재사용했고 36조건을 새로 계산했다. 새 test prediction은 4,860건이다. 앞선 24조건과 합친 고유 CPU 조건은 60개/8,100 prediction이며, 고유 test 영상은 270장(anomaly 189장)이다. Seed 반복을 새 영상으로 세지 않았다.

Bank는 같은 정상 fit 영상의 동일 global patch ordinal 4,096개, dimension 36, float32를 사용한다. 각 bank/query의 정상 calibration과 quantile 0.99를 따로 fit했다. Test GT는 query prediction 저장 이후 evaluation에서만 읽었다.

## 관측 결과

Primary pooled AU-PRO@0.3의 세 seed 평균이다. 개별 값과 범위는 CSV 및 첫 그림에 있다.

| category | 정상 bank | Bicubic query | SwinIR query |
|---|---|---:|---:|
| hazelnut | clean | 0.010316 | 0.083058 |
| hazelnut | bicubic_matched | 0.568351 | 0.566180 |
| hazelnut | swinir_restored | 0.475435 | 0.595390 |
| hazelnut | balanced_mixed | 0.547290 | 0.592339 |
| screw | clean | 0.064565 | 0.198103 |
| screw | bicubic_matched | 0.742211 | 0.672008 |
| screw | swinir_restored | 0.736018 | 0.737736 |
| screw | balanced_mixed | 0.736797 | 0.711667 |

Bicubic query를 유지하고 clean bank를 Bicubic 정상 bank로 바꾸면 평균 pooled AU-PRO는 Hazelnut +0.558035, Screw +0.677645 증가했다. 동일 query의 RGB hash와 PSNR/SSIM이 bank 사이에서 일치한다. 정상 feature 분포와 query의 일치 효과를 복원 화질 변화와 구분할 수 있는 비교다.

전용 정상 bank끼리의 SwinIR−Bicubic delta는 Hazelnut +0.027039, Screw −0.004475다. Clean bank를 고정한 앞선 비교의 +0.072742/+0.133538과는 배포 조건이 다르다. 앞선 고정-bank 관측은 그대로 보존하며, 이 추가 결과로 두 조건을 섞어 평균하지 않는다.

50:50 후보는 36조건을 본 뒤 별도 amendment로 규칙을 고정한 탐색 후보다. 기존 ordinal마다 Bicubic 또는 SwinIR feature 하나를 배정해 2,048개씩 구성했다. 비율 탐색이나 score/map fusion은 수행하지 않았다. 전용 bank 대비 네 category/query cell의 평균 pooled AU-PRO가 모두 낮았다. 단일 bank의 trade-off로 남기고 성능 개선 성공으로 분류하지 않는다. Query별 calibration은 따로 필요하다.

| category | 비교 | pooled delta 평균 | conditional per-image delta 95% CI |
|---|---|---:|---|
| hazelnut | 혼합 − 전용 Bicubic | -0.021060 | [-0.019992, -0.006079] |
| hazelnut | 혼합 − 전용 SwinIR | -0.003051 | [-0.010432, +0.003046] |
| hazelnut | 전용 SwinIR − 전용 Bicubic | +0.027039 | [-0.006072, +0.051383] |
| screw | 혼합 − 전용 Bicubic | -0.005414 | [-0.013017, -0.000297] |
| screw | 혼합 − 전용 SwinIR | -0.026070 | [-0.038000, -0.021495] |
| screw | 전용 SwinIR − 전용 Bicubic | -0.004475 | [-0.031650, +0.011193] |

위 CI는 각 영상의 세 seed delta를 먼저 평균한 뒤 anomaly 영상 단위로 bootstrap(2,000회, seed 11)한 평균 per-image AU-PRO 차이다. 고정된 세 fit에 조건부이며 pooled AU-PRO의 CI가 아니다. 전용 pipeline 비교의 per-image CI는 두 category 모두 0을 포함한다. Multiple comparisons 보정이나 독립 validation category에서의 재현은 이번 분석 범위에 포함하지 않았다.

전용 SwinIR pipeline을 전용 Bicubic pipeline과 비교한 per-image localization regression은 seed 11/23/37에서 Hazelnut 31/27/26장(70장 중), Screw 67/57/60장(119장 중)이다. 평균 성능과 개별 사례 위험을 별도로 보고한다. Taxonomy와 delta magnitude는 paired_effects.csv 및 per_image_deltas.csv에 있다.

두 category는 이미 개발에 사용했다. HOG의 clean-bank 열화 query 절대 성능이 낮다는 한계도 표에 남겼다. PatchCore의 개선이나 feature suppression의 인과 기제로 일반화하지 않는다. Capsule은 이번에 사용하지 않았다. 다음 독립 비교는 GPU PatchCore에서 같은-query 정상 bank 적응 효과를 확인하는 것이다.

## 산출물과 검증

- [48조건 표](../analysis/cpu_bank_domain_20261109/matrix_summary.csv), [seed 비교](../analysis/cpu_bank_domain_20261109/seed_summary.csv), [사례별 delta](../analysis/cpu_bank_domain_20261109/per_image_deltas.csv).
- [bank/query 그림](../analysis/cpu_bank_domain_20261109/figures/bank_query_matrix.png), [conditional CI 그림](../analysis/cpu_bank_domain_20261109/figures/conditional_bank_effects.png). 두 PNG를 직접 열어 축·공유 색 범위·CI 표기와 경계를 확인했다. 첫 CI 그림의 reference 제목을 수정했으며 첫 render는 로컬에 보존했다.
- [master table](../analysis/cpu_bank_domain_20261109/master/master_results.csv): 70행/5 protocol groups. 신규 36조건만 추가해 재사용 anchor의 중복 집계를 피했다. 서로 다른 family를 합쳐 성능 평균을 만들지 않았다.

전체 pytest 643 passed/1 skipped(310.98s), 최종 분석·export 관련 6 passed(5.25s), 기존 CPU smoke 2행 통과다. HOG feature/evaluator/fusion/metrics/dataset 원본 5개 파일은 base b247500과 일치한다. 테스트 임시 폴더는 새 OS temp를 사용했다.

SwinIR cache 981장은 614장을 byte-검증 복사하고 부족한 정상 fit 367장만 새로 복원했다. 일시적 Windows checkpoint 교체 오류를 제한된 retry로 수정하고, 중단 상태와 AST 비교 증거를 보존한 뒤 같은 cache를 재개했다. Image/model/data 함수는 그 IO 수정 전후 동일하다. 현재 cache elapsed/peak 필드는 마지막 재개 process 범위이며 전체 시도의 시간이나 peak로 합산하지 않는다. 기존 완성 cache·bank·예측은 보존했다.

코드는 base b247500 위의 dirty worktree에서 실행했고 실제 source hash를 각 run에 남겼다. 나중의 공개 commit과 실행 시 source commit은 구분한다. Dataset/RGB/GT/raw prediction/bank/checkpoint 및 개인 노트는 Git에 포함하지 않는다. 공개 숫자 파일은 UTF-8/LF이며 source/table hash를 남겼다.

## 저장 결과 재현

로컬 구현 worktree outputs/cpu-research-20261108에서 PowerShell로 실행한다. 새 checkout에는 환경·입력·raw artifact가 포함되지 않는다. 기존 .venv를 명시적으로 사용한다.

```powershell
$py = '..\..\.venv\Scripts\python.exe'
$study = '..\cpu-bank-domain-campaign-20261108'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
& $py scripts/analyze_cpu_bank_domain_study.py --execution "$study\execution" --mixed-execution "$study\mixed-execution" --output "$studynalysis-replay-$tag"
& $py scripts/plot_cpu_bank_domain_study.py --run "$studynalysis-replay-$tag"
& $py scripts/export_cpu_bank_domain_results.py --analysis "$studynalysis-replay-$tag" --execution "$study\execution" --output "$study
umeric-replay-$tag"
& $py scripts/build_research_master_table.py --catalog configs/research_reporting_cpu_bank_20261109.json --output "$study\master-replay-$tag"
& $py scripts/smoke_test.py
git diff --check
```

새 모델 계산은 run_cpu_bank_domain_study.py --stage full 및 run_cpu_mixed_bank_study.py에서 기존 source campaign/cache를 명시해 새 output에 수행할 수 있다. 이번 완료 결과를 재사용할 때는 위 read-only 명령만 필요하다.
