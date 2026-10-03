# 부분 복원 feasibility 시험

기존 Hazelnut Branch B에서 검사기가 의심한 픽셀을 Bicubic 입력으로 유지하면 전체 SwinIR 복원보다 localization 손실을 줄이는지 확인한다. 기존 졸업논문 측정 연구와 구분되는 소규모 탐색이다.

## 고정 조건

- 기준 커밋: `01a03840730836a76b92eca37b22fc8713b979b8`.
- 검사기: 기존 Hazelnut 313장 bank. 정상 78장의 기존 보정값을 사용하며 재학습·재보정하지 않는다.
- 표본: good/crack/cut/hole/print의 `000.png`, `001.png`, 총 10장. 정상 2장, 결함 8장. 파일명으로 선택했으며 이전 악화 수치로 선택하지 않았다.
- 보호 마스크: 저장된 normalized degraded-only anomaly map이 기존 99% pixel threshold `1.321750563871199`보다 큰 픽셀. 영역 확장과 경계 보정은 없다. GT는 평가에만 사용한다.
- 열화: 기존 Pillow resize 256 / center crop 224 후 Bicubic `224 → 56 → 224`. BasicSR MATLAB-compatible endpoint family와 수치를 혼합하지 않는다.
- 복원: 기존 SwinIR-S x4 checkpoint, tile 56, overlap 0.

`B`는 Bicubic RGB, `R`은 전체 SwinIR RGB, `M`은 보호할 픽셀에서 1인 마스크다. 부분 복원은 `M*B + (1-M)*R`, 균일 혼합은 `alpha*B + (1-alpha)*R`, `alpha = mean(M)`이다. 균일 혼합은 반올림한 uint8 RGB로 평가한다. 네 조건 모두 같은 검사기로 실제 RGB를 다시 추론한다. anomaly map을 합성해서 대체하지 않는다.

## 실행

저장소 루트에서 기존 `.venv`를 사용한다. 새 dependency를 설치하지 않았다. CPU 실행이다.

```powershell
rtk proxy .\.venv\Scripts\python.exe -X utf8 scripts\run_partial_restoration_feasibility.py --self-check
rtk proxy .\.venv\Scripts\python.exe -X utf8 scripts\run_partial_restoration_feasibility.py --prepare-only
rtk proxy .\.venv\Scripts\python.exe -X utf8 scripts\run_partial_restoration_feasibility.py --smoke
rtk proxy .\.venv\Scripts\python.exe -X utf8 scripts\run_partial_restoration_feasibility.py
```

`PROTOCOL.json`은 추론 전에 생성하며 이미 있으면 덮어쓰지 않는다. 실행 시 bank, checkpoint, 기존 결과, split, 평가 코드, 표본과 GT 파일의 checksum을 비교한다. 원본 파일이 달라지면 중단한다. 이미 고정된 이 저장소에서는 `--prepare-only`를 다시 실행할 필요가 없다.

한 장 점검은 미리 고정한 `crack/000.png`다. 보호율 0%와 100%에서 부분 복원과 균일 혼합이 각각 전체 복원과 입력으로 일치하는 검사도 수행한다. 실제 Bicubic/전체 복원 map을 기존 저장된 map과 비교하며 normalized map의 최대 절대 차이가 `1e-5`를 넘으면 중단한다.

기본 출력은 `outputs/partial-restoration-feasibility/smoke`, `outputs/partial-restoration-feasibility/pilot10`이다. 재실행할 때는 `--output-dir`로 새로운 빈 폴더를 지정한다. 기존 출력은 덮어쓰지 않는다.

## 출력과 해석

- `per_image.csv`: 10장 × 네 조건. 정상 영상의 per-image AU-PRO와 그 차이는 비워 둔다.
- `summary.csv`, `results.json`: pooled AU-PRO, 결함 8장의 평균 per-image AU-PRO, 손실 크기, 전체 복원 이득을 잃은 정도, 부분 복원과 균일 혼합의 차이.
- 조건별 prediction NPZ와 보호 마스크 NPZ, 실제 조건별 RGB PNG.
- `figures/`: clean reference, 입력, 전체 복원, 보호 영역, 부분 복원, 균일 혼합, GT와 anomaly map. 각 이미지의 네 map에 같은 raw-score 색 범위를 사용한다.

화질은 clean reference에 대한 PSNR/SSIM으로 측정한다. 실험의 보호 선택에는 clean reference와 GT를 사용하지 않는다. 새 두 조건의 정상 보정을 하지 않았으므로 F1이나 운영 임계값의 안전성을 주장하지 않는다. 정상 2장은 pooled 평가의 정상 픽셀과 화질 비교에 포함한다.

시간은 모델 초기화, 실제 sample wall time, SwinIR, 검사기, RGB 합성으로 구분한다. 조건별 `inference_seconds`에는 부분 복원/균일 혼합의 입력 검사 비용을 포함하지만 보호 마스크 자체는 기존 cache에서 가져온다. RGB 합성 시간은 두 후보를 함께 생성한 시간이다. 반복 측정한 시스템 성능 벤치마크로 해석하지 않는다.

`delta < -0.01`은 손실 크기를 기술하는 값이며 산업 현장의 허용 기준이 아니다. 부분 복원이 전체 복원보다 손실을 줄이더라도 균일 혼합보다 나은지, 다른 이미지의 기존 이득을 잃는지 함께 평가한다. 8장 결과로 안정적인 우월성이나 독립 검증을 주장하지 않는다. 결과에 맞춰 표본·임계값·보호 영역을 변경하지 않는다.
