# CPU 제어·선택 map 분석 전달

2026-11-09의 작업은 기존 GPU 수치를 제어 인터페이스까지 전달하는 software replay와 native map 분석 도구를 준비했다. 기준은 exp/juhyung-results-analysis의 6472f69이며 구현 branch는 exp/inspection-controller-cpu다. GPU 담당자의 execution source와 기존 연구 결과는 보존했다.

## 완료한 범위

- 하드웨어 비종속 controller의 요청·ACK, 중복·충돌, timeout, stale result, 재연결 상태 유지와 완료 ACK를 구현했다. Synthetic 6cycle에서 OK/NG/REVIEW 각 1개, ERROR 3개를 확인했다.
- PCB 저장 normalized_image_score와 기존 threshold를 variant마다 200건씩 replay했다. Clean OK120/NG80, Bicubic OK126/NG74, SwinIR OK145/NG55였다. 동일한 200개 보드의 세 조건이며 독립 보드 600개로 세지 않는다. GT/label은 판정에 사용하지 않았다.
- 선택 native map의 hash·shape·metadata·GT binding과 exploratory descriptor/그림 경로를 구현했다. 2026-11-10에27개를 받아 무결성 검사를 마쳤다. 공간 분석은 고정 메모리 기준 미달로 BLOCKED_MEMORY이며 real_spatial_cases_analyzed=0이다.
- Synthetic mask/map으로 component·gap·centroid·seam descriptor를 검증하고 PNG를 직접 열었다. 선택된 실제 PCB 사례 그림은 파일 수신 후 생성한다.

Replay의 simulated timestamp와 fake 배출 event는 software 계약 검사용이다. 실제 카메라 노출, GPIO, 이송·배출 latency는 장치 연결 후 계측한다. Process 내 reconnect를 지원하며, process 재시작과 부품 위치 복구 계약은 후속 장치 단계에서 정한다.

## 재현 명령

구현 worktree root에서 실행한다. 원본 Python 환경과 기존 반환 metadata를 재사용한다. 새 checkout에는 데이터·가중치·venv·반환 ZIP이 따라오지 않는다.

```powershell
$py = '..\..\.venv\Scripts\python.exe'
$original = (Resolve-Path '..\..').Path
$package = Join-Path $original 'outputs/juhyung-return-review-20261109/artifacts/return-package-20261109'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
& $py scripts/simulate_inspection_station.py --output "outputs/station-synthetic-$tag"
foreach ($variant in @('clean', 'bicubic_x4', 'swinir_x4')) {
    & $py scripts/simulate_inspection_station.py --saved-pcb-return $package --variant $variant --output "outputs/replay-$variant-$tag"
}
$testTemp = Join-Path ([IO.Path]::GetTempPath()) ('station-tests-' + [guid]::NewGuid().ToString('N'))
& $py -m pytest -q tests/test_inspection_station.py tests/test_pcb_selected_spatial.py --basetemp $testTemp
& $py scripts/smoke_test.py
git diff --check
```

Map은 원본 outputs/gpu-followup-review-20261110/artifacts/ 아래에 전달된 경로를 유지해 보존했다. 누락 시 WAITING_FOR_SELECTED_MAPS, RAM 부족 시 BLOCKED_MEMORY로 종료한다. Metadata가 검토된 값과 다르면 거부한다.

```powershell
$maps = Join-Path $original 'outputs/gpu-followup-review-20261110/artifacts/pcb-native-maps-20261109/pcb-native-maps-20261109/pcb-full-cohort-20261101-a'
$data = Join-Path $original 'data/external/VisA'
& $py scripts/analyze_pcb_selected_maps.py --maps-root $maps --metadata-root $package --data-root $data --output "outputs/pcb-selected-spatial-$tag"
```

## 다음 반환의 연결

지혁의 새 bank-domain ZIP은 아직 없다. 기존 다섯 파일 계약과 scripts/analyze_bank_domain_study.py를 유지했다. 새 COMPLETE run이 오면 receipt를 한 번 만들고 네 셀, 동일 query RGB/quality, fit/calibration 분할과 source를 대조한다. Matched Bicubic-bank extension은 별도 schema가 전달되면 작은 adapter로 연결한다.

주형의 원본 map이 오면 고정 9개 사례만 descriptor와 그림으로 분석한다. GT는 post-hoc 공간 분석에만 사용하고 ROI를 이용해 method/threshold를 바꾸지 않는다. RGB/GT overlay PNG와 배열은 local-only다. Native geometry audit의 8-connectivity와 이 분석의 evaluator-aligned 4-connectivity를 구분한다.

기존 master는 133행/9protocol groups를 보존했다. 새 실제 연구 조건이 없어 master 행과 pooled 지표를 다시 계산하지 않았다. analysis/cpu_control_spatial_20261109/evidence_status.csv는 새 제어 검증과 대기 중인 증거를 기존 연구 주장에 연결한다. Synthetic/replay 수치는 연구 성능 표에 합치지 않는다.

검증 기록과 원본 log는 원본 outputs/cpu-control-spatial-20261109/에 저장한다. 원본 PROGRESS에는 실행 사실, ignored notes/RESEARCH_EVOLUTION_LOCAL.md에는 검증 가능한 판단과 다음 질문을 나눠 기록한다.
