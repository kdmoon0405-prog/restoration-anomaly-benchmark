# 주형 최종 반환 후 CPU 검토 반영

반환59bc262/source7b868a3의22개 metadata 해시,112cell과 운영표16행을 확인했다. 기존96cell은 이전 반환과 같고 v0.3은 같은24장/16cycle에서v0.2와 같은 결과다. Consumer11개와 source 신규4개 CPU 테스트가 통과했다. 상세 [검토 보고서](../analysis/phone_final_return_20261117/REVIEW.md)를 반영한다.

다음은 새 모델 실험 없이 현재 문서·포스터 생성기·표시 문구에서 마칠 작업이다.

1. FINAL_REPORT §6.5와 FINAL_REVIEW에서 원근 입력을 중심 보정/화면 이동으로 나눈다. 중심 보정은5도 ACCEPT·10~30도 REVIEW·40~50도 RETAKE, 화면 이동은5도 ACCEPT·10~30도 RETAKE다. 실제 허용각으로 일반화하지 않는다.
2.147/423초는 코드·조건 수·전원이 함께 다른 개발 실행이라고 적는다.633초는 pytest 부하도 있다. 전원 때문에3배 느려졌다는 원인 표현을 고친다.
3. make_figures.py와 make_poster_spec.py의 ‘평균 AU-PRO’를 ‘pooled AU-PRO’로 바꾼다. 공통 seed11도 family별로 고친다. Historical_recovery seed는 미기록, PCB native full cohort는11이다.
4. Team No_??·저자·소속을 실제 확정 정보로 마무리한다. 확정 전에는 검토용 포스터로 반환한다. HTML banner의 운영 기준도v0.3에 맞춘다.
5. 실제 비공개 PPTX/PDF·그림7개·최신HTML·capture_sheet·새private원문을 bytes/SHA와 마지막 결정ID를 붙여 비공개로 전달한다. 원시 배열은 실제 제공 상태를 명시한다. 공개 PROGRESS와 실제 private 원문을 각각 반환한다.

새32장 평가·사람 판독·물리 촬영시간·UNO 실물·지혁24+4는 실제 확보 상태에 따라 병행한다. 문구 수정과 시각 파일 전달을 위해 기존 확정 실행을 반복할 필요는 없다. 자원 guard·source 소유권·완료 cache를 유지한다.
