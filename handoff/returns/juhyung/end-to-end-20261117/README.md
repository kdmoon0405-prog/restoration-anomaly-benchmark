# 주형 반환 — 사진 결과, 정상 bank 비교, 포스터 갱신 (2026-11-17)

- **실행 모델:** Claude Opus 5.5 (`claude-opus-5-5`). 요청 모델 Fable 5.2가 아니다.
- **공개 범위:** 코드 commit과 scalar 결과만 담았다. 사진, 확대 그림 PNG, GT, raw 배열, bank, HTML 갤러리, PPTX/PDF, 비공개 결정 노트는 비공개 ZIP으로 직접 전달한다.
- **경로 표기:** 이 폴더의 CSV/JSON에 있던 로컬 절대경로 앞부분을 `<workspace>/`로 바꿨다. 그래서 `bank/consumer/analysis_manifest.json`의 표 해시는 원본(비공개 묶음) 기준이다.

## 담긴 것

| 파일 | 내용 |
| --- | --- |
| `FINAL_REPORT.md` | §0에 이번 갱신(정상 bank 결과, 재실행과 지혁 결과의 관계, 문구 정정) |
| `FINAL_REVIEW.md`, `DEMO_GUIDE.md` | 원근 2종, 시간 조건, HTML 첫 줄 정정 |
| `RUN_RECORD_20261117.md` | 소스, 실행, 테스트, 시간 |
| `PROGRESS.md` | 공개 진행 기록 |
| `bank/consumer/` | 주형 재실행 3 run의 CPU consumer 출력 |
| `bank/crosscheck/` | 지혁 확장 수신값과 재실행의 대조, 결과 표 |
| `bank/selected_cases_index.csv` | 선정 6사례의 값·crop·RGB 해시 |
| `gallery_index/` | MVTec 같은 위치 확대 23사례 인덱스와 선정 규칙 |
| `figure_sources.json` | 포스터 그림 9개의 수치 출처 |

## 코드

- `exp/bank-domain-juhyung`: `b94a189`, `2796dc6`, `45c9a65`, `c60dd80`
- `exp/phone-lighting-juhyung`: `87c78ed`, `3632df1`, `10ca115`, `9aa54cd`, `b3dc3c7`, `74dc9fa`
