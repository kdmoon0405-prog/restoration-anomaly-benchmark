# 연구 과정과 실험별 근거

산업 검사에서 초해상도가 작은 이상을 보존하는지 확인하고자 했다. 복원 전후를 같은 위치에서 비교하고, 결과가 바뀌면 정상 기준과 검사 임계값까지 대조했다.

| 단계 | 실험과 다음 판단 | 결과 자료 |
|---|---|---|
| 9월 초기 CPU 파일럿 | Bottle과 Hazelnut에서 원본·Bicubic·SwinIR을 비교해 실행과 지표를 검증했다. 작은 test split에서 모델 순위를 일반화하기 어려워 같은 이미지의 실패를 따로 조사했다. | [초기 진행](../PROGRESS.md) · [Hazelnut 분석](../analysis/hazelnut/README.md) |
| 9월 결함별 진단 | Hazelnut의 전체 위치 지표가 오르는 동안 이미지 70장 중 30장에서는 개별 위치 지표가 낮아졌다. 결함 영역과 배경 점수의 상대 변화를 확인했다. Screw도 별도로 검사해 품목에 따른 차이를 비교했다. | [Hazelnut 요약](../analysis/hazelnut/summary.md) · [Screw 대표 사례](../analysis/screw/NN_HANDOFF.md) · [같은 위치 확대](figures/mvtec/README.md) |
| 9월 말~10월 초 복원 모델 | PSNR 중심 RRDB와 지각 품질 중심 RRDB를 동일 저해상도 입력에서 비교했다. Hazelnut 110장 확인에서 지각 품질과 픽셀 오차가 다른 방향으로 움직였고, 위치 지표 차이의 신뢰구간은 0을 포함했다. | [파일럿](../analysis/restoration_objective_pilot/PILOT_RESULT.md) · [110장 본실험](../analysis/restoration_objective_full/FULL_RESULT.md) · [Screw 적용](../analysis/restoration_objective_screw/RESULT.md) |
| 10월 부분 복원과 지도 결합 | 전체 복원 결과 중 일부만 쓰거나, 원 입력과 복원 결과의 이상 지도를 결합했다. 소규모 저장 결과 재분석에서 선택 기준을 만족한 주 실험 대안을 얻지 못해 탐색 결과로 남겼다. | [부분 복원](../analysis/partial_restoration_feasibility/REPORT.md) · [지도 결합](../analysis/map_gating_feasibility/hazelnut-branchb-20261014/REPORT.md) |
| 10월 PCB 처리 단위 | 전체 PCB를 하나로 축소하면 작은 결함이 적은 픽셀로 표현된다. 좌표를 보존하는 native 224 타일, 중첩 재조립, 보정과 메모리 사용량을 따로 확인했다. | [전체 영상 구조](../analysis/pcb_geometry/pcb2-full-frame224-20261015/REPORT.md) · [native 타일](../analysis/pcb_geometry/pcb2-native224-tiling-20261016/REPORT.md) |
| 11월 VisA PCB 코호트 | native 처리 방식으로 380장 × 3조건을 실행했다. Pooled 위치 지표와 제품 단위 운영점이 달라질 수 있어 테스트 200장에서 미검·오검 전환을 재집계했다. | [전체 코호트](../analysis/pcb_full_cohort/RESULT.md) · [실측 실행 단계](../analysis/pcb_full_cohort/derived/raw_stage_times.csv) · [대표 전환 4사례](figures/visa/README.md) |
| 11월 현실적 열화와 점수 집계 | 흐림·노이즈 조건을 늘려 결과 순서를 대조했다. 지도 최대값 및 상위 픽셀 점수 집계가 Screw의 영상 단위 판정 저하를 해소하는지 별도로 확인했다. | [56단위 열화 비교](../analysis/realistic_degradation/RESULT.md) · [점수 진단](../analysis/image_score_diagnosis/REPORT.md) |
| 11월 정상 특징 bank | 이미지 복원과 정상 기준의 영향을 분리하려고 검사 입력을 고정하고 bank를 바꿨다. 기본 24조건과 Bicubic bank 확장 4조건을 기록했다. 고정 SwinIR 입력에서 pooled 증가와 평균 영상별 감소가 함께 나타난 경우가 있었다. | [28조건](data/bank/bank-domain-28.csv) · [개별 결과](data/bank/base/) · [Bicubic bank 확장 검토](../analysis/jihyuk_bicubic_bank_return_20261117/REVIEW.md) · [이상 지도](figures/mvtec/README.md) |
| 11월 15~17일 실물 시제품 | 기판 한 장에서 기준 조명, 다른 각도의 조명, 저조도, 흐림, 모사 이물을 촬영했다. 직접 검사, 복원, 조건부 대체 촬영, 상시 두 조명 정책을 같은 사례로 비교했다. | [24장 개발 자료](data/phone/station_run/) · [사진과 검사 흐름](figures/phone/README.md) |
| 11월 18~19일 고정 평가와 진단 | 별도 50장 세션에서 기존 방법이 대체 조명 입력을 기준 사진에 정렬하지 못했다. 대비 보정도 개선을 주지 않아 같은 조명 기준을 선택했다. 평가용 46장에서는 정렬 성공 15→38장으로 늘었다. | [고정 결과](data/phone/station_fixed_v03/) · [같은 세션에서 개발한 정렬](data/phone/station_dev_samelight/) · [정렬 진단](data/phone/registration_probe/) |
| 11월 20일 자세 재시도 | 회전만으로 정렬 문제가 해결되는지 확인했다. 같은 조명에서도 실패한 8장 중 2장의 정렬을 복구했고, 품질 판정은 두 장 모두 RETAKE였다. | [회전 시도](data/phone/rotation-probe.csv) · [재시도 후 품질](data/phone/rotation-recovered-quality.csv) |
| 11월 25일 사람 판독과 운영 결과 | 두 사람이 독립적으로 본 원본 평가용 46장 중 일치 24장, 불일치 22장이었다. 저조도·흐림 10쌍은 첫 사진과 실제 다른 조명에서 찍은 대체 사진을 비교했다. | [판독 46장](data/phone/human-readability-46.csv) · [촬영 10쌍](data/phone/capture-pairs-10.csv) · [상세보고서](report/team-2-report.pdf) |

실물 판독의 대체 사진은 별도 촬영한 입력이다. 같은 사진을 복원한 효과를 사람과 자동 검사에서 동시에 확인하려면 동일 입력과 복원본 사이의 블라인드 비교가 필요하다. 별도의 양산 라인 시험이나 실제 촬영·조명 전환 시간 측정은 이번 연구 범위에 포함되지 않았다.
