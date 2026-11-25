# CPU 후속 결과 통합

현재 원본 research_code와 구현 worktree를 보존하며 PROGRESS 최신 부분과 outputs/gpu-followup-review-20261110/HANDOFF.md를 먼저 읽는다. 완료 receipt는 cache를 재사용하고 handoff/juhyung 및 handoff/jihyuk의 새 반환만 확인한다.

주형의9사례와 noise32는 검토 완료다. exp/pcb-selected-spatial-review@30b420d와 새 noise 분석 branch의 보고서·master·검증 manifest를 확인한다. 다음은 지혁의 실제 bank-domain24+4와 주형의 저장 map image-score aggregation 반환이다. 기존 strict4셀의 bank clean/swinir_restored,query bicubic_x4/swinir_x4를 유지한다. Extension과 다른 family는 source manifest에 맞춘 별도 adapter로 연결한다.

Paired sample identity, normal calibration, 동일query hash, actual source와 부분 완료를 확인한 뒤 저장 수치만 집계한다. 같은 영상의 seed 반복을 독립 표본으로 늘리지 않는다. Pooled AU-PRO point와 mean per-image CI를 구분한다. 원본raw/GT/bank/가중치는 보존하고 고정 자원guard를 유지한다.

두 담당자의 private 결정 텍스트는 공개 artifact와 별도로 읽는다. 검증 가능한 문제·근거·대안·선택이유·수정전후·미해결질문만 중앙 notes/RESEARCH_EVOLUTION_LOCAL.md에 날짜·담당자·source·run-id와 함께 통합한다. 원본 PROGRESS에는 수행 사실·결과·commit·blocker를 적는다. Private 노트는 ignored/untracked를 확인하고 stage/commit/push하지 않는다.

새 실제 반환이 없으면 유한한 완료 queue를 유지한다. 반복 실험이나 동일자료 재검토를 추가하지 않는다. 필요한 코드·테스트·공개 보고서는 별도 CPU branch에 공개하고 원격 commit을 확인한다.
