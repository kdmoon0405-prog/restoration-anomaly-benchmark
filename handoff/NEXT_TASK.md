# 주형의 다음 작업

2026-11-17 사용자 지시를 반영했다. 지혁의 미완료 bank-domain 24+4 실행을 주형에게 이관한다. 현재 최우선 산출물은 같은 결함 위치에서 원본·열화·Bicubic·SwinIR을 확인할 수 있는 확대 사진과 대응 검사 지도다.

[실행 프롬프트](../docs/BANK_DOMAIN_TAKEOVER_JUHYUNG_20261117.md)를 읽고 기존 Fable 환경과 실행 checkout을 이어간다. [사진 목표 대조](../docs/PHOTO_RESULT_GOAL_REVIEW_20261117.md), [기존 CPU 수정](../docs/PHONE_FINAL_CPU_FEEDBACK_20261117.md)을 함께 반영한다.

## 실행 순서

1. 기존 worker·소스·완료 condition·RGB/map 캐시를 확인하고 보존한다.
2. 기존 선정 사례를 같은 좌표로 확대한 원본/열화/Bicubic/SwinIR/GT/검사 지도 사진 묶음을 만든다. 실제 스마트폰 사진의 저조도·조명 변경·모사 이물도 확대해서 반환한다.
3. 별도 bank 실행 checkout에서 지혁 producer를 통합하고 실제 PatchCore 기본 24조건과 확장 4조건을 완성한다. 먼저 두 category의 seed 11 완료 단위부터 반환한다.
4. bank만 바꾼 동일 query의 그림을 추가하고 보고서·A0 포스터를 수정한다. 새 사진 평가·사람 판독·물리 시간은 실제 입력이 도착한 뒤 연결한다.

producer 패치는 handoff/code/에 있다. scripts/analyze_bank_domain_study.py는 CPU consumer와 producer의 이름이 같으므로 읽고 통합한다. 기존 phone/CPU 분석 경로를 덮어쓰지 않는다. source 전용 worktree의 vendor·checkpoint·자산 준비 상태를 확인한다.

최종 비공개 ZIP은 CPU가 수신했다. 실제 PDF/PPTX와 사진 그림, 새 private 결정 D-20261115-10~17도 확인·통합했다. 이전의 ‘최종 비공개 파일 미수신’ 상태는 해소됐다. ZIP의 누락 template_copy는 이전 동일 SHA 공식 양식으로 별도 보충했고 원본 ZIP은 보존했다.

현재 24장/16 cycle은 개발 결과다. 정상 13 cycle은 OK 6/NG 1/REVIEW 6, 모사 이물 3 cycle은 NG 3이다. 기존 완료 165조건·9사례·noise32·image-score200/160paired·phone a350b07 캐시를 재사용한다.

새 모델 실행 없이 HTML의 v0.2 문구를 수정할 수 있다. 원근 결과 구분·시간 원인 해석·pooled AU-PRO·seed 표기·팀 정보를 수정한다. 실제 사용 모델과 검토 범위를 기록한다.

A0 PDF 마감은 2026-12-01 23:59 KST다. 실제 발표일은 미확인이다. 사진 포함 산출물과 실제 private 노트는 비공개 파일로 직접 반환한다.
