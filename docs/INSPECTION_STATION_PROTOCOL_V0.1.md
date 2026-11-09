# 검사 스테이션 software simulator v0.1

이 계약은 CPU에서 검사 요청과 판정 전달을 검증하는 초안이다. Transport는 command/response JSON이며 현재 구현은 메모리 안의 fake controller다. 실제 MCU·PLC·카메라 연결과 물리 배출 동작은 후속 장치 단계에서 검증한다.

## 상태와 소유권

Controller는 한 번에 한 cycle만 접수한다. 연결 여부는 connected 필드로 별도 기록한다. READY는 새 요청 접수 가능, BUSY는 판정 대기, OK/NG는 전달된 판정, REVIEW는 보류, ERROR는 실행·입력·통신 실패다.

| 현재 상태 | 입력 | 다음 상태 |
|---|---|---|
| READY, connected | start | BUSY |
| BUSY | 유효한 complete | OK / NG / REVIEW / ERROR |
| BUSY | deadline 도달 또는 disconnect | ERROR |
| terminal, connected | 같은 cycle_id의 acknowledge | READY |
| 임의 상태 | connect / status | 현재 상태 보존 |

연결이 끊긴 BUSY cycle은 ERROR로 종료한다. 재연결의 ACK는 현재 상태와 해당 cycle을 반환한다. ERROR의 acknowledge 전에는 새 cycle을 받지 않는다. 종료된 cycle의 늦은 결과가 현재 cycle을 바꾸지 못하게 한다. 동일 process에서의 재연결을 검증한다. Process 재시작 뒤의 controller 복구는 장치 측 상태·부품 위치 재동기화가 필요한 별도 계약이다.

## 명령과 ACK

모든 명령에 request_id와 command가 필요하다. command는 connect, disconnect, status, start, complete, acknowledge 중 하나다. Response에는 request_id, accepted, code, state, connected, active_cycle_id, cycle과 fake_actions가 있다. accepted는 명령 접수 여부이며 OK 판정과 구분한다.

start에는 part_id, cycle_id, recipe_id, image_ref가 필요하다. 각 값은 비어 있지 않은 printable string이다. image_ref와 prediction_ref는 opaque 참조이며 controller가 파일이나 URL을 자동으로 열지 않는다. 접수할 때 started_at_seconds와 deadline_seconds를 기록한다. Timeout은 controller 설정 하나로 고정한다. Demo의 5초는 synthetic timeout 검사용 설정이다.

complete에는 cycle_id, verdict, prediction_ref, result_source가 필요하다. OK/NG/REVIEW의 참조나 출처가 없으면 ERROR로 종료한다. 명시적 ERROR에는 error 설명과 result_source가 필요하다. Controller는 detector 결과의 과학적 정확도를 인증하지 않는다. 실제 inference 연결 시 recipe/checkpoint/threshold 출처 검증은 상위 adapter가 담당한다.

동일 cycle_id의 동일 start를 재전송하면 기존 cycle을 ACK하고 추가 검사를 dispatch하지 않는다. 같은 ID에 다른 part/recipe/image를 넣으면 충돌로 거부한다. 완료 결과 재전송도 같은 내용에 한해서 ACK하고 fake 배출 event를 반복하지 않는다. Timeout·연결 종료로 끝난 cycle의 결과는 stale로 거부한다. acknowledge 재전송은 이미 완료된 ACK로 처리한다.

Timeout은 매 command에서 검사한다. 실제 adapter는 deadline 전에 status polling/heartbeat를 실행해야 한다. 이 동기 simulator는 실시간 watchdog으로 검증되지 않았다. Clock은 finite·단조 증가 값이어야 하며 시작·종료 시각은 clock_kind와 함께 저장한다. Demo의 simulation_seconds는 장비 latency와 구분한다.

## 실행과 산출물

구현 worktree에서 기존 Python 환경으로 실행한다.

```powershell
$py = '..\..\.venv\Scripts\python.exe'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
& $py scripts/simulate_inspection_station.py --output "outputs/station-demo-$tag"
```

기본 scenario는 OK/NG/REVIEW, 결과 참조 누락, timeout, 중복 요청, stale 결과, 연결 끊김과 재연결을 포함한다. events.jsonl은 command와 response를 함께 기록하고 cycles.csv는 cycle별 식별자·시각·참조·결과를 저장한다. manifest는 synthetic_controller_simulation, research_metrics=null, physical_hardware_tested=false를 명시한다. 모든 출력은 새 directory에 저장한다.

--saved-pcb-return으로 검토된 반환 root를 명시하면 저장 normalized_image_score와 기존 image_threshold의 >= 규칙을 software replay한다. --variant는 clean/bicubic_x4/swinir_x4다. 두 입력 파일의 hash를 기존 분석 manifest와 대조한다. Replay에서 label/GT는 판정을 정하는 데 사용하지 않는다. kind는 software_replay_of_saved_scores이며 timeline과 배출 event는 simulator의 값이다. 실제 detector 실행·물리 latency 측정과 구분한다.

보유 카메라의 trigger I/O, MCU/PLC, scope/PSU/DMM, 예산은 미확인이다. 실제 인터록·전원·비상정지·actuator 사양은 이 software 계약에서 정하지 않았다. 후속 장치 검증에서는 LED 전류·노출·완료 GPIO와 실제 cycle time을 별도로 계측한다.
