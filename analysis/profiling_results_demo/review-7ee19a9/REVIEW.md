# 실제 화면·저장 수치·PCB 전처리 검토

2026-10-15. 시작 HEAD `7ee19a9`, branch `exp/profiling-results-demo`. 실제 Git root는 상위 DesignProject의 `research_code/`다. 시작 시 작업 트리는 깨끗했고 더 최신 로컬 commit은 없었다. 상위 `AGENTS.md`와 RTK 지침을 확인했다. Reset/clean/사용자 파일 덮어쓰기, push/main merge/배포는 하지 않는다. 이번 검토는 기존 파일을 읽고 표시·검증 도구를 수정한 작업이며, 모델 fit/재추론, 새 성능 실험, bank/threshold/gating 변경, PCB/Capsule 실행은 없다.

## 직접 확인한 자료와 화면

다음 실제 파일·코드를 확인했다. 이전 보고의 결론만 옮긴 평가가 아니다.

- `analysis/map_gating_feasibility/hazelnut-branchb-20261014/`의 `summary.csv`, `per_image.csv`, `PROTOCOL.json`, 입력 manifest와 raw candidate identity. Primary selection과 GT 제한을 실제 protocol에서 확인했다.
- `analysis/profiling_results_demo/hazelnut-ten-20261015/`의 `timings.csv`, protocol/manifest, summary, parity 기록, PCB inventory/readiness. CSV 통계를 독립 재집계해 저장 JSON과 대조했다.
- `scripts/serve_results_demo.py`, `demo_results/index.html`/README, `profile_patchcore_stages.py`, `summarize_profiling_readiness.py`의 집계·자원 추정, `check_pcb_readiness.py`.
- `src/sr_anomaly/{dataset,fusion,map_gating}.py`, Branch B의 canonical preprocessing, 원본 PatchCore `_predict`와 CPU `FaissNN.run` 계측 경계.
- 실제 Branch B `results.json`, 네 baseline 및 두 candidate NPZ, quality/per-image CSV, pilot10 RGB. 실제 VisA `split_csv/1cls.csv`, pcb2 이미지 1,101개 파일 해시와 불량 GT 100개를 점검했다.

연결된 브라우저 도구는 없었지만 로컬 Edge를 Playwright로 실제 실행했다. 내장 JS 로더 실패 후 별도 ASCII 경로 CPU 검증 환경에 선택적 Playwright를 설치했다. 연구 환경/pyproject의 필수 의존성은 바꾸지 않았고 브라우저 바이너리도 내려받지 않았다. Microsoft Edge headless `154.0.4258.48`, Playwright `1.64.0`, 1440x1000 및 760x1000 viewport다. 실제 페이지를 렌더하고 dropdown/checkbox/download를 조작한 뒤 PNG를 저장해 이미지 보기로 직접 열었다. HTTP/DOM 검사만을 시각 확인으로 부르지 않는다.

직접 조작한 사례는 정상 `good/000.png`, 불량 `crack/000.png`, RGB 없는 `crack/016.png`다. Degraded/restored/candidate_1/candidate_2/mean/max 선택, discrepancy·두 gate, GT on/off/원상 복귀, CSV download를 확인했다. 세 사례의 여섯 method PNG 18개는 원본 NPZ에서 독립 색 변환한 전체 픽셀 배열과 정확히 같았다. Baseline 4개는 원본 results JSON의 AU-PRO/Pixel AUROC/Image AUROC와 CSV가 정확히 일치했다. 화면 summary 6개와 CSV, 사례별 metric 및 baseline quality도 일치했다. [DISPLAY_SOURCE_AUDIT.json](DISPLAY_SOURCE_AUDIT.json), [browser-after.json](browser-after.json)에 범위를 기록했다. 이는 모든 사례의 새 metric 재평가가 아니다.

## 화면의 장점, 문제와 최소 수정

첫 화면에서 여섯 method와 선택 row가 보이고, 음성 feasibility·개발 데이터·candidate F1/calibrated FPR 부재가 상단에 명시돼 있다. GT는 빨간 표시 윤곽일 뿐 gate 입력이 아니다. 정상 AU-PRO와 delta는 `해당 없음`이다. 저장 RGB가 없는 영상은 두 RGB panel 모두 unavailable이며 추론으로 채우지 않는다. Candidate 선택 시 보이는 PSNR/SSIM은 명시적으로 baseline quality이며 candidate 고유 값으로 표시하지 않는다. Candidate image score도 기존 restored score를 유지한 설계다.

문제와 수정:

- 760px 화면에서 표가 document 폭을 밀어내 CI 열이 잘렸다. 표 안의 수평 스크롤로 제한하고 직접 오른쪽 끝까지 스크롤해 확인했다. 페이지 전체 수평 overflow는 수정 전 true, 수정 후 false다. 좁은 화면에서 표 전체가 한 번에 보이는 것은 아니며 스크롤이 필요하다.
- 색 의미/단위와 CI 대상이 불명확했다. 실제 Viridis palette의 색 범례, discrepancy의 독립 최대값, gate 0/1, GT 윤곽, PSNR dB/무차원 SSIM을 표시했다. `AU-PRO@0.3`과 불량 70장 paired mean CI를 표에 설명했다. Mean CI를 pooled AU-PRO CI처럼 쓰지 않는다. Map 여섯 개는 같은 sample min/max, discrepancy는 별도 0..max다.
- Favicon 404가 console error 1건을 만들었다. 빈 favicon 204 응답을 추가했다. 수정 후 page/console 오류, 실패 요청, HTTP 오류 모두 0건이다. CSP를 약화시키지 않았다.

수정은 표시/API 설명 필드에 한정했다. 기존 metric 숫자, 원본 NPZ, 원본 CSV/JSON, calibration과 gate 식은 바꾸지 않았다. 연구용 내부 viewer로는 사례와 근거를 대조할 수 있다. 아직 검증된 위험 경보나 일반 사용자용 제품 UI는 아니다.

스크린샷은 `screenshots/`에 로컬 보관한다. Dataset RGB가 포함되므로 Git에서 제외했고 public 공유 승인으로 취급하지 않는다. [SCREENSHOT_MANIFEST.json](SCREENSHOT_MANIFEST.json)에 파일 해시·크기와 직접 열어 본 범위를 기록했다. 대표 화면:

- [수정 전 첫 화면](screenshots/before-initial-restored.png) / [수정 후 첫 화면](screenshots/after-initial-restored.png)
- [정상과 저장 RGB](screenshots/after-normal-degraded-rgb.png)
- [candidate_2와 GT overlay](screenshots/after-candidate2-gt-rgb.png)
- [candidate_1과 RGB unavailable](screenshots/after-candidate1-unavailable.png)
- [좁은 화면](screenshots/after-narrow.png) / [표 오른쪽 스크롤](screenshots/after-narrow-scrolled.png)

수정 후 PNG 6개, 수정 전 대표 PNG 3개, PCB crop 그림은 이미지 보기로 직접 확인했다. 실제 headed 브라우저/물리적 모바일 화면, 다른 브라우저, screen reader, 인쇄 layout까지 확인한 것은 아니다.

## CSV에서 재계산한 시간과 실제 병목

아래는 **instrumented** phase의 이미지당 평균 초다. 각 경로는 같은 고정 10장 x 2회 = 20관측이다. 20개 독립 이미지가 아니다. 전처리는 공유 RGB decode/canonical/degradation과 tensor normalization의 합이다. 전체는 별도로 잰 E2E parent이며 child와 더하면 안 된다. 전체 정밀값은 [TIMING_RECALCULATED.csv](TIMING_RECALCULATED.csv), 통계/검사는 [EVIDENCE_AUDIT.json](EVIDENCE_AUDIT.json)에 있다.

| 단계 | Degraded | Restored |
| --- | ---: | ---: |
| 전처리 (RGB + tensor) | 0.104067 | 0.100426 |
| SwinIR 복원 | 0.000000 | 1.276684 |
| Backbone·embedding | 0.722982 | 0.743846 |
| Feature detach/CPU/NumPy | 0.011181 | 0.008891 |
| CPU exact FAISS | 8.001780 | 7.539598 |
| Score/map 후처리 | 0.004623 | 0.005027 |
| Detector glue | 0.009081 | 0.007703 |
| Detector parent (비가산) | 8.749647 | 8.305065 |
| 전체 E2E parent (비가산) | 8.854309 | 9.682190 |

FAISS 비중은 `mean(FAISS)/mean(detector parent)`이다. Degraded `8.001779790/8.749646735=91.4526%`, restored `7.539598005/8.305064885=90.7831%`. 이는 SR/전처리/loading을 포함한 전체 wall time의 91%가 아니다. `_embed(detach=False)` 안의 backbone/embedding, 이후 원래 detach loop, `FaissNN.run`의 CPU `IndexFlatL2.search`, 두 unpatch/score/segmentation 후처리 호출은 비중첩 child다. Glue는 parent에서 이 child 합을 뺀 잔여다. CSV의 child+glue와 detector parent 잔차는 0.0이지만, 이는 glue가 잔여로 정의됐다는 점도 포함한다. 함수 호출 구조도 따로 확인했다. Parent와 child를 중복 합산하지 않았다.

로딩/준비/추론 구분:

- 준비 `21.217156 s`, bank+model load `7.968969 s`. 준비에는 입력 검사/import/초기 metadata write가 포함된다.
- Warmup `23.373536 s`는 phase wall `701.134440 s` **안에** 포함된다. Phase는 warmup 2장 x 두 경로 4회, 계측 40회, 별도 원형 20회, 합계 detector 호출 64회다. 같은 고정 10장이다.
- Phase wall에는 parity 확인과 중간 JSON/CSV write도 포함된다. 기록상 no-new-metric evaluation은 0이지만 parity 시간이 0이라는 뜻은 아니다. 최종 CSV/JSON write는 phase 종료 후이고 별도 write timer가 없다. Cached anchor NPZ load는 model-load timer 이후/phase 이전으로 별도 시간 기록이 없다. 따라서 이 값들을 더해 정확한 전체 프로그램 wall이나 순수 inference 시간이라고 쓰지 않는다.
- 별도 **non-instrumented** 1회(10장/path) E2E 평균은 degraded `14.478164 s`, restored `16.526787 s`다. 후반 pass가 더 느리며 원인은 기록만으로 알 수 없다. Hook overhead, thermal throttling, contention 중 하나로 확정하거나 계측 전후 speedup으로 해석하지 않는다.
- CPU Torch/FAISS threads 4, batch 1, bank 245,392 x 1,024, float32 vector storage 약 0.936 GiB다. 이 값은 peak RSS/VRAM이 아니다. CUDA/생산라인 throughput/p95를 측정하지 않았다. 기존 full110 3563.561 s는 범위가 다르므로 여기 latency와 나눠 scaling을 주장하지 않는다.

### 조건부 복원: 실측 부품으로 계산한 모의 비용

같은 non-instrumented phase에서 tensor preprocessing을 포함한 detector만 사용하고 공유 RGB preprocessing은 양쪽에서 제외했다. Instrumented와 비계측 수치를 섞지 않는다.

`T_raw=14.359707980`, `T_SR=1.712624260`, `T_rest=14.696307190` 초.

`T_always=T_SR+T_rest=16.408931450`

`T_conditional=14.359707980 + p * 16.408931450`

| 가정한 p | 조건부 비용 s | 항상 복원 s |
| ---: | ---: | ---: |
| 0 | 14.359708 | 16.408931 |
| 0.25 | 18.461941 | 16.408931 |
| 0.5 | 22.564174 | 16.408931 |
| 0.75 | 26.666407 | 16.408931 |
| 1 | 30.768639 | 16.408931 |

이 모델에서 strict 절감은 `p < 0.124884638`일 때뿐이다. p와 trigger 정확도는 측정하지 않았으며 조건부 시스템을 실행한 결과가 아니다. p=0의 가상 최대 절감을 실제 성과로 쓰지 않는다. 음성 gating 결과를 비용 계산으로 뒤집지 않는다.

### 정확검색 효율 최적화의 가능성

Thread/query batching은 조사 가치가 있다. 가장 큰 measured stage를 겨냥하고 bank와 exact L2 정의를 유지할 수 있기 때문이다. 다만 현재도 **이미 한 이미지의 28x28=784 patch query를 한 번에 검색**하며 FAISS threads도 4다. 단순히 “batching을 추가”하거나 thread를 늘리면 빨라진다고 할 수 없다. Memory bandwidth/cache/BLAS 실행 경로와 oversubscription에 따라 느려질 수 있다.

향후 허용할 비교는 같은 bank/query/정확검색을 고정한 thread 수 및 query chunk/여러 이미지 query 묶음의 latency·메모리·prediction parity다. 저장 NPZ는 maps/scores이지 test embedding cache가 아니므로 이것만으로 FAISS를 재실행할 수 없다. 원래 query feature를 고정·보존하는 별도 준비가 필요하다. 이번에는 feature 추출/검색 benchmark, coreset, bank 축소, ANN 전환을 하지 않았다. 이전 REPORT의 bank/coreset 제안은 이번 검토의 선택 과제가 아니다.

## PCB 실행 가능성: 파일은 준비됐지만 FOV 판정이 빠져 있다

공식 CSV의 pcb2 train normal 901장을 lexical 정렬한 뒤 기존 `split_train_calibration(901, 0.8, 11)`을 적용하면 round(720.8)=721 fit / 180 calibration이다. Test는 공식 normal 100 / anomaly 100이다. Fit/calibration은 정상만 있고 path 교집합은 0이다. 전체 1,101개 이미지 파일의 SHA256 중복 그룹도 0이다. 이는 byte-identical 검사이며 유사 장면/촬영 연속성 누수까지 배제한 것은 아니다. 경로·분할 구성·CSV 해시는 [PCB_SPLIT_AUDIT.json](PCB_SPLIT_AUDIT.json)에 있다.

로컬 outputs/checkpoints의 results/metadata/split JSON을 구조적으로 읽어 pcb2 category 실행 기록을 찾았지만 0건이다(읽기 실패 0). Local Git의 pcb2 commit-message 검색도 일치 기록이 없었다. 이 제한된 탐색이 다른 폴더/schema/이전 장비의 미사용 증명은 아니다. **팀원 과거 사용 여부는 미확인**으로 남긴다. 타인에게 연락하지 않았다. 이번에 GT를 구조 점검했으므로 “GT도 전혀 본 적 없는 untouched category”라고 쓰지 않는다. Detector test 성능은 보지 않았다.

기존 raw checker는 anomaly GT가 canonical crop 뒤 완전히 비는지만 확인했다. 실제 1404x1070은 짧은 변 256 resize 후 335x256, 중앙 `[56:280,16:240]`의 224x224만 남는다. 같은 nearest mask 변환을 적용한 결과:

- 마스크 전체가 빈 영상: 0/100.
- GT 픽셀이 일부 잘린 영상: **9/100**.
- Resized GT의 8-neighbor 연결요소가 통째로 사라진 영상: **3/100**, 연결요소 총 4개. 이는 물리적 결함 개수나 detector regression taxonomy가 아니다.
- 부분 잘림 연결요소: 10개. 전체 100장별 GT 픽셀 손실률 단순 평균 1.946847%, 최대 39.334155%. 원본 픽셀 수와 다른 해상도의 픽셀 수를 비교한 값이 아니라 **동일한 full-resized mask에서 crop 전후**의 손실이다. Resize 자체가 만든 작은 GT 소실까지 측정한 값은 아니다.

사례별 값은 [PCB_CROP_AUDIT.csv](PCB_CROP_AUDIT.csv)에 있고, [실제 PCB/GT 그림](screenshots/pcb-crop-structural-examples.png)도 직접 열어 확인했다. 023.JPG는 손실 26.0%/연결요소 1개, 042.JPG는 39.3% 잘림이다. 녹색은 GT, 빨간 사각형은 기존 crop이다. 이 두 장은 구조 설명용 사후 사례이며 population estimate나 성능 근거가 아니다.

현재 crop image와 crop GT는 서로 정렬되고 모두 양성 영역이 남으므로 **중심 ROI에 한정한** metric 계산은 가능하다. 다만 이를 PCB 전체/모든 결함의 외부 검증으로 표현하면 안 된다. 기존 Hazelnut 연구의 metric 오류가 발견됐다는 뜻도 아니다. 파일 완전성만으로 whole-board validation ready라고 판단할 수 없다.

모델 실행 전 제안: 평가 대상을 중앙 ROI로 명시할지 full board로 정할지 먼저 결정한다. Full-board가 목적이면 full-FOV resize(종횡비 왜곡/작은 GT aliasing 확인) 또는 coverage가 보장된 tiling(좌표 역변환·중복/경계 규칙 필요)을 구조 기준으로 정한다. Letterbox를 택하면 padding valid-region 처리까지 protocol에 정의해야 한다. Test AUROC가 높은 방법을 고르거나 잘린 9장을 제외하는 방식은 쓰지 않는다. 결정한 image/mask/metric 좌표 변환을 synthetic tests로 확인하고 모든 method/train/calibration/test에 동일 적용한 뒤 새 protocol과 bank identity를 freeze한다. 기존 bank/calibration/전처리를 사후 수정하지 않는다.

준비 완료는 data/split/정상 분리/재사용 adapter와 기존 checkpoints까지다. 누락은 평가 FOV 결정, standalone frozen manifest, VisA runner 연결, 전용 PCB bank/정상 calibration, 실제 자원 smoke와 팀원 사용 이력이다. Bank storage 약 2.156 GiB 및 CPU 6.21 h는 이전 단순 추정이지 PCB/GPU 실측이 아니며 이 검토에서 실험 예산 확정값으로 쓰지 않는다.

## 다음 우선순위 하나: C. 검증을 막는 문제 수정

현재 먼저 해결할 것은 **PCB 검증 대상/FOV와 전처리 protocol의 미정의**다. A는 병목이 확인된 공학적 후속 후보지만 속도 개선은 아직 입증되지 않았다. B는 그럴듯한 외부 검증 후보지만 지금 whole-board 결과로 실행하기에는 준비가 부족하다.

다음 작업은 최대 세 가지다(이번에는 실행하지 않음).

1. 모델 실행 전에 central ROI 대 full-board 평가 목표와 coverage/GT 좌표 규칙을 결정하고, 선택한 하나의 전처리를 CPU 구조 테스트로 확인한다. 성능 비교로 선택하지 않는다.
2. 그 규칙으로 VisA adapter/runner를 연결하고 721/180/200 경로·해시·GT 사용 범위·bank/calibration identity를 별도 protocol에 freeze한다. 팀원 사용 이력은 확인 전까지 미확인으로 유지한다.
3. 이후 별도 승인된 고정-query exact-search 실험에서만 thread/query batching의 latency·memory와 score/map parity를 측정한다. 그 준비와 PCB baseline 실행 중 무엇을 먼저 할지 그때 예산으로 결정하며 이번 검토에서 자동 실행하지 않는다.

교수님께 제시할 현재 증거는 제한된 category의 저장 품질/localization 결과, 유지된 negative feasibility, 측정 범위가 명확한 CPU 병목, 원본 수치와 연결된 시연, 그리고 새 외부 검증 전에 찾은 crop 제한이다. 아직 detector 개선, 배치 최적화의 실효성, 생산라인 실시간성, CUDA 효율, 외부 category 일반화가 입증된 것은 아니다. 테스트 개수나 화면 외형으로 연구 수준·수상 가능성을 판단하지 않는다. 남은 공학적 기여는 평가 coverage를 명확히 하고 동일한 검출 의미를 유지하는 효율 개선을 실제 수치로 검증하는 데 있다.

## 검증과 재현

기존 환경 `137 passed (36.66 s)`, 별도 CPU/no-Torch·FAISS 환경 `136 passed, 1 existing torch-only skip (49.57 s)`. 두 환경 smoke는 2 result rows로 통과했다. 실제 Edge 수정 후 console/request/HTTP 오류 0, export 원본 bytes 일치, overlay on/off 원상 복귀, 정상 null, 부족 RGB 표시를 확인했다. 원본 source 30개 SHA와 기존 연구 파일/metric에 변경이 없다. Git diff 검사와 로컬 commit만 하고 push/main merge/배포하지 않는다. Graphify는 AST-only 갱신이며 연구 근거로 대신 쓰지 않았다.

PowerShell, repository root:

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts/smoke_test.py
.venv\Scripts\python scripts/serve_results_demo.py --port 8765
```

`http://127.0.0.1:8765`에서 열고 Ctrl+C로 종료한다. 이미 같은 viewer가 실행 중이면 재사용한다. Browser verifier는 선택적 Playwright가 설치된 Python 3.11 환경과 기존 Edge가 필요하다. 다음은 별도 terminal에서 수행하며 모델은 실행하지 않는다. 저장된 이번 검토를 덮어쓰지 않도록 새 output 이름을 만든다.

```powershell
$reviewReplay = 'analysis/profiling_results_demo/review-replay-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
.venv\Scripts\python scripts/review_saved_evidence.py --output $reviewReplay
.venv\Scripts\python scripts/verify_results_demo_browser.py --output $reviewReplay --phase after
```

선택적 browser 도구가 없다면 임시 CPU 환경에 Playwright를 설치해 해당 Python으로 마지막 명령을 실행한다. 이번에는 기존 별도 CPU 환경에서 했으며 `pyproject.toml`을 변경하지 않았다. Data/bank/checkpoint/raw predictions와 screenshot은 local-only다. Git checkout만으로 이 파일들이 생기지 않는다.
