# bank-domain 담당 이관

2026-11-17 사용자가 지혁의 미완료 bank-domain 실행을 주형에게 넘기도록 승인했다. 실제 PatchCore 기본 24조건과 Bicubic-bank 확장 4조건은 주형이 이어간다. 최신 [주형 실행 지시](https://github.com/kdmoon0405-prog/restoration-anomaly-benchmark/blob/4c333f295e6ea8daf7c469a8a82630d7c1b774e2/docs/BANK_DOMAIN_TAKEOVER_JUHYUNG_20261117.md)와 origin/handoff/juhyung의 NEXT_TASK를 따른다.

기존 producer 패치, 데이터·checkpoint, 완료 또는 부분 실행 결과와 로그를 보존한다. 실행 중 worker가 있으면 현재 상태·완료 단위·재개 위치를 주형에게 전달해 중복 실행을 피한다. 완료된 CPU HOG 대조 결과는 실제 PatchCore GPU 반환과 별도 기록한다.

주형에게는 이 branch d8dcceb의 공개 producer 패치 두 개와 원본 SHA를 전달했다. CPU consumer와 producer의 scripts/analyze_bank_domain_study.py 이름 충돌은 별도 bank 실행 checkout에서 해결하도록 지시했다. 원본 patch·기존 source·결과 이력은 유지한다.

공개 Git에는 코드와 허용된 scalar metadata를 반환한다. 사진·RGB/GT·map·bank·weights·실제 private 노트는 비공개 전달 경로를 사용한다. CPU는 새 receipt를 받아 기존 계약으로 통합한다.
