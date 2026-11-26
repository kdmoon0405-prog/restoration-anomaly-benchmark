# 팀 2 연구 결과와 보고서 자료

## 보고서 작업에 쓸 파일

- [보고서 작성 인계](../docs/REPORT_AUTHOR_HANDOFF.md) · [연구 결정 기록 전체](../docs/RESEARCH_EVOLUTION.md) · [고해상도 사진과 원판독 기록](local-evidence/README.md)

- [상세 결과보고서 PDF](report/team-2-report.pdf) · [편집용 Word](report/team-2-report.docx)
- [A0 포스터 작업본 PDF](report/team-2-a0-draft.pdf) · [편집용 PPTX](report/team-2-a0-draft.pptx)
- [결과 그림 모음](FIGURES.md) · [연구 과정과 실험별 근거](RESEARCH_HISTORY.md) · [진행 기록](../PROGRESS.md)
- [정상 특징 bank 28조건 표](data/bank/bank-domain-28.csv) · [기본 24조건 개별 점수와 집계](data/bank/base/) · [Bicubic bank 확장 원 기록과 교차 검토](../analysis/jihyuk_bicubic_bank_return_20261117/REVIEW.md)
- [VisA PCB 전체 코호트 결과](../analysis/pcb_full_cohort/RESULT.md) · [테스트 200장 판정 전환표](data/visa/decision-changes.csv) · [대표 4사례 자료](data/visa/operating-point-cases.csv)
- [실물 기판 첫 24장](data/phone/development-captures.csv) · [새 50장 촬영 계획과 사진 번호](data/phone/evaluation-capture-plan.csv) · [고정 평가 23건](data/phone/station_fixed_v03/station_result.csv) · [같은 조명 정렬 개발 23건](data/phone/station_dev_samelight/station_result.csv)
- [두 사람의 판독 46장](data/phone/human-readability-46.csv) · [열화 첫 사진과 대체 사진 10쌍](data/phone/capture-pairs-10.csv) · [회전 재시도](data/phone/rotation-probe.csv)
- [그림 출처·변환 기록](figure-provenance.csv) · [데이터 출처와 그림 라이선스](FIGURE_LICENSES.md)

## 수치를 읽는 기준

VisA PCB는 380장(정상 보정 180장, 테스트 200장)을 세 처리 조건에서 실행한 1,140 처리 단위다. 테스트 정상 100장과 이상 100장의 변형별 정상 보정 운영점에서 Bicubic과 SwinIR의 미검은 29건과 46건, 오검은 3건과 1건이다. 같은 이미지의 전환은 검출→미검 25건과 미검→검출 8건이다.

Bank 기본 24조건은 Hazelnut·Screw 두 종류, seed 11·23·37, 유형별 2×2 비교다. Bicubic bank 확장 네 조건은 seed 11이다. Pooled AU-PRO는 여러 이미지의 지도와 결함 영역을 합쳐 계산한다. 영상별 변화량의 평균과는 계산 단위가 다르다.

스마트폰 50장은 참조·보정 4장과 23번의 검사에 연결된 평가 사진 46장이다. 같은 조명 참조 정렬의 성공은 평가용 46장에서 15장(32.6%)에서 38장(82.6%)으로 늘었다. 같은 사진을 보고 선택한 개발 방법의 결과다. 작은 이물 9건의 개발 최종 판정은 모두 NG였고 최대 이상 영역이 이물 위치와 일치한 건 3건이었다. 선명한 대체 사진 9장에 인위적 ×4 왕복 처리를 한 위치 비교는 별도 실험이다.

저조도·흐림으로 계획한 10쌍에서 두 판독자가 모두 잘 보인다고 한 사진은 첫 촬영 0장, 대체 촬영 5장이다. 자동 검사 결과를 보기 전 판독했고, 개별 확대 배율은 기록되지 않았다. 같은 첫 사진에 Bicubic·SwinIR을 적용한 C1은 23건에서 직접 검사와 최종 판정이 같았다. 실측 촬영 시간과 전체 기판에 대한 일반화 자료는 없다.

공개 사진은 촬영 세션 순번을 부여한 표시용 사본이다. 밝기와 결함 위치를 가공하지 않았고, 스티커의 식별 표식과 EXIF를 제거했다. 고정 평가와 개발 결과의 수치는 기존 결과 파일에서 옮겼다.
