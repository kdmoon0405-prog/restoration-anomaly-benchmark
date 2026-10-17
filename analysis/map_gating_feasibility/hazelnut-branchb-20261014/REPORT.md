# Branch B map-gating feasibility

별도 Hazelnut 개발자료의 탐색적 후속 분석. 기존 연구 종료 기록과 full110 B/B-uncertain은 변경하지 않았다.

Protocol frozen before evaluation: `2026-10-14T14:47:27.180862+00:00`, SHA256 `eaf84392bb328e9bae58abffde41bfd265626dc4e4c1ec7c2c809065a933f299`. Source/code identities: INPUT_MANIFEST.json; base commit `47422007daf62c7d39385c7ea6f470d92acf15d2`.

| method | pooled_au_pro | pixel_auroc | mean_delta_vs_restored | mean_delta_ci95_low | mean_delta_ci95_high | regressed_count | loss_gt_0.01_vs_restored | normal_common_threshold_exceed_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| degraded_only | 0.817486365 | 0.984044170 | -0.012289987 | -0.021750942 | -0.003843422 | 40 | 19 | 0.000000000 |
| restored_only | 0.841262986 | 0.985050794 | 0.000000000 | 0.000000000 | 0.000000000 | 0 | 0 | 0.006757713 |
| mean_0.5_0.5 | 0.833354121 | 0.985360020 | -0.002483998 | -0.006630858 | 0.001131081 | 34 | 8 | 0.000875917 |
| max | 0.840552370 | 0.985290223 | -0.000108850 | -0.000539500 | 0.000332941 | 36 | 0 | 0.006757713 |
| candidate_1 | 0.841242157 | 0.985252784 | -0.000018427 | -0.000389416 | 0.000392190 | 16 | 0 | 0.006757713 |
| candidate_2 | 0.841258566 | 0.985192744 | -0.000115514 | -0.000411486 | 0.000138634 | 15 | 0 | 0.006757713 |

선택 후보: `None`. 판정: 음성 feasibility: 두 primary anchor를 모두 넘는 후보 없음; 추가 탐색 없이 종료.

All four saved anchor arrays/evaluations/summary passed; metric differences: `{'degraded_only': {'passed': True, 'max_abs_metric_difference': 0.0}, 'restored_only': {'passed': True, 'max_abs_metric_difference': 0.0}, 'mean_0.5_0.5': {'passed': True, 'max_abs_metric_difference': 0.0}, 'max': {'passed': True, 'max_abs_metric_difference': 0.0}}`.

CI는 70장 anomaly의 restored 대비 mean paired per-image delta에만 적용한다. Pooled AU-PRO의 CI가 아니다. Normal per-image AU-PRO는 빈칸이다.

Candidate image scores는 restored_only와 동일하다. Image AUROC 개선을 주장하지 않는다. Calibration metadata만 있으며 실제 정상 calibration predictions는 이 source run에 없다. Candidate F1/고정 FPR은 계산하지 않았다. 정상 test threshold 초과는 공통 restored threshold의 진단이며 새 후보의 calibrated FPR이 아니다.

CPU fusion 함수 두 후보 공동 처리: 20 repeats, mean 0.240249 s, median 0.242190 s, min 0.201784 s, max 0.264769 s. 검증/할당 포함, 읽기·metric·NPZ 저장 제외. 모델 추론 절감이나 전체 FPS가 아니다.

표시 사례는 사후 설명용 극값이며 population estimate가 아니다: `['hazelnut/test/crack/016.png', 'hazelnut/test/crack/001.png']`. 4 maps share one scale per sample. Raw candidate NPZ: `outputs/map-gating-feasibility/hazelnut-branchb-20261014`; source files never overwritten.

두 고정 후보 이외 weight/threshold/dilation/smoothing/feature/FFT 탐색은 하지 않았다. 이 결과는 이미지 복원, feature preservation 또는 결함 삭제 방어 mechanism의 입증이 아니다. GT는 evaluation에만 사용했다.

다음 검토는 독립 category 한 개의 frozen protocol, 별도 FAISS/backbone timing 측정, read-only 결과 탐색 데모로 제한한다. 새 실행은 이번 작업에 포함하지 않는다.
