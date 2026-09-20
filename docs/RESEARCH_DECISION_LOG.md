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
대표 strong-failure와 geometry-failure sample을 비교한다.

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
