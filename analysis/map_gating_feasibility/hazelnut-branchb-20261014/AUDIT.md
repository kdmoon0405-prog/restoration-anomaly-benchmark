# Map-gating follow-up audit

점검 완료일: 2026-10-15 (Asia/Seoul). 분석 protocol의 UTC 실행일은 2026-10-14다. 기존 종료된 연구와 별개의 Hazelnut 개발자료 후속 feasibility다. 과거 종료 기록·선택·full110 B/B-uncertain을 바꾸지 않는다.

## Git와 원격 확인 범위

- 작업 위치는 저장소 `research_code/`다. 시작 branch `exp/restoration-objective-study`, HEAD `47422007daf62c7d39385c7ea6f470d92acf15d2`; 시작 working tree는 clean이었다. 사용자 미커밋 변경은 없었다.
- `git fetch origin` 후 연구 branch와 upstream은 같은 HEAD였다(ahead/behind 0/0). 원격 main은 `ba92bc0`; 연구 branch는 main 대비 30 commits ahead, 0 behind다. 변경 목록과 관련 entry point를 확인했으며, 30 commits 전체 코드를 재검토했다는 뜻은 아니다.
- 새 로컬 branch `exp/map-gating-feasibility`에서 작업했다. upstream 설정·push·main merge·PR 생성·배포·Actions 재실행은 하지 않았다.
- 상위 AGENTS.md는 2026-09-19 수정본이다. 대화에 제공된 동일 지침을 적용했고, 변경되지 않은 프로젝트 handoff/연구 계획서는 다시 읽지 않았다. Graphify는 관련 위치 검색과 AST 업데이트에만 사용했다. Task-observer는 사용하지 않았다.

## Artifact 현황과 이번 검증

| 항목 | 상태 | 이번 직접 확인 | 이번에 하지 않은 검증/누락 |
| --- | --- | --- | --- |
| Historical Branch A Hazelnut | 기존 완료 | `outputs/legacy-patchcore/hazelnut-full391-test110-repro/`의 CSV/JSON와 clean/bicubic/swinir NPZ 존재 | 재평가·재추론·전체 재해싱 없음; 이번 후보와 섞지 않음 |
| Historical Branch A Screw | 기존 완료 | `outputs/legacy-patchcore/screw-full320-test160/` 동일 saved artifact 종류 존재 | 재평가·재추론 없음 |
| Branch B Hazelnut | 기존 완료, 이번 입력 검증 완료 | `outputs/fusion-patchcore/hazelnut-313x78-test110/`; 313 fit/78 calibration/110 test(40/70), seed 11, 224x224, split·bank metadata·sample order·labels·masks·유한 값 확인 | raw maps/embedding을 사용하지 않음; 이미 normalized인 maps를 다시 normalize하지 않음 |
| Branch B 정상 보정 | metadata 존재, calibration prediction 누락 | 기존 0.99 normal-only robust normalization과 pixel thresholds 재사용. Source run에 calibration prediction NPZ 없음 | 새 후보 calibration/F1/고정 FPR은 미실행이며 출력은 빈칸 |
| Full110 endpoint | 기존 GPU 실행 완료, 로컬 raw 누락 | tracked FULL_RESULT/EXECUTION_RECORD/derived 수치에서 B/B-uncertain 유지 확인 | `outputs/restoration-objective/hazelnut-full110-gpu/` 없음; NPZ/RGB 독립 재검증 불가. 다른 머신/개인 폴더 전체를 검색했다는 주장은 하지 않음 |
| RGB partial-restoration pilot10 | 기존 완료 | `analysis/partial_restoration_feasibility/PROTOCOL.json`, REPORT와 원본 `outputs/partial-restoration-feasibility/pilot10/` 확인: CSV/JSON, 5 NPZ, top-level PNG 50개 | 재실행·새 추론·수치 수정 없음. 성공한 방어 방법으로 채택하지 않음 |
| Dataset/bank/checkpoint | 현재 작업에 필요한 파일 존재 | Hazelnut train 이미지 391장/test 110장 목록 확인; 313-bank metadata와 두 artifact 존재, metadata spec 일치. Checkpoint identity는 기존 ledger/result SHA 일치 | bank/checkpoint 대용량 bytes는 다시 해싱하지 않음; ledger hash와 파일 존재를 실제 bytes 재검증이라고 부르지 않음 |
| 두 map-gating 후보 | 이번 saved-prediction 분석 완료 | protocol 저장 후 평가. 네 baseline array/evaluation/summary anchor 통과, 평가 차이 모두 0.0 | feature/image preservation mechanism, 독립 validation, 새로운 모델 학습/추론 없음 |

Input identity는 INPUT_MANIFEST.json을 따른다. 원본 prediction 네 개와 작은 results/split/summary/per-image/bank metadata, frozen runner/fusion/evaluator code를 해싱했다. 기존 pilot ledger에 있던 두 source NPZ·results·split·bank metadata·scientific code는 일치했다. Mean/max NPZ와 summary 등은 이번 digest를 기록했으며 옛 ledger에서 검증됐다고 부르지 않는다. Bank artifact hashes는 metadata의 기록값이다.

Prediction NPZ에는 sample path/normalized flag가 없다. 결과 metadata와 per-image CSV의 순서, 보존 runner 코드의 저장 경로, mean/max algebra를 결과 평가 전에 확인했다. Normal label의 mask는 모두 비었고 anomaly mask는 defect/background를 모두 포함했다. GT는 gate나 threshold를 정하는 데 쓰지 않았다.

## CI 원인과 깨끗한 환경 검증

[GitHub Actions run 37134244217](https://github.com/kdmoon0405-prog/restoration-anomaly-benchmark/actions/runs/37134244217)의 job 111235384721 로그에서 두 renderer 관련 test 수집 중 `ModuleNotFoundError: matplotlib`을 직접 확인했다. 당시 install 단계는 통과했고 pytest 단계는 실패, smoke는 skipped였다.

최소 정정: `dev` extra에 matplotlib 추가, workflow에 headless Agg 환경 지정. Workflow의 기존 `pip install -e ".[dev]"` 설치 경로는 유지했다. 테스트 삭제나 새 skip을 추가하지 않았고 GPU dependency를 dev/base에 넣지 않았다. 고정 passed 배지도 추가하지 않았다.

깨끗한 환경 첫 검증은 125 passed/1 skipped/1 failed였다. Matplotlib 문제 뒤에 숨어 있던 renderer의 torchvision 의존성을 발견했다. Shared `_canonical_transform()`의 PIL resize/crop 결과를 동일하게 유지하면서 torchvision import를 제거했다. Floor resize dimensions와 round-to-even center offsets를 그대로 적용했다. 기존 torchvision 0.29.0+cpu와 12개 synthetic sizes 및 실제 figure 두 sample의 RGB bytes가 모두 일치했다. 세 reference-byte SHA를 CPU regression test로 남겼다.

최종 검증:

- 기존 Python 3.11 venv: **128 passed in 35.54 s**, CPU smoke 2 result rows 통과.
- System-site packages 없는 새 Python **3.11.16** venv에 CI와 같은 editable `[dev]` 설치: **127 passed, 1 skipped in 30.31 s**, CPU smoke 2 result rows 통과. NumPy 2.4.6/Matplotlib 3.11.2; torch/FAISS 설치 없음. Skip은 기존 torch 전용 RRDB test이며 이번에 추가한 renderer/gating tests는 실행됐다.
- Windows에서 검증했다. Ubuntu GitHub runner의 실제 재실행은 아직 하지 않았고, 원격 CI 통과라고 주장하지 않는다.
- 두 saved-map 그림을 시각적으로 확인했다. 각 sample의 네 map은 동일 color scale이며 사후 설명용 최소/최대 delta 사례다.

## 실행 코드와 CI 정정의 구분

PROTOCOL.json은 metric 평가 전에 저장됐고 SHA256은 `eaf84392bb328e9bae58abffde41bfd265626dc4e4c1ec7c2c809065a933f299`다. INPUT_MANIFEST의 code hashes는 **실제 feasibility 실행 당시 코드**다. 당시 코드 8개 사본은 ignored `outputs/map-gating-feasibility/hazelnut-branchb-20261014/execution_source/`에 보존했다.

Frozen protocol bytes는 `.gitattributes`의 해당 PROTOCOL.json `-text` 규칙으로 Git의 line-ending 변환에서 보호한다. 최종 점검에서 원본 source hashes, frozen protocol SHA, 실행 코드 사본 8개, 새 NPZ의 두 gate 식과 유지된 scores/labels/masks, per-image 660행의 정상 AU-PRO 빈칸을 확인했다. 기존 full110/pilot/partial artifacts와 runner/fusion/evaluator의 Git diff는 없었다.

그 뒤 깨끗한 CI 검증에서 canonical helper의 dependency 문제만 정정했다. 이 변경은 rendering dependency 정정이며 gate·threshold·입력·metric·후보 선택을 바꾸지 않았다. Original frozen protocol/manifest, prediction/summary/per-image/그림은 다시 생성하거나 덮어쓰지 않았다. 현재 코드로 다시 분석할 때는 새 run-id에 새 protocol/code hashes를 기록해야 한다.

## 판정과 main 반영 제안

두 후보는 max를 넘지만 restored-only pooled AU-PRO를 넘지 못했다. Pixel AUROC 증가로 후보를 재선택하지 않는다. 음성 feasibility로 종료하며 추가 threshold/weight/feature/FFT 후보를 탐색하지 않는다. 정상 common-threshold 초과 rate가 같다는 관측은 새 후보의 calibrated FPR 또는 운영 안전성 증명이 아니다.

향후 승인된 PR의 변경 목록은 CI dependencies, shared CPU renderer/canonical parity fix, 두 gate 모듈·saved analysis CLI·tests·작은 분석 산출물·진행 기록이다. 우선 research branch를 base로 검토한다. Main에는 아직 기존 연구 30 commits와 관련 helpers가 없어 gating script만 따로 복사하면 안 된다. CI-only 정정과 연구 branch 전체 통합 여부를 분리해 검토한다. 이번 작업에서는 merge/PR 생성/push하지 않았다.

다음 작업은 REPORT의 전제를 따르는 별도 설계 검토다. 이 음성 결과가 추가 실험 자동 진행의 근거가 되지는 않는다.
