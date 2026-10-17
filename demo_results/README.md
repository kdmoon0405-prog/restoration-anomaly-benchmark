# Local saved-results viewer

Repository root에서 설치된 `[dev]` 환경으로 실행한다. 외부 서버/hosting은 없고 `127.0.0.1`에만 bind한다.

```powershell
python scripts/serve_results_demo.py
```

브라우저에서 `http://127.0.0.1:8765`를 연다. Category/defect/sample/variant 선택과 GT evaluation overlay를 사용한다. Ctrl+C로 종료한다. 모든 요청은 read-only이며 모델을 로드하거나 추론하지 않는다.

입력:

- `analysis/map_gating_feasibility/hazelnut-branchb-20261014/`: PROTOCOL, summary/per-image CSV.
- `outputs/fusion-patchcore/hazelnut-313x78-test110/`: results, per-image quality CSV, 네 baseline NPZ.
- `outputs/map-gating-feasibility/hazelnut-branchb-20261014/`: candidate NPZ 두 개와 results identity.
- 선택적 RGB: `outputs/partial-restoration-feasibility/pilot10/`의 protocol 및 bicubic/full_swinir PNG. 동일 source/bank identity를 확인한 열 장 subset만 표시한다. 나머지는 unavailable이다.

각 경로는 CLI `--analysis`, `--source-run`, `--raw-run`으로 지정 가능하다. 필수 파일이 없거나 bank/cohort/schema가 다르면 화면에 Unavailable을 표시하고 데이터 API를 차단한다. 파일이 없는 sample을 위해 복원 이미지를 생성하지 않는다. Candidate map fusion에는 고유 RGB/PSNR/SSIM/LPIPS가 없다. Image scores도 restored-only에서 유지됐다. Normal per-image AU-PRO는 해당 없음이다.

비교 anomaly maps는 sample 내 공통 scale, normalized discrepancy는 별도의 0..max scale, gates는 Boolean이다. GT overlay는 PNG 표시 단계에만 들어가며 gate 식에 GT input은 없다. 전체 110 목록을 제공하고 기존 사후 극값 그림을 population estimate로 포장하지 않는다. 개발 자료·음성 feasibility·candidate calibration 부재·미검증 위험 경보를 화면에 표시한다.

Export: summary CSV 저장 링크, `/api/catalog`의 read-only JSON 저장, PNG에서 우클릭 이미지 저장. Screenshot은 브라우저 screenshot 기능을 쓰고 Ctrl+P로 현재 view를 인쇄/로컬 PDF 저장한다. 민감한 데이터가 포함된 screenshot은 별도 공유 판단이 필요하다. Git에는 원본 NPZ/RGB/bank/weights를 넣지 않는다.

mean/max variant 선택 시 해당 map도 별도 panel에 표시한다. 브라우저 연결이 없는 환경에서는 HTTP/PNG/JavaScript 문법만 검증할 수 있으며 실제 화면·선택 조작·인쇄 레이아웃 검증과 구분한다. 이번 검증 범위는 [DEMO_VERIFICATION.md](../analysis/profiling_results_demo/hazelnut-ten-20261015/DEMO_VERIFICATION.md)에 기록했다.

후속 실제 Edge 검토는 [REVIEW.md](../analysis/profiling_results_demo/review-7ee19a9/REVIEW.md)에 있다. 표 내부 가로 스크롤, Viridis/GT/gate 범례와 CI·단위 설명을 추가했다. API 설명 필드와 favicon 204만 확장했으며 원본 예측/지표/gate는 바꾸지 않았다. 실제 PNG와 CSV download를 확인했고 screenshot은 dataset RGB 때문에 로컬에서만 보관한다. `scripts/verify_results_demo_browser.py`는 선택적 Playwright/기존 Edge가 있는 환경에서만 실행하며 일반 CPU tests에 Playwright는 필요하지 않다.
