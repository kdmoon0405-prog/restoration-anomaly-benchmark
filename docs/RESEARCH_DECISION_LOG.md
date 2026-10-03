# Research decision log

Date: 2026-09-20

이 문서는 단순 실행 기록이 아니라, 연구 질문이 어떤 실험과 관찰을 거쳐 현재 형태로 바뀌었는지를 남긴다. 각 단계는 **가설 → 실험 → 관찰 → 해석 → 다음 결정** 순서로 기록한다.

## 0. 출발점: 화질 개선이 downstream 검사에도 항상 좋은가?

### 가설
Super-Resolution / Image Restoration은 PSNR·SSIM 같은 화질 지표를 개선하더라도, 결함 texture를 정상적인 pattern 쪽으로 복원하거나 smoothing하여 anomaly evidence를 약화시킬 수 있다.

### 실험 원칙
- restoration quality와 anomaly detection 성능을 분리해서 측정한다.
- PSNR/SSIM/LPIPS를 downstream metric의 대체물로 사용하지 않는다.
- anomaly detector는 normal train image만 사용한다.
- test label/mask는 threshold, checkpoint, preprocessing 선택에 사용하지 않는다.
- MVTec AD에서는 AUROC/AU-PRO를 primary metric으로 사용하고, F1은 별도 normal calibration이 있을 때만 계산한다.

### 결정
단순 SR benchmark가 아니라 다음 paired pipeline을 만든다.

```text
original -> degradation -> detector
original -> degradation -> restoration -> detector
```

---

## 1. 재현 가능한 실험 프레임워크 구축

### 목표
큰 실험을 먼저 돌리지 않고, CPU에서도 전체 데이터 흐름과 metric 계산이 재현되는지 검증한다.

### 구현
- deterministic degradations
- MVTec AD / MVTec AD 2 / VisA adapters
- PSNR / SSIM / optional LPIPS
- Image AUROC / Pixel AUROC / AU-PRO@0.3
- validation-derived F1 only
- CSV / JSON(L) output
- bounded experiment matrix
- smoke test + pytest

### 관찰
framework와 metric/evaluation 경로가 동작함을 확인했다.

### 결정
모델 수를 늘리지 않고 real-data pilot으로 넘어간다.

---

## 2. Bottle 소규모 Anomalib pilot

### 실험
- MVTec AD bottle
- Anomalib PatchCore
- official SwinIR-S x2
- 168 normal fit / 41 normal calibration / 4 balanced test

### 결과
SwinIR-S x2 minus Bicubic x2:
- PSNR: +0.8185 dB
- SSIM: +0.00629
- Pixel AUROC: -0.000071
- AU-PRO: -0.000203

### 해석
4장의 balanced subset은 연구 결론을 내리기에는 너무 작다. 이 단계는 실제 모델과 metric pipeline이 연결되는지 확인하는 engineering smoke test로만 사용한다.

### 결정
기존 팀원이 사용했던 PatchCore 설정을 먼저 정확히 재현한다.

---

## 3. 기존 PatchCore Colab의 설정 확인 및 공식 구현 재현

### 확인된 설정
기존 notebook은 Amazon 공식 PatchCore implementation을 사용하고 있었다.

- backbone: WideResNet50
- feature layers: layer2 + layer3
- pretrain embedding: 1024
- target embedding: 1024
- patch size: 3
- sampler: IdentitySampler
- preprocessing: Resize(256) -> CenterCrop(224)

공식 PatchCore source는 commit
`fcaa92f124fb1ad74a7acf56726decd4b27cbcad`
로 고정했다.

### SR 비교 규약
```text
canonical clean 224
      ↓
bicubic downsample 56
      ├─ bicubic x4 -> 224
      └─ SwinIR-S x4 -> 224
```

GT mask는 동일한 공간 변환을 적용하되 resize에는 nearest-neighbor를 사용한다.

### 결정
기존 notebook의 숫자를 그대로 신뢰하지 않고, 동일 detector 설정으로 새 reproducible run을 만든다.

---

## 4. Hazelnut 소규모 pilot

### 실험
- 16 normal train
- 4 held-out normal calibration
- 20 balanced test
- seed 11

### 결과
Bicubic x4:
- PSNR 37.2866
- SSIM 0.93454
- Image AUROC 0.9900
- Pixel AUROC 0.985777
- AU-PRO 0.687230

SwinIR-S x4:
- PSNR 39.5309
- SSIM 0.95545
- Image AUROC 1.0000
- Pixel AUROC 0.986678
- AU-PRO 0.691774

SwinIR minus Bicubic:
- ΔPSNR +2.2443 dB
- ΔSSIM +0.02091
- ΔPixel AUROC +0.000901
- ΔAU-PRO +0.004544

### 해석
초기 가설과 달리 pilot에서는 SR이 quality와 localization을 함께 개선했다. 작은 subset이므로 'SR은 안전하다' 또는 'SR은 anomaly를 지운다' 어느 쪽도 결론내리지 않는다.

### 결정
전체 normal memory bank와 full test로 확대한다.

---

## 5. Hazelnut full-memory 및 Branch A full evaluation

### Full-memory pilot
- 391 normal train
- IdentitySampler
- exact FAISS memory bank
- 10 balanced test

SwinIR minus Bicubic:
- ΔPSNR +2.0830 dB
- ΔSSIM +0.02177
- ΔPixel AUROC +0.005708
- ΔAU-PRO +0.036695

### Branch A full result
- 391 train
- 110 test
- F1 없음: independent normal calibration이 없으므로 의도적으로 비워둠

Clean:
- Image AUROC 1.000000
- Pixel AUROC 0.986880
- AU-PRO 0.875000

Bicubic x4:
- PSNR 36.4654
- SSIM 0.93173
- Image AUROC 0.998214
- Pixel AUROC 0.983933
- AU-PRO 0.818910

SwinIR-S x4:
- PSNR 38.7789
- SSIM 0.95422
- Image AUROC 0.998214
- Pixel AUROC 0.985092
- AU-PRO 0.843461

SwinIR minus Bicubic:
- ΔPSNR +2.3135 dB
- ΔSSIM +0.02249
- ΔImage AUROC 0
- ΔPixel AUROC +0.001159
- ΔAU-PRO +0.024551

### 해석
이 조건에서는 "SR이 평균 anomaly localization을 악화시킨다"는 단순 가설이 지지되지 않았다. 오히려 quality와 localization이 함께 개선됐다.

### 연구 질문 수정
기존 질문:
> SR이 anomaly detection을 떨어뜨리는가?

수정된 질문:
> **SR은 언제 defect information을 복원하고, 언제 anomaly evidence를 약화시키는가?**

---

## 6. Branch B: degraded/restored score fusion 시도

### 목적
Bicubic과 SwinIR prediction이 상보적이라면 단순 fusion으로 더 나은 downstream 성능을 얻을 수 있는지 확인한다.

### leakage control
- 313 normal fit
- 78 normal calibration
- 110 test
- seed 11
- robust median/IQR normalization은 calibration normal만 사용
- F1 threshold도 calibration normal에서만 결정
- test label은 fitting/normalization/threshold 선택에 사용하지 않음

### 비교
- degraded_only
- restored_only
- mean_0.5_0.5
- max

### 결과 요약
restored_only:
- Image AUROC 0.998571
- Pixel AUROC 0.985051
- AU-PRO 0.841263

mean_0.5_0.5:
- Image AUROC 1.000000
- Pixel AUROC 0.985360
- AU-PRO 0.833354

max:
- Image AUROC 0.999643
- Pixel AUROC 0.985290
- AU-PRO 0.840552

### 해석
fixed fusion은 image-level metric을 약간 올렸지만 localization에서 restored-only를 확실히 넘지 못했다.

### 결정
Hazelnut test를 보며 fusion weight를 추가 탐색하지 않는다. GPU 시간과 test leakage 위험에 비해 정보 가치가 낮다.

---

## 7. Hazelnut defect-level post-hoc analysis

Branch A의 110-test prediction을 재사용했다. 70장의 anomalous image에 대해 GT mask는 **inference 이후 post-hoc evaluation에만** 사용했다.

### 계산 항목
- defect ROI mean / max anomaly score
- background mean
- ROI-background gap / ratio
- defect area / area ratio
- per-image Pixel AUROC
- per-image AU-PRO
- Bicubic vs SwinIR anomaly-map correlation

### 관찰 1: raw defect score 감소와 localization failure는 같은 의미가 아니다
- ROI mean 감소: 49/70 = 70.0%
- ROI-background gap 감소: 25/70 = 35.7%
- per-image Pixel AUROC 감소: 30/70 = 42.9%
- per-image AU-PRO 감소: 30/70 = 42.9%

평균:
- mean ΔROI mean = -0.180891
- mean ΔROI-background gap = +0.178580
- mean Δper-image Pixel AUROC = +0.001745
- mean Δper-image AU-PRO = +0.012914

따라서 SwinIR 후 defect의 absolute anomaly score가 낮아지는 경우가 많아도 background score가 더 크게 낮아져 separability가 오히려 좋아질 수 있다. **raw ROI score 감소만으로 restoration failure를 정의하면 안 된다.**

### Bootstrap
5000회 paired image-resampling, seed 2026.

Image AUROC delta:
- estimate 0.0
- 95% CI [-0.005482, +0.005778]

Mean per-anomaly Pixel AUROC delta:
- estimate +0.001745
- 95% CI [+0.000147, +0.003495]

Mean per-anomaly AU-PRO delta:
- estimate +0.012914
- 95% CI [+0.004487, +0.022950]

Mean defect ROI delta:
- estimate -0.180891
- 95% CI [-0.277204, -0.082284]

주의: Pixel AUROC/AU-PRO CI는 pooled-pixel dataset-level bootstrap이 아니라 **per-anomalous-image paired metric delta의 image-resampling bootstrap**이다.

### Strong failure candidate
Historical terminology from the first exploratory pass follows. Section 11 supersedes it: these 14 images are the **suppression subtype** of 30 localization regressions, not the primary failure definition. The `strong failure` label is deprecated.

현재 탐색적 정의:
```text
ΔROI-background gap < 0
AND
Δper-image AU-PRO < 0
```

결과:
- 14/70 = 20.0%

Defect type별:
- crack: 4/18
- cut: 1/17
- hole: 7/18
- print: 2/17

hole에서 strong failure가 상대적으로 많이 관찰됐지만, 표본이 작고 사후 탐색이므로 확정적 일반화는 하지 않는다.

### Defect-size 가설
- Spearman(defect area ratio, ΔROI mean) = -0.0318
- strong failure median area ratio = 0.02286
- others median area ratio = 0.02091

hole:
- failure median 0.01559
- non-failure median 0.01646

### 해석
현재 Hazelnut에서는 **'작은 defect일수록 SR failure가 크다'는 가설이 지지되지 않는다.** size 축은 우선순위를 낮추고 defect morphology/type 및 spatial map 변화 쪽으로 이동한다.

### 중요한 반례
일부 sample은 ROI score/gap 또는 Pixel AUROC가 좋아졌는데 AU-PRO가 악화됐다. 이는 단순 score suppression이 아니라 anomaly-map의 spatial coverage/geometry가 변했을 가능성을 시사한다.

예: `hazelnut/test/crack/013.png`
- ΔROI mean +0.108560
- ΔROI-background gap +0.423456
- ΔPixel AUROC +0.004057
- ΔAU-PRO -0.076146

### Oracle 분석 주의
초기 oracle은 anomalous image에서 GT ROI raw mean이 더 큰 branch를 고르는 방식이었다. 이 정의에서는 AU-PRO가 restored-only보다 낮아졌다.

따라서 **ROI raw mean 기반 선택은 localization upper bound가 아니다.** 이 결과는 최종 oracle으로 사용하지 않는다. 다음 버전은 per-image localization metric을 기준으로 한 명시적 post-hoc upper-bound 분석으로 재정의해야 한다.

---

## 8. 현재 연구 가설

현재 가장 적절한 질문은 다음이다.

> **Super-resolution improves average anomaly localization, but under which defect morphologies does it suppress or spatially distort anomaly evidence despite the aggregate gain?**

한국어:
> **초해상도 복원은 평균 이상탐지 성능을 향상시키더라도, 어떤 결함 형태에서 anomaly evidence 또는 anomaly-map의 공간 구조를 훼손하는가?**

현재 관찰은 "SR이 항상 결함을 지운다"도, "SR이 항상 downstream에 좋다"도 지지하지 않는다.

---

## 9. 다음 실험

### 우선순위 1: qualitative failure inspection
당시 `strong-failure`라고 부른 suppression 후보와 geometry 후보를 비교한다. 현재 명칭과 해석은 11절과 14~16절을 따른다.

패널:
- Clean
- Bicubic x4
- SwinIR-S x4
- GT mask
- Bicubic anomaly map
- SwinIR anomaly map

### 우선순위 2: feature-space cause analysis
전체 70장을 다시 계산하지 않고, 선정된 failure/success sample만 PatchCore NN distance를 계산한다.

```text
D_defect = E[d(f_i, M_normal) | i in defect]
D_background = E[d(f_i, M_normal) | i outside defect]
```

판단:
- SwinIR 후 D_defect가 감소하면 defect feature가 normal memory bank에 가까워졌다는 feature-space suppression evidence.
- feature distance는 유지되는데 AU-PRO만 낮아지면 spatial localization/geometry 변화 가능성.

위 문장은 실행 전 가설이었다. 16절 결과 이후에는 어느 조건도 인과 증거로 해석하지 않고, suppression을 map-score pattern으로만 부른다.

### 우선순위 3: cross-category stress test
- screw: local/tiny defect stress
- grid: repeated-texture stress
- capsule: method/metric/analysis를 고정한 뒤 **unseen final validation**으로 유지

---

## 10. AI-assisted implementation workflow

이 프로젝트에서 ChatGPT/Codex는 장시간 실험의 대체물이 아니라 repository-aware implementation과 분석 보조로 사용한다.

```text
Research question / experiment decision
        ↓
GitHub code + prior result inspection
        ↓
ChatGPT / Codex
- minimal code modification
- analysis script
- tests / smoke test
- exact run command
        ↓
Local PowerShell / GPU machine
- actual long-running experiment
        ↓
NPZ / CSV / JSON / figures
        ↓
post-hoc analysis
        ↓
hypothesis update / next experiment
```

원칙:
- 긴 full experiment는 로컬 CPU/GPU에서 실행한다.
- Codex 사용량을 장시간 process waiting에 쓰지 않는다.
- 기존 코드를 먼저 재사용한다.
- 결과가 가설과 다르면 가설을 수정한다.
- test 결과를 보며 weight/checkpoint/threshold를 튜닝하지 않는다.

이 문서는 결과가 추가될 때마다 위의 '가설 → 실험 → 관찰 → 해석 → 결정' 형식으로 업데이트한다.

---

## 11. Hazelnut post-hoc 기준 정리 (2026-09-21)

### 관찰
Branch A는 pooled AU-PRO를 개선했지만 70장 중 30장에서 per-image AU-PRO가 감소했다. 이전 `gap↓ AND AU-PRO↓` 14장은 전체 localization regression이 아니라 그 하위 유형이다. ROI-mean 기반 oracle도 localization 상한이 아니었다.

저장된 prediction으로 다시 계산한 AU-PRO screening oracle은 Bicubic 30장, SwinIR 40장을 선택했고, per-image AU-PRO 평균은 복원 단독 0.903398에서 oracle 0.907052로 +0.003655 올랐다. 하지만 해당 branch의 전체 맵을 선택해 pooled AU-PRO를 다시 계산하면 0.843461에서 0.840458로 -0.003003 떨어졌다. 따라서 이미지별 선택 가능성이 pooled 성능 개선으로 바로 이어진다고 볼 수 없다.

### 결정
[`EXPERIMENT_PROTOCOL_V0.2.md`](EXPERIMENT_PROTOCOL_V0.2.md)에 현재 규칙을 기록했다. `delta_per_image_aupro < 0`를 localization regression으로, 그중 ROI-background gap이 감소하면 suppression-type, 그렇지 않으면 geometry candidate로 분류한다. 크기 임계값은 사후에 추가하지 않는다. Hazelnut은 development/exploration이며 이 분류의 독립 검증 자료가 아니다.

새 oracle은 per-image metric별 두-branch screening 평균과, AU-PRO 기준 whole-map 선택 뒤 pooled 지표를 재계산한 결과를 분리한다. 이 선택은 GT-assisted이고 배포 불가능하며, pooled 성능의 보장된 상한도 아니다. 기존 `preliminary_roi_mean_oracle.json`은 역사적 기록으로만 남긴다.

가중치 탐색은 지금 실행하지 않는다. 위의 작은 per-image headroom과 음수인 pooled 선택 결과만으로는 GPU 시간을 쓸 우선순위가 높지 않다. 다른 근거로 상보성이 확인될 때에는 Hazelnut을 명시적인 development set으로 취급해 `alpha ∈ {0, 0.25, 0.5, 0.75, 1}`의 후속 coarse search를 검토할 수 있다. 그 경우 Hazelnut에서 선택된 점수를 독립 테스트 성능으로 발표하지 않고, 방법을 고정한 뒤 untouched Capsule에서 한 번 확인한다. Screw는 다음 stress 후보, Grid는 정보 가치가 분명할 때만 추가한다.

---

## 12. Branch B 저장 예측의 5점 가중치 분석 결정 (2026-09-21, 실행 전)

### 이전 결정과 변경 이유
위 11절의 가중치 탐색 보류는 새 GPU inference를 들일 정보 가치가 낮다는 판단이었다. 그러나 Branch B의 정규화된 `degraded_only`/`restored_only` 예측은 이미 저장돼 있다. Oracle headroom이 작더라도 `alpha=0.5` 하나만으로 global scalar fusion을 기각하기에는 부족하고, 저장 예측만으로 5점을 평가하는 계산 비용은 낮다. 따라서 이 분석을 feasibility ablation으로 수행한다. 과거 결정을 지우거나 Hazelnut을 독립 테스트로 다시 부르지 않는다.

### 실행 전 고정
`alpha`는 Bicubic/degraded 가중치이며 grid는 `{0.00, 0.25, 0.50, 0.75, 1.00}`이다. 선택 지표는 pooled AU-PRO@0.3 하나다(동률이면 작은 alpha). Pixel/Image AUROC와 결함별 regression은 보조·위험 지표이며 alpha 선택에 쓰지 않는다. F1·새 임계값·fine search·adaptive gating은 이번 단계에서 제외한다. `alpha=0/0.5/1`은 저장된 기존 방법과 수치 검증한다. 이 결정을 [`EXPERIMENT_PROTOCOL_V0.2.md`](EXPERIMENT_PROTOCOL_V0.2.md)의 amendment에도 기록했다.

---

## 13. Branch B 5점 분석 결과 (2026-09-21, 실행 후)

저장된 110장 예측만으로 계산했다. alpha 0/0.25/0.5/0.75/1의 pooled AU-PRO@0.3은 각각 0.841263/0.838005/0.833354/0.826236/0.817486이다. 고정된 단일 선택 지표에 따라 alpha=0(복원 단독)이 가장 높다. 최선의 내부 점 0.25도 복원 단독보다 0.003258 낮다. alpha=0.5의 Pixel AUROC 0.985360은 alpha=0의 0.985051보다 높지만 선택 지표를 바꾸지 않는다.

Bicubic 대비 per-image localization regression은 alpha 0/0.25/0.5/0.75/1에서 각각 30/27/24/18/0장이다. alpha=1의 0장은 구조적 결과다. 0/0.5/1 anchor는 저장된 prediction 및 기존 evaluation과 정확히 일치했다. 현재 Hazelnut 결과만으로 finer scalar search를 진행하지 않는다. 다른 개발 자료에서 내부 coarse weight가 양 끝점 모두보다 pooled AU-PRO를 높이고 결함별 손실도 수용 가능한 경우에만 탐색 범위와 선택 규칙을 새로 고정한다. Capsule은 여전히 untouched final validation이다.

---

## 14. 9개 고정 사례의 PatchCore feature-distance 확인 규칙 (2026-09-21, 실행 전)

Hazelnut의 map-level taxonomy가 feature-normal 거리 변화와 대응하는지 확인한다. 사후 결과에서 고른 탐색용 사례라는 한계를 명시하고 geometry `crack/013`, `crack/015`, `print/005`, suppression `crack/001`, `crack/017`, `hole/014`, 성공 대조 `crack/006`, `cut/003`, `hole/006`의 9개를 고정한다. 두 branch 모두 동일한 Branch A 391장 normal memory bank를 사용한다. 새 fit이나 전체 test feature 재추론은 하지 않는다.

공식 PatchCore embedding의 실제 feature grid에서 FAISS 최근접 **squared-L2** 거리를 측정한다. GT는 224×224 canonical mask를 grid cell별 면적 점유율로 줄여 연속 가중치로 사용한다. 결함 가중 평균 거리, 배경 가중 평균 거리, 두 값의 차이와 SwinIR−Bicubic 변화를 기록한다. 이 grid-cell 매핑은 backbone patch의 receptive field를 정확히 대변하지 않는다는 제한을 함께 적는다. 저장 anomaly map의 AU-PRO/Pixel AUROC/ROI-background gap을 연결하되, pixel map 통계를 NN 거리라고 부르지 않는다. n=3 수준 subtype 비교는 기술 통계이며 인과·유의성 주장은 하지 않는다. 결과가 맞지 않으면 suppression 명칭을 map-score pattern으로만 유지한다.

---

## 15. 고정 9개 사례의 시각 검토 (2026-09-21, 실행 후)

가설: map-gap suppression과 geometry candidate가 이상 맵에서 서로 다른 양상으로 보이는가. 조건: 사전 지정한 각 3장, 동일한 sample 내 두 맵의 공통 색 범위, 저장된 Branch A 이상 맵과 GT를 재사용했다. RGB 패널용 SwinIR 복원만 9장 다시 계산했고 PatchCore 추론은 하지 않았다. 결과는 `analysis/hazelnut/qualitative_cases/`의 9개 패널과 CSV/README에 남겼다.

`crack/013`은 SwinIR 후 ROI-background gap +0.423456, Pixel AUROC +0.004057이지만 AU-PRO -0.076146이며 가는 GT branch가 맵에서 퍼져 보인다. `crack/001`의 복원 맵에서는 결함 hotspot이 약해지고 gap/AU-PRO 모두 하락했다. 반례인 `hole/006`은 gap -0.370210에도 AU-PRO +0.139957이다. 해석: taxonomy는 서로 다른 map-level 패턴을 기술하는 데 유용하지만, 이 그림만으로 feature suppression이나 공간 왜곡의 원인을 확정할 수 없다. 다음 결정은 고정 9장에서 동일한 PatchCore normal bank에 대한 patch NN 거리를 확인한 뒤 내린다.

---

## 16. 동일 메모리뱅크 NN 거리 결과와 가설 수정 (2026-09-21, 실행 후)

가설: suppression 후보에서는 SR 뒤 결함 patch가 normal memory에 가까워지고 feature separation이 줄어들며, geometry 후보에서는 separation이 유지될 것이다. 조건: 고정 9장, Branch A의 검증된 391장 FAISS bank 하나, PatchCore 공식 embedding의 28×28 grid, GT cell 점유율 가중 평균. 기준은 Bicubic x4, 변화량은 SwinIR−Bicubic이고 단위는 FAISS squared-L2다. 저장 맵과 재계산 맵 18개가 모두 일치했다.

결과: suppression 3장의 평균 ΔD_defect -0.6123, 평균 Δfeature gap -0.2491; geometry 후보 3장은 +0.0044/+0.3506; 성공 대조 3장은 +0.1345/+0.4580이다. 그러나 두 값이 함께 감소한 사례는 suppression 2/3, geometry 0/3, control 1/3이었다. `crack/017`은 feature gap이 +0.00346으로 거의 유지됐고, 성공한 `hole/006`은 feature gap -0.35296이었다. 배경 거리도 세 그룹에서 모두 평균 약 0.3~0.4 감소했다.

해석/결정: 선택된 사례에서는 geometry 후보 3장의 feature gap 증가와 AU-PRO 감소가 공간 coverage 문제와 일치하지만, suppression 후보와 control이 완전히 분리되지 않는다. “SR이 결함 feature를 지웠다”는 인과 주장은 하지 않는다. suppression은 **map-score suppression pattern**이라는 기술적 이름으로 유지한다. n=3씩의 사후 선정 사례이므로 유의성이나 전체 Hazelnut 일반화를 주장하지 않는다. 추가 Hazelnut 사례·임계값을 결과에 맞춰 고르지 않고, 사전 고정한 Screw 전체 카테고리에서 taxonomy의 재현성을 확인한다.

---

## 17. Screw cross-category stress 사전 고정 (2026-09-21, 실행 전)

Hazelnut에서 고른 결함 사례와 taxonomy가 다른 형태에서도 나타나는지 확인한다. Screw 전체 정상 학습 320장과 전체 테스트 160장을 사용하며 seed 11, 기존 Branch A와 동일한 Amazon PatchCore pinned commit, WideResNet50 layer2+layer3, 1024/1024, patch size 3, IdentitySampler, 256 resize→224 crop, 정확한 FAISS normal bank를 고정한다. 224→56 Bicubic x4 저해상도, Bicubic x4와 동일 SwinIR-S x4 체크포인트 비교를 유지한다. GT는 동일 spatial transform/nearest-neighbor다. Dataset primary metric은 pooled AU-PRO@0.3(기존 200 thresholds), secondary는 Pixel/Image AUROC와 PSNR/SSIM이다. 회귀는 per-image AU-PRO delta<0, map-gap 부호로 suppression/geometry 후보를 나눈다. 전체 결함 유형을 보고하고 사후 사례 선택으로 결론을 바꾸지 않는다.

Screw test label로 fusion weight, F1 threshold, 체크포인트, 전처리, taxonomy를 조정하지 않는다. 독립 정상 calibration이 없으므로 F1은 비워둔다. Scratch로 맞출 새 가중치나 adaptive gating은 없다. 로컬에는 Screw 데이터와 SR 체크포인트가 있지만 CUDA가 없어 full run이 길고 Screw PatchCore bank도 아직 없다. GPU 장비에서 같은 알고리즘을 실행할 수 있도록 device 옵션만 최소 추가하고, 실행 명령/산출물을 고정한 뒤 결과는 별도로 기록한다. Capsule은 최종 규칙이 고정되기 전까지 열지 않는다.

Branch A runner에는 기존 기본값을 유지하는 `--device cpu`와 명시적 `auto/cuda`만 추가했다. CUDA는 PatchCore feature extraction과 SwinIR에만 쓰고 exact FAISS는 CPU에 둔다. resolved device는 결과에 기록하며 model spec은 바꾸지 않는다. 현재 로컬 CUDA가 없으므로 Screw full run은 실행하지 않았다.

---

## 18. SurgClean 확장 보류와 최소 pilot 범위 (2026-09-21)

로컬 `data/external/`에는 MVTec AD와 VisA만 있고 SurgClean은 없다. 데이터 구조·공식 split·checkpoint를 확인할 수 없어 결과 생성이나 adapter 구현을 시작하지 않는다. 향후 entry gate가 충족되면 Desmoke 한 task, 공식 severity 두 단계, 해당 task의 공식 모델 하나로만 시작한다. 인접 clean frame이 unaligned라는 전제에서 고정된 정합/공식 평가 절차 없이 pixelwise PSNR/SSIM을 주 결론으로 쓰지 않는다. downstream label이 없으면 feature 보존을 task 성능이라고 부르지 않는다. 구체적인 정지 조건과 산출물은 `docs/SURGCLEAN_EXTENSION_PLAN.md`에 기록했다. MVTec/Screw 연구축보다 우선하지 않는다.

---

## 19. Screw 결과 전 cross-category 분석 규칙 고정 (2026-09-21)

Screw 결과가 존재하거나 확인되기 전에 Hazelnut의 taxonomy와 사례 선택 규칙을 generic cross-category analyzer에 고정했다. 이 결정 시점에는 Screw inference를 실행하지 않았고 Screw 수치도 생성하지 않았다.

---

## 20. Screw cross-category 결과 (2026-09-22, artifact 수령 후)

가설: 고정된 x4 Branch A 조건에서 Hazelnut의 평균 localization 개선과 image별 regression이 Screw에서도 함께 나타날 수 있다. 조건: CUDA에서 생성된 320 normal train / 160 test(41 normal, 119 anomalous), seed 11, calibration/F1 없음, 고정 PatchCore 설정과 SwinIR-S x4 체크포인트다. 기존 generic analyzer를 그대로 사용했고 이 CPU PC에서는 inference를 실행하지 않았다.

기준과 지표: Bicubic x4가 기준이며 pooled AU-PRO@0.3이 primary다. Pixel/Image AUROC와 PSNR/SSIM은 secondary다. image별 AU-PRO regression과 suppression/geometry 분류에는 Screw 결과 전에 고정한 규칙을 적용했다.

결과: SwinIR-Bicubic은 PSNR +2.437479 dB, SSIM +0.016426, Image AUROC +0.198606, Pixel AUROC +0.019490, pooled AU-PRO +0.055000이다. anomalous image 119장 중 23장에서 per-image AU-PRO가 감소했다. 23장 모두 suppression pattern이며 geometry candidate는 0장이다. 나머지 96장은 improvement/tie다. Screw 안에서는 regression이 `thread_side` 12/23장, `thread_top` 8/23장에 집중됐지만 결함 유형 일반화로 사용하지 않는다.

해석과 한계: 평균 localization 개선과 sample-level regression의 공존은 Hazelnut과 Screw 모두에서 관찰됐다. subtype 구성은 Hazelnut의 suppression 14 / geometry 16과 달리 Screw는 suppression 23 / geometry 0이다. 이 결과만으로 feature evidence 감소가 Screw regression의 원인이라고 할 수 없다. 두 category만으로 SwinIR이 anomaly detection을 일반적으로 개선한다고 주장하지 않는다.

결정: 모델, threshold, taxonomy, fusion weight, selected case를 바꾸지 않는다. 다음 확인은 고정된 Screw 6개 사례(suppression 3, success control 3)의 NN-distance 분석 하나다. 수령한 ZIP에는 checksum-bound 320-normal FAISS bank가 없으므로 GPU PC에서 원래 bank를 전달받은 뒤 실행한다. Capsule은 계속 untouched로 둔다.

---

## 21. Screw selected-case NN-distance 결과 (2026-09-23, 실행 후)

고정된 suppression 3장과 success control 3장만 동일한 320-normal bank로 분석했다. 입력 tensor를 resolved CUDA device로 이동한 것 외에 preprocessing, PatchCore, CPU exact FAISS, 28x28 GT occupancy, metric, case selection은 바꾸지 않았다. 저장 map과 재계산 map의 12개 비교는 모두 최대 절대 오차 0.0이다.

suppression 3장의 평균 ΔD_defect/ΔD_background/Δfeature gap은 -1.824677/-0.565741/-1.258936이고 세 장 모두 ΔD_defect<0 및 Δfeature gap<0이다. success control 3장은 -0.292801/-0.620176/+0.327375이며 같은 joint-negative pattern은 0/3이다. 따라서 selected Screw suppression-pattern cases are consistent with relative defect-feature normalization이라고 제한해 해석한다. n=3씩의 사후 선정 사례이므로 인과적 또는 모집단 수준 결론을 주장하지 않는다. 추가 threshold나 사례를 만들지 않고 Capsule은 untouched로 유지한다.

---

## 22. Restoration-objective pilot rules frozen before inference (2026-09-23)

The primary endpoint comparison is official `RRDB_PSNR_x4` versus `RRDB_ESRGAN_x4`; Bicubic and SwinIR-S are context baselines. Both RRDB endpoints use the same 23-block x4 architecture, but the official records document DF2K for the PSNR checkpoint and DF2K+OST for the ESRGAN checkpoint. The study therefore reports an endpoint comparison, not a causal loss-only effect.

For this new pilot only, replace the historical Pillow downsampling with BasicSR's pinned MATLAB-compatible bicubic implementation. Feed the exact same 56x56 RGB input to every learned restorer and keep historical Branch A unchanged. Freeze a 25-image Hazelnut development manifest by lexical first-five selection in normal/crack/cut/hole/print before inference. Reuse the exact 391-normal PatchCore bank; no fit, fusion, threshold, F1, interpolation, new detector, or test-label tuning is allowed.

Proceed to full Hazelnut only if the stored 25-image outputs show an actual quality/detection, regression-composition, or repeatable qualitative endpoint difference. Do not create a post-hoc cutoff. If the endpoints are nearly indistinguishable, stop instead of adding models. Real-ESRNet/Real-ESRGAN is deferred to a separate realistic-degradation study. Capsule remains untouched.

---

## 23. Frozen 25-image restoration-endpoint pilot result (2026-09-29)

질문: 공식 RRDB의 PSNR 지향 endpoint와 perceptual/GAN 지향 endpoint가 동일한 x4 LR 입력에서 화질과 anomaly localization의 trade-off를 다르게 보이는가? `95d097799c10135a982dbddf91f97b71e3ca29e6`에서 고정한 Hazelnut 25장 manifest, BasicSR bicubic, 391-normal PatchCore bank, 지표, taxonomy를 바꾸지 않고 전달된 CUDA 결과를 검증했다. 이 단계에서 새 추론이나 튜닝은 하지 않았다.

저장된 summary의 RRDB-ESRGAN minus RRDB-PSNR은 PSNR `-2.622296262852899 dB`, SSIM `-0.03448956157055605`, LPIPS `-0.04259542234241963`, Pixel AUROC `+0.0005923647012515687`, pooled AU-PRO@0.3 `+0.005095647801611869`이다. Image AUROC는 양쪽 모두 1.0이다. 20장 anomaly의 Bicubic 대비 per-image AU-PRO regression은 RRDB-PSNR 8장(3 suppression/5 geometry), RRDB-ESRGAN 5장(4/1)이었고, 직접 endpoint 쌍에서는 ESRGAN 11장, PSNR 9장이 우세했다. 원본 ZIP·NPZ·CSV의 구조와 해시 및 모델/메모리뱅크 provenance는 `analysis/restoration_objective_pilot/`에 기록했다.

결정: 기존 stop/go 규칙에서 요구한 fidelity/perceptual 품질 차이와 downstream 차이의 신호가 있어 full Hazelnut endpoint 평가를 **다음 별도 작업으로 준비**한다. 그러나 25장 결과만으로 한 endpoint의 일반적 우월성을 주장하지 않는다. Full Hazelnut도 이미 탐색에 사용한 development category이므로 독립 최종 검증이 아니다. 두 공식 checkpoint는 objective뿐 아니라 학습 데이터(DF2K 대 DF2K+OST)도 다르다. 따라서 질문을 “Does restoration objective affect defect-evidence preservation?”에서 “Do PSNR-oriented and perceptual/GAN-oriented restoration endpoints trade image quality against anomaly localization differently?”로 좁히고, objective-only 인과 표현을 피한다. Phase C gating, Capsule, 새 degradation/detector, feature NN 후속 분석은 계속 보류한다.
---

## 24. Full Hazelnut endpoint confirmation frozen before inference (2026-09-29)

The frozen 25-image pilot showed a PSNR/SSIM versus LPIPS trade-off and a small, mixed localization difference. That is enough to justify one full 110-image Hazelnut stability check, not a new model search. The question remains a comparison of official PSNR-oriented and perceptual/GAN-oriented *endpoints*, not an objective-only causal claim: the checkpoints also differ in training data. The full manifest, four variants, 391-normal bank, pooled AU-PRO@0.3 primary metric, paired uncertainty plan, and interpretation cases A/B/C are fixed in `docs/RESTORATION_ENDPOINT_FULL_HAZELNUT.md` before inference. No new model family follows automatically from the full result. Phase C, Capsule, new degradation, and new detector stay closed. No full-run result exists yet.

---

## 25. Pre-inference full110 preregistration hardening (2026-09-30)

An external design review occurred after `982cbe0` and before full110 inference. The scientific question, cohort/manifest hash, degradation, four restorers, PatchCore bank, and primary pooled AU-PRO did not change. The dated protocol amendment replaces discretionary A/B/C interpretation with a sign-and-bootstrap-CI rule; separately pre-registers five tau values for regression magnitude, pilot20 overlap and pilot-unseen50 reporting, negative-gap base rates for both regression and non-regression images, and a sorted per-image AU-PRO waterfall. The analysis script was implemented and checked against saved pilot CSVs before any full110 result. Pilot tau counts are post-hoc code-validation sensitivity, not a revision of the prior GO decision. No new model search, Phase C, Capsule, or causal mechanism claim is opened.

---

## 26. Second pre-inference review hardening (2026-10-01, after `607510b`)

A second external adversarial review was conducted before inference. Keep the scientific question, frozen inputs, primary metric, and strict-sign taxonomy. Quantify magnitude/distribution, baseline performance, and quality–localization relationship before supporting taxonomy. Final A/C also require pilot-unseen50 mean direction agreement; B-small is only an inclusive ±0.01 CI magnitude descriptor, not equivalence/non-inferiority. Add baseline terciles 23/23/24 with lexical ties, near-zero delta quantiles/counts, explicit taxonomy four-cell counts, and secondary unseen85 saved-map metrics. Existing tau/paired bootstrap/base rates/figures are reused. Pooled AU-PRO stays a point estimate; the mean-image bootstrap is not its CI. No pooled bootstrap, Wilcoxon, arbitrary ROI metric, or binary correlation cutoff is added.

Historical strict-sign counts must not be presented alone as practical failure rates. Review context suggests many Hazelnut deltas are near zero and Screw has a more substantial negative tail; this is post-hoc context for old results, not preregistered historical evidence. No historical numbers or artifact packages are rewritten here. Baseline/ceiling association is descriptive, not causal. Taxonomy and selected NN-distance results describe maps/consistency; because PatchCore maps derive from NN distances, they do not independently establish a mechanism.

---

## 27. Full110 result recorded and GPU branch closed (2026-10-02)

One full110 execution was run from preregistration commit `fddad881276da120ffcce1362ce062f85ea4759a` on `NVIDIA GeForce MX570 A`, with no change to the cohort, manifest, degradation, four variants, PatchCore bank, primary metric, taxonomy, tau grid, or bootstrap. `fit_performed=false`; `sample_count=110` (40/70); all provenance and output-artifact hashes were independently recomputed and matched. The frozen analysis script was run once, unmodified, against this saved output.

Applying the 2026-10-01 rule to `P=+0.006790` (pooled AU-PRO delta, ESRGAN minus PSNR), `D70=+0.005110`, bootstrap 95% CI `[-0.000907, +0.013954]`, and `D50=+0.005062`: all three point estimates are positive, but `CI.lower` is not `>0`, so the agreement-with-excluded-zero condition for case A is not met. The result is case **B**, and because the CI is not fully inside `[-0.01, +0.01]` it is **B-uncertain**, not B-small. Quality-trade-off reproduction holds (`mean ΔPSNR<0 AND mean ΔLPIPS<0`). Pilot20 overlap reproduced exactly; pilot-unseen50 and the secondary pilot-unseen85 saved-map evaluation agree in direction with the full result. Neither is used to redefine A/B/C. No objective-only causal claim is made, since the two official checkpoints differ in training data as well as objective; the taxonomy and selected NN-distance diagnostics remain map-level/consistency evidence, not a proven feature-space mechanism; Capsule was not opened and no untouched-category generalization claim is made.

Per the frozen stop rule, one valid full110 execution closes this restoration-endpoint GPU branch for every outcome. No further endpoint, Real-ESRGAN, network interpolation, additional NN-distance case, Phase C/adaptive gating, Capsule, new degradation/detector, Screw rerun, or SurgClean work follows from this result. Remaining permitted work is limited to verifying the saved result, confirming figures/tables, writing up the result for the thesis, and provenance/Git housekeeping.

Runner changes are provenance only (environment/argv, output hashes, wall time). One valid full110 closes the GPU experiment branch regardless of A/B/C. No additional NN cases, endpoints, Capsule, Phase C, or other GPU expansion follows in this thesis; Capsule stays unused and no untouched-category generalization claim is made. Future work requires a separate study. All changes precede any full110 inference/result, and the private review/local evolution note remain excluded from Git.

---

## 28. Completed-study thesis synthesis and runtime prose correction (2026-10-03)

Starting from result commit `2dcac3f2c0c8418e2909641c473cd9498600929e`, compile saved evidence only. Historical Pillow recovery and MATLAB-compatible full110 endpoints remain separate families; historical Clean is not an additional byte-proven endpoint. The 10-row master table, claim/evidence matrix, figure index, and limitations prioritize magnitude/distribution, baseline association, and quality–localization relationships. Historical tau counts are explicitly post-hoc; full110 tau, taxonomy, bootstrap, case B/B-uncertain, metrics, hashes, provenance, and derived analysis are unchanged. Pilot20 overlap is numerical agreement within tolerance (maximum difference about `3e-8`), not bitwise identity. The full110 raw NPZ is not present in this checkout; local verification compares tracked records, not newly recomputed full predictions.

Correct only the approved timing-comparison paragraph in `EXECUTION_RECORD.md`: full/pilot same-scope timed stages are `3283.923/342.224 s ≈ 9.596×`, versus image-count `4.4×` and per-image stage-cost `2.181×`. The cause of the higher per-image cost is not established. Wall-clock/stage `10.413×` is not scaling evidence. Preserve all experimental artifacts. One CPU plot reads the six saved historical summary rows; no research experiment or inference runs. The experimental phase remains closed. Private Stage 13 stays local-only and excluded from Git.
