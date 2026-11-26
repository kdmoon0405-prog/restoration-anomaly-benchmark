# 팀 2 보고서와 포스터 작성 인계

[현재 Word 보고서](../results/report/team-2-report.docx)와 [A0 포스터 작업본](../results/report/team-2-a0-draft.pptx)을 기준으로 작성한다. 보고서는 시작 가설, 실험 설계와 변경 이유, 결과와 한계까지 이어서 설명한다. [결과 자료실](../results/README.md)과 [그림 모음](../results/FIGURES.md)에서 표와 그림을 찾는다.

## 기록을 읽는 순서

1. [연구 과정과 실험별 근거](../results/RESEARCH_HISTORY.md)를 먼저 읽어 초기 파일럿, 복원 모델 선택, bank 실험, VisA PCB 운영점, 실물 촬영과 판독이 어떤 질문으로 이어졌는지 확인한다.
2. 판단의 출처가 더 필요하면 [연구 결정 기록](RESEARCH_EVOLUTION.md)과 [진행 기록](../PROGRESS.md)을 읽는다. 두 문서는 시점별 이력을 담고 있어 결론에는 최종 검증 자료와 같은 수치를 사용한다.
3. [고해상도 실물 사진과 원 판독표](../results/local-evidence/README.md)에서 본문에 넣을 실물 비교를 고른다. 기존 [복원·이상 지도](../results/FIGURES.md)는 같은 위치 패널과 조건별 사례 모음에 있다.
4. 원고의 그림 설명에 데이터·사례 번호, 처리를 한 입력, 결과를 고른 기준을 쓴다. 표에는 분모를 표기한다. 데이터에 포함된 그림은 [그림 출처와 라이선스](../results/FIGURE_LICENSES.md)를 따른다.

## 본문에서 다룰 비교

| 질문 | 자료 | 쓸 때 확인할 값 |
|---|---|---|
| 복원 화질이 좋아질 때 결함 검사도 좋아졌는가 | [복원 모델 실험](../analysis/restoration_objective_full/FULL_RESULT.md) · [같은 위치 확대](../results/figures/mvtec/README.md) | PSNR과 결함 지표의 방향, 개선과 악화의 개별 사례, 조건별 표본 |
| 정상 특징 bank가 바뀌면 검사가 얼마나 달라졌는가 | [28조건](../results/data/bank/bank-domain-28.csv) · [Bicubic bank 확장](../analysis/jihyuk_bicubic_bank_return_20261117/REVIEW.md) | 입력을 고정했는지 bank를 고정했는지, pooled AU-PRO와 영상별 평균, seed |
| 운영점에서 무엇을 놓쳤는가 | [VisA PCB 본실험](../analysis/pcb_full_cohort/RESULT.md) · [테스트 200장 판정 전환](../results/data/visa/decision-changes.csv) | 정상 100장과 이상 100장, 각 처리의 보정 임계값, 미검 29→46건과 오검 3→1건 |
| 실물 촬영에선 어떤 입력이 쓰였는가 | [고정 v0.3](../results/data/phone/station_fixed_v03/station_result.csv) · [같은 조명 정렬 개발](../results/data/phone/station_dev_samelight/station_result.csv) · [원 판독과 사진](../results/local-evidence/README.md) | 평가 46장과 판정 23건, 정렬 성공 15→38장, 작은 이물의 9건 NG 및 최대 이상 영역 위치 일치 3건 |
| 사람이 더 잘 볼 수 있었는가 | [판독 결과 46장](../results/data/phone/human-readability-46.csv) · [첫 사진과 대체 사진 10쌍](../results/data/phone/capture-pairs-10.csv) | 두 판독자 모두 잘 보임 0→5장. 이 비교의 각 쌍은 별도 촬영이다. 같은 원본 복원본을 두 사람이 별도로 판독한 기록은 없다. |

실물은 같은 기판 한 개의 모사 이물 검사다. 같은 조명 정렬 결과는 평가 사진을 보고 고른 개발 방법이다. 실제 촬영·조명 전환 시간과 양산 라인 성능은 측정 기록이 확보되지 않았다. 합성 ×4 왕복, 실물 열화의 대체 촬영, 기준 입력에 대한 사람 판독의 차이를 캡션과 표에서 유지한다. 제출 표지에는 팀에서 확정한 저자, 지도교수, 소속과 제목을 넣는다.
