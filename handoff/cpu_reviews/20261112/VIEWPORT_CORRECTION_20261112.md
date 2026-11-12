# 좁은 화면 검증 해석 정정

2026-11-12 CPU 후속 측정이다. 앞선 보고서는390px screenshot의 잘림을 모바일 레이아웃 문제로 해석했다. 실제 viewport를 측정하지 않은 상태의 해석이었으며 이 부분을 정정한다.

새 측정에서 headless Edge에 window-size390을 요청해도 innerWidth는 기본504px,scale1옵션에서492px였다. 두 경우 모두 document와body의 scrollWidth가clientWidth와 같았고표wrapper의overflow-x는이미auto였다. 해당 screenshot만으로실제390px환경의본문잘림을확정할수없다.

동일source의synthetic E2E 보고서를390 CSS-pixel iframe에넣어추가검증했다. innerWidth390,document client/scrollWidth375,body client/scrollWidth343을확인했다. 본문은폭에맞춰줄바꿈됐고긴표는wrapper내부에서스크롤됐다. PNG를직접열어확인했다. 측정값은 responsive_390_measurements.json에있다.

이검증은실제모바일기기의터치/글꼴/다운로드동작검증과구분한다. 클릭·console검사는추가실행하지않았다. 실기기미검증표기는유지한다. 기존phone source수정과실험결과변경은없다. 이전CPU피드백의모바일본문wrap/표scroll필수수정요청은철회한다. 실제390pxiframe에서기존구현의동작을확인한것이며새구현결과로집계하지않는다.

대표영상/품질overlay와짧은요약을첫화면위쪽에두는제안은시연구성개선후보로유지한다. 결과표·code·screenshot의관측과원인해석을분리한다.
