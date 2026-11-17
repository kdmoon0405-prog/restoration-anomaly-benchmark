# 실행 기록 — 2026-11-17 (주형 GPU host)

- **실행 모델:** Claude Opus 5.5 (`claude-opus-5-5`, Claude Code). 지시가 요청한 Fable 5.2가 아니다.
- **지시:** `PROMPT_JUHYUNG_END_TO_END_20261117.md`(zip SHA-256 `6c6d0b14…c0cb`)와 추가 수신 `juhyung-bank-results-followup-private-20261117`.
- **환경:** Windows 11, `.venv` Python 3.11.2, GPU NVIDIA GeForce MX570 A. 프로세스마다 `GIT_LFS_SKIP_SMUDGE=1`, `PYTHONDONTWRITEBYTECODE=1`.
- **`progress_revolution.md`:** 묶음과 저장소 어디에도 없었다. `records/PROGRESS.md`와 `RESEARCH_EVOLUTION_LOCAL*.md`(실패한 시도 포함: 고정 fusion 실패, gap 부호 반례, 전체 화면 축소로 미세 성분 소실)를 읽었다.

## 소스

| worktree / branch | commit | 내용 |
| --- | --- | --- |
| `juhyung-bank-20261117` / `exp/bank-domain-juhyung` | `b94a189` | 지혁 패치 2개 적용(바이트 보존). 기본 run이 기록한 실행 commit |
| 〃 | `2796dc6`, `45c9a65` | CPU consumer 5파일 export(roi_bg_gap은 cell 정규화 지도), 기록된 commit 기본값 |
| 〃 | `c60dd80` | Bicubic bank 확장 runner (**미실행**) |
| `juhyung-phone-20261112` / `exp/phone-lighting-juhyung` | `87c78ed` | 촬영 계획 v2(50장, 두 묶음) |
| 〃 | `3632df1` | MVTec 같은 위치 확대 갤러리, 기판 확대 그림 |
| 〃 | `10ca115` | 스테이션 HTML 첫 줄 v0.3, bank 지도 그림 |
| 〃 | `9aa54cd`, `b3dc3c7`, `74dc9fa` | 결과 갤러리, 선정 사례 그림(SwinIR은 producer 장치에서 재생성해 RGB 해시 확인) |

## 실행

| 무엇 | 출력 | 결과 |
| --- | --- | --- |
| 기본 bank run (`run_bank_domain_study.py`, run-id `bank-domain-juhyung-20261117b`) | `outputs/bank-domain-study/…20261117b/` | Hazelnut s11 COMPLETE(17:09–18:23), Screw s11 COMPLETE(–19:00), Hazelnut s23 COMPLETE(–19:39), Screw s23 원본 bank 후 세션 종료로 정지(`BUILDING`, 보존). 이후 추가 지시로 재개하지 않음 |
| 첫 시도 `bank-domain-juhyung-20261117` | 보존 | 커밋 전 소스로 시작해 직접 중단(`STOPPED_dirty-source`), 결과로 쓰지 않음 |
| export → CPU consumer (`juhyung-handoff…/scripts/analyze_bank_domain_study.py --source-root`) | `bank/juhyung_rerun_export/` | 3 run COMPLETE, source 바이트 대조 통과 |
| 지혁 확장 대조 | `bank/crosscheck/` | Bicubic 입력 화질 270장 비트 일치, SwinIR 최대 0.0015 dB, 원본 bank pooled 차이 ≤0.0004 |
| MVTec 확대 갤러리 | `defect-zoom-gallery/` | 23사례, 열화 입력은 저장 Bicubic을 바이트 단위로 재현해 확인 |
| 선정 6사례 / bank 분류 그림 | `bank/selected_cases/`, `bank/taxonomy_figures/` | 검사 입력 RGB가 producer 해시와 일치(GPU) |
| 결과 갤러리 | `gallery/index.html` | 이미지 73개 링크 확인, Edge headless로 상단·bank 구역 표시 확인 |
| 포스터 | `poster_final.pptx/.pdf` | PowerPoint COM, A0 1쪽, 본문 상자 넘침 없음(템플릿 제목 상자 1개 기존 상태) |

## 테스트

| 대상 | 결과 | 로그 |
| --- | --- | --- |
| phone station/capture (`10ca115` 변경 전후) | 19 passed (553 s, bank run과 동시 실행이라 느림) | `logs/pytest_phone_related_banner_fix.txt` |
| bank producer (`c60dd80`) | 11 passed | `logs/pytest_bank_domain_study_c60dd80.txt` |
| CPU consumer (handoff checkout) | 24 passed | `logs/pytest_cpu_consumer_handoff.txt` |

전체 pytest는 이번에 다시 돌리지 않았다. 새 그림·갤러리 스크립트에는 단위 테스트가 없고 실제 실행 결과로만 확인했다.

## 실행 시간 (MX570 A, 원본+SwinIR bank 2개, 질의 2종)

Hazelnut s11 74분, Screw s11 37분, Hazelnut s23 38분. 첫 run은 같은 시간대의 pytest(9분)와 겹쳤다. 처리량 계산에 쓰지 않는다.

## 쓰지 않은 것

- 시험 GT로 임계값·선택을 정하지 않았다(정상 보정만). 사례 선정은 사후 설명용이다.
- 같은 이미지의 seed 반복(Hazelnut 11/23)을 독립 표본으로 더하지 않았다.
- 원본 이미지·GT·raw 배열·bank·사진은 공개 Git에 넣지 않았다.
