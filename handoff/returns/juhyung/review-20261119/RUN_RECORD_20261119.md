# 실행 기록 — 2026-11-19 (주형 GPU host)

- **실행 모델:** Claude Opus 5.5 (`claude-opus-5-5`). 요청 모델 Fable 5.2는 연결이 확인되지 않았다(`REVIEW_20261119.md` §0).
- **지시:** `juhyung-fable52-full-review-private-20261118/fable-review-handoff-20261118/PROMPT_FABLE52_FULL_REVIEW_20261118.md`, 사용자 메시지(새 촬영 50장 폴더 참조).
- **원본 ZIP 확인:** `final-delivery-20261117-private.zip` 48,629,145 bytes, SHA-256 `d39461ca…ec58`(패킷 기록과 일치).
- **환경:** Windows 11, `.venv` Python 3.11.2, MX570 A, `PYTHONDONTWRITEBYTECODE=1`.

## 소스 (`exp/phone-lighting-juhyung`)

| commit | 내용 |
| --- | --- |
| `74dc9fa` | 고정 평가 실행 시점(실행기·정책 변경 없음) |
| `3e1a9c6` | `make_phone_eval_cases.py`, `probe_registration_contrast.py`, `run_phone_station_same_light_dev.py`(개발 래퍼), `make_pcb_operating_point_cases.py` |
| `f73bab4` | `make_result_gallery.py` 새 구역(평가 세션, PCB, 없는 근거) |

포스터 생성기(`poster_work/make_figures.py`, `make_poster_spec.py`)는 비공개 묶음 안의 사본을 고쳤다. 공개 `tools/poster_20261116/`은 바꾸지 않았다.

## 실행

| 무엇 | 명령 요지 | 출력 | 결과 |
| --- | --- | --- | --- |
| 입력 준비 | 사진 50장 바이트 복사, 기록표 `file` 열을 촬영 순서로 채움, EXIF·SHA 기록 | `outputs/phone-captures/20261118-eval-v2/` | 원본 폴더는 그대로 |
| recipe | anchor = REF_L0, ROI [0.15, 0.27, 0.68, 0.70] (평가 전 참조 사진으로 정함) | `outputs/phone-station-inputs-20261118/recipe.json` | |
| 고정 평가 | `run_phone_station_compare.py --input … --recipe … --kind real --device cuda` | `outputs/phone-station-eval-20261118` | 00:44–00:49, rc 0 |
| 위치 표시 | 사례별 선명 L0 사진에서 물체 중심(색 성분, 눈으로 확인). 평가 후 | `object_annotations.json` | GT 아님 |
| 위치 근거(고정/개발) | `make_phone_eval_cases.py [--same-light]` | `outputs/phone-eval-cases-20261118-{fixed,samelight}` | 각 30장·15그림 |
| 정렬 probe | `probe_registration_contrast.py` | `outputs/phone-dev-probes-20261119/registration_probe.csv` | anchor 16, CLAHE 13, 같은 조명 41 / 49 |
| 개발 변형 | `run_phone_station_same_light_dev.py` (실행기 무수정, 정렬 참조만 교체) | `outputs/phone-station-dev-samelight-20261119` | 01:10–01:16, rc 0 |
| PCB 운영점 | `make_pcb_operating_point_cases.py` (저장 점수·지도, map 파일 SHA 대조) | `outputs/pcb-operating-point-cases-20261119` | TP/FP 재현 |
| 포스터 그림 | `make_figures.py` (전체 재생성, 그림 N의 물체 덩어리 320 px를 저장값과 대조) | `poster_figures/` | 그림 11개 |
| 포스터 | `make_poster_spec.py`, `build_poster.ps1` | `poster_final.pptx/.pdf` | A0 1쪽, 본문 넘침 없음 |
| 갤러리 | `make_result_gallery.py` | `gallery/index.html` | 이미지 157개 링크 확인, Edge로 §5–7 확인 |

## 시험

| 대상 | 결과 | 로그 |
| --- | --- | --- |
| phone station/capture (`f73bab4`) | 19 passed (111 s) | `logs/pytest_phone_related_f73bab4.txt` |

새 스크립트에는 단위 시험이 없다. 실제 데이터로 실행해 결과 수치를 대조했다. 대조 항목:
- PCB TP/FP가 기존 표와 일치
- 그림 N의 물체 덩어리가 저장값과 일치
- 지도 파일 SHA가 manifest와 일치

전체 pytest는 다시 돌리지 않았다.

## 하지 않은 것

- 새 GPU 모델 추론(PatchCore/bank)
- 지혁 자료 없이 Bicubic bank 지도 생성
- 사람 판독을 AI로 채우기
- 고정 계획서 수정
