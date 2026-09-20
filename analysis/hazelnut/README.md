# Hazelnut defect-level analysis

Branch: `exp/hazelnut-analysis`

이 디렉터리는 MVTec AD hazelnut Branch A full run(391 normal train / 110 test)의 저장된 prediction을 이용한 **post-hoc defect-level analysis**를 정리한다.

## Research question

전체 평균에서는 SwinIR-S x4가 Bicubic x4보다 Pixel AUROC와 AU-PRO를 개선했다. 그러나 개별 anomaly image 또는 특정 defect morphology에서는 anomaly evidence/localization이 악화되는 subset이 존재하는가?

## Current results

70 anomalous test images:

| Measure | SwinIR worse than Bicubic |
|---|---:|
| defect ROI raw mean | 49/70 (70.0%) |
| defect-background gap | 25/70 (35.7%) |
| per-image Pixel AUROC | 30/70 (42.9%) |
| per-image AU-PRO | 30/70 (42.9%) |
| gap↓ AND AU-PRO↓ strong-failure candidate | 14/70 (20.0%) |

Mean deltas:
- ΔROI mean: -0.180891
- ΔROI-background gap: +0.178580
- Δper-image Pixel AUROC: +0.001745
- Δper-image AU-PRO: +0.012914

5000 paired image bootstrap:
- mean per-anomaly Pixel AUROC Δ 95% CI: [+0.000147, +0.003495]
- mean per-anomaly AU-PRO Δ 95% CI: [+0.004487, +0.022950]
- mean defect ROI Δ 95% CI: [-0.277204, -0.082284]

Defect size:
- Spearman(area ratio, ΔROI mean): -0.0318
- strong-failure median area ratio: 0.02286
- other median area ratio: 0.02091

현재 Hazelnut에서는 small-defect hypothesis는 지지되지 않는다.

Strong failure by type:
- crack 4/18
- cut 1/17
- hole 7/18
- print 2/17

hole은 follow-up 대상으로 우선순위가 높지만, 작은 sample의 사후 탐색 결과이므로 일반화하지 않는다.

## Files to commit

작고 해석 가능한 결과는 Git에 남긴다.

- `hazelnut_per_defect.csv`
- `bootstrap_ci.json`
- `strong_failure_cases.csv`
- 수정된 oracle 결과 및 정의
- `summary.md`
- aggregate scatter/histogram plots
- 선정된 failure/success qualitative figures
- analysis script: `scripts/analyze_hazelnut_failures.py`

## Raw artifact policy

### What are the NPZ files?

예:
- `clean_predictions.npz`
- `bicubic_x4_predictions.npz`
- `swinir_x4_predictions.npz`

이 파일들은 각 test sample의 raw numerical prediction을 압축해 저장한다.

대표 배열:
- `labels`: image-level label
- `scores`: image-level anomaly score
- `masks`: GT pixel mask
- `maps`: full anomaly map

즉 CSV/JSON보다 훨씬 상세한 **재분석용 원시 출력**이다.

### Why not commit all NPZ/anomaly maps to normal Git history?

NPZ가 쓸모없어서가 아니다. 오히려 정확한 post-hoc 재분석에는 매우 유용하다. 다만 regular Git에는 다음 문제가 있다.

- binary file이라 diff/review가 어렵다.
- full-resolution map과 mask가 sample × variant만큼 반복되어 용량이 빠르게 커진다.
- 수정할 때마다 Git history에 binary snapshot이 누적된다.
- dataset-derived output을 repository source history에 섞으면 clone/pull 비용이 계속 증가한다.

현재 repository의 `.gitignore`도 `outputs/*`를 기본적으로 제외한다.

### Recommended storage split

**Git repository**
- code
- config
- run command
- checksums
- small CSV/JSON summaries
- selected plots/failure figures
- decision log

**Artifact storage outside normal Git**
- raw `*_predictions.npz`
- full anomaly-map dump
- PatchCore FAISS memory bank
- model checkpoints
- dataset archive

원시 NPZ는 삭제하지 않는다. 로컬/공용 Drive/별도 artifact storage에 보존하고, 필요하면 Git LFS 또는 release artifact 같은 binary-oriented storage를 사용할 수 있다.

핵심은 **GitHub에는 결론을 재검토할 수 있는 작은 결과와 재생성 recipe를 남기고, raw 대용량 artifact는 별도로 보관하는 것**이다.

## Important caution: preliminary oracle

현재 생성된 `oracle_headroom.json`은 GT ROI raw mean이 큰 branch를 고르는 정의다. 이 선택 기준은 localization quality와 일치하지 않았고 AU-PRO를 실제로 낮췄다.

따라서 이 파일은:
- 현재 분석 과정의 기록으로는 보존 가능
- **final upper-bound result로 인용하면 안 됨**
- 다음 script revision에서 per-image localization metric 기반 explicit post-hoc oracle로 수정

## Next analysis

1. AUPRO regression과 strong-failure sample을 시각화한다.
2. hole을 포함한 representative failure와 success control을 함께 선정한다.
3. 선택한 sample에서만 PatchCore feature-to-normal-memory NN distance를 계산한다.
4. feature suppression과 spatial geometry failure를 분리한다.

전체 70장의 NN-distance를 다시 계산하지 않는다.
