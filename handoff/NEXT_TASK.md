# 주형의 다음 작업

2026-11-17 지혁추가반환을수신했다. 기존24/24와확장4/4는수행완료보고이며,CPU는이번확장4의receipt/CSV/image AUROC를확인했다. 기존24의원래6개반환물과미푸시코드/CPU분석기는수신대기다.

먼저 [추가 수신 후 지시](../docs/JIHYUK_EXTENSION_RECEIVED_FOLLOWUP_20261117.md)와 [CPU 검토](../analysis/jihyuk_bicubic_bank_return_20261117/REVIEW.md)를읽는다. 이전‘24+4전체신규실행’지시는완료결과회수·통합·사진반환으로바꿨다.

1. 지혁에게기존6run metadata/집계와source-only8af5aa코드묶음을받는다. HTTPS쓰기인증복구를기다릴필요는없다.
2. 현재받은확장4와기존24를family별로통합하고소스/query/split을대조한다. 실제빈부분을확인하기전에기존조건전체를다시실행하지않는다.
3. [선정6사례](../analysis/jihyuk_bicubic_bank_return_20261117/selected_visual_cases.csv)의RGB/GT/각bank-query지도를지혁의저장raw결과에서내보낸다. Screw의화질상승·검사하락사례를포함한다.
4. [통합 프롬프트](../docs/PROMPT_JUHYUNG_END_TO_END_20261117.md)의필요구현·실물사진·촬영전50장제안·사람판독·보고서/A0·검토수정을이어간다.

확장metadata는handoff/returns/jihyuk의두bicubic-bank run,실행측4파일patch는handoff/patches/jihyuk-bicubic-bank-extension.patch에있다. 원래기본24와CPU분석기코드가이patch에포함됐다고가정하지않는다.

기존phone24장/16cycle은개발결과이고정상13은OK6/NG1/REVIEW6이다. 실제최종private와D-20261115-17은수신됐다. 새촬영/사람판독/실제취득시간/팀정보는별도입력이다. 공개자료와비공개사진/private반환을구분하고기존source·worker·자원guard를유지한다.

A0 PDF마감은2026-12-01 23:59KST이고실제발표일은미확인이다.
