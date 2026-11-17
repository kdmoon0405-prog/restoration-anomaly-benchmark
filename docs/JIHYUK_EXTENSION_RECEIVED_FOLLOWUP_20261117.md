# 지혁 확장 결과 수신 후 주형에게 추가할 지시

2026-11-17. 이 지시는 이전 통합 프롬프트의 bank24+4 신규실행 부분을 갱신한다. 지혁은 기존24/24와확장4/4를완료했다고보고했고CPU는이번확장4의metadata를수신·대조했다. 기존완료조건을즉시다시실행하지않고아래수신·통합·사진작업을먼저진행한다.

## 1. 완료 결과와 실제 소스를 회수한다

- 기존24조건은Hazelnut/Screw×seed11/23/37의6개run이다. 지혁에게원래반환ZIP6개와28조건집계,각run의manifest/config/provenance/summary/per_image/receipt를받는다.
- 지혁로컬handoff/jihyuk 최신8af5aa606c96bbb5738fddf63fe3db16dc9f6ac7은미푸시보고다. 실제feature source HEAD ac93134/dirty의파일과source-only전달commit을구분한다. source-only코드/CPU분석기·테스트를비공개ZIP또는bundle로받는다. GitHub쓰기인증을고치느라분석을멈출필요는없다.
- 현재extension.patch에는실행runner·검증module·resume·실행측테스트4파일만있다. scripts/analyze_bicubic_bank_extension.py와분석측구현·5테스트,당일수정된base runner/study와실행시점source사본도받는다.
- Hazelnut최초runner는ebc196fe…35d4ac,현재수정runner는224dbed7…a8d97이다. 최초실패status/transcript·소스사본과평가재개기록을유지한다. baseline query/input원본hash를직접대조한다.
- 저장bank는count/hash만남았고행렬은직렬화되지않았다. 기존raw prediction/map으로할수있는분석·그림을우선한다. 사진지도반환을위해전체bank를다시만들필요가있는지먼저검토한다.

## 2. 이번에 받은4조건을 먼저 재사용한다

현재handoff/returns/jihyuk/의두bicubic-bank run과 [CPU 검토](../analysis/jihyuk_bicubic_bank_return_20261117/REVIEW.md)를읽는다. 두ZIP의CRC/receipt24payload,개별540행/paired378행,화질평균과4조건image AUROC가대조됐다. pooled AU-PRO와pixel AUROC는저장값의내부일치검토이며raw배열독립재평가는아직없다. 원래24의receipt수신을별도로완료한다.

같은Bicubic bank에서SwinIR query가주는pooled AU-PRO변화는Hazelnut+0.016908,Screw−0.037334다. Screw는PSNR+2.437522dB인데image AUROC는0.934208→0.725763,pooled AU-PRO는0.898887→0.861553이다. 이대조를그림과수치로설명한다. 개선·악화의기전은추가근거없이단정하지않는다.

고정SwinIR query의clean→Bicubic bank비교에서Screw의pooled값은상승하지만per-image평균은−0.010678이고64/119가감소한다. 이대조와‘동일bank의query복원’대조를분리한다. seed11두cohort,pooled CI미계산,같은물체seed반복,실행RAM peak미측정을보고한다.

## 3. 저장 예측에서 사진을 먼저 뽑는다

[선정 사례표](../analysis/jihyuk_bicubic_bank_return_20261117/selected_visual_cases.csv)에6개ID와선정기준이있다. 이는수신후설명용선정이다.

Screw의감소예시screw/test/manipulated_front/020.png부터확인한다. Bicubic bank내per-image AU-PRO의SwinIR-minus-Bicubic은−0.535514다. 증가예시thread_side/011과변화가작은scratch_neck/008, Hazelnut의대응3개도함께내보낸다.

지혁에게해당6개sample의clean canonical224 RGB/대응GT/Bicubic/SwinIR RGB와seed11의clean·swinir_restored·bicubic_x4 bank×두query검사maps를기존raw파일에서내보내달라고요청한다. raw전체전송이부담되면이6개배열·PNG와원본run/hash/순서인덱스만받는다. 같은기하·crop·색범위·이미지ID를유지한다. benchmark224기하와nativePCB기하를혼용하지않는다.

이사진으로동일query에서bank가달라지는모습과동일bank에서복원이달라지는모습을각각보여준다. 원본결함이RGB에서약해졌는지,검사map의위치/대비가변했는지관측과해석을나눠적는다.

## 4. 최종 목적에 필요한 나머지 작업

통합프롬프트의설계보완·실제기판사진·정렬/해상도/검사경로연결·관련테스트·실제HTML·보고서/A0·검토수정을이어간다. 기존24+4를새실험으로다시추가하지않는다.

촬영전기본32v2+작은모사이물열화18=50장제안은보유사진과대조해고정한다. 실제사진과사람판독·취득시간이도착한범위에서검증한다. 모사이물과실제제조미세결함,benchmark GT와실물위치표시를구분한다. 사진을기다리는동안기존저장결과의그림·분석·보고서를계속한다.

공개Git에는코드와허용된metadata만반환한다. 실제private노트·사진·GT·raw maps·weights·bank는비공개로직접반환한다. 받은28조건과전체평가범위,새사진,미해결입력을표기해최종결과를마무리한다.
