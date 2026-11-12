# 스마트폰 첫 9장 촬영 안내 (사용자용)

추가 구매는 필요 없다. 준비물은 스마트폰, 책상 조명, 책 몇 권, 종이 한 장, 펜이다.

## 1. 고정

1. 책상 위에 종이를 깔고 대상을 놓는다. 대상은 노출 기판의 커넥터·핀·납땜부 또는 USB-A 커넥터다.
2. 대상의 네 모서리 위치를 펜으로 표시한다. 대상을 다시 놓을 때 같은 자리에 둘 수 있게 하기 위해서다.
3. 책을 쌓아 폰을 고정한다. 대상이 화면의 절반 이상을 채우고 초점이 맞는 거리로 맞춘다. 촬영하는 동안 폰과 대상은 움직이지 않는다.
4. 카메라 앱 설정을 확인한다.
   - 필터는 끈다.
   - 가능하면 화면을 길게 눌러 초점과 노출을 고정한다(AE/AF 잠금).
   - HDR이 자동인지 꺼져 있는지 적어 둔다. 모르면 "미확인"으로 적는다.
5. **사진 형식을 JPEG로 맞춘다.** 이 도구는 HEIC/HEIF와 RAW(DNG)를 읽지 못한다. 그런 파일은 "읽을 수 없음(RETAKE)"으로 처리된다.
   - 아이폰: 설정 → 카메라 → 포맷 → "높은 호환성".
   - 갤럭시: 카메라 설정에서 "고효율 사진(HEIF)"을 끈다.
6. 위치 정보(GPS) 저장은 꺼 둔다. 켜져 있어도 도구는 좌표를 출력하지 않고 "있음/없음"만 기록한다.

## 2. 촬영 (3조명 × 3반복 = 9장)

- 방 조명은 매번 같은 상태로 둔다. 책상 조명만 **왼쪽 → 정면 → 오른쪽**으로 옮긴다.
- 각 위치에서 셔터를 3번 누른다. 셔터는 화면 터치 대신 볼륨 버튼이나 타이머를 쓰면 흔들림이 적다.
- 조명과 대상 사이 거리는 대략 같게 유지한다. 실제 거리를 cm로 재면 `notes`에 적는다. lux는 쓰지 않는다.
- 플래시는 이 9장이 끝난 다음 별도 조건(`flash`)으로 3장을 찍는다. 선택 사항이다.
- 사진이 흐리거나 과노출이면 지우지 말고 그대로 둔다. 같은 칸을 다시 찍고 `attempt=2`로 적는다.

## 3. 기록표 `capture_sheet.csv`

`docs/phone_capture_sheet_template.csv`를 복사해서 사진과 같은 폴더에 둔다. 한 줄에 사진 한 장을 적는다.

| 열 | 예시 | 설명 |
| --- | --- | --- |
| file | IMG_0001.jpg | 폰에서 옮긴 원본 파일 이름 그대로 |
| part_id | usbA01 | 같은 물체는 항상 같은 ID |
| session_id | S1 | 같은 날, 같은 배치로 찍은 묶음 |
| recipe_id | left / front / right / flash | 조명 조건 |
| repeat_id | 1, 2, 3 | 반복 번호 |
| attempt | 1 | 재촬영이면 2, 3 … |
| label_status | unknown | normal / real_defect / simulated_defect / unknown |
| reference | 1 | front 1번 한 장에만 1 |
| roi_x0..roi_y1 | 0.2,0.2,0.8,0.8 | 검사할 영역(비율). 비워 두면 전체 화면 |
| ae_af_locked, hdr, notes | yes / 미확인 / … | 확인한 대로 |

## 4. 전달

- 원본 사진(JPEG, 편집하지 않은 것)과 `capture_sheet.csv`를 한 폴더에 넣는다.
- 그 폴더를 GPU PC의 `outputs/phone-captures/<날짜>/`에 복사한다. Git이나 공개 채널에는 올리지 않는다.
- 결함 여부는 확인된 것만 적는다. 일부러 만든 결함은 `simulated_defect`로 적는다.

## 5. 실행 명령 (GPU PC)

```powershell
$py = '.venv\Scripts\python.exe'
& $py ..\juhyung-phone-20261112\scripts\run_phone_capture_audit.py --input outputs\phone-captures\<날짜> --output outputs\phone-audit-<날짜> --kind real
```

결과는 출력 폴더의 `report.html`을 브라우저로 열어서 본다. 이 파일에는 사진 축소본이 들어 있어 비공개다. CSV/JSON에는 사진이 없다.
