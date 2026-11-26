# 연구 결정 기록

로컬 연구 노트의 공개 사본이다. 실험을 시작한 시점부터 당시의 결과, 실패, 조건 변경 이유를 남겼다. 과거의 가설과 실행 계획은 날짜가 표시된 이력이다. 현재 보고서 작성에는 [인계 문서](REPORT_AUTHOR_HANDOFF.md)와 [결과 자료실](../results/README.md)을 함께 사용한다.

공개 사본을 2026-11-26에 만들었다. 실험 경로를 가리키는 개인 작업 위치는 생략했다.

이 문서는 restoration-anomaly-benchmark 연구의 가설 변화, 실험 결과, negative result, 방향 전환 및 다음 질문이 생성된 이유를 기록하는 로컬 연구 노트이다. 논문/보고서의 공식 결과표가 아니며 최종 주장보다 연구 과정 보존이 목적이다. AI의 내부 사고 과정이 아니라 저장된 결과와 검증 가능한 연구 결정만 적는다.

Last updated: 2026-11-17
Local research checkout: `79a1c0f` (`exp/profiling-results-demo`). Published memory-readiness branch: `bb22cf8a1f7073229ff615b67b3df2a100763827` (`exp/pcb-native-memory-readiness`). Producer worktree and independently verified published delivery: `83ef04e6a55f12f7d7cb6d6bfd69bebab98793d9` (`exp/pcb-full-producer-integration`, parent2f418c0, code-only fast-forward on2026-10-27). Local feature branch exp/pcb-fullcap-resource-probe points to the same commit; no additional remote branch was pushed. The original checkout was not reset to these branches.

Local-only maintenance rule: after executing project work, append the verified observations, decision rationale, limitations, evidence paths/commit and next step here. Do not record private internal reasoning. Do not stage, commit, push or copy this notebook into public handoff documents. Check its ignore rule and absence from tracked files after updates. GPU teammate reports are inputs to the next local update, not permission to publish this notebook. Historical stage entries stay unchanged; a later stage may explicitly extend an earlier decision.

읽은 근거: [`README.md`](../README.md), [`PROGRESS.md`](../PROGRESS.md), [`RESEARCH_DECISION_LOG.md`](../docs/RESEARCH_DECISION_LOG.md), [`EXPERIMENT_PROTOCOL_V0.2.md`](../docs/EXPERIMENT_PROTOCOL_V0.2.md), [`analysis/hazelnut/`](../analysis/hazelnut/), [`analysis/screw/`](../analysis/screw/), [`analysis/reporting/`](../analysis/reporting/), `git log --all --oneline --decorate`. 아래 수치는 이 저장 자료에서 확인했다. Branch A와 B는 정상 학습 데이터 수가 다르므로 서로 같은 memory bank의 점수처럼 비교하지 않는다.

## Stage 0 — 초기 문제의식

가설은 SR·restoration이 PSNR/SSIM을 높여도 미세 결함을 정상 texture처럼 복원해 downstream PatchCore의 anomaly evidence를 약화시킬 수 있다는 것이었다. 산업 검사에서는 영상의 보기 좋은 정도보다 놓친 결함(false negative)과 결함 정보 보존이 더 직접적인 문제다. 처음부터 목표는 최고 화질 모델 선정이 아니라 `image quality`와 `defect detectability`를 같은 이미지에서 따로 측정하는 것이었다.

그래서 `original → degradation → detector`와 `original → degradation → restoration → detector`를 비교하는 CPU-safe 프레임워크부터 만들었다. 이 시점에는 가설을 지지하거나 기각할 실제 카테고리 결과가 없었다. 결론 대신 동일 입력·detector·평가 절차를 재현할 수 있게 한 뒤 실험으로 넘어갔다. 근거: decision log §0–1, commit `cad618f`.

## Stage 1 — 고정 SwinIR baseline: 평균 악화 가설 수정

질문은 “SR이 anomaly detection을 해치는가?”였다. Hazelnut Branch A에서 정상 학습 391장, 테스트 110장, WideResNet50 `layer2+layer3`, 1024/1024 embedding, patch size 3, IdentitySampler, CPU exact FAISS를 고정했다. 224×224 clean을 Pillow bicubic으로 56×56으로 낮춘 뒤 Bicubic x4와 SwinIR-S x4를 비교했다. 별도 정상 calibration이 없어 F1은 비웠다.

| Hazelnut Branch A | PSNR | SSIM | Image AUROC | Pixel AUROC | pooled AU-PRO@0.3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bicubic x4 | 36.465447 | 0.931733 | 0.998214 | 0.983933 | 0.818910 |
| SwinIR-S x4 | 38.778937 | 0.954225 | 0.998214 | 0.985092 | 0.843461 |
| SwinIR − Bicubic | +2.313490 | +0.022492 | +0.000000 | +0.001159 | +0.024551 |

화질은 좋아지지만 평균 localization은 나빠질 수도 있다고 예상했다. 실제로는 두 지표 모두 개선됐다. 이 조건에서 “SR은 전체적으로 anomaly detection을 악화시킨다”는 주장은 버렸다. 다음 질문은 “평균이 좋아져도 손해 보는 개별 결함은 있는가?”가 됐다. 근거: [`category_summary.csv`](../analysis/reporting/category_summary.csv), decision log §5, commit `08d74d9`.

## Stage 2 — 고정 fusion: 증거 보존 아이디어와 실패한 전역 해법

복원 과정에서 일부 증거가 약해진다면 degraded branch의 증거를 함께 두는 편이 안전할 수 있다고 생각했다. 별도 Branch B는 Hazelnut 정상 313장 fit, 78장 calibration, 테스트 110장, seed 11을 사용했다. calibration normal만으로 median/IQR 정규화와 F1 threshold를 만들고, degraded-only·restored-only·고정 0.5 평균·max fusion을 비교했다. 이는 Stage 1의 391장 bank와 다른 실험이다.

restored-only pooled AU-PRO는 0.841263이었다. 0.5 평균은 0.833354, max는 0.840552로 둘 다 낮았다. 0.5의 Image AUROC는 1.000000으로 restored-only 0.998571보다 높았지만, 사전 primary localization metric을 바꿀 이유는 아니었다. 당시에는 추가 GPU 추론을 동반한 가중치 탐색의 정보 가치가 낮다고 보류했다.

이후 저장된 예측만 이용하면 비용이 작고 0.5 한 점으로 전역 scalar fusion을 기각하기에는 부족하다는 이유로 5점 grid를 **실행 전에** 고정했다. `alpha`는 degraded 가중치이며 `{0, 0.25, 0.5, 0.75, 1}`의 pooled AU-PRO는 순서대로 `0.841263, 0.838005, 0.833354, 0.826236, 0.817486`이었다. 최선은 alpha 0, 즉 restored-only였다. 내부 최선인 0.25도 restored-only보다 0.003258 낮았다. 따라서 고정 비율을 전 sample의 안전장치로 쓰는 가정과 fine scalar search는 중단했다. 상황에 따라 원본/degraded 증거를 보존할 수 있다는 더 좁은 생각은 남겼지만, adaptive gating을 구현하거나 검증한 것은 아니다. 근거: [`fusion_weight_search.csv`](../analysis/hazelnut/fusion_weight_search/fusion_weight_search.csv), [`fusion_weight_search.md`](../analysis/hazelnut/fusion_weight_search/fusion_weight_search.md), protocol amendment, commits `fab60c3`, `e41ea1c`.

## Stage 3 — 평균에서 개별 결함으로 질문 이동

Branch A의 pooled AU-PRO는 +0.024551 올랐지만, Hazelnut anomalous image 70장 중 per-image AU-PRO가 감소한 이미지는 30장(42.86%)이었다. 40장은 개선 또는 동률이었다. 평균 per-image AU-PRO delta는 +0.012914로 양수이며, 이것은 pooled delta +0.024551과 다른 통계다.

평균 개선은 모든 결함의 안전을 뜻하지 않았다. 따라서 “평균 성능이 좋아지는가?”에서 “그 평균 속에서 어떤 sample이 손해를 보는가?”로 질문을 좁혔다. Test mask는 추론 후 분석에만 사용했다. 근거: [`summary.md`](../analysis/hazelnut/summary.md), [`cross_category_summary.json`](../analysis/hazelnut/cross_category_summary.json), commits `c265bad`, `4d7af50`.

## Stage 4 — failure taxonomy와 점수 감소 가정의 반례

Hazelnut 탐색 뒤 고정한 분류는 `delta per-image AU-PRO < 0`을 localization regression으로 한다. 그중 `delta ROI-background gap < 0`이면 suppression pattern, `>= 0`이면 geometry candidate다. 결과는 회귀 30장 중 suppression 14장, geometry candidate 16장이다. 이 이름은 anomaly-map 패턴을 기술하며 feature-space 원인을 증명하지 않는다. “strong failure” 14장을 전체 failure로 부르던 초기 명칭은 폐기했다.

반례 `hazelnut/test/crack/013.png`은 ROI mean `+0.108560`, ROI-background gap `+0.423456`, Pixel AUROC `+0.004057`인데 per-image AU-PRO는 `-0.076146`이었다. 반대로 성공 대조 `hole/006`은 map gap `-0.370210`에도 AU-PRO `+0.139957`이었다. ROI 절대 점수 또는 gap의 부호 하나로 localization 성공·실패를 판정하는 가정은 버렸다. 다음 질문은 spatial coverage와 feature-distance 변화가 이 분류에 어떻게 대응하는가였다. 근거: [`regression_taxonomy.csv`](../analysis/hazelnut/regression_taxonomy.csv), [`selected_cases.csv`](../analysis/hazelnut/qualitative_cases/selected_cases.csv), protocol §Regression taxonomy, commits `4d7af50`, `fed49a7`.

## Stage 5 — Hazelnut feature-distance 소규모 확인

사후에 고른 suppression 3장, geometry 3장, 성공 대조 3장에 동일한 391-normal bank를 적용했다. 공식 PatchCore feature grid의 FAISS squared-L2 NN 거리에서 결함 평균 `D_defect`, 배경 평균 `D_background`, 차이 `G_feature = D_defect − D_background`를 계산했다. GT는 28×28 grid cell별 연속 점유율에만 썼다. 18개 재계산 map은 저장 map과 일치했다.

| 선택군 | n | 평균 ΔD_defect | 평균 ΔD_background | 평균 ΔG_feature | ΔD_defect<0 및 ΔG_feature<0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| suppression | 3 | -0.612300 | -0.363200 | -0.249100 | 2/3 |
| geometry candidate | 3 | +0.004376 | -0.346242 | +0.350618 | 0/3 |
| success control | 3 | +0.134499 | -0.323525 | +0.458024 | 1/3 |

suppression 평균은 가설 방향이지만 개별 사례를 완전히 구분하지 못했다. 따라서 “suppression pattern = 결함 feature 제거 메커니즘”은 주장하지 않고 map-score suppression pattern이라는 이름만 남겼다. geometry 후보의 gap 증가도 공간 coverage 해석과 일치할 뿐 원인 증명은 아니다. 다음에는 Hazelnut에서 만든 규칙을 다른 category에 그대로 적용하기로 했다. 근거: [`nn_distance_selected_summary.md`](../analysis/hazelnut/nn_distance_selected_summary.md), [`nn_distance_selected.csv`](../analysis/hazelnut/nn_distance_selected.csv), decision log §16, commit `fed49a7`.

## Stage 6 — Screw cross-category stress

Screw는 결과를 보기 전에 full-category stress로 고정했다. 정상 학습 320장, 테스트 160장(정상 41, 이상 119), seed 11, 동일한 x4 SwinIR·PatchCore 설정과 Hazelnut taxonomy를 사용했다. Screw test로 checkpoint·threshold·fusion weight를 바꾸지 않았다.

| Screw Branch A | PSNR | SSIM | Image AUROC | Pixel AUROC | pooled AU-PRO@0.3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bicubic x4 | 35.507249 | 0.951995 | 0.480016 | 0.951112 | 0.801397 |
| SwinIR-S x4 | 37.944728 | 0.968421 | 0.678623 | 0.970602 | 0.856397 |
| SwinIR − Bicubic | +2.437479 | +0.016426 | +0.198606 | +0.019490 | +0.055000 |

이상 119장 중 localization regression은 23장(19.33%), improvement/tie는 96장이다. 회귀 23장은 모두 map-score suppression pattern이고 geometry candidate는 0장이다. Hazelnut처럼 평균 개선과 개별 손실이 공존했지만 subtype 구성은 달랐다. 결함 유형별로 `thread_side` 12/23, `thread_top` 8/23, `manipulated_front` 2/24, `scratch_head` 1/24, `scratch_neck` 0/25가 회귀했다. 이는 이 category의 기술 통계이며 thread 결함 일반화가 아니다. 다음에는 고정된 선택 사례의 feature distance를 확인했다. 근거: [`category_summary.csv`](../analysis/reporting/category_summary.csv), [`summary.json`](../analysis/screw/summary.json), [`defect_type_summary.csv`](../analysis/screw/defect_type_summary.csv), commits `27a06f1`, `9f78e9c`.

## Stage 7 — Screw 선택 사례의 feature evidence

사전에 정한 suppression 3장과 success control 3장만 동일한 320-normal bank로 재분석했다. 12개 재계산 anomaly map과 저장 map의 최대 절대 오차는 0.0이었다. GT occupancy, 모델, 전처리, CPU exact FAISS는 유지됐다.

| 선택군 | n | 평균 Δper-image AU-PRO | 평균 Δmap gap | 평균 ΔD_defect | 평균 ΔD_background | 평균 ΔG_feature | joint-negative |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| suppression | 3 | -0.147568 | -1.180901 | -1.824677 | -0.565741 | -1.258936 | 3/3 |
| success control | 3 | +0.307945 | +0.208704 | -0.292801 | -0.620176 | +0.327375 | 0/3 |

두 군 모두 normal-memory 거리가 감소할 수 있었다. 선택된 suppression 사례에서는 결함 거리 감소가 배경보다 커 상대 separation이 줄었고, 성공 대조에서는 배경 거리 감소가 더 컸다. 허용되는 해석은 “selected Screw suppression-pattern cases are consistent with relative defect-feature normalization”까지다. n=3/군인 선택 사례가 인과 또는 모집단 메커니즘을 증명하지 않는다. 근거: [`nn_distance_selected_summary.md`](../analysis/screw/nn_distance_selected_summary.md), [`nn_distance_execution_record.md`](../analysis/screw/nn_distance_execution_record.md), commits `360bcbd`, `1f93422`.

## Stage 8 — 현재 연구 질문이 생긴 경로

질문은 실험 결과에 따라 `Does super-resolution hurt anomaly detection?` → `Can aggregate improvement coexist with sample-level localization regression?` → `Under which defects do regressions occur, and what changes inside anomaly evidence?`로 이동했다. 두 category의 평균 개선, 다른 subtype 구성, 선택 사례의 제한적인 feature evidence 이후 현재 질문은 다음과 같다.

> 복원 목적함수의 차이가 영상 품질, 평균 anomaly localization, 그리고 개별 결함 증거 보존 사이의 trade-off에 영향을 미치는가?

이는 새 모델을 더 시험하기 위한 임의 확장이 아니다. 기존 결과로는 모든 복원이 같은 방식으로 결함 증거를 바꾸는지 알 수 없어서, 복원 성격 자체를 비교하는 다음 변수를 택했다. 아직 objective에 따른 실제 결과는 없다.

## Stage 9 — 현재 준비된 restoration-objective 연구

현재 HEAD `95d0977`은 Hazelnut 25장 development pilot의 **설계와 실행 경로만** 고정했다. 정상/good·crack·cut·hole·print에서 경로순 첫 5장씩의 manifest를 추론 전에 만들었다. 고정된 391-normal PatchCore bank를 다시 fit하지 않으며, 같은 56×56 LR 입력으로 Bicubic, SwinIR-S, 공식 `RRDB_PSNR_x4`, `RRDB_ESRGAN_x4`를 비교하도록 준비했다. 기존 Branch A의 Pillow bicubic과 혼동하지 않도록 이 pilot은 BasicSR MATLAB-compatible bicubic을 별도 프로토콜로 사용한다.

두 RRDB endpoint는 같은 architecture family와 x4 task를 공유하지만, 공식 기록상 PSNR 모델은 DF2K, ESRGAN 모델은 DF2K+OST로 학습 데이터도 다르다. 따라서 향후 차이가 나더라도 **손실 함수만의 인과 효과**로 해석할 수 없다. PSNR/SSIM/선택적 LPIPS, pooled AU-PRO@0.3, 개별 회귀와 map-gap 분류를 보되, 현재는 pilot inference와 새 detection metric이 없다. 25장 결과를 보고 차이가 실제로 있는지 확인한 뒤 full Hazelnut 진행 여부를 정한다. Capsule은 사용하지 않는다. 근거: [`RESTORATION_OBJECTIVE_STUDY.md`](../docs/RESTORATION_OBJECTIVE_STUDY.md), [`pilot_manifest.csv`](../analysis/restoration_objective_pilot/pilot_manifest.csv), [`PROGRESS.md`](../PROGRESS.md), commit `95d0977`.

## Stage 10 — 장기 산업 질문

최종 질문은 “가장 좋은 SR 모델은 무엇인가?”가 아니라 “언제 복원을 신뢰하고, 언제 degraded/original 결함 증거를 보존해야 하는가?”다. 고정 0.5/max 및 coarse scalar fusion은 현재 Hazelnut의 primary localization metric에서 restored-only를 이기지 못했다. 따라서 지금은 전역 가중치를 미세 조정하지 않는다. 향후 목적함수별 failure 차이가 실제로 확인될 때만, degraded·restored branch와 복원 신뢰도 또는 feature disagreement를 활용하는 selective evidence preservation을 별도 Phase C로 설계한다. 아직 구현·검증한 방법이 아니다.

## Stage 11 — 복원 endpoint 25장 pilot (2026-09-29 기록)

### Before running

질문은 “같은 x4 LR 이미지에서 공식 PSNR 지향 RRDB와 perceptual/GAN 지향 RRDB가 화질·anomaly localization의 다른 trade-off를 보이는가?”였다. 기존 SwinIR 분석은 평균 개선과 개별 결함 손실이 공존함을 보여줬지만, 복원 성격을 바꾸면 그 패턴이 달라지는지는 알 수 없었다. 결과를 보기 전 Hazelnut good/crack/cut/hole/print 각 5장, BasicSR MATLAB-compatible bicubic, 동일 56×56 LR, checksum-bound 391-normal PatchCore bank, pooled AU-PRO@0.3과 기존 taxonomy를 고정했다. 이번 실행에서 PatchCore fit과 F1 calibration은 없다. 근거: source commit `95d097799c10135a982dbddf91f97b71e3ca29e6`, [`pilot_manifest.csv`](../analysis/restoration_objective_pilot/pilot_manifest.csv), frozen design 문서.

### Observed result

수령 ZIP과 압축 해제 폴더의 179개 파일은 모두 바이트 단위로 일치했다. 저장 summary의 Bicubic / SwinIR / RRDB-PSNR / RRDB-ESRGAN pooled AU-PRO는 `0.791050335607512 / 0.8047205871264165 / 0.8075341064347228 / 0.8126297542363347`이다. 직접 비교 `RRDB-ESRGAN − RRDB-PSNR`은 PSNR `-2.622296262852899 dB`, SSIM `-0.03448956157055605`, LPIPS `-0.04259542234241963`, Image AUROC `0.0`, Pixel AUROC `+0.0005923647012515687`, pooled AU-PRO `+0.005095647801611869`였다. 네 Image AUROC는 모두 1.0이었다.

20장 anomaly에서 Bicubic 대비 per-image AU-PRO 회귀는 SwinIR 10장(4 suppression/6 geometry), RRDB-PSNR 8장(3/5), RRDB-ESRGAN 5장(4/1)이었다. 직접 RRDB pair의 per-image AU-PRO는 ESRGAN 우세 11장, PSNR 우세 9장, 동률 0장이고 평균 delta `+0.005228730586261677`, 중앙값 `+0.00060070251796146`, 범위 `[-0.026003721611708497, +0.0781594382510824]`이다. Stage 시간 합은 `342.2242296000477 s`이며 전체 wall time은 아니다.

### Unexpected / important observation

ESRGAN endpoint는 RRDB-PSNR보다 PSNR/SSIM이 크게 낮고 LPIPS는 크게 낮았다. 이 작은 pilot에서는 pooled localization과 regression count도 서로 달랐지만 per-image 직접 승패는 11:9로 섞여 있다. 품질 지표의 순위 하나를 downstream 순위로 대신할 수 없다. Image AUROC 1.0은 이 비교에서 변별력이 없다.

### Interpretation

공식 endpoint 간 fidelity/perceptual-quality trade-off는 관찰됐다. Downstream localization 차이는 신호 수준이며 20장 anomaly로 안정적인 모집단 효과를 주장할 수 없다. “objective만의 인과 효과”라는 표현은 약화·재구성했다. 두 checkpoint는 loss뿐 아니라 학습 데이터(DF2K와 DF2K+OST)도 다르다. 반면 “화질 개선이 결함 증거 보존을 자동 보장하지 않는다”는 질문은 유지한다. 이번 결과는 새 bicubic kernel을 쓰므로 과거 Branch A와 직접 동일 조건의 숫자로 합치지 않는다.

### Decision

기존 GO 규칙에 맞춰 full 110-image Hazelnut endpoint 평가를 **다음 별도 작업으로 준비**한다. 같은 development category의 확대 확인이며 최종 독립 검증은 아니다. 이번 commit에서는 full inference, feature NN 분석, Phase C gating, Capsule, 새 degradation·detector를 열지 않는다.

### Evidence

- tracked: [`PILOT_RESULT.md`](../analysis/restoration_objective_pilot/PILOT_RESULT.md), [`EXECUTION_RECORD.md`](../analysis/restoration_objective_pilot/EXECUTION_RECORD.md), [`summary.csv`](../analysis/restoration_objective_pilot/results/summary.csv), [`objective_pair_per_image.csv`](../analysis/restoration_objective_pilot/results/objective_pair_per_image.csv), [`regression_taxonomy.csv`](../analysis/restoration_objective_pilot/results/regression_taxonomy.csv).
- source commit: `95d097799c10135a982dbddf91f97b71e3ca29e6`.
- result-recording commit: `ead257aa82430603116ab5be98933e7bbea624f6`.
- local/team-only ZIP SHA-256: `cab69ad9b9ad4b54177ff8cdb575fdb5244f13aa68a68006cc83fe4a222e0d46`; 원본 `results.json` SHA-256: `c1c3189604916665639db57568a4be4b078bdb9a000cf839cc3cedf2464669b8`. 나머지 raw NPZ 해시는 tracked hash ledger에 있다.

## 현재 고정한 결정

| Item | Current status | Why |
| --- | --- | --- |
| PatchCore | 고정 evaluator | 복원 branch 비교에서 detector 변화를 섞지 않기 위해 |
| pooled AU-PRO@0.3 | primary localization metric | 기존 200-threshold 구현과 선택 규칙 유지 |
| Hazelnut | development/exploration | 질문·taxonomy 형성에 이미 사용 |
| Screw | 사전 고정 cross-category stress, 완료 | 동일 규칙의 다른 결함 형태 확인 |
| Capsule | untouched final validation | 방법·지표·선택 규칙 동결 전 사용 금지 |
| 고정 anomaly-map fusion | negative ablation, 추가 fine search 중단 | 0.5/max와 5점 grid에서 restored-only를 넘지 못함 |
| feature suppression causal claim | 중단 | 선택 사례가 인과·모집단 원인을 확정하지 못함 |
| suppression | descriptive map-score pattern | AU-PRO와 ROI-background gap의 관찰 부호만 정의 |
| Grid | 보류 | 별도의 미해결 메커니즘을 시험할 근거가 생길 때만 |
| SurgClean | bounded future extension | 데이터·split·정합·checkpoint entry gate 미충족 |

## 버리지 말아야 할 negative results

1. **“SR은 전반적으로 AD를 해친다”는 가설은 지지되지 않았다.** 예상: 화질 상승과 평균 localization 하락. 실제: Hazelnut PSNR `+2.313490 dB`, pooled AU-PRO `+0.024551`; Screw `+2.437479 dB`, `+0.055000`. 다음 실험은 평균 악화 여부가 아니라 개별 회귀를 보게 됐다.
2. **고정 0.5/max fusion은 restored-only를 넘지 못했다.** 예상: degraded 증거 보존으로 localization 개선. 실제 Branch B pooled AU-PRO restored `0.841263`, 0.5 `0.833354`, max `0.840552`. 다음에는 전 sample 공통 결합 대신 손실이 발생하는 조건을 찾았다.
3. **fine scalar search는 현재 정당화되지 않는다.** 예상: 0.5를 벗어난 내부 가중치가 개선할 수 있음. 실제 5점 grid의 내부 최고 alpha `0.25`는 `0.838005`, restored-only보다 `0.003258` 낮았다. 추가 fine search·adaptive gating은 하지 않았다.
4. **작은 defect일수록 실패한다는 가설은 지지되지 않았다.** 예상: 작은 면적에서 ROI score 감소/실패 증가. 실제 Hazelnut Spearman(area ratio, ΔROI mean) `-0.0318`, suppression median area ratio `0.02286`, 나머지 `0.02091`. 다음에는 size보다 morphology와 map 변화를 살폈다.
5. **ROI raw mean selector는 localization oracle이 아니다.** 예상: GT ROI mean이 큰 branch 선택이 상한에 가까울 것. 실제 그 선택의 pooled AU-PRO `0.831213`은 restored-only `0.843461`보다 낮았다. per-image AU-PRO screening headroom도 `+0.003655`에 그쳤고, AU-PRO로 고른 whole-map 조합의 pooled delta는 `-0.003003`이었다. 따라서 ROI-mean 파일은 역사적 예비 결과로 남기고 final upper bound로 사용하지 않는다.
6. **Hazelnut feature distance는 subtype을 완전히 분리하지 않았다.** 예상: suppression은 joint-negative, 성공 대조는 그렇지 않을 것. 실제 joint-negative suppression `2/3`, geometry `0/3`, success `1/3`. 다음에는 인과 명칭을 버리고 Screw의 사전 고정 규칙으로 이동했다.
7. **절대 anomaly-map score 감소가 localization failure를 뜻하지 않는다.** 예상: ROI score가 낮아진 sample이 곧 실패. 실제 ROI mean 감소 `49/70`이지만 AU-PRO 감소는 `30/70`; 평균 ΔROI mean `-0.180891`, 평균 Δgap `+0.178580`. `hole/006`은 gap `-0.370210`에도 AU-PRO `+0.139957`. 다음 분석의 회귀 기준을 per-image AU-PRO로 고정했다.

## Research numerical snapshot

각 delta는 SwinIR-S x4 − Bicubic x4이며, aggregate AU-PRO는 pooled 값이다. 두 category 모두 Branch A 전체 테스트다.

| Category | Train / test / anomaly | ΔPSNR dB | ΔSSIM | ΔPixel AUROC | Δpooled AU-PRO@0.3 | Per-image regression | Suppression | Geometry candidate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hazelnut | 391 / 110 / 70 | +2.313490 | +0.022492 | +0.001159 | +0.024551 | 30/70 (42.86%) | 14 | 16 |
| Screw | 320 / 160 / 119 | +2.437479 | +0.016426 | +0.019490 | +0.055000 | 23/119 (19.33%) | 23 | 0 |

선택 사례 feature-distance 평균은 FAISS squared-L2이며 전체 category 추정치가 아니다.

| Category / selected subtype | n | 평균 ΔD_defect | 평균 ΔD_background | 평균 ΔG_feature | joint-negative |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hazelnut suppression | 3 | -0.612300 | -0.363200 | -0.249100 | 2/3 |
| Hazelnut geometry candidate | 3 | +0.004376 | -0.346242 | +0.350618 | 0/3 |
| Hazelnut success control | 3 | +0.134499 | -0.323525 | +0.458024 | 1/3 |
| Screw suppression | 3 | -1.824677 | -0.565741 | -1.258936 | 3/3 |
| Screw success control | 3 | -0.292801 | -0.620176 | +0.327375 | 0/3 |

---

## YYYY-MM-DD — Experiment / Decision

### Before running
Research question:

Hypothesis:

Why this experiment:

What is frozen:

Expected informative outcomes:

### Result
Actual numeric results:

Unexpected observations:

Visual observations:

### Interpretation
What this result supports:

What this result does NOT support:

Previous hypothesis status: retained / weakened / rejected

### Decision
What we keep:

What we stop:

### New question
What question did this result create?

### Next experiment
Why is this the highest-information next step?

### Evidence
- files:
- commit:
- plots:
- raw artifact hashes:

---
## Stage 12 — Full Hazelnut endpoint confirmation design (local-only, before inference)

### Why this question emerged

The frozen 25-image pilot showed a clear PSNR/SSIM versus LPIPS trade-off and a possible localization difference, but 20 anomalous images and an 11/9 direct AU-PRO split cannot establish endpoint ranking. The next question is whether that signal persists across the complete Hazelnut test set.

### Hypothesis

Endpoint-dependent image-quality character may persist. Localization differences may persist, weaken, or reverse; all three outcomes are informative.

### Frozen conditions

All 110 Hazelnut test images (40 normal, 70 anomalous), same MATLAB-compatible LR and four variants, same checksum-bound 391-normal bank, metrics/taxonomy, no fit, no tuning. Full manifest SHA-256: `2ddb62748c750b3e4fae2b4b0b0cb4f3c354fd02faac74c95117afe1b3e116cc`.

### Interpretation plan

Case A: quality trade-off and localization direction persist; retain a Hazelnut endpoint-dependent finding without causal wording. Case B: quality trade-off persists but localization difference is small/uncertain; no stable localization ranking. Case C: localization reverses; record sample sensitivity and do not search another subset. Follow the frozen full protocol rather than choosing a new threshold after results.

### What remains closed

Phase C gating, Capsule, new degradation, new detector, and new endpoint models. Clean Branch A is contextual only; historical source image bytes were not checksum-bound.

### Evidence

Starting pilot result commit `ead257aa82430603116ab5be98933e7bbea624f6`; `analysis/restoration_objective_pilot/PILOT_RESULT.md`; `analysis/restoration_objective_pilot/EXECUTION_RECORD.md`; `docs/RESTORATION_ENDPOINT_FULL_HAZELNUT.md`; `analysis/restoration_objective_full/full_manifest.csv`. No full inference result exists in this stage.
## Stage 12b — Pre-inference adversarial-review hardening (local-only, 2026-09-30)

An external adversarial design review occurred after preparation commit `982cbe043fd22c3b688caebc6573cdfa8d347e85` and **before viewing any full110 result**. The private source review is stored outside the repository at the user's OneDrive Desktop as `RESEARCH_REVIEW_full110.md`; it was read after the hardening commit and is not copied to tracked files. The user-requested hardening rules, rather than every suggestion in the private review, define this preregistration amendment.

The review pointed out that strict-sign regression can exaggerate tiny AU-PRO losses, especially in Hazelnut; suppression labels need the negative-gap base rate among both regression and non-regression images; selected NN-distance cases are consistency evidence, not independent mechanism proof; the initial A/B/C prose left discretion; and derived-analysis code should be frozen before the GPU result.

Decision: retain the same scientific question and full110 experiment. Before inference, add the fixed tau sensitivity grid `{0, 0.005, 0.01, 0.02, 0.05}`, deterministic A/B/C localization rule, pilot20 overlap and pilot-unseen50 within-category reporting, taxonomy gap base rates, and a saved-CSV-only analysis script. The original strict-sign taxonomy and primary pooled AU-PRO stay unchanged. Historical Hazelnut/Screw tau summaries, if ever reported, are post-hoc; the pilot tau table generated for code validation does not change the pilot GO decision.

Phase C, Capsule, new degradation/detector/endpoints, and mechanism claims remain closed. Evidence: `docs/RESTORATION_ENDPOINT_FULL_HAZELNUT.md` dated amendment and `scripts/analyze_restoration_endpoint_full.py`. No full110 inference or result existed when this addendum was written.

## Stage 12c — Second adversarial review before full110 (local-only, 2026-10-01)

This addendum follows `607510bf39fd67d5b24f01c83fbe509092ab671c` and precedes any full110 inference/result. The second private review file was not present under local `notes/`; no whole-PC search was performed. Accepted findings come from the user's final incremental review request; the private review path remains locally excluded.

Review observations: strict-sign regression can exaggerate effect size; baseline/ceiling association is a plausible alternative explanation; the suppression taxonomy needs its high negative-gap base-rate context; selected NN analysis is not independent mechanism evidence because anomaly maps derive from NN distances. The pilot endpoint localization difference is small and mixed. Full110 remains worth one execution because positive, small/mixed, or reversed evidence can all answer the fixed question.

Research decisions: keep the main question and all frozen scientific inputs. Move the headline from regression existence to magnitude/distribution and quality–localization relationship. Reuse tau sensitivity and bootstrap rather than repeating them. Add near-zero counts/quantiles, baseline terciles, explicit taxonomy 2×2, D50 sign confirmation and secondary unseen85 saved-map metrics. Strengthen execution provenance without changing inference. Do not add a pooled bootstrap, Wilcoxon, arbitrary 8-pixel ROI fidelity, or rho success threshold. Close further NN/Capsule/Phase C/new-GPU expansion after one valid full110 for every outcome. These changes are preregistered before results, not a reinterpretation after the GPU run.

## Stage 13 — Completed study and thesis synthesis (local-only, 2026-10-03)

Full110 evidence at `2dcac3f2c0c8418e2909641c473cd9498600929e` yields case B/B-uncertain: pooled ESRGAN−PSNR delta `+0.006790420`, mean-image D70 `+0.005109973`, 95% CI `[-0.000907432, +0.013954090]`, and D50 `+0.005062470`. Quality trade-off persists: ΔPSNR `-2.696301 dB`, ΔLPIPS `-0.044133`. These observations do not establish stable localization ranking, equality, or objective-only causality. Pilot overlap is within tolerance, not bitwise exact. The local checkout has tracked derived records but no raw full110 NPZ for independent recomputation.

Retain controlled mean recovery, heterogeneous magnitude/distribution, baseline/ceiling association, and quality–localization reporting as the thesis framing. Taxonomy and selected NN cases are supporting diagnostics; fusion is a bounded negative ablation. Keep historical Pillow and MATLAB endpoint families separate. Preserve preregistration, all results, and A/B/C decisions. The runtime prose correction compares like-scoped stages (`9.596×`), not wall-clock against stages; the `2.181×` per-image cost increase has no established cause.

The experimental phase is closed for this graduation project. No additional GPU run, endpoint, NN case, adaptive gating, Capsule, SurgClean, new degradation/detector, or rerun follows. Remaining work is source-backed thesis/presentation synthesis and evidence verification. This note and private reviews remain excluded from Git and must not be published.

## Stage 14 — CPU bottleneck and separate PCB readiness question (retrospective update, 2026-10-17)

The notebook had not been appended after Stage 13. The following entries are retrospective summaries of stored records, not claims of preregistration on earlier dates. Subsequent user requests separately authorized profiling and PCB engineering preparation; they do not revise full110 B/B-uncertain or turn negative gating into a positive finding.

The fixed ten-image CPU profiling record distinguishes two instrumented repeats, two warmup images and a separate uninstrumented pass. Stored-anchor comparison reported 64 exact map/score matches. Mean degraded detector time was 8.750 s, including 8.002 s CPU exact FAISS and 0.723 s backbone/embedding; FAISS is approximately 91% of that detector denominator. This is not a CUDA or production-line benchmark. Conditional restoration was a cost estimate, not a demonstrated trigger or saving.

Actual-browser review checked saved-artifact connections, common map scales, normal-image AU-PRO N/A, GT overlays, missing RGB and export. PCB inventory suggested pcb2 with 721 normal fit / 180 normal calibration / 200 test (100 normal, 100 anomaly). However, central crop removed GT pixels in 9/100 anomaly images and entire resized-mask components in 3/100. Nonempty-mask checking alone was insufficient. The next question became geometry validity before a PCB model result, not selecting preprocessing by test performance.

Evidence: `analysis/profiling_results_demo/hazelnut-ten-20261015/`; `analysis/profiling_results_demo/review-7ee19a9/REVIEW.md`; `PCB_CROP_AUDIT.csv`; `PCB_SPLIT_AUDIT.json`; original checkout `PROGRESS.md`. Team members' earlier pcb2 use remains unconfirmed.

## Stage 15 — Full FOV does not guarantee small-component retention (retrospective update, 2026-10-17)

The separate full-frame224/bilinear-RGB/nearest-GT draft kept the whole FOV but lost 19 of 324 original 8-connected GT IDs across 9 images. No anomaly mask became fully empty. Lost components had original area 1–28 pixels. The draft remained BLOCKED_GEOMETRY; no GT correction, exclusion or model inference was used to make it pass.

The next single candidate used native224 tiles, maximum stride192 and deterministic evenly spaced half-up-rounded starts, independent of GT. The audit recorded exact RGB/GT/ID reconstruction for 1,101 images; coverage 1–4; all 324 components and the previously lost19 IDs retained with exact original areas. Each board has48 tiles: fit34,608 / calibration8,640 / test9,600 tiles. This established geometry identity, not detection quality or full-pilot readiness.

Unchanged IdentitySampler payload would require 27,132,672 vectors ×1,024×4 bytes =103.503 GiB, with a possible three-buffer310.509 GiB scenario. These were estimates, not RSS. A separately authorized bounded-bank draft then froze uniform global patch selection, seed11/cap262,144/chunk8,192, rather than silently changing the earlier sampler. Bank payload is1GiB; actual full bank is still NOT_CREATED. This is a separate protocol family from past crop/full-frame224 studies.

Evidence: geometry v0.1/v0.2 reports under `analysis/pcb_geometry/`; `analysis/pcb_bank_budget/pcb2-uniform-cap262144-20261016/`; protocol v0.3; original `PROGRESS.md`. Local geometry commits `195df54`, `41d45ca` remain historical evidence, not assumed available from the public handoff history.

## Stage 16 — Thin model connection and normal-only board rules (retrospective update, 2026-10-17)

Synthetic integration verified deterministic tile ordering, bounded-bank streaming, board overlap-mean maps, max original tile scores, persistence and bank immutability. Separate real-model adapters and a guarded raw-smoke path followed; the full-pilot path remained blocked before model construction. Fake-model/CPU tests do not establish real model performance.

The later explicit user request adopted v0.6: one clean-normal bank shared by three variants; raw maps merged before calibration; independent image/map robust statistics per variant from all180 calibration-normal boards; pooled board pixels count each physical pixel once; existing median/IQR and std/unit fallbacks; normal quantile0.99 when required. Native RGB overlap reconstruction precedes one PSNR/SSIM computation per board. GT is evaluation-only. Existing AU-PRO4-connectivity/threshold/integration definitions remain unchanged, distinct from the geometry audit's8-connected IDs.

Synthetic board-lifecycle verification recorded243 tests passed,31 related no-Torch/FAISS tests passed and CPU smoke success. Native calibration/evaluation remained memory estimates (about6.09/18.42GiB), not measured peaks. Actual full bank/calibration and the full raw/RGB producer were not created or enabled.

Evidence: protocols v0.4–v0.6; `docs/PCB_TILED_GPU_HANDOFF.md`; `docs/PCB_BOARD_LIFECYCLE_HANDOFF.md`; `analysis/pcb_board_pipeline/pcb2-board-lifecycle-20261017/`; original `PROGRESS.md`.

## Stage 17 — Received CUDA raw smoke and public input delivery (2026-10-17)

Received run `pcb-tiled-cuda-raw-smoke-20261017-140311` was reviewed from the immutable ZIP and separate preflight. Stored verification lists27 passing checks: bank(37,632,1,024) float32,9 native(1,070,1,404) maps,12 stored-file hashes and matching separate/embedded preflight. This is limited raw smoke, not full bank, calibration or research performance. Preserve `source_worktree_dirty=true`. Historical peak RAM/VRAM was not measured; post-exit0MiB does not recover a peak. Run-id/ZIP timestamps are not precise perf_counter timing evidence.

GPU handoff failed earlier because local-only code/history and inputs were absent on the teammate machine. Public delivery therefore used a sanitized snapshot rather than pushing the original unpublished branch history. Public `exp/pcb-tiled-gpu-handoff` ends at `d732574f613cd7d79719a8fb557a28886b6cd28c`. Licensed pcb2 inputs are a Release asset, not Git source: `pcb2-inputs-v1/visa-pcb2-frozen-v1.zip`,274,645,313 bytes, SHA256 `bf5fcce555140be6b460ecbfac849c5580fafcc64c4c7093308448f05b484fc5`. Setup verifies frozen files and retrieves pinned publisher checkpoints; raw predictions and weights are not newly committed as source.

Evidence: local `outputs/pcb-smoke-received-review-20261017/verification.json`; received ZIP/preflight originals; public `configs/pcb_gpu_inputs.json` and `scripts/setup_pcb_gpu_inputs.py`.

## Stage 18 — Native postprocessing resource rehearsal before execution approval (2026-10-17)

Raw CUDA smoke does not demonstrate that exact native calibration/evaluation fits RAM. The next CPU tool therefore uses explicitly synthetic scores/RGB and separate sequential calibration/normalization/quality/evaluation processes. Native evaluation alone reads hash-verified original GT to preserve its region-memory structure. It never creates models/FAISS/banks or exports synthetic research metrics. Default is preflight only; `--execute` is explicit; the existing full-pilot block stays in place.

Published `exp/pcb-native-memory-readiness` commit `bb22cf8a1f7073229ff615b67b3df2a100763827` is one commit after public d732574. Verification records280 tests passed/1 optional-data skip,22 focused no-Torch/FAISS tests passed and CPU smoke success. Small2-calibration/2-test rehearsal completed12 workers, with maximum individual OS peak working set109,289,472 bytes (104.23MiB), not a summed/native/VRAM peak. Native PRE-FLIGHT ONLY returned BLOCKED_MEMORY; no native large arrays or workers were created locally.

The native technical gate currently needs21,923,497,568 available RAM bytes (20.42GiB, including2GiB reserve) and4,681,310,976 free disk bytes (4.36GiB, including1GiB margin).32GB installed RAM does not guarantee passage. Preserve blocked attempts; do not weaken guards, change OS/pagefile settings or terminate other users' processes. Synthetic completion is `MEMORY_REHEARSAL_COMPLETE_NOT_FULL_APPROVAL`, not full-pilot authorization or a general upper bound.

On this update, a fresh GitHub `ls-remote` matched both public branch SHAs above; the Release asset HEAD returned HTTP200 and Content-Length274,645,313. The asset was not downloaded/hash-recomputed again in this check. The source checkout contains the native CLI/module/tests, v0.6, lifecycle handoff, memory handoff and frozen reference files. No new push is needed for this handoff. This notebook is still ignored by local `.git/info/exclude`, untracked and absent from `git log --all -- notes/RESEARCH_EVOLUTION_LOCAL.md`.

Decision/next step: send the GPU operator the existing-folder CPU memory prompt (small execute → native preflight → conditional native execute only on a fresh passing gate). Receive resource JSON/CSV/logs, not synthetic arrays or dataset. Then update this notebook from the actual report and separately review native memory evidence and full producer/process integration. No automatic full pilot, fine weight/gating search or retrospective change to earlier scientific conclusions follows.

Evidence: public `docs/PCB_NATIVE_MEMORY_HANDOFF.md`; `analysis/pcb_native_memory/implementation-20261017/VERIFICATION.md`; local published worktree `outputs/pcb-native-memory-readiness-20261017/outputs/pcb-native-memory/{small-execute-20261017-final,native-preflight-20261017-final}/`.

## Stage 19 — Separate local integration from teammate resource measurement (2026-10-17, before implementation)

The user requested separate maintenance of two records. This private notebook keeps evidence-backed hypothesis changes, alternatives considered, reasons for decisions and their limits. `PROGRESS.md` keeps completed implementation, executed checks/results, reproducibility references and remaining tasks. Neither document should present proposed work as completed or expose private internal reasoning. This notebook remains ignored/untracked; PROGRESS is a normal tracked project document.

Native postprocessing RAM remains unmeasured while the teammate prepares the resource rehearsal. Waiting for that report does not prevent small synthetic CPU development of the missing streaming producer/process connections. The selected next local task is therefore full-producer integration with fake-model fixtures, not another geometry/model experiment or automatic full execution. This is a planned task only; no producer implementation or new tests are claimed in this entry.

The integration must reuse the frozen bank selection/geometry/normal-only calibration and existing exact evaluator; consume each restoration output once for both prediction and quality; bound embedding chunks; release model/index references before large evaluation; and preserve a full-pilot block before real model construction. Source completeness, native RAM feasibility and actual-model resource evidence remain separate gates. The teammate's future synthetic native success would address only one scenario, not approve full execution or supply PCB research performance.

On completing the future local task, append actual implementation/testing/failures and artifact/commit references to PROGRESS, and append the decision, supporting evidence, unresolved alternatives and next question here. Check this notebook's local exclusion before any commit; never stage it or transfer it into public worktrees. In a different code worktree, update that branch's public PROGRESS and then mirror only the factual checkpoint into the original local PROGRESS without overwriting unrelated edits. The private notebook remains at the original local path.

Evidence/status: public base bb22cf8, preserved original79a1c0f, current handoff checkpoint in original `PROGRESS.md`, and Stage18 resource verification. This update changes only the two documentation files, not code, predictions or experimental rules; no commit/push or actual model/native execution is part of this update.

## Stage 20 — Streaming/RGB/process candidate verified locally (2026-10-17)

The user executed the Stage19 task prompt. Implemented on separate local branch `exp/pcb-full-producer-integration`, commit `676b071178967381261a886599998ce56b31becc`, based on public bb22cf8 in the existing memory-readiness worktree. Original exp/profiling-results-demo/79a1c0f and its prior PROGRESS edits were preserved. New commit is local only; no push or original-history publication occurred.

Reason for this connection: existing bounded bank, raw merger and v0.6 postprocessing already passed their own checks, but the old generated lifecycle checker recomputed a fake transform for quality. That was not evidence that a real restorer would execute only once. The new producer sends each prepared tile both to prediction and a lossless uint8 spool. A separate quality process consumes saved native references/canonical tile sequences without a model/transform callback. One clean bank is streamed/bound once for the three named variants; no whole fit-feature cohort is accumulated. The existing exact bank/merger/calibration/quality/evaluator and full-pilot block have no code diff.

Chosen trade-off: retain actual produced tiles and original test RGB until every downstream worker succeeds. Rerunning restoration merely for quality was rejected because it duplicates model work and may not represent the originally predicted RGB. A more elaborate compressed/reconstructed-board storage alternative was not implemented; preserving original canonical tiles gives direct equality/hash validation with the existing quality API at an explicit disk cost. Existing assemble_board retains one board's map snapshots, and the quality reader holds one board/variant tile tensor; neither is hidden behind an mmap claim.

Observed small synthetic evidence:2 normal fit/2 normal calibration/2 test boards at336x224;16 observed vectors,7 retained;12 maps; one factory and one bank bind. Transform8 calls per variant, zero further transform calls for quality. Seven sequential workers exited0, fake model/index/scorer weak references released,14 recorded source hashes match, and2258944 consumed RGB bytes including NPY headers were cleaned after validation. Largest individual OS process-lifetime working set109326336 bytes (104.26MiB) is not native/combined/VRAM peak. Full pytest294 passed/1 optional-data skip; no-Torch/FAISS new tests14 passed; CPU smoke passed with2 rows; diff and protected-source comparisons passed.

Implementation/testing corrections: failure injection initially intercepted Git metadata as well as stage launches; scoped it to owned workers. Error JSON containing a Korean path needed explicit UTF-8 in tests. A helper held closed NumPy mmap arrays, causing pytest repr to hit a Windows access violation; replaced retained arrays with mmap-handle observations. Final tests include partial-mapping closure, resource/index/overwrite/split/checksum guards and later-worker failure preservation. These were harness/implementation verification issues, not research results or evidence about native model stability.

Resource consequence: native RGB spool adds5236574400 bytes (4.877GiB). Total retained file payload is20373754176 bytes (18.975GiB) before RGB cleanup and15137179776 bytes (14.098GiB) afterward; original data/checkpoints, headers/logs, failed runs and margins are extra. Visible producer build/prediction RAM scenarios2.012/3.038GiB exclude actual model/runtime/FAISS scratch/page cache. The prior memory rehearsal's4.36GiB disk gate cannot certify this different producer topology. Existing calibration/evaluation envelopes and frozen4-connected region estimate remain unchanged; no native RGB/GT or full arrays were loaded here.

Decision: local synthetic producer/process gap is addressed, not full execution readiness. Keep synthetic-only input guard, no default real factory/data CLI, and old full block before real construction. Native postprocessing measurement, actual model RSS/VRAM, producer disk budgeting, hash-audited real RGB/GT callback binding and explicit final approval are still separate gates. The teammate report has not arrived; actual full PCB bank/calibration remain NOT_CREATED. No tuning, new metric, actual model/FAISS/SR run, native experiment or change to negative gating/full110 B/B-uncertain occurred.

Next question: does the adequate-RAM teammate machine pass the unchanged native resource rehearsal with real GT structure, and what measured/remaining resource evidence is still needed for a separately approved full producer? Review that returned report before any real execution. PROGRESS receives the factual completion checkpoint; this private note retains the rationale/trade-off and remains ignored/untracked, never committed or copied to the public branch.

Evidence: implementation worktree `docs/PCB_FULL_PRODUCER_HANDOFF.md`; `analysis/pcb_full_producer/implementation-20261017/VERIFICATION.md`; ignored `outputs/pcb-full-producer/pcb-producer-synthetic-20261017-final/`; full/no-Torch logs `outputs/producer-full-pytest-final.log` and `outputs/producer-notorch-final.log`. Pre-commit synthetic records correctly retain bb22cf8/dirty=true and content hashes; publication/local-commit metadata was not retroactively substituted.

## Stage 21 — Teammate report confirms pre-allocation RAM blocker, not native peak (2026-10-17)

Received pcb-native-memory-review-20261017.zip; immutable SHA25689c601ff76498995dc508db1b16cf355c62aa197922069246e3d9a19ab2dc84d. Independent local metadata audit passes171 assertions and the existing completion loader.12 executable hashes and5 frozen references match; protocol/CSV/12 stage hashes and numeric records agree. These are consistency/integrity checks, not cryptographic proof of remote execution. No submitted instructions/code were executed and no native/model experiment was run here.

Observed: small generated336x224 case completes12 workers on the teammate host, no model runtime imports. Largest individual OS lifetime peak110030848bytes(104.93MiB); worker action sum6.259233400s versus parent launch-to-exit sum10.372911200s. Native only ran preflight: requires21923497568 available bytes, has20398669824, missing1524827744 (1.42GiB); rehearsal disk guard passes. Native execute_requested=false, stages empty. Thus the report has arrived but native evaluator working set is still unmeasured.32GB installed RAM/report does not establish enough currently available RAM, and this was not an OOM or GPU failure.

Review corrections are distinct from execution validity. The teammate Markdown says worker6.56s; actual12 records sum6.26s. Its19.78GiB envelope phrase mixes decimal GB and GiB; correct18.42GiB plus2GiB reserve yields20.42GiB. Parent minimum20275834880 differs from worker20277796864bytes. The protocol does not include run_legacy_patchcore.py or hash logs, despite broader prose. Dirty=true cause, setup1202-file verification and remote empty-workspace observation cannot be independently established by the included metadata. Preserve raw records and dirty flag; add errata rather than altering supplied evidence. No scientific metric/result is affected.

Decision rationale: retain the unchanged native guard and evaluator. First let the operator independently arrange sufficient available RAM and rerun preflight, or use a more available-RAM host if needed. Do not infer a safe native peak from the small105MiB process figure, reduce reserve/GT/cohort/metric, or reopen model/bank/geometry choices to make this artifact pass. No new code push or GPU computation is necessary for that next resource check. Passing native later still cannot approve the producer's different18.975GiB disk payload, actual model peak, real callback wiring or final full pilot.

This narrows the remaining question from whether the teammate received runnable code to whether the unchanged native workload can execute under the required available-RAM budget. No source changes, full bank/calibration, inference, GPU/FAISS experiment or commit/push follows. Canonical PROGRESS gets the actual state/numeric corrections; this note retains the decision rationale privately. Evidence: ignored `outputs/pcb-native-memory-received-review-20261017/{REVIEW.md,verification.json,received/}`; incoming ZIP and review remain byte-preserved.

## Stage 22 — Local host cannot satisfy the native physical-RAM gate (2026-10-17)

The user asked whether their own local PC could perform the native rehearsal instead. Read-only Windows GlobalMemoryStatusEx measured total OS-visible physical RAM16671768576bytes(15.527GiB) and currently available3586400256bytes(3.340GiB). Recomputed unchanged native plan requires21923497568 available bytes(20.418GiB). Requirement exceeds total physical RAM by4.891GiB, not merely current free RAM; even releasing local application memory cannot meet that gate. Do not confuse pagefile/commit/VRAM with physical availability.

Decision: keep small synthetic tests and development local; native verification belongs on a host with sufficient currently available RAM, such as the teammate machine after independently arranged resources and fresh preflight. No guard/reserve/metric/cohort reduction or local native allocation follows. Available3.340GiB is only the measurement-time snapshot. PROGRESS receives the numeric host constraint; no model/OS/process/commit/push action occurred. The initial one-line diagnostic had a shell quoting syntax error, corrected before the successful read-only measurement; no allocation or system mutation resulted.

## Stage 23 — Retry package validates another blocked snapshot, not cleanup causality (2026-10-18)

Received pcb-native-memory-retry-review-20261017.zip, SHA25672fd90117d29b3c01507ef3785af1ab103afaf112e50186e09234bbf31b852d6.70 metadata assertions pass:27 small files exactly reuse the earlier201510 package, existing completion loader validates those bytes, new235448 native protocol hash matches status, source12/reference5 hashes and recalculated plan agree with earlier/local code. Small reuse does not constitute a new small run. Native execute_requested=false/stages empty; no native/model/GT evaluation occurred in this review.

Observed retry available19276013568bytes(17.95GiB), required21923497568bytes(20.42GiB), shortfall2647484000bytes(2.47GiB). Available decreased1122656256bytes from first preflight; rehearsal disk gate passes. Stable recorded code/plan makes changed availability the direct guard input, but neither a process-level cause nor the operator's cleanup actions can be inferred from two snapshots. No memory-consumer list or raw Git status is included. Dirty=true is retained without asserting its origin.

Time/envelope/hash-range corrections in the retry Markdown mostly match raw records. Remaining measurement-scope correction: small preflight snapshot20406476800bytes is not the parent runtime minimum20275834880; worker minimum is20277796864. Keep all three concepts distinct rather than relabeling a snapshot as a runtime minimum. This prose issue does not alter BLOCKED_MEMORY or require repeating a valid small case.

Decision: move from repeated preflight attempts to read-only host memory diagnosis and operator-managed resource cleanup, or another adequate-RAM host. Do not blame the AI model, infer no cleanup was attempted, lower reserve or revisit geometry/metric/bank choices merely to pass. Fresh preflight after a real resource-state change still gates any native execute; full model/producer approval remains separate. Original PROGRESS records delivered artifact/results/limits; this private notebook records why the next action is diagnosis rather than another identical retry. No commit/push, submitted-command execution, source change or native allocation occurred. Evidence: ignored outputs/pcb-native-memory-retry-received-review-20261018/{REVIEW.md,verification.json,verify_retry.py}; incoming ZIP preserved.

## Stage 24 — Native-size rehearsal succeeded; production wrapper is a separate gate (2026-10-18)

Received cleanup/execute ZIP SHA256b175bcfd5f29e53ae2552124754f2aa66939cec70a17aacd3f85732cca58c55e.206 metadata assertions plus the existing completion loader pass. Unlike earlier returns, this contains separate passing native preflight011907 and execute011933 with12 completed native workers. Code12/reference5 hashes, counts721/180/200,1404x1070,dtypes, sequence, CSV/JSON, protocol/stage hashes and memory-plan formulas agree with prior/local source. Preserve bb22cf8/dirty=true and immutable original artifacts. No submitted commands, models or native workloads were executed in this local review.

Observed scenario-specific evidence: synthetic raw scores/maps and generated RGB at full native cohort size, real original anomaly-GT hash/shape/4-connected-region check reached only in evaluation, no model runtime imports. Stage OS process-lifetime maxima are4.071GiB calibration/0.080 normalization/0.320 quality/10.150 evaluation. Worker action sum1093.272510900s and parent launch-to-exit1097.886997400s are different sequential scopes, not whole-job or detector runtime. Parent available minimum11.097GiB. GT observed-count/hash receipts are not separately exported; check acceptance is inferred from exact source and normal worker exits, not an independent raw-GT recheck here.

The report says the operator closed apps in three rounds. Reported RAM byte values yield +5.196GiB available; actions/process attribution remain operator/report evidence without raw event snapshots. After-cleanup available22,471,106,560 and execute fresh available22,517,452,800 exceed required21,923,497,568 by0.510/0.553GiB. Correct initial shortfall4.706GiB rather than5.058, execute margin0.553 rather than0.59, and quality phase peak0.320 is below its0.716GiB phase envelope. These prose issues do not invalidate completion. Remote empty work-root or dirty cause is not independently established.

Decision: accept native checker resource execution for this scenario and stop treating it as not-yet-run. Do not change past planning flags, lower the20.42GiB guard, claim a universal RAM bound or assume the local15.53GiB machine is now safe merely because one measured process peak was10.15GiB. No actual model/FAISS/SR performance or GPU/VRAM was measured. Full producer's different retained disk18.975GiB and bank/index/model lifetimes remain outside this rehearsal.

Code-review finding determines the next local priority: the native tool's guard_memory subtracts already-live maps/masks and adds the fixed reserve before comparing remaining available RAM. The production-candidate board.evaluate_variant instead calls _budget on the entire phase envelope after arrays are allocated, without matching live-byte/reserve semantics. Same underlying evaluator does not mean identical wrapper budgeting: this can double-budget already-live arrays. Therefore first align and boundary-test the CPU wrapper/lifecycle accounting without changing metrics or simply reducing guard constants, review real RGB/GT loader binding, then scope separate actual-model/index RAM/VRAM/runtime evidence. Old CUDA raw smoke's37632-vector bank is not full262144-bank evidence. Do not extrapolate these18min postprocessing sums to real full inference time.

No fix is implemented in this review-only task and full block remains. Original PROGRESS gets the accepted measured checkpoint and concrete remaining integration issue; this private notebook retains why the next step changed from acquiring RAM to wrapper/integration review. Prior blocked attempts remain historical evidence, not overwritten mistakes. No commit/push or research conclusion changes. Evidence: ignored outputs/pcb-native-memory-native-completion-review-20261018/{REVIEW.md,verification.json,verify_native.py,received/}; unchanged implementation source at local676b071.

## Stage 25 — Correct wrapper accounting without lowering the memory gate (2026-10-18)

User authorized a code fix after Stage24. The separate producer worktree now has local commit d88573d on exp/pcb-full-producer-integration, parent676b071. Board evaluate_variant had rechecked its full envelope after maps/masks were filled. It now subtracts only those known live arrays from the remaining-available-RAM requirement. A single guard shared with the rehearsal preserves the fixed2GiB reserve and the total envelope-plus-reserve cap. Cap checks never subtract live bytes. Invalid counts/probes and live payload larger than the plan are rejected, including safe integer arithmetic for NumPy counts.

The correction also adds the previously missing reserve to other board/producer guard callers. Tiny synthetic checker caps are explicitly3GiB total, composed of the same1GiB payload allowance plus2GiB reserve; protocols record these semantics. This is not an increase of native research settings or a bypass: real free-RAM checks still apply, native pre-allocation requirement remains21923497568bytes and full/real execution guards stay blocked. Sharing the existing helper avoids a parallel memory-policy implementation. Lowering the native envelope to the previously observed10.15GiB peak was not chosen because a single synthetic measurement is not a general bound.

Verified: full pytest326 passed/1 optional-data skip(186.46s), focused68 passed, no-Torch/FAISS boundary/producer46 passed(74.21s), CPU smoke2 rows, diff checks and protected science/model/geometry/protocol comparison pass. Native arithmetic boundaries were tested with byte counts only; the board integration uses tiny generated inputs. Exactly sufficient availability/cap passes; one byte short blocks before the evaluator. Existing region-explosion guard and direct evaluator-equivalence test still pass. Initial sandboxed full run was interrupted; the completed full run used normal execution permissions, without changing OS/Git settings, test semantics or any other user's process.

No actual PCB RGB/GT, model, FAISS, degradation, anomaly-performance experiment or native allocation was run. Old artifacts/hashes and dirty=true provenance remain immutable; changed-source tests do not relabel the older native success as a run of d88573d. Actual RGB/GT loader binding, model/index RAM/VRAM/runtime evidence, producer disk review and separate full approval remain next gates. No push; teammate GitHub availability of these new commits is not claimed. Evidence: worktree docs/PCB_MEMORY_GUARD_ALIGNMENT.md and ignored outputs/memory-guard-{full-verified,focused,notorch,cpu-smoke}.log. Original PROGRESS records completed work/results; this ignored notebook records the observed issue, chosen correction and limits. Original research branch and its prior progress edits are preserved.

## Stage 26 — 실제 입력 연결을 검증하고 GPU 자원 계측을 분리함 (2026-10-20)

사용자가 로컬에서 가능한 작업을 최대한 진행하도록 요청했다. 연구 결과를 더 만들기 전에 남아 있던 실제 RGB/GT 파일 연결을 검증하고, 모델 자원 계측 도구를 준비했다. 기존 전처리·bank·calibration·metric·full 실행 가드는 수정하지 않았다. 새 콜백은 frozen Parent의 경로/분할/label/크기를 대조하고, 같은 검증된 파일 바이트를 디코딩한다. GT는 test 평가 입력 검증에만 읽으며 producer/화질/calibration 콜백으로 전달하지 않는다. 테스트에서는 기존 fake producer와 품질·평가기까지 연결했다.

초기 가용 RAM 스냅샷은2011963392bytes(약1.87GiB)로2GiB 여유보다 적었다. 가드를 낮추는 대신 배열을 만들지 않는 전수 해시 확인을 별도 상태로 구현했다. 해시만 맞는 것을 디코딩 완료로 기록하지 않는다. 이후 가용량2473545728bytes인 프로토콜 스냅샷에서 한 보드의96145920byte 계획+2147483648byte 여유를 충족했고, 매 보드의 실제 가드를 통과하며 전체 디코딩 검증을 완료했다. 특정 앱 정리나 사용자 조작이 원인이라고 추정하지 않았다. 다른 프로세스 종료나 OS/pagefile 변경은 하지 않았다.

실제1101 RGB와100 anomaly GT의 해시,1101 RGB/200 test mask의 native 크기·자료형·정상 zero 정책이 일치했다. 분할721/180/100-normal+100-anomaly는 유지됐다. GT4-connected 영역332개와498756960byte 기존 평가기 지역 마스크 계획이 일치한다. geometry의8-connected324개와 혼동하지 않으며 물리적 결함 수나 탐지 성능으로 해석하지 않는다. RGB68.733s/GT4.794s는 파일 구조 검증 시간이고 모델 runtime이 아니다. 큰180/200 맵 stack 없이 하나씩 읽은 성공이므로 native 평가기20.42GiB 조건을 충족했다는 주장도 하지 않는다.

새 모델 자원 도구는 기존37632-vector limited smoke만 감싸 모델 생성/extraction/bank bind/SR/detector/close를 측정한다. CUDA 동기화 시간, RSS sample, OS lifetime peak, PyTorch CUDA allocated/reserved를 구분하고 outer/child 시간을 중복 합산하지 않는다. 실행 전 코드·참조·공식 CSV·체크포인트 변경을 거부하며 기본은 preflight-only다. 로컬 CPU preflight는 통과했지만 factory/model_execution_started=false이고 torch2.14.0+cpu/cuda_available=false다. 실제 model/FAISS/CUDA는 실행하지 않았다. 이 도구의 향후 subset peak를 full262144 bank 증거로 확대하지 않는다.

첫 전체 테스트는 현재 데스크톱 RAM에 종속된 기존 tiny unit20건과 OneDrive 폴더 안 os.replace WinError5/남은 partial 오류1건으로 실패했다. 작은 in-process fixture만 자원 probe를 분리했고, 실제 subprocess는 실제 RAM 조건과 가드를 계속 사용한다. 실패하는 production 가드를 낮추거나 자식에게 가짜 RAM을 전달하지 않았다. 테스트 임시 파일을 OS temp로 옮겼지만 기존 atomic statewriter를 바꾸지 않았고, OneDrive/파일 잠금이 일반적으로 해결됐다고 주장하지 않는다. 최초 실패 로그와 산출물은 보존했다.

최종376passed/1 optional-data skip(221.69s), 자원 부족으로 건너뛴 subprocess 없음. CPU smoke2 rows, no-Torch binding/budget53와 profiler29 통과. 실제 데이터·원본 예측·기존 연구 결과·hash·프로토콜은 변경하지 않았다. 로컬 commit4b3368e, parentd88573d. 성공 audit는 pre-commitd88573d/dirty=true 기록과 소스 해시를 그대로 보존한다. 원래 연구 branch와 PROGRESS 변경도 유지했다. GitHub에는 push하지 않았고 이 노트는 계속 local-only다.

다음 단계는 별도로 승인된 GPU limited resource smoke이며, 그 이후에도 full-bank model/index RAM·VRAM과 producer disk 및 full 실행 승인이 남는다. 이전 GPU raw smoke/전체 native synthetic rehearsal과 이번 입력 검증은 서로 다른 증거를 채운다. 어느 하나로 나머지를 승인하지 않는다. 근거는 작업 worktree의 analysis/pcb_input_binding/implementation-20261020/VERIFICATION.md, 두 handoff 문서, ignored outputs/pcb-input-binding/pcb2-input-decode-final-20261020-180807 및 outputs/pcb-model-resource-smoke/pcb2-model-resource-preflight-20261020-180410, 최종 테스트 로그다. PROGRESS에는 완료 상태·결과를, 이 노트에는 위 구분과 선택 이유를 기록했다.

## Stage 27 — GPU 반환 자료를 받기 전에 검토 기준 구현 (2026-10-20)

입력 파일 검증과 계측 준비 다음에는 팀원 자료를 수작업으로 읽으면서 기준을 바꾸지 않도록 read-only 검토기를 추가했다. COMPLETE 표기만 읽지 않고 protocol/resource/raw-status 해시 연결, 검토한 source/reference 바이트, 고정 부모·variant·RGB receipt, 호출 수와 시간 합계, RSS/CUDA counter의 모순 여부를 검사한다. 기존 scientific/model/geometry/guard/v0.6 source는4b3368e 대비 바꾸지 않았다. 큰 배열을 로드하거나 새로운 모델·평가 실험을 실행하지 않는다.

검토 범위는 자료의 내부 일관성이다. CUDA라고 적힌 합성 테스트를 실제 GPU 성공으로 세지 않는다. 정상적인 reported CUDA 자료도 원격 실행을 독립적으로 관찰했다는 뜻은 아니므로 independent_remote_execution_verified=false를 유지한다. 전달하지 않은 bank/map은 미검증 목록으로 남기고, 제공한 파일 해시가 일치해도 NPY 내용의 shape/finite까지 별도로 확인했다고 쓰지 않는다. 제한 smoke37632 bank와 full262144 bank도 구분한다. 이 한계를 유지하는 편이 반환 ZIP의 크기나 해시 목록만으로 full 준비를 과대평가하는 것을 막는다.

최종 전체399 passed/1 optional-data skip(178.95s), Torch/FAISS 없는 환경의 검토기23 passed(13.67s), 기존 CPU smoke2 rows 및 diff 검사 통과. 실제 로컬 preflight-only 자료는 exit2/REJECTED_NOT_FULL_APPROVAL로 거부했다. 합성 worker fixture만 사용했으며 실제 GPU resource 반환·추론·anomaly 성능 수치는 생성하지 않았다. 별도 검토 에이전트도 기존 실제 코드의 추출24/준비·복원144/검출432 호출 수 및 metadata 계약을 대조했고 차단 이슈를 찾지 않았다. 이 검토는 추가 실행 결과가 아니다.

작업 commit ef2ca8614cb1067a26af034a45ecf339b9d58a4f, branch exp/pcb-full-producer-integration. 근거는 같은 worktree의 docs/PCB_RESOURCE_RETURN_REVIEW.md, tests/test_pcb_resource_review.py, ignored outputs/resource-review-full-tests.log 및 outputs/pcb-model-resource-review/preflight-negative-final-20261020-191303/review.json이다. 코드 worktree는 clean이며 원본 연구 branch는 유지했다. Push하지 않았다. 다음은 별도 GPU 제한 resource smoke와 그 반환 검토다. 그 후에도 full-bank 자원·producer disk·명시적 full 승인 차단 항목이 남는다. 이 노트는 local-only이며 진행 결과는 원본 PROGRESS에 따로 반영했다.

## Stage 28 — 두 GPU 담당자의 작업 분리와 코드 전달 선행 조건 (2026-10-27)

프롬프트 작성 전에 실제 로컬 HEAD·작업 트리와 원격 ref를 확인했다. 작업 worktree는 ef2ca86으로 clean이며 origin에는 exp/pcb-full-producer-integration이 없다. 공개 memory-readiness는 bb22cf8, tiled-handoff는 d732574다. 따라서 로컬에 있는 파일을 두 사람이 바로 fetch할 수 있다고 안내하지 않는다. 사용자 CPU 작업은 bb22cf8 이후4개 commit과 공개 금지 파일을 검토한 뒤 필요한 코드만 전달하고 수신 검증하는 일부터 맡긴다. 이번 세션 자체에서는 push나 테스트 재실행을 하지 않았다.

심주형씨는 기존 환경·입력·과거 실패 기록을 보존하고 고정된4보드의 계측 smoke를 맡는다. 손지혁씨는 처음 사용하는 PC에서 Python3.11, CUDA 가능한 Torch/torchvision, 프로젝트 legacy 의존성, 고정 submodule과 입력을 설치한 뒤 같은 subset의 기존 raw smoke를 재현한다. 후자는 설치·전달·경로 문제를 확인하는 독립 환경 검증이며 새 과학적 반복 실험이나 bitwise parity 검증으로 세지 않는다. 필요한 pcb2 데이터와 두 checkpoint는 기존 setup CLI로 hash 검증하며, 다른 dataset/model 일괄 다운로드는 하지 않는다. 설치 환경의 차이는 기록하고 연구 설정과 혼동하지 않는다.

소규모 bank37632와 full-cap262144, raw smoke와180-normal calibration/full 연구 결과를 계속 구분한다. 두 제한 실행이 성공해도 full-bank 자원, producer disk/lifecycle, 실제 full executor 및 최종 승인 문제는 남는다. 신규 category·gating·weight search를 병렬로 시작하지 않는다. 결과가 오면 자원 계측 자료는 기존 검토기로, 독립 raw smoke는 원본 artifact·source/checkpoint/split inventory로 대조한다. 새 입력 bundle은 기존 licensed Release를 사용하고 raw prediction·weights와 이 노트는 Git에 올리지 않는다. 기록은 PROGRESS와 이 노트로 나누어 갱신했다. 메모리 observer의429 경고는 알렸고 직접 조회는 가능했지만, 판단은 실제 파일과 원격 ref를 근거로 했다.

## Stage 29 — 제한된 이력 공개와 실제 GitHub 수신 검증 (2026-10-27)

사용자가 코드 push와 수신 검증을 명시적으로 요청했다. 원본 연구 branch를 통째로 올리는 대신 공개 bb22cf8 위의4개 선형 commit 전체를 검사했다. 중간 버전까지40개 blob/27개 경로를 확인했고 금지 파일·바이너리·선택한 credential 패턴은 없었다. 두 역할의 전달 명령과 CPU 검증 제한을 정리한 문서 commit2f418c0을 추가한 뒤5개 commit/43개 blob/28개 경로를 다시 검사했다. 원본 private79a1c0f는 조상이 아니며 이 노트도 이력에 없다. exp/pcb-full-producer-integration 한 branch만 push했고 ls-remote로2f418c046bca5d607b7c3e199f4a85396c851fb4를 확인했다. main merge, force push, PR 생성은 하지 않았다.

이번 전체 pytest는397 passed/3 skipped(205.37s)다. 과거399/1을 새 결과로 복사하지 않는다. 실제 generated-worker2개는 가용1848459264/1848520704bytes가 요구2186018816bytes보다 적어 skip됐고, focused 확인도1 passed/2 skipped였다. 나머지1개는 optional MVTec data다. 메모리 보호 기준을 낮추거나 다른 앱을 종료하지 않았다. 공개는 제한 smoke 준비 코드 전달이며 이 skip을 full 자원 검증 완료로 해석하지 않는다. 기존 CPU smoke2 rows와 diff 검사는 통과했다.

기존 setup verify-only도 확인했다. 처음에는 worktree에 기본 SwinIR checkpoint가 없어 실패했고 그 로그를 보존했다. 원본 checkout의 checkpoint를 환경변수로 명시하자1202개 입력 파일과 두 checkpoint 검증이 통과했다. 파일을 복사하거나 새 다운로드로 덮어쓰지 않았다. 이 사례 때문에 새 worktree/clone에 환경·입력이 자동으로 따라온다고 안내하지 않는다. 세 다운로드 endpoint의 HEAD200도 확인했지만 HTTP 응답 자체를 본문 SHA 검증으로 쓰지 않는다.

별도 [로컬 경로 생략]

전달 문서는 공개 docs/PCB_TWO_OPERATOR_HANDOFF.md, 실제 검증 근거는 작업 worktree의 ignored outputs/publication-20261027-124910/VERIFICATION.md와 receive_verification.json이다. 심주형씨는 기존 환경의 제한 계측, 손지혁씨는 최초 설치 및 독립 raw smoke를 같은 공개 commit에서 시작한다. 이후에도 full262144 bank 자원·producer disk/lifecycle·full 실행 승인은 남는다. 실제 GPU 추론/native180/200/새 연구 metric은 이번에 실행하지 않았다. 진행 사실은 원본 PROGRESS에, 역할 분리와 검증 범위의 이유는 이 local-only 노트에 따로 기록했다.

## Stage 30 — 첫 CUDA 계측 반환 수용 범위와 다음 자원 검증 (2026-10-27)

55904byte ZIP의SHA256은e2270fc445d77c6b5f3ddc960e1d3aaf866983b4092fdf2144f1930e3f87c437이다. 첨부 문서는 증거로만 읽고 명령으로 실행하지 않았다. 안전한 새 폴더에9개 metadata만 풀고 기존 검토기로2f418c0 source/reference 및 scope 일관성을 확인했다. preflight와 실행의7개 식별 그룹, CSV891개 호출과8단계 요약을 대조했다. dirty=true는 유지했다. outer1073.346526300s, 단계합1055.357244501s이며 잔여17.989281799s의 세부 원인은 별도 계측하지 않았다.

Detector986.460462800s가outer91.9051%지만 backbone과CPU FAISS 등 합계이므로 FAISS 단독 병목 비율이라고 쓰지 않는다. SwinIR은52.999492000s다. Sampled RSS1.674801GiB와OS lifetime1.688538GiB, CUDA max allocated456.123MiB와reserved518MiB를 구분한다. 드라이브 여유 변화0.321175GiB를 실험 output 사용량으로 단정하지 않는다. 기록된 output payload는0.194236GiB다. 원본 보고서는 고치지 않고 이 구분을 로컬 검토에 추가했다.

현지 검토기는12개 raw hash를 확인했다고 보고한다. 이번 ZIP에는그중bank/status만 있어 로컬 직접해시 확인은1개, 미전달 array는11개다. 이 때문에 로컬 결과는PARTIAL_OR_METADATA_ONLY이며 배열shape/finite를 다시 확인했다거나 원격 실행을 독립적으로 증명했다고 쓰지 않는다. 현재 자원 검토에 작은 ZIP은 유용하지만 후속 배열 검증과 같은 범위는 아니다.

동일 limited smoke 반복을 다음 주력 작업으로 삼지 않는다. 고정262144x1024 payload와기존CPU exact scorer/model의 동시 자원·소수 질의 시간 검증을 별도 engineering probe로 준비한다. 합성 bank/합성 RGB를 쓴다면 연구 bank·selection·성능 결과가 아니라고 강하게 표시해야 한다. 현재full bank1GiB는복사/FAISS scratch를 제외한 payload이며, 기존37632 bank peak를 그대로 full 상한으로 쓸 수 없다. 사용자 추가 요청에 따라 가능한 CPU 구현·fake tests를 이어가되 실제 GPU/FAISS/native/full 실행과 연구 설정 변경은 하지 않는다. 설계와 결과 검토는 같은 채팅에서 유지하되 protocol/version/decision 기록을 기준으로 하고, 팀원 PC의 결과는 별도 전달이 필요하다.

## Stage 31 — Full-cap 자원 fixture의 CPU 구현과 동일 branch 전달 (2026-10-27)

사용자가 가능한 후속 작업을 계속 요청해 별도 자원 probe를 구현했다. 기존 모델·CPU exact scorer를 그대로 두고 262144x1024 합성 float32 bank와 합성 RGB224 tile 2개, 변형 3종의 6질의만 다룬다. 이는 실제 정상 fit bank나 selected-index 산출물이 아니며 GT/보정/threshold/metric/연구 prediction을 만들지 않는다. full_bank_validated와 full_pilot_approved는 항상 false다. CLI는 preflight가 기본이며, 실제 resource 동작은 명시적 execute가 필요하다. 현재 PC에서는 실행하지 않았다. Fake 주입은 4096 float 이하의 명시적 shape로만 허용해 테스트가 은밀히 1GiB를 만들지 못하게 했다.

자원 계획은 bank copy 3개, pairwise distance scenario 2개, chunk/query workspace, 과거 small-run OS peak 전체와 기존 2GiB 여유를 더한 명시적 scenario다. 서로 겹칠 수 있는 계획치이지 동시 실측 peak나 보장 상한이 아니다. 최신 로컬 preflight는 필요 8.283056GiB 대비 가용 snapshot 1.866390GiB로 BLOCKED_MEMORY/exit2이며 큰 NPY/model은 생성하지 않았다. 가드를 낮추거나 앱을 종료하지 않았다. Hash/source/submodule/체크포인트 변경, 미완료·기존 output, CUDA 불가, cleanup/monitor 실패를 검사한다. 성공 시에만 자원용 NPY를 정리하고 실패 자료는 보존한다. 개별 FAISS 호출의 hard timeout은 없어 unattended 실행 준비라고 부르지 않는다.

전체 429 passed/1 optional-data skip(180.96s), 최종 focused 30 passed(5.59s), backend import 차단 30 passed(5.57s), CPU smoke 통과다. 오래된 임시 no-Torch venv는 distutils/pytest 시작부터 깨져 있어 수정하지 않고 실패 log를 남겼다. 일반 Python에서 Torch/FAISS import를 금지한 검증을 새 환경 설치 검증으로 바꿔 말하지 않는다. 로컬 사전점검은 commit 전 2f418c0/dirty=true로 기록돼 그 상태를 보존한다.

기존 공개 target을 유지하기 위해 local feature branch에서 83ef04e를 만든 뒤 exp/pcb-full-producer-integration만 fast-forward/push했다. 새 text blob 7개 검사 통과, 원래 bound source/reference byte 36개 동일을 확인했다. 개인 노트·받은 ZIP·raw 배열·가중치는 stage하지 않았다. 별도 원격 branch/main merge/force push는 없다. 독립 수신 clone이 같은 83ef04e를 받아 byte hash 38개, canonical blob 22개, submodule 2개를 확인했다. 수신 src 직접 import, 신규 30 tests(5.60s), CPU smoke 2 rows와 CLI help도 통과했다. 원본 .venv를 명시적으로 재사용했으며 새 CUDA 설치나 실제 GPU 실측은 아니다.

공개 문서 docs/PCB_FULLCAP_RESOURCE_PROBE_DRAFT.md와 로컬 ignored FULLCAP_IMPLEMENTATION_VERIFICATION.md/fullcap_receive.json이 근거다. 이 채팅에서 설계·구현·반환 검토를 연결하되 실행 규칙은 파일로 고정한다. 다음은 GPU 담당자의 별도로 허용된 full-cap resource probe와 결과 검토다. 실제 full bank fit/selection, full producer 연결, 전체 RAM/디스크 gate와 full 승인은 여전히 별도다. 이번에 새 연구 성능 결과나 실제 모델/FAISS/native 실행을 만들지 않았다.

## Stage 32 — 중간보고서 피드백 반영 범위 (2026-10-28)

기존 10월 22일 검토본의 연구 기록 기준일(10월 20일)을 유지한 채 설명 순서와 문장을 수정했다. 배경·방법을 결과 앞 3페이지로 옮겨 평가 지표를 먼저 정의하고, 표 번호를 읽는 순서에 맞췄다. VisA pcb2 선택 이유는 물체 중심 비교에서 회로 기판으로 범위를 넓혀 전체 시야와 작은 결함 보존을 점검한다는 내용으로 한 문장 추가했다. 정상 학습 901장과 별도 테스트 200장을 구분해 721/180/200 분할의 분모 혼동을 줄였다.

표 7 뒤에 요청된 보존 결론을 넣되, 보존의 의미를 RGB·GT 재구성과 원본 마스크 연결 성분 일치로 한정했다. 이 구조 점검과 실제 탐지 성능을 구분하는 조건은 유지했다. 반복적인 부정형은 확인한 결과·사전 기준·후속 검증으로 바꿨고 B-uncertain, 인과 해석 및 일반화 한계도 남겼다. 최신 GPU 반환을 이 과거 보고서에 소급해서 넣는 작업은 요청 범위에서 제외했다.

수정본은 ../중간보고서/디자인프로젝트_중간보고서_의견반영_20261028.docx다. 원본과 수치 표를 보존하고 Word 렌더 11페이지를 모두 직접 확인했다. 진행 사실은 PROGRESS, 이 선택 이유는 local-only 노트에 나눠 기록했다. 코드·모델 실행이나 공개 branch 변경은 없으며 이 노트는 계속 Git ignore/untracked 상태다.

## Stage 33 — 다음 GPU 실행과 로컬 검토 준비의 분담 (2026-10-28)

다음 두 작업을 병행하도록 프롬프트를 만들었다. 심주형씨는 이미 완료한 37,632-vector limited smoke를 반복하는 대신, 공개 83ef04e의 고정 262144×1024 합성 payload와 6개 tile query로 자원 공존만 확인한다. 실제 PCB 정상 fit·selection·보드 성능과 구분하며, 성공해도 full_bank_validated와 full_pilot_approved는 false다. VisA 입력은 이 자원 probe에 필요하지 않으므로 재다운로드 작업을 넣지 않았다. 매번 실제 가용 자원 guard를 적용하며 이전 RSS를 상한이나 실행 보장으로 쓰지 않는다.

이 PC는 큰 배열이나 모델을 실행하지 않고 새 artifact kind의 read-only 반환 검토기를 구현하도록 범위를 정했다. 기존 limited reviewer에 새 kind를 억지로 허용하면 검증 대상이 섞이므로 별도 진입점과 작은 metadata fixture 테스트가 필요하다. 원격 경로와 미전달·삭제 payload는 로컬 내용 검증 완료로 취급하지 않는다. 두 프롬프트 작성은 실제 구현·실행 완료를 뜻하지 않는다. 다음 단계는 새 반환의 범위·hash·시간·자원 정합성을 확인한 후 실제 bank/producer 연결과 전체 실행 gate를 검토하는 것이다.

보고서 날짜 문구 제거 요청도 처리했다. 이전 산출물 이름은 사라졌고 최신 디자인프로젝트_중간보고서.docx에는 사용자 추가 표지가 있어 이를 원본으로 보존했다. 별도 날짜문구제거 수정본에서 선택된 한 문단만 제거했으며 표지나 연구 기록의 날짜 자체를 소급 변경하지 않았다. 추가 표지 때문에 현재 수정본은 12페이지이며 모두 직접 확인했다. 이 기록은 local-only로 유지하고 공개 branch에는 변경을 올리지 않았다.

## Stage 34 — Full-cap 반환 검토기의 CPU 구현 완료 (2026-10-28)

새 artifact kind 전용 read-only 검토기를 구현했다. 기존 limited checker를 넓히면 두 실행 범위가 섞이므로 별도 CLI와 모듈을 두고 숫자·CUDA 검사 및 recorder summary는 재사용했다. 실행 측 reference 절대 경로를 자동으로 읽는 대신 전달된 로컬 --reference-run만 검증한다. 추가 source/reference 경로를 기존 검토기에 넘기기 전에 제한하고 dataset·checkpoint 파일은 열지 않는다. 실제 모델·평가기·bank·seed·geometry와 full executor는 그대로다.

검증된 것은 metadata 내부 정합성과 제공된 바이트의 hash 연결이다. 실행 commit과 검토기 commit, raw-byte binding과 Git canonical source를 구분했다. status.json 해시는 이번 검토의 수신 기록이며 외부 기대값과 대조한 hash라고 부르지 않는다. 성공 시 삭제된 synthetic NPY와 미전달 배열은 독립 검증한 내용으로 승격하지 않는다. sampled RSS, OS lifetime peak, CUDA 누적 counter와 드라이브 여유 변화·output payload도 따로 기록한다. 이 정합성 통과는 실제 연구 bank나 full pilot 승인이 아니다.

73개 신규 테스트를 포함해 관련126개가 39.39초에 통과했고, 최종 전체502 passed/1 optional-data skip은 139.36초다. CPU smoke2 rows와 diff 검사를 통과했다. 실제 tiny producer의7×4 float/fake adapter 결과를 CUDA 증거로 거부하는 테스트와 새 프로세스에서 runtime import를 차단한 전체 metadata 검토 테스트도 통과했다. 기존 reference 연결에서는 실제 보관 metadata와12개 probe source binding이 맞았고 기존11개 미전달 배열은 그대로 남겼다. 최초 읽기 순서 오류와 지수형 JSON overflow 검사를 수정한 뒤 최종 suite를 다시 실행했다.

코드·테스트·공개 가능한 문서7개만 로컬 a7b2a26c26aa7a26589a0da4f3af88e297c006a3에 commit했다. 원본 checkout79a1c0f와 기존 사용자 변경은 유지했고 push하지 않았다. 이 노트는 ignored/untracked로 남긴다. 실제 새 full-cap GPU 반환은 아직 없고 큰 payload·실제 모델/FAISS 자원 probe·native cohort를 실행하지 않았다. 다음은 실제 반환을 검토한 뒤 fit/selection·full producer·현재 RAM/디스크·최종 실행 승인 gate를 따로 확인하는 것이다.

## Stage 35 — 실제 full-cap 합성 자원 반환 검토와 연구 bank 단계로의 전환 (2026-10-28)

59425byte ZIP f7cddc837ca79c2e428e37f7e85c42ffd2f8e3308703d39a94a13407b6793486을 받아 실제 a7b2a26 검토기에 대조했다. manifest13개 hash가 맞았고 별도 preflight와 실행의10개 고정 식별 그룹이 일치했다. reference의 raw_status/raw_bank_status 파일명이 평탄화돼 있어 원래 배치는 정상적으로 거부됐다. 원본은 보존하고 새 복사본의 경로만 raw/status와 raw/bank/status로 복원한 뒤 실행-bound5개 hash를 재확인했다. 내용·JSON·기존hash를 바꿔 검사를 통과시킨 작업은 아니다. 최종 reported CUDA synthetic full-cap 정합성 검토가 통과했다.

재계산한 outer33.819174700초,16개 call합28.794385900초, 잔여5.024788800초다. 잔여는 outer에 포함되는 unwrapped 구간이며 원인별 timer가 없어 hashing/mmap/CUDA초기화 등에 각각 배분하지 않는다. detector19.309442800초는 FAISS 외 작업도 포함한다. RSS sampled/lifetime4.144115448GiB는 이번에 수치가 같았을 뿐 개념은 구분한다. CUDA allocated/reserved peak370.314941406/426MiB, output약1.000004467GiB와 drive여유+47.6015625MiB도 따로 해석한다. 기존CUDAvenv를 명시적으로 사용한 interpreter 수정은 task 의도에 맞으며 향후 명령에도 bare python 대신 실제 환경 경로를 쓴다.

이제 (262144,1024) 합성 payload와 기존 model/index가 공존한 reported 자원 근거가 생겼다. 삭제된 synthetic배열·미전달reference배열11개·체크포인트 내용과 원격 실행 자체는 로컬 독립 검증 대상에서 제외한다. actual bank와 full_pilot flag는 false를 유지한다. 실제 GPU 반환과 직전 CPU개발 검증502pass/1skip을 구분하고 이번에 그 suite를 다시 실행했다고 쓰지 않는다.

같은 합성 probe를 반복하는 대신 실제 정상 fit bank를 재사용 가능한 연구 자산으로 만드는 쪽으로 진행한다. 현 producer는 코드상 synthetic only여서 CPU에서 별도 실제 입력 fit/bank 경로·provenance·완료/재사용 guard를 연결하고 작은 fake test로 검증하는 작업이 다음 우선순위다. GPU 담당자는 코드 전달 후 정상721장의 실제 feature stream으로 고정cap bank를 생성한다. 그 다음 full raw380보드와 보정/화질/평가를 연결하고 native약20.42GiB 진입기준과 최종 승인을 별도로 확인한다. 작은 synthetic자원4.144GiB 관측값으로 그 기준을 낮추지 않는다. 이번 검토는 source/설정 변경·로컬모델실행·새성능지표·commit/push 없이 마쳤다.

## Stage 36 — 최종 제출물과 남은 실행 단계의 구분 (2026-10-29)

사용자가 최종 목표와 남은 단계를 물어 현재 문서들을 대조했다. 10월3일 THESIS_SYNTHESIS와 LIMITATIONS_AND_BOUNDARIES의 실험 종료·기여 정의는 기존 MVTec 묶음의 기록이다. 기여는 평균 회복과 개별 손실, 변화 크기·분포, baseline과 화질-localization 관계를 함께 보고하는 평가 구성이다. 새 탐지개선 모델의 우수성이 확보됐다는 주장은 현재 결과에 포함하지 않는다. 과거 v0.2의 Capsule 예약 문구만 읽고 이후 닫힌 실험을 다시 필수 작업으로 제시하지 않는다.

이후 명시적으로 진행한 PCB full-FOV/native tiling 확장은 별도 protocol family다. 여기는 구조 보존·CPU 코드·실제 제한 모델 및 합성 full-cap 자원 반환까지 확인했고 실제 full bank와380보드 성능은 아직 없다. 따라서 현재 프로젝트 전체를 완료 또는 몇 퍼센트 완료라고 단정하지 않고, 완료된 연구 분석과 남은 확장 실행을 구분한다.

현재 PCB를 포함한 최종 패키지의 남은 순서는 CPU에서 실제 입력 실행 경로 연결, GPU에서 정상fit bank 생성, 고정3variant 추론, 충분한 RAM의 보드 보정·화질·탐지 평가, 최종 보고서/논문·발표·재현 자료 정리다. 가장 가까운 다음 작업은 첫 단계이며 실제 모델 실행은 여기서 수행하지 않는다. 이 정리는 상태 설명과 권고 다음 순서이며 새 연구축·선택 기준·승인을 추가한 결정은 아니다. 기존 B/B-uncertain과 negative 결과를 유지한다.

## Stage 37 - 실제 bank 작업 프롬프트와 세 사람 역할 분리 (2026-10-29)

CPU 구현/공개와 GPU fit-only 실행의 두 초안을 먼저 작성했고, 손지혁의 독립 raw smoke 보고를 받은 뒤 별도 outputs/pcb-three-role-prompts-20261029/에 세 역할의 프롬프트를 준비했다. 현재 구현 a7b2a26은 clean이고 공개 branch는83ef04e임을 실제로 확인했다. 실데이터 fit-only CLI는 아직 없으므로 이번 기록은 코드 구현 완료나 공개 결과가 아니다. CPU 담당자가 기존 synthetic-only guard를 보존한 실제 normal-fit 스트림/고정cap bank 경로를 구현하고 작은 fake 테스트 및 안전한 branch 공개·수신 검사를 마친 다음 심주형이 실제 bank를 만든다.

손지혁은 GTX1660 SUPER6GiB와 별도 Python/Torch 환경에서 기존 limited raw smoke 성공을 보고했다. 이는 두 번째 환경의 운용 보고이며 수신 ZIP·배열 검증과 cross-machine numerical parity는 아직 없다. reported ZIP SHA와 원격 경로는 실제 수신 파일을 대신하지 않는다. 전체 pytest는46분/16% 중단이고 peak는 미측정으로 유지한다. 이 조건에서 또 raw smoke를 실행하는 대신 기존 입력 audit의 decode 경로와 집중 테스트 진단을 맡겨 남은 입력·환경 문제를 확인하기로 했다. 기존 audit은 RGB1101장과 test200개 mask 입력 receipt를 순차 확인하며 실제 anomaly GT 파일100개를 구분한다. 4-connected 평가 입력 구조 수를 과거8-connected 물리 보존 감사와 혼동하지 않는다.

심주형은 실제 정상721장의 특징 스트림에서 고정 선택을 거쳐 저장262144x1024 bank를 한 번 만들고 재사용 가능한 상태로 비공개 보존한다. 예상 전체 관측/검증 feature27132672개와 저장262144개를 구분한다. 이 단계의 fit-bank 무결성은 full bank/cohort 성능 검증이나 full-pilot 승인과 별도로 기록한다. 손지혁은 동일 bank를 다시 fit하지 않는다. CPU는 받은 자료가 없더라도 구현을 진행하고, 새 공개 full commit과 필수 파일을 확인하기 전 GPU 실행을 허용 가능한 명령이라고 설명하지 않는다.

이번에는 프롬프트와 사실/판단 기록만 갱신했다. 실제 모델 실행·새 metric·source 변경·commit/push는 없다. 이 노트는 local-only이며 stage/commit/push하지 않는다. 다음 질문은 실제 fit 스트림의 자원 및 완료 계약이 검증된 bank를 만들 수 있는지이며, 그 뒤에만 full raw380보드와 normal-only calibration/평가 연결을 검토한다.

## Stage 38 - 실제 fit-only 경로 구현과 공개 수신 검증 (2026-10-29)

사용자가 CPU 프롬프트를 실행 지시로 전달해 기존 구현 worktree에서 실제 코드를 작성했다. 기존 synthetic producer를 확장해 실행 차단을 우회하는 대신 별도 pcb_fit_bank 경로를 추가했다. 이는 bank 생성 단계만 먼저 분리해 실제 연구 입력을 재사용 가능한 자산으로 남기기 위한 범위 선택이다. 기존 FrozenPCBInputs.rgb, feature_chunks, bounded_bank, 모델 factory를 재사용하며 fit-normal721장만 특징 callback으로 전달한다. calibration/test RGB·GT, 복원/열화·예측·index binding·보정·metric은 이 경로에 없다. factory가 SwinIR도 생성하는 점은 자원 계획에 남겼고 실제 복원 호출은 하지 않는다.

관측/검증 전체 feature27132672개와 저장262144개를 구분하고 고정 선택 SHA를 검사한다. 저장한 bank는 기존 완료 계약으로 재로드하고 청크 단위 finite 검사를 한다. 실제 bank 무결성, actual-bank 생성, full detector 검증/승인 flag를 구분한다. private tiny injection은 별도 synthetic 상태이며 전체 shape를 CLI로 바꿀 수 없다. 진행 기록은 restart 가능한 checkpoint가 아니다. cleanup 실패도 완료로 승격하지 않으며 owned reference 해제와 OS/allocator/예외 frame의 수명은 구분한다.

새34개 테스트와 최종 전체536 passed/1 optional-data skip, CPU smoke2 rows를 확인했다. 전체 suite는185.59초이며 연구 runtime 측정이 아니다. 초기 별도 Python 테스트가 원본 editable install을 읽는 오류를 src 경로 명시로 수정했다. CI에는 submodule이 없을 수 있어 runtime import 금지/정적 preflight 검증은 실제 모델 파일에 의존하지 않게 구성하고, frozen source/submodule guard는 별도 작은 fake-source 테스트로 확인했다. preflight 상태의 승인 flag 변경도 실행 전에 거부한다.

실제 로컬 정적 preflight는721개 fit 이미지의 압축 파일 hash와 고정 source/reference/checkpoint를 확인하고 현재 RAM gate에서 차단됐다. 해당 실행은 a7/dirty=true이며 나중 commit 값으로 바꾸지 않는다. 기록 snapshot은 가용2626314240byte, 요구6661915776byte다. source20개/reference7개를 확인했지만 RGB decode나 모델 실행은 없고 CUDA도 정적 단계에서는 미확인이다. 계획치6.204393GiB는 모델/버퍼에 대한 가정과2GiB 여유를 포함한 값이며 과거 합성4.144GiB를 fit 상한으로 사용하지 않았다. GPU 담당자의 현재 자원은 별도로 검사한다.

코드05f3cdd와 전달 문서 보완865f26a를 공개 branch 하나에 push했다. 이전 미공개 a7도 포함한83ef04e 이후3개 commit/22개 이전·이후 blob을 검사해 비공개 노트·데이터/가중치/배열·원본 미공개 이력이 포함되지 않았음을 확인했다. 원격에서 새로 clone한 수신본은 처음 불필요한 upstream LFS 모델 자동 다운로드/DNS 때문에 submodule checkout이 실패했다. 새로 만든 이 수신본에서만 source pointer 방식으로 index/worktree를 완성하고 process-scoped skip 값을 복구했다. 전역 설정·원본 checkout·고정 revision/hash는 바꾸지 않았다. 이 LFS 파일은 현재 factory가 쓰는 publisher checkpoint와 다른 예전 FAISS artifact다.

최종 원격/수신 HEAD865f26a, pinned source20개와 reference7개 일치, 수신 테스트34개/CPU smoke2 rows를 확인했다. 수신 검증은 원본 .venv Python을 명시적으로 사용했고 데이터·가중치·venv가 clone에 생겼다고 쓰지 않는다. 원본79a1c0f/사용자 변경과 이 ignored/untracked 노트는 보존했다. 손지혁의 ZIP·decode·전체 pytest는 별도 미확인이다. 다음 실행은 심주형이 새 공개 commit에서 fresh preflight 뒤 실제 normal-fit bank를 한 번 만들고 보존하는 것이며 full380보드·native 평가·최종 승인은 후속 검토 범위다.

## Stage 39 - 실제 bank 반환 수신과 독립 입력 검증의 연결 (2026-10-29)

심주형 실제 fit와 손지혁 초기/후속 ZIP 세 개를 받아89개 metadata 파일과86개 manifest hash를 확인했다. 첫 지혁 ZIP은 이전 전달 기대 hash와도 맞았다. 원격 경로를 이 PC 경로로 따라가지 않고 명시적으로 받은 파일/보관 source/frozen inventory만 대조했다. 실제 bank/index와 지혁 raw 배열11개는 여전히 미전달이며 finite/파일 hash 현장 검증은 담당자 기록이다. 로컬에서는 source/metadata 연결이 맞는지를 확인했다. 내부 명령은 실행하지 않고 원본 ZIP을 보존했다.

실제 bank 생성 보고의 source865f26a/dirty=true,721fit,관측27132672·저장262144 구분과20개 source/7개 reference가 맞았다. Expected index digest와 NPY digest를 고정 규칙으로 재현했다. bank 자체 digest19c3bb...는 제공 metadata 사이에서 맞지만 미전달 bank byte 검증이라고 부르지 않는다. 다음 GPU loader가 해당 실제 파일을 직접 검사해 재사용한다. 이미22.64분 정도에 생성한 이 bank를 다시 fit할 이유는 없으며 이 CPU로1GiB를 받는 것도 주실험 필수 조건이 아니다.

시간 CSV17307호출/4phase를 재계산했다. 기록의 outer⊃fit-stream⊃전체child합이라는 문장은 factory/integrity/close가 fitstream 밖이라 수정이 필요하다. Outer1358.670672초가 fitstream1319.060208초와 child호출 전체를 포함하고, fitstream은 feature합1144.075326초를 포함한다. 전체child합1169.007185초를 fitstream 안의 부분집합으로 쓰지 않는다. 원본 값·hash·실험 판정은 바꾸지 않고 파생 검토에 정정했다. 단계의 측정 범위를 확인하는 문제이며 실제 bank 실패나 탐지 성능 결과가 아니다.

지혁 후속 decode1101 RGB/200 mask 입력, actual GT100개,4-connected332개가 기존 고정 metadata와 맞았다. 특히 두 머신의 fit721개 compressed/decoded RGB hash가 모두 일치해 학습 입력 receipt를 연결할 수 있었다. 모델map parity와는 다른 확인이다. 집중38개/fake adapter4개 통과 로그와 CPU smoke2 rows를 확인했고, 전체 pytest 미완료/옛 stalled node불명·peak미측정은 그대로 남겼다. 초기 read-only validator의 dictionary와 scalar 비교 실수는 원본 raw를 바꾼 증거가 아니며 두 ZIP raw status byte동일로 확인했다. 우리 로컬 검토도 raw row에 shape가 직접 있다는 가정을 실제 size_wh/별도arrayreceipt schema에 맞춰 수정했고 첫 실패 log를 보존했다.

다음 우선순위는 actual bank를 명시적으로 load해 fit 없이 index/추론/RGB spool을 연결하는 것이다. 기존 producer의 synthetic guard를 풀어 real로 둔갑시키지 않는다. 고정 작은 실제 bank 재사용 통합을 한 번 확인한 뒤 전체cal180/test200과 보정·화질·exact 평가로 이어간다. 이전2026-10-18 native 메모리 rehearsal 성공을 잊고 같은 합성 실험을 무조건 다시 요구하지 않으며, source/version 범위와 최신 guard/lifecycle/현재 가용 자원은 별도로 확인한다.

주형 환경에 bank·데이터와 native 메모리 실행 기록이 모여 있으므로 primary cohort는 우선 한 환경에 고정한다. 지혁은 필요하면 같은 bank의 소수 사례 독립 확인을 맡고 서로 다른 Torch 버전의 두 산출물을 근거 없이 primary 결과로 섞지 않는다. 전체 pytest를46분째 같은 명령으로 재시도하거나 새 모델을 추가하는 일은 지금 첫 우선순위가 아니다. 이번에는 metadata 검토/기록만 수행했고 실행 source·연구 설정·원본 데이터/ZIP·Git 공개 branch는 바꾸지 않았다.

## Stage 40 - 독립 설계 판단을 포함한 세 역할 프롬프트 (2026-10-30)

사용자는 심주형의 Opus 세션에도 설계 판단을 맡기고 그 결과를 받아 공동 검토하는 방식으로 진행하자고 요청했다. 이에 모델 이름만으로 결론을 신뢰하는 대신 실제 파일/측정/반례와 대안 선택을 적는 독립 연구·설계 리뷰 역할을 부여했다. 원시 사고 과정은 요구하지 않으며, 근거 있는 결정·이견·미확정 사항·권고 다음 단계를 구조화한 문서로 반환하게 한다. 기존 CPU 제안을 그대로 승인하는 것이 완료 조건은 아니다.

새 프롬프트 세 개는 outputs/pcb-design-and-reuse-prompts-20261030/에 있다. CPU는 load-only inference/RGB-spool 경로와 fake 테스트/공개를 구현하고, 주형은 현재 설계를 먼저 독립 평가한 뒤 새 공개 코드가 자신의 GO와 preflight 조건을 만족할 때만 고정 소수 통합을 실행한다. 지혁은 admission/출처/불변성/범위/리소스의 반례와 독립 테스트를 맡는다. 새 코드나 실제 bank가 없어도 각자의 문서 검토와 준비도 확인은 완료하게 해 단순 대기 작업으로 만들지 않았다. Code 실행이 준비됐다고 허위로 설명하지 않는다.

중점 설계 문제는 현재 raw loader의 로컬 bank/provenance 일치 조건과 synthetic RGB reader를 actual reuse로 잇는 계약이다. bank source를 외부 명시 참조로 둘지 검증된 복사본으로 둘지는 이유/공간/이식성을 비교하도록 했고 원본 bank metadata 수정은 금지했다. bank 재학습과 scorer.fit에 의한 index 구성을 구분하고, 기존 guard를 풀어 small real smoke를 full cohort로 승격하지 않게 한다. 주형에게는 PCB 확장이 핵심 연구 질문에 추가하는 증거, tile-wise x4/overlap/작은 결함의 confounder, 최소 결과표·후속 실험 우선순위도 판단하게 했다. 연구 조건 변경은 제안과 영향 검토가 가능하지만 현재 frozen 실험을 사후 변경해 실행하는 권한으로 확대하지 않는다.

동시 공통 코드 재작성을 피하고 CPU 구현을 한 곳에서 관리하되 주형/지혁의 patch·반례·이견을 통합할 수 있게 했다. 공개 사실과 독립 승인, integration GO와 full 승인, 서로 다른 Torch 환경의 독립 확인과 primary 결과 혼합을 각각 구분한다. 기존 native rehearsal과 입력 검증을 잊고 같은 무거운 검증부터 반복하는 일은 우선순위에서 제외했다. 이번에는 프롬프트/진행 기록만 작성했고 실행 source·실제 실험·Git 공개 상태는 바꾸지 않았다. 이 노트는 local-only로 유지한다.

## Stage 41 - Actual bank 재사용 추론의 CPU 구현·공개·수신 (2026-10-31)

사용자가 CPU 프롬프트 실행을 요청해 run_pcb_reuse_inference와 별도 scope reader를 구현했다. 외부 명시 bank reference를 선택해 매 실행마다1GiB를 복사하지 않으며 원본 fit provenance는 수정하지 않는다. 이 선택은 공간/원본 보존의 이점이 있으나 portability는 bank 별도 보관에 의존한다. 향후 portable/full format에서는 검증된 복사본의 비용을 peer 의견과 비교할 수 있다. 현재 작은 통합을 full180/200 loader에 넣기 위해 기존 guard를 풀지는 않았다.

리뷰한 bank hash19c3bb...와 source865f/dirty=true, source20개/reference7개·frozen input/선택·원본 payload 무결성을 확인하도록 했다. Metadata가 일관돼도 다른 같은-shape 값으로 바꾼 bank는 고정 identity에서 거부한다. 새 inference commit이 fit commit과 다르다는 사실은 정상이며 공통 source bytes가 같으면 허용하고 현재 실행 출처는 별도로 저장한다. 옛 JSON의 원격 경로는 자동으로 열지 않는다. CPU에는 실제 bank가 없어 metadata-only bank preflight는 누락 NPY 사유로 exit2가 됐다. 이를 우회하거나 가짜 큰 bank를 만들지 않았다.

실제 경로는 bank bind/index 구성1회만 수행하고 fit RGB/feature stream/save_bank를 호출하지 않는다. Cal/test 추론의 feature 추출과 scorer.fit index 구성은 필요한 inference 동작이다. 고정 cal0000/testnormal0011/testanomaly000의3variants/432queries/9maps를 대상으로 동일한 RGB를 prediction과 spool에 사용한다. Native mean map/max tile-score와 고정geometry를 유지하고 GT·통계·threshold·연구 metric은 제외했다. Test reference2개/variant RGB6개를 보존해 품질 계산 때문에 복원을 반복하지 않게 한다.

Tiny fake E2E, payload/metadata 위조, path/불완전/자원/CUDA/cleanup/monitor 실패, 기존 guard 유지 등을 검증했다. 최종 전체568pass/3skip(193.16s), 새34개와 runtime import 차단34개(7.66s), CPU smoke2 rows를 통과했다. Skip2개는 실제 가용 RAM 약0.928GiB가 기존 subprocess 요구 약2.036GiB에 못 미쳤기 때문이며 reserve를 낮추지 않았다. 나머지는 optional MVTec data다. JSON tuple/list 비교와 처음 JUnit shell 인자 오류를 수정한 뒤 최종 검증했고 앞선 log는 보존했다. 이 시간은 software test 시간이며 연구 runtime으로 쓰지 않는다.

Inference RAM 계획8.687914GiB와 disk1.161637GiB는 bank/scorer/index/query/map/RGB/model/여유를 포함한 시나리오다. Fit6.2044GiB를 추론 요구로 복사하지 않았고 실측 상한도 주장하지 않는다.9개 bank source 파일은 전후 hash가 같아야 하며 일부 저장·cleanup 실패 시 완료로 승격하지 않는다. Owned reference 해제와 process exit/OS cache는 구분한다. 기존 native rehearsal의 과거 성공은 그대로 남겼다.

코드/테스트/공개 문서7개만8abed721eec43f14e9e04fae005f6b5cb6faa702로 commit하고 branch 하나에 push했다.865f 이후1commit/10개 이전·이후 blob을 검사했고 원본 미공개 이력과 비공개 노트/데이터/가중치/배열은 제외했다. GitHub 새 clone에서24 source/7 reference, ancestor/submodule와 새34개 테스트(10.56s)/smoke2 rows를 확인했다. 원본 .venv를 명시적으로 재사용했으며 clone에 data/weights/venv가 생겼다고 쓰지 않는다. 원본79a1c0f와 이전 사용자 변경은 유지했다.

주형/지혁의 독립 검토는 아직 받지 못했으므로 이 구현 선택을 그들이 승인했다고 쓰지 않는다. 다음 단계는 주형이 실제 diff/설계를 보고 GO/NO_GO를 정하고 새 CLI의 fresh preflight 뒤 제한 통합1회를 실행하는 것이다. Full cohort와 실제 보정/평가 승인은 별도이며 이번 CPU 작업은 GPU/모델/과학 결과를 생성하지 않았다. 이 노트는 계속 local-only이며 stage/commit/push하지 않는다.

## Stage 42 - 이전 설계 리뷰와 공개 구현의 차이 정리 (2026-10-31)

심주형의 설계 반환 ZIP을 실제로 검증해 11개 파일과 manifest 10개 일치를 확인했다. 리뷰는 865f26a에서 새 코드가 없던 시점의 판단이며, 현재 공개 8abed72에는 재사용 CLI와 별도 reader가 있다. 리뷰를 틀린 판단으로 지우지 않고 기준 revision 차이를 기록했다. 제안한 feature-path 7개 모두 현재 fit source 20개 비교에 포함돼 I-1의 위험을 이미 차단한다. 동일 FrozenPCBInputs.rgb 사용과 smoke 전용 reader도 확인했다.

남은 수정은 조립·저장 계측/보드 RSS와 clean spool 재조립 byte equality 검사다. 조립 generator 안에서 transform/predict가 실행되므로 단순한 외부 timing을 child 시간과 더하면 중복된다. Inclusive board span과 독립 stage를 구분하는 최소 수정이 필요하다. 실제 bank/data가 없는 이 PC에서는 작은 synthetic map으로 평균5/score10 반례만 재현했고 모델·GT·연구 metric은 실행하지 않았다.

Bank 복사 제안의 이식성 이점은 남기되, 현재 구현은 옛 full reader를 고치지 않는 명시적 외부 bank/별도 reader 방식이라는 차이를 주형이 다시 판단하도록 했다. Small 통합을 full artifact로 승격하지 않는다. 다른 가정의 RAM 추정으로 기존 guard를 줄이지 않으며 fit source/hash를 수정해 호환성 검사를 통과시키지 않는다. 다음 행동은 CPU의 작은 수정과 공개, 주형의 독립 GO 및 고정432-query smoke, 지혁의 작은 반례 검증이다. 새 fit/full-cap probe/전체 pytest 정체 반복은 우선순위가 아니다.

연구 제안 중 보드별 paired quality-localization 분석은 검토할 가치가 있으나 새 ROI 최대값/region recall, tile 평균 화질, tertile/CI 정의는 자동 채택하지 않았다. Primary pooled AU-PRO와 per-image AU-PRO 평균을 구분하고 normal board의 per-image AU-PRO는 해당 없음으로 둔다. 실제 GT loader도 이미 존재하므로 없는 것으로 적지 않으며 full-cohort 연결과 resource/승인 gate를 구분한다. 새로운 코드·실험·성능값은 만들지 않았고 현재 노트는 계속 local-only다.

## Stage 43 - 검증 반복을 줄이고 연구 결과 확대로 전환 (2026-10-31)

사용자는 검증이 너무 많고 보수적이라며 두 GPU 담당자에게 더 많은 실험을 맡겨 질 높은 여러 결과를 만들고 싶다고 명확히 했다. 앞으로 검증을 독립 산출물로 계속 늘리지 않고 자동 체크로 묶는다. 입력/자원/코드 정합성 문제가 없다면 최초 연결 확인부터 계획된 cohort까지 같은 작업에서 이어가며 매 단계 문서 승인만 기다리지 않는다. 기존 guard를 우회하거나 과거 full 승인 false를 true로 바꾼다는 뜻은 아니다.

실제 thesis synthesis와 기존 runner를 확인했다. Hazelnut full110의 SwinIR/RRDB-PSNR/RRDB-ESRGAN 비교는 이미 끝났으므로 같은 결과를 다시 만드는 일은 우선순위가 아니다. Branch B는 현재 clean 정상 bank 하나를 사용한다. 새로운 개선 후보로 clean/restored 정상 bank와 Bicubic/SwinIR query의2x2를 제안해 복원된 정상 분포에 맞춘 bank가 탐지를 개선하는지 검증하도록 했다. 동일 fit 경로·벡터수/선택·query를 유지하고 정상 calibration을 분리한다. 개선을 보장하지 않으며 기존 protocol family와 구분한다.

실행 역할은 주형의 PCB full 경로 구현·실제 cohort/후처리와 지혁의 normal-bank2x2로 나눴다. CPU는 후자의 코드/분석을 맡고 주형과 PCB 공통 파일을 동시에 수정하지 않는다. 후속 seed/category 반복, 현실 열화 조건의 복원 후보, 선택 조건의 다른 detector 검증을 열어둔다. 모든 모델·열화·시드를 한꺼번에 조합하지 않고 서로 다른 질문에 답하는 결과를 만든다. 현재 자료에 없는 실행 시간/효과/성공 수는 채우지 않았다.

새 계획과 대체 프롬프트는 outputs/research-expansion-20261031/에 저장했다. 직전의 제한 smoke 후 종료 프롬프트보다 넓은 이번 지시를 우선한다. 이번에는 계획·문서·기록만 갱신했고 모델/연구 metric/source/공개 Git은 바꾸지 않았다. 이 노트는 계속 ignored/untracked local-only로 유지한다.

## Stage 44 - 지혁 반환의 실제 범위와 실행 중심 장기 배분 (2026-10-31)

지혁 ZIP6개 파일/manifest5개를 실제로 확인했다. 파일명733e320a와 달리 환경 JSON의 HEAD는83ef04e였다. GitHub443 연결 실패로 공개865f 이후 코드를 보지 못했고 실제 주형bank도 없어서 새 경로 검토를 못한 상태다. 이 NO_GO를 최신공개8abed 코드가 실패했다는 결론으로 옮기지 않았다. 옛 lazy loader와 sample metadata 귀속에 대한 작은 반례는 실제producer가 오류를 만들었다는 증거가 아니며 검증 범위 설명에 반영했다. 현재 reader의 관련9개 테스트만 실행해1.89초에 통과했고 전체pytest/옛probe는 반복하지 않았다.

지혁의 설치RAM16GiB·가용7.84GiB·C여유19.33GiB는 보고 snapshot이므로 nativePCB를 맡기지 않는다. 224MVTec 작업은 해당계획으로 새 자원확인을 하되 native20.42GiB gate를 그대로 적용하지 않는다. 지혁에게는 검토뿐 아니라 bank-domain실험 코드구현부터3category/3seed/4cell queue와 제한된EfficientAD를 맡겼다. ActualPCBbank를 받지 못해도 독립 연구를 시작하게 했다. 주형은PCB full과Screw endpoint/현실열화복원 비교를 맡고 CPU는분석·입력전달을 맡아 실행파일동시수정을 줄인다.

GitHub에 다시 막힐 수 있어83ef→8abed 공개4commit만 incrementalbundle로 만들었다. 변경text22버전검사와bundleverify/list-heads가 맞았고60KB정도다. 데이터/weights/bank/arrays/venv/private원본이력은 없다. 이bundle은기존공개code만전달하며 새로운bank-domain/full구현을포함한다고쓰지않는다. 새 작업자가직접구현할범위와이미끝난검증을프롬프트에서구분했다.

계획된36/56평가조건은실제완료성과가아니며자원/시간에따라완전한batch로진행한다. 두GPU를실제연구에활용하면서도같은sample의seed반복을독립표본으로세지않고각family를분리한다. 사용자앞의중계가중국어로잘못출력돼즉시한국어로정정했다. 새문서는한국어와기술식별자위주로확인한다. 이번에는source/GPU/metric을바꾸지않고검토·작업묶음·오프라인전달파일·진행기록만추가했다. 이노트는local-only다.

## Stage 45 - CPU 분석·입력 전달 경로 구현과 공개 (2026-11-02)

GPU 실행 소유권을 나눈 상태에서 CPU가 새 모델 runner를 다시 만들지 않고 저장 결과 분석과 전달을 완성했다. 앱 worktree 도구가 중첩 repository 경로를 허용하지 않아 Git의 별도 worktree/branch를 사용했고 원본79a1c0f와 기존 integration8abed72를 보존했다. Public exp/bank-domain-analysis commit은 1f0c801df111357d92bb759ccb051f3832008286다. 원격과 새 수신본의20개 source/doc 파일 및 기존 fit-source20/reference7이 일치한다. Dataset·weights·bank·prediction·RGB·venv·private note는 공개하지 않았다.

분석에서 중요한 분리는 stored dataset pooled AU-PRO와 per-image paired 평균 CI다. 같은 이미지를 세 seed에서 평가했다고 독립 표본을 늘리지 않고 within-seed CI와 between-seed descriptive variation을 나눴다. 동일 query의 bank별 quality는 한 번만 센다. Protocol/checkpoint/source가 다르면 자동으로 다른 그룹이 되며 duplicate run은 독립 반복으로 세지 않는다. Producer의 source/input/bank digests를 bind하지만 raw 배열 없이 원격 실행이나 실제 prediction 내용을 독립 검증했다고 쓰지 않는다. Normal per-image AU-PRO는 해당 없음이다.

원본 MVTecAD에 세 category가 모두 있어 추가 다운로드 없이 private category ZIP과 file/split manifest를 만들었다. Seed11의 fit/cal은 Hazelnut313/78, Screw256/64, Capsule175/44이며11/23/37을 기존 split helper로 생성했다. 원본 license/readme와 공식 CC BY-NC-SA 출처를 보존했다. Archive 안의 source entries575/603/464가 hash에 맞았지만 RGB/GT를 decode하거나 새 성능/geometry 검증을 한 것은 아니다. Capsule test 성능을 보고 방법을 바꾸지 않았으며 파일 전달 자체를 새로운 연구 결과로 세지 않는다.

현재 실제 저장 결과10행/3protocol 그룹만 master로 옮겼고 새 bank-domain GPU 결과나 그림은 없다. 기존 지혁 ZIP은 automated metadata receipt를 cache해 두 번째 요청에서 중복 검사를 건너뛰었다. Receipt의 성공을 raw arrays/model source/GPU acceptance로 승격하지 않는다.

관련37개와 전체603pass/3skip, 기존 CPU smoke2행을 확인했다. 첫 중단된 full run의 완료 기록은 없었고 Nov02의 새 run256.99초가 실제 완료 근거다. Skip2개는 실제 가용RAM이 기존 reserve를 포함한 조건보다 작았기 때문이며 낮추지 않았다. 나머지는 code-only worktree에 optional dataset이 없어서다. GitHub 수신본37개/CPU smoke2행도 통과했고 원본 .venv와 pinned submodule cache 재사용 사실을 명시했다.

새 offline bundle은 공개5commit만 포함하고 이전4commit bundle은 보존했다. Code package와1.2GB 정도 category inputs는 분리해 GitHub 연결 문제와 실제 데이터 전달 문제를 따로 해결했다. 다음은 지혁이 공개 handoff의5파일 계약으로 결과를 내고 주형이 PCB 실험을 계속하는 것이다. CPU는 실제 반환이 오면 기존 분석 경로로 바로 표·그림·근거를 만든다. 이 노트는 local-only로 유지한다.

## Stage 46 - 저장 prediction 확장과 실제 CPU 대조군 (2026-11-08)

사용자 요청에 따라 새 검토 gate만 늘리는 대신 기존 prediction에서 검사 면적별 localization과 운영 지점을 계산하고, GPU 담당과 소스가 겹치지 않는 HOG 대조군을 실제 실행했다. HOG는 공식 라이브러리와 0.5625MiB descriptor bank를 사용해 현재 CPU 자원으로 전체 test와 seed 반복을 처리할 수 있다. 이 선택의 범위는 특징 기반 대조군이며 기존 PatchCore source/model은 바꾸지 않았다.

저장 SwinIR 결과의 top1% pixel recall delta는 Hazelnut−0.116%p, Screw+24.309%p였다. Screw scratch_head/neck에서 큰 평균 증가가 있었고 thread_top은23장 중10장이 감소했다. Hazelnut mean fusion의 fixed operating threshold에서는 기존 미탐3장을 얻고1장을 잃어 net2장이 개선됐지만 paired CI는0을 포함한다. 기존 primary pooled AU-PRO와 negative gate 결정을 이 새 supplementary 분석으로 바꾸지 않는다. FPR0/40의 exact95% 상한8.810%와 1% 목표의 zero-error 정상 표본368장 계산을 함께 기록했다.

HOG18조건에서는 세 seed 모두 sharpening PSNR/SSIM 증가와 pooled AU-PRO 감소가 함께 관측됐다. 평균 delta는 Hazelnut−0.003956, Screw−0.026889다. 이 detector의 degraded-query 절대 성능이 낮아서 수치와 그림에 Clean/Bicubic의 전체 절대값을 남겼다. Seed11을 본 뒤23/37을 추가했다는 시점도 기록했다. 같은 영상의 seed delta를 먼저 평균해 anomaly189개 영상 단위로 분석하며 567개 독립 영상으로 늘리지 않는다.

학습된 복원도 CPU에서 처리 가능한지 정상 calibration3장으로 실제 측정했다. 약1초/query, process OS peak447848448B로 확인해 기존 SwinIR checkpoint의 고정된 네 번째 query 조건을 추가했다. Test 결과 전에614개 calibration/test union을 단일 cache로 복원하고 여섯 bank/split을 재사용하도록 정했다. GT는 cache에 전달하지 않고 query generation이 끝난 뒤 evaluator 입력으로만 읽는다. 모델/threshold 선택이나 원래 GPU source 변경은 없다. 이 단계는 현재 실행 중이며 완료 후 결과와 최종 commit을 덧붙인다.

Git 원본·GPU 구현·private note를 분리했다. 임시 폴더 ACL 오류와 빈 submodule 테스트 실패를 해결했으며 원본 결과를 바꾸지 않았다. Source clone 중 자동 LFS 예제 파일 수신을 중단하고 process-local skip을 사용했다. 개인 노트와 dataset RGB/GT·bank·prediction은 local-only로 유지한다. 공개 가능한 요약 수치와 코드는 별도 branch에서 관리한다.

Stage46 완료 기록. SwinIR614개 cache와 기존 HOG bank6개 재사용을 실제 완료했다. 동일한 정상 fit/calibration과 x4조건에서 SwinIR의 평균 pooled delta는Hazelnut+0.072742, Screw+0.133538이고, sharpening은−0.003956/−0.026889였다. 둘 다quality가 올랐으므로 이 추가 family에서 quality gain 하나로 localization 방향을 정할 수 없었다. SwinIR 내 per-image regression도 각각4/2/1장,19/19/27장으로 남았다. Weak HOG baseline의 절대값과 이 한계를 공개 그림/보고서에 함께 남겼다. 세 seed의 image-평균 CI를 dataset-pooled CI로 바꾸지 않았다.

전체623pass/3skip과 fresh GitHub receiver20pass/smoke2행을 확인했다. 공개 branch exp/cpu-research-expansion, commit b24750074f887304d6b50fc8bcd00b2ea7e14410이다. Code/runtime는 uncommitted 상태로 실행했고 실제 runtime source digest/base1f0c/dirtytrue와 나중의 공개commit을 구분했다. Windows JSON LF정규화는 설정 내용의 동등성으로 확인하고 원본run bytes는 보존했다. Dataset/RGB/GT/rawmap/bank/가중치와 이 노트는 공개하지 않았다.

새 CPU 대조군으로 다음 질문을 구체화했다. 학습된 복원의 feature alignment 회복과 은폐될 수 있는 defect 반응을 bank/query2×2와 비교할 필요가 있다. 현재 HOG의 degraded 절대 성능이 낮아 이를 PatchCore 일반 결과로 확장하지 않는다. GPU 두 사람의 execution source를 동시에 수정하지 않고 기존 read-only bank-domain analysis/reporting 계약으로 반환을 연결한다. 이번 CPU queue는 완료했고 다음의 구체적 실험 질문에 따라 batch를 정한다.

## Stage47. CPU 정상 bank/query domain 분리 (2026-11-09)

앞선 clean-bank HOG에서 열화 query 절대 성능이 낮아, 같은 정상 fit 영상과 patch ordinal의 bank domain을 바꾸는 비교를 추가했다. 실제 신규 36조건을 완료했고 clean anchor 12조건은 재계산하지 않았다. 같은 query의 RGB와 화질은 bank 사이에서 일치한다. 전용 bank끼리의 SR−Bicubic 평균 pooled delta는 Hazelnut +0.027039, Screw −0.004475로 기존 frozen clean-bank 조건과 다른 값을 보였다. 두 설정을 별도 배포 조건으로 남긴다.

세 bank 결과를 본 뒤 하나의 bank를 쓰는 50:50 후보를 결과 계산 전에 고정했다. 같은 4096 ordinal에 domain 하나씩을 배정하며 비율 탐색이나 feature 평균은 하지 않았다. Query별 정상 calibration은 유지했다. 네 category/query 평균 모두 전용 bank보다 낮았다. 이 후보를 개선 성공으로 선택하지 않고 용량 제약의 trade-off와 사례별 regression을 보고한다.

같은 영상의 세 seed를 먼저 평균한 conditional image bootstrap과 pooled point estimate를 구분했다. 두 category는 탐색 이력이 있고 HOG 결과이므로 PatchCore 일반 결론이나 인과 기제로 확장하지 않는다. 다음 질문은 GPU PatchCore에서도 같은-query 정상 bank 적응 효과가 존재하는지다. Capsule은 보존한다.

정상 fit SR cache의 일시적 Windows IO 오류는 checkpoint 교체 retry만 수정하고 AST 비교와 548개 완료 RGB hash를 확인해 재개했다. 원본 완성 cache와 중단 증거를 보존했다. 전체 643 pass/1 skip, 최종 분석 6 pass, smoke 2행을 확인했다. 공개는 코드·테스트·수치만 별도 branch로 하고 이 노트는 ignored/untracked로 유지한다.

Stage47 전달 완료. 공개 commit a90764e3addc840f5867c82a85a68471a22e75f1, branch exp/cpu-bank-domain-study. 원격과 fresh receiver HEAD/source10개/숫자·그림 hash를 확인했고 receiver32pass/CPU smoke2행이 통과했다. fusion.py는 명시적 CRLF checkout 규칙으로 raw runtime hash가 유지된다. Git LF blob과 checkout bytes를 구분해 확인했다. 빈 data/images/.gitkeep는 데이터 수신으로 세지 않았다. 실제 배열과 이 노트는 공개하지 않았다. 정해둔 CPU queue는 완료했으며 GPU 반환 전 임의의 추가 ratio/category 탐색을 반복하지 않는다.

## Stage48. 실물 제조·검사 장비 후보 논의 (2026-11-09)

사용자는 최종 산출물에 계측기·실물 하드웨어를 포함하고 싶다고 명확히 했고, 취업 방향을 반도체·생산기술·양산기술·스마트팩토리로 답했다. 이 선호는 이후 산출물 설계의 기준이다. 기존 CPU 연구 queue 완료와 별개로 실물 시연 장치가 새 논의 대상이다.

제안은 정지형 실제 기판 AOI 검사 셀이다. 지그/투입 감지→촬영→기존 복원·탐지→MCU/PLC 완료 신호→OK/NG 표시·분류를 연결한다. 직접 설계할 전자공학 부분은 LED 정전류·광량/온도 계측과 안정화, 촬영 동기화, 트리거/전류/판정 GPIO 파형 측정이다. 확장 후보는 pogo-pin 저전압 전기검사 지그와 이송·배출 handshake다. 아직 구매·회로 확정·제작·성능 측정은 하지 않았다.

연구 연결은 조명·초점 등 물리 조건에서 복원/정상 bank 구성에 따른 미검·과검·검사시간을 비교하는 것이다. 새 실물 보드와 촬영계에는 별도 정상 bank/calibration 및 board 단위 분할이 필요하다. 반복 촬영은 재현성 자료로 다루고 독립 보드 수로 늘리지 않는다. 연속형 광량/계측값의 변동과 binary 판정 일치율을 구분한다. 노출 timing은 카메라의 실제 trigger/exposure I/O 지원을 확인해야 한다.

참고 공식 자료는 Samsung DS 설비기술/스마트팩토리 직무 소개, TI TIDA-01081 조명 제어 reference, Basler acquisition timing/Exposure Active, NIST 측정 반복성·재현성 지침이다. 취업 연결은 이 직무 내용과 프로젝트 범위를 비교한 제안이며 채용 성과를 측정한 결과가 아니다. 예산·마감·보유 camera/oscilloscope/PSU/DMM/PLC는 미확인이다. 다음은 이 자원 정보를 확인해 첫 장비 범위와 부품표를 정하는 것이다.

## Stage49. 기업 공개 과제·Anyshot 수상과 실물 전략 검토 (2026-11-09)

사용자 제공 graduation_project_strategy_and_summary.md를 참고했다. 서강대 공식 공지에서 김태우·강석주 연구팀 Anyshot의 2026 삼성디스플레이 산학협력 논문대회 금상을 확인했다. 소개된 산업 제약은 제품군 간 정상 데이터 수량 불균형이다. 원문 논문·공개 코드·심사표는 이번 검색에서 확보하지 못했다. OpenAlex 제목 검색은 1회/최대 5건으로 제한했고 반환 0건이었다. 학교 연구 소개와 삼성디스플레이 공식 검사영상·희소불량 해커톤 과제, KLA 공식 검사·review 자료를 비교했다.

옵션A에 광량·초점 기준 점검과 실제 재촬영을 붙이는 실물 검사 스테이션을 우선 제안했다. 두 경로 불일치는 재검 요청으로 사용하고 원인은 후속 분석한다. 실제 재조명·재초점 후 재취득의 비용과 미검·과검을 측정한다. 확장 후보는 품종·드리프트 recipe 검증과 계측 기반 검색·장비 시퀀스 최적화다. 현재는 설계 후보 단계다.

첨부 글의 90% 즉시 통과/10% SR, 8초→0.5초와 AU-PRO 손실 0.001은 미측정 목표다. 기존 12.49%는 특정 CPU 10장/2회 비용 모형이다. Stage47은 정상 feature bank도 교체한 HOG 실험이며, few-shot calibration-only/PatchCore 현장 자동 보정은 별도 검증 대상이다. 실제 CPU calibration은 Hazelnut 78/Screw 64장이고 PCB 180장과 family를 구분한다. 1GiB bank payload와 탐지 성능, PC Busy와 장비 cycle time, 디지털 48tile과 물리 좌표의 범위도 각각 기록한다.

BH1750의 typ120ms/16ms 측정과 펄스광 계측의 대역폭을 구분한다. 빠른 파형에는 photodiode/TIA와 scope를 고려한다. LED 전류·실제 노출·완료 GPIO를 계측한다. 예산·보유 stage/camera/scope·마감은 미확인이다. 다음은 가용 자원으로 정지형 장비 범위를 정하는 것이다. 출처와 상세 판단은 outputs/industry-physical-strategy-20261109/REVIEW.md에 local-only로 보존했다.


## Stage50. 주형 full cohort 반환과 다음 실행 분담 (2026-11-09)

반환 ZIP의 213개 명시 파일과 저장 metadata를 검토했다. PCB 1,140unit/54,720query, calibration 59조건, source 26개와 timing 110,065행을 대조했다. 원본 map/bank 배열이 없어 pooled 지표는 저장 수치를 사용한다. Selection index 값 인코딩 hash와 NPY 파일 hash를 별도 필드로 확인해 bank 변경으로 잘못 판단하지 않았다. Windows CRLF 차이는 실행 LF hash를 유지하는 attributes로 처리했다.

PCB SwinIR의 pooled AU-PRO 이득 +0.00483155와 고정 threshold의 미검 증가 29→46/100을 함께 보존했다. 100개 anomaly 사례의 평균 delta +0.00372962와 post-hoc paired CI를 추가했으며 고정 fit 조건부 per-image 구간으로 표시했다. Pooled CI와 seed 반복 일반화는 확보하지 않았다. Regression33개 중 suppression5/geometry후보28이다. 두 map 표현과 board max score가 다른 공간 집계라는 점을 다음 진단 대상으로 삼았다.

추가 열화 12조건의 ESR 계열 최고는 전체 정밀도로11개다. Screw blur0.8의 작은 SwinIR 우세를 반올림 동률과 구분했다. LPIPS 상관과 Screw endpoint의 반대 localization 방향을 함께 보고해 단일 화질 지표로 model을 고르지 않는다. Screw의 낮은 Image AUROC도 원인 미확정 실패 결과로 유지한다. Native/PIL/MATLAB/realistic/HOG family는 분리된 master133행으로 남겼다.

다음 역할은 주형의 저장map27개 부분 전달·image score 원인 진단·작은 exact batch 실험, 지혁의 기존 PatchCore bank/query2×2 완료와 사전 고정 Bicubic-bank 대조군, CPU의 반환 통합·선택 map 공간 분석·장치 인터페이스 simulator다. 역할별 source 소유권을 분리해 실행을 서로 막지 않게 한다. 선택9개 map 사례는 정성 분석용이며 population 추정에 쓰지 않는다. 실물 장비는 아직 설계 후보이고 I/O simulator의 지연을 물리 계측으로 표현하지 않는다.

공개 수정5c4ddd8과 분석6472f69를 별도 branch로 push하고 원격 hash를 확인했다. 신규 관련15pass, peer89pass/1skip, smoke2행을 확인했다. 깨끗한 receiver에서도15pass/smoke2행이다. 처음 RAM fixture mock의 잘못된 module을 실제 getter로 정정했고 production guard는 보존했다. 이 노트는 git/info/exclude 적용과 tracked 목록 부재를 확인했으며 공개하지 않았다.


## Stage51. 검사 제어 계약과 CPU replay (2026-11-09~10)

저장 prediction을 part/cycle/recipe 식별자에 연결하는 software controller를 구현했다. Synthetic6cycle과 PCB 저장score600개 replay로 request/ACK, 중복·stale·timeout·재연결을 검증했다. 물리 I/O와 장비 latency는 별도 계측 대상으로 남긴다. Process 내 reconnect와 장치 재시작 시 부품 위치 복구를 구분했다. Public source7d5c177, 실행 당시6472f69기반 dirtytrue와 source SHA를 따로 보존했다.

전체674pass/3skip과 clean receiver45pass/smoke2행을 확인했다. RAM 전제조건2개와 optional data fixture1개 skip을 유지했다. Receiver의 임시 폴더/들여쓰기 오류를 수정하고 재검증했다. Private note는 public commit에서 제외했다.

## Stage52. 실제 map·진단 반환과 입력 병목 해소 (2026-11-10)

주형의 진단27파일과 map ZIP 최상위51파일 hash가 일치했다. 중첩bank-source manifest가 가리키는 미전달10파일은 historical receipt로 한정했다. 실제27map은 bounded chunk로 SHA/shape/dtype/finite를 확인했다. Native9case 분석은 고정2GiB 여유가 부족해 자체 worker 종료 후에도차단됐다. 기준을 낮추는 대신32GB 주형 호스트로 같은 source와 metadata를 전달한다.

FP3/100을 유지하는 threshold plateau에서 TPR은 Bicubic0.62~0.82,SwinIR0.59~0.70이었다. 같은 FPR의 한 점으로 F1 변화의 원인 기여도를 확정하지 않는다. 기존600scalar cross-match와 affine 정규화의 판정 일치를 확인했다. Peak-in-GT와 AU-PRO regression을 함께 해석하고 matched-bank 미회복을 정보 소실 증명으로 취급하지 않는다. 원본 threshold/결과는 보존했다.

Screw endpoint의 원본 metadata로 seed11/train320/fit_performedfalse를 확인해4조건의 metadata를 보강했다. 성능 수치는 원본과 같고 master133조건/9groups를 유지했다.

지혁 patch의 all-patch IdentitySampler는 legacy 설정과 같아 HOG4096/PCB262144 cap을 새로 넣지 않는다. Test의 실제 checkpoint/Git/RAM 의존성만 격리해11pass를 확인했다. Producer source provenance, ROI gap과 scalar export는 owner가 연결한다. 동명payload analyzer와 CPU consumer는 소유권을 나눈다.

Hazelnut/Screw만 private team transfer ZIP으로 준비하고 새 directory에서1177파일을 검증했다. 원래 publisher archive가 보존되지 않아 그 checksum은 미확인이다. 새813040630B transfer archive의 실제 SHA와 역할을 명시하고 license/readme/출처를 동봉했다. Dataset·bank·weights는 Git에 올리지 않았다.

다음은 지혁의 bank-domain24조건과 matched Bicubic4조건, 주형의9case 공간 분석과 noise32조건이다. Noise 반복은 bank/splitseed11을 고정하고 noise realization23/37만 바꾼다. Deterministic JPEG 중복과 같은 영상의 seed 반복을 독립 실험 표본으로 늘리지 않는다. CPU는 반환을 protocol별로 통합한다. 실제 bank-domain 성능은 아직0/24다.

사용자가5시간 간격 재개를 요청해 current-thread heartbeat를 설정했다. 정확한 계정 reset 시점은 조회하지 못했다. Local 예약은 PC/app이 켜진 상태에서 동작한다. 자동 memory observer 장애는 사용자에게 알리고 파일 기록을 유지했다. Worker/OS 설정은 바꾸지 않았다.


## Stage53. 담당자별 Git 전달·반환 창구 (2026-11-10)

반복 ZIP 전달을 줄이기 위해 이미 공개된7d5c177 위에 handoff/juhyung과 handoff/jihyuk을 분리했다. 담당자가 한 ref의 실행 지시를 받고 같은 ref에 텍스트 결과를 반환한다. CPU는 run-id/receipt/source commit을 기준으로 새 결과만 검토한다. 실행 feature source와 CPU 분석 source는 별도로 기록해 동명 bank-domain analyzer의 소유권을 유지한다.

저장소가 public이므로 branch 분리는 접근 통제가 아니다. Dataset/GT/RGB/raw map/bank/checkpoint/비공개 노트는 기존 private 보관을 유지한다. 공개 결과의 scalar·metadata·hash만 Git으로 전달한다. 실제 array가 필요한 분석은 보유 호스트에서 수행하거나 private 채널을 이용한다. 지혁의 최초 private dataset 전달과 GitHub443/Write 권한은 아직 확인해야 한다.

새 worktree의 submodule 초기화와 Windows CRLF 의존성이 전체 테스트에서 드러났다. 같은 upstream commit의 두 Python 파일은 텍스트가 같고 checkout bytes만 달랐다. Frozen hash와 연구 코드를 변경하지 않고 Git checkout 규칙을 맞췄다. 필요하지 않은 upstream LFS bank 자동 다운로드도 제외했다. 전체 실행 결과와 실패 항목의 focused 재검 결과를 분리 기록했다. 원본 source와 기존 연구 결과는 보존했다.

현재 독립 CPU queue는 완료됐고 다음은 주형의9사례/noise32, 지혁의bank-domain24+4 저장 결과를 protocol별로 통합하는 단계다. 새 metric·모델 선택이나 미도착 실험 행을 생성하지 않는다. 실물 제어는 기존 fake 계약까지 검증됐고 하드웨어 사양은 미확인이다.


## Stage54. 두 담당자의 반환과 설계 결정 통합 (2026-11-11)

확인한 자료는 주형 52b4c23의 9사례와 ba4672d까지의 noise 4run 공개 receipt·CSV·metadata다. 두 담당자의 private 결정 원문은 수신 전이다. 기존 RUN_RECORD에서 확인되는 판단을 통합하고 당시 기록과 현재의 사후 해석을 구분했다. PROGRESS에는 실제 수행·결과를, 이 노트에는 문제·대안·선택 이유·수정 전후·남은 질문을 기록한다. 각 담당자는 ignored outputs/private-decisions/에 결정 요약을 작성해 비공개로 반환한다.

9사례에서 normalized seam gradient와 raw/비율의 방향이 달랐다. Variant별 calibration scale 차이를 함께 고려하도록 해석을 보완했다. Geometry 후보 2/3의 raw gap도 감소해 기존 taxonomy를 유지하면서 기전 분리의 한계로 남겼다. Manifest의 runtime_source_commit은 원본 prediction 54cf를 가리킨다. 분석 source 1e6의 파일 SHA를 별도로 연결했다. 원격 사례 PNG는 추가 비공개 수신이 필요하다.

Noise 반복은 정상 bank/split seed 11을 고정한 두 draw 23/37이다. 같은 image ID를 묶어 CI를 만들고 v1은 historical anchor로 남겼다. σ15의 SwinIR 열세가 두 category에서 반복됐고 ESR 대비 pooled 차이의 부호도 유지됐다. Screw σ5는 pooled point와 mean per-image의 방향이 다르며 CI가 0을 포함한다. 다른 학습 seed에 대한 일반화는 추가 확인이 필요하다.

후속 작업은 두 변수의 영향을 따로 확인하도록 배분했다. 지혁의 bank-domain은 같은 query에서 정상 reference 변경을 평가한다. 주형은 같은 저장 map에서 image-score readout을 바꿔 비교한다. 다섯 집계 규칙을 새 label 비교 전에 고정하고 정상 calibration으로 q0.99를 정한다. 저장 결과를 재사용해 Screw ranking/operating-point 문제를 검토한다. 계획된 최대 200cell은 같은 예측의 재평가이며, 독립 cohort 수는 기존과 같다.

이전 자연어의 clean/restored query 표현을 정정했다. 실제 코드와 CPU 계약의 query는 bicubic_x4/swinir_x4이며 bank는 clean/swinir_restored다. Bicubic-bank extension은 두 query를 평가하는 새 4조건이다. 기존 clean-bank/Bicubic-query baseline을 재사용하도록 전달했다.

지혁의 GitHub 443 실패 원인은 현재 자료만으로 확정할 수 없다. CPU 호스트에서는 같은 원격에 접속했고, 공개 83ef04e만 있는 수신 저장소에서 최신 handoff 코드 bundle을 검증했다. 데이터 ZIP은 이미 checksum이 맞으므로 재전달 없이 오프라인 코드 경로로 설치·실행을 재개하도록 했다. 네트워크 진단과 별개로 이 실행 경로를 사용할 수 있다.

Hazelnut의 사용자 경로는 v1_bank_dir 한 필드에 있었다. 해당 필드의 상대경로 사본과 원본 hash 연결을 공개했고 실행 원본은 보존했다. 과거 경로는 기존 Git 이력에 남는다. 중앙 private 노트와 실제 GPU 결정 요약은 공개 대상에서 제외한다.

최종 CPU 분석은 615ae7d, 전달 ref는 주형 346f95e6 및 지혁 21b690b5다. 최종 오프라인 v2는 수신 테스트 17개와 CPU smoke 2행, ZIP 및 내부 payload hash 검증을 통과했다. 다음 확인 대상은 지혁의 실제 24+4조건, 주형의 저장 map 집계 결과, 두 담당자의 private 결정 요약 및 사례 PNG다.


## Stage55. 집계 방식 대조와 추가 구매 없는 촬영 산출물 (2026-11-11)

주형의 실제 private 결정 기록을 수신했다. 원본은 ignored outputs/image-score-return-review-20261111/juhyung-20261111.private.md에 보관한다. 기록은 당일 결정(A1~A7)과 과거 문서에서 사후 정리한 부분(B)을 구분한다. Source40d57dd를 기반으로 한 이유, 규칙 문서4afae6d의 선행 기록, original score/map payload 두 anchor의 역할, 실제 payload 메모리 계획과 exporter의 JSON 문자열 치환을 확인했다. 기록이 없는 과거 선택 이유는 미기록 상태로 유지한다.

한 unit이 약0.22초라 category마다 약7초가 걸려 두 번에 나눠 반환한 판단을 수용했다. 앞으로 짧은 작업은 category/session 단위로, 긴 작업은 검증 가능한 완료 단위로 전달하는 편이 적절하다. 모든 unit의 개별 metadata는 유지한다. Screw 공개 사본의 한 줄 CR 소실은 새 정정 문서로 반영했고 원본 반환과 결과는 보존했다.

CPU에서200cell scalar를 검산하고 fixed rule 대비160 paired AUROC 구간을 만들었다. Screw top1%는14/20unit에서 original보다 낮았고, 다섯 규칙의 낮은 Image AUROC가 유지됐다. 집계 변경만으로 문제를 해소한 결과는 얻지 못했다. Bank/query domain 영향은 지혁 대조를 기다린다. 단순 max vs top-k 차이와 source-domain 가설을 구분한다. 같은 영상·노이즈 조건 반복을 독립 표본으로 합치지 않는다. 구간은 결과를 본 뒤 추가한 exploratory pointwise 분석임을 기록했다.

세 사례 PNG를 실제로 열었다. 047의 작은 component,006의 핀 영역,050의 좁은 GT와 비교 map의 위치를 확인했다. 그림은 RGB/GT가 포함돼 기존 local-only 보관 범위를 유지한다. 선택 사례 그림으로 전체 population이나 원인 기전을 확정하지 않는다.

사용자는 추가 부품 구매를 원하지 않으며 스마트폰·책상 조명/플래시를 사용할 수 있다고 답했다. 실물 부품의 수량·정상/결함 상태는 미확인이다. 고정된 카메라·기판에서 조명만 바꾸는 첫9장을 제안했다. 기울기와 노출 자동 변화는 별도 metadata로 기록한다. 세 물리 조명에서의 입력 품질·판정 변화·재촬영을 시연하면 기존 SR 결과와 입력 촬영 관리의 차이를 설명할 수 있다. 실제 사진·성능은 아직 없다.

주형에게 독립 설계 검토와 phone_* manifest/품질 계측·정렬·리포트·synthetic 테스트 준비를 배분했다. Photometric stereo는 조명·카메라 보정과 실제 입력을 확인한 뒤 확장 여부를 판단한다. 기판이 한 개뿐이면 동일 물체 조건 반복성 범위로 보고한다. 안정성 개선은 미검·오검·미해결 비율과 함께 검증해야 한다. CPU는 반환 통합을, 지혁은 bank-domain을 계속 맡는다.

## Stage56. 12월1일 발표에 맞춘 독립 설계와 검토 순서 (2026-11-12)

사용자는Fable5.2로설계한뒤우리가진행한전체검토를받아실험을이어가길원하며,주형에게더많은완결작업을맡기고발표일12월1일에맞춰속도를높이길요청했다. 기존12월초초안의12월1~3일마무리는발표일보다늦어11월23일핵심실험정리,27일포스터초안,29일최종정리로앞당겼다.

독립설계초안을먼저저장하고전체근거를검토한수정안과대조하도록순서를정했다. 현재165prediction조건/8families/13protocolgroups와별도200readoutcell을근거인계에연결했다. CPU HOG와GPU PatchCore,noise draw와bank seed,selectedcase와population,per-image와pooled CI의범위를유지한다. 설계에서부족한근거를먼저식별하고주력구현하나와baseline을고정해실행한다.

추가구매가없고물체가아직정해지지않아보유기판의핀/커넥터를우선제안했다. 없으면USB-A금속커넥터처럼작은형상과반사가있는보유물을사용해별도의실물조명실험으로표시한다. 카메라기울기와조명변화를처음부터섞지않고첫9장에서정렬·노출·input품질을확인한다. 동일물체한개로가능한주장과실제정상/결함평가에필요한입력을구별한다.

주형의과제는설계검토·구현·저장control·사진연결·포스터근거/화면까지완결된유한queue다. 지혁의bank-domain과CPUconsumer소유권은유지한다. 실제사진대기중에도synthetic E2E와기존근거의포스터그림을완성하도록했다. Fable설계와새실물성능은아직수행된결과로기록하지않는다.

## Stage57. 선택 근거 기록과 실험 병행의 명시 (2026-11-12)

사용자는설계의견과함께선택과정의근거를기록해받고,필요한실험을동시에계속하길요청했다. 이전독립설계→전체검토→실행표현은기존고정실험전체의대기로해석될수있어NEXT_TASK와근거문서의해당문구를수정했다. 새로운평가방법의기준고정과기존실험의진행을분리했다.

두담당자에게실제수행PROGRESS와비공개선택근거RESEARCH_EVOLUTION_LOCAL의작성·반환을명시했다. 근거파일과가정,대안과선택이유,기준과관측값,수정전후와남은질문을연결한다. 당시기록과사후해석을구분하고미기록과거판단을추측해채우지않는다. 짧은완료단위마다두기록을각각공개/비공개경로로받아중앙노트에통합한다.

병행은작업흐름의병행이다. 자원경합시기존guard안에서무거운GPU작업은순차화하고검토·문서·그림을같이진행한다. 지혁bank-domain과주형phone/설계,CPUconsumer의소유권은유지한다. 실제GPU작성·반환은새실행에서확인할대상이며문서를보냈다는사실과구분한다.

## Stage58. Fable 재검토와 구현의 실제 근거 확인 (2026-11-12)

새공개4반환은초기Opus5.5작업과Fable5.2재검토를구분했다. Fable v1은기존초안·근거를본상태였고독립성한계를명시했다. 이한계를보존하며실제자료검토·수정·재현결과를채택한다. 새로운private결정원문은아직미수신이며이번통합은공개기록범위다.

정렬보간이품질지표를편향한다는지적은원본화소/투영ROI계산으로수정됐고로컬regression test를포함한24tests가통과했다. 단순반복수재현과물리조명검증을구분한다. HEIC/RAW입력미지원은JPEG안내로수정돼실사진첫입력의형식을명확히한다. 실제조명반사에서의정렬은향후9장으로확인한다.

Historical clean-control3unit/15cell의같은영상/라벨과AUROC를검산했다. Clean에서의작은집계차이와×4에서의image저하가모든규칙에걸쳐남는결과를근거로집계방식만으로설명하는가설을좁힌다. Domain/representation/정보손실의기전은확정하지않고지혁대조를기다린다.

자체synthetic E2E 보고서를실제브라우저에서열었다. Desktop상태이력과detector미연결표시는명확했고모바일은전체가로overflow로본문도잘렸다. 원격source소유권을보존해작은표scroll/본문wrap수정을주형에게반환했다. 입력품질PASS와부품정상판정을구분하며station은모두REVIEW였다. 현재실물성능주장은보류한다.

## Stage59. 주형 비공개 결정 D01~D13 원문 수신·통합 (2026-11-12)

새 원문 SHA256은 26e0173fafee4eafbffc00ec28dc6800f0f252a78e392a9b592d63ec7f6d0fa1이며 공급된9870bytes와 마지막결정D-20261112-13을 확인했다. 원본 byte 사본은 outputs/private-decision-imports/juhyung-20261112-26e0173f/RESEARCH_EVOLUTION_LOCAL.md에 보관했다. 아래 통합본은 줄바꿈과 제목 깊이만 조정했고 원문 표현·수치·불확실성을 보존했다. D01~09의 작성모델은 기록상 Opus5.5,D10~13은 Fable5.2다. [당시]/[사후] 표기를 유지한다. Stage58의 새private원문 미수신 상태는 이 수신으로 해소됐다.

이 통합은 수신된 선택 근거를 보존하는 것이며 원격 실험·수치·모델 사용을 별도 독립 관측한 것으로 승격하지 않는다. 원격 PROGRESS는 각 반환 사본을 중앙에서 수행·결과 단위로 정리하는 현재 방식을 유지한다. 모바일 미검증/Edge viewport 가능성도 전달자가 남긴 한계로 보존하며 CPU screenshot 관측과 구분한다.

### 주형 전달 원문 통합본

### RESEARCH_EVOLUTION_LOCAL — juhyung (private; not in Git)

이 노트는 사용자의 중앙 `notes/RESEARCH_EVOLUTION_LOCAL.md`에 통합하기 위한 것이다.
- 이전 노트 `outputs/private-decisions/juhyung-20261111.private.md`(11-11, 집계 v0.1)를 이어 쓴다. 그 내용은 여기 다시 쓰지 않는다.
- D-20261112-01~09는 Claude Opus 5.5 (`claude-opus-5-5`)가 작성했다. D-20261112-10부터는 Claude Fable 5.2 (`claude-fable-5-2`)가 작성했다.
- **[당시]**는 결정 시점에 남긴 기록이고, **[사후]**는 나중에 정리한 해석이다.

---

#### D-20261112-01 · 독립 초안의 작성 순서와 모델 표기 [당시]
- **문제:** 지시는 "Fable 5.2 독립 초안"을 요구했다. 실제 실행 모델은 Opus 5.5이고, 같은 세션에서 기존 결과를 이미 다뤘다.
- **대안:**
  - (a) Fable 모델 subagent로 작성한다.
  - (b) 직접 작성하고 모델과 독립성의 한계를 명시한다.
- **선택:** (b).
  - subagent 생성은 사용자가 명시적으로 요청할 때만 한다는 운영 원칙이 있다.
  - Fable 5.2를 쓸 수 있는지 확인되지 않았다.
- **절차:**
  - 근거 문서(FABLE_RESEARCH_EVIDENCE_REVIEW)와 phone 문서 3개를 읽기 **전에** 초안을 저장했다. 13:31:08 KST, SHA `efd6a608…6e06`.
  - commit은 `bc62f06`이고, `-text` 속성으로 바이트를 그대로 보존했다.
- **남은 질문:** 중앙에서 Fable 5.2로 따로 독립 초안을 받을지.

#### D-20261112-02 · 핵심 주장 C1–C3과 주력/baseline [당시]
- **근거:** `57235a2` master(165/8/13), `cross_category_summary.json`(30/14/16/40), `paired_auc_intervals.csv`(Screw 80개 구간 중 0 미만 37), legacy Screw `results.json`(clean 0.984).
- **대안:**
  - 주력 구현 후보: 단일 영상 조명 보정 / 다중 조명 정렬·반응 분석 + recipe / photometric stereo
  - baseline 후보: 손으로 든 비관리 촬영 / 정책 없음
- **선택:** 주력은 "품질·정렬·recipe·재촬영 정책 도구", baseline은 "정책 없음(모든 사진 수용)"이다.
- **선택 이유:**
  - 첫 9장만으로 바로 비교할 수 있다.
  - 탐지 성능 주장 없이도 완성할 수 있다.
  - photometric stereo는 보정 근거가 부족하고 12/1 일정에 맞지 않는다.
- **보류:** 사전학습 특징 거리 점수 안정성. phone용 bank와 calibration을 분리할 입력이 없다.
- **성공 기준 (사전):**
  - synthetic 주입 결함이 모두 의도한 상태로 판정된다.
  - 실제 9장으로 report가 끝까지 생성된다.
  - 성능은 주장하지 않는다.

#### D-20261112-03 · v0.2 clean control의 범위와 지표 [당시]
- **문제:** v0.1 보고서의 한계는 "clean 기준선 없음"이었다. NEXT_TASK C는 저장 자료가 있으면 v0.2를 별도로 고정해 평가하라고 했다.
- **확인한 사실:**
  - `outputs/legacy-patchcore/screw-full320-test160`에 clean/bicubic/swinir map이 있다.
  - test 160장의 순서와 라벨이 realistic family와 같다.
  - calibration은 없다(paths 없음, threshold null).
  - Hazelnut clean map은 로컬에 없다. smoke run만 있다.
- **대안:**
  - (a) 재추론으로 calibration을 만든다.
  - (b) AUROC만 쓴다.
  - (c) 하지 않는다.
- **선택:** (b). 재추론은 지시상 자동으로 추가하지 않는다. AUROC는 순위 기반이라 calibration이 필요 없다. family는 `historical_recovery`로 분리했다.
- **Anchor:** A는 원본 AUROC, B는 GT mask로 다시 계산한 pixel AUROC다. GT는 payload 검증에만 썼다.
- **순서:** scope `ba2d4de` 13:36 → 실행 13:37–13:38.
- **관측:** clean은 규칙 전체 0.983–0.984, ×4는 0.43–0.68이다. ×4에서는 모든 규칙이 원본 이하다.
- **해석 [당시]:** 이 family에서 clean과 ×4의 차이는 규칙 선택으로 생기지 않는다. map이 바뀐 원인은 미확정이다.
- **다음:** 지혁의 bank-domain 결과와 대조한다.

#### D-20261112-04 · OpenCV 대신 scikit-image [당시]
- **근거:** venv에서 `import cv2`가 ModuleNotFoundError다. skimage 0.26과 SciPy는 있다.
- **대안:** opencv 설치 / skimage 사용.
- **선택:** skimage. 구매 0원이고 환경을 바꾸지 않으며, CPU 쪽 환경 차이를 줄일 수 있다.
- **비용:** ORB+RANSAC이 1024 px 기준으로 장당 약 3–4초다. 9장은 1분 안쪽이다.

#### D-20261112-05 · noise 추정 함수 교체 (사전 데이터 수정) [당시]
- **문제:** protocol `e6462ef`에 고정한 `estimate_sigma`가 PyWavelets를 요구하는데, 설치되어 있지 않다.
- **선택:** Immerkær 추정으로 바꿨다. 보고만 하는 지표이고 임계값이 없으며, 실제 사진을 보기 전이다.
- **기록:** protocol 문서와 Git 이력에 남겼다.

#### D-20261112-06 · synthetic 기대값 수정 (임계값은 유지) [당시]
- **관측:** σ4 blur의 기대값을 REVIEW(low_sharpness)로 적었는데, 실제로는 정렬이 실패해서 RETAKE가 나왔다. 규칙상 RETAKE가 우선하므로 프로그램 동작은 맞았다.
  - 크기에 비례한 blur도 시도했다. 그런데 working resize 때문에 inlier ratio가 0.27~0.28로 임계값 0.25 근처에 걸렸다.
- **선택:** protocol 임계값은 바꾸지 않았다. synthetic 입력을 1600×1200 고정 크기로 두고, blur를 임계값에서 충분히 떨어진 값으로 정했다.
  - σ8: inlier ratio 0.06 → RETAKE
  - σ1.5: inlier ratio 0.79, sharpness ratio 0.42 → REVIEW
- **이유:** synthetic 결과에 맞춰 임계값을 고치면 사전 고정이 무의미해진다.

#### D-20261112-07 · 탐지기 없는 station 판정 [당시]
- **대안:** PASS를 OK로 보내기 / 항상 REVIEW로 보내기.
- **선택:** 항상 REVIEW로 보낸다. 사유는 `prediction_ref`에 적는다. 품질이 PASS라는 것은 결함이 없다는 판정이 아니다.

#### D-20261112-08 · 공개 PROGRESS의 위치 [당시]
- **문제:** 루트 `PROGRESS.md`는 CPU가 공동으로 관리하는 파일이라, 주형 branch에서 수정하면 충돌할 위험이 있다.
- **선택:** 로컬 `outputs/progress/PROGRESS.md`에 이어 쓰고, 각 반환에 그 시점 사본을 넣는다.
- **남은 질문:** 중앙에서 루트 PROGRESS에 병합할 방식.

#### D-20261112-09 · 브라우저 검증 범위 [당시]
- 데스크톱 1400 px 화면은 확인했다.
- 390 px에서는 `overflow-wrap`을 넣은 뒤에도 텍스트가 잘렸다. headless Edge가 최소 창 폭 때문에 실제보다 넓게 그린 것으로 추정하지만 확인하지 못했다. 그래서 미검증으로 기록했다.
- **다음:** 실제 폰 브라우저나 DevTools의 device emulation으로 확인한다.

#### D-20261112-10 · Fable 5.2 재실행의 범위 [당시]
- **문제:** 조원은 Fable 5.2 검토를 요청했는데 앞선 작업은 설정 실수로 Opus 5.5가 했다. 사용자가 모델을 바꾸고 "다시 실행"을 요청했다.
- **대안:**
  - (a) 전부 지우고 처음부터 다시 한다.
  - (b) 모델에 따라 달라지는 것(설계 초안, 검토, 구현 검토)만 다시 하고, 수치 결과는 재현만 확인한다.
- **선택:** (b). 실험 수치는 코드와 저장 자료로 결정된다. 기존 결과를 보존하라는 지시가 있고, 같은 계산을 새 결과로 다시 집계하면 중복이 된다.
- **한계:** 초안 v1은 독립이 아니다. 문맥 없는 Fable 초안은 새 세션이 필요하다. subagent는 사용자 요청이 없어 만들지 않았다.

#### D-20261112-11 · 품질 지표를 warp 전 화소에서 계산 (사전 수정 2) [당시]
- **문제:** Opus 구현은 지표를 bilinear warp한 영상에서 계산했다. 기준 사진만 warp되지 않는다.
- **근거 (실측, synthetic):** 0.25 / 0.5 px 이동에서 선명도 0.789× / 0.731×, noise 0.45× / 0.29×. 1.0 px(정수 이동)에서는 1.004×.
- **대안:**
  - (a) 기준 사진도 같은 보간을 거치게 한다.
  - (b) ROI mask를 투영해 warp 전 화소에서 계산한다.
  - (c) 그대로 두고 한계로 적는다.
- **선택:** (b). 보간 자체를 지표 경로에서 없앤다. (a)는 이동량마다 평활 정도가 달라 편향이 남는다.
- **수정 전후:** `quality_basis`가 `aligned_roi` → `projected_roi_unwarped`. 임계값과 판정 규칙은 그대로다. synthetic 16행의 판정 변화는 없다.
- **남은 것:** pairwise MAE는 여전히 warp 영상을 쓴다. 작은 차이는 해석하지 않는다고 protocol에 적었다.

#### D-20261112-12 · HEIC 미지원 [당시]
- **근거:** PIL 12.3에 HEIF 등록이 없고 `pillow_heif`도 없다. 안내서는 "JPG/HEIC 원본"이라고 적혀 있었다.
- **대안:** `pillow_heif` 설치 / JPEG 촬영 안내.
- **선택:** 안내서 수정. 환경을 바꾸지 않는다.
- **남은 질문:** 사용자의 폰 기종과 기본 저장 형식.

#### D-20261112-13 · 주장 문구 수정과 확장 후보 B [당시]
- **수정:** C1은 noise 입력으로 한정했다. C2의 "localization 유지"는 AU-PRO 0.957 → 0.80–0.86 저하로 바꿨다. C3은 실제 사진 전에는 주장하지 않는다.
- **후보 B (자기 기준 차이 map):** 채택하지 않았다. 첫 9장의 정렬 결과와 모사 결함 사진 유무를 본 뒤 정한다. 쓰게 되면 첫 비교 전에 별도 문서로 고정한다.
- **미검증 위험:** 조명 방향이 다를 때 금속 반사면에서 ORB 정렬이 실패할 가능성. synthetic으로는 시험하지 못한다.

#### 남은 질문 (전체)
1. 실제 첫 9장의 대상: 기판인지 USB-A인지. 정상/결함 상태.
2. 공식 포스터 규격과 템플릿.
3. 지혁의 bank-domain 24+4 결과가 도착하는 시점.
4. 모바일 레이아웃 실기기 확인.


## Stage60. 새 원문의 한계 기록에 따른 CPU 해석 정정과 촬영 준비 (2026-11-12)

D09가headless창크기와실제viewport의차이를미검증으로남긴것을확인해추가측정했다. 앞선CPU보고서는390px screenshot잘림을레이아웃결함으로확정했지만실제innerWidth는492~504px였다. Document/body전체overflow는없었고표에는이미내부scroll이있었다. 실제390 CSS-pixel iframe에서본문/표동작을확인해공개정정문과NEXT_TASK를수정했다. 불필요한필수수정요청을철회하고실기기QA는미검증으로남긴다. 선택근거원문을받아기존CPU판단을교정한사례다.

첫사진전에는기존guide/template을재사용해로컬입력폴더만준비했다. Camera잠금값을기정사실yes로채우지않고unknown으로두며ROI는초기미설정임을표시한다. 실제파일명을적은뒤기존audit에연결한다. 첫9장을development로명시해자기기준차이map의정렬/ROI/방법선택과나중평가세션을분리한다. 실제촬영결과는아직없다. 새source/helper를만드는대신기존도구와입력표를재사용했다.

## Stage61. 검증과 실행의 비중 조정,사진 의존성의 범위 (2026-11-12)

첨부평가의 반복검증비중·실물입력/발표산출물부족 지적을검토했다. 코드원문을보지못했다고명시한자료의상위1%/심사위원99%/수상권밖판정은객관적근거로채택하지않는다. 소프트웨어로물리손실을복구못한다는단정이나시스템으로이겼다는결론도실제대조결과가필요하다.

현재지시서앞부분에완료설계/검토가활성작업처럼남아있어현재상태와남은실행중심으로정리했다. 같은receipt/source의완료검증은cache를재사용하고새입력·변경·실패영향만추가확인한다. 진행중모델대조와포스터/시연준비는실물사진과독립적으로계속한다.

사진첫9장은계획이며프로젝트전체의수량gate로삼지않는다. 실제로자체synthetic한장/기록표한행을기존runner에넣어1attempt/1slot,HTML생성을확인했다. 실물사진이오면같은경로로입출력·품질표시를먼저연결하고조명비교는추가development촬영으로이어간다. 실제검출개선은별도라벨·대조조건이확보된범위에서평가한다.

## Stage62. 첫 실제 어댑터 사진과 품질 규칙의 재질 영향 (2026-11-13)

사진3장이처음도착했다. 각이미지는같은어댑터의다른자세로보이며사용자의질문은촬영대상의적합성과방법확인이었다. 어댑터를개발대상으로채택하고방향/보이는면/크기변화가포함된현재사진과조명만변경한반복세트를구분했다. EXIF가없는clipboard PNG임을기록해ISO/노출값을추측하지않았다.

첫뷰의수동ROI를수치확인전에정해정식phone도구에연결했다. 초기RAM차단후가용RAM의실제증가가관측돼기존guard로재시도했고정상완료했다. 저메모리중간단계의직접ROI통계와정식audit상태는별도로보관했다. 같은조건의막힌작업을무한반복하거나guard를낮추지않았다.

첫실물에서clipped-low16.41%로기존1%규칙이RETAKE를냈다. 검은플라스틱의재질과노출이혼합될수있어이알림을부품결함이나입력전체불가로간주하지않는다. 추가동일구도조명사진과정상참조를확보해품질정책의내용의존성을development에서검토할필요가있다. Test결함성능을보고임계값을조정하지않는다. 현재detector는미연결이다.

다음촬영은대상과카메라를고정하고어댑터를중앙에서더크게담아같은면에서조명만변경하도록안내한다. 첫실물로품질보고서가생성됐다는사실과통제된조명비교/실제탐지검증의미완료범위를함께기록한다.

## Stage63. 촬영 인자 분리와 포스터 제출일 정정 (2026-11-13)

12장 제안은 조명 반복과 모사 이물 시연을 바로 시작할 수 있는 개발 입력으로 채택했다. 초기 PASS/RETAKE와 baseline 미검을 미리 결론으로 두면 실제 품질 규칙의 오류가 가려지므로 조건명과 측정 출력을 분리했다. 첫 실물의 clipped-low 16.41%가 검은 재질과 노출을 함께 포함할 수 있다는 관측도 근거다. 기준 사진의 거부와 판독 어려운 사진의 통과를 함께 보고한다.

기본 물체·카메라·나무 배경을 유지하고 조명만 바꾸는 안을 우선했다. 12장으로 시작 가능하며 후반 3조건의 반복을 늘린 18장을 권장했다. 배경 및 시점 변화는 별도 각 3장 확장이다. 저조도와 역광, 초점 흐림과 손떨림도 각각의 조건으로 기록한다. 반복 사진은 동일 객체 1개의 촬영 반복이다.

모사 이물은 회수 가능한 종이·실을 외부 표면에 두고 위치를 유지한다. 전기적 고장·단선이라는 주장은 추가 검증 범위를 요구하므로 관측한 표면 이물과 판독 가능성을 기록한다. 결과가 기대와 다를 때도 원본·재촬영·정책 버전을 남긴다. 알고리즘을 연결한 뒤 결함 회복 또는 미검 감소를 주장할 수 있는지 별도 평가가 필요하다.

첨부 A0 양식을 실제 PowerPoint로 읽기 전용 렌더해 9예시를 확인하고 3번의 넓은 결과 영역을 추천했다. 사용자 공지의 12월 1일 23:59는 PDF 제출 마감이며 발표일은 미확인이다. 이전 발표일 표현을 정정하고 중앙 PROGRESS와 후속 HANDOFF에 반영했다. 현재 주장은 기존 정량 연구와 실제 촬영 입력 품질·재촬영 시연의 범위에서 구성한다. 최종 포스터와 신규 촬영 결과는 미생성이다.

## Stage64. 그래픽카드 실물 선택과 경계에 가까운 high-clipping 알림 (2026-11-13)

사용자는 세 후보 중 그래픽카드 뒷면으로 진행한다고 명시했다. 작은 소자·납땜·배선과 반사가 있는 표면을 촬영 대상으로 채택하고 기존 어댑터와 UNO 후보도 보존했다. 촬영 안내는 같은 면·위치·배경·카메라로 조명만 바꾸는 9장과 초점 흐림·모사 이물 9장의 18장 계획이다. 기준 조명 세 장부터 분석할 수 있으며 전체 수량을 구현의 선행조건으로 두지 않는다.

새 첫 사진에서 품질 수치를 보기 전에 왼쪽 밀집부 ROI를 정해 기존 aa2 CPU 도구를 한 번 실행했다. High-clipping1.05191%가 기존1%기준을 조금 넘어 RETAKE가 발생했다. Low-clipping은0.0234592%다. 실제 화면의 overlay에는 금속/밝은 부위에 붉은 표시가 보인다. 이 알림을 성공 사례나 판독 불가로 확정하지 않고 기준 조명 사진에서 재질·인쇄·반사 기여를 확인한다. ROI/기준을 결과에 맞춰 재탐색하지 않았다.

소스는 clean aa2, 연구/장치 검출 결과는 미연결 상태로 남긴다. 단일 자기 기준 등록의0정렬오차를 영상간정렬검증으로 사용하지 않는다. 조명·EXIF·전기적 상태가 미확인인 입력을 통제된 기준사진으로 승격하지 않는다. Raw/HTML/RGB overlay는 local-only이며 공개 진행 사실과 private 결정 근거를 분리했다. 제출 마감과 현재 촬영 대상을 예약 지시에도 정정해 오래된 정보가 다음 작업을 유도하는 문제를 줄였다.

## Stage65. 현업 대응 주 비교군과 촬영 예산 대조 (2026-11-13)

사용자는 새6장을예시로제공하고현업라인의촬영과주요비교기준을설계에반영해주형담당에게많은후속작업을맡기길요청했다. 예시에는자세·배율·시야변화가있어조명반복라벨을추측하지않고개발입력으로보관했다. 6번은전체배치구도후보이며일부사진에서벗어난관찰영역은정렬만으로복구됐다고처리할수있는범위가확보되지않았다.

MIRTEC의다단조명·광학설정,Basler의trigger/encoder예시,KohYoung의recipe·falsecall·escape·cycle설명을근거로고정촬영직접검사를주비교군으로채택하는안을제안했다. 무정책임의촬영만을비교상대로두면촬영조건정리의효과를분리하기어렵다. 조건부재촬영과항상두조명촬영은동일최대2장예산과사전지정두번째광원을사용하도록설계했다. 이예산은이번실물prototype제안이며생산라인공통규정으로주장하지않는다.

기존v0.1품질규칙을ablation으로보존하고관찰ROI유효성·정상참조대비변화를다루는단일개선안을주형이판단하도록했다. 개발정상참조로선정근거를기록하고별도고정평가세션에적용한다. 실제라벨없는미검·오탐은NA이고REVIEW/미해결과모든최초cycle을분모에남긴다. SW시간과실제촬영·장치시간을구분한다. C0~C3는제안이며효과수치는아직없다.

실행소유권은주형phone_*·지혁bank-domain·CPU분석통합으로유지한다. 설계보고서완성이나전체사진수령을기존구현·원고작업의선행조건으로두지않는다. 기존정량결과·A0원고·기존HTML시연을병행하고보유UNO표시는USB연결확인후추가시연후보로남겼다. 공개문서만handoff/juhyung@e76d28fe705bf5e9583e89c5de8b44fdf399f604에올렸으며private원문·실물사진은local-only다.

Stage65 전달 보완. 실제 파일을 받지 못한 GPU 담당이 문서만으로 입력 검토를 완료한 것으로 오해하지 않도록, 예시6장과 receipt·README만 담은 비공개 ZIP을 준비했다. 라벨은 unknown으로 유지하고 전체8항목의 내부 SHA/CRC를 검증했다. 공개 Git에는 문서만 있으며 ZIP의 팀원 직접 전송은 아직 수행하지 않았다.


## Stage66. 11월 15일 촬영 스테이션 개발 반환 검토

2026-11-15 CPU 검토 완료 시점의 근거 요약이다. 담당자의 새 private 원문은 수신하지 않았다. 기존 D01~13 원문은 Stage59에서 통합 완료했다. 연결 run은 phone-station-dev-20261115, 반환7b2c894, 실행 source5839caa, CPU 분석8ddde87이다.

### CPU-PHONE-20261115-D01. 비교 분모와 사진 재사용

근거는 cycles.csv96행, plan.json과 summary.csv다. 전체 C2의16건19회와 C3의16건14회를 직접 비교하는 대안은 C3에 NA9건이 있어 채택하지 않았다. 전체16건을 보존하고 공통7건·참조보정 재사용 제외5건을 사후 진단으로 추가했다. 기존 방법 선택 기준은 이 진단으로 변경하지 않았다.

공통7건 C2/C3의 사진 사용은10/14회, 정상라벨 NG0/1건, 모사3건 NG각3건이다. lowlight-1의 대체는 L1참조, lowlight-2의 대체는 L1보정이다. 이를 제외한5건은 사진 사용6/10회다. normal-3와 lowlight-3는 같은 대체파일을 공유한다. 같은 보드·같은 모사물체 위치의 반복이므로 독립 표본 CI를 계산하지 않았다. 논리적 파일 접근 횟수로 실제 취득시간을 추정하지 않는다.

### CPU-PHONE-20261115-D02. 복원 해석과 현업 비교군

Bicubic/SwinIR의16개 최종판정이 일치했다. C0 정상라벨 NG2건과 C1 각0건은 두 복원 조건에 공통인 관측이다. SwinIR 고유 우위를 채택하는 해석은 보류했다. 작업 해상도에서 0.25배 축소 후 x4인 phone_x4_roundtrip을 별도 family로 표기한다.

11월13일 사전 제안의 고정촬영 C0와 항상두조명 C3를 우선 대조군으로 유지하고 C2의 조건부 사진 부담과 C1 Bicubic을 같은 사례에서 본다. 이 프로젝트의 대조군 설계 선택이다. 새 방법의 기준은 새 입력을 보기 전에 고정한다. 기존 포스터·확정 실험은 새 촬영 계획과 병행한다.

### CPU-PHONE-20261115-D03. v0.2 개발 순서와 남은 질문

v0.2는 같은 세션의 v0.1 감사와 사진을 본 뒤 작성됐다. RGB차이, 자세5도/배율.10, 합성검사 뒤 tau2배/최소blob25로 수정한 순서를 RUN_RECORD와 source에서 확인했다. 사후 위치 annotation은 위치 일치 평가용 코드에만 연결되어 있다. 이 세션을 독립 평가로 서술하지 않는다.

품질 v0.2는 PASS15/REVIEW9이며 사람 판독 라벨이 없다. 밝기제곱 정규화 선명도는 L1약3배/L2약3.7배로 증가해 조명 독립성을 확인할 수 없다. 현재 L2는 별도 밝기 게이트가 처리한다. 새 선명도 정책 검색을 추가하지 않고 미해결 질문으로 남겼다. L0/L1 조명별 golden-reference 보정은 유지한다.

### 실제 수행과 후속

JPEG24·metadata17·source6·이전예시6 해시가 일치했다. 사진/GPS/private는 ignored, untracked다. 실행 source의 CPU7개와 consumer 합성9개 테스트가 통과했다. 전체 pytest·GPU 복원·반환 pixel판정맵 재계산은 이번 검토에서 실행하지 않았다. 그림과 비공개 인화판을 열어보고 겹친 범례를 수정했다. Graphify AST 갱신, 공개 문장0flags, diff/stage allowlist를 확인했다. 공개 분석과 주형 handoff는8ddde87이다.

후속은 포스터/PROGRESS에 NA·같은 분모·논리 사용횟수·C1 판정일치를 반영하고 실제 private 새 결정 원문을 run/commit/결정ID와 반환하는 유한 작업이다. 새 평가의 작은 계획에 참조/보정/평가파일 분리, 사례별 고유 대체사진, 조명 위치·AE/AF·HDR 기록, 사람 판독 라벨과 실제 취득시간을 먼저 고정한다. 원본 capture_sheet와 pixel판정맵은 미반환이며 지혁24+4 결과를 기다린다.


## Stage67. 주형 실제 private 11월15일 원문 수신과 최종 위임

사용자가 2026-11-15에 전달한 실제 private 파일15035bytes/SHA256e63678677c8953545f0c743c35ab7de6d7276cd809eda4a6f1771d5ed63061aa를 수신했다. 반환7b2c894에 대응하며 마지막 결정ID는D-20261115-09다. 원본 바이트는 outputs/private-decision-imports/juhyung-20261115-e6367867/RESEARCH_EVOLUTION_LOCAL.md에 보존했다. 기존D-20261112-01~13은 Stage59에 있어 신규9개만 아래에 통합한다. EOL과 제목 깊이만 바꿨다. 원문의 당시/사후 표기를 유지한다.

시연 HTML962865bytes/SHA25637438851f65bfb78fe67edb96532b12a13148186b8f2e84f320c4fdd70ffb065도 수신했다. 자체 포함 이미지46개와 표시용 차이지도가 있으며 외부자원/스크립트는없다. Raw검사배열 수신을 뜻하지않는다. CPU smoke2행통과는 사용자 전달 실행보고이고 원본로그는 아직없다. 다음반환에 실제로그/명령/commit을 연결하도록 지시한다.

사용자는 남은 설계·구현·검토·시연·그림·보고서·A0제작을 Fable5.2에 일괄 위임하고 실제 파일을 보고 판단하겠다고 요청했다. 완료된 실험 재시작 대신 일반 실행 경로와 누락 원근시험, 평가 입력/판독표, 포스터 파일까지 마무리하는 유한 프롬프트를 작성했다. 미수신 실물·라벨을 전체 구현의 선행조건으로 삼지 않는다. 기존 공식 A0원본과 미리보기를 비공개 패킷으로 준비한다. 새private의 ‘공식양식?’ 질문은 이번전달로해소한다. 사람 판독/새평가/UNO실물 여부는 실제 확보상태로 기록한다.

아래는 주형 신규 결정 원문의 정규화 사본이다.

### D-20261115-01 · 세션 1개를 development로만 쓰기 [당시]
- **문제:** 입력은 24장짜리 세션 1개다. 방법을 정하기 전에 v0.1 audit 수치 전체와 축소 사진 9장을 이미 봤다.
- **대안:**
  - (a) 세션 안에서 일부를 "평가"라고 부른다.
  - (b) 전부 development라고 쓰고, 세션 안 분할은 calibration에 쓰지 않은 반복(held-out)이라고만 부른다.
- **선택:** (b). 본 것을 `DESIGN_DECISION_PHONE_V0.2.md` §0에 공개했다. 고정 평가는 새 촬영 세션이 필요하다.
- **관련:** commit `e00eca6`, run `phone-station-dev-20261115`.

### D-20261115-02 · 관찰 ROI와 recipe [당시]
- **근거:** v0.1 audit에서 L0의 포화 4.4–8.9 %가 책상 배경에서 났다. 기판은 화면 가로의 절반 정도다.
- **선택:** ROI = anchor의 PCB 안쪽(x 0.12–0.61, y 0.31–0.70). anchor 사진만 보고 정했다.
- **자세 허용 범위 5°, 0.10:** 기울임 세트가 약 14°, 다른 세트가 3–8 %인 것을 본 뒤 정했다. 사후에 맞춘 값이라는 점을 문서에 적었다.

### D-20261115-03 · 품질 정책 단일 개선안 `ref_roi` [당시]
- **대안:** A. v0.1에 ROI만 적용 / B. 정상 참조 대비 변화 / C. 학습 기반 품질 예측.
- **선택:** B. 검은 재질, 원래 밝은 부위, 새 반사, 관찰 부위 소실을 한 체계로 나눈다. 모델을 추가하지 않는다. C는 라벨이 없어 기각했다.
- **실행 후 관측:** 같은 ROI에서 v0.1은 PASS 3 / REVIEW 6 / RETAKE 15, v0.2는 PASS 15 / REVIEW 9 / RETAKE 0이다.
  - anchor ROI에 원래 포화가 1.81 % 있다(납땜, 흰 인쇄). v0.1은 이것 때문에 L0를 전부 RETAKE로 냈다.
- **발견한 약점:** 밝기 제곱으로 나눈 선명도 비율이 L1 2.9–3.1, L2 3.6–3.8로 나왔다. 어두운 사진에서 과보정된다. 흐림을 낮은 쪽에서만 잡는 용도로는 동작했다(흐림 0.19). 조명 간 비교에는 쓸 수 없다.
- **미해결:** 사람의 판독 기록이 없어 어느 정책이 사람 판단에 가까운지 모른다.

### D-20261115-04 · golden-reference 판정 규칙의 사전 수정 [당시]
- **처음 고정한 규칙 (`e00eca6`):** τ = q0.999, 판정 = 점수 > 2 × (calibration 1장의 최대 덩어리 넓이).
- **합성 시험에서 본 문제:** calibration 점수 53, 정상 반복 10장의 점수 89–174, 6/10이 NG. 사진 1장의 극값 통계라 흔들린다.
- **대안 비교 (합성 입력만):** τ 배수 1.0 / 1.5 / 2.0 / 3.0에서 정상 10장의 최대 점수는 174 / 13 / 0 / 0, 반지름 3 px 이물 점수는 322 / 231 / 145 / 115였다.
- **선택:** τ = 2 × q0.999, 최소 넓이 25 px(`5839caa`). 실제 사진에 검사를 돌리기 전이다.
- **실행 후 관측:** 실제 사진에서 held-out 정상은 점수 0, 이물은 L0 165, L1 1500–1515. 정상 기판 오검 2건은 점수 28, 30으로 한계 25 바로 위다.
- **사후 해석:** 최소 넓이 25 px는 실제 사진에서 여유가 작다. 고치려면 새 버전과 새 세션이 필요하다.

### D-20261115-05 · 채널 선택과 본 것의 공개 [당시]
- RGB 최댓값을 쓰는 규칙은 일반 규칙이지만, 이물이 분홍색인 것을 축소 사진에서 본 뒤 고정했다. 문서 §0과 §4에 적었다.

### D-20261115-06 · C1의 정의 [당시]
- **문제:** 실물 사진에는 "저해상도 입력"이 따로 없다.
- **대안:**
  - (a) 계산용 영상을 ×0.25로 줄였다가 ×4로 되돌린다(Bicubic / SwinIR).
  - (b) 원본 해상도에서 SwinIR을 적용한 뒤 줄인다.
  - (c) pending으로 둔다.
- **선택:** (a). 기존 benchmark의 왕복과 같은 형태라 Bicubic 대조를 둘 수 있다. 참조와 calibration도 같은 처리를 거친다. family는 `phone_x4_roundtrip`으로 분리했다.
- **관측:** 이물 3/3 NG(점수 117–130), 정상 오검 0/13. 왕복이 차이 map을 평활해 오검과 이물 점수가 함께 줄었다. "복원이 검사를 개선했다"로 쓰지 않는다.

### D-20261115-07 · 세 장의 점수가 똑같이 나온 것 [당시]
- **관측:** F0 3장의 점수(165)와 중심 좌표가 소수점까지 같았다.
- **확인:** 따로 다시 계산했다. 세 사진은 다르다(화소 평균 차이 1.7–2.3, τ 초과 화소 214 / 215 / 214). 가장 큰 덩어리의 모양만 같다. 버그가 아니라고 판단했다.

### D-20261115-08 · 예시 6장 [당시]
- 기준 후보 6번에 나머지 5장을 정렬했더니 모두 임계값 미달이었다. RETAKE로 두고 "보정 완료"로 처리하지 않았다.
- 더 강한 정렬 방법은 시험하지 않았다.
- 기록표를 `supplied/` 폴더에 추가했다. 사진 바이트는 그대로다.

### D-20261115-09 · UNO 시연 [당시]
- 문서 초안만 남겼다. 연결 가능 여부가 미확인이고 기본 실험과 포스터가 우선이다.


### CPU 최종 전달 기록 (원문 통합 이후 추가)

공개 프롬프트·NEXT_TASK·PROGRESS·익명수신receipt4파일을492aa6a57d14816f33446329f1929bb876af2bfb로 분석브랜치와 handoff/juhyung에push해원격일치를확인했다. 공식A0원본SHA일치,3번미리보기·private원문·시연HTML·프롬프트·README·receipt의7항목ZIP은2995950bytes/SHA256e2b9ca0fb9dd0d399e4e48ba0e239a23e5f7b4d02e5a2c3fc10aefc81e234e87이다. ZIP CRC와내부파일SHA를검증했다. ReasonNetwork에서일치하는liveClaude세션이없어사용자가넘길수있는비공개패킷으로제공했다. 실제Fable실행결과수신은아직없다.

최종목표는정지촬영PCB시제품의일반입력경로·검사/품질/조건부재촬영/이력·시연·실제그림·공식A0 PPTX/PDF·결과보고서·자체검토까지완성하는것이다. 코드와문서를준비한것을실제물리실험완료로집계하지않는다. CPU smoke는2rows통과라는담당자전달보고이며다음반환에실제로그를연결하도록했다. 이번에는문서/수신작업으로기존모델과테스트를반복하지않았다. 공개문서3개문장검사0flags/low,diff/stagedallowlist통과. private와사진포함자료는Git에서제외했다.


## Stage68. 최종 phone 반환59bc262의 CPU 검토

2026-11-17 작성. 실제 새private D-20261115-10..17 원문은 미수신이며 이 절은 CPU가 검증한 근거와 선택만 기록한다. 마지막 실제 수신 원문은Stage67의D-20261115-09다.

### CPU-PHONE-FINAL-20261117-D01.7조건 consumer와 기존 결과 재사용

반환22개metadata bytes/SHA와receipt를검증했다. 실행source7b868a3/포스터59db971을연결했다. 코드4와문서3해시는원본EOL에맞는Gitblob/checkout표현에서일치했다. 기존consumer가6조건계약이라알려진C2v0.3을포함한7조건을추가했다. 임의새조건은거부하고기존6조건호출/검사를유지했다. 실제112cell/운영16행과21개cohort요약을재집계했다. 기존96cell의상태·품질·점수·한계값·사진수,24사진해시목록·참조·보정이이전cache와같아모델추론을반복하지않았다. Consumer11/source신규4CPUtests통과.

### CPU-PHONE-FINAL-20261117-D02.새 정책과 비교 범위

v0.3은같은조명참조의Tenengrad와신규clipping을쓴다. 근거는개발사진에디지털흐림을준경우이며실제L1초점흐림/사람판독은없다. 현재24장15PASS/9REVIEW,16cycle6OK/4NG/6REVIEW는v0.2와같다.48품질행은24사진×기대조명2개이므로사진48장으로부르지않는다. 기존7/5사후묶음과공유대체사진을유지한다.

원근32행은10ACCEPT/12REVIEW/10RETAKE다. 중심보정10~30도는REVIEW지만화면이동10~30도는RETAKE다. 최종요약의단일각도범위를조건별로고치도록했다.147/423초는코드/조건수/전원이함께달라전원원인만추정하지않는다.633초는pytest와겹쳤다. 새시간실험을추가하지않고문구를수정한다.

### CPU-PHONE-FINAL-20261117-D03.포스터 근거와 반환 범위

동결57235a2에서Hazelnut70장중저하30,14suppression/16geometrycandidate,40개나머지와Screw/PCB인용값을확인했다. pooled AU-PRO를영상별산술평균으로쓰지않도록고친다. historical_recovery seed칸은비어있어공통seed11로표기할근거가없다. PCBnative fullcohort는seed11이다. Team No_??·저자/소속/제목이미확정이고HTML운영banner는v0.2만가리킨다는자체검토가있어마무리지시를작성했다.

포스터PPTX/PDF·그림7·최신HTML·capture_sheet·새private원문은아직없다. 비공개ZIP첨부를사용자에게요청했고직접연결된ReasonNetwork상대세션도없었다. 보고서의완료주장과실제수신/검증을구분했다. 새시각파일이오면배치/가독성/원자료를확인하고새private원문은run/commit/결정ID로한번만통합한다.

### 수행·검증·전달

CPUconsumer11tests0.84초,source새4tests105.50초통과. 받은696/4skip전체로그는6748c95,49관련/smoke2행로그는7b868a3다. 마무리와기록을Opus5.5로전환했다는RUN_RECORD를보존한다. 실제GPU/전체pytest는이번CPU에서반복하지않았다. 새숫자그림직접확인,문장3파일0flags,diff14파일allowlist,AST3488nodes/6446edges확인. 공개분석과주형handoff는a350b0707d4914c69a71da32e42ddf8e41bd7046다. 원본79a1c0f/사용자변경·privateignoreduntracked를보존한다. 다음은시각/private최종파일과새평가/판독/지혁24+4실제반환이다.


## Stage69. 최종 private 수신·가이드 대조·bank 담당 이관

2026-11-17 사용자제공 final-delivery-20261116-private.zip을수신했다. 16048325bytes/SHAe64ac163ce49e11b9834160b6b6e3ab18ee3eda17e1a5f30ce87c3cda310c4fc. ZIP46파일의CRC와45payload를receipt해시와대조했다. index의template_copy.pptx1개는빠졌고기존공식A0와동일SHA라supplemental에사본을보완했다. 원본ZIP/receipt는보존한다. 기존22metadata는a350검토본과바이트동일해재계산하지않았다. private원문19661bytes/SHAbce461ae591cf367887aa946b0a189681f151149aa29ffb16ecb9f20193712f3의D-20261115-10..17 신규8개만통합한다. 원본바이트는outputs/private-decision-imports/juhyung-20261117-bce461ae에보존했다. EOL·제목깊이만정규화했다.

사용자는지혁의bank-domain잔여작업을주형에게넘겨도된다고지시하고,실물시연보다눈에보이는사진결과가최종목표라고강조했다. 붙여넣은EEE4185가이드는검토자료로읽고새부품구매·장비구현·새고성능목표의자동명령으로취급하지않는다. 실제연구/시제품/사진산출물과제안단계알고리즘·하드웨어를대조한다.

다음은새로수신한주형원문8개다.

### D-20261115-10 · 선명도 과보정: 유지할지 고칠지 [당시]
- **문제:** v0.2의 밝기 제곱 정규화가 어두운 사진에서 과보정된다(L1 2.9–3.1배, L2 3.6–3.8배). CPU 검토도 조명 독립성 주장을 보류하라고 했다.
- **확인 (development 사진, 디지털 흐림 σ1.0):** v0.2 비율이 L0 0.243, L1 0.745. 같은 조명 참조 대비 원래 Tenengrad 비율은 L1 0.258. σ1.5에서는 0.107 / 0.315 / 0.110. σ2.0 이상은 정렬이 실패했다.
- **대안:**
  - A. v0.2를 유지하고 사용 범위만 설명한다.
  - B. 밝기 지수를 다시 맞춘다.
  - C. 같은 조명의 참조와 비교한다.
- **선택:** C (정책 v0.3). 운영 경로의 대체 사진이 L1이라 A는 실제 구멍이 된다. B는 L1과 L2에서 필요한 지수가 달라(약 0.5, 1.2) 맞출 수 없다.
- **고정:** `a031195`에서 문서를 먼저 commit하고 그 뒤에 구현했다.
- **실행 후 관측:** development 24장에서 v0.3 판정은 v0.2와 같다. 저조도 첫 사진은 "어두움"과 "선명도 낮음"이 함께 표시된다(비율 0.14–0.15).
- **남은 것:** L1에서 실제로 흐리게 찍은 사진이 없다. 새 평가 세션의 F 묶음은 첫 사진만 흐리게 찍는다.

### D-20261115-11 · 원근 전용 임계값을 넣지 않음 [당시]
- **근거 (합성):** 중심을 유지한 기울기 5°는 배율 편차 0.049로 수용, 10°는 0.112로 자세 허용 범위(0.10)를 넘어 REVIEW, 30°까지 정렬 성공(inlier 비율 0.46), 40° 이상 정렬 실패.
- **대안:** `perspective_term`에 새 임계값을 둔다 / 기존 규칙에 맡긴다.
- **선택:** 기존 규칙. 새 값을 넣을 근거 자료가 합성뿐이다. `perspective_term`은 기록만 한다(실제 기울임 사진 0.129).

### D-20261115-12 · 실행 계획을 기록표에서 만들기 [당시]
- **문제:** 일반 사용자가 `plan.json`을 손으로 쓰기 어렵다. 새 평가 세션은 참조·보정·평가 사진을 따로 찍어야 한다.
- **선택:** 기록표에 `station_role`, `cycle_id`, `light` 열을 두고 계획을 자동으로 만든다. 한 사진을 두 역할에 쓰면 거부한다.
- **보존:** 기존 `--plan` 경로는 그대로다. development 세션은 기존 plan을 쓴다(참조·보정 재사용이 들어 있고 표시돼 있다).

### D-20261115-13 · 새 평가 세션의 크기 [당시]
- **대안:** 지난 세션과 같은 24장 / 32장(정상 4, 이물 3위치 × 2, 저조도 2, 흐림 2, 모두 대체 사진 포함) / 더 큰 세트.
- **선택:** 32장. 한 번에 찍을 수 있는 양이고(지난 세션 24장이 약 10분), 모든 cycle에 대체 사진이 있어 C3의 NA가 없어진다. 이물 위치를 3곳으로 늘린다.
- **조명 위치를 테이프로 고정:** 지난 세션의 L0 반복 간 차이(평균 12.3)가 L1(2.0)보다 컸기 때문이다.

### D-20261115-14 · 시간 기록 [당시]
- **관측:** 같은 실행이 전원 연결 147 s, 배터리 423 s였다. 테스트와 동시에 돌린 실행은 633 s였다.
- **수정:** 보고서 그림 시간을 검사 시간에서 분리했다(`7b868a3`).
- **결정:** 세 값을 조건과 함께 적고 처리량 계산에는 쓰지 않는다.

### D-20261115-15 · 포스터 구성과 미확정 정보 [당시]
- 공식 양식 3번 구성을 썼다. 원본은 그대로 두고 사본을 PowerPoint 자동화로 편집했다. python-pptx가 없어 새로 설치하지 않았다.
- 팀 번호, 저자, 소속, 제목은 확인된 자료가 없다. `Team No_??`와 "[확인 필요]"로 자리만 잡았다.
- C3와 C0를 우선 대조군으로 두라는 지시에 따라 비교 그림의 순서를 C0, C3, C2, C1로 했다.

### D-20261115-16 · UNO [당시]
- 연결된 UNO가 없다(COM3, COM4는 Bluetooth). pyserial도 없다.
- fake serial 경로, 1바이트 상태 프로토콜, 스케치, 재생 CLI까지 만들었다. 스케치는 컴파일하지 않았다.

### D-20261115-17 · 결과 화면 문구 미수정 [당시]
- 최종 결과 화면의 첫 줄이 결정 문서로 v0.2만 가리킨다. 고치려면 다시 실행해야 해서 그대로 두고 FINAL_REVIEW에 적었다. manifest에는 v0.3 문서가 기록돼 있다.


### CPU 검토와 담당 이관 완료 (2026-11-17)

- 사용자의 우선순위는 눈에 보이는 사진 결과다. 첨부 가이드의 하드웨어·ANN·자동 보정 확장 제안 전체를 이번 필수 구현으로 확대하지 않고, 같은 결함 crop의 원본/열화/Bicubic/SwinIR과 대응 GT/지도, 동일 query의 bank 비교를 먼저 반환하도록 정했다.
- 실제 PDF/PPTX와 E1/E2,기존case00을 열어 확인했다. 현재 그림은 모사 표면 이물/저조도 대체입력/검사 지도를 보여준다. 복원RGB의 미세결함 확대비교와 실제 PatchCore24+4 반환은 남아 있다. 정상13은OK6/NG1/REVIEW6이므로1/13만으로 현장오검률을 결론내리지 않는다.
- D17의‘문구를 고치려면 다시 실행’ 설명은 수정했다. 저장결과 render 또는 사본문구 수정으로HTMLbanner를 바꿀 수 있다. D10의 실제 L1흐림 부재는 새32장계획의 흐림2cycle중한대체L1도흐리게촬영하는보강안으로연결한다. 실제새촬영과사람판독은미실행이다.
- 지혁producer의ac93134객체가 로컬없어그commit을무조건checkout하도록하지않았다. 기존공개패치2개의원본SHA를보존해주형handoff/code로옮겼다. scripts/analyze_bank_domain_study.py가CPUconsumer와producer에함께있어별도실행checkout과호출자보존을지시했다. 기존vendor/checkpoint/부분실행재사용과원래RAMguard를유지한다.
- 주형전달4c333f295e6ea8daf7c469a8a82630d7c1b774e2,지혁담당변경c69f1c19685b4296adddb33556f76627d8551188을공개하고원격일치를확인했다. 실제상대Claude연결세션은없어착수확인은남아있다. 모델실행을대체하거나새GPU작업을시작하지않았다.
- ZIP내부누락template_copy는이전수신동일SHA양식을supplemental에보충했다. 원본archive와receipt는바꾸지않았다. 새private8개통합과사본/IMPORT_RECEIPT를확인했다. 비공개원문/사진은공개하지않았다.

## Stage 70 · 최종 목표 통합 위임과 결함 동반 열화 촬영안 (2026-11-17)

### 사용자 요청과 근거

사용자는‘실환경열화에서도작은결함을보존하며검사하고사진/수치로보여주는방법’이라는최종목적을확인했다. 전체설계·남은구현·실험·사진·검토·수정·보고서반환을주형에게위임할통합프롬프트와필요사진촬영법을요청했다. PROGRESS,초기연구노트의평균개선/개별손해·고정fusion실패·gap부호반례,Stage69와실제새32장계획을대조했다.

### 선택과 촬영안

기존32장에는이물존재상태의저조도/흐림사진이없다. 정상기판의입력품질평가만으로이물보존을주장할수없으므로보조18장을제안했다. 작은모사이물1종의크기를유지하고3표면위치각각에서선명L0/L1,저조도L0/선명대체L1,흐림L0/선명대체L1을촬영한다. 기본32장v2는정상blur-2의L1도흐리게한다. 계획50행=관측0이며촬영전에주형이고정한다. 사진수는추가구매없는기존폰/조명/기판범위의제안이다. 같은물체반복과기본14cycle/보조9cycle을분리하고human판독과실취득시간을별도받는다.

### 설계 연결과 반환

통합프롬프트는phone GR검사와SR/PatchCorebenchmark를연결할때대상·모델·해상도·GT의차이를유지하고정렬용축소와검사용원해상도를점검하도록했다. SwinIRx4의실제저조도/흐림복원을가정하지않고범위를평가한다. 고정된저장사례RGB/GT/maps를먼저반환하고실제PatchCore24+4,필요구현과정상진입점회귀검사,사진·보고서·A0,자체/별도검토와수정까지이어간다.

통합지시는8aaee07e4b4f299fd8fbb325661926beec7d4fca로공개하고원격일치를확인했다. 새실험은실행하지않았다. 중앙private전체는비공개ZIP스냅샷에만넣고공개문서에는복사하지않는다. 마지막수신한주형원문결정ID는D-20261115-17이다. 새촬영/사람판독/팀정보/실제실행은해당증거가도착한뒤확인한다.

### 이번 비공개 패킷의 최종 검증

29entries/22641579bytes, SHA256 6c6d0b14bc6248e8160a00f112be78a3734b72f6e4d79ff05f86e6186d9bc0cb의비공개ZIP을만들고CRC/내부payload SHA를검증했다. records는포장직전스냅샷이고이검증문구는외부기록이다. 계획50사진/실제0,기본14cycle/보조9cycle·참조2/보정2를검사했다. 원본HEAD79a1c0f/사용자변경과private ignored/untracked를확인했다. 5시간자동화는일정/상태/현재채팅을유지하고8aaee07/Stage70/50장제안을반영했다. 사용자가직접전달할ZIP과메시지를준비했으며상대에게직접메시지를보내지않았다.

## Stage 71 · 지혁 확장 반환 검토와 주형 작업 갱신 (2026-11-17)

### CPU에서 확인한 범위와 선택

확장ZIP2개/총26metadata파일의CRC,receipt24payload bytes/SHA와분석표hash를검증했다. 수신summary4행·개별540행·paired378행의identity/화질/산술을대조하고제공된normalized_score와label로4조건image AUROC를독립재계산해맞췄다. raw maps/GT/bank배열은없어pooled AU-PRO와pixel AUROC는저장값내부대조까지다. 원래baseline query/hash의실물manifest는미수신이다.

Screw의Bicubic bank고정에서SwinIR-query는PSNR+2.437522dB/SSIM+0.016426인데pooled AU-PRO−0.037334/image AUROC−0.208444다. 고정SwinIR query의clean→Bicubic bank에서는pooled+0.008372지만per-image평균−0.010678,감소64/119다. 두대조를혼용하지않고표/그림에반영한다. RGB의결함억제기전은실제사진을확인한후판단한다.

기존24는첨부PROGRESS/JH노트의수행완료보고다. 기존6반환ZIP·전체metadata와미푸시8af5aa소스는이번첨부/다운로드폴더/fetch된c69f1c1remote에없다. 주형에게전체24+4새실행을유지하면중복될수있어현재master프롬프트·bank상세계약·NEXT_TASK를완료자료회수/통합/저장사진반환으로갱신했다. 수신누락을실행실패로판정하지않는다. 새실행은실제빈조건확인후판단한다.

첨부patch4aeeade3...5b03a6는신규4파일(실행runner/extension module/resume/실행테스트)이며8aaee07에서git apply --check통과,코드적용은없다. 실행runner SHA는Screw와맞고extension module은둘다맞으며resume SHA는Hazelnut과맞는다. Hazelnut최초runner ebc196fe...는현재224dbed7...와달라당시사본과실패status/transcript를받아보존한다. CPU분석기/분석측5테스트·base 수정전체는패치에없다. fake10통과는보고이며CPU는새GPU/배열실행이나이테스트의재실행을하지않았다.

후속사진은수신후선정6개category별최대감소/최대증가/0근접case를지혁의저장예측에서내보내도록정했다. 같은query의bank효과와같은bank의query복원을구분한다. 선정은사후설명용이고새평가표본/정책선정이아니다. 원래전체평가수치를유지한다.

공개handoff/juhyung과exp/phone-final-return-review는90d2bf34d16d8cdad5df96c20d8d65d9e7f5bf3d로원격일치를확인했다. 36개공개파일allowlist/receipt바이트/index/SHA/링크/diff/문장Unicode검사통과. 중앙private에는아래JH01~10원문을처음통합하고raw bytecopy/IMPORT_RECEIPT를보존한다. 주형의마지막실제수신D-20261115-17은별도다. 기존50장촬영전제안·사람판독·시간·팀정보는그대로남고기존사진/그림/보고서작업을이어간다.

### 수신한 지혁 private 원문 JH-20261117-01~10

### Jihyuk private research decisions and execution notes

#### JH-20261117-01 — Resume from the locally available handoff, not an absent ZIP

**Date / source / run:** 2026-11-17; execution source HEAD `ac931349ba0f3db795a5400534b3a79d2bdc4f44`, dirty worktree; completed run `jihyuk-bankdomain-hazelnut-seed11-20261117-1432`.

**Problem and evidence.** The request named `JIHYUK_OFFLINE_HANDOFF_20261111-v2.zip`, but it was absent from Downloads, Desktop, workspace and the attachment directory already checked. Its embedded `HANDOFF.json` and `SHA256SUMS.txt` therefore could not be inspected or authenticated. A read-only host-network `git ls-remote` and fetch succeeded after the default sandbox path's earlier 443 denial. The delivery branch contained minimum commit `61c2170dec726e76be4a4dbd488a84f893a6db16`, START_HERE, receiver, receipt, workflow, and patches. I used this available source contract without claiming the missing ZIP digest had been checked. `handoff/INPUT_FILES.json`'s listed delivery-file hashes were checked. The later handoff text assigned the queue to Juhyung; the current direct request explicitly continued Jihyuk's work. No local active worker or matching completed result existed, so I followed the current request, preserved the other branch, and used a unique run ID.

**Input decision.** Reused the provided local team repack rather than downloading another copy. Its 813,040,630 bytes and SHA-256 `635ced502743817e8ef8fe704b2bbd1634fe87f15edaef5e7d85e6d3b86a28b9` matched the private receipt. The receiver installed 1,177 inventory-verified files in a new ignored data directory. The repack receipt explicitly leaves the original publisher archive SHA unknown; no inference was added.

**Protocol decision.** Retained exactly two normal banks (`clean`, `swinir_restored`) and two queries (`bicubic_x4`, `swinir_x4`). The other wording that implied clean/restored query inputs was treated as superseded by the explicit source/CPU-consumer contract. Fit/calibration used only normal train images; fixed q=0.99 thresholds came only from normal calibration. Test GT was read only after bank prediction NPZs were written. All patch rows and the existing `IdentitySampler`, FAISS CPU index, image preprocessing, geometry and metrics remained unchanged. No FAISS threading/batching, bank-capacity, category, threshold or performance search was introduced.

**Code decision.** The original `bank-domain-study-ac93134.patch` remains a storage/receipt artifact and was not reapplied. `jihyuk-fixture-portability.patch` had passed `git apply --check` before application; it isolates tiny synthetic checkpoints, RAM probing, and subprocess reporting in the fake test. The raw-array executor was renamed to `scripts/analyze_bank_domain_raw_runs.py`; CPU consumer remains `scripts/analyze_bank_domain_study.py` in the source-only handoff worktree. Added source digests, five-file export manifest, ROI/background gap, and GT-after-prediction ordering. The later reverse-check of the original fixture patch no longer matched because subsequent test assertions and synthetic-fixture edits overlap its context hunk; patch lines are present, and final focused tests passed. Do not report reverse-check as passing after these edits.

**Test evidence and correction.** One initial pytest attempt placed its log inside `--basetemp`; on Windows, pytest's own temp cleanup could not delete that open log, yielding 4 teardown errors after 8 passing tests. Moved the log outside the fresh OS temp folder and reran. That revealed one stale test expectation (`PARTIAL`) while the runner correctly preserved an inference failure as `FAILED`; updated the assertion to `FAILED`. Final focused run: **12 passed, exit 0**, fresh OS temp basetemp. The actual run subsequently passed `verify_complete_run` and `verify_result_contract`; the separate CPU consumer accepted it as one `model_predictions` result with exit 0.

**Run observation.** Hazelnut seed 11 completed 313 fit / 78 calibration / 110 test rows with 245,392 vectors in each bank. Stored raw arrays have finite 78x2x224x224 calibration maps and 110x2x224x224 test maps. Query input/Bicubic/SwinIR RGB digest lists are identical across banks; bank feature hashes differ. There are 440 stored cell/sample rows. Normal per-image AU-PRO and ROI gap remain NA; anomaly ROI gaps are finite. Both bank artifacts preceded saved GT-mask file timestamps. CPU consumer reports pooled-AU-PRO deltas: bank +0.008115 at Bicubic query and +0.006754 at SwinIR query; query +0.023733 at clean bank and +0.022372 at restored bank. The per-image mean bank delta at SwinIR query is negative (-0.000367) while pooled delta is positive. This discordance is retained; no mechanism claim follows from one seed. The raw data and raw NPZ files were not included in public return.

**Resources and limits.** Fixed fit/disk guard passed. Before-fit available RAM snapshot was 9,015,386,112 bytes; after-run snapshot 8,741,904,384 bytes; free disk was 17,945,870,336 bytes before and 17,811,337,216 after. These are snapshots, not RAM peaks. Runner-measured CUDA allocated peak was 1,021,221,376 bytes for both banks. Fit and query inference seconds are in status; end-to-end wall time was about 23m10s. No OOM occurred.

**Public/private boundary.** Public result metadata was prepared with `scripts/prepare_team_return.py` under `handoff/returns/jihyuk/jihyuk-bankdomain-hazelnut-seed11-20261117-1432/`; receipt says `NOT_REVIEWED`. Per-image/effect CSV source paths were replaced with the actual run ID before return. `raw_clean.npz` SHA-256 is `1ad95d2dda97951ce5a6d8e959837162e2a9b4177a610e5631fcdb1c756dd12e`; `raw_swinir_restored.npz` SHA-256 is `8d89a661d3c20d2d1cae87c1bda93aa60795d2b6d578e860d20036b343195330`. These arrays and the saved GT masks remain local. `git check-ignore` confirms `outputs/private-decisions/` is ignored; `git ls-files` confirms this note is untracked. No reset, clean, force push, commit or push has been performed.

**Next.** Run Screw seed 11 as the next unique category/seed; only then continue remaining seeds, checking current local workers and existing artifacts before every launch. Keep incomplete/failed runs. The four Bicubic-bank extension cells remain later and separate. Before publishing any return, fetch/read the current `handoff/jihyuk` tip, inspect staged files for absolute paths/private material, and use a normal non-force push only if still fast-forward.

#### JH-20261117-02 — Return commit and authentication blocker

After JH-20261117-01, the canonical handoff return plus public `PROGRESS.md` entry was committed locally on the source-only worktree as `baa51cc1ebec9219c49f2dde8a1d034175b0249b`, using the existing project commit identity `Codex <codex@localhost>` only for that command. Before publishing, `ls-remote` confirmed `handoff/jihyuk` was still `c69f1c19685b4296adddb33556f76627d8551188`; the new commit is its direct child. The normal push waited on Git Credential Manager and did not update the remote. A single retry with `GCM_INTERACTIVE=never` and `GIT_TERMINAL_PROMPT=0` returned exit 128: `could not read Username for 'https://github.com': terminal prompts disabled`. The remote still points at c69f1c1. No credential was entered or exposed; do not force push. A metadata-only fallback ZIP, 14 files, no raw arrays/GT/weights, was created at `outputs/private-returns/JIHYUK_BANKDOMAIN_RETURN_HAZELNUT_SEED11_20261117.zip`; SHA-256 `498bb4c6fbf71fac1c19dca503fa25a435faaed292e95c8ae71370d5bfcaadbe`, verified against its adjacent `.sha256` file.

The first GPU return is complete locally and its exact files/receipt are reviewable. Remaining dependent action for publication is interactive GitHub authentication by the user; local execution continues with the next unique category/seed independently.


#### JH-20261117-03 — Screw seed-11 completion

**Run/source:** `jihyuk-bankdomain-screw-seed11-20261117-1510`; source HEAD `ac931349ba0f3db795a5400534b3a79d2bdc4f44`, branch `codex/bank-domain-study`, dirty. The unique Screw seed-11 path did not exist and no Python worker was active before launch. Command exit 0; status `COMPLETE`; 640 rows, 256 fit / 64 normal calibration / 160 test, 119 anomalies, 200,704 vectors per bank. Exact summary and contract exports are in the local run. `verify_complete_run`, `verify_result_contract`, finite raw shape checks, equal query hash lists and the CPU stored-result analyzer all passed. CPU analyzer accepted `model_predictions`; no detector reevaluation occurred.

**Observed pooled contrasts:** cells clean/Bicubic `0.7990657469`, clean/SwinIR `0.8531818394`, restored/Bicubic `0.8587810123`, restored/SwinIR `0.9384327317`. Restored-bank deltas at fixed query were `+0.0597152654` and `+0.0852508923`; mean paired per-image deltas were `+0.0801270449` and `+0.0763874149`. Query deltas at fixed clean/restored bank were `+0.0541160924` and `+0.0796517193`; per-image means `+0.0772741454` and `+0.0735345154`. Per-image rows are supplementary and do not replace the pooled dataset metric. The query was byte-identical across bank domains. As with Hazelnut seed 11, this only supports a paired association, not a causal feature-reference mechanism. One seed is not a cross-seed estimate.

**Resources:** 8,704,872,448 available-RAM bytes and 17,809,051,648 free-disk bytes before fit; after snapshots 8,655,253,504 RAM and 17,647,198,208 disk. RAM values are snapshots, not peak. CUDA allocation peak recorded in-process was 1,021,221,376 bytes for each bank. The measured per-bank fit/query timing is in status; wall time was about 21m21s. No OOM or guard adjustment.

**Return:** public text return prepared at `handoff/returns/jihyuk/jihyuk-bankdomain-screw-seed11-20261117-1510/`, receipt is honest that peer review is pending and raw array contents are not included. Fallback metadata ZIP hash: `773378ded2dbe0d1f4da73988c43b40b372f8b66548a444d176f49daa2b538f9`. Private raw NPZ SHA-256 values: `raw_clean.npz` `d984ba037fe1a240c92aa77bf7d614eb5ec218371ab30d0b4130b5ebc5848d17`; `raw_swinir_restored.npz` `29fbd7f1116dc30b5f109c5fd7ae531cb89f8b509ed8ce0db4eebe227e37919f`. All private files remain local.

#### JH-20261117-04 — Hazelnut seed-23 four-cell completion

**Run/source:** `jihyuk-bankdomain-hazelnut-seed23-20261117-1540`; execution source HEAD `ac931349ba0f3db795a5400534b3a79d2bdc4f44`, dirty branch `codex/bank-domain-study`; command exit 0. No repeat was launched: this run completed its unique seed-23 output. Source hash, code digests, split/query manifests, checkpoint IDs and submodule revisions are in its provenance.

**Verification:** `COMPLETE`, 440 prediction rows, four frozen cells; 313 normal fit / 78 normal calibration / 110 test (70 anomaly). `verify_complete_run` checked stored row order and all payload hashes; the five-file export validator passed. CPU consumer read the saved CSV/JSON as `model_predictions` and exited 0 without recomputing detector metrics. Prediction NPZ score arrays are finite (`[78,2]`, `[110,2]`); maps are finite (`[78,2,224,224]`, `[110,2,224,224]`). The clean/restored bank files have distinct digests; calibration/test sample order and query-input/Bicubic/SwinIR RGB digest lists match exactly across both banks. Test prediction arrays were saved before test GT was read. Normal per-image AU-PRO and ROI/background gap stay NA.

**Observed primary metric:** pooled dataset AU-PRO@0.3: clean bank/Bicubic `0.8176424797`; clean/SwinIR `0.8422990406`; restored bank/Bicubic `0.8258870795`; restored/SwinIR `0.8495953793`. At fixed queries, restored-minus-clean pooled deltas were `+0.0082445998` (Bicubic) and `+0.0072963387` (SwinIR). Mean paired per-image deltas were `-0.0002580576` and `-0.0003541804`; 34/70 and 35/70 anomalies regressed respectively. Query pooled deltas at fixed clean/restored bank were `+0.0246565609` and `+0.0237082998`; per-image means `+0.0118495983` and `+0.0117534755`. Per-image uncertainty is supplementary, not a pooled-AU-PRO CI. One seed is not independent cross-seed evidence. The pooled/per-image direction difference is retained and no feature-reference mechanism is claimed.

**Resources:** available RAM before fit `8,804,618,240` bytes, before clean/restored bank `8,757,112,832` / `8,612,945,920`; free disk `17,644,544,000` before and `17,505,746,944` after; these are snapshots. CUDA allocated peak was `1,021,221,376` bytes for both banks, reserved peaks `1,264,582,656` / `1,268,776,960`. Fit/inference seconds are in `execution_status.json`; run began at 15:40 and status last updated 16:01:57, about 22 minutes end-to-end. No OOM or guard change.

**Return:** text-only metadata return at `handoff/returns/jihyuk/jihyuk-bankdomain-hazelnut-seed23-20261117-1540/`, receipt honestly says `NOT_REVIEWED` and `array_contents_verified=false`. Fallback metadata ZIP is `outputs/private-returns/JIHYUK_BANKDOMAIN_RETURN_HAZELNUT_SEED23_20261117.zip`, SHA-256 `80af8bffcec0650942205cb3d5c54bf5c90373cce5e3b3864df1f11b129b8fa4`. No raw maps, GT, input images, checkpoints or bank matrix was included. Correction for prior loose wording in the seed-11 notes: the runner retained bank vector counts and SHA-256 digests, not serialized bank matrices; the live in-memory banks were released at process end. Reconstructing them would repeat a completed fit, so no backfill run was made. Future source can preserve a bank matrix only if its existing disk guard/capacity can support that artifact; no such guard was weakened here.

**Next / interpretation:** queue now has 12 of 24 2x2 cells complete. Next unique run is Screw seed 23; then Hazelnut and Screw seed 37. The four Bicubic-normal-bank extension cells remain gated behind the original 24. No new category, sampling, metric, threshold, weight or performance search was added.

#### JH-20261117-05 — Screw seed-23 four-cell completion

**Run/source:** `jihyuk-bankdomain-screw-seed23-20261117-1612`; execution HEAD `ac931349ba0f3db795a5400534b3a79d2bdc4f44`, dirty branch `codex/bank-domain-study`; command exit 0, final state `COMPLETE`. The earlier seed-23 destination did not exist and no Python worker was active. The first guard-extraction wrapper stopped before model launch with `KeyError: required_free_bytes` because the saved disk requirement is nested under `resource_plan.prediction_disk`; no model process or run artifact was created by that attempt. The corrected read-only guard check passed before launch: available RAM `9,876,381,696` vs required `4,639,424,512` bytes; free disk `17,501,863,936` vs required `2,335,349,760` bytes.

**Verification:** 640 prediction rows, four frozen cells; 256 normal fit / 64 normal calibration / 160 test (119 anomaly). `verify_complete_run` checked expected bank/query/sample order and artifact hashes; five-file export contract passed. CPU consumer accepted one `model_predictions` run and exited 0 without re-evaluating detection metrics. Stored scores are finite `[64,2]` and `[160,2]`; maps finite `[64,2,224,224]` and `[160,2,224,224]`. Calibration/test parent order and query-input/Bicubic/SwinIR RGB hash lists are byte-identical across banks; bank hashes differ. Test predictions were persisted before GT reads. Normal-image per-image AU-PRO and ROI/background gap remain NA.

**Primary metric:** pooled AU-PRO@0.3 by clean/restored bank × Bicubic/SwinIR query: `0.8010117756`, `0.8545928632`, `0.8598559401`, `0.9394241365`. At fixed queries, restored-minus-clean pooled deltas were `+0.0588441644` (Bicubic) and `+0.0848312733` (SwinIR); mean paired per-image deltas were `+0.0773293879` and `+0.0749595374` across 119 anomalies. Localization regression cases were 17/119 and 9/119 respectively. At fixed clean/restored bank, SwinIR-query pooled deltas were `+0.0535810875` and `+0.0795681964`; paired per-image means were `+0.0758619913` and `+0.0734921407`. Per-image CI is not a pooled-AU-PRO CI; one seed is not independent cross-seed evidence. The query-by-bank association is not mechanism proof. No threshold/weight/performance search occurred.

**Inputs, source and resources:** protocol SHA-256 `79decd9b91e56df2c684e5409eec7b39e61dde6b763cc4e8723cbdc2c7ad9552`; WRN checkpoint SHA `95faca4d11227dddf8633dbb5ff6c8a9003c1aa5b8945c73834b8007b10950b8`; SwinIR SHA `09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e`. Available RAM before fit/after was `8,760,070,144` / `8,633,364,480` bytes; before-bank snapshots `8,730,648,576` / `8,554,983,424`. Free disk before/after was `17,501,818,880` / `17,342,705,664` bytes. These are snapshots, not peak RSS. In-process CUDA allocated peak was `1,021,221,376` bytes per bank, reserved peak `1,268,776,960` bytes. Per-bank fit/query durations were 16.30/570.64 s clean and 27.15/565.61 s restored. Total observed wall time about 21 minutes (worker started 16:13:37; exit 0 around 16:34). No OOM and no guard was altered.

**Return and artifact boundary:** text metadata return `handoff/returns/jihyuk/jihyuk-bankdomain-screw-seed23-20261117-1612/`, receipt `NOT_REVIEWED`, `array_contents_verified=false`. Fallback metadata ZIP SHA-256 `7d4499a73c894e5f07e3e370b227a2ba137323e3fd2d0baedadf1004b477e855`. Private raw NPZ hashes: clean `977e73f88f245a9c07da3f2f0f43523e01df3ccbdb4adc9b38b158794416247b`; restored `d37b805792b3865c9129c1fa0e434291ce81c845a52b62e890340bf2dd96e66`. Bank hashes: clean `0f0e7e79b39934e448195fbe78755f79e0faa794ce87f1942b0dbceb771dc299`; restored `0139cc61d065a74b6e1fc6454a7960042e658b2e13e1024122e0b66346ad6157`. Correction carried forward: bank counts and digests were recorded but the 200,704×1,024 float32 matrices themselves were not serialized; they were released after process exit. No completed fit was repeated to recreate them.

**Queue:** 16/24 original 2x2 cells are now complete. Next unique runs are Hazelnut seed 37 and Screw seed 37; after those, assess only the separately frozen 4-cell Bicubic-normal-bank extension. No new category or protocol search.

#### JH-20261117-06 — Hazelnut seed-37 four-cell completion

**Run/source:** `jihyuk-bankdomain-hazelnut-seed37-20261117-1639`; execution HEAD `ac931349ba0f3db795a5400534b3a79d2bdc4f44`, dirty branch `codex/bank-domain-study`; complete, command exit 0. Source/code/checkpoint/submodule/query and split hashes are in the run provenance and verification JSON.

**Verification:** 440 rows; 313 normal fit / 78 normal calibration / 110 test (70 anomaly). Artifact order/hash validation and five-file contract passed. CPU consumer accepted one stored `model_predictions` result with exit 0 and no detector reevaluation. Both bank hashes differ; calibration/test sample order and all three query RGB hash lists match. Scores and maps finite at `[78,2]`, `[110,2]`, `[78,2,224,224]`, `[110,2,224,224]`. Prediction arrays were saved before GT reads. Normal per-image AU-PRO and ROI/background gap stay NA.

**Pooled AU-PRO@0.3:** clean/Bicubic `0.8164353502`; clean/SwinIR `0.8417597795`; restored/Bicubic `0.8263199072`; restored/SwinIR `0.8494360616`. Restored-minus-clean at fixed query: `+0.0098845571` Bicubic, `+0.0076762821` SwinIR; mean paired per-image deltas `+0.0003275115`, `+0.0006112354` over 70 anomalies. Per-image regressions: 30/70 Bicubic and 32/70 SwinIR. Query pooled deltas at fixed clean/restored bank: `+0.0253244293` and `+0.0231161543`, per-image means `+0.0124687459` and `+0.0127524698`. Per-image confidence intervals include zero; they are not pooled-AU-PRO intervals. Seed is a paired repeated subset, not extra independent images. These observations do not establish a mechanism; no metric/model/threshold/weight search.

**Resources:** available-RAM snapshots before fit/after `8,790,212,608` / `8,773,083,136` bytes; before-bank snapshots `8,764,043,264` / `8,766,259,200`. Free disk before/after `17,340,387,328` / `17,180,319,744`. CUDA allocated peak `1,021,221,376` bytes per bank; reserved peaks `1,264,582,656` / `1,268,776,960`. Fit/query inference times 24.59/601.18 s clean and 37.43/605.17 s restored. About 22m30s elapsed from worker start 16:39:45 to final status 17:02:13. RAM/disk are snapshots, not peaks. No OOM or guard changes.

**Return:** `handoff/returns/jihyuk/jihyuk-bankdomain-hazelnut-seed37-20261117-1639/`; receipt is `NOT_REVIEWED`, `array_contents_verified=false`. Metadata-only ZIP SHA-256 `8608c90ecb9bc5e97de9b085eb2e5cc995ca6c14a7b63c87e602e93ad1371668`. Raw NPZ SHA-256 clean `b6868d8c1be11701d2a293f51161615c3128a2fe5632d3743fb30e9001c5af07`; restored `5502cb9d30729bf11b70d9c5e071ee6c9c004a5da786768eff0887a2ac3b8eba`. Those raw arrays and GT remain private. Bank matrix serialization limitation from JH-04/05 remains: counts/digests were saved, not the full matrices.

**Queue:** 20/24 original 2x2 cells complete. Next is Screw seed 37. Bicubic-normal-bank four-cell extension remains after the original 24.

#### JH-20261117-07 — Screw seed-37 four-cell completion; original queue closed

**Run/source:** `jihyuk-bankdomain-screw-seed37-20261117-1704`; HEAD `ac931349ba0f3db795a5400534b3a79d2bdc4f44`, dirty branch `codex/bank-domain-study`; `COMPLETE`, process exit 0. No duplicate seed-37 run was present before launch.

**Verification:** 640 rows, 256 normal fit / 64 normal calibration / 160 test (119 anomaly). Complete ordered artifact hashes and five-file result contract passed; CPU consumer accepted `model_predictions` with exit 0 without recomputing detector metrics. Both banks have different feature digests; calibration/test sample lists and original/Bicubic/SwinIR query hashes match across banks. Calibration/test score arrays finite `[64,2]`, `[160,2]`; maps finite `[64,2,224,224]`, `[160,2,224,224]`. Prediction arrays were saved before reading test GT. Per-image normal AU-PRO and ROI/background gap are NA.

**Pooled AU-PRO@0.3 cells:** clean/Bicubic `0.8019283686`; clean/SwinIR `0.8563210721`; restored/Bicubic `0.8571735018`; restored/SwinIR `0.9425510874`. Fixed-query restored-bank deltas were `+0.0552451332` and `+0.0862300153`; per-image mean deltas `+0.0773482134` and `+0.0745254701`, over 119 anomaly images. Per-image regression counts were 16/119 and 12/119. Fixed-bank query pooled deltas were `+0.0543927034` clean and `+0.0853775856` restored; per-image means `+0.0765731703` and `+0.0737504270`. Per-image uncertainty intervals are supplementary; pooled AU-PRO CI was not computed. This is a single-seed paired result, not a mechanism proof or cross-seed interval.

**Resources:** RAM snapshots before/after `8,823,853,056` / `8,665,124,864` bytes; per-bank snapshots `8,823,599,104` / `8,779,128,832`. Free disk before/after `17,177,391,104` / `16,276,123,648`. These are snapshots, not peak RSS. CUDA allocated peak `1,021,221,376` bytes per bank; reserved peaks `1,264,582,656` / `1,268,776,960`. Fit/query timings 16.37/597.44 s clean and 26.59/597.21 s restored. Wall time about 21 minutes. No OOM or resource guard adjustment.

**Return:** `handoff/returns/jihyuk/jihyuk-bankdomain-screw-seed37-20261117-1704/`; receipt honestly says review pending and array contents not independently verified. Metadata-only ZIP SHA-256 `448a3d4f61ec84a0e89dd4121336d6e053cc0c581cc6854a9fe31931b53885b2`. Raw NPZ hashes: clean `4e3fd2bf0c24475dd77cc62d9381dd681a6143510aed6b753ef825f5e1cadd55`; restored `fc63cef0bc72043f2eaec9f62c0c023d44245c47beed56ad7c235eb0addebf90`. Bank hashes: clean `c25e7ddbfe616d0759b7893216cf64fc225bb169933dfc07605714eb5ce600bb`; restored `901fb2cf16129e5cabe0ce739fc765b35c53c339cc0c93bc1921ebc4d0214914`. Raw files/masks/inputs/weights remain private. As already corrected in JH-04 onward, only bank digests/counts—not full bank matrices—were serialized.

**Queue transition:** original 2x2 plan is 24/24 completed: Hazelnut/Screw × seeds 11/23/37. The seed11 Bicubic-query baselines are in their existing complete returns. Next is the four-condition Bicubic-normal-bank extension, with only Hazelnut/Screw seed11 and both already existing queries; no new query-clean or extra seed/category. Extension remains a distinct family/schema.

#### JH-20261117-08 — Pre-register the separate Bicubic normal-bank extension

**Timing:** written after the fixed 24-cell queue completed and before the extension code/model execution. Frozen by the user's explicit prompt; this record makes the implementation boundary and acceptance checks explicit before observing extension results.

**Question:** when the normal fit images and a query are both represented by the same fixed x4 Bicubic transform, does a normal PatchCore bank built from Bicubic-transformed fit images change stored pooled AU-PRO relative to the already complete clean-bank result for the identical Bicubic query? A second fixed query (`swinir_x4`) in the new bank is retained to keep the extension a two-query family; it does not create a query-clean input.

**Frozen conditions:** only Hazelnut and Screw, seed 11. New bank domain `bicubic_x4` is fit from the exact same normal fit parent subset and ordinal all-patch IdentitySampler rows as the other seed-11 banks. Queries are the two existing byte-identical `bicubic_x4` and `swinir_x4` streams. Calibration uses the same normal calibration parent subset, separately, and the existing robust normalization/fixed q0.99 thresholds are fit separately for each query from normal calibration only. Test paths, RGB hashes, SwinIR/backbone checkpoints, preprocessing, PatchCore feature/geometry, FAISS, memory and disk guard, metric definitions and query order remain fixed. Test GT stays unread until the extension prediction NPZ is saved. Existing main-study seed-11 clean-bank/Bicubic-query rows are reused as the matched baseline; no query-clean data or new clean-bank prediction is generated.

**Primary/failure rule:** compare stored dataset pooled AU-PRO@0.3 for `bicubic_x4 bank × bicubic_x4 query` against the existing `clean bank × bicubic_x4 query`, then report the analogous same-query SwinIR row as context. Keep per-image paired deltas/regressions supplementary. Do not promote a method, claim an information-loss mechanism, tune any threshold/weight/sampler, or reinterpret query-quality values. Extension output family/schema and analyzer stay separate from the four-cell 2x2 contract.

**Acceptance before execution:** fake tests must cover exact bicubic fit transform, extension manifest/file hashes, baseline-query identity and per-image pairing; complete run must preserve full bank/query cells, fit/calibration/test identities, finite native maps/scores, raw hashes, test-GT ordering, actual source/code/checkpoint/query digests, fixed guard, and CPU-only analysis with no raw array/model loads. If any gate fails, preserve the partial and do not substitute/trim conditions.

#### JH-20261117-09 — Hazelnut seed-11 Bicubic-bank extension completed and raw predictions resumed

**Source/run:** `jihyuk-bicubic-bank-hazelnut-seed11-20261117-175015`; run-time source HEAD `ac931349ba0f3db795a5400534b3a79d2bdc4f44`, dirty branch `codex/bank-domain-study`. The four-condition main 2x2 seed-11 baseline is the existing Hazelnut run `jihyuk-bankdomain-hazelnut-seed11-20261117-1432`. The extension is its own family/schema: Bicubic normal-fit bank against the same existing Bicubic and SwinIR query streams.

**Observed failure and recovery:** the first model command exited 1 after the complete raw archive had been saved. The evaluation stage attempted `sha256_file(sample.mask_path)` for normal test samples, whose official `mask_path` is `None`. No test GT was read before the failure. The failed status snapshot is preserved as `status.failed.initial.json`, SHA-256 `d3efd406b8ca1aba892af89ccb234a8e2330251988bfd59d80c1d891a82379f8`; the original PowerShell transcript is also kept privately. Raw `raw_bicubic_x4.npz` SHA-256 is `675a099f70a7d0f4ebb9b6b9e548ebbe8e5633a42d8150d3d662e0eb536eb9c8` (66,758,287 bytes), with 78×2 calibration scores, 78×2×224×224 calibration maps, 110×2 test scores and 110×2×224×224 test maps; the raw artifact verifier checked all finite and the correct query/sample order. The saved feature bank had 245,392×1,024 float32 vectors, 1,005,125,632 bytes, SHA `d04ea63a56fd8530352ae94ccac9aff0651349e69c471606a3ca32129b4814bd`; the run code checked shape/dtype/finiteness before retaining only its digest.

The correction is to represent a normal sample with no official mask as an all-false 224×224 mask and `mask_sha256=None`, while retaining masks for anomalous test samples. The saved raw predictions were reused by `resume_bicubic_bank_extension_evaluation.py`; no model, fit, or query inference was rerun. The complete clean-bank baseline's stored per-image quality rows were reused because the extension's input/query manifest digest exactly matches that baseline; quality pixels were not regenerated. That provenance choice avoids a second SwinIR pass and is recorded in `provenance.json`. Resume exit code was 0; final status is COMPLETE with 220 ordered prediction rows. The first failure remains explicit in `initial_error`, `resume_history`, and the immutable status snapshot.

**Results:** 313 normal fit / 78 normal calibration / 110 test (70 anomaly); one Bicubic bank with 245,392 all-patch IdentitySampler vectors and two fixed query domains. Pooled AU-PRO@0.3: same Bicubic query clean bank `0.8175193283`, Bicubic bank `0.8379849620`, delta `+0.0204656337`; same SwinIR query clean bank `0.8412522084`, Bicubic bank `0.8548927960`, delta `+0.0136405876`. The within-Bicubic-bank query delta is `+0.0169078340`. CPU analyzer validated byte-bound execution sources from a preserved run-time source snapshot, accepted `model_predictions`, opened no raw arrays/images/models, and recomputed no detector metrics. Per-image deltas/regressions are supplementary; pooled AU-PRO CI is absent. This is one paired test cohort; it does not prove an information-loss or restoration mechanism.

**Resource record:** in-process fit 26.356 s and query inference 632.229 s; torch CUDA peak allocated/reserved 1,021,221,376 / 1,264,582,656 bytes. Available RAM snapshot before fit was 7,943,634,944 bytes and after evaluation/resume 10,183,442,432 bytes; free disk before fit 17,019,781,120 bytes and after 16,913,240,064 bytes. These are snapshots, not RAM/disk peaks. No RAM peak was measured. A post-run idle query showed 49°C and 493 MiB used; this is not execution peak temperature/VRAM. No OOM and no guard adjustment.

**Alternatives and choice:** a full repeat would recreate quality and metrics but would duplicate completed fit/query work; rejected. Reusing the same-query baseline quality is valid only after exact input/query manifest equality and is explicitly distinguished from a quality measurement in this extension. The true issue was missing handling for normal `mask_path=None`, not a metric/model incompatibility. Future Screw seed-11 extension now applies the normal-mask rule in the runner before starting. No additional category, seed, query, threshold, sampler, weight, or metric changes.

**Return/artifact:** public text return `handoff/returns/jihyuk/jihyuk-bicubic-bank-hazelnut-seed11-20261117-175015/`, receipt `NOT_REVIEWED`, `array_contents_verified=false`. Metadata-only ZIP SHA-256 `c8988ce32e040c85f2b046d58838a4326ec81dde4b5c186aa2d898244885950b`. Raw maps/masks/bank arrays/checkpoints remain outside Git/ZIP. No full bank matrix was serialized; counts and hash only. Pending: finish the same four-condition family for Screw seed 11, then consolidate the two seed-11 extension outputs. GitHub push/auth status remains separate from local return preparation.

#### JH-20261117-10 — Screw seed-11 extension completed; Bicubic-bank 4-condition family closed

**Run/source:** `jihyuk-bicubic-bank-screw-seed11-20261117-181942`; command exit 0, final `COMPLETE`; source HEAD `ac931349ba0f3db795a5400534b3a79d2bdc4f44`, dirty `codex/bank-domain-study`. Existing complete baseline: `jihyuk-bankdomain-screw-seed11-20261117-1510`. This was a new Bicubic normal-fit bank only; same clean/SwinIR query streams, same seed-11 input/split/checkpoints and main clean-bank baseline. No query-clean dataset or duplicate main 2x2 result was made.

**Verification:** 256 normal fit / 64 normal calibration / 160 test (119 anomalies), 200,704×1,024 float32 all-patch IdentitySampler vectors (822,083,584 bytes), bank SHA `8e30cab1847207be147a96fa9719db69469ae805838e01af1eb098230d9910e6`. Raw `raw_bicubic_x4.npz` SHA-256 `2f741f381af63e5c633976e13e77bee40b566053e897d195c178a2ef40505678`; complete verifier checked 320 prediction rows, ordered calibration/test and two fixed queries, expected shapes, finite maps/scores, and all artifact/export hashes. Query manifest SHA matches its existing clean/restored baseline. Predictions were saved before any GT access. The fixed resource guard passed without change.

**Pooled AU-PRO@0.3:** at fixed Bicubic query, clean-bank `0.7990657469` vs Bicubic-bank `0.8988871109`, delta `+0.0998213640`; at fixed SwinIR query, clean-bank `0.8531818394` vs Bicubic-bank `0.8615534070`, delta `+0.0083715677`. Within the Bicubic bank, SwinIR-query minus Bicubic-query is `-0.0373337039`; its same contrast in the existing clean bank is `+0.0541160924`. These are paired associations from one test cohort, not a causal mechanism. Same-query quality deltas across banks are zero by contract. Supplementary per-image bank deltas: Bicubic query mean `+0.138520` (13/119 regressions); SwinIR query mean `-0.010678` (64/119 regressions). No pooled AU-PRO CI was computed.

**Resources:** measured fit `16.763 s`, query inference `576.393 s`; query restoration sum `6.950 s`; torch CUDA allocated/reserved peak `1,021,221,376 / 1,264,582,656` bytes. Transcript wall duration was 676 seconds (18:19:42–18:30:38). RAM snapshots before fit / after `8,979,808,256 / 9,150,791,680` bytes; free disk snapshots before / after `16,910,475,264 / 16,036,585,472` bytes. RAM peak was not measured. Post-run idle GPU observation was 49°C and 490 MiB used; not execution peak. No OOM or guard adjustment.

**CPU consumer:** completed actual extension analysis under separate family/schema; source-byte binding passed for the current execution tree, no raw arrays/images/models were opened, and detector metrics were not recomputed. Per-image bank deltas were retained as supplementary rows. The adapter and its 5 synthetic tests are distinct from the execution runner. Focused execution-side contract/resume tests: 5 passed; source-only analysis tests: 5 passed, all in fresh OS temp directories.

**Source patch:** storage-only patch `handoff/patches/jihyuk-bicubic-bank-extension.patch`, SHA-256 `4aeeade3e0e0438fccab390bcb1db5acb24d81bfed2c564ef5ea7a4e665b03a6`; `git apply --check` passed in the source-only tree. It includes the runner, contract, resume utility and focused synthetic tests; it was not reapplied to the existing feature checkout. Run-time code SHA snapshots are recorded in each run's provenance. The local `handoff/jihyuk` return commit is `9fb5947d59151e49360e6350c2fc0262a6f2a826` and follow-up progress commit is `305aec4a40dbc6f9520d360c3066a04d234c311d`; the branch is clean locally but remains unpushed because the known HTTPS username/auth failure is unchanged.

**Extension interpretation:** Hazelnut seed 11 same-query Bicubic-bank deltas were `+0.020466` (Bicubic query) and `+0.013641` (SwinIR query); the within-Bicubic-bank query delta was `+0.016908`. Screw's corresponding bank deltas were `+0.099821` and `+0.008372`; its within-Bicubic-bank query delta was `-0.037334`. Thus query-domain comparison changes with bank domain in these paired test cohorts, especially Screw. Absolute performance and seed-11-only scope remain visible; no mechanism claim, method promotion, threshold/weight/sampler search, new category, or new query.

**Return/artifact:** `handoff/returns/jihyuk/jihyuk-bicubic-bank-screw-seed11-20261117-181942/`, receipt `NOT_REVIEWED`, `array_contents_verified=false`; metadata-only ZIP SHA-256 `305e106789aa7d48c333c3ded478ed7f81fc3d1a98b81322c01cdb1978145a6a`. No arrays, bank matrices, GT, RGB, or checkpoint entered the return. Main 24 cells plus this separate 4-condition Bicubic-bank extension are complete. Open: CPU review and public remote update; the earlier GitHub HTTPS username/auth failure is unchanged, so no repeated auth probe or push was attempted. The private MVTec repack SHA is verified; original publisher archive SHA remains unknown.

### CPU 추가 전달 검증


추가전달ZIP은outputs/jihyuk-bicubic-return-review-20261117/juhyung-bank-results-followup-private-20261117.zip이다. 24entries/286291bytes/SHA256 8b47b695b3776abe5bcc8131e0ed48eee4731a8b5b0b618dd434f41a83ae6d13, CRC/내부SHA검증통과. 기존23MB패킷은보존하고이번추가지시가bank신규실행부분을갱신한다. 기존자동화의실제상태PAUSED/5시간일정/현재채팅은그대로유지하고prompt만갱신했다.
이검증문구는ZIP내스냅샷이후외부기록이다. 새모델/장비실행은없다.

## Stage 72 · 차기 반환의 결론·그림 검토 기준 (2026-11-17)

사용자는현재주형작업의결과를받은뒤필요한추가작업을정리하도록요청했다. 첨부글은후속아이디어로읽고,실제Git source90d2bf3과기존표/문서로수치와범위를검증했다.

PCB 1140은처리단위이고평가분모는정상100/이상100영상이다. 각variant의normal-calibration q0.99임계값은서로다르며FN29→46/FP3→1의관측과AU-PRO+0.00483155를함께설명할수있다. 동일empirical FP3에서TPR범위가겹치므로일률적우열을확정할수없다. 이진단은test-score사후분석이며새운영임계값을testlabel로고르지않는다.

pooled/per-image부호차이를Simpson역설이나대면적소수사례의효과로확정하는근거는없다. 계열전체최고bank나SR효과부재도미확정이다. 세기/형상변화분류와실제RGB결함소실기전을구분한다. 코호트imageAUROC와개별그림의per-image지표도분리한다.

phone전체16/공통7/사후5는각분모를유지한다. 공통7에서는REVIEW0,전체16에서는REVIEW6이며정상라벨13중NG1/REVIEW6이다. 논리사진접근10/14,6/10은실제취득시간/비용절감으로일반화할수없고사후구성·공유대체·참조재사용을유지한다. 5도는합성시험관측이며실제카메라공차미검증이다.

후속작업은현재반환을받아receipt/실제파일로완료여부를먼저확인하고실제미완료만마무리하는것으로제안했다. 6bank사례사진을재사용하고기존PCB9case중운영점전환사례가없으면저장결과에서TP→FN/FP→TN각1개를사후그림으로보강한다. 필요한새촬영/사람판독/시간이없으면대기범위로표시하고기존사진·보고서·포스터를완성한다. 추가GPU조건·모델·하드웨어확장은지시하지않았다.

차기검토문서는outputs/final-evidence-next-review-20261117/NEXT_RETURN_REVIEW.md다. 현재공개handoff/작업지시/촬영계획은그대로유지했다. 이번선택은다음반환검토안이며새프로토콜채택이나실험결과가아니다.


## Stage 73 · 11월17일 최종 반환 수신과 Fable 5.2 전체 검토 준비 (2026-11-18)

사용자는 새 반환물을 바탕으로 Fable 5.2의 전체 검토·개선 설계 프롬프트를 요청했다. 실제 Fable 실행은 이번 작업의 산출물로 주장하지 않는다. 최신 반환 RUN_RECORD와 receipt는 claude-opus-5-5를 기록한다. Fable의 실제 세션·라우터 실행 모델 확인이 다음 검토의 조건이다.

원본 ZIP 48,629,145 bytes / SHA-256 d39461caf2dc7ac52ce91390e91a7e7d38533a650b0039c25831355116c7ec58를 확인했다. receipt 대상262개 payload의 bytes/SHA, CRC, 내장 지혁 확장24개 payload를 검증했다. 내장 확장 결과는 이전 수신본과 동일하므로 이전 검토를 재사용한다. 신규12개 private 결정을 아래 원문으로 처음 통합한다. 과거 D-20261115 항목은 중복 수록하지 않는다. 원본 전체는 outputs/private-decision-imports/juhyung-20261118-35218d50/RESEARCH_EVOLUTION_LOCAL.private.md에 보존했다.

주형3개 완결 run의12셀은 metadata binding과 per-image score 기반 image AUROC, PSNR/SSIM 평균을 CPU로 재계산해 일치했다. 실행소스24개 해시도 기록 commit과 대조했다. pooled/pixel 지표와 full raw stack은 재계산하지 않았다. 선정6개 crop NPZ는 finite/numeric 확인을 마쳤고 clean/swinir_restored bank 지도만 있다. full raw 예측 stack과 bank matrix는 전달되지 않았다.

gallery의 local image73참조에 누락이 없고 manifest76파일 해시가 맞는다. 결함 zoom은24슬롯 중23개 available이다. 수신 포스터 preview와 Screw 대표1개 패널을 시각 확인했다. 갤러리 전체와 PDF/PPTX의 전수 시각검토는 다음 Fable 작업이다.

독립 검토에서 확인할 사항을 기록한다. 과거 Screw clean image AUROC0.984218의 normal fit은320이고 신규 bank 실험은256 fit/64cal이다. 해당 기준선을 동일 protocol 대조로 해석하려면 조건 차이를 해결해야 한다. 우선 역사적 참고값으로 명시할 수 있다. Hazelnut 평균 per-image CI가0을 포함한다는 결과는 효과 부재의 확정 근거가 아니다. 주형·지혁 교차검증은 seed11 clean-bank4셀 범위이며 PSNR/SSIM 일치는 RGB bytes 동일성 확인과 구별한다. Bicubic-bank6사례 지도와 지혁 기본24의6원래반환/미공개코드가 수신 대기다.

촬영은 주형 소유 source74dc9fa의 고정v2를 사용한다. 이전 CPU50행 초안의 라벨/그룹 오류를 주형이 수정했으므로 새 패킷에 소유자의 실제v2계획·기록표·사람판독표를 그대로 넣는다. 기본14cycle32장과 작은이물9cycle18장을 별도로 보고한다. 새 사진·사람판독·실제시간·팀정보는 아직 없다. UNO는 사용자가 결정한 시연 범위에 따라 후속이다.

원본 checkout79a1c0f와 사용자 PROGRESS 변경을 보존한다. 검토용 detached worktree73f7245를 별도 만들었다. 현재 새 source commit으로 bankc60dd80/phone74dc9fa를 fetch했다. 이번에는 새 모델/장비실험·pytest·공개 push·외부 메시지 전송을 하지 않았다. 다음 작업은 실제 Fable 세션에서 전체 검토와 독립 설계를 기록하고, 기존 결과·cache를 재사용해 가능한 수정과 최종 사진 산출물을 완성하는 것이다.

### 수신 결정 원문
#### D-20261117-01 · bank 실행을 별도 worktree에서, CPU 분석기는 handoff checkout에서 [당시]
- **문제:** 지혁 producer 패치의 `scripts/analyze_bank_domain_study.py`가 CPU consumer와 이름이 같다.
- **대안:** (a) 한 checkout에 합치고 이름을 바꾼다. (b) producer는 새 worktree `exp/bank-domain-juhyung`(40d57dd 기반), consumer는 기존 handoff checkout에서 그대로 실행한다.
- **선택:** (b). 두 구현과 호출자를 바꾸지 않는다. 패치 2개는 바이트 그대로(`-text`) `b94a189`로 적용했다.

#### D-20261117-02 · 더러운 소스로 시작한 첫 run 중단 [당시]
- **문제:** 첫 run을 패치 미커밋 상태로 시작했다(git_dirty true가 기록될 상황).
- **선택:** 즉시 중단하고 커밋 후 새 run-id(`…20261117b`)로 재시작했다. 중단 run과 로그는 `STOPPED_dirty-source`로 보존했고 결과로 쓰지 않는다.
- **이후 규칙:** run이 도는 동안 그 worktree에 미추적 파일을 두지 않는다. 새 스크립트는 바로 커밋했다.

#### D-20261117-03 · 데이터셋 provenance 영수증 [당시]
- **문제:** runner가 `dataset_provenance.json`을 요구하는데 원본 archive가 로컬에 없다.
- **선택:** `scripts/fit_patchcore.py`에 기록된 archive SHA(`cf4313b1…cd3d`, commit 2c1be57)와 실제 license 파일 해시로 영수증을 만들었다. archive 파일 자체는 대조하지 않았다는 점을 그대로 둔다.

#### D-20261117-04 · 확장 4조건은 별도 스크립트·별도 family [당시]
- **선택:** 기본 run이 쓰는 runner를 실행 중에 고치지 않으려고 `run_bank_domain_bicubic_extension.py`를 따로 만들었다. 기본 run의 split·query 해시가 같을 때만 진행한다.
- **[사후]** 추가 지시로 실행하지 않았다(D-20261117-09).

#### D-20261117-05 · export의 ROI-background gap [당시]
- **문제:** bank마다 지도 척도가 달라 원시 지도의 gap은 bank 사이에서 비교할 수 없다.
- **선택:** 각 cell의 정상 보정 median/IQR로 정규화한 지도에서 gap을 잰다. 시험 GT는 사후 평가에만 쓴다.

#### D-20261117-06 · 같은 결함 위치 확대의 사례 선정과 crop [당시]
- **선택:** 기존 분류(Δ영상별 AU-PRO, Δgap)로 분류별 1사례: 개선은 최대 Δ, 억제·형상은 최소 Δ, 작은 변화는 최소 |Δ|. 없는 분류는 "없음"으로 남긴다(Screw 추가 열화 없음의 형상 후보 0건).
- crop은 GT 상자 + 25 %(최소 48 px)이고, 처음 쓴 64 px 중심 crop은 큰 결함을 잘라서 버렸다.
- 열화 입력은 다시 만들어 저장된 Bicubic 출력을 바이트 단위로 재현할 때만 썼다.

#### D-20261117-07 · 촬영 계획 v2 [당시]
- **문제:** 보유 사진(24장)은 이물+저조도, 이물+흐림, 작은 이물 조합이 없어 계획 50장 어느 것도 대신할 수 없다.
- **선택:** 실행 계획 v2(`eval_v2_frozen_20261117`)를 고정했다. 기본 14 cycle(정상 8, 이물 6)과 작은 이물 9 cycle로 묶음을 나누고, 섞이면 거부한다.
- 고친 버그: 작은 이물 행이 "unknown"이라 정상으로 셀 위험, L1 위치 문구 불일치, 흐림-2 메모의 모순.

#### D-20261117-08 · 결과 화면 문구: 사본 정정 + 소스 수정 [당시]
- D-20261115-17(다시 실행해야 고칠 수 있음)을 바로잡는다.
- 사본 HTML 첫 줄만 v0.3 문서로 고쳤고, 원본은 `report_original_v02banner.html`로 보존했다. 판정·수치는 그대로다.
- 이후 실행부터는 `10ca115`에서 v0.3 문서를 자동으로 표시한다.

#### D-20261117-09 · 지혁 완료 보고 후 기본 run 재개 중단 [당시]
- **상황:** 기본 run 3개가 완료된 뒤 세션이 끊겼다(Screw seed 23은 원본 bank까지, `BUILDING`). 그 사이 지혁의 24/24 + 확장 4/4 완료 보고와 "중복 실행하지 말고 회수·통합"이라는 갱신 지시가 도착했다.
- **선택:** 재개하지 않고 확장도 돌리지 않는다. 완료된 3 run은 독립 재현으로 보존하고 교차 확인에 쓴다.
- **교차 확인:** Bicubic 입력 화질은 비트 일치했다. SwinIR은 GPU 차이로 ≤0.0015 dB, 원본 bank pooled 차이는 ≤0.0004다.
- **남은 것:** 지혁의 원래 6개 반환과 선정 6사례의 Bicubic bank 지도. 요청 초안을 썼다(전송하지 않음).

#### D-20261117-10 · 선정 6사례 그림의 출처 혼합 [당시]
- **문제:** CPU 검토가 정한 6사례(지혁 Bicubic-bank 표 기준)에 필요한 지도가 수신 자료에 없다.
- **선택:** 원본/SwinIR bank 지도는 주형 재실행에서 만들고, Bicubic bank는 수신 값만 그림 안에 인용한다. 그림과 index에 출처를 구분해 적었다.
- SwinIR 입력은 CPU에서 다시 만들면 해시가 달라 GPU에서 만들었다. 6사례 모두 producer 해시와 일치한다.

#### D-20261117-11 · 포스터 구성 변경 [당시]
- **추가:** 그림 K(Screw seed 11 bank × 입력 6셀, 기준선 = 열화 없음 0.984), 그림 Z(같은 결함 위치의 원본/56 px/Bicubic/SwinIR와 두 bank 지도).
- **제외:** 공간 때문에 C(집계 규칙)와 E2(품질·대체 촬영 사진)를 뺐다. C의 결론은 본문 한 줄로 남겼고 E2 사진은 갤러리에 있다.
- 팀 정보는 확정 자료가 없어 자리 표시를 유지했다. USER_GOAL_GUIDE에 소속·지도교수·과제명 후보가 있지만 확정값으로 쓰지 않았다.

#### D-20261117-12 · 해석의 범위 [당시]
- **관측:** Screw에서 검사 입력과 같은 처리의 정상 bank가 image AUROC를 0.67 → 0.92로 올렸다. 영상별 평균 +0.076 [0.057, 0.097]이다. Hazelnut에서는 효과가 없다(CI가 0을 포함).
- **주장하지 않는 것:** 기전(결함 RGB 소실 대 정상 기준 불일치), 다른 category·seed로의 일반화, 최적 bank. seed 11 한 번이고 Hazelnut seed 23은 같은 이미지의 반복이다.
- 이는 Stage47 CPU HOG의 "같은-query 정상 bank 적응" 질문에 대한 PatchCore 쪽 첫 관측이다. HOG 결과와 합치지 않는다.

#### 남은 질문 (2026-11-17)
1. 새 평가 촬영 50장(계획 v2)과 사진별 사람 판독표, 실제 촬영 시간.
2. 지혁의 기존 24조건 원래 반환 6개, source-only `8af5aa` 코드, 선정 6사례의 Bicubic bank 지도.
3. 포스터의 팀 번호, 저자·지도교수, 소속·연구실, 제목 확정.
4. AE/AF 잠금과 HDR 상태.
5. UNO 실물 시연 여부.
6. ANN 검색, 자동 drift 보정, 조명 피드백 보드, XY 스캐너 확장은 채택하지 않았다(가이드 제안). 채택하려면 별도 결정이 필요하다.

마지막 결정 ID: **D-20261117-12**

### CPU 패킷 최종 검증

전달 패킷 최종 검증은 25파일/336317bytes, SHA-256 225b7a7d7f801b0d773700f5656505c7b410fbdbf220015257473004fa6c4c77이다. CRC와 인덱싱한24payload 해시가 모두 맞다. ZIP 안 기록은 포장 전 snapshot이고 이 최종 포장 기록은 외부에 남긴다.


## Stage 74 · 고정50장 촬영 안내와 범위 확인 (2026-11-18)
사용자가 이전24장 안내판처럼 새50장을 정리해 달라고 요청했다. owner74dc9fa의 v2 CSV50행을 그대로 번호화했다. 기본32장/평가14cycle, 작은이물18장/보조9cycle, 전체23cycle이다. 32번만L1대체도흐림이며 작은이물9cycle의L1은모두선명이다.

outputs/phone-capture-guide-50-20261118에 준비·위치PNG, 기본32PNG, 작은이물18PNG, 통합HTML, 간편50행촬영·시간·사람판독표와 owner계획/실행CSV를 준비했다. 기존4사진은구도·흐림예시로동일crop/resize만적용했고밝기·대비·합성흐림은없다. M1=P1,M2=P2,M3=P3는구역제안이며실제빈초록면에놓을점은촬영전에고정·기록한다. 저조도첫사진방조명OFF→평소방조명+선명L1대체로절차를명시했다.

50번호/조건·group·23cycle,owner4파일byte동일성,HTMLlinks,원고Unicode,PNG3장시각확인을마쳤고footer여백/줄바꿈을수정했다. 14개파일/3624030bytes SHAa9e4dc7e7e4e1c0aa5dcd5ea7f41da6a572996bb2406693e507b93bd64c14b44 CRC/receipt해시통과. 새관측사진은0장이고사람판독/실제시간도아직없다. 현재한기판·모사이물의고정촬영입력을50장으로채울수있으며,그뒤복원/검사/사진비교/정책평가가필요하다. 실제균열·단선·납땜결함과다른보드·현장의일반화근거는별도로남는다. 기존실행정책과완료실험은변경하지않았다.


## Stage 75 · 11월 19일 반환 결정과 현재 범위 (2026-11-19)

주형의 비공개 원문에서 새 결정 8건을 가져왔다. 아래 결정 내용은 당시 기록이다. 현재 판단은 문서 끝에 덧붙였다. 원문과 해시는 `outputs/private-decision-imports/juhyung-20261119-025ee29a/`에 있다.

#### D-20261119-01 · Fable 검토 대기와 수행 범위 [당시]
- **문제:** 지시는 Fable 5.2의 실제 실행 증빙을 요구하는데, 실행 모델이 Opus 5.5로 표시됐다.
- **선택:** Fable 의존 검토는 대기로 기록한다. 사용자 요청인 새 사진 평가·수정·갤러리·보고서·포스터는 Opus 5.5로 수행하고 그렇게 표시한다.
- Codex 검토를 시작 때 함께 읽어 "독립 판단 후 대조" 순서를 지키지 못했다. 그대로 적었다.

#### D-20261119-02 · 사진-행 대응과 ROI [당시]
- 기록표 `file` 열이 비어 있어 촬영 순서로 넣었다. 밀착 인화로 대조했고 소유자 확인은 요청했다.
- ROI는 새 REF_L0만 보고 PCB(방열판 제외)로 정했다. 평가 결과를 보기 전이다.

#### D-20261119-03 · 고정 평가 결과를 그대로 보고 [당시]
- L1 25장이 정렬에 실패해 C3가 23/23 ERROR, 대체 조명이 무효였다. 방법을 고쳐 다시 돌린 결과를 평가로 바꾸지 않는다.

#### D-20261119-04 · Hazelnut 결론 문구 정정 [당시]
- D-20261117-12의 "Hazelnut에서는 효과가 없다(CI가 0을 포함)"를 "방향·크기 불확실"로 바로잡는다.
- 그 CI는 고정 fit에서의 평균 paired per-image delta에 대한 것이고 pooled CI가 아니다. 원문은 보존한다.

#### D-20261119-05 · 정렬 개선안 선택: 같은 조명 참조 [당시]
- **대안:** CLAHE 균등화 / 같은 조명 참조 정렬 / 학습형 특징.
- **probe:** 49장 기준 성공은 anchor 16, CLAHE 13, 같은 조명 41이다.
- **선택:** 같은 조명 참조 정렬을 v0.4 후보로 한다. 실행기를 바꾸지 않는 래퍼로 구현했다.
- 이 세션으로 고르고 확인했으므로 개발 근거다. 가정: 두 조명 참조가 같은 카메라 자세다.

#### D-20261119-06 · 작은 이물 판정의 해석 [당시]
- 개발 변형에서 9/9 NG다. 물체 위치 덩어리는 9/9에 있으나 가장 큰 덩어리는 3/9만 물체에 있다.
- 작은 이물 블록은 같은 자세의 정상 사진이 없어 다른 곳 차이의 원인(이동·정상 변동)을 가리지 못한다.
- "작은 이물 검출 9/9"로 주장하지 않는다. 다음 계획에 블록 정상 사진을 넣는다.

#### D-20261119-07 · 기준선 0.984 표시 [당시]
- historical_recovery(정상 320장 bank)의 참고값이다. 새 bank(256 fit)와 같은 조건의 기준선이 없으므로, 새 실험 대신 범례와 제목 문구를 고쳤다("되살린다" → "크게 높아진다").

#### D-20261119-08 · 포스터 패널 ② 교체 [당시]
- 개발 세션 24장의 그림 E1·E3·E4를 빼고, 새 촬영 세션 그림 N(저조도 → 대체 조명 → 같은 위치 차이 지도)과 P(묶음별 판정)를 넣었다.
- 개발 세션 결과는 보고서와 갤러리에 남는다.

## 남은 질문 (2026-11-19)
1. Fable 5.2 실제 연결과 재검토.
2. 사진-행 대응 확인, 사람 판독표, 촬영 시간, 이물 종류·크기.
3. 지혁의 Bicubic bank 지도와 기존 24조건 원래 반환.
4. 팀 정보.
5. 계획 v3(블록 정상 사진, 조명당 보정 3장) 촬영 여부.
6. historical_recovery seed 기록 불일치(미기록 / seed 11).

### 이후 확정한 항목

- 사용자가 Fable 5.2 검토와 모델 증빙 요구를 철회했다. 주형의 이번 결과 생성과 검토 수행 기록은 Opus 5.5이고, Codex가 수신 자료와 원 실행을 대조해 제출 범위를 판단했다.
- 원본 50장의 해시와 촬영 시각 순서를 확인했다. 실제 조명·흐림·이물 조건은 촬영자가 확인한다. 고정 v0.3을 별도 촬영 세션의 결과로 사용한다. 같은 조명 참조 정렬은 이번 세션을 보고 고른 v0.4 개발 후보다. 작은 이물은 개발 변형에서 9건 NG, 가장 큰 이상 영역의 위치 일치는 3건이었다. 선명 L1 사진의 인위적 ×4 비교는 실제 저조도·흐림 복원과 구분한다.
- 제출은 기존 50장의 결과로 진행한다. v0.4 후보를 독립 평가할 때는 방법과 판정 기준을 먼저 고정한 뒤 56장으로 새 세션을 연다.
- 과거 Screw 정상 학습 320장 기준선 0.984218의 seed 11을 원 실행 파일과 반환 해시의 일치로 확인했다.
- 지혁의 기본 24조건 원래 반환 6개를 수신했다. 기존 확장 4조건을 더한 결과표를 정리했다. 24개 기본 조건의 image AUROC를 영상별 점수로 재계산해 모두 맞았다. pooled AU-PRO와 pixel AUROC는 저장값을 옮겼다. 신규 Screw 지도는 주형의 Figure Z 목록과 겹치는 샘플이 없다.
- 남은 제출 작업은 촬영자 확인, 원본을 사용한 사람 판독, 기록된 촬영 시간과 팀 정보 확인, 보고서·포스터에 28조건과 위치 집계 반영, 최종 A0 PDF 확인이다. 같은 Figure Z에 Bicubic bank를 붙이려면 해당 샘플의 지도와 실행 소스를 추가로 받는다. UNO는 실물 시연 선택에 따른다.


## Stage 76 · 포스터 팀 번호와 피드백 반영 범위 (2026-11-20)

포스터 팀 번호는 사용자 확인값 2번이다. 제출은 50장 고정 v0.3과 같은 세션의 개발 결과로 구성한다. 포스터에 Fable 검토를 완료 조건으로 넣지 않는다. 실제 판정은 NG와 위치 일치를 구분한다. 두 Screw 지도는 입력 변화에 따른 이미지 내 점수 분포의 사례로 쓴다. 조회한 반환물에는 원인 실험과 지도에 대응하는 결함 마스크가 없어 질감 때문에 점수가 바뀌었다는 문구를 쓰지 않는다.

지혁 ZIP의 기본 24조건은 집계했다. Figure Z의 샘플은 manipulated_front/020.png다. 새 Screw 지도와 기존 포스터/주형 선정 파일의 샘플 ID가 겹치지 않는다. 동일 사례 RGB 해시와 Bicubic bank 지도 확보는 별도다.

사진 열람용 화면과 블라인드 판독표는 `outputs/phone-original-review-20261120/`에 있다. 촬영자가 실제 조건을 확인하고 사람 판독은 분석 결과를 보지 않은 사람이 기록한다. 원본에 GPS 메타데이터가 들어 있다.


## Stage 77 · 촬영 자세 보정과 사람 판독의 역할 (2026-11-20)

50장 모두 평가 작업에 들어갔다. 참조 2·보정 2·평가 46장으로 구성되고, C2의 고정 운영 경로는 첫 사진 23장과 대체 사진 11장을 확인했다. 사람 판독은 46장 평가 사진의 검사 가능성을 독립적으로 기록하는 절차다. 운용 시에는 장비가 자동 판정하고 해결되지 않은 건을 사람에게 넘긴다. 사람 판독 화면의 세 기준을 구체화했다.

f73bab4의 기존 정렬과 ROI·자세 조건으로 ±2.7° 재시도를 했다. 같은 조명에서도 실패한 8장 중 41·47번 2장이 정렬됐고, 두 장 모두 기존 품질 판정은 RETAKE였다. L1을 L0에 맞춘 표본 4장은 모두 실패했다. 결과는 `outputs/phone-rotation-probe-20261120/`에 보관했다. 같은 세션에서 시도한 개발 결과다.


## Stage 78 · 두 사람의 판독 결과와 불일치 처리 (2026-11-25)

두 사람의 판독표가 원본 50장과 모두 일치한다. 평가용 46장 중 판독 일치 24장, 불일치 22장이다. 잘 보임과 판독 어려움으로 직접 갈린 9장은 모두 첫 L0 사진이고 고정 v0.3에서 품질 PASS다. 두 사람이 잘 보인다고 본 18장의 PASS는 고정 3장, 같은 조명 정렬 개발 17장이다. 두 사람 모두 판독이 어렵다고 본 6장은 두 방법에서 모두 품질 PASS가 아니었다. 사진별 품질 판정과 결함 검사 결과는 분모가 다르다.

판독자·판독 시각·자동 검사 결과 사전 열람 여부는 두 표 모두 미기록이다. 원 판독을 보존하고, 직접 불일치 9장부터 원본을 확인할 수 있도록 표를 만들었다. 촬영 조건 확인 및 실측 시간, 팀 2번의 나머지 포스터 정보, 보고서 및 A0 제출본 갱신은 남아 있다. 결과는 `outputs/phone-human-ratings-20261125/`에 있다.


## Stage 79 · 원본 재확인과 실험 종료 (2026-11-25)

사용자가 두 판독자 모두 검사 결과를 사전에 보지 않았다고 확인했다. 제공 화면은 원본 확대를 안내했으나 실제 배율은 미기록이다. 원 판독 일치 24/46, 불일치 22/46을 보존했다. 촬영 순서 5·13번은 잘 보임, 11·15·19·23번은 판독 어려움으로 사후 반영했다. 7·17번은 개인 편차, 9번은 별도 판단 없음으로 보류했다. 잠정 분포는 잘 보임 20장, 어려움 10장, 보류 16장이다. 잠정 어려움 10장 중 양쪽 품질 변형 PASS가 각각 4장이다.

추가 실험을 중단하고 현재 수신 결과로 제출 작업본을 만들었다. 팀 2번 A0 1쪽 PPTX/PDF와 4쪽 DOCX/PDF(제목은 기존 포스터 문구)다. 저자, 지도교수, 소속, 확정 제목은 입력 대기다. 재확인 자료는 `outputs/phone-human-ratings-20261125/판독_재확인_46장.csv`에 있다.


## Stage 80 · 대체 촬영과 복원 근거 구분 (2026-11-25)

첫 사진의 계획 조건이 저조도 또는 흐림인 10쌍을 원 판독 자료와 연결했다. 두 사람 모두 잘 보임은 첫 사진 0장, 대체 사진 5장이며, 둘 다 어려움에서 둘 다 잘 보임으로 바뀐 쌍은 2개다. 고정 C2는 10건 모두 보류, 같은 조명 정렬 개발 변형은 OK 3·NG 6·보류 1이다. 새로 찍은 대체 사진의 근거이며 영상 복원과 구분한다. 첫 사진에 적용한 C1 Bicubic 및 SwinIR의 최종 판정은 23건 모두 직접 검사 C0와 같았다. 별도의 선명 L1 사진 ×4 왕복 위치 일치 결과는 원본 4/9, Bicubic·SwinIR 각 9/9이며 복원본의 사람 판독 결과는 없다. 새 실험 없이 제출 작업본과 집계표를 갱신했다.


## Stage 81 · GitHub 통합과 제출 보고서 그림 보강 (2026-11-25)

공개 GitHub의 main을 3d10197로 갱신했다. 앞서 흩어져 있던 실험·분석 커밋의 원본은 main 조상으로 보존했고, 임시 전달·초안 브랜치 6개는 열린 PR이 없고 백업과 커밋이 일치하는 것을 확인해 정리했다. 27→21개다. 기존 로컬 실험 작업 경로를 보존한 채 로컬 main을 같은 SHA로 맞췄다.

최종 결과의 접근 경로는 results/README.md, 그림은 results/FIGURES.md, 판단 흐름은 results/RESEARCH_HISTORY.md다. 파일명은 공개용 촬영 순번으로 정리하고 라벨 및 EXIF를 가린 실물 74장, 라이선스를 별도로 표시한 MVTec·VisA 확대 비교, 매칭된 수치표를 넣었다. 이전 보고서의 그림이 부족하다는 피드백을 반영해 21개를 보강했고, PDF 25쪽과 24개 그림을 렌더링해 구조를 확인했다. 기존 데이터·실험 자체를 변경하거나 새로 실행하는 단계는 아니다.
