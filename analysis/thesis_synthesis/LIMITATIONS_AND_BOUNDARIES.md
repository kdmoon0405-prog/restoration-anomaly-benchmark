# Limitations and boundaries

- **Acquisition scope:** Canonical image에 synthetic x4 bicubic resolution loss를 적용했다. Real-camera blur/noise/compression이나 산업 취득 환경의 성능은 검증하지 않았다.
- **Two kernels:** Historical recovery는 Pillow, endpoint study는 BasicSR MATLAB-compatible bicubic이다. 같은 이름의 Bicubic 숫자를 cross-family subtraction에 사용하지 않는다. Historical Clean은 endpoint의 byte-proven 다섯 번째 method가 아니다.
- **Detector scope:** Amazon PatchCore WideResNet50와 fixed feature/FAISS 설정만 평가했다. 새로운 detector나 detector 개선법을 제안하지 않았다.
- **Bank uncertainty:** Hazelnut 391-normal bank와 Screw 320-normal bank는 category-specific이다. 각 paired 비교 안에서는 bank가 고정됐으며 다중 seed/bank 재학습에 따른 불확실성은 추정하지 않았다. Branch B의 313/78 bank/calibration도 별도다.
- **Data reuse:** Hazelnut은 질문·taxonomy·feasibility 선택에 사용한 development category다. Full110은 독립 validation이 아니라 within-category stability check다. Pilot25와 full110은 overlap하므로 independent repetitions가 아니다.
- **Cross-category scope:** Screw는 결과 전에 정한 stress category다. 두 category만으로 industrial/object-level universal generalization을 주장하지 않는다.
- **Untouched validation:** Capsule은 의도적으로 사용하지 않았다. Untouched final category의 generalization evidence가 없다.
- **Endpoint confounding:** 공식 RRDB checkpoint는 objective뿐 아니라 training data도 DF2K와 DF2K+OST로 다르다. Loss-only 인과 차이를 분리하지 못한다.
- **Uncertainty estimand:** Pooled AU-PRO는 point estimate다. Paired bootstrap CI는 mean anomalous-image delta의 uncertainty이며 pooled CI나 hardware/seed uncertainty가 아니다. Case B는 equivalence/non-inferiority 판정이 아니다.
- **Magnitude:** Strict-sign regression과 practical failure를 동일시하지 않는다. Frozen tau/±0.01은 descriptive sensitivity이며 검증된 산업 허용오차가 아니다. Historical magnitude 집계는 post-hoc이고 full110 sensitivity는 preregistered다.
- **Baseline dependence:** Ceiling/baseline association은 descriptive다. Delta에 baseline이 포함되는 수학적 coupling과 bounded AU-PRO도 있으므로 해당 연관으로 regression-to-the-mean causality나 defect mechanism을 확정할 수 없다.
- **Quality relationship:** 세 model의 per-image Spearman과 네 method의 aggregate ordering은 서로 다른 관측이다. PSNR/SSIM/LPIPS는 여기서 측정한 reconstruction/perceptual 특성이며 그 자체가 inspection reliability 검증은 아니다. 범용 metric 무효 주장도 하지 않는다.
- **Taxonomy:** GT-assisted post-inference anomaly-map description이다. Negative-gap base rate가 non-regression에도 있으므로 suppression/geometry를 mechanism classifier로 쓰지 않는다.
- **Selected NN:** Subtype별 n=3의 사후 선정 사례다. Grid-cell GT occupancy가 receptive-field membership을 완전히 표현하지 못한다. Map은 NN distances에서 생성되므로 NN/map 대응은 독립 mechanism 증거가 아니다.
- **Fusion:** 고정 global scalar grid의 development negative ablation만 평가했다. 모든 fusion/gating 방법의 불가능성을 입증한 것이 아니다. Test outcome에 따라 fine tuning을 다시 열지 않는다.
- **Artifact access:** Full110 수치는 tracked result/derived artifact와 execution record를 대조했다. 원본 NPZ/RGB는 이 checkout에 없어 현재 세션에서 독립 checksum/array 검증을 반복하지 않았다. 실행 머신에서의 검증 기록과 로컬 확인을 구분한다.
- **Runtime:** Full/pilot의 동일 timed-stage 범위만 비교할 수 있다. Full wall-clock과 pilot stage 시간을 섞은 비율은 scaling 증거가 아니다. 이미지당 stage cost 증가의 원인은 현재 기록으로 확정하지 않았다.

## Scope control

Frozen 질문에 대해 평균 회복, sample delta magnitude/distribution, category/baseline context, quality association, endpoint uncertainty까지 보고할 근거가 확보됐다. One valid full110 이후 모든 A/B/C outcome에서 GPU branch를 닫는 사전 규칙을 따랐다. Favorable 결과를 얻기 위한 model/category/subset 확장은 하지 않는다.

추가 endpoint, Real-ESRGAN, interpolation, NN mechanism follow-up, Phase C/gating, Capsule, 새 degradation/detector, Screw/Hazelnut rerun, SurgClean은 이 연구에서 종료된 방향이다. 남은 작업은 논문·발표 작성과 저장 evidence 검토이며 새로운 연구축 구현이 아니다.
