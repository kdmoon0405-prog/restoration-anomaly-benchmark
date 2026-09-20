# Hazelnut defect-level analysis

Branch: `exp/hazelnut-analysis`

이 디렉터리는 MVTec AD hazelnut Branch A full run(391 normal train / 110 test)의 저장된 prediction을 이용한 **post-hoc defect-level analysis**를 정리한다. 현재의 분류·선택 기준은 [실험 프로토콜 v0.2](../../docs/EXPERIMENT_PROTOCOL_V0.2.md)에 고정했다. Hazelnut은 이미 살펴본 development category다.

저장된 prediction만으로 표와 oracle을 다시 생성하는 PowerShell 명령(`research_code/`에서 실행):

```powershell
.venv\Scripts\python -X utf8 scripts\analyze_hazelnut_failures.py --run-dir outputs\legacy-patchcore\hazelnut-full391-test110-repro --output-dir analysis\hazelnut --select-cases 10 --render-cases 0
```

그림까지 그릴 때에는 `--render-cases`를 양수로 두고 `--swinir-checkpoint`를 제공해야 한다. 그림의 SwinIR 이미지 재구성은 별도 추론이므로 위 명령에서는 하지 않는다.

## Research question

전체 평균에서는 SwinIR-S x4가 Bicubic x4보다 Pixel AUROC와 AU-PRO를 개선했다. 그러나 개별 anomaly image 또는 특정 defect morphology에서는 anomaly evidence/localization이 악화되는 subset이 존재하는가?

## Current results

70 anomalous test images:

| Measure | SwinIR worse than Bicubic |
|---|---:|
| defect ROI raw mean | 49/70 (70.0%) |
| defect-background gap | 25/70 (35.7%) |
| per-image Pixel AUROC | 30/70 (42.9%) |
| per-image AU-PRO↓: localization regression | 30/70 (42.9%) |
| AU-PRO↓ AND ROI-background gap↓: suppression-type | 14/70 (20.0%) |
| AU-PRO↓ AND ROI-background gap≥0: geometry candidate | 16/70 (22.9%) |

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
- former gap↓ AND AU-PRO↓ subset median area ratio: 0.02286
- other images' median area ratio: 0.02091

현재 Hazelnut에서는 small-defect hypothesis는 지지되지 않는다.

Historical gap↓ AND AU-PRO↓ subset by type (not the primary regression definition):
- crack 4/18
- cut 1/17
- hole 7/18
- print 2/17

hole은 follow-up 대상으로 우선순위가 높지만, 작은 sample의 사후 탐색 결과이므로 일반화하지 않는다.

## Files to commit

작고 해석 가능한 결과는 Git에 남긴다.

- `hazelnut_per_defect.csv`
- `regression_taxonomy.csv`
- `selected_cases.csv` (worst/best ranked by per-image AU-PRO delta)
- `bootstrap_ci.json`
- `oracle_localization_headroom.json`
- `strong_failure_cases.csv` and `preliminary_roi_mean_oracle.json` (historical only)
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

## Oracle interpretation

`preliminary_roi_mean_oracle.json`은 GT ROI raw mean이 큰 branch를 고르는 과거 정의다. 이 선택 기준은 localization quality와 일치하지 않았고 AU-PRO를 실제로 낮췄다. 삭제하거나 새 결과로 덮어쓰지 않는다.

새 `oracle_localization_headroom.json`은 per-image AU-PRO와 Pixel AUROC 각각의 두-branch screening upper bound, 그리고 AU-PRO 기준으로 전체 맵을 선택한 뒤 다시 계산한 pooled 지표를 구분한다. GT-assisted이므로 배포 가능한 선택법이 아니다. Per-image 평균 headroom은 두 branch 사이의 상한이지만, pooled AU-PRO가 복원 단독보다 높아진다는 보장은 없다.

## Next analysis

1. `selected_cases.csv`의 AU-PRO worst/best와 suppression/geometry 후보를 동일 anomaly-map 색상 범위로 시각화한다.
2. 선택한 sample에서만 PatchCore feature-to-normal-memory patch distance를 ROI와 background로 나눠 계산한다.
3. feature-distance 감소와 anomaly-map의 spatial coverage 변화를 구분한다. 그 후 Screw를 사전 고정된 cross-category stress로 검토한다. Grid는 필요한 경우만 추가한다.

전체 70장의 NN-distance를 다시 계산하지 않는다.
