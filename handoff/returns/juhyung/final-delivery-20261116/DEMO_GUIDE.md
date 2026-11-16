# 시연 가이드 — 스마트폰 검사 시제품

- 모든 명령은 GPU checkout(`restoration-anomaly-benchmark`) 폴더에서 PowerShell로 실행한다.
- 코드는 옆 폴더 `..\juhyung-phone-20261112` (`exp/phone-lighting-juhyung@7b868a3`)에 있다.
- 출력 폴더는 매번 새 이름을 쓴다. 같은 이름이 있으면 실행이 멈추고 기존 결과는 그대로 남는다.

```powershell
$py  = '.venv\Scripts\python.exe'
$src = '..\juhyung-phone-20261112'
$env:PYTHONPATH = "$src\src"
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
```

## 1. 가장 빠른 시연: 이미 만든 결과 화면 열기

`outputs\final-delivery-20261115\station_run\report.html`을 브라우저로 연다. 실제 사진 24장의 결과다(비공개).

| 화면에서 볼 곳 | 보여 주는 것 |
| --- | --- |
| 맨 위 "Station result" 표 | cycle별 최종 상태, 사진 수, 이유 (운영 경로) |
| "Summary by condition" 표 | C0–C3 비교. 모든 cycle이 분모 |
| "Cycles"의 카드 | 정렬된 사진(노란 상자 = 관찰 영역), 차이 지도, 빨간 상자 = NG 위치, 조건별 판정 |

**대표 cycle (이 순서로 보여 주면 흐름이 이어진다)**

| cycle | 내용 | 운영 경로의 결과 |
| --- | --- | --- |
| `normal-3` | 정상 기판 | 품질 PASS → 검사 OK, 사진 1장 |
| `foreign-1` | 모사 이물(분홍 조각) | 품질 PASS → 차이 덩어리 165 px → NG, 사진 1장. 위치가 빨간 상자로 표시된다 |
| `lowlight-3` | 첫 입력이 저조도 | 품질 REVIEW(어두움) → 대체 조명 L1 → PASS → OK, 사진 2장 |
| `blur-1` | 초점 흐림 | 품질 REVIEW(선명도) → 대체 사진 없음 → REVIEW |
| `tilt-1` | 카메라 기울임(약 14°) | 품질 REVIEW(recipe 자세 밖) → REVIEW |
| `background-2` | 흰 배경(정상) | 품질 PASS → 차이 28 px → NG. 정상 기판의 오검 사례다 |

## 2. 사진 없이 전체 흐름 실행 (합성 입력, 약 5분)

```powershell
& $py -m pytest -q "$src\tests\test_phone_station.py" -p no:cacheprovider
```

합성 기판 영상으로 폴더 입력부터 보고서까지 실행하고, 오류 상황(잘못된 recipe, 누락 파일, 기존 출력 폴더)과 UNO fake 재생까지 확인한다.

## 3. 실제 사진으로 다시 실행 (약 3–7분)

```powershell
& $py "$src\scripts\run_phone_station_compare.py" `
  --input outputs\phone-captures\20261115 `
  --recipe outputs\phone-station-20261115-inputs\recipe.json `
  --plan outputs\phone-station-20261115-inputs\plan.json `
  --output "outputs\phone-station-demo-$tag" `
  --kind real --assets-root . --device cuda
```

- 끝나면 `station_result.csv`와 `report.html`의 경로가 출력된다.
- `--assets-root`와 `--device`를 빼면 복원 조건(C1)만 PENDING으로 남고 나머지는 그대로 실행된다. GPU가 필요 없다.
- 전원을 연결하고 실행한다. 배터리 동작에서는 같은 작업이 약 3배 걸렸다(147초 → 423초).

## 4. 새 촬영 세션 실행 (기록표만으로)

1. `$src\docs\PHONE_EVAL_SESSION_PLAN_V1.md`대로 찍는다.
2. `$src\docs\phone_eval_capture_sheet_template.csv`를 사진 폴더에 `capture_sheet.csv`로 복사하고 `file` 열을 채운다.
3. recipe의 `anchor`를 새 L0 참조 사진 이름으로 바꾼 사본을 만든다.

```powershell
& $py "$src\scripts\run_phone_station_compare.py" --input outputs\phone-captures\<새 폴더> `
  --recipe <새 recipe.json> --output "outputs\phone-station-eval-$tag" --kind real --assets-root . --device cuda
```

`--plan`을 생략하면 기록표의 `station_role` / `cycle_id` / `light` 열에서 실행 계획을 만든다.

## 5. UNO 상태 표시

- **지금 가능한 것 (하드웨어 없음):**

```powershell
& $py "$src\scripts\replay_phone_station_uno.py" --events outputs\final-delivery-20261115\station_run\station_events.jsonl --fake
```

  상태 변화마다 1바이트를 보낸다. 출력에 `physical_hardware_tested: false`가 찍힌다.

- **UNO가 있을 때 (이 프로젝트에서 시험하지 않았다):**
  1. Arduino IDE로 `$src\docs\examples\phone_station_status_led\phone_station_status_led.ino`를 올린다. 내장 LED(13번 핀)만 쓴다. 배선은 USB 케이블뿐이다.
  2. 시연 PC에 pyserial을 설치한다(이 환경에는 없다).
  3. `--fake` 대신 `--port COM<번호> --delay 1.5`로 실행한다.

  | 바이트 | 상태 | LED |
  | --- | --- | --- |
  | R | READY | 꺼짐 |
  | B | BUSY | 켜짐 |
  | T | 대체 촬영 요청 | 느린 점멸 |
  | O / N | OK / NG | 긴 한 번 / 짧게 세 번 |
  | V | REVIEW | 빠른 점멸 |
  | E | ERROR | 계속 켜짐 |

## 6. 오류 복구

| 증상 | 원인 | 조치 |
| --- | --- | --- |
| `STATION RUN STOPPED: FileExistsError` | 출력 폴더가 이미 있다 | 새 폴더 이름을 쓴다. 기존 결과는 지워지지 않았다 |
| `STATION RUN STOPPED: ValueError: recipe …` | recipe의 ROI, anchor, 허용 범위가 잘못됐다 | 메시지의 항목을 고친다 |
| `… plan names files not in the sheet` | 실행 계획의 파일 이름이 기록표에 없다 | 기록표의 `file` 열을 확인한다 |
| `capture_sheet.csv missing` | 사진 폴더에 기록표가 없다 | 양식을 복사해 채운다 |
| 사진이 `unreadable`로 나온다 | HEIC/RAW 형식 | 폰을 JPEG로 설정해 다시 찍는다 |
| cycle이 `alignment_below_threshold`로 REVIEW | 자세·배율이 크게 다르다 | recipe 구도로 다시 찍는다 |
| 실행이 평소보다 몇 배 느리다 | 배터리 동작 | 전원을 연결한다 |

## 7. 화면 캡처

`outputs\final-delivery-20261115\demo\station_report_top.png` (Edge headless, 1500 px 폭, 비공개).
