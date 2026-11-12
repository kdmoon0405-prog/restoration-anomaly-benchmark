# Fable 재검토·clean control·phone 도구의 CPU 검토

2026-11-12 검토. handoff/juhyung@5794b2d까지4receipt/34공급파일을 SHA·크기와 대조했다. 같은 ZIP·구조건의 반복 검토는 수행하지 않았다. 지혁 branch는 d8dcceb로 새실험 반환이 없었다.

## 설계 검토의 출처

초기 설계와 phone 구현은 기록상 Opus5.5에서 수행됐고,이후 사용자 설정 변경으로 Fable5.2 재검토가 반환됐다. Fable v1은 이전 초안·근거가 문맥에 있었음을 원격 기록이 명시한다. 독립 초안으로 승격하지 않고 실제 근거 검토와 수정의 내용으로 평가한다. 이전 결과와 기록은 보존됐다.

Fable이 발견한 정렬 보간의 품질지표 편향은 source aa2f7fa에서 원본 화소/투영 ROI mask로 수정됐다. 새 source의 해시 연결과 regression test를 확인했다. 조명 간 정렬 실패는 실제 사진에서 추가 확인할 항목이다. C1 문구는 CPU 기존 분석에 맞춰 σ15의 두 category 반복과 Hazelnut σ5의 관측을 구체적으로 쓰고,Screw σ5의 불확실성을 함께 표시하는 편이 정확하다.

## 저장 clean control 검산

Historical Screw family의3unit×5규칙15cell을 동일160영상(정상41/이상119)의 scalar로 재계산했다. Sample/label pairing,원본 NPZ 해시 참조와 CSV 연결,summary·unit Image AUROC가1e-12범위 내 일치했다.

| variant | original | map max | top0.1% | top0.5% | top1% |
| --- | --- | --- | --- | --- | --- |
| clean | 0.984218 | 0.983193 | 0.984013 | 0.984218 | 0.982578 |
| Bicubic x4 | 0.480016 | 0.452962 | 0.449682 | 0.439844 | 0.434720 |
| SwinIR x4 | 0.678623 | 0.634351 | 0.626153 | 0.602787 | 0.582701 |

Clean은집계에따른차이가작고×4조건의낮은image AUROC는모든규칙에서유지된다. 이범위에서집계변경만으로저하가해소되지않았다. Bank/query domain이나정보손실의원인은별도대조가필요하다. Source에calibration이없어F1/FPR/미검률은NA를유지한다. Pixel AUROC anchor와GT검산은원격실행보고범위이며raw NPZ는CPU미수신이다. 기존165prediction조건과200readout조건에중복15개독립실험을더하지않는다.

## Phone synthetic 재현

새phone source aa2f7fa를별도detached source-only worktree에받아기존CPU환경으로 tests/test_phone_capture.py 및 tests/test_inspection_station.py를실행했다. 24tests가97.70초에통과했고합성E2E의HTML과재촬영/station replay도생성됐다. 복합명령의후속psutil환경조회만실패해전체명령exit는1이었다. 설치를추가하지않고기존 _budget으로후속화면검증자원확인을통과했다. Test통과와보조조회실패를구분한다.

공급된두phone버전의source4파일해시와상태16개를대조했다. Sheet16행에미등록파일1개를더한captures17행이며PASS7/REVIEW6/RETAKE4다. Slot14개중7개가해결됐고station14cycle은모두REVIEW다. PASS는입력품질허용상태이며detector는연결되지않았다. 실제정상/불량성능이나물리지연·lux결과는없다.

## 실제 브라우저 화면

자체합성E2E가생성한report.html을분리된headless Edge profile에서열고1440×1100,390×844 PNG를저장해직접확인했다. Desktop의상태·재촬영이력과합성/미연결표기는읽을수있다. Mobile에서는긴표때문에페이지가가로로늘어나안내문과열이잘린다. Screenshot은ignored local outputs에보관한다. 클릭·console검사는이번범위에포함되지않는다.

주형의다음소규모수정은모바일에서본문을viewport에맞추고표만가로scroll되게하는것이다. 포스터용첫화면에는대표원본/품질overlay와해석가능한짧은요약을위에배치할수있다. Source소유권을유지하기위해CPU가phone실행코드를병행재작성하지않았다. Desktop시연과실사진수신을진행하면서수정할수있다.

## 다음 실행

실사진첫입력은JPEG9장이다. 최신가이드가현재환경에서HEIC/RAW를읽지못하는점을반영했다. 고정된대상/카메라와세조명×세반복을기록한다. 사진수량·결함상태는아직미확인이다. 실제조명에서정렬·품질기준을확인하고새방법은해당test비교전범위를기록한다. 주형의완료단위PROGRESS와private결정노트도계속받는다. 이번에새private원문은수신되지않았다.
