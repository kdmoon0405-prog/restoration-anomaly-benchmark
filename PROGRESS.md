# Progress

## 2026-11-26 · 보고서 작성 인계와 로컬 연구 기록 반영

[연구 결정 기록](docs/RESEARCH_EVOLUTION.md)에 실험 선택과 변경 근거 61개 단계를 게시했다. [추가 근거](results/local-evidence/README.md)에 개발 24장과 평가 50장의 고해상도 공개 사진, 촬영·원판독 기록, 개발 확대 비교와 회전 재시도 그림을 연결했다. [작성 인계](docs/REPORT_AUTHOR_HANDOFF.md)에서 본문 순서와 사용할 근거를 확인한다.

## 2026-11-25 · 팀 2 최종 결과 자료 통합

실험 코드, 분석 결과, 담당자 반환 기록과 보고서 그림을 main에서 연결했다. 핵심 순서는 [연구 과정](results/RESEARCH_HISTORY.md), 사진과 지도는 [그림 모음](results/FIGURES.md), 상세 결과와 수치표는 [보고서 자료실](results/README.md)에 있다.

- 기본 bank 24조건은 두 품목과 seed 11·23·37이다. 영상 단위 AUROC 재계산값을 수신 값과 맞춰 봤고, Bicubic bank 확장 4조건과 함께 통합표를 기록했다.
- 실물 50장은 참조·보정 4장, 평가 46장으로 구성한다. 같은 조명 기준 정렬의 같은 세션 개발 결과와 고정 결과를 함께 수록했다. 회전 재시도의 정렬 복구 2건도 품질 재촬영 판정으로 남았다.
- 원본 판독 46장 중 두 사람의 동의는 24장, 불일치는 22장이다. 추가 재확인 이후 잠정 분포는 잘 보임 20, 어려움 10, 보류 16이다. 저조도·흐림 사진과 별도 대체 촬영 10쌍에서 두 사람이 모두 잘 보인다고 답한 사진은 첫 촬영 0장과 대체 촬영 5장이다.
- 상세보고서에 동일 위치 복원 비교, 정상 bank에 따른 지도 변화, VisA PCB 운영점 전환, 실물 기판 촬영과 정렬 결과를 포함했다.
- 기록된 성능 범위에는 새 실험을 추가하지 않았다. 복원 전후 사람 판독과 고정 자동 검사 성능을 동시에 비교하는 실험은 같은 사진으로 별도 설계할 수 있다.

## 이전 기록


Date: 2026-09-20


## Noise v2 반복 분석과 지혁 오프라인 전달 (2026-11-11)

주형 handoff/juhyung@ba4672d의4run32조건, 공개80파일을 검토했다. 기존 v1 split/checkpoint/vendor와 source40d57dd,calibration q0.99와 공유LR hash를 확인했다. 관련27tests와 CPU smoke2행이 통과했고 직접 확인한scalar그림·paired CI·per-image 표를 생성했다. Master165행/13groups이며 이전133개entry의ID와값을 유지했다. 상세 결과는 analysis/noise_repeatability_20261111/REVIEW.md다.

Hazelnut 두 protocol의v1_bank_dir만 상대경로 사본으로 변환하고 source/execution/public hash를 연결했다. 새 source는code 내용 동일성에 더해 Gitblob/CRLF checkout 형식을 기록한다. Source 줄바꿈 및 Windows에서POSIX절대경로 판별 오류는 수정 후 재검증했다. Raw array는미수신이며 pooled metric은저장 point estimate를사용했다.

지혁용incremental public bundle은83ef04e prerequisite,61c2170 tip이다. 새 수신 저장소에서17tests/CPU smoke2행을 확인했고 기존데이터ZIP을재사용하는1.9MB offline packet을 준비했다. docs/followup_20261111/에 담당자별프롬프트와private 결정반환 규칙을 작성했다. 실제 query는Bicubic/SwinIR이며 이전 자연어의clean/restored표현을 정정했다. 주형의다음유한queue는저장map image-score집계대조,지혁은bank-domain24+4다. 두사람private결정원본과 실제지혁GPU실행은추가반환을기다린다.

## 선택 PCB 공간 분석 반환 검토 (2026-11-10)

주형 handoff/juhyung@52b4c23의 두 receipt와 공개6파일을 검증했다. 사전 선택9보드×3variant와4-connectivity36요소의 scalar CSV 정합성, source/GT/map/calibration 연결을 확인했다. 기존 raw 배열의 무결성 receipt를 연결했고 이번 로컬 native 재계산은 수행하지 않았다. RGB/GT case PNG9개는 미수신이다.

단위를 나누어 재계산하면 SwinIR의 보정 seam gradient는 Bicubic보다9/9 높지만 raw gradient와 seam/non-seam 비율은9/9 낮다. 기존 geometry_candidate의2/3에서 raw gap 감소가 함께 관측돼 명칭만으로 공간 원인을 확정하지 않는다. Taxonomy와 master133조건/9groups는 유지했다. 관련17tests, CPU smoke2행, 새scalar그림 직접확인과 diff검사를 통과했다. 결과는 analysis/pcb_spatial_return_20261110/와 docs/PCB_SPATIAL_RETURN_REVIEW_20261110.md에 있다.

## CPU 제어 연결과 후속 GPU 반환 검토 (2026-11-10)

별도 exp/inspection-controller-cpu에서 controller·software replay·native-map reader·category transfer receiver·FPR plateau 진단을 구현했다. Synthetic6cycle과 저장 PCB score600개 replay를 완료했다. 물리 장치와 실제 모델은 실행하지 않았다. 전체674pass/3skip, 관련28pass, 추가score/receiver5pass, CPU smoke2행이다. 기존 RAM 전제조건2개와 optional MVTec fixture1개 skip을 보존했다.

새 진단27파일과 map ZIP 최상위51파일 hash를 확인했다. Native27array의 SHA/1070×1404/float32/finite를 bounded chunk로 확인했다. 실제9case spatial analysis는2GiB OS 여유를 포함한 약2.39GiB 기준에 미달해 BLOCKED_MEMORY다. Array/GT/그림은 비공개로 보존했다.

Timing12pass/44call 재집계가 일치했고 small-sample batch4speedup은1.498988이다. 같은 empirical FP3/100에서도 TPR은 Bicubic0.62~0.82,SwinIR0.59~0.70 범위여서 단일 matched-FPR 지점으로 원인을 확정하지 않는다. Scalar600개와 affine-normalization 판정 일치를 확인했다. Screw endpoint 원본metadata에서seed11/train320/fit_performedfalse를 확인해 별도master에 반영했다. Point metrics와133조건/9groups는 유지했다.

지혁patch는 격리해서 검토했다. Fake test의 실제weight/Git/RAM 의존성을 test fixture만 수정해11pass를 확인했다. CPU consumer와 동명인 실행 측 analyzer, source provenance와ROI gap/export 연결은 owner에게 전달한다. 필요한 두 category만 private813040630B ZIP으로 만들고 새directory의1177파일 수신 검증을 완료했다. Publisher archive 원본 checksum은 미확인으로 유지하며 private transfer checksum과 구분했다. 데이터/가중치/bank는 공개하지 않는다.

보고서는 docs/GPU_FOLLOWUP_REVIEW_20261110.md, code는 scripts/의4개새CLI와src/sr_anomaly/의2개모듈, 수치는analysis/cpu_control_spatial_20261109/와analysis/gpu_followup_20261110/다. 원본checkout과private노트는 별도로 보존한다.

## 주형 GPU 전체 결과 반환 검토·통합 (2026-11-09)

Incoming 4c2fc40의 PCB 전체 cohort, 실사형 56조건, Screw endpoint 결과를 별도 worktree에서 검토했다. ZIP의 213개 명시 파일 hash, PCB 1140unit/54720query, runtime source26개, image calibration59개와 저장 score 기반 Image AUROC/F1을 확인했다. 원본 map 배열은 원격에 보관돼 있으며 pooled 지표는 저장 수치를 사용한다.

PCB의 SwinIR−Bicubic pooled AU-PRO는+0.00483155, 사례 평균 차이는+0.00372962였다. Post-hoc conditional per-image CI는[+0.00060021,+0.00671106]이다. 고정 threshold에서 미검은 Bicubic29/100→SwinIR46/100, 오검은3/100→1/100이었다. Regression33개는 suppression5/geometry_candidate28로 분류됐다. 선택9개 사례의 원본map27개를 요청할 manifest를 준비했다.

실사형의 Real-ESR 계열 최고는 전체 정밀도로11/12조건이다. 나머지 Screw blurσ0.8은 SwinIR이0.000050317 높아 세 자리 반올림 동률과 구분했다. LPIPS 상관은 조건 단위 기술통계로, Screw endpoint caseC와 함께 해석한다. Source CSV와 평가 정의를 보존했다.

신규63조건을 기존70행과 분리된 protocol로 집계해 master133행/9groups와 수치PNG2개를 만들고 직접 확인했다. 신규 read-only 분석·보고 테스트15pass/CPU smoke2행, peer 수정 branch 관련89pass/1skip이다. Synthetic RAM fixture의 잘못된 mock 대상은 실제 getter로 정정했다. Production guard는 동일하다.

별도 source fix branch는 exp/juhyung-return-review-fixes, CPU 분석 branch는 exp/juhyung-results-analysis다. 분석 보고서는 docs/GPU_RETURN_REVIEW_20261109.md, 수치는 analysis/gpu_return_20261109/다. 다음 임무는 주형의 저장map 부분 전달·score 진단·작은 exact 검색 benchmark, 지혁의 bank-domain 완료·matched Bicubic 대조군, CPU의 반환 통합·map 분석·장비 인터페이스 초안이다.

## CPU bank/query domain 추가 결과 (2026-11-09)

Public base b247500 위의 exp/cpu-bank-domain-study에서 신규 36조건과 test prediction 4,860건을 완료했다. 기존 정상 HOG bank의 같은 patch ordinal 4,096개를 사용해 Bicubic/SwinIR 정상 bank 12개를 fit하고 24조건을 평가했다. 이후 50:50·동일 용량 규칙을 결과 계산 전에 고정한 혼합 bank 6개와 12조건을 추가했다. 비교표 48조건 중 clean-bank 12조건은 재사용이다. 앞선 CPU 24조건과 합친 고유 조건은 60개/prediction 8,100건이며 고유 test 영상 270장과 구분한다.

전용 bank끼리의 SwinIR−Bicubic 평균 pooled AU-PRO는 Hazelnut +0.027039, Screw −0.004475였다. 보조 conditional per-image CI는 두 category 모두 0을 포함한다. 혼합 bank는 전용 bank 대비 네 category/query cell 평균이 모두 낮아 성능 개선 성공으로 분류하지 않았다. HOG 탐색 결과이며 PatchCore/PCB로 일반화하지 않는다. Test GT는 prediction 저장 후 평가에서만 사용했다.

SwinIR cache 981장 중 614장은 byte 검증 복사하고 부족한 정상 fit 367장만 신규 복원했다. 일시적 Windows checkpoint 교체 오류는 IO retry만 수정해 재개했고 중단 기록·AST 동등성·원본 완성 cache를 보존했다. 최종 cache elapsed/peak는 마지막 재개 process 범위다. HOG/evaluation/fusion/metrics/dataset 원본 5개 source는 b247500과 동일하다.

analysis/cpu_bank_domain_20261109/에 48조건 표·seed/사례 delta·수치 PNG 2개·source manifest·master 70행/5 protocol groups를 저장했다. 신규 36조건만 master에 추가했다. 전체 pytest 643 pass/1 skip(310.98s), 최종 분석/export 6 pass(5.25s), 기존 CPU smoke 2행 통과다. 두 PNG를 직접 확인했고 CI 그림의 reference 제목을 수정했다. 첫 render는 로컬에 보존했다. 상세 결과와 재현 명령은 docs/CPU_BANK_DOMAIN_RESULTS_20261109.md다.

코드·테스트·공개 문서·수치만 새 branch로 전달한다. Dataset/RGB/GT/rawmap/bank/weights/개인 노트는 local-only다. 원본 exp/profiling-results-demo와 GPU 구현 branch를 보존한다. 다음 연구 우선순위는 GPU PatchCore의 같은-query 정상 bank 적응 결과와의 대조다.

## 실제 CPU 연구 확장 완료 (2026-11-08)

Branch exp/cpu-research-expansion에서 saved PatchCore spatial/operating 분석과 실제 HOG-kNN/SwinIR 대조 실험을 완료했다. Hazelnut110·Screw160, seed11/23/37, Clean/Bicubic/Unsharp/SwinIR24조건, test prediction3240건이다. SwinIR는 고유614개 calibration/test RGB를 CPU cache로 한 번 복원하고 기존 HOG bank6개를 재사용했다.

Unsharp−Bicubic의 평균 pooled AU-PRO 차이는 Hazelnut−0.003956, Screw−0.026889이고, SwinIR−Bicubic은+0.072742, +0.133538이었다. 두 조건 모두 PSNR/SSIM이 증가했다. Sample-level 감소도 모두 보고했고 HOG의 낮은 절대 성능과 이미 탐색한 category의 한계를 함께 기록했다. 같은 영상의 seed 반복은 독립 이미지 수로 늘리지 않았다.

기존 저장 맵의 top1% pixel recall delta는 Hazelnut−0.116%p, Screw+24.309%p다. Branch B의 기존 정상 calibration 운영 지점에서는 mean fusion FN5→3, FP0/40이었다. Primary pooled metric과 supplementary 운영 지점을 분리했다. 공개 numeric summary/그림은 analysis/cpu_research_20261108/, 상세 결과·명령은 docs/CPU_RESEARCH_RESULTS_20261108.md다. Master는34행/4protocol groups이며 raw/data/RGB/GT/bank는 local output에 보존한다.

전체 pytest623pass/3skip(269.50s), 기존 CPU smoke2행을 확인했다. 두 skip은 실제 RAM 사전조건, 한 skip은 optional dataset 부재다. Source 초기화와 Windows 임시 폴더 문제를 해결한 뒤 검증했고 초기 실패 로그를 보존했다. 실행 당시 source_worktree_dirty=true, base1f0c801과 실제 source/table digest를 기록했다. GPU 담당 source·기존 결과·Capsule은 보존했다.

## CPU bank-domain analysis, input transfer and reporting (2026-11-02)

Implemented read-only analyze_bank_domain_study.py and its analysis module. The five-file producer contract binds config/provenance and summary/per-image CSVs, preserves family/protocol/category/seed, verifies the complete 2x2 paired cohort, deduplicates identical run copies and rejects conflicting conditions. Same-query bank quality is counted once. Dataset pooled AU-PRO remains a stored point estimate; per-anomaly-image paired delta CI is supplementary and within-seed only. Three seeds of the same images are not treated as independent image observations. The existing Hazelnut percentile/paired-bootstrap helper was moved unchanged into analysis_statistics.py and shared; inference/evaluator semantics were not changed.

Added category-only MVTec transfer preparation/verification, ZIP manifest receipt cache and manifest-driven research master reporting. Original local Hazelnut/Screw/Capsule inputs are present: normal train391/320/219, official test110/160/132, seed11 normal fit/cal313/78,256/64,175/44. Source bytes and notices were preserved; local-only category ZIPs verify575/603/464 source entries including duplicate root notices. No RGB/GT decoding, model inference or actual anomaly metric was performed. Official dataset/CC BY-NC-SA notices are linked in the handoff. Data archives/inventories remain outside Git.

Existing stored thesis tables generate10 actual metric rows in3 protocol groups without recomputation. The new ZIP receipt records5 supplied manifest matches for Jihyuk's existing return and reuses the cached receipt on the second call; this is not independent GPU/array/source acceptance. New bank-domain results have not arrived, so none of their research numbers or figures were fabricated. Both GPU execution owners keep their scripts.

Validation:37 related tests passed(4.57s), full suite603 passed/3 skipped(256.99s), existing CPU smoke2 rows passed, git diff --check passed. Two existing subprocess tests skipped with1827414016bytes available versus2186018816bytes required including the unchanged2GiB reserve; one optional MVTec dataset check skipped in this data-free code checkout. All20 fit-source and7 reference hashes still match the integration base. Existing GPU bank/model/metric/geometry/seed/fusion code was not modified. Python3.11 environment was explicitly reused from the original checkout.

New handoffs: docs/BANK_DOMAIN_ANALYSIS_HANDOFF.md and docs/CPU_DATA_REPORTING_HANDOFF.md. Local verification/logs: outputs/verification-20261101/. The first interrupted full-suite attempt had no completion record; the fresh Nov02 run above completed. Only code/tests/config/docs and this public progress entry are in the CPU branch; original checkout/private evolution notes are updated separately and are not included in its commit.

## Reviewed-bank reuse integration implemented on CPU (2026-10-31)

Added run_pcb_reuse_inference.py, its small scope-specific module/reader,34 new tests and PCB_BANK_REUSE_INFERENCE_HANDOFF.md. The explicit reviewed bank-run remains external/read-only: no1GiB copy, normal-fit RGB/feature stream or new patch bank. Its historical865f26a/dirty=true and fit receipts are preserved while inference gets a separate source record. Shared20 fit source/7 reference bytes match; the new execution binds24 source files. Admission pins reviewed bank bytes, validates payload/settings/indices/provenance and permits a newer compatible inference commit. JSON remote bank/data/checkpoint paths are not followed as inputs.

The fixed integration processes calibration1/test-normal1/test-anomaly1 across3 variants:bank bind1,query432,maps9,reference RGB2/produced tile RGB6. It reuses native map overlap mean/score max and existing adapter/transform without GT or statistics/threshold/metric generation. New actual/fake kinds and a dedicated reader preserve old synthetic/full guards. Bank/source invariance, same-RGB prediction/spooling, sequential payload validation and success/error cleanup are checked. Current engineering choice is an explicit external bank reference; future full/portable contracts and independent reviews remain pending.

Final full pytest568 passed/3 skipped(193.16s);34 final new tests passed and CPU smoke2 rows passed. Existing two subprocess tests skipped at996282368/996286464bytes available versus2186018816bytes required including unchanged2GiB reserve; MVTec-data test also skipped. No resource override was used. Runtime import-denial and tiny fixtures cover mandatory new behavior without real models/FAISS. Initial tuple/list serialization comparison and one shell JUnit argument issue were corrected; final logs preserve prior attempts. Metadata-only actual-bank preflight rejects absent NPY files before models, rather than fabricating local bank validation.

Inference-specific plan8.687914GiB available RAM/1.161637GiB new-output free disk is an allocation scenario, not a measured bound. The actual bank/model/GPU integration has not run here; no full executor is enabled. Independent design GO plus fresh source/bank/resource/CUDA checks precede the GPU's one integration. Publication and clean-receipt evidence is recorded locally after audit. Existing scientific definitions, old protocol/fit/source artifacts and prior native rehearsal status are unchanged.

## Real normal-fit bank path ready for separate CUDA execution (2026-10-29)

Added scripts/run_pcb_fit_bank.py and pcb_fit_bank.py as a separate fit-only path. Static preflight binds frozen metadata/source/submodule/checkpoint/fit file hashes without importing Torch/FAISS or decoding RGB; opt-in execution repeats bindings and RAM/disk checks and requires live CUDA. It reuses the existing model factory, input RGB callback, feature_chunks and bounded_bank writer/loader. Only721 normal-fit parents enter extraction; no cal/test RGB or GT, restoration, scorer binding, predictions, thresholds or metrics. The existing synthetic-only full producer and full-pilot guard remain unchanged.

Observed/validated expectation is27132672 vectors, stored262144x1024 float32, with the frozen selection SHA and unchanged geometry/batch/seed/chunk rules. Saved payloads are reloaded and checked chunkwise; progress and source/input/resource/timing receipts remain separate. Actual-fit integrity flags cannot promote CPU fixtures or full-pilot approval. Fit RAM/disk estimates are6.204393GiB available including2GiB reserve and2.064453GiB disk; these are planning scenarios, not measured actual-fit peaks. The existing factory also constructs SwinIR but no restoration is invoked.

Final new tests34 passed; final full pytest536 passed/1 optional MVTec-data skip in185.59s; existing CPU smoke passed with2 result rows. Earlier related suites179/181 passed before the final approval-flag test. New deterministic tests cover tiny fit/reuse, runtime import denial through static preflight, source/input/order/selection/metadata changes, invalid streams, shortage, CUDA failure and cleanup. The fresh-process test uses this worktree's explicit src path; vendored-source guards have separate fake-source tests so CI does not require model submodules merely to run CPU fixtures. Delivery commands and resource/lifecycle/return scopes are in docs/PCB_REAL_FIT_BANK_HANDOFF.md.

An actual static preflight checked721 fit RGB file hashes,20 bound source files,7 references and both pinned checkpoints, then blocked before models/bank arrays: available RAM2626314240bytes versus required6661915776bytes. CUDA was not checked by this static preflight. That local snapshot does not predict the GPU host's current availability. No real PCB fit/model inference or new research metric ran; model/metric tests used synthetic fixtures. Publication and receiving evidence is recorded separately after audit; full cohort producer/postprocessing/final approval remain pending.

## Read-only full-cap return checker ready on CPU (2026-10-28)

Added scripts/review_pcb_fullcap_probe.py, its small review module, 73 deterministic tests and docs/PCB_FULLCAP_RETURN_REVIEW.md. The new kind has a separate checker; the old limited-smoke checker and producer/model/evaluator bytes are unchanged. Explicit local reference metadata is required for a passing review, with no automatic reads of recorded remote reference/checkpoint paths. Source commit/canonical bindings and raw-byte bindings, six query records, sixteen ordered calls, summaries, RSS/CUDA domains and cleanup contracts are checked. Status-file SHA is a computed receipt, separate from the three verified artifact hash links. Missing/deleted arrays remain unverified; every classification keeps full approval false.

Final related tests126 passed(39.39s); full pytest502 passed/1 optional-data skip(139.36s). Fresh-process runtime import denial covers a complete metadata review plus CLI help; the actual tiny injected producer is rejected as CUDA full-cap evidence. Existing CPU smoke passed with2 rows and git diff --check passed. Known83ef04e execution-source bindings and the existing reported-CUDA limited reference are compatible; its11 omitted arrays remain unverified. Evidence is local-only outputs/pcb-fullcap-review-readiness-20261028-230346/. No new full-cap GPU return, actual model/FAISS/native run, bank/metric/geometry change, full executor activation or push. Next is real returned-metadata review followed by separate actual fit/selection, full producer, current resource and final-approval gates.

## Bounded full-cap synthetic resource probe implemented (2026-10-27)

Added a separate no-execute-by-default engineering CLI/module and30 tests. It validates accepted reported-CUDA limited-smoke metadata, bound model/source/submodule/checkpoint bytes and current RAM/disk before allocating. Opt-in runs only a synthetic262144x1024 float32 payload and2 generated RGB tiles across3 unchanged variants(6 predictions), retaining CPU exact scorer behavior. It never fits a PCB bank, selects indices, uses GT or exports predictions/metrics; full-bank/full-pilot approval flags remain false. Temporary payload is removed only after successful query/owned-cleanup/monitor checks; failures retain evidence. No full executor or scientific source change.

Full pytest429 passed/1 optional-data skip(180.96s); final30 new tests pass with backend imports explicitly denied(5.57s), including scope/drift/shortage/failure/cleanup guards. Existing CPU smoke passes. Local no-execute preflight plans8.283056GiB including unchanged2GiB reserve and blocks inadequate current RAM before NPY/model creation. The prior temporary no-Torch environment failed startup and was not repaired; import-denial checks used the normal Python. See docs/PCB_FULLCAP_RESOURCE_PROBE_DRAFT.md. The accepted old limited resource ZIP remains metadata-only locally; this new artifact kind cannot be passed to the old limited-smoke checker. No actual model/FAISS/GPU/native run here; full real bank/producer/resource approval remain pending.

## Audited two-operator delivery preparation (2026-10-27)

Reviewed all four linear commits from public bb22cf8 through ef2ca86, including40 historical blobs across27 paths (largest64937bytes). No forbidden input/private/binary path or credential signature found; original private79a1c0f history is not an ancestor. Required13 files,13 frozen geometry artifact/source checks, pinned submodules and36 current byte-bound source/reference hashes verified. pcb2 bundle/backbone/SwinIR HEAD requests return200 with274645313/138223492/17225941bytes respectively; payloads were not downloaded by this check.

Fresh full CPU pytest397 passed/3 skipped(205.37s), CPU smoke2 rows passed. Two real generated-worker tests skip under unchanged actual-RAM guard; focused confirmation1 passed/2 skipped records1848459264/1848520704bytes available versus2186018816 required. The third skip is optional MVTec data. No guard, production code, model, metric, bank, geometry or frozen hash changed. Added docs/PCB_TWO_OPERATOR_HANDOFF.md: established operator instruments the fixed limited smoke; new operator verifies setup/inputs and runs independent raw smoke. Neither task approves full pilot or strict cross-device parity. Publication and fresh GitHub receipt must be verified separately; no actual model/native execution here. Detailed local evidence remains ignored under outputs/publication-20261027-124910/. Private rationale stays outside the published history.

## Read-only returned-resource consistency review (2026-10-20)

Added scripts/review_pcb_model_resources.py and a metadata/hash-only checker for the future limited GPU resource-smoke return. It checks source/reference coverage, completion/hash chains, fixed subset/parent/variant inventory, RGB receipts, call counts, timing arithmetic and RSS/CUDA counter consistency. CPU/injected fixtures are not GPU evidence; omitted payloads remain explicitly unverified. Even matching hashes do not independently validate array contents or attest remote execution. No actual CUDA resource return exists yet and no full-pilot approval is issued.

Final full pytest399 passed/1 optional-data skip(178.95s), no-Torch/FAISS reviewer23 passed(13.67s), existing CPU smoke2 rows passed. The local CPU preflight-only folder is correctly rejected as incomplete execution evidence. No existing scientific/model/geometry/guard/protocol source changed relative4b3368e. See docs/PCB_RESOURCE_RETURN_REVIEW.md; test logs remain ignored under outputs/resource-review-*.log. Local-only rationale/progress mirrors are maintained separately. No actual model/index/GPU/native inference, performance result or push.

## Frozen inputs and limited resource-smoke tooling (2026-10-20)

Added hash-bound native RGB/test-GT callbacks and a model-free input audit. Actual local1101 RGB files and100 anomaly GT files match frozen hashes;100 normal test masks remain implicit zeros. Full decoded audit passed1101 native RGB/200 test masks, fixed721/180/100-normal/100-anomaly composition,332 four-connected GT regions/payload498756960bytes. RGB/GT structural verification68.733/4.794s is not inference runtime. Earlier low-RAM blocked decode and hash-only evidence are preserved; later sequential decode passed its single-board96,145,920byte plan + unchanged2GiB reserve. Actual native180/200 map-stack guard20.42GiB is not bypassed.

Added opt-in limited-smoke resource instrumentation around unchanged preflight/execute: disjoint synchronized phase timings, RSS samples vs OS lifetime high-water vs CUDA counters, fresh source/reference/official/checkpoint guards and preserved partial failures. Local CPU preflight passes with factory/model_execution_started=false, torch2.14.0+cpu/cuda_available=false. No actual model/index/GPU inference, bank/calibration, degradation or anomaly-performance result. Limited37632-vector resource evidence still cannot validate full262144 bank.

Final pytest376passed/1 optional-data skip(221.69s), CPU smoke2 rows passed, no-Torch binding/budget53passed and resource29passed; protected science/model/geometry/guard/protocol files unchanged. Tiny unit tests now isolate host RAM, while real subprocess tests use actual resource checks (none skipped in final run). First full attempt's20 RAM-dependent unit failures and one OneDrive-folder atomic replace error are retained; final OS-temp test run passes without altering production statewriters/guards. See docs/PCB_INPUT_BINDING_HANDOFF.md, docs/PCB_MODEL_RESOURCE_SMOKE.md and analysis/pcb_input_binding/implementation-20261020/VERIFICATION.md. Original research checkout preserved; private rationale note remains ignored. No push or full approval.

## Align board/rehearsal memory accounting (2026-10-18)

Correct the board evaluator's post-allocation double budgeting: subtract only already-filled float64 maps/bool masks from the remaining available-RAM requirement. Board and rehearsal now reuse one guard, preserving the fixed2GiB reserve and total envelope-plus-reserve cap. Small synthetic checker caps explicitly include1GiB payload plus2GiB reserve, recorded in their protocols. Native pre-allocation requirement remains21923497568bytes; no native allocation, model execution or full approval. Evaluation/metric/model/geometry/bank/protocol sources are unchanged outside these technical guard wrappers.

Full pytest326 passed/1 optional-data skip(186.46s); focused tests68 passed; no-Torch/FAISS boundary/producer tests46 passed; existing CPU smoke passed(2 rows). Exact-boundary/one-byte-short, invalid inputs, NumPy overflow and already-live-array integration checks pass; existing unchanged-evaluator equivalence and region-explosion guards remain tested. See docs/PCB_MEMORY_GUARD_ALIGNMENT.md. Earlier native ZIP evidence belongs to its recorded older source revision and is not rewritten. Real RGB/GT binding, model/index RAM/VRAM/runtime and producer disk review remain separate full-pilot blockers. No push.

## Streaming producer candidate, fake-process integration (2026-10-17)

Local exp/pcb-full-producer-integration from public bb22cf8 adds an injected synthetic-only streaming producer, lossless already-produced test RGB spool/reader and seven-worker integration checker. Reuses bounded-bank streaming, canonical map mean/max tile score, v0.6 calibration/quality and unchanged exact evaluation; no real factory/full CLI or old guard change. Small generated2-fit/2-calibration/2-test fixture produces16 vectors/7 retained,12 maps, one bank bind and no second quality transform. Seven workers exit0, owned fake references release and2258944 RGB spool bytes are cleaned after validation. Maximum individual OS lifetime peak109326336 bytes is small-scenario-only, not native/VRAM/global peak. All14 executable source hashes match; pre-commit run source bb22cf8/dirty=true is preserved.

Full pytest294 passed/1 optional-data skip; no-Torch/FAISS new tests14 passed; existing CPU smoke passed(2 rows); diff check/protected source comparison passed. Native721/180/200 inspected as metadata only. Native disk payload estimate18.975GiB before RGB cleanup/14.098GiB after, excluding dataset/checkpoints/headers/margins; producer visible RAM scenarios2.012/3.038GiB exclude model/runtime/FAISS/page-cache. Native memory rehearsal, model peak, actual RGB/GT factory binding and final approval remain separate; full runner blocked, actual full bank/calibration NOT_CREATED. No actual model/data/degradation/metric experiment or push. Evidence/reproduction: `docs/PCB_FULL_PRODUCER_HANDOFF.md`, `analysis/pcb_full_producer/implementation-20261017/VERIFICATION.md`, ignored `outputs/pcb-full-producer/pcb-producer-synthetic-20261017-final/`. Negative gating/full110 B/B-uncertain unchanged.

## Native postprocessing memory readiness (2026-10-17)

Separate resource-only CLI reuses v0.6 helpers and unchanged evaluator, with preflight default, explicit execute,12 sequential exited workers, OS RSS high-water plus sampled RSS/free RAM/disk and checksummed completion records. Maps/scores/RGB are generated independently of GT; native hash-checked GT loads only in evaluation. No real model/index, full producer or research-performance output. Native guard adds fixed2GiB OS/runtime headroom:21923497568 available bytes required, not merely32GB installed RAM. Small final run passed, max individual worker OS peak109289472 bytes; native preflight BLOCKED_MEMORY with2856202240 available bytes and no workspace created. Full pytest280 passed/1 optional MVTec-data skip; no-Torch/FAISS focused tests22 passed; CPU smoke passed. See `docs/PCB_NATIVE_MEMORY_HANDOFF.md` and `analysis/pcb_native_memory/implementation-20261017/VERIFICATION.md`. Native execution and full pilot remain unapproved; incoming CUDA smoke's dirty=true provenance is preserved.

## Implemented

- CPU-safe framework: deterministic degradations, MVTec AD/AD 2/VisA adapters, manifests, PSNR/SSIM, optional LPIPS, model protocols, YAML runner, CSV aggregation, bounded experiment matrices, image/pixel AUROC and F1, and AU-PRO@0.3.
- Anomalib 2.6.2 PatchCore CPU training/export and official SwinIR-S x2 restoration pilot (scripts/fit_patchcore.py, scripts/run_cpu_pilot.py). Its thresholds come from held-out normal training images.
- Jihyuk-style pilot using the official Amazon PatchCore source pinned to fcaa92f124fb1ad74a7acf56726decd4b27cbcad: WideResNet50, layer2+layer3, 1024/1024 embeddings, patch size 3, IdentitySampler, Resize(256) then CenterCrop(224). It saves a checksum-verified FAISS memory bank and handles FAISS's Windows non-ASCII-path limitation through an ASCII staging directory.
- The legacy pilot compares clean, bicubic x4, and optional official SwinIR-S x4 on the same detector and test images. It records per-image true FAISS squared-L2 nearest-neighbor distances, runtimes, raw NPZ outputs, summary CSV, and a quality-vs-detection comparison. F1 uses only held-out normal images for threshold calibration. The x4 checkpoint SHA-256 is 09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e.
- Downloaded and locally ignored the official full MVTec AD archive, official VisA archive/Anomalib conversion, SwinIR-S x2/x4 checkpoints, and model artifacts. MVTec AD 2 (roughly 32 GB) is not downloaded.

## Verified CPU results

- Python 3.11 audit baseline: 93 passed. Synthetic end-to-end smoke test also passes.
- Bottle Anomalib pilot: 168 normal training, 41 normal calibration, 4 balanced test images. SwinIR-S x2 vs bicubic x2: mean PSNR +0.8185 dB and SSIM +0.00629; pixel AUROC -0.000071 and AU-PRO -0.000203. Four images are only a pipeline check.
- Hazelnut original-PatchCore pilot: 16 normal training, 4 held-out normal calibration, 20 balanced test images (10 normal, 10 anomalous), seed 11. Bicubic x4: PSNR 37.2866 dB, SSIM 0.93454, image AUROC 0.99, pixel AUROC 0.985777, AU-PRO@0.3 0.687230. SwinIR-S x4: PSNR 39.5309 dB, SSIM 0.95545, image AUROC 1.00, pixel AUROC 0.986678, AU-PRO@0.3 0.691774. SwinIR minus bicubic: +2.2443 dB PSNR, +0.02091 SSIM, +0.000901 pixel AUROC, +0.004544 AU-PRO. The CSV/JSON include image/pixel F1 and all raw predictions. The small, balanced subset and 16-image memory bank cannot establish a full-dataset research conclusion.
- Hazelnut full-memory pilot: trained the original IdentitySampler on all 391 normal training images; saved the 1.26 GB FAISS index. On 10 balanced test images (5/5), clean pixel AUROC/AU-PRO were 0.987115/0.841313; bicubic x4 were 0.974984/0.721629; SwinIR-S x4 were 0.980693/0.758324. SwinIR minus bicubic: +2.0830 dB PSNR, +0.02177 SSIM, +0.005708 pixel AUROC, +0.036695 AU-PRO. All image AUROCs were 1.0 on this small subset. F1 is deliberately null because all training images entered the memory bank and no independent normal calibration set remained. Per-image NN statistics were measured in a separate 4-image full-memory run; the 10-image run used --skip-nn-stats to avoid doubling FAISS searches.
- The original Jihyuk notebook's reported numbers cannot be assigned reliably to specific clean/degraded/restored runs from its saved cells. The new pilot matches its detector settings, not a verified reproduction of those reported numbers. Our mask preprocessing uses nearest-neighbor interpolation; the upstream dataset loader defaults to bilinear.
- Hazelnut Branch A full result (391 train / 110 test, seed 11, F1 null by design): clean image/pixel AUROC 1.0/0.986880, AU-PRO 0.875000. Bicubic x4: PSNR 36.4654, SSIM 0.93173, image AUROC 0.998214, pixel AUROC 0.983933, AU-PRO 0.818910. SwinIR-S x4: PSNR 38.7789, SSIM 0.95422, image AUROC 0.998214, pixel AUROC 0.985092, AU-PRO 0.843461. SwinIR minus bicubic: +2.3135 dB, +0.02249 SSIM, 0.0 image AUROC, +0.001159 pixel AUROC, +0.024551 AU-PRO. Full-dataset run, no sampling, so no seed variation applies.
- Hazelnut Branch B full result (313 fit / 78 calibration / 110 test, seed 11, robust median/IQR per-variant normalization): degraded_only image AUROC/F1 0.997857/0.96296, pixel AUROC 0.984044, AU-PRO 0.817486, pixel F1 0.57004. restored_only 0.998571/0.96296, 0.985051, 0.841263, 0.58034. mean_0.5_0.5 1.0/0.97810, 0.985360, 0.833354, 0.57440. max 0.999643/0.97059, 0.985290, 0.840552, 0.58067. Mean minus restored: +0.00143 image AUROC, +0.01514 image F1, +0.000309 pixel AUROC, -0.005939 pixel F1, -0.007909 AU-PRO. Max minus restored: +0.001071, +0.007625, +0.000239, +0.000332, -0.000711. Fusion helps image-level slightly but does not beat restored-only on localization; single seed, so no unchanged/improved verdict per protocol.
- The teammate models.py/runner.py were reviewed but not copied: the factory definition and image_score assignment are commented out, and the proposed memory-bank statistics are pixel-map statistics rather than nearest-neighbor distances. The existing runner already preserves per-stage runtimes and unique output paths.


## Hazelnut defect-level post-hoc analysis

Using the completed Branch A 391-train / 110-test predictions, 70 anomalous test images were re-analyzed with GT masks used only after inference.

Per-image SwinIR-S x4 minus Bicubic x4 findings:

- defect ROI raw mean decreased on 49/70 anomalous images (70.0%);
- defect-to-background mean gap decreased on 25/70 (35.7%);
- per-image Pixel AUROC decreased on 30/70 (42.9%);
- per-image AU-PRO decreased on 30/70 (42.9%);
- both ROI-background gap and per-image AU-PRO decreased on 14/70 (20.0%); under the current taxonomy these are suppression patterns, and the older "strong failure" name is deprecated.

Mean deltas across anomalous images:

- defect ROI mean: -0.180891;
- defect-to-background gap: +0.178580;
- per-image Pixel AUROC: +0.001745;
- per-image AU-PRO: +0.012914.

A paired image-resampling bootstrap (5000 repeats, seed 2026) gave:

- image-AUROC delta estimate 0.0, 95% CI [-0.005482, +0.005778];
- mean per-anomaly Pixel-AUROC delta +0.001745, 95% CI [+0.000147, +0.003495];
- mean per-anomaly AU-PRO delta +0.012914, 95% CI [+0.004487, +0.022950];
- mean defect-ROI raw-score delta -0.180891, 95% CI [-0.277204, -0.082284].

Important interpretation: raw defect ROI score often falls after SwinIR, but the background score can fall even more, so raw ROI-score decrease alone is not a valid restoration-failure criterion. Aggregate localization improves on average while a nontrivial sample-level regression subset remains.

The small-defect hypothesis is not supported in hazelnut so far: Spearman(defect area ratio, ROI-mean delta) = -0.0318, and the suppression-subtype median defect-area ratio (0.02286) is close to the remaining images (0.02091).

Suppression-subtype counts by defect type (historically called strong failure):

- crack: 4/18;
- cut: 1/17;
- hole: 7/18;
- print: 2/17.

The concentration in hole was a follow-up signal, not a final generalization. The later selected-case visual and NN-distance analyses are recorded below and did not establish a clean causal separation.

The first ROI-mean-based oracle is not treated as a valid localization upper bound: choosing the branch with the larger GT ROI raw mean reduced AU-PRO relative to restored-only. Its JSON remains a historical artifact and is not used in the current analysis.

## Protocol v0.2 and saved-prediction reanalysis (2026-09-21)

- `docs/EXPERIMENT_PROTOCOL_V0.2.md` freezes the hazelnut post-hoc taxonomy: 30/70 per-image AU-PRO regressions, partitioned into 14 suppression-type (`gap < 0`) and 16 geometry candidates (`gap >= 0`). It introduces no magnitude cutoff and treats the labels as map-level patterns, not proven feature-space causes.
- `scripts/analyze_hazelnut_failures.py` now ranks worst/best cases by per-image AU-PRO delta, shares the two anomaly-map color limits within each figure, and writes `regression_taxonomy.csv` and `selected_cases.csv`. The historical ROI-mean oracle file is left untouched.
- The new GT-assisted screening oracle gives mean per-image AU-PRO 0.907052 versus restored-only 0.903398 (headroom +0.003655). Choosing whole maps by per-image AU-PRO gives pooled AU-PRO 0.840458 versus restored-only 0.843461 (delta -0.003003); pooled selection is not a guaranteed upper bound.
- Reanalysis used the existing 110-test NPZ files only (`--render-cases 0`); no PatchCore or SwinIR inference was run. At this point the coarse grid was deferred; the later saved-prediction feasibility ablation below executed it and selected restored-only, with no fine search.

## Branch B saved-prediction feasibility ablation (decision recorded before execution, 2026-09-21)

The Branch A oracle headroom is small, but a five-point global scalar fusion check needs no new fit or inference because Branch B predictions are already saved. Testing only alpha=0.5 would not rule out the other coarse weights. The grid `{0.00, 0.25, 0.50, 0.75, 1.00}` and pooled AU-PRO@0.3 as the **sole** alpha-selection metric were fixed before this analysis; Pixel/Image AUROC and Bicubic-relative defect regression are supplementary/risk descriptors. Hazelnut remains development data. Fine search and adaptive gating are not part of this step.

### Observed result (saved predictions only)

`scripts/analyze_fusion_weights.py` read `outputs/fusion-patchcore/hazelnut-313x78-test110/` and wrote `analysis/hazelnut/fusion_weight_search/`. Pooled AU-PRO@0.3 for alpha 0/0.25/0.5/0.75/1 was 0.841263/0.838005/0.833354/0.826236/0.817486. The primary metric selects alpha=0 (restored-only); the best interior alpha 0.25 is 0.003258 below restored-only. Pixel AUROC at alpha=0.5 is higher than at alpha=0 (0.985360 vs 0.985051), but it is not the selection objective. Localization regression counts against Bicubic were 30/27/24/18/0; alpha=1 has zero by definition, so these counts are risk descriptors, not selection criteria. The alpha=0/0.5/1 predictions and recorded evaluations all matched exactly (maximum score/map/metric difference 0). No fine search or adaptive gating was run. This single development-category result does not justify a finer scalar search now; a new, separately specified study would be needed if an interior weight later improves the primary metric over both endpoints.

## Remaining work and boundaries

- Two-branch plan (agreed 2026-09-20): Branch A = Jihyuk-setting reproduction on all 391 hazelnut normals (AUROC/AU-PRO, F1 empty). Branch B = detection improvement on a fixed 80/20 split (313 fit / 78 calibration, seed 11), robust median/IQR per-variant normalization, fixed mean_0.5_0.5 vs restored-only as the first comparison, degraded-only and max as preset baselines. `src/sr_anomaly/fusion.py` plus `scripts/run_fusion_patchcore.py` implement Branch B; `split.json` freezes the reused image lists and all F1 thresholds come from fused calibration normals. The later five-point Hazelnut ablation selected restored-only and does not justify fine search. Hazelnut remains development/exploration; final validation belongs on untouched `capsule` only after all rules are frozen.
- The full hazelnut 110-test evaluation is complete. The next model-inference step, when needed, is preselected cross-category stress on Screw; Grid is optional and Capsule remains untouched final validation. Full IdentitySampler plus exact FAISS search is expensive even with a GPU backbone. For F1, use an independent normal calibration set or leave it empty; do not tune on test labels. Branch B uses its own 313-image bank; the 391 bank must not be reused because its 78 calibration images would leak into the memory bank.
- Sandbox note (2026-09-20): this container's egress fails TLS (curl exit 35) to release-assets.githubusercontent.com, download.pytorch.org, huggingface.co, and mydrive.ch, so the SwinIR checkpoint and MVTec archive cannot be fetched here. torch 2.14/torchvision 0.29/timm 1.0.29/faiss-cpu 1.15.1 install from PyPI, both submodules check out at their pinned commits, and the real PatchCore/SwinIR import surface verifies. Real-data runs (Branch A/B, capsule final) go to the local Windows machine or a GPU box that already holds the dataset and checkpoints.
- Connect other restoration checkpoints only after the degradation scale/task matches each model. EDSR, Restormer, Real-ESRGAN, EfficientAD, previous student code, and previous student weights are not available here. No metrics have been fabricated for them.
- Obtain MVTec AD 2 only if its size and data terms fit the experiment, and run VisA categories after selecting comparable splits.
- The current AU-PRO@0.3 uses 200 sampled thresholds; report this implementation detail in comparisons with external papers.

## Reproduce on this machine

From research_code/ in PowerShell, with the already downloaded ignored dataset/checkpoints:

    git submodule update --init
    uv pip install --python .venv\Scripts\python.exe -e ".[dev,pilot,legacy]"
    .venv\Scripts\python -X utf8 -m pytest -q -p no:cacheprovider
    .venv\Scripts\python -X utf8 scripts\smoke_test.py
    .venv\Scripts\python -X utf8 scripts\analyze_fusion_weights.py
    .venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 16 --test-limit 20 --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --output-dir outputs\legacy-patchcore\hazelnut-pilot-16x20-rerun
    .venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --train-limit 0 --test-limit 10 --calibration-limit 0 --skip-nn-stats --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --output-dir outputs\legacy-patchcore\hazelnut-full-train-test10-rerun

On a fresh machine, follow the data/checkpoint download commands in README.md first. Each completed legacy output directory is non-overwriting; choose a new --output-dir for a rerun.

## Selected Hazelnut qualitative review (2026-09-21)

Hypothesis: the map-gap suppression and geometry-candidate labels may correspond to visibly different anomaly-map patterns. Condition: nine cases fixed from the prior Hazelnut analysis (three per group), Branch A saved PatchCore maps and GT, Bicubic and SwinIR x4 RGB, shared anomaly-map color scale within each sample. Only the nine SwinIR RGB panels were reconstructed with the original checksum-verified checkpoint (25.3 s on this CPU); no PatchCore fit or inference was rerun. Outputs: `analysis/hazelnut/qualitative_cases/` has nine six-panel figures, a nine-row CSV, and per-case observations. In `crack/013`, AU-PRO fell 0.076146 despite Pixel AUROC rising 0.004057 and map ROI-background gap rising 0.423456; the thin upper GT branch remains diffuse. `crack/001` shows a weaker restored-map hotspot with AU-PRO and gap both falling. The success control `hole/006` gained 0.139957 AU-PRO while its gap fell 0.370210, so raw gap direction alone is not a failure test. These are visual observations, not causal proof. Next: compare official PatchCore patch-to-bank squared-L2 distances for the same nine cases.

## Selected Hazelnut PatchCore NN-distance check (2026-09-21)

Hypothesis: map-gap suppression cases may lose defect-to-background feature separation after SR, while geometry cases may retain it despite lower localization. Condition: the same nine exploratory cases, exact checksum-verified Branch A 391-normal FAISS bank for both x4 branches, official PatchCore embedding and nearest-neighbor squared-L2, continuous GT occupancy averaged over each actual 28×28 feature-grid cell. This mapping approximates ROI membership and does not equal the backbone receptive-field footprint. Saved 224×224 maps supplied per-image AU-PRO/Pixel AUROC/map gaps. There was no fit or whole-test feature inference; all 18 recomputed maps matched saved predictions exactly. Results: mean SwinIR−Bicubic ΔD_defect/Δfeature gap were -0.6123/-0.2491 (suppression, n=3), +0.0044/+0.3506 (geometry candidates, n=3), and +0.1345/+0.4580 (success controls, n=3). Joint ΔD_defect<0 and Δfeature gap<0 occurred in 2/3 suppression cases, 0/3 geometry candidates, and 1/3 controls (`hole/006`); `crack/017` lost defect distance but gained a small +0.00346 feature gap. Thus the selected cases do not cleanly separate a causal feature-suppression mechanism. Retain “suppression” as a map-score pattern; geometry cases are consistent with a spatial coverage/localization issue but do not prove it. Full values and source validation are in `analysis/hazelnut/nn_distance_selected.csv` and `nn_distance_selected_summary.md`. No significance claim is made for n=3 groups.

Next: preselected Screw cross-category stress after freezing the same x4 model/detector, pooled AU-PRO@0.3 primary metric, taxonomy, full-category reporting, and no fusion/threshold tuning. Local CUDA is unavailable and Screw has no fitted PatchCore bank; do not open Capsule. A minimal device switch can prepare the existing Branch A runner for a GPU machine without changing the algorithm.

The Branch A runner now accepts `--device {cpu,auto,cuda}` with `cpu` as the unchanged default. The resolved device is used only for the PatchCore backbone/embedding and SwinIR; exact FAISS remains CPU and the detector model specification remains unchanged, allowing reuse of compatible saved banks. An explicit unavailable CUDA request fails before the run. Result JSON and per-image CSV record the resolved device.

GPU execution support is now shared by Branch A and Branch B. Both keep CPU as the default, use the selected device for PatchCore/SwinIR, and retain `FaissNN(False, 4)` on CPU. CUDA timing synchronizes immediately before and after PatchCore fit, SwinIR restoration, and detector inference; Branch B aggregate calibration/test timing is synchronized as well. Each result JSON adds `requested_device`, `actual_device`, `cuda_available`, and CUDA-only `gpu_name` without changing detector specs, splits, calibration, normalization, fusion, thresholds, metrics, or saved prediction schemas. CPU-only tests pass; numerical parity and timing remain to be checked on an NVIDIA machine.

GPU Screw command after installing a CUDA-enabled PyTorch build:

    .venv\Scripts\python -X utf8 scripts\run_legacy_patchcore.py --category screw --train-limit 0 --test-limit 0 --calibration-limit 0 --skip-nn-stats --seed 11 --device cuda --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --model-dir checkpoints\legacy-patchcore\screw-seed11-train320 --output-dir outputs\legacy-patchcore\screw-full320-test160

Expected artifacts are a checksum-bound Screw PatchCore bank in the model directory and full-category clean/Bicubic/SwinIR prediction NPZ, CSV, and result JSON in the output directory. Do not reuse a partial output directory after failure; use a new empty output directory.

## SurgClean extension status (2026-09-21)

SurgClean is not present in `data/external/`; only MVTec AD and VisA are available locally. No download, experiment, or metric was attempted. `docs/SURGCLEAN_EXTENSION_PLAN.md` limits a future pilot to Desmoke, two official severity levels, and one matched official model after the dataset structure, terms, split, checkpoint, and evaluation protocol are verified. Because the described adjacent clean frames are unaligned, raw PSNR/SSIM is not accepted as a primary paired conclusion without an official alignment/evaluation procedure. This extension remains separate from MVTec and is lower priority than the frozen Screw stress test.

## Generic cross-category saved-prediction analysis (2026-09-21)

`scripts/analyze_cross_category.py` freezes the Hazelnut per-image taxonomy and deterministic case ranking before Screw results exist. It reads only a completed Branch A run directory and writes `per_anomaly.csv`, `regression_taxonomy.csv`, `summary.json`, `selected_cases.csv`, and `CROSS_CATEGORY_NOTE.md`; it cannot fit or run PatchCore/SwinIR. Applied to the saved Hazelnut run, it reproduced 70 anomalous images, 30 localization regressions (14 suppression, 16 geometry candidates), 40 improvement/ties, and the four stored mean deltas to floating-point precision. Synthetic guard/ranking tests pass. Screw inference and Screw analysis outputs remain ungenerated.

## Device parity and category reporting tools (2026-09-22)

`scripts/compare_cpu_cuda_runs.py` freezes exact artifact checks and configurable numeric comparison (`atol=rtol=1e-5` by default) for the saved CPU/CUDA fusion smoke runs. Device metadata may differ; model/split/checkpoint/method metadata, prediction shapes, labels, and masks may not. It reports numeric, raw-prediction, and separate runtime differences. No CUDA result or parity output exists yet. `scripts/aggregate_category_results.py` reads stored legacy run and cross-category summaries without inference or metric recomputation. `analysis/reporting/category_summary.csv` and `.md` currently contain Hazelnut only; Screw is omitted until both required artifacts exist.

## Research and reproducibility audit (2026-09-22)

`docs/RESEARCH_AUDIT.md` records the design, code, artifact, performance, and claim-boundary review. The audit added fail-fast verification for the frozen SwinIR checkpoint, Branch B split replay, cross-category source configuration, reporting/parity source consistency, and a read-only full-run preflight. The existing Hazelnut cross-category summary is now tracked under `analysis/hazelnut/` so the reporting table no longer depends on an ignored derived file. No saved prediction or research metric was recomputed. All 93 tests pass. Local Screw execution remains blocked only by unavailable CUDA; the dataset, pinned sources/checkpoint, and frozen command are present, while the Screw bank and result artifacts do not yet exist.

## Screw full cross-category result (2026-09-22)

- **Hypothesis:** the Hazelnut aggregate localization benefit and sample-level regression pattern may recur in Screw under the unchanged x4 protocol.
- **Condition:** received CUDA Branch A artifact, 320 normal train / 160 test (41 normal, 119 anomalous), seed 11, no calibration/F1, pinned PatchCore and SwinIR-S x4. Analysis reused saved predictions only.
- **Baseline:** Bicubic x4. SwinIR-S x4 is the fixed comparison; no fusion or test-label tuning.
- **Metric:** pooled AU-PRO@0.3 primary; Pixel/Image AUROC and PSNR/SSIM secondary; the Hazelnut-frozen per-image taxonomy describes heterogeneity.
- **Result:** SwinIR minus Bicubic was +2.437479 dB PSNR, +0.016426 SSIM, +0.198606 Image AUROC, +0.019490 Pixel AUROC, and +0.055000 pooled AU-PRO. Of 119 anomalous images, 23 regressed in per-image AU-PRO; all 23 met the suppression-pattern rule and none met the geometry-candidate rule. The other 96 improved or tied. Regressions were concentrated in `thread_side` (12/23 images) and `thread_top` (8/23) within this category.
- **Interpretation:** the aggregate restoration benefit and sample-level regression coexistence recur in Screw. The subtype composition differs from Hazelnut (14 suppression / 16 geometry): Screw's 23 regressions are all map-score suppression patterns.
- **Limitation:** two MVTec categories do not establish generality. Defect-type concentration is descriptive, and suppression is not a proven feature-space cause. The received ZIP does not include the 320-normal FAISS bank.
- **Next experiment:** run the frozen six-case selected NN-distance handoff only after the exact Screw bank is copied from the GPU machine. Do not open Capsule or add Grid/SurgClean before that check is recorded.

Outputs are under `analysis/screw/` and the two-category paper table under `analysis/reporting/`. The source ZIP SHA256 is `DB6B7CAB2F356B4C48710E29A9C0D145957E9816BAB910AF50AB3F43A334B5D6`. No full GPU inference was run on this CPU machine. All 96 tests pass after adding the defect-type, saved-map rendering, and bounded selected-manifest checks.

## Screw selected-case NN-distance result (2026-09-23)

The frozen six-case manifest was run on CUDA with the unchanged 320-normal Screw bank, SwinIR checkpoint, preprocessing, 28x28 continuous GT occupancy, and CPU exact FAISS squared-L2 search. The incoming code differs only by moving the normalized input tensor to the resolved device before the direct private `_embed()` call. All 12 recomputed maps match the stored maps with maximum absolute error 0.0.

For suppression patterns (n=3), mean SwinIR-minus-Bicubic ΔD_defect/ΔD_background/Δfeature gap are -1.824677/-0.565741/-1.258936; all 3 have both ΔD_defect<0 and Δfeature gap<0. For success controls (n=3), the corresponding means are -0.292801/-0.620176/+0.327375 and the joint-negative pattern occurs in 0/3. The selected Screw suppression-pattern cases are consistent with relative defect-feature normalization, but n=3 per subtype cannot establish a mechanism or population effect. No model, threshold, taxonomy, case selection, or research metric changed. All 96 tests pass after integration.

## Restoration-objective pilot preparation (2026-09-23, before inference)

The next development question is whether a distortion/PSNR endpoint behaves differently from a perceptual/GAN endpoint under the same x4 LR input. `docs/RESTORATION_OBJECTIVE_STUDY.md` freezes the primary pair (`RRDB_PSNR_x4` versus `RRDB_ESRGAN_x4`), MATLAB-compatible BasicSR degradation, metrics, taxonomy, figure layout, and stop/go rule. Official ESRGAN and BasicSR sources are pinned as submodules. The original checkpoints were downloaded locally, strict-loaded, and checksum-verified; checkpoint binaries remain ignored.

`analysis/restoration_objective_pilot/pilot_manifest.csv` fixes 25 Hazelnut test images before inference: five each from normal, crack, cut, hole, and print, selected by lexical path order and bound to image/mask SHA-256. `scripts/run_restoration_objective_pilot.py` reuses the checksum-bound 391-normal Branch A PatchCore bank without fitting, gives every learned restorer the same 56x56 LR image, records PSNR/SSIM/optional LPIPS and the frozen detection metrics, and writes Bicubic-relative regression taxonomy. No GPU pilot, full Hazelnut run, Capsule/Grid/SurgClean run, fusion, or gating was performed in this preparation step.

Validation on 2026-09-28: the tracked manifest matches the fixed lexical selection and file hashes; the runner also verifies its exact manifest hash, pinned source revisions, checkpoint hashes, and the two known bank-artifact hashes before inference. Direct RRDB endpoint differences are written per image as well as in the aggregate. All 101 CPU tests pass; no objective-pilot detection metrics have been generated.

## Hazelnut restoration-endpoint pilot result (2026-09-29)

- **Hypothesis:** official PSNR-oriented and perceptual/GAN-oriented RRDB endpoints may trade pixel fidelity, perceptual quality, and downstream defect localization differently under the same controlled x4 input.
- **Condition:** received a CUDA artifact from frozen source commit `95d097799c10135a982dbddf91f97b71e3ca29e6`: the preselected 25 Hazelnut test images (5 good, 20 anomalous), BasicSR MATLAB-compatible x4 LR, one checksum-verified 391-normal PatchCore bank, no fit, NVIDIA GeForce MX570 A. The original ZIP and all four NPZs were verified but remain outside Git.
- **Baseline/metrics:** new-pilot Bicubic x4, with pooled AU-PRO@0.3 as primary localization metric; PSNR/SSIM/LPIPS and Pixel/Image AUROC as separate outcomes. F1 and thresholds are null because no normal calibration was performed.
- **Result:** Bicubic / SwinIR / RRDB-PSNR / RRDB-ESRGAN pooled AU-PRO was `0.791050 / 0.804721 / 0.807534 / 0.812630`. RRDB-ESRGAN minus RRDB-PSNR was PSNR `-2.622296 dB`, SSIM `-0.034490`, LPIPS `-0.042595`, Pixel AUROC `+0.000592`, and pooled AU-PRO `+0.005096`; Image AUROC was 1.0 for all four variants. Bicubic-relative per-image AU-PRO regressions among 20 anomalies were SwinIR `10` (4 suppression/6 geometry), RRDB-PSNR `8` (3/5), and RRDB-ESRGAN `5` (4/1). Direct endpoint per-image AU-PRO favored ESRGAN on 11 images and PSNR on 9.
- **Interpretation:** the fixed subset shows a clear PSNR/SSIM versus LPIPS trade-off and a possible difference in localization behavior. The small 25-image lexical-first pilot does not establish a stable endpoint ranking.
- **Limitation:** official RRDB checkpoints differ in both loss and training data, so this is not objective-only causal evidence. Image AUROC saturation, 20 anomalous images, and Hazelnut's development status limit claims. The tracked `results.json` changes only two personal absolute paths to relative paths; the raw JSON SHA-256 is retained in the artifact hash ledger.
- **Decision:** GO to preparing a separate full 110-image Hazelnut endpoint run as a development-category stability check. Do not execute it or open Capsule/Phase C in this result-recording commit. Detailed numbers and provenance are in `analysis/restoration_objective_pilot/PILOT_RESULT.md` and `EXECUTION_RECORD.md`.

## Full Hazelnut endpoint confirmation prepared (2026-09-29, before inference)

`docs/RESTORATION_ENDPOINT_FULL_HAZELNUT.md` freezes the question, full-cohort analysis, uncertainty, figures, and A/B/C interpretation before results. The verified test cohort is 110 images (40 good, 70 anomaly). `analysis/restoration_objective_full/full_manifest.csv` records all images and masks in lexical order with SHA-256; manifest SHA-256 is `2ddb62748c750b3e4fae2b4b0b0cb4f3c354fd02faac74c95117afe1b3e116cc`. The existing runner now accepts `--cohort full110` with fixed hash/count guards while defaulting to the original `pilot25`; the same four variants, detector bank, metrics, and taxonomy remain in force. Historical Branch A Clean is only a contextual reference, not a new endpoint variant. No full inference or new research result was produced in this preparation step. Capsule, Phase C, new degradation, and further endpoint models remain closed.

## Full Hazelnut preregistration hardened (2026-09-30, still before inference)

After commit `982cbe0`, an external design review led to a dated amendment in `docs/RESTORATION_ENDPOINT_FULL_HAZELNUT.md`. It fixes deterministic A/B/C localization rules, a secondary five-point AU-PRO magnitude-sensitivity grid, pilot20 overlap versus pilot-unseen50 reporting, negative-gap base rates for regression and non-regression images, and the waterfall/sensitivity figure hierarchy. `scripts/analyze_restoration_endpoint_full.py` computes these only from saved runner CSV/JSON and tracked manifests; it cannot fit or infer models. A pilot25 artifact check reproduced its direct endpoint mean/median/min/max, 11/9 sign split, and 10/8/5 Bicubic-relative regression counts. Pilot tau values are post-hoc validation only. No full110 inference or result was created; original model, manifest, bank, primary metric, and GPU command remain unchanged.

## Second pre-inference review finalized (2026-10-01, after `607510b`)

A second external adversarial review was conducted before inference. Reused the existing tau grid, deterministic bootstrap, pilot20/unseen50 split, base rates, and figures without duplication. Added D50 direction to A/C and descriptive B-small/B-uncertain; inclusive near-zero counts/quantiles; lexical-tie baseline terciles (23/23/24); explicit taxonomy 2×2; secondary saved-NPZ unseen85 evaluation (35 normal/50 anomaly). Reporting prioritizes magnitude/distribution and quality–localization association, not strict-sign regression existence alone. Runner additions record environment/argv, eight output hashes, and end-to-end wall time only; scientific inference is unchanged. No pooled bootstrap, Wilcoxon, ROI fidelity, or optional method plot was added. One valid full110 closes this GPU branch for all cases, including NN/Capsule/Phase C expansions. No full110 inference/result exists. Exact execution/analysis commands remain in the frozen protocol.

Validation: `python -m pytest -q` **121 passed**. Saved-pilot CLI dry-run under ignored `outputs/restoration-objective/pilot-final-preregistration-validation` reproduced direct pooled delta `+0.005095647801611869`, 11/9/0 signs, and Bicubic-relative regression counts 10/8/5. Bootstrap remained seed 2026 / 5,000 repeats, CI `[-0.0020104776701971657, 0.01471828253404857]`. A runner AST comparison against `607510b`, after removing only added provenance statements, was identical. Both manifest hashes, three local checkpoint hashes, and both local bank artifact hashes verified unchanged. Local evolution/review notes are excluded through `.git/info/exclude`, not staged or published.

## Full Hazelnut endpoint confirmation executed and closed (2026-10-02)

One full110 GPU execution was run from preregistration commit `fddad881276da120ffcce1362ce062f85ea4759a`, with no protocol change before or during the run. `NVIDIA GeForce MX570 A`, `fit_performed=false`, `sample_count=110` (40 normal/70 anomaly), manifest/checkpoint/bank/source-commit hashes and all eight output-artifact hashes verified by independent recomputation, end-to-end `wall_clock_seconds=3563.561`. The frozen `scripts/analyze_restoration_endpoint_full.py` was then run once against this saved output with no refitting or inference.

Final case under the 2026-10-01 rule: **B (B-uncertain)**. `P=+0.006790` (pooled AU-PRO, ESRGAN minus PSNR), `D70=+0.005110`, bootstrap 95% CI `[-0.000907, +0.013954]`, `D50=+0.005062`; all three directional estimates are positive but the CI includes zero, so case A's uncertainty condition fails and the result is reported as B, not A. The quality trade-off reproduced (`mean ΔPSNR=-2.696 dB`, `mean ΔLPIPS=-0.0441`). Pilot20-overlap reproducibility passed exactly (0 mismatches, max abs diff `3e-8`); pilot-unseen50 and the secondary pilot-unseen85 saved-map evaluation agree in direction with the full 70-image result. Full numbers, the tau/tercile/taxonomy tables, and interpretation limits are in `analysis/restoration_objective_full/FULL_RESULT.md`; environment/provenance detail is in `analysis/restoration_objective_full/EXECUTION_RECORD.md`.

Per the frozen stop rule, this one valid full110 execution closes the restoration-endpoint GPU branch for this graduation project: no further endpoint, Real-ESRGAN, interpolation, NN-distance case, Phase C/gating, Capsule, new degradation/detector, or SurgClean work follows from this result.

## Completed-study thesis synthesis (2026-10-03)

Result baseline: `2dcac3f2c0c8418e2909641c473cd9498600929e`. Added `analysis/thesis_synthesis/` with a 10-row master CSV (six historical recovery rows, four full110 endpoint rows), thesis synthesis, 14-claim evidence matrix, figure index, and limitations. The two bicubic protocols and Branch A/B banks stay separate. Two small original historical summary snapshots supply the previously unreported Clean values; all three rows in each snapshot match the locally preserved original CSV, and Bicubic/SwinIR values match the existing reporting artifact. No raw NPZ, images, models, or private notes are published.

Full110 remains B/B-uncertain with unchanged metrics, hashes, provenance, bootstrap, taxonomy, and derived outputs. Pilot20 agreement is within `1e-5` tolerance (max difference about `3e-8`), not bitwise identical. Raw full110 outputs are unavailable locally, so this session verifies tracked evidence, not raw prediction arrays. The approved runtime paragraph alone now compares same-scope stages (`3283.923/342.224 s ≈ 9.596×`), image counts (`4.4×`), and per-image stage cost (`2.181×`); the cause of the increase is unknown, and the wall/stage `10.413×` ratio is not scaling evidence.

Validation: `python -m pytest -q` **124 passed in 105.88 s**; original-summary snapshot comparison and all synthesis relative links passed; paired quality CSV contains three variants with 70 unique anomaly samples each. Existing four full110 figures were visually reviewed, not regenerated. The original waterfall's uniform legend swatches are documented as a display limitation; its data/PNG remain unchanged. One new CPU recovery plot uses only six stored historical rows. Local Stage 13 and private reviews remain excluded by `.git/info/exclude`.

Reproduce reporting only: `python scripts/synthesize_thesis_results.py`; `python -m pytest -q tests/test_thesis_synthesis.py`. No additional research experiment was run. The experimental phase remains closed; next work is thesis/presentation writing and saved-evidence review, not GPU execution.

## Separate Branch B map-gating feasibility and CPU CI repair (completed 2026-10-15)

At the user's explicit request, opened local `exp/map-gating-feasibility` from clean `4742200`; fetched origin and confirmed the research upstream matched. Main is 30 commits behind the research branch. No push/merge/deployment/Actions rerun occurred. The historical closure, full110 B/B-uncertain, Branch A/B distinction, and existing RGB pilot10 results remain unchanged.

Reused saved normalized 313-fit/78-normal-calibration/110-test Branch B maps and original normal pixel thresholds. PROTOCOL and its SHA were stored before evaluation. Both fixed gates use map coordinates, never embeddings or GT. Four baseline arrays/evaluations/summary reproduced with metric differences 0.0. Pooled AU-PRO: degraded 0.817486365, restored 0.841262986, mean 0.833354121, max 0.840552370, candidate_1 0.841242157, candidate_2 0.841258566. Both candidates exceed max but not restored; this is negative feasibility under the fixed primary selection rule. Higher Pixel AUROC does not change selection. No further candidate/weight/threshold search follows.

Candidate mean-image deltas vs restored are -0.000018427 and -0.000115514; both paired CIs include zero. Normal common-threshold exceed rate remains 0.006757713 for restored/max/both candidates, only a diagnostic. Raw calibration predictions are absent in the source run, so candidate F1/fixed-FPR is empty. Full110 raw remains absent locally; tracked full110 results were not recalculated. New NPZ and exact execution-source snapshots are ignored; small artifacts and audit are in `analysis/map_gating_feasibility/hazelnut-branchb-20261014/`.

Confirmed remote job's matplotlib import failure; added it to dev and headless CI. Clean-env testing exposed a second torchvision dependency in the shared renderer helper. Replaced only its PIL transform implementation, with exact bytes versus torchvision on 12 synthetic sizes and both actual figures. No preprocessing semantics or scientific evaluator changes. The helper CI repair came after saved-data analysis; execution hashes/snapshots and results remain preserved.

Final tests: existing venv **128 passed (35.54 s)**; fresh Python 3.11.16 editable `[dev]`, without torch/FAISS, **127 passed/1 existing torch-only skip (30.31 s)**. Both CPU smoke tests passed (2 rows). Remote Ubuntu Actions has not rerun. All findings, timing scope, provenance limits and proposed main PR boundaries are recorded in AUDIT/REPORT.

## Frozen timing, local demo and PCB readiness (2026-10-15)

Local branch `exp/profiling-results-demo` starts at `9f0cfb8`; no push/main merge/deployment. Preserve the negative Branch B map-gating result, completed full110 B/B-uncertain, partial pilot10, old predictions, calibration, metric implementations and provenance. No fitting, new calibration/model/candidate inference, weight search or PCB experiment occurred.

Actual bounded CPU profiling reused the exact 313-fit bank and SwinIR checkpoint on the fixed pilot10 filenames: 2 warmup images, 2 instrumented repeats and one separate original/uninstrumented pass. The 64 normalized saved-anchor checks all matched exactly (map/score maximum difference 0.0). Inference-phase wall was 701.134 s of a 900 s budget; that clock conservatively includes parity/intermediate CSV writing, not just model time. Preparation/load/warmup are reported separately. Instrumented degraded means: backbone+embedding 0.723 s, CPU exact FAISS 8.002 s, detector parent 8.750 s; restored SR 1.277 s. FAISS is about 91% of detector time. Separate original pass drifted slower; no instrumentation-overhead or causal hardware explanation is established. CPU vector memory estimate is not peak RSS; CUDA was unavailable, so GPU time/memory is unmeasured. Conditional SR simulation requires call fraction below 0.124885 under its assumptions, not demonstrated savings or a deployable trigger. Protocol, source/input hashes, timings, parity, REPORT and estimates are in `analysis/profiling_results_demo/hazelnut-ten-20261015/`.

Added a loopback read-only demo over the actual 110-image/six-method saved results. GT only affects optional display; maps share color scale; normal AU-PRO is null; no candidate RGB/quality is invented. Only the verified historical ten-image RGB subset is available. HTTP/PNG/export/error-path checks passed; actual browser-screen interaction remains unverified because no browser was connected. See `demo_results/README.md` and `DEMO_VERIFICATION.md`.

VisA official split/image/mask audit passed for pcb1-4 without model execution. The pre-audit minimum-total/lexical rule recommends pcb2: 901 train-normal, 100 normal + 100 anomalous test, proposed 721 fit / 180 normal calibration. Files are ready, but teammate prior-use confirmation, a standalone frozen protocol/manifest, actual PCB bank/calibration, runner adapter wiring and actual GPU resource smoke are still missing. No PCB metric/result is created; readiness is not authorization or independent validation. Capsule remains unused.

Reproduce without inference: `.venv\Scripts\python scripts/summarize_profiling_readiness.py --input analysis/profiling_results_demo/hazelnut-ten-20261015`; launch `.venv\Scripts\python scripts/serve_results_demo.py --port 8765`. Final validation: existing venv **135 passed (47.65 s)**; separate Python 3.11.16 `[dev]` environment without Torch/FAISS **134 passed, 1 existing torch-only skip (46.92 s)**. Both CPU smoke tests passed (2 rows each). Frozen protocol and all 30 source hashes remain unchanged; protected old research code/results have no diff. JavaScript syntax passed; no actual browser-screen pass is claimed. The Graphify update was AST-only. Exact protocol and profiler bytes are protected from Git line-ending conversion. This is a local-only commit; no push/main merge/deployment or extra inference follows.

## Actual-browser and PCB structural review (2026-10-15)

Reviewed clean `7ee19a9` on `exp/profiling-results-demo` against actual timing CSV/code, stored JSON/NPZ/quality CSV and an actual local Edge renderer. Added `analysis/profiling_results_demo/review-7ee19a9/REVIEW.md`, reproducible read-only audit/browser scripts, evidence/split/crop/timing artifacts and local-only screenshots. No new model/search performance experiment, fit, inference, calibration, scientific metric or bank change. Negative gates and full110 B/B-uncertain remain unchanged.

Fixed only narrow-page table overflow, missing color/metric/CI/unit explanations and favicon 404. After-screen console/request/HTTP errors are zero; 4 stored baseline JSON/CSV anchors and 18 independent NPZ-to-rendered-PNG comparisons match exactly. Normal AU-PRO is not applicable, GT is display-only and candidate quality is baseline-only. Original protocol plus all 30 source hashes are unchanged. Actual screenshot review supersedes the earlier browser-unavailable limitation for the tested Edge/viewport cases, not every browser/production interface.

Recomputed FAISS fractions are 91.4526% of degraded and 90.7831% of restored detector parent time, not total system wall time. Warmup lies inside the 701.134 s phase; parity/intermediate writes and unmeasured intervals prevent an exact program-wall reconstruction. Non-instrumented pass drift is not an instrumentation-overhead measurement. Exact-search thread/query batching remains a candidate, not demonstrated improvement; existing search already batches 784 patch queries and uses four threads.

PCB2 split reproduced 721 fit-normal / 180 calibration-normal / 100 normal + 100 anomalous test, no overlapping paths or byte-identical image groups. Scoped local execution traces were absent; teammates' prior use is unconfirmed. More complete crop inspection found 9/100 masks lose defect pixels, with 4 resized 8-connected GT components entirely lost across 3 images, despite 0 entirely empty masks. This is a structural FOV limit, not a new detector result. Current crop can evaluate only the retained ROI; whole-board external validation needs a separately frozen coverage/geometry decision first. Priority is C (resolve that protocol limitation), not new gating or immediate PCB inference. Existing preprocessing/results were not changed.

Tests: existing venv **137 passed (36.66 s)**; no-Torch/FAISS CPU environment **136 passed/1 existing skip (49.57 s)**; both CPU smokes passed. Work remains local-only; screenshots containing dataset RGB are excluded from Git.

## User-requested separate partial-restoration feasibility (2026-10-03)

After closing the original study, the user explicitly requested a separate small RGB partial-restoration experiment, based on `01a03840730836a76b92eca37b22fc8713b979b8`. The completed endpoint study and thesis evidence remain unchanged. `scripts/run_partial_restoration_feasibility.py` reuses the existing 313-image Branch B bank and 78-normal calibration without fitting or recalibration. The ten filenames (first two good/crack/cut/hole/print), saved degraded-map 99% threshold, hard protection mask and area-matched uniform RGB control were frozen before inference in `analysis/partial_restoration_feasibility/PROTOCOL.json`.

CPU self-check, one-image smoke and fixed ten-image run completed. Pilot wall time `225.214 s`. Twenty replayed baseline maps matched saved normalized maps exactly (maximum absolute difference `0.0`); original source/artifact checksums verified unchanged after execution. Partial versus full: mean per-image AU-PRO `+0.000839` on 8 anomalous images, pooled AU-PRO `-0.004717` on all 10 images; 3 improved/5 worsened, and all 4 images benefiting from full restoration lost some gain. Partial versus uniform: mean per-image `+0.000357`, pooled `-0.005284`. Worst input-relative per-image loss shrank from `-0.021142` to `-0.007157`, while strict negatives increased from 4/8 to 6/8. This fixed candidate is not promoted to the main solution. No parameter search, new model, GPU training, or independent-validation claim followed.

Program, protocol, CSV/JSON, interpretation and two explicitly post-hoc explanatory figures are under `analysis/partial_restoration_feasibility/`; all ten figure panels, composed RGB and raw prediction arrays are under ignored `outputs/partial-restoration-feasibility/pilot10/`. Figure layout/report were corrected after inference without altering predictions, numerical results or measured times; the executed program snapshot and separate renderer hash are recorded. The executable self-check and saved-artifact recomputation passed. No GitHub push was performed.

## PCB full-FOV geometry draft blocked (2026-10-16)

From clean `53b5e21`, added a separate fixed full-frame 224 bilinear-image/nearest-GT geometry API, CPU audit/manifest, explanatory renderer and six tests; no legacy preprocessing/runner changes. Official seed-11 split reproduced 721 fit-normal / 180 calibration-normal / 100 normal + 100 anomalous test, no path overlap or byte-identical image groups. All 1,101 images were geometry-checked; 100 actual anomaly GT masks had zero input/alignment errors and zero empty target masks. However, 19/324 original-resolution 8-connected GT IDs disappear across 9 images (lost original areas 1–28 pixels). Verdict: **BLOCKED_GEOMETRY**, not GPU-pilot ready. This is resize aliasing, distinct from the historical crop-loss audit; no physical-defect or cross-resolution pixel-retention claim.

`docs/PCB_FULL_FOV_PROTOCOL_V0.1.md` is draft/blocked. Full FOV includes the coordinate domain but does not preserve all small components or shapes; non-square inputs are anisotropically resized. Two local-only figures were directly opened and visually reviewed, including exact NN source sampling of selected lost IDs. No exclusion/dilation/adaptive crop, new geometry search, degradation, fit/inference, calibration or anomaly metric was performed. PCB bank/calibration and runner integration are not created; team prior use remains unconfirmed. Negative gating/full110 B/B-uncertain are unchanged.

Evidence: `analysis/pcb_geometry/pcb2-full-frame224-20261015/` (frozen before inspection late on Oct 15; completed Oct 16). Existing Python 3.11 venv: **143 passed**; separate no-Torch/FAISS CPU venv: **142 passed, 1 existing skip**; both smokes passed (2 rows). Reproduction commands and visual/hash record: `VERIFICATION.md`. Next: separately specify a single high-resolution full-FOV or coverage-defined tiling revision, structurally validate before model execution, then wire the runner and prepare category-specific bank/calibration/device smoke. No automatic PCB/Capsule execution or push/main merge/deploy.

## Native PCB tiling identity pass, resource design still blocked (2026-10-16)

Added one separate native224/max-stride192/half-up layout, CPU audit/resource estimator, figure-only typography revision and tests. Whole 1,101-image audit passes exact RGB/GT/ID reconstruction and coverage (1–4); 324 original 8-connected IDs preserved, including all 19 lost by v0.1 with exact areas. Official anomaly masks 100; implicit normal backgrounds 1,001. 48 tiles/board gives fit/calibration/test 34,608/8,640/9,600, same 721/180/200 parent split. Prior blocked resize draft and old preprocessing/results remain untouched. Verdict **GEOMETRY_IDENTITY_PASS / NOT_READY_FOR_PILOT**.

Unchanged IdentitySampler with 784×1024 float32 vectors/tile implies 27,132,672 fit vectors and **103.503 GiB index payload**, a potential **310.509 GiB** three-vector-buffer fit scenario, not measured peak/RSS/runtime. Local physical RAM is 15.53 GiB. Native test maps are 1.119 GiB/method; evaluator conversions/sort arrays need additional memory. No bank changes/model loading/fit/inference/degradation/anomaly metric/FAISS benchmark ran. Resource feasibility, map merger, board score, calibration stage, tile-wise x4, runner/checkpoint/device smoke remain unresolved; no automatic pilot. Protocol `docs/PCB_FULL_FOV_PROTOCOL_V0.2.md` remains draft. Source/input hashes rechecked; original and readable PNGs directly viewed and local-only. Full pytest **154 passed**, no-Torch focused tests **11 passed**, CPU smoke passed. Evidence/reproduction: `analysis/pcb_geometry/pcb2-native224-tiling-20261016/VERIFICATION.md`. Negative gates/full110 B/B-uncertain and unconfirmed team-use history remain unchanged.

## Separate bounded-bank CPU draft (2026-10-16)

Added a NumPy-only builder that preselects sorted uniform global patch IDs with a local CPython RNG, seed 11, cap 262,144, then consumes bounded chunks without whole-feature concatenation. Default D=1024 bank payload 1 GiB, index 2 MiB, chunk ≤32 MiB; Python selection overhead, temporary buffers, upstream model and evaluation remain separate budgets, not measured RSS/VRAM. This is a new sampled-bank method, not IdentitySampler/greedy coreset; old runners, bank settings, geometry and research results are unchanged.

Frozen CPU run `analysis/pcb_bank_budget/pcb2-uniform-cap262144-20261016/` creates only PCB index planning (no real features), plus a lazy 1,000,003-row/D8 synthetic stream storing 257 vectors with exact formula agreement. Atomic BUILDING/FAILED/COMPLETE state and checksum/mmap loader prevent incomplete artifact reuse. Actual PCB bank/calibration **NOT_CREATED**, pilot **NOT_READY_FOR_PILOT**. Source/geometry/index hashes verified. Full pytest **187 passed**; focused **33 passed**, also **33 passed** without Torch/FAISS; both CPU smokes passed. No model/FAISS/degradation/metric execution, new dependency or geometry rerun. v0.3 protocol remains draft; runner integration, merger/board score/calibration/x4/native evaluation/hardware smoke remain pending. Reproduction and limitations: run `VERIFICATION.md`.

## Tiled synthetic CPU integration (2026-10-16)

Added separate injected feature/prediction callbacks connecting native tile order -> bounded bank -> board mean map/max tile-image score -> persistence/reload. Existing runners/third-party/geometry/bank/metrics/results are unchanged. Canonical tile-ID float64 accumulation with uint32 coverage returns float32; no GT weights, clip or per-tile normalization. Missing/duplicate/mixed/invalid tile and output provenance guards added. Bank mmap is read-only during cal/test and all bank artifact hashes are compared before/after.

`analysis/pcb_cpu_integration/tiled-dummy-20261016/`: synthetic **PASS**,2 fit/1 cal/2 test parents, toy grid2×2/D4/K17,32 observed vectors/17 stored,6 maps independently recomputed and exactly reloaded. GT change/removal and feature batch1/3/8 do not change predictions/bank. Full pytest **208 passed**; no-Torch/FAISS focused **21 passed**; both CPU smokes passed. No real RGB/GT/feature/model/FAISS/degradation/calibration/metric execution or old geometry rerun. v0.4 is **DRAFT_CPU_INTEGRATION**; actual PCB bank/calibration **NOT_CREATED**, pilot **NOT_READY_FOR_PILOT**. Real wrapper/order proof, calibration/x4/quality/evaluation memory/hardware remain pending. Per-board payload plan is not measured RSS/VRAM. See run `VERIFICATION.md` for commands and hashes. Negative gates/full110 B/B-uncertain remain unchanged.

## Native tiled model adapter and guarded preflight (2026-10-16)

Added separate PatchCore/SwinIR thin adapters and runner; no changes to existing runners/models/geometry/bank/metrics/results. CPU tests exercise vendored _embed/PatchMaker/segmentation with fabricated features and fake distances, not a real backbone/search. Preserve native normalization, shared CLEAN normal-fit bank, fixed tile224→LR56→224, mean map/max tile-score. No auto-download; pinned local checkpoints/source hashes and default model-free preflight. Explicit --execute enables raw limited model-smoke only after guards. Full scope always blocks; v0.5 records one board calibration/quality proposal but does not pretend its previously pending choices or native evaluation lifecycle are approved/implemented.

Full pytest **228 passed**; no-Torch/FAISS new tests **16 passed,4 skipped**; both CPU smokes pass. Real metadata/checkpoint/path-only CPU preflight: model-smoke **PREFLIGHT_PASS**, full **PREFLIGHT_BLOCKED**. Smoke1 fit/1 cal/2 test uses37632 expected vectors/147MiB bank; full bank1GiB plus scorer/index copies. Native Pixel AUROC39P visible payload lower-bound≈10.91GiB excludes model/sort workspace; full memory/lifecycle unvalidated. No RGB/GT content read, actual model/search/SR/degradation/calibration/anomaly metrics run, or PCB bank created. **CPU_ADAPTER_TEST_PASS / REAL_MODEL_SMOKE_NOT_RUN / NOT_READY_FOR_FULL_PILOT**. Next: separate GPU raw smoke per `docs/PCB_TILED_GPU_HANDOFF.md`; approve proposed board rules and validate/implement native evaluation/calibration/quality lifecycle before any full pilot. Evidence: `analysis/pcb_tiled_preflight/VERIFICATION.md`. Negative gates/full110 B/B-uncertain unchanged.

## PCB GPU input delivery amendment (2026-10-17)

GPU recipient had no VisA inputs in the new worktree. Added stdlib-only setup/verification and a separate CC-BY-4.0 pcb2 Release bundle (not Git-tracked RGB): 1101 unchanged RGB, 100 unchanged GT, official CSV and license/NOTICE/attribution, 274645313 bytes. Checkpoints are fetched from original publishers with frozen hashes. No runner/protocol/geometry/bank/metric changes. Full pytest **258 passed, 1 optional MVTec-data test skipped**; CPU smoke, empty-folder bundle install, all1202 input hashes, checkpoint checks, safe resume and model-free CPU preflight passed. Full pilot stays blocked and CUDA smoke unreviewed. See `docs/PCB_GITHUB_HANDOFF.md`; original local branch preserved.

## Board calibration, quality and process lifecycle (2026-10-17)

User explicitly authorized adopting the single v0.5 proposal if compatible; no conflict found. v0.6 now adopts post-mean per-variant image/pixel robust calibration on180 normal boards, fixed0.99 normal quantile, and board RGB overlap mean + existing PSNR/SSIM. Added source/split/checksum-bound calibration persistence, streamed normalized test files, exact unchanged evaluator per variant, GT-derived region-mask memory guard, explicit adapter close on success/error. Old protocols/results/metrics/geometry/bank remain unchanged; full executor stays disabled.

Synthetic-only process-separated check `analysis/pcb_board_pipeline/pcb2-board-lifecycle-20261017/`:2 fit/2 cal/2 test,12 raw maps,6 normalized maps,7 exited worker processes. Existing helper/reference calibration/quality/evaluation all equal, normalized maps exact; fake model/index/scorer and large-array release verified. Full pytest **243 passed**; no-Torch/FAISS related **31 passed**; both CPU smokes pass. **CPU_CALIBRATION_QUALITY_TEST_PASS**, synthetic **MEMORY_LIFECYCLE_VALIDATED**; native **BLOCKED_MEMORY**, GPU smoke **NOT_REVIEWED**, full **NOT_READY**. Native planning: calibration6.09GiB, evaluation18.42GiB, additional normalized files6.72GiB; estimates not RSS/VRAM. No real RGB/GT, model/SR/FAISS/degradation/calibration/anomaly metric execution. Actual PCB bank/calibration NOT_CREATED. Next: review GPU raw smoke and hardware RAM, validate native working set, then separately approve full producer/RGB/GT/process orchestration. See run VERIFICATION.md and `docs/PCB_BOARD_LIFECYCLE_HANDOFF.md`.

## 로컬 진행 기록에서 가져온 항목

### 결론 강화 제안 검토와 다음 반환 체크리스트 (2026-11-17)

사용자는첨부된결론고도화글을참고해주형의현재작업반환후추가시킬작업을정리하도록요청했다. fetch로공개handoff/juhyung이90d2bf34d16d8cdad5df96c20d8d65d9e7f5bf3d임을확인하고PCB운영점/empirical FPR plateau/phone cohort표를직접대조했다. 웹raw조회는cache miss였으나Git원본으로확인했다.

PCB test평가분모는정상100/이상100 총200영상이다. 1140unit/54720tile query는실행처리량표기로구분한다. Bicubic normal-cal q0.99 임계값2.720750에서TP71/FN29/FP3/TN97, SwinIR2.264221에서TP54/FN46/FP1/TN99가맞다. 동일한수치의threshold를적용한실험으로표현하지않는다. FP3의TPR구간은.62~.82/.59~.70으로겹치고사후test-score plateau범위이며CI나배포threshold선정이아니다.

phone C2v03 전체16은OK6/NG4/REVIEW6,정상13은OK6/NG1/REVIEW6이다. 공통7의정상0/4NG·이물3/3NG·REVIEW0/논리접근10vs14와사후5의정상0/2·이물3/3·논리접근6vs10을각분모로유지한다. 실제촬영비30~40percent절감·REVIEW안전성·실카메라5도공차로확대하지않는다. pooled/per-image부호차이는보고하되Simpson역설·대면적원인·SR효과부재·Bicubic전체최적은확정하지않는다.

로컬outputs/final-evidence-next-review-20261117/NEXT_RETURN_REVIEW.md에검토결과와조건부후속프롬프트를준비했다. 다음반환에서이미완료된항목을먼저대조하고6bank사진·PCB TP→FN/FP→TN각1개사진·운영점표·실물새평가/사람판독/시간·최종캡션의빈부분만보완하도록했다. 후보포스터는소수핵심패널확대를우선하고전체사례는기존HTML/부록으로연결한다. 현재NEXT_TASK/모델실행지시/촬영고정버전은수정하지않았다. 새실험·모델·장비실행은없다.

### 지혁 Bicubic-bank 확장4 수신과 주형 중복실행 지시 갱신 (2026-11-17)

새Hazelnut/Screw extension ZIP SHA c8988ce32e040c85f2b046d58838a4326ec81dde4b5c186aa2d898244885950b / 305e106789aa7d48c333c3ded478ed7f81fc3d1a98b81322c01cdb1978145a6a와CRC,각receipt12payload/총24개의bytes/SHA를검증했다. 외부SUMMARY2개는각ZIP내부와같다. 개별540행/paired378행과4summary행,품질평균/identity/delta를대조하고제공image score로image AUROC4개를독립재계산해일치했다. pooled AU-PRO/pixel AUROC는raw maps가없어재계산하지않았다.

Screw의Bicubic bank에서query SwinIR-minus-Bicubic은PSNR+2.437522dB와동시에pooled AU-PRO−0.037334/image AUROC−0.208444다. 같은SwinIR query의clean→Bicubic bank대조는pooled+0.008372지만per-image평균−0.010678,감소64/119다. 다른대조를구분해보고한다. seed11두cohort/pooled CI미계산/RAM peak미측정/dirty provenance는유지한다.

기존24는Jihyuk의PROGRESS/JH원문에수행완료가기록돼있지만기존6개run의원래receipt/metadata는이번첨부·로컬다운로드·fetchedc69f1c1remote에없다. source-only8af5aa는미푸시보고다. 주형은24+4재실행에앞서기존완료결과·CPU분석기/테스트·base소스와실행시점사본을비공개ZIP/bundle로받아통합한다. 받은patch4파일은CPU분석기/당일base수정전체를포함하지않는다.

공개36파일을exp/phone-final-return-review와handoff/juhyung@90d2bf34d16d8cdad5df96c20d8d65d9e7f5bf3d에반영해원격일치를확인했다. docs/JIHYUK_EXTENSION_RECEIVED_FOLLOWUP_20261117.md,분석REVIEW/CROSSCHECKS/selected_visual_cases와두run의26metadata/원본patch를전달했다. 기존master와bank계약의전체신규실행문구를완료자료회수·통합·사진반환으로수정했다. 두ZIP/patch소스바이트와index가같고git apply --check·공개allowlist·diff·문장/링크검사를통과했다. 모델코드적용/새GPU/전체pytest/fake10재실행은없다.

JH01~10 원문36441bytes SHA8ee28e5ce9a0a143f2e65074aa667e973543b97e0821524e8bb6a2ac31bd8525를중앙private Stage71에한번통합했다. rawcopy/IMPORT_RECEIPT는outputs/private-decision-imports/jihyuk-20261117-8ee28e5c다. 입력cache는outputs/jihyuk-bicubic-return-review-20261117이다. 새그림6개case는저장예측에서내보내고원본/열화/Bicubic/SwinIR RGB+GT/같은query bank지도·같은bank query지도로연결한다. 기존촬영전50장제안과최종보고서/A0·필요구현·사람판독작업은유지한다. 원본79a1c0f/사용자변경·비공개ignored/untracked를보존한다.


추가전달ZIP은outputs/jihyuk-bicubic-return-review-20261117/juhyung-bank-results-followup-private-20261117.zip이다. 24entries/286291bytes/SHA256 8b47b695b3776abe5bcc8131e0ed48eee4731a8b5b0b618dd434f41a83ae6d13, CRC/내부SHA검증통과. 기존23MB패킷은보존하고이번추가지시가bank신규실행부분을갱신한다. 기존자동화의실제상태PAUSED/5시간일정/현재채팅은그대로유지하고prompt만갱신했다.

### 최종 목표 통합 프롬프트와 결함 동반 열화 촬영안 (2026-11-17)

사용자는 최종목적(실제촬영열화에서도미세결함보존과검사,사진/수치증거)을달성할전체과정의설계·구현·실행·검토·최종반환을주형에게넘길프롬프트와촬영방법을요청했다. 실제PROGRESS,private연구노트의초기가설·실패시도·Stage69,기존이관문서,새32장평가계획과기록표를읽었다. progress_revolution이라는사용자표현은실제존재하는PROGRESS.md와notes/RESEARCH_EVOLUTION_LOCAL.md경로로연결하고상대에게동명파일이있으면확인하도록했다.

기존32장계획은정상기판에서만저조도/흐림을만들고이물은선명L0/L1에서시험한다. 따라서‘결함이있는열화입력의보존’을직접보는보조촬영이필요하다. 기본32장v2(blur-2의대체L1도흐림)+작은모사이물3위치×선명/저조도/흐림×최초/대체2장=보조18장,총50장촬영전제안을작성했다. 원래참조/보정4장·기본평가14cycle과보조challenge9cycle을분리한다. 계획행50,실제관측0이다. 새촬영전주형이고정하고보유development활용과독립평가를구분한다. 기록표의runner호환은담당자확인대상이다.

전체프롬프트는docs/PROMPT_JUHYUNG_END_TO_END_20261117.md,촬영방법은docs/PHOTO_CAPTURE_REQUEST_20261117.md다. 공개4파일을exp/phone-final-return-review및handoff/juhyung@8aaee07e4b4f299fd8fbb325661926beec7d4fca에반영하고두원격ref일치를확인했다. 문장4파일Unicode0flags/링크검사와diff·allowlist검사를통과했다. 기존bank상세계약/공개패치4c333f2와지혁이관c69f1c1은유지한다.

phone GR검사와SR/PatchCorebenchmark경로,정렬용축소와원해상도검사,실제흐림/저조도와artificialx4를설계에서연결하도록했다. 기존RGB와GT/map의동일crop사진을먼저만들고bank24+4·기존코드보완·실제사진·보고서/A0·검토수정까지마치도록했다. 데이터가없는동안독립가능한작업을계속하고실제모델/장비/사람판독미수행을완료로표현하지않는다. 사진포함자료와private는비공개직접전달한다.

비공개전달ZIP은outputs/juhyung-end-to-end-handoff-20261117/juhyung-end-to-end-private-20261117.zip이다. 29entries/22641579bytes/SHA256 6c6d0b14bc6248e8160a00f112be78a3734b72f6e4d79ff05f86e6186d9bc0cb, CRC와내부payload SHA를검증했다. ZIP의records는이포장검증직전스냅샷이다. 최신전체진행/연구노트스냅샷,원문결정사본,실제최종반환ZIP,동일SHA공식양식보충본,기존선정그림과새프롬프트/계획표를재사용해준비한다. 원본79a1c0f와사용자변경을보존하며새GPU·하드웨어실행은없다.

### 최종 비공개 시각 자료 수신과 bank-domain 주형 이관 (2026-11-17)

최종 private ZIP 16048325 bytes/SHA256 e64ac163ce49e11b9834160b6b6e3ab18ee3eda17e1a5f30ce87c3cda310c4fc를 받았다. ZIP CRC와 내부45 payload의 bytes/SHA를 검증했다. receipt의 template_copy.pptx 1개가 archive에 없어서 이전 수신한 동일 SHA 공식 양식을 supplemental에 별도로 보충했다. 원본 ZIP/receipt는 보존했다. 기존22 metadata와는 바이트가 같아 a350b07의 수치·테스트 cache를 재사용했다.

실제 PDF를 렌더해 1쪽 약841×1189 mm를 확인했고 PPTX1슬라이드31shape, 모사이물/저조도 사진그림과 기존선정case00 PNG를 직접 열었다. 같은 source의 새 station_events를 fake serial로 재생해57frame을 확인했다. 정상라벨13cycle은OK6/NG1/REVIEW6,모사이물3cycle은NG3이다. 사진보드1개/한세션 개발 결과이며 복원RGB의같은결함확대비교가 다음핵심산출물이다. 비공개갤러리는outputs/phone-final-private-review-20261117/RESULT_PHOTOS.html에있다. 새GPU모델추론·실물UNO실행은없었다.

private 원문19661bytes/SHA256 bce461ae591cf367887aa946b0a189681f151149aa29ffb16ecb9f20193712f3를 대조하고 새 D-20261115-10~17의8개만 중앙 private Stage69에 통합했다. 이전01~09/11월12일13개는 유지했다. rawbytecopy와IMPORT_RECEIPT는outputs/private-decision-imports/juhyung-20261117-bce461ae에있다. 이전의 최종private/시각자료 미수신상태는해소됐다.

사용자요청으로 지혁의 실제 PatchCore bank-domain24+4를 주형에게이관했다. 사진우선 실행프롬프트·가이드대조·NEXT_TASK와공개producer패치2개/SHA출처를 handoff/juhyung 및 exp/phone-final-return-review@4c333f295e6ea8daf7c469a8a82630d7c1b774e2에공개했다. 지혁handoff는c69f1c19685b4296adddb33556f76627d8551188에서담당변경을안내한다. 두원격ref를검증했다. 문서·JSON whitespace/링크·stage7파일allowlist검사통과. 패치기존공백은원본SHA그대로보존했다. 새소스기능변경은없다.

새완료검사를반복하지않고 같은결함crop 원본/열화/Bicubic/SwinIR/GT/지도와동일query의bank비교사진을먼저반환하도록했다. producer/consumer의동명analyze_bank_domain_study.py충돌은별도실행checkout에서해결하도록했다. HTML표기는저장결과render/사본수정으로고칠수있다. L1실제흐림을새32장계획에포함하는보강안을촬영전고정하도록했다. 실시간시연·UNO미확보는사진결과물의선행조건이아니다. 팀정보·독립새촬영·사람판독·실제촬영시간·실물검증은남아있다.

연결된상대세션은없어실제착수미확인이다. 5시간자동화designproject-cpu-5는기존일정/상태/현재채팅을유지하고주형담당과수신완료cache를반영했다. 확정A0PDF마감2026-12-01 23:59KST,실제발표일미확인. 원본79a1c0f/사용자변경과비공개자료ignored/untracked상태를유지했다.

### 주형 최종 반환의 CPU 검토 완료 (2026-11-17)

반환59bc262의metadata22개를receipt bytes/SHA256과대조했다. 실행source7b868a3·포스터source59db971을연결했다. 기존24사진해시목록·참조·보정·96cell은이전cache와일치했다.7조건112cell과운영표16행을재집계했고v0.3은현재24장/16cycle에서v0.2와같았다. 품질CSV48행은24사진×가정조명2개이며실제recipe조명선택시PASS15/REVIEW9다. 전체C3 NA9건과사후공통7건/제외5건,공유대체사진을보존했다.

기존consumer에7조건을추가하고6조건회귀검사를유지했다. Consumer11개가0.84초,source신규4개가105.50초에CPU에서통과했다. 담당자의전체696passed/4skipped(6748c95),관련49passed·smoke2행/exit0(7b868a3)로그를받았다. 새GPU추론·전체pytest를CPU에서반복하지않았다. 설계·구현·자체검토는Fable5.2,후반기록·반환은사용자전환에따른Opus5.5라는RUN_RECORD표기를기록했다.

원근중심보정/화면이동의결과가다르고,147/423초는코드·조건수·전원이함께다르다. 포스터의평균/pooled AU-PRO 혼용과historical seed미기록의공통11표현을확인해수정지시를작성했다. 숫자그림을직접열어확인했고문장3파일0flags,diff/공개14파일allowlist검사를통과했다. ASTgraph3488nodes/6446edges를확인했다.

공개분석exp/phone-final-return-review와handoff/juhyung을a350b0707d4914c69a71da32e42ddf8e41bd7046로push하고원격일치를확인했다. 보고서는analysis/phone_final_return_20261117/REVIEW.md,후속은docs/PHONE_FINAL_CPU_FEEDBACK_20261117.md다. 수신cache는outputs/phone-final-return-review-20261117이다. 원본79a1c0f와사용자변경은보존했다.

실제PPTX/PDF·그림7개·최신HTML·capture_sheet·새private원문은미수신이며첨부를요청했다. 중앙private Stage68에는CPU의근거·수정·남은질문만기록했다. 새32장평가·사람판독·물리취득시간·UNO실물·지혁24+4는대기한다. A0PDF마감12월1일23시59분KST,실제발표일은미확인이다.

### 실제 private 수신과 Fable 최종 실행 일괄 위임 (2026-11-15)

사용자가 전달한 실제 private 노트15035bytes/SHA256e63678677c8953545f0c743c35ab7de6d7276cd809eda4a6f1771d5ed63061aa와 시연 HTML962865bytes/SHA25637438851f65bfb78fe67edb96532b12a13148186b8f2e84f320c4fdd70ffb065가 안내 값과 일치했다. 기존13개와 겹치는 부분을 보존하고 신규 D-20261115-01~09를 중앙 ignored private Stage67에 통합했다. 원본 바이트 사본과 import receipt를 비공개 보관했다.

HTML의 축소 사진·표시용 차이지도46개와 첫 화면을 headless Edge1440×1100으로 렌더해 확인했다. 전체 cycle의 동작이나 raw검사배열을 검증한 상태로 확대하지 않는다. Source5839caa의 CPU smoke2행 통과는 사용자 전달 담당자 실행 보고로 기록했고 원본 로그는 다음 반환에서 연결하도록 지시했다.

사용자가 남은 설계·구현·실험·자체 검토·시연·보고서·A0 제작을 Fable5.2에 모두 맡겨 실제 결과물을 보고 판단하겠다고 요청했다. docs/PROMPT_FABLE_FINAL_DELIVERABLES_20261115.md와 NEXT_TASK를 작성했다. 공식 A0 원본·3번 미리보기·받은 private두파일·전체프롬프트·README·receipt의7항목 ZIP을 비공개 준비하고 CRC/파일별SHA를 검증했다. 상대 Claude의 live 연결이 없어 사용자 전달용 패킷으로 제공한다. 새 촬영·사람판독·UNO실물의 실제 확보 상태에 맞춰 진행하며 구현·시연·포스터 제작을 병행하도록 했다.

문서·수신 기록 작업이며 기존 모델 실행과 테스트는 재실행하지 않았다. 공개 대상은 프롬프트·NEXT_TASK·PROGRESS·익명 receipt4개다. 실제 private·사진 포함 HTML·공식 양식·ZIP은 Git에서 제외했다.

공개 프롬프트·NEXT_TASK·수신 receipt·PROGRESS 4파일을 commit492aa6a57d14816f33446329f1929bb876af2bfb로 분석브랜치와 handoff/juhyung에 push하고 원격 일치를 확인했다. 전체 지시문은 docs/PROMPT_FABLE_FINAL_DELIVERABLES_20261115.md다. 비공개 ZIP은 outputs/fable-final-handoff-20261115/fable-final-handoff-private-20261115.zip이며2995950bytes,7항목이다.

### 11월 15일 실제 PCB 24장과 촬영 스테이션 반환 통합 (2026-11-15)

주형 handoff7b2c894/source5839caa의 신규 반환을 수신했다. Metadata17개와 실제 JPEG24장의 바이트·SHA256, 실행 source6개와 이전 예시6개 해시가 일치했다. 대표 실제 사진의 조명·흐림·회전·모사 이물을 직접 확인했다. 사진과 GPS EXIF는 ignored outputs/phone-station-return-review-20261115에 비공개 보관했다. 담당자 실행 기록의 사용 모델은 Claude Fable5.2다. 전기적 정상 여부·실제 제조 결함·사람 판독 라벨은 미확인이다.

저장 cycles96행에서 전체16건·두조명 공통7건·참조/보정 재사용 제외5건을 독립 consumer로 재집계했다. 전체 C3는 NA9건이다. 공통7건의 C2v0.2/C3 사진 사용10/14회, 정상라벨 NG0/1건, 모사이물 NG각3건이다. 제외 진단5건은 사진 사용6/10회이며 normal-3/lowlight-3의 대체사진 공유가 남는다. 두 묶음은 이번 검토의 사후 개발 진단이고 사진 수는 오프라인 논리적 접근 횟수다. Bicubic/SwinIR의 최종 판정은16건 모두 일치했다. 한 보드·한 세션의 반복이며 독립 평가·실제 촬영시간·라인성능은 미측정이다.

별도 exp/phone-station-return-analysis에서 consumer·검사·수치·그림·REVIEW·유한 후속문서를 추가했다. 새 합성 metadata 테스트9개(0.40초), 실행 source의 CPU 테스트7개(137.68초, fake복원기)가 통과했다. 반환 pixel판정맵과 원본 capture_sheet는 미반환이다. 전체 pytest·GPU 복원 추론은 이번 CPU 검토에서 실행하지 않았다. 숫자 그림에서 겹친 범례를 고쳐 다시 열어 확인했다. Graphify AST갱신3240nodes/6203edges, 공개 문장3파일0flags, diff/stage allowlist 검사를 통과했다.

공개12파일만 commit8ddde87f8628a624d7d9695ea21c596c1e3004d5로 분석브랜치와 handoff/juhyung에 push하고 원격 일치를 확인했다. 지혁 handoff는 d8dcceb로 새 반환이 없다. 원본 exp/profiling-results-demo@79a1c0f와 사용자 변경을 보존했다. 중앙 private Stage66에 선택·근거·남은 질문을 기록했다. 기존165조건과 완료 GPU 반환 cache를 재사용한다.

보고서는 outputs/phone-station-analysis-20261115/analysis/phone_station_return_20261115/REVIEW.md다. 다음은 주형 포스터의 수치·오프라인 표기·private 원문 반환과 작은 새 평가 세션의 사전 고정이다. 주형의 새 private 결정 원문과 지혁24+4 실제 결과는 대기한다. A0 PDF 마감은12월1일23시59분 KST, 실제 발표일은 미확인이다.

### 현업 촬영 기준과 주형 후속 실행 queue 공개 (2026-11-13)

사용자가 보낸 그래픽카드 예시 PNG6장(각4000×3000, EXIF 없음)을 해시와 함께 ignored outputs/industrial-capture-review-20261113/에 보관했다. 자세·배율·부분 FOV 변화가 섞인 개발 예시로 검토했고 조명·반복·결함 라벨은 unknown이다. 이번6장에 새 품질 batch나 anomaly metric을 계산하지 않았다.

MIRTEC·Basler·Koh Young의 공식 자료5개를 읽고 촬영 recipe, 트리거, 다중 조명, 미검·오탐·재검 부하·cycle time을 연구 비교군에 연결했다. 고정 촬영 직접검사(C0), 같은 입력 복원(C1), 조건부 최대1회 재촬영(C2), 항상두조명 촬영(C3)을 제안했다. 정상 참조·단일 품질 개선안·golden-reference 기본검사·bounded retake·비교 실행기·포스터/시연을 주형 담당의 유한queue로 정리했다. 공장별 수치와 실제 효과는 미확인이다.

비공개 촬영 예시 ZIP도 준비했다. 사진6장·receipt·README의8항목이며 내부 파일 SHA256과 ZIP CRC를 검증했다. 파일은 outputs/industrial-capture-review-20261113/pcb-capture-examples-private-20261113.zip이고 아직 팀원에게 직접 전송하지 않았다.

공개 문서3개만 handoff/juhyung@e76d28fe705bf5e9583e89c5de8b44fdf399f604에 commit/push하고 원격 HEAD 일치를 확인했다. 문장/숨은문자 검사,공개절대경로·token검사,stage allowlist,diff검사를 통과했다. Source코드 변경이 없는 문서 작업으로 pytest는 재실행하지 않았다. 원본 exp/profiling-results-demo@79a1c0f와 사용자변경을 보존했다. 원본사진·private노트는 Git에서 제외했고 중앙 비공개 Stage65를 갱신했다.

### 그래픽카드 첫 사진의 CPU 품질 보고서 (2026-11-13)

사용자가 주 촬영 대상으로 선택한 그래픽카드 뒷면을 기존 phone aa2 도구에 연결했다. 신규 후보 PNG 세 장(각4000×3000, EXIF 없음)을 해시와 함께 local-only로 보관하고 첫 장만 분석했다. 왼쪽 소자 밀집부 ROI (.10,.25,.40,.70)를 수치 확인 전에 정했다.

Working long side1024의 고정 ROI에서 mean Y113.3454, clipped-high1.05191%, clipped-low0.0234592%를 측정했다. 기존 high-clipping 1% 규칙에 따라 RETAKE가 기록됐다. 단일 attempt/slot이며 detector 미연결, station REVIEW, research_metrics null이다. 원본 조명은 unknown으로 남겼고 영상 간 정렬·반복성·결함 성능으로 확대하지 않는다.

HTML을 headless Edge에서 열고 PNG를 직접 확인했다. 입력/CSV/manifest 정합성 assert와 diff 검사를 수행했다. 산출물은 ignored outputs/phone-real-pcb-dev-20261113/에 있으며 모델 추론·코드 변경·commit/push는 없다. 두 handoff remote를 한 번 fetch했고 주형 a5d7922, 지혁 d8dcceb로 새 반환은 없었다. 예약 후속 작업의 오래된 발표일 표현을 A0 PDF 제출 마감(12월1일23:59)으로 정정하고 최신 촬영 대상·기록을 반영했다.

### 촬영 계획과 A0 양식 검토, 제출 일정 정정 (2026-11-13)

사용자 제안 12장과 A0 PowerPoint를 검토했다. 실제 PowerPoint 읽기 전용 렌더 9장과 접촉 인화 이미지, 3번 예시를 직접 확인했다. 양식은 약 840.98×1188.99 mm이며 원본 SHA256 불변을 확인했다. 결과 영역이 넓은 3번 예시를 권장했다.

기존 어댑터로 12장 초기 촬영을 시작하고 시연 조건도 3회씩 반복하는 18장 권장안을 작성했다. 배경·시점은 각 3장 별도 확장으로 두고, 동일 객체·ROI와 모사 이물을 유지한다. PASS/RETAKE는 측정 출력으로 기록하며 현재 detector 미연결과 검은 재질의 clipped-low 영향을 명시했다. 계획과 렌더는 ignored outputs/poster-capture-review-20261113/에 보관했다. 새 촬영이나 모델 실행은 수행하지 않았다.

제공 공지로 확정된 일정은 2026-12-01 화요일 23:59의 A0 PDF 제출 마감이다. 기존 ‘12월 1일 발표’ 표현을 이 기록에서 정정하며 실제 발표일은 미확인으로 남긴다. 포스터 원본과 제출 상태는 그대로 보존했다.

### 첫 실물 사진 수신과 어댑터 품질 보고서 (2026-11-13)

사용자첨부실물어댑터3PNG(각1080×1920,EXIF없음)를수신·보관했다. 사진별자세·단자방향·화면내크기가달라조명반복세트로집계하지않는다. 첫사진에서어댑터주변수동development ROI를정해기존phoneaa2도구에연결했다. 초기BLOCKED_MEMORY는보존했고실제가용RAM이기존기준을충족한뒤새output으로재시도해1attempt/1slot품질보고서생성을완료했다.

첫사진은기존규칙의clip_low로입력품질RETAKE,stationREVIEW다. ROI mean Y63.91,clipped-low16.41%,clipped-high0.84%였다. 검은재질과노출의영향을확인할개발단계이며실제결함판정이나검출개선으로해석하지않는다. Detector미연결/research_metrics null을유지했다. 별도의소규모ROI통계는세뷰에서계산했으나pose/ROI차이로비교추정하지않는다.

실제입력·receipt·보고서는ignored outputs/phone-real-adapter-dev-20261113/에있다. 성공보고서는first_view_audit_retry/report.html이며기존실험·bank·모델은재실행하지않았다. 원본PROGRESS와비공개Stage62를갱신했다.

### 실행 우선순위 정리와 사진 한 장 입력 확인 (2026-11-12)

사용자가 반복 검증의 비중과 사진의 선행조건 여부를 질문했다. 완료된 설계/실험이 다시 활성queue로 읽힐 수 있던 NEXT_TASK를 현재완료상태와 남은실행중심으로 정리해 handoff/juhyung@a5d79225f3c9c636a2500a63ccf7a6c2f833eeef에 공개했다. 사진대기중 기존결과의 포스터·시연·통합진입점 정리와 승인된실험을 계속하며 추가검증은 새변경·새입력·실패의 영향범위에 집중한다.

기존phone도구에 자체synthetic JPEG한장과해당기록표 한행을 넣어 정상완료/HTML생성과1attempt/1slot을 확인했다. 탐지기는미연결이며research_metrics는null이다. 9장은조명비교용 권장development계획이고 사진한장도 입출력·품질표시부터 연결할 수 있다. 실제실물사진·검출성능은 아직 미수신이다. 이번확인은새연구성능실험으로 집계하지 않는다. 원본환경·기존자원guard를 재사용했다.

### 첫 촬영 입력 준비와 viewport 해석 정정 (2026-11-12)

새private기록D09의headless제약을근거로실제viewport를추가측정했다. Window390요청의innerWidth는492~504px였고본문/document전체overflow는없었다. 별도390 CSS-pixel iframe에서innerWidth390,document client/scroll375,body client/scroll343과표wrapper overflow:auto를확인하고PNG를직접열었다. 앞선모바일레이아웃문제확정과필수수정요청을정정했다. 실제모바일기기·클릭·console은미검증이다. 정정문과측정JSON을공개했고기존metric/source는변경하지않았다.

outputs/phone-first9-local-20261112/input에기존도구용9행capture_sheet와README/PREPARATION.json을준비했다. 이는촬영계획이며실제사진/실험결과는없다. 객체P1·세션DEV01·상태unknown·미확인camera옵션unknown과미설정ROI를명시했다. 첫9장은development로사용하고방법고정후별도촬영세션에서평가하도록지시했다. 새의존성·GPU모델실행없이기존phone도구의실행명령을연결했다.

### 주형 비공개 결정 원문 수신·통합 (2026-11-12)

사진으로만 확인됐던 새 RESEARCH_EVOLUTION_LOCAL.md 원문을 사용자 첨부로 받았다. 전달된 SHA256 26e0173f…6d0fa1과9870bytes,결정D-20261112-01~13을 확인했다. 원본 byte 사본과 IMPORT_RECEIPT는 ignored outputs/private-decision-imports/에 보관하고 중앙 비공개 notes/RESEARCH_EVOLUTION_LOCAL.md Stage59에13결정을 빠짐없이 통합했다. 원문 표현·수치·[당시]/[사후]와 모델 출처를 보존했고 중앙본의 줄바꿈·제목 깊이만 조정했다. 새 private원문 미수신 상태는 해소됐다. 이 파일과 중앙 노트는 ignored/untracked이며 stage/commit/push에서 제외했다.

### Fable 재검토·phone synthetic·clean control 반환의 CPU 검토 (2026-11-12)

주형5794b2d까지4receipt/34공급파일을해시검증·캐시했다. Historical Screw3unit/15cell의Image AUROC를동일160영상(정상41/이상119)의CSV에서기존함수로검산했다. Clean은다섯규칙0.983~0.984,×4조건의낮은image AUROC는집계방식전반에서유지된다. Calibration이없어F1/FPR/미검률은NA다. Master165prediction조건은유지한다.

Phone source aa2f7fa를별도detached worktree로받아기존CPU환경의24tests가97.70초에통과했다. 후속psutil환경조회만실패했고기존_budget재검은통과했다. 실제합성E2E의HTML을headless Edge에서열고desktop1440×1100/mobile390×844 PNG를직접확인했다. Mobile본문·표잘림을발견해주형에게source소유권을유지한작은수정을요청했다. PNG와합성입력/HTML은ignored outputs에보관했다.

두phone버전의16개sheet예상상태와추가미등록1개를검산했다. PASS7/REVIEW6/RETAKE4,slot14중7해결,station14cycle전부REVIEW다. 실제detector미연결·synthetic표기는유지했다. 실제사진·물리latency·lux·생산검사성능은아직없다.

원격기록에따라초기작업Opus5.5와이후Fable5.2재검토를구분했다. Fable v1은기존문맥을본상태로독립초안이아님이명시됐다. 공개근거에서확인한지표보간편향수정과JPEG가이드변경을기록했다. 새private노트원문은미수신이다. 검토는handoff/cpu_reviews/20261112/에공개했다. 원본PROGRESS변경·private노트제외·기존source를보존했다.

### 설계 검토·실험 병행과 선택 근거 반환 계약 (2026-11-12)

사용자가 선택 과정의 근거 기록과 반환을 요구하고 필요한 실험도 설계와 병행하라고 보완했다. 주형 NEXT_TASK에서 전체 설계 완료를 기존 고정 실험의 선행조건으로 읽을 수 있는 문구를 수정했다. 새 방법은 해당 실험의 첫test비교 전에 질문·대조군·분할·지표·선택기준을 짧게 고정하며,기존 기준의 실험·구현은 검토 중에도 계속한다. 자원 경합 시 무거운 실험은 순차 처리하고 독립적인 검토·문서·그림을 병행한다.

두 전달branch에 handoff/RECORDING_AND_RETURN.md를 추가했다. PROGRESS는 실제수행·결과·실패·검증·다음작업,비공개 RESEARCH_EVOLUTION_LOCAL은 대안·근거·선택이유·수정전후·남은질문을 기록한다. 각 완료단위에 공개PROGRESS와 비공개결정노트 증분/전체본을 각각 반환하고 run-id/commit/마지막결정ID를 연결한다. 실제비공개노트와 RGB/GT/raw자료는 기존공개제외범위를 유지한다.

공개head는주형 handoff/juhyung@4cfd3fa6a082196aecf867217c73d511fc5331c5,지혁 handoff/jihyuk@d8dcceb2e17c18ce43ab4ae2a90bca41a037ae6c다. 문서·diff검사와push가통과했다. 이번작업은지시문·기록계약수정이며새연구실험은실행하지않았다. 12월1일발표와내부실험/포스터마감목표는유지한다.

### 12월1일 포스터 일정과 Fable 설계·전체검토 인계 (2026-11-12)

사용자가 포스터 발표일을12월1일로 앞당겼고,Fable5.2 독립 설계→기존 전체 연구 검토→수정 설계 고정→실험 순서를 요청했다. 실제 master165조건을 읽어8study families/13protocol groups와PCB 수치를 확인한 뒤,전체 근거 요약과 실제 CSV/JSON/code 참조를 작성했다. 두 담당자의 신규 반환은 이번 확인에서 없었다.

handoff/juhyung@8f4e4daf795cacdad2ac8938dd965ffe6899a70b에 새 NEXT_TASK,전체 근거 검토 문서,촬영 대상·일정 계획을 공개했다. 이전12월1~3일 마무리 초안에는 일정 대체 안내를 추가해 기록을 보존했다. 내부 목표는11월23일 핵심실험 정리,11월27일포스터초안,11월29일최종정리다. Fable 설계 자체는 주형 호스트의 다음 실행 과제다.

보유 노출기판의 커넥터/핀/납땜부를 우선 촬영 대상으로 제안했고,기판이 없으면 보유USB-A케이블의 금속커넥터로 조명·입력 실험을 시작할 수 있게 안내했다. 추가구매 없이 스마트폰과 대상 고정,조명3방향×3반복의첫9장을 유지했다. 동일물체 반복과 독립부품 수,실제결함·모사결함·상태미확인 라벨을 구분한다. 실물 수량과 사진은 여전히 미수신이다.

이번 변경은공개문서6개다. 문장검사와 source 참조 존재 확인,git diff --check 및원격push가통과했다. 연구코드·metric·prediction을실행하거나변경하지않았으며pytest는재실행하지않았다. 원본branch와사용자PROGRESS변경을보존했고비공개노트는Git제외상태다.

### Image-score 반환 검토와 스마트폰 조명 파일럿 준비 (2026-11-11)

주형의 image-score aggregation 반환 8f98ed5/0ad6d07을 수신했다. 두 category 반환46+46파일과 공개 경로 정정1파일의 SHA·크기를 확인했다. 40unit×5규칙의200cell에서 calibration·정규화·threshold·판정·Image AUROC/F1/FPR/미검률을 기존 함수로 검산했다. 영상 단위 paired stratified bootstrap(2,000회,seed11)의 rule−original AUROC CI160개를 추가했다. 같은 category의 반복 unit은 같은 영상 cohort를 재사용한다. Master165조건은 유지하고200행을 별도 readout ablation으로 기록했다. Raw NPZ40개와 calibration-map anchor는 원격 실행 보고 범위를 구분했다.

공개 CPU branch는 exp/image-score-return-analysis@57235a2c3dbb2e485bd41fea958b6bb598b9a6c8다. 관련 테스트39개, 기존 CPU smoke2행, diff 검사와 scalar 그림 직접 확인을 마쳤다. 전체 pytest는 이번 변경에서 재실행하지 않았다. 정적 source graph도 AST로 갱신했다.

Private 사례 ZIP의3PNG를 내부 SHA와 대조하고 직접 열었다. 사례047/006/050의 RGB·GT·공통 색 범위 map을 확인했다. juhyung-20261111.private.md를 수신하고 원본 사본·receipt는 ignored outputs에 보관했다. 원본 notes/RESEARCH_EVOLUTION_LOCAL.md Stage55에 근거가 있는 결정과 사후 해석, 수정 사항·남은 질문을 통합했다. 원문과 PNG는 stage/commit/push에서 제외했다.

사용자가 추가 구매 없이 스마트폰·책상 조명/플래시를 쓰겠다고 알려 촬영 초안과 주형의 설계·구현 지시를 작성했다. 주력 초안은 고정 촬영에서 조명 조건의 품질·결함 반응·재촬영 이력을 보여주는 로컬 도구다. 첫 입력은 같은 기판 세 조명×세 반복의9장으로 제안했다. 실물 수량·결함 상태·사진은 아직 확인 전이다. 공개 docs/PHONE_LIGHTING_PILOT_DRAFT.md와 docs/PROMPT_JUHYUNG_PHONE_LIGHTING.md 및 handoff/juhyung@c461c3806dabdecd5c7e268f01cc5eab5a658d47의 NEXT_TASK에 전달했다. 실제 촬영 성능 수치는 아직 없다.

### GPU 반환 통합과 오프라인 실행 재개 준비 (2026-11-11)

주형의 9사례 공간 분석을 exp/pcb-selected-spatial-review@30b420d에서 검토·공개했다. 9보드, 27map, 36개 4-connected 요소의 scalar와 source/GT/hash 연결을 확인했다. 관련 테스트 17개와 CPU smoke 2행이 통과했다. 정규화 seam gradient는 SwinIR이 9/9 높았고, raw gradient와 seam/non-seam 비율은 9/9 낮았다. Geometry 후보 2/3에서 raw gap도 감소했다. 원격 RGB/GT 사례 그림은 추가 수신이 필요하며, 이번에 만든 scalar 그림은 직접 확인했다.

추가 noise 32조건의 4run, 공개 파일 80개를 receipt와 대조했다. Source 40d57dd와 고정 v1 split/checkpoint/vendor, 동일 bank metadata 및 LR hash를 확인했다. σ15에서 SwinIR−Bicubic pooled AU-PRO 차이는 새 4조건 모두 음수였다. Screw σ5의 영상별 평균 차이 CI에는 0이 포함됐다. 각 영상의 두 noise draw를 평균한 뒤 기존 paired helper로 70/119개 영상 ID를 2,000회(seed 11) 재표집했다. Pooled AU-PRO point estimate와 CI의 대상을 구분했다. Master는 165조건/13 protocol groups이며, 이전 133개 entry의 ID와 모든 기존 값을 대조했다. 관련 테스트 27개와 CPU smoke 2행이 통과했다. Raw NPZ와 bank payload는 이번 반환에 포함되지 않았다.

CPU 분석은 exp/noise-repeatability-analysis@615ae7d432c88ffb7e6f61b65df40be4b6907e2a로 공개했다. Hazelnut 두 protocol의 v1_bank_dir만 상대경로 공개 사본으로 변환해 원본·실행·공개 사본 SHA를 연결했다. 기존 Git 이력과 실행 원본은 보존했다. 전달 ref는 handoff/juhyung@346f95e6affc564c5d054b7243724e105456025c 및 handoff/jihyuk@21b690b560ba624bc1402b8871e0726e45881841이다.

지혁용 최종 오프라인 패키지는 outputs/JIHYUK_OFFLINE_HANDOFF_20261111-v2.zip이다. 크기는 1,899,465 bytes, SHA256은 aae234a1291851915749277a893ffca8ad291ff74dc9a970a823b33f1a80e304다. Bundle은 공개 prerequisite 83ef04e를 기준으로 최소 61c2170과 최신 21b690b를 포함한다. 별도 수신 저장소의 테스트 17개와 CPU smoke 2행이 통과했다. 기존 환경을 명시적으로 재사용했으며 수신 checkout 자체에는 venv·입력·가중치가 포함되지 않는다. 이미 checksum이 맞는 dataset ZIP을 재사용하도록 안내했다. 실제 지혁 호스트의 GitHub 연결과 GPU 재개는 확인 전이다.

중앙 private 노트 Stage54에 검증 가능한 설계 결정을 기록했고, 두 담당자의 private 결정 요약을 별도로 받는 절차를 추가했다. 원본 노트는 ignored/untracked 상태를 확인해 stage/commit/push에서 제외했다. 주형의 다음 범위는 저장 map의 image-score 집계 대조(계획 40unit×5rules), 지혁은 bank-domain 24+4조건이다. 실제 query는 bicubic_x4/swinir_x4이며, 이전 자연어의 clean/restored query 표현을 정정했다. 새 실행 결과는 아직 수신 전이다. 5시간 재개 작업은 완료된 9사례/32조건을 반복하지 않고 새 반환만 확인하도록 갱신했다.

### 담당자별 Git 전달과 결과 반환 (2026-11-10)

공개 CPU 기반 7d5c177에서 별도 worktree로 handoff/juhyung@1e6c6bcd0e59ed91c6c3e6eb0e078f8d75b8bf39와 handoff/jihyuk@61c2170dec726e76be4a4dbd488a84f893a6db16을 만들고 두 ref만 atomic push했다. 주형에는 원본 metadata 8개와 9사례/noise32 지시를, 지혁에는 receipt와 원본/테스트 patch 3개 및 bank-domain24+4 지시를 전달했다. 각 handoff/START_HERE.md를 GitHub HTTP200으로 수신해 commit blob과 비교했다. 전체 새 commit 범위와 8+3 파일 hash가 일치했고 diff check가 통과했다. 원본 exp/profiling-results-demo와 exp/inspection-controller-cpu 및 사용자 변경을 보존했다.

scripts/prepare_team_return.py는 명시한 공개 UTF-8 CSV/JSON/Markdown/text만 새 run-id로 복사하고 byte hash receipt를 생성한다. 배열/이미지/기존 반환 덮어쓰기와 unsafe path를 거부한다. 반환 receipt는 NOT_REVIEWED이며 미수신 배열의 검증을 의미하지 않는다. 두 담당자는 본인 branch의 handoff/returns/<owner>/<run-id>/로 결과를 push하고 CPU는 새 receipt만 확인한다. HANDOFF에 scheduled Git fetch 경로를 추가했다.

관련17tests와 clean receiver14tests/CPU smoke2행이 통과했다. 첫 전체 검사는 새 submodule 미초기화로 680pass/6fail/1skip/4error였다. 이후 전체는685pass/3fail/3skip이었고 남은3fail은 frozen PatchCore 두 파일의 CRLF checkout 차이였다. Source text 일치를 확인한 뒤 새 submodule의 Git checkout만 원래 규칙으로 복구했고 관련34tests 및 CPU smoke2행 재검이 통과했다. 이 결과를 단일 전체 실행688pass로 기록하지 않는다. 두 경로를 합쳐 모든 수집 test의 최종 확인 결과는688pass/3skip이다. 중간 별도-root 수집 시도는33 collection errors로 실패해 통과 집계에서 제외했다. 생산 code/metric/frozen hash는 수정하지 않았다.

검증 로그는 outputs/team-delivery-pytest*.log와 team-delivery-recheck.log, 공개 수신 감사는 outputs/team-delivery-publication-audit.json이다. Graphify AST update를 완료했다. Dataset ZIP813040630B와 raw map/bank/가중치/RGB-GT 그림은 비공개로 유지했다. 지혁의 최초 dataset 1회 전달, 두 계정의 GitHub Write 권한, 지혁 호스트의443 접속은 별도 확인이 필요하다. 새 GPU 연구 결과는 아직 도착하지 않았고 master133/9는 유지했다.

### 기업 공개 과제와 실물 전략 검토 (2026-11-09)

사용자 제공 전략 글과 서강대 Anyshot 수상 공지, 삼성디스플레이 공개 AI 과제, KLA 검사·review 자료를 검토했다. 광량/초점 점검과 실제 재촬영이 가능한 정지형 검사 스테이션을 우선 후보로 제안했다. 자동 보정·즉시 통과 비율·속도 목표를 측정 성과와 구분했고, CPU HOG calibration 수와 PCB protocol 혼용을 정리했다. 원문 논문·심사표는 확보하지 못했다. 상세 검토는 outputs/industry-physical-strategy-20261109/REVIEW.md에 저장했다. 이번 작업은 문헌·설계 검토이며 새 모델 실험이나 하드웨어 제작 결과는 없다.

### 실물 검사 장비 산출물 후보 논의 (2026-11-09)

사용자가 취업 방향을 반도체·생산기술·양산기술·스마트팩토리로 명시했다. 실물 기판 AOI 셀과 조명 제어·동기화 계측 보드, 선택적 전기검사 지그를 후보로 비교했다. 공식 제조/계측 자료를 확인했으며 현재 단계는 제안이다. 예산·보유 장비·회로/구매 범위는 다음 설계에서 정한다.

### CPU 연구 확장 완료 (2026-11-08)

별도 exp/cpu-research-expansion에서 실제 CPU24조건을 완료하고 GitHub에 공개했다. Commit b24750074f887304d6b50fc8bcd00b2ea7e14410. 기존 exp/profiling-results-demo79a1c0f와 GPU 구현8abed72/CPU 분석1f0c801을 보존했다. 구현은 outputs/cpu-research-20261108/, 실제 결과는 outputs/cpu-research-campaign-20261108/에 있다.

Hazelnut110·Screw160, seed11/23/37, Clean/Bicubic/Unsharp/SwinIR의24조건과 test prediction3240건을 생성했다. 고유 test270장/anomaly189장을 구분하며, 같은 영상의 seed delta를 먼저 평균했다. 기존6개 HOG bank4096×36을 SwinIR 조건에 재사용했다. Checkpoint09fad24e...의 calibration/test union614장 CPU cache는553.736s, OS process peak457326592B였다. Cache와6개 추가 bank query/evaluation 전체 status 경과는970.326s다. 이 값들은 합산하거나 GPU 성능으로 외삽하지 않았다.

Unsharp−Bicubic은 PSNR/SSIM 증가와 pooled AU-PRO 감소를 세 seed 모두에서 보였다. 평균 delta는 Hazelnut−0.003956, Screw−0.026889다. SwinIR−Bicubic은PSNR+2.313490/+2.437519dB, pooled AU-PRO+0.072742/+0.133538이며 세 seed 모두 증가했다. SwinIR도 per-image regression은Hazelnut4/2/1, Screw19/19/27장이었다. HOG의 낮은 절대 성능, category 탐색 이력, 추가 seed/조건의 사후 설계 시점과 conditional image CI를 기록했다.

저장 PatchCore prediction270장×3variant×5budgets=4050행을 분석했다. Top1% pixel recall의 SwinIR−Bicubic delta는Hazelnut−0.116%p, Screw+24.309%p다. Defect subtype 결과, spatial distance, quality association과 min/max 사례를 저장했다. Branch B의 고정 정상 calibration threshold에서는 mean fusion TP65→67/FN5→3/FP0/40이었고 sensitivity delta의 CI는0을 포함한다. 기존 primary와 supplementary 결과를 분리했다.

공개 전달은48개 코드/테스트/문서/수치/그림 파일이다. Public summary14개CSV와5개numeric PNG, 환경·provenance를 포함하고 data/weights/RGB/GT/map/bank/private note는 제외했다. Master는34행/4protocol groups이며 outputs/cpu-research-campaign-20261108/master-final-lf/에 있다. 상세 보고와 재현은 구현 worktree docs/CPU_RESEARCH_RESULTS_20261108.md다.

전체pytest623pass/3skip(269.50s), 기존 CPU smoke2행, git diff --check 통과다. Skip2개는 실제RAM prerequisites,1개는 optional dataset 부재다. GitHub fresh receiver에서17개 공개 source/config canonical bytes와 config값,14CSV/5PNG/env hash를 확인했고20tests12.57s 및smoke2행이 통과했다. Receiver는 원본 .venv를 재사용하고 data/weights/submodules는 받지 않았다. Windows CRLF seed/catalog JSON3개는 Git LF 정규화와 semantic 동등성을 구분했다. 초기 임시폴더 ACL/빈 submodule 오류와 LFS 예제 파일 자동수신 중단 기록은 VERIFICATION.md에 남겼다.

원본 PROGRESS와 ignored/untracked notes/RESEARCH_EVOLUTION_LOCAL.md Stage46을 갱신했다. 개인 노트는 stage/commit/push하지 않았다. 정해둔 CPU queue는 완료했고 추가 queue를 무한히 생성하지 않는다. 다음 연구 우선순위는 GPU 담당의 고정 bank-domain2×2 결과를 읽어 정상 bank/query domain matching 효과와 기존 quality/localization 차이를 함께 분석하는 것이다.

### CPU bank-domain analysis published and category inputs ready (2026-11-02)

Completed the requested CPU implementation in the separate exp/bank-domain-analysis worktree. Public commit 1f0c801df111357d92bb759ccb051f3832008286; actual GitHub ref and a fresh receiving clone match. New source is limited to read-only result analysis, category input transfer, receipt cache and master reporting. Original exp/profiling-results-demo79a1c0f and exp/pcb-full-producer-integration8abed72 remain unchanged.

New tools: analyze_bank_domain_study.py, prepare_mvtec_transfer.py, cache_artifact_receipt.py and build_research_master_table.py, with small modules/config/tests and two handoff docs. The existing Hazelnut paired-bootstrap helper is shared unchanged. Family/protocol/category/seed stay separate; same-query quality is counted once, partial results excluded and duplicate copies are not independent repeats. Dataset pooled AU-PRO is not replaced by supplementary per-image mean/CI. No real RGB/GT decode, model/FAISS execution, new anomaly metric or bank/geometry/seed/fusion change occurred.

Validation: related37 passed(4.57s); full603 passed/3 skipped(256.99s), CPU smoke2 rows; fresh GitHub receiver37 passed(8.23s)/smoke2 rows. Skip2: actual RAM1827414016 versus2186018816bytes including unchanged2GiB reserve; skip1: optional MVTec data is absent from the code-only worktree. All20 new/modified public file bytes and existing20 fit-source/7 reference bytes match the receiver. It explicitly reuses the original .venv and local pinned submodule cache; data/weights/venv did not transfer. Base8abed..head is one audited code/docs commit with23 before/after text blob versions.

Actual local inputs: Hazelnut391 normal train/110 test(40 normal70 anomaly), Screw320/160(41/119), Capsule219/132(23/109). Existing split helper creates seed11 fit/cal313/78,256/64,175/44 and seed23/37 manifests. Category ZIPs and original notices are under outputs/mvtec-team-inputs-20261101/. Archive source entries575/603/464 match their file inventory. These are file/split checks, not decoded geometry/model/metric checks. Inputs are not pushed.

Existing stored metrics generate10 rows/3protocol groups at outputs/bank-domain-analysis-20261101/outputs/master-report-20261101/. Receipt cache verified5 supplied manifest entries for the existing Jihyuk return and a second call hit cache. New GPU bank-domain results have not arrived; no figures or numeric results for them were created.

Small offline handoff: outputs/cpu-bank-domain-delivery-20261102/CPU_ANALYSIS_DELIVERY_20261102.zip. Its incremental Git bundle83ef..1f0c801 contains5 already-public commits only; old4commit bundle is preserved. Data archives are separate. Detailed verification/reproduction: outputs/bank-domain-analysis-20261101/outputs/verification-20261101/VERIFICATION.md. Next: Jihyuk emits the five-file producer contract and runs bank-domain study; Juhyung continues PCB execution; CPU reads their stored returns. Private evolution noteStage45 is kept ignored/untracked and outside this public commit.

### Jihyuk independent return and expanded two-GPU campaign package (2026-10-31)

Verified independent-bank-review-20261031-005151-733e320a.zip:11485 bytes,SHA256 68bd4167a1e82ec4ddba3363cb907bf592324a2dad38b25bea6b3165bb9cc05f,6 files/5 manifest matches. Despite the filename, actual checkout HEAD in the report is83ef04e; GitHub443 fetch failed, so the NO_GO is limited to missing newer code/actual bank on that host. Current remote remains8abed72. Supplied toy counterexamples describe old lazy-reader/sample-binding limits, not a failed real producer or new-reader run. Reused existing latest reader tests locally:9 passed,25 deselected,1.89s; no whole-suite rerun or actual model/metric execution.

Jihyuk reports16GiB installedRAM,7.84GiB available snapshot and19.33GiB free disk, so native PCB is assigned to Juhyung while Jihyuk owns224-scale MVTec bank-domain implementation/execution. Long prompts combine prior review with substantive queues: Jihyuk3categories x3seeds x4cells (36 planned dataset evaluations), plus limited EfficientAD; JuhyungPCB full, Screw4-endpoint comparison and separate2category x7degradation x4restoration (56 planned conditions). These are prospective tasks, not completed measurements. CPU owns input/metadata handoff and analysis/reporting to avoid concurrent execution-file rewrites.

Created outputs/two-gpu-campaign-20261031/ with REVIEW_JIHYUK.md,three role prompts,README,focused-test log and offline public-code bundle. Bundle83ef..8abed contains4 already-public commits,22 changed text blob versions;verified bundle heads/prerequisite,60223 bytes,SHA256 3fd28436570fba9953317995a4e0293a8c0169b4a6b289a8cce46eeefb0fea51. No private original history,notes,dataset/weights/bank/prediction/RGB/venv included. It delivers existing source, not the still-to-implement bank-domain/full executor. No source commit/push occurred. Original local-only evolution noteStage44 updated separately.

### Research expansion prioritized over repeated validation (2026-10-31)

User clarified that both GPU operators should run more substantive, high-quality experiments rather than remain in repeated validation/approval loops. Prepared outputs/research-expansion-20261031/ROADMAP.md and three replacement role prompts. This is a prospective expansion; historical protocols, negative results and previous full-approval=false artifacts are preserved.

Juhyung owns completing the PCB real full-cohort path and execution, including one initial actual-bank integration when needed, existing normal calibration/quality/exact evaluation and practical resume. CPU owns a new normal-bank domain study and reporting; Jihyuk executes its clean/restored normal-bank by Bicubic/SwinIR query 2x2, first Hazelnut then the same fixed Screw design. Existing code currently uses a single clean bank in Branch B, so this is a new proposed study, not a completed experiment. Later priorities are category/seed repetition, a separate realistic-degradation restoration comparison and selected-condition detector generalization, rather than the full Cartesian product.

Previously completed full110 already compares Bicubic, SwinIR, RRDB-PSNR and RRDB-ESRGAN; those results are reused rather than rebranded as new repeats. Automatic source/input/leakage/resource checks remain; manual document approval between every stage is removed from the new task prompts. Actual technical guards are not bypassed and missing full executor must be implemented. No new source, fit/inference, anomaly metric, pytest run, commit or push occurred while preparing this plan. Prose audit and diff checks verify the new documents; actual experiment results remain pending.

### Opus design return compared with already-published reuse code (2026-10-31)

Verified the supplied pcb-reuse-design-review-20261030-190249.zip (27187 bytes, SHA256 cf94c47afd1bc18db9b92a3d6d532cc4fb72e26055753bdadcf43e500465f4c6), safely extracted 11 files and matched all 10 manifest entries. Its WAITING_FOR_CODE assessment used 865f26a; current local and actual remote tip are 8abed721eec43f14e9e04fae005f6b5cb6faa702. Current admission already binds all 20 fit source files, including the proposed seven feature paths, seven references and checkpoint identity. Dedicated smoke reader and FrozenPCBInputs.rgb exist. No new GPU return or execution was received/performed in this review.

Remaining focused work: board assembly/save timing and per-board RSS ledger; explicit clean-spool reconstructed RGB equality in the reader; targeted source-drift/callback tests. External explicit bank reference versus a verified portable copy remains an engineering tradeoff for updated peer review; the existing full/synthetic reader was not changed. Existing FrozenPCBInputs.evaluation_mask is present, while real full-cohort integration and final approval remain separate gates.

Reproduced the overlap-mean/max-score counterexample with two small synthetic maps using existing assemble_board: overlap 5.0 versus board score 10.0. Torch/FAISS were not imported. This is a structural check, not a measured PCB/SR failure or anomaly metric. No source edit, new pytest run, commit, push or model execution occurred. Previous 568-pass/3-skip source verification belongs to the published implementation and is not reported as rerun here.

Evidence: outputs/pcb-native-memory-readiness-20261017/outputs/pcb-opus-design-review-20261031/{REVIEW.md,verification.json}. Three updated role prompts: outputs/pcb-opus-followup-prompts-20261031/{CPU_REVIEW_RESPONSE_AND_TELEMETRY.md,JUHYUNG_REVIEW_AND_ONE_REUSE_SMOKE.md,JIHYUK_INDEPENDENT_REUSE_CODE_CHECK.md}. Next: minimal CPU patch/publication, independent updated peer review, then one fixed actual-bank 432-query integration smoke if GO and fresh preflight pass. No repeat fit/probe or full380 is authorized by this review.

### Load-only reviewed-bank integration published and received (2026-10-31)

Completed the pasted CPU implementation task in the existing worktree. Public exp/pcb-full-producer-integration HEAD is8abed721eec43f14e9e04fae005f6b5cb6faa702. Added the reuse CLI/module/dedicated reader,34 tests, handoff and minimal public records/line-ending rules. The explicit reviewed bank remains external/read-only; its original865f26a/dirty=true is preserved while the new run records its own commit/interpreter/Python/NumPy/device. Existing20 fit source/7 reference bytes match; execution now binds24 source files. Only the pre-fixed1-calibration/2-test three-variant integration is enabled; no real fit replay, GT/statistics/threshold/metric or full executor.

Final full pytest568 passed/3 skipped in193.16s. The two existing subprocess skips required2186018816bytes including the unchanged2GiB reserve but observed996282368/996286464bytes available; the third is optional MVTec data. All34 new tests pass, also34 pass with Torch/torchvision/FAISS/timm/PatchCore imports denied(7.66s); CPU smoke2 rows passes. Metadata-only bank preflight correctly exits2 before models because actual NPY files are absent here. The reviewed actual bank was not downloaded/faked to make a pass. New plan8.687914GiB available RAM/1.161637GiB free disk is a scenario, not observed peak/bound.

Audited865f26a..8abed72 including1 commit/10 before-after blob versions, exact seven-file staged whitelist and unchanged staged/committed blobs; no private notes/data/weights/arrays/original unpublished history. Only the integration branch was pushed. Fresh GitHub clone outputs/pcb-reuse-receive-check-20261031 has the exact HEAD/ancestor/pinned submodules and matching24 source/7 reference hashes. Receiving34 tests pass(10.56s) and CPU smoke2 rows passes using original .venv explicitly; clone itself has no dataset/checkpoint/venv. Process-scoped LFS skip avoids unused upstream payload downloads; no global settings changed. Source/receiving trees clean and original79a1c0f branch/user changes preserved.

Handoff: docs/PCB_BANK_REUSE_INFERENCE_HANDOFF.md. Local evidence: implementation outputs/pcb-reuse-delivery-20261030/VERIFICATION.md, full-suite-release.log/XML, runtime-denied-release.log, publication-audit.json, receiving-check.json and receiving logs. Private local evolution note updated/ignored/untracked. Peer design reviews are not yet received, so publication is not their approval. Next: Juhyung reviews the exact new code and, after his integration GO and fresh preflight, runs the existing actual bank once for432 queries/9 maps/test RGB spool. Jihyuk may independently review/test the same code. No actual model/GPU/full cohort execution or new scientific metric was generated here.

### Three-role independent design/implementation prompts prepared (2026-10-30)

Prepared local prompts in outputs/pcb-design-and-reuse-prompts-20261030/: CPU_REUSE_INFERENCE_AND_PUBLISH.md, JUHYUNG_INDEPENDENT_DESIGN_AND_GPU.md, JIHYUK_INDEPENDENT_CONTRACT_REVIEW.md. User requested that Juhyung's existing Opus session make independent design judgments and return evidence/alternatives/recommendations, rather than only execute our commands. The prompt covers research-question relevance/confounders as well as the engineering admission/provenance/RGB/resource contract, permits disagreement and a GO/NO_GO recommendation, and preserves the separate full-execution gate. This assignment does not assert comparative model superiority.

CPU prompt implements/tests/audits/publishes a load-only actual-bank integration path and handoff. Juhyung can review the existing design immediately and, only after exact new-code receipt and his GO/fresh preflight, execute one fixed1-cal/2-test actual-bank integration. Jihyuk can immediately review adversarial contracts and later run focused tests; optional GPU crosscheck requires the same actual bank and explicitly documented scope, never a refit or implicit cohort merge. All three can start nondependent work without repeated polling. No results from these future tasks are claimed.

Targeted source checks reconfirmed that load_raw_run requires raw-local bank/provenance and full-cohort admission while RGBSpool is synthetic-only. Prompts explicitly leave these old guards intact and require an honest new integration artifact/reader contract. Current implementation remains clean at865f26a; the new run_pcb_reuse_inference.py and handoff are requested additions, not existing published commands. Prompt prose checks found no suspicious Unicode/placeholders. Original progress/private ignored note updated; no framework changes, tests/model execution, commit or push occurred in this prompt-writing task.

### Actual fit-bank and independent input/test returns reviewed (2026-10-29)

Received pcb-fit-bank-review-20261029.zip(697901B,SHA256647bac5e01da7b6ebaaac620de0581988e86f75daafb65bf564da2b7f1d3cb1e), FIRST_LOCAL_GPU_METADATA.zip(92729B,expected SHA2564e4fd0b09abeae396f2863b352c39ef7acee26914c630fc82e9701faf932b0c6 matches), FOLLOWUP_METADATA.zip(278948B,SHA256b7a885e2a563af91fba5ac9d0a1ca5a678268b3957b6cbb1a48a4e1d1f365b38). Safely received89 metadata files; all86 manifest entries match. Original archives remain unchanged. Read-only local checks return SUPPLIED_METADATA_CONSISTENT_NOT_FULL_APPROVAL. Bank/index,11 raw arrays, dataset/checkpoint bytes and remote execution remain unsupplied/unobserved locally.

Juhyung865f26a/dirty=true reports actual normal-fit completion:721 parents, observed/validated27132672,stored262144x1024 float32.20 source/7 reference hashes, preflight identity, bank/protocol/receipt links and expected selection/index-NPY digest match. Recorded actual bank digest19c3bb03a6b84475bfdc36602d05b975c57c387da81f0713c5da86b8d2f1278e; retain privately on GPU host for reuse. Actual/fit-integrity flags true; full-bank/cohort/approval false, metrics/threshold/calibration null. Recalculated17307 calls/four phases:outer1358.670672200s,fit-stream1319.060207900s,feature17304 calls1144.075326403s,all-child sum1169.007184803s. Correct the record's further-subset wording:all-child sum includes factory/integrity/close OUTSIDE fit-stream; both are inside outer. This is a reporting correction, not a failed run or source-artifact change. Sampled/lifetime RSS2.405396/2.410137GiB and CUDA allocated/reserved0.445433/0.505859GiB remain distinct; drive delta-2.092323GiB is not output1.002508GiB.

Jihyuk's original83ef04e limited raw/bank metadata is byte-identical between ZIPs. Decode followup passes reported structural audit1101 RGB/200 test mask inputs(100 actual GT files), frozen split/file digests,332 four-connected input regions. All721 decoded fit RGB receipts match Juhyung's compressed AND decoded digests. Supplied logs confirm38 focused/4 fake-adapter tests and CPU smoke2 rows; these are remote logs, not local reruns/full-suite completion. Whole pytest remains incomplete and stalled node/cause unknown; peaks unmeasured. Initial local validator dict/hash comparison error was corrected with raw artifacts unchanged; failed record retained.

Evidence: implementation outputs/pcb-two-gpu-review-20261029/REVIEW.md,verification.json,archive_receipts.json,review_metadata.py and original extracted metadata. Next CPU task is actual-bank reuse-only inference/RGB-spool integration, preserving synthetic full guard; next GPU is one fixed1-cal/2-test integration with that262144 bank, then frozen180/200 cohort and existing normal-only calibration/quality/evaluation. Prior native180/200 resource rehearsal succeeded on2026-10-18 and is not relabelled unexecuted; retain its version/scenario limits and fresh resource gates. No new model/metric/whole pytest, source-code commit/push or full-pilot approval occurred in this review.

### Real fit-only bank code published and clean receipt verified (2026-10-29)

Implemented the requested CPU task in the existing integration worktree. Code commit05f3cdd72543884f0e0da75a45fca320f2bf17d5 adds the guarded real fit-only CLI/module,34 deterministic tests, handoff and minimal public records/line-ending rules. Docs-only commit865f26aabf4598354e1b8fb4605dc9ff09a7e810 explains process-scoped skipping of unused upstream LFS model payloads. The integration branch alone is pushed; actual git ls-remote and the separate receiving clone both confirm865f26a. Full83ef04e..865f26a range audited:3 commits including the prior a7 reviewer,22 before/after blob versions, no forbidden payloads/private notes/original unpublished research history.

Final executable source tests:34 new passed; full536 passed/1 optional MVTec-data skip in185.59s, CPU smoke2 rows. Latest docs-only tip has identical20 bound source bytes. Fresh GitHub receiving clone at outputs/pcb-fit-receive-check-20261029 verifies the required a7/ef2 ancestors, pinned submodules,20 source hashes,7 references and frozen fit selection; receiving34 tests pass in3.69s and CPU smoke2 rows passes. It reuses the original .venv interpreter explicitly; data/checkpoints/venv did not transfer. Plain submodule initialization first failed on an unused upstream LFS model download/DNS; that failed checkout is recorded and was repaired only in this newly owned receiving clone, using source pointers and the unchanged pinned source. No global Git/LFS/OS setting was changed.

Actual local static preflight, before commit at a7/dirty=true, verified721 compressed fit-image hashes, official CSV, references/sources and checkpoints, then returned PREFLIGHT_BLOCKED for RAM: snapshot2626314240bytes available vs6661915776bytes required. No Torch/FAISS runtime import, RGB decode, model or bank allocation occurred in that static check. The fit plan is4.204393GiB payload+2GiB reserve,2.064453GiB disk, not an actual-fit peak or upper bound. GPU opt-in must recheck live CUDA/resources/bindings; there is no CPU fallback/resume/shape override. Only the721 normal-fit stream is allowed, with27132672 observed/validated and262144 stored vectors, frozen selection/order/geometry/seed, no cal/test/GT callback, restoration/prediction/scorer binding/calibration/metric. Full producer guard remains unchanged.

Local evidence: outputs/pcb-native-memory-readiness-20261017/outputs/pcb-real-fit-delivery-20261029/ (full/receiving test logs, XML, audits, source receipt and VERIFICATION.md). Original exp/profiling-results-demo HEAD79a1c0f and prior user PROGRESS edits are preserved. Private evolution note remains ignored/untracked. Jihyuk's ZIP is still not locally received/verified; his decoded-input check and complete pytest remain unconfirmed. Next: Juhyung receives the exact public865f26a commit and executes the new normal-fit-bank CLI once after fresh preflight. Actual bank, full cohort inference/calibration/metrics and final full-pilot approval have not been produced here.

### Three-role next-task prompts and Jihyuk report triage (2026-10-29)

Prepared local prompt files under outputs/pcb-three-role-prompts-20261029/: CPU_IMPLEMENT_AND_PUBLISH.md, JUHYUNG_GPU_REAL_FIT_BANK.md and JIHYUK_INPUT_AND_TEST_REVIEW.md. The CPU task implements/tests/audits/publishes a guarded real fit-only bank path; Juhyung executes it once only after the new exact public commit and preflight are verified; Jihyuk preserves his independent raw smoke and completes sequential input decoding plus focused diagnosis of his interrupted pytest. The earlier two-role drafts remain in outputs/pcb-real-fit-bank-prompts-20261029/. These are task prompts, not implemented or executed capabilities.

Current source check: implementation remains clean at a7b2a26c26aa7a26589a0da4f3af88e297c006a3; actual origin branch remains83ef04e6a55f12f7d7cb6d6bfd69bebab98793d9. Existing input-audit CLI supports decoded sequential RGB/test-GT structural verification without models/metrics. The new real-fit CLI is still absent from the published tree. No source change, test-suite rerun, model execution, commit or push occurred while preparing these prompts.

Jihyuk's user-forwarded report states raw COMPLETE at83ef04e on GTX1660 SUPER6GiB, Python3.11.9/Torch2.14.1+cu126/torchvision0.29.1+cu126; bank37632x1024 and nine maps reportedly passed finite/hash checks. Only file hashes, not decoded inputs, were audited. Full pytest stopped after about46 minutes at16%, with no final counts; RAM/VRAM peaks are unmeasured. FIRST_LOCAL_GPU_METADATA.zip expected SHA256 is4e4fd0b09abeae396f2863b352c39ef7acee26914c630fc82e9701faf932b0c6, but the ZIP and11 arrays have not been supplied to this PC. These remain operator-reported claims, not independent local artifact verification. No cross-machine numeric parity or full-pilot approval is asserted.

### Deliverable status clarified, no new experiment (2026-10-29)

Rechecked current source/status: implementation remains clean at local a7b2a26. Existing MVTec Hazelnut/Screw and full110 evidence synthesis is available; its closed-scope record does not require reopening new models, gating or Capsule. The later PCB native-tiling work is a separate protocol family and currently has structural, CPU pipeline and reported GPU synthetic-resource evidence, rather than actual full-bank/380-board performance.

For the current PCB-inclusive final package, the remaining sequence is real-input fit/bank/producer connection on CPU; actual reusable clean normal-fit bank creation on GPU; frozen three-variant calibration/test inference; normal-only calibration, board quality/detection evaluation on sufficient-RAM hardware; and final evidence-linked report/presentation/reproduction material. Target deliverables are the research analysis, reproducible implementation/artifacts and final manuscript/presentation. New method superiority is not an established result. This entry clarifies status and next actions; no scientific scope/metric/threshold change, code change or execution occurred.

### Full-cap synthetic GPU return reviewed locally (2026-10-28)

Received pcb-fullcap-probe-review-20261028.zip, 59425 bytes, SHA256 f7cddc837ca79c2e428e37f7e85c42ffd2f8e3308703d39a94a13407b6793486. Safely extracted14 files and verified13 manifest digests. Two flattened reference filenames caused the expected original-layout rejection; copied six reference metadata files into a separate canonical layout with identical bytes, preserving original archive/JSON/hashes. Actual a7b2a26 CPU reviewer then returned CONSISTENCY_VERIFIED_NOT_FULL_APPROVAL / REPORTED_CUDA_SYNTHETIC_FULLCAP_PROBE for execution83ef04e/dirty=true. Ten preflight/execution identity groups match.

Independent CSV recalculation:16 calls/8 phases, outer33.819174699951s, child sum28.794385900255s, residual5.024788799696s, detector6 calls19.309442800004s. RSS sampled/lifetime both4449710080bytes(4.144115448GiB), kept separate; CUDA peak allocated/reserved370.314941406/426MiB. Output before cleanup1073746620bytes; drive-wide free change+49913856bytes, not output size. Residual is inside outer and outside child sum; causes were not separately timed. Explicit use of the existing CUDA venv after bare python resolved to system Python is documented and consistent with task intent.

CPU implementation evidence rechecked:502 passed/1 skip, related126 and CPU smoke2 rows from the prior code verification; suites were not rerun for this unchanged-code receipt. New actual check, source/reference bindings and manifest/calculation checks pass. Deleted synthetic NPY, checkpoint bytes and11 missing reference arrays remain unverified locally; independent remote attestation and all full-bank/full-pilot approval flags remain false. Evidence: outputs/pcb-native-memory-readiness-20261017/outputs/pcb-fullcap-return-review/received-20261028-f7cddc83/LOCAL_REVIEW.md, review/review.json, independent_checks.json and layout_map.json. Next is guarded real-input fit/bank/producer integration and actual normal-fit bank creation, followed by separate native resource/final approval gates. No local model/FAISS/metric run, source change, commit or push.

### Full-cap return reviewer implemented and committed locally (2026-10-28)

Implementation worktree local commit a7b2a26c26aa7a26589a0da4f3af88e297c006a3 adds the separate read-only full-cap reviewer, CLI, 73 tests and docs/PCB_FULLCAP_RETURN_REVIEW.md. Explicit --reference-run prevents following remote JSON paths. Checks include fixed scope, execution commit/canonical and raw-byte bindings, hash links, six queries/sixteen ordered calls, summary/RSS/CUDA domains and cleanup. Deleted/omitted arrays and checkpoint bytes remain unverified. Status SHA is a computed receipt, separate from the three checked artifact links. The old reviewer, producer, models, metrics and frozen bindings are unchanged.

Final related tests126 passed(39.39s); full pytest502 passed/1 optional-data skip(139.36s), CPU smoke2 rows and diff checks passed. Fresh-process runtime-import denial covers the full review path; a real tiny injected producer fixture is rejected as GPU full-cap evidence. Existing83ef04e source and limited-reference compatibility pass; its11 omitted arrays remain unverified. Local verification evidence is outputs/pcb-native-memory-readiness-20261017/outputs/pcb-fullcap-review-readiness-20261028-230346/. Staged audit covered seven text files and unchanged12 probe source bindings. Implementation tree clean; original79a1c0f branch preserved. No push, actual new GPU return, full-cap allocation or full executor activation. Next: review real return, then actual fit/selection/full producer/current resource/final-approval gates.

### Next two-role handoff and report annotation (2026-10-28)

Rechecked implementation and origin delivery HEAD: 83ef04e6a55f12f7d7cb6d6bfd69bebab98793d9, exp/pcb-full-producer-integration; implementation tree clean. Prepared two local prompt files under outputs/pcb-next-prompts-20261028/: GPU operator executes at most one guarded full-cap synthetic resource probe; this PC prepares its separate read-only return checker and CPU tests. The latter is a requested next task, not implemented by writing the prompt. Neither new GPU execution nor full approval occurred. Prompt files and private notes were not pushed.

The prior report output was no longer at its old filename. Preserved the newer user-edited ../중간보고서/디자인프로젝트_중간보고서.docx (SHA256 b14adabc637e2d13e5785e4336706f9e9193247ad7fba1b78bebd5c7337d9a05), including its added cover, and removed only the selected metadata paragraph in a new ../중간보고서/디자인프로젝트_중간보고서_날짜문구제거_20261028.docx. Only word/document.xml differs; no research or table content changed. Word export has 12 pages, all visually inspected. Removed text absent; original remains unchanged. QA: ../중간보고서/.작업/날짜문구제거_20261028/. No commit/push.

### Interim report feedback incorporated (2026-10-28)

Created ../중간보고서/디자인프로젝트_중간보고서_의견반영_20261028.docx from the retained 20261022 review copy. Moved background/methods to page 3 and renumbered table captions. Added the pcb2 selection rationale, clarified that test 100 normal + 100 anomaly images are separate from the 901 normal-training images (721 fit + 180 calibration), and placed the native-tile preservation conclusion below table 7 with its RGB/GT and component-audit scope. Rephrased repetitive negative prose while retaining uncertainty and remaining work.

Original SHA256 9e69f407b4db0feaa293e4e09f949dd60b7d9fdfba239898dbc4c92cb72b4ce8 remains unchanged. Only word/document.xml differs in the new package; 19 other parts and numerical result tables are preserved. Native Word PDF export has 11 pages; all 11 page PNGs inspected, methods confirmed on page 3 and PCB explanation on page 8. The packaged LibreOffice renderer was unavailable; existing Word export plus bundled PDFium rasterization was used. Text hygiene: no suspicious Unicode. QA evidence is ../중간보고서/.작업/피드백반영_20261028/. Research cutoff remains 2026-10-20; no later GPU measurements or new experiments added. No commit/push.

### Full-cap engineering probe implemented, tested and delivered (2026-10-27)

Published83ef04e6a55f12f7d7cb6d6bfd69bebab98793d9 to the same exp/pcb-full-producer-integration branch after seven-text-file audit and fast-forward. Adds a separate synthetic resource CLI/module,30 tests and docs/PCB_FULLCAP_RESOURCE_PROBE_DRAFT.md. It plans/guards fixed262144x1024 float32 payload plus six synthetic tile queries through unchanged models/CPU exact scorer. No actual bank fit/selection, GT/calibration, research outputs or full approval. Default is preflight-only; actual execution remains opt-in on a separately authorized CUDA host. Original36 bound source/reference bytes unchanged; private records and received artifacts excluded.

Full suite429 passed/1 optional-data skip(180.96s); final focused30 pass(5.59s), backend-import-denied30 pass(5.57s). Existing CPU smoke passes. Last local no-execute preflight BLOCKED_MEMORY/exit2:8893863936bytes required(8.283056GiB),2004021248 available snapshot; no large payload/model allocation. The old temporary no-Torch venv failed startup and was not modified; import-denial used normal Python. Pre-commit preflight source2f418c0/dirty=true remains historical, not rewritten.

Independent GitHub receiving clone fetched/fast-forwarded to83ef04e, verifies38 byte hashes/22 canonical blobs/two pinned submodules and actual receiving-src import. Receiver30 focused tests(5.60s), CPU smoke2 rows and CLI help pass; tree clean. Original Python reused; no fresh CUDA environment/data/weights supplied by clone. Evidence: outputs/pcb-native-memory-readiness-20261017/outputs/pcb-model-resource-review/received-20261027-e2270fc4/FULLCAP_IMPLEMENTATION_VERIFICATION.md and fullcap_receive.json. No actual GPU/FAISS/full-cap allocation/native run performed here. Next: separate GPU resource-probe execution review, then actual-bank/full-producer/current-resource approval; no repeated identical limited smoke or new research tuning.

### Received limited CUDA resource measurements reviewed (2026-10-27)

Reviewed55904byte ZIP e2270fc445d77c6b5f3ddc960e1d3aaf866983b4092fdf2144f1930e3f87c437 from the established GPU operator. Existing checker passes source/reference/contracts/timing consistency for reportedCUDA at2f418c0; dirty=true preserved. Independent recalculation:891 calls/8 phases, outer1073.346526300s, phases1055.357244501s, residual17.989281799s. Detector986.460462800s(91.9051% outer) includes CPU FAISS and other detector work; SwinIR52.999492000s. Sampled/lifetime RSS1.674801/1.688538GiB; CUDA allocated/reserved cumulative peaks456.123/518MiB, not full-system/full-bank bounds.

Correct interpretation:0.321175GiB is drive-wide free-space change, not attributable output size; output payload before resource files0.194236GiB. Residual timing causes were not separately measured. GPU-side checker reports12 raw hashes; ZIP supplies only bank/status among these, leaving11 arrays unverified locally. Local coverage is PARTIAL_OR_METADATA_ONLY, array-content/remote-execution attestation=false. No actual local inference/metric rerun. Evidence is ignored outputs/pcb-native-memory-readiness-20261017/outputs/pcb-model-resource-review/received-20261027-e2270fc4/LOCAL_REVIEW.md, independent_checks.json and local-review/review.json. Next is a bounded full-cap synthetic-payload resource probe, not repeated limited smoke or full approval; actual full-bank fit/selection, full producer and resource gates remain separate.

### PCB integration branch published and independently received (2026-10-27)

Published only exp/pcb-full-producer-integration at2f418c046bca5d607b7c3e199f4a85396c851fb4; remote ls-remote confirms HEAD and included ef2ca86. Five linear commits above public bb22cf8 comprise four previously local code commits plus one handoff/record-only commit. Final audit covers28 historical paths/43 blobs(largest66390bytes), including intermediate versions, with no forbidden file/binary/credential signature. Original private79a1c0f is not an ancestor; original research branch/worktree changes preserved. No force push/main merge/other-branch push or PR creation.

Fresh CPU pytest397 passed/3 skipped(205.37s), existing CPU smoke2 rows passes. Focused worker confirmation1 passed/2 skipped preserves actual-RAM guard:1848459264/1848520704bytes available versus2186018816 required. Third full-suite skip needs optional MVTec data. Local setup verify-only passes1202 input files and both checkpoint hashes after explicitly pointing to the original SwinIR path; first missing-worktree-checkpoint attempt remains logged. No input copy/download/model execution. All three configured download URLs return200 to HEAD requests, not payload-hash verification by HTTP.

Fresh HTTPS GitHub clone at [로컬 경로 생략]

### Two GPU operators: delivery prerequisite and bounded work allocation (2026-10-27)

Read-only local/remote inspection confirms the integration worktree remains at ef2ca8614cb1067a26af034a45ecf339b9d58a4f with a clean tree. git ls-remote confirms exp/pcb-full-producer-integration is not published; public memory-readiness/tiled-handoff heads remain bb22cf8/d732574. Four local commits extend bb22cf8. Prepared separate prompts: local CPU reviews/publishes only this bounded code history and verifies a clean receipt; existing GPU operator measures the instrumented fixed limited smoke; first-time GPU operator installs Python3.11/CUDA dependencies, verifies the licensed pcb2 bundle and two pinned publisher checkpoints, then runs the unchanged independent raw smoke. New-machine smoke is environment/reproducibility evidence, not a new dataset experiment or strict cross-device parity claim.

No push, installation, model/native execution or new tests were performed in this prompt-preparation session. Prior399/1 test counts remain historical. Both GPU tasks stop at limited1-fit/1-calibration/2-test scope; full-bank262144 evidence, full producer disk/lifecycle and explicit full approval remain pending. The licensed pcb2 input setup is already implemented by scripts/setup_pcb_gpu_inputs.py; other datasets/models are not prerequisites. Existing PROGRESS/private rationale records are reused; no competing research log or code change. Private note remains ignored/untracked. The memory observer reported429; direct memory lookup worked, and repository records remain the evidence source.

### Returned resource evidence checker prepared locally (2026-10-20)

Local commit ef2ca8614cb1067a26af034a45ecf339b9d58a4f on exp/pcb-full-producer-integration adds a read-only limited-smoke return checker, tests and handoff documentation. It verifies source/reference/hash-chain coverage, frozen cohort/variants/RGB receipts, timing/call counts and RSS/CUDA counter consistency without model or array loading. Missing heavy payloads remain explicitly unverified; consistent reported CUDA metadata is not independent execution attestation, array-content validation or full-bank approval. Actual GPU resource return is still pending. Previous input-binding/resource-tooling commit4b3368e is preserved.

Final full pytest399 passed/1 optional-data skip(178.95s); no-Torch/FAISS reviewer23 passed(13.67s); existing CPU smoke2 rows and diff checks pass. Current CPU preflight-only artifact correctly returns REJECTED_NOT_FULL_APPROVAL, exit2. Existing scientific/model/geometry/memory-guard/v0.6 protocol sources unchanged relative4b3368e. Source worktree clean after commit; original research checkout/prior progress preserved. Evidence: outputs/pcb-native-memory-readiness-20261017/docs/PCB_RESOURCE_RETURN_REVIEW.md and ignored resource-review test logs; negative control outputs/pcb-model-resource-review/preflight-negative-final-20261020-191303 in that worktree. Private rationale note updated separately and excluded from Git. No push, actual model/index/GPU/native execution, new research result or full approval.

### Actual input callbacks and next resource-smoke tooling (2026-10-20)

Local commit4b3368e on exp/pcb-full-producer-integration(parentd88573d) adds frozen native RGB/test-GT callbacks, a sequential input audit and opt-in resource instrumentation around the unchanged limited model-smoke. Actual local1101 RGB/100 anomaly-GT files match frozen hashes; full decoded1101 RGB/200 test masks pass, unchanged721 fit/180 calibration/100-normal+100-anomaly test split. Four-connected regions332, evaluator region-mask payload498756960bytes. RGB/GT input verification68.733/4.794s is not model runtime. Initial blocked/hash-only attempts are retained; later decoding passed the unchanged2GiB-reserve single-board guard. No native180/200 map stacks or actual model/index/calibration/performance experiment ran.

Limited-smoke CPU preflight passes, factory/model_execution_started=false, torch2.14.0+cpu/cuda_available=false. New profiler records synchronized phases, sampled RSS/OS lifetime high-water/CUDA counters separately and rejects changed references/checkpoints before setup. It does not validate full262144 bank or enable the full executor. Final tests376passed/1 optional-data skip(221.69s), CPU smoke2 rows passed, no-Torch related53+29passed; old production science/model/geometry/guard/protocol sources unchanged. Existing tiny unit tests now isolate current desktop RAM, while subprocess tests still use actual probes (none skipped in final run). First full attempt's20 resource-dependent failures and OneDrive-folder atomic-replace error remain documented; final test temp is outside OneDrive, without OS/guard/statewriter changes.

Evidence: outputs/pcb-native-memory-readiness-20261017/analysis/pcb_input_binding/implementation-20261020/VERIFICATION.md and docs/PCB_INPUT_BINDING_HANDOFF.md / PCB_MODEL_RESOURCE_SMOKE.md in that worktree. Ignored decoded audit: pcb2-input-decode-final-20261020-180807; ignored model preflight: pcb2-model-resource-preflight-20261020-180410. Both retain pre-commitd88573d/dirty=true truth. Original research checkout and earlier progress edits preserved. Local-only rationale note updated separately and excluded from Git. No push/main merge/deployment; next requires separately authorized CUDA limited resource smoke, full-bank model/index resource proof, producer disk review and explicit full approval. Negative gating/full110 B/B-uncertain unchanged.

### Board/rehearsal memory guard corrected locally (2026-10-18)

Local commit d88573d on exp/pcb-full-producer-integration (separate outputs/pcb-native-memory-readiness-20261017 worktree, parent676b071) removes the board evaluator's duplicate demand for already-filled float64 map/bool mask stacks. Board and rehearsal share one guard: total cap includes the fixed2GiB reserve; current available RAM covers only not-yet-live planned bytes plus that same reserve. Small checkers explicitly record1GiB synthetic payload plus2GiB reserve as a3GiB total cap. Native21923497568byte pre-allocation requirement and full/real execution guards remain unchanged.

Validation: full pytest326 passed/1 optional-data skip(186.46s); related68 passed; no-Torch/FAISS budget/producer tests46 passed; CPU smoke passed(2 rows); staged diff check and protected science/model/geometry/protocol comparison passed. Added exact-boundary/one-byte-short, invalid byte/probe, integer-overflow and small evaluation accounting tests. Old metrics/results/predictions/hashes were not rewritten; no native/model/inference experiment or push. An initial sandboxed full attempt was interrupted; the completed run used normal execution permissions without OS/Git/test-setting workarounds. Evidence in worktree docs/PCB_MEMORY_GUARD_ALIGNMENT.md and ignored outputs/memory-guard-*.log. Original research branch/other changes preserved; local-only notes separately record rationale. Remaining: audited actual RGB/GT binding, model/index RAM/VRAM/runtime, producer disk and explicit final full-execution review. This CPU fix does not approve full pilot.

### Native postprocessing rehearsal completion accepted, not full approval (2026-10-18)

Received pcb-native-memory-cleanup-execute-review-20261018.zip(29182bytes, SHA256b175bcfd5f29e53ae2552124754f2aa66939cec70a17aacd3f85732cca58c55e).206 metadata assertions and existing completion loader pass. Separate011907 preflight and011933 execute fresh preflight pass;12 workers complete native1404x1070/180-calibration/200-test synthetic-score processing with source12/reference5 hashes unchanged. native_rehearsal_measured=true/full_pilot_approved=false. This resolves the earlier 'native never executed' evidence gap for THIS scenario, not a universal peak or real model validation.

Maximum individual OS lifetime peaks: calibration4.071GiB, normalization0.080GiB, quality0.320GiB, evaluation10.150GiB. Worker action sum1093.272511s; parent launch-to-exit sum1097.886997s, distinct from full runtime. Minimum parent-observed available11.097GiB. No model/FAISS/SR/VRAM or research-performance output. GT region check acceptance follows unchanged source plus evaluation exits; raw GT/per-file receipts were not provided. Planning/native_peak flags and20.42GiB gate remain unchanged; this result does not authorize local native execution on15.53GiB hardware.

New integration issue to review before full: native checker accounts for already-live maps/masks in guard_memory(live_bytes=...), whereas board.evaluate_variant rechecks its full envelope against remaining available RAM without that adjustment or the same fixed reserve. Synthetic producer currently uses the latter wrapper. Next CPU task should align/test these accounting semantics and real RGB/GT binding, then separately scope actual model/index RAM/VRAM/runtime evidence and producer disk budget. Existing full block remains. Local review records small Markdown unit/plan-comparison errors without changing original artifacts. No code/metric/bank/prediction change, native rerun, commit or push. Evidence: ignored outputs/pcb-native-memory-native-completion-review-20261018/REVIEW.md and verification.json. Earlier blocked entries below remain historical records.

### Native retry ZIP independently reviewed, no new native execution (2026-10-18)

Reviewed pcb-native-memory-retry-review-20261017.zip(25840bytes, SHA25672fd90117d29b3c01507ef3785af1ab103afaf112e50186e09234bbf31b852d6).70 metadata assertions pass. Small27 files are byte-identical to the first received ZIP, not a new small run; existing completion loader passes. New235448 native protocol/status hash matches, execute_requested=false/stages empty, and source12/reference5 hashes and recomputed memory plan match the prior check/local code.

Retry available19276013568bytes(17.95GiB), required21923497568bytes(20.42GiB), shortfall2647484000bytes(2.47GiB); disk passes rehearsal gate. Native/model peaks remain unmeasured and full execution blocked. Existing time/unit corrections are valid, but parent runtime minimum is20275834880bytes, distinct from small preflight snapshot20406476800 and worker minimum20277796864. No process-RAM diagnostic/Git status raw output is included: availability decline does not prove lack of operator cleanup or identify a consuming app. Next is read-only memory-use diagnosis/operator-arranged resources, not another unchanged retry. No code/result/guard changes or commit/push. Local-only evidence: outputs/pcb-native-memory-retry-received-review-20261018/REVIEW.md and verification.json.

### Local physical RAM checked without native execution (2026-10-17)

Read-only Windows GlobalMemoryStatusEx snapshot: total OS-visible physical RAM16671768576bytes(15.527GiB), currently available3586400256bytes(3.340GiB). Existing native plan requires21923497568 available bytes(20.418GiB), exceeding even total physical RAM by4.891GiB. Closing local apps cannot satisfy this unchanged gate; use the adequate-RAM teammate host for native rehearsal, while small CPU tests/development remain local. No native arrays, model execution or OS/process changes. Available RAM is a transient snapshot, not a future guarantee.

### Teammate native-memory return reviewed: small pass, native still blocked (2026-10-17)

Received `pcb-native-memory-review-20261017.zip` (25265bytes, SHA25689c601ff76498995dc508db1b16cf355c62aa197922069246e3d9a19ab2dc84d). Byte-preserving metadata review passes171 assertions plus existing load_completed_rehearsal validation:12 source hashes match unchanged local/public code,5 frozen references match, protocol/CSV/12 worker hashes and CSV/JSON numbers agree. Small run pcb-memory-small-20261017-201510 completes12 workers; OS individual peak110030848bytes(104.93MiB). Recomputed worker action sum6.259233400s, parent launch-to-exit sum10.372911200s; these are different timed scopes, not full runtime/native measurements.

Native pcb-memory-native-preflight-20261017-201553 is correctly BLOCKED_MEMORY: required available21923497568bytes(20.42GiB), observed20398669824bytes(19.00GiB), shortfall1524827744bytes(1.42GiB). Disk180108976128bytes passes the rehearsal's4681310976-byte gate only. execute_requested=false and no stages; native memory/GT evaluation and actual model peaks remain UNVALIDATED. Preserve dirty=true without assuming its cause. The report has arrived; the remaining blocker is resource feasibility, not waiting for this ZIP.

Review text corrections are recorded locally without modifying incoming evidence: worker sum6.56→6.26s; evaluation envelope19.78GiB→18.42GiB; parent/worker minima differ;12-file list excludes run_legacy_patchcore.py and does not bind log hashes. Setup1202-file verification and remote cleanup are reported, not independently rechecked from the ZIP. Next: operator-arranged available RAM then unchanged native preflight with a new ID; if still blocked use an adequate-RAM host, never lower guards. Public bb22cf8 already suffices. Full pilot/model runs remain blocked; no metric, bank, source or prediction changed, no commit/push. Details: ignored `outputs/pcb-native-memory-received-review-20261017/REVIEW.md` and verification.json. Previous producer integration checkpoint remains valid and local-only.

### Local producer integration completed, full execution still blocked (2026-10-17)

Latest separate local implementation: `exp/pcb-full-producer-integration`, commit `676b071178967381261a886599998ce56b31becc`, in existing worktree `outputs/pcb-native-memory-readiness-20261017/`, based on public bb22cf8. Original exp/profiling-results-demo/79a1c0f and previous document edits remain preserved. This commit is LOCAL ONLY, not pushed; the teammate's published memory-readiness branch remains bb22cf8.

Added streaming injected-synthetic producer, lossless produced-RGB reuse and seven-process integration. Generated2-fit/2-calibration/2-test case:16 observed vectors/7 retained, one bank bind,12 maps,8 transform calls per variant, zero quality-stage transforms. All7 workers exited0; fake model/index/scorer weak references released;2258944 consumed RGB bytes cleaned after artifact verification. Final executable14 source hashes match. Full pytest **294 passed,1 optional-data skip**; no-Torch/FAISS new tests **14 passed**; CPU smoke passed(2 rows); staged diff/protected-source checks passed. No actual model/native/GT/performance experiment was run. Maximum individual small-worker OS peak109326336 bytes is not a native/VRAM/global peak.

Native payload estimates: raw maps6.380GiB, produced RGB spool4.877GiB, normalized files6.716GiB; retained disk18.975GiB before RGB cleanup/14.098GiB after, excluding dataset/checkpoints/headers/margins. Producer visible RAM scenarios2.012GiB build/3.038GiB prediction exclude model/runtime/FAISS/page cache. Native postprocessing measurements, real model peak, total disk approval, actual RGB/GT factory binding and explicit final execution review remain pending. Full guard unchanged; actual full PCB bank/calibration NOT_CREATED. Evidence: implementation worktree `docs/PCB_FULL_PRODUCER_HANDOFF.md`, `analysis/pcb_full_producer/implementation-20261017/VERIFICATION.md`, ignored `outputs/pcb-full-producer/pcb-producer-synthetic-20261017-final/`. Next: review teammate native resource report, not automatic full execution. The earlier handoff checkpoint below records the prior state, not a still-missing synthetic integration.

### Current handoff checkpoint (2026-10-17)

This section distinguishes the original local checkout from the published PCB worktree. Original research checkout: `exp/profiling-results-demo` at `79a1c0f`; public resource-check code: `exp/pcb-native-memory-readiness` at `bb22cf8a1f7073229ff615b67b3df2a100763827`, based on public handoff `d732574`. No original unpublished history was pushed. Earlier dated entries below remain historical records, including their then-pending GPU review status.

- **Received CUDA raw smoke reviewed:** local `outputs/pcb-smoke-received-review-20261017/verification.json` records27 passing checks, bank(37632,1024),9 native maps and12 matching stored-file hashes. Separate preflight matches the embedded record. Preserve `source_worktree_dirty=true`; smoke peak RSS/VRAM was not measured. This is not a full bank, actual calibration or performance result.
- **CPU resource tool delivered:** `scripts/check_pcb_native_memory.py`, its module/tests, v0.6/lifecycle/native-memory handoffs and frozen references exist in the published worktree. Fresh remote-ref verification on2026-10-17 matched bb22cf8; the licensed pcb2 Release asset returned HTTP200 with274645313 bytes. Dataset delivery is via Release, not Git source; setup uses pinned input/checkpoint hashes.
- **Completed test evidence, not rerun in this documentation update:** published `analysis/pcb_native_memory/implementation-20261017/VERIFICATION.md` records280 passed/1 optional-data skip,22 focused no-Torch/FAISS tests passed, and CPU smoke passed. Small2-calibration/2-test synthetic memory rehearsal completed12 sequential workers; maximum individual OS peak working set109289472 bytes (104.23MiB), not native/combined/VRAM peak.
- **Native remains untested:** local native preflight was BLOCKED_MEMORY with2856202240 available bytes; no native large arrays/workers were created. Current gate requires21923497568 available RAM bytes (20.42GiB, including2GiB reserve) and4681310976 free disk bytes (4.36GiB, including1GiB margin). Native --execute on the teammate machine has not been reported. Installed32GB RAM alone is insufficient evidence.
- **Execution blockers:** full producer/RGB reuse/process orchestration still needs implementation and fake-model validation; native resource evidence and actual-model peak memory need separate review. Actual full PCB bank/calibration are NOT_CREATED and the existing full-pilot hard block remains. Negative gating and full110 B/B-uncertain are unchanged.

Next parallel workstreams: (1) teammate runs small -> native preflight -> conditional model-free native memory rehearsal, returning metadata/logs only; (2) local CPU development connects a streaming full-producer orchestration candidate using small synthetic/fake inputs only. No new bank/geometry/metric/seed selection, real PCB inference or full-pilot approval follows from either workstream. This checkpoint is a documentation update; producer integration has not yet been implemented, and no new model/native execution, commit or push was performed for it.

### 2026-11-18 · 주형 최종 비공개 반환 검토와 Fable 5.2 전체 검토 준비

사용자가 final-delivery-20261117-private.zip을 전달했고, 실제 Fable 5.2의 전체 검토·개선 설계에 넘길 프롬프트와 입력 준비를 요청했다. 최신 반환의 실제 기록 모델은 claude-opus-5-5다. 이번 작업은 Fable 검토 준비이며 실제 Fable 실행은 아직 확인하지 않았다.

원본 ZIP 48,629,145bytes, SHA-256 d39461caf2dc7ac52ce91390e91a7e7d38533a650b0039c25831355116c7ec58. receipt262payload의 bytes/SHA와 CRC가 맞았다. 내장 지혁 확장24payload도 이전 수신본과 같다. 주형3run/12cell의 manifest binding, per-image score 기반 image AUROC, PSNR/SSIM 평균을 CPU로 재계산해 일치했고 실행소스24해시를 기록 commit과 대조했다. pooled/pixel 지표와 full raw stack은 재계산하지 않았다.

gallery local image73참조에 누락이 없고 manifest76파일 해시가 맞다. MVTec zoom24슬롯 중23available이다. 선정6crop NPZ는 숫자형/finite 확인을 마쳤다. 해당 배열은 clean/SwinIR-restored bank 지도이며 Bicubic-bank 지도는 아직 수신되지 않았다. full raw stack/bank matrix도 미수신이다. 수신 포스터 preview와 대표 bank1패널을 시각 확인했으며 전체 gallery/PDF/PPTX 시각 검토는 다음 Fable 작업이다.

공개 소스는 handoff/juhyung73f7245, bankc60dd80, phone74dc9fa를 fetch해 확인했다. 원본79a1c0f와 사용자 변경을 보존하고 검토용 detached worktree를 새로 만들었다. 새 모델/장비실험, pytest, 공개 push, 외부 메시지 전송은 없었다.

새 패킷은 outputs/juhyung-final-review-20261118/fable-review-handoff다. prompt, Codex 수신 검토, 입력 조건, exact source map, tracked2113행/고유1013object의 미검토 ledger와 현재 기록 snapshot을 준비했다. 모델 확인→독립 전체 검토→Codex 대조→개선 설계→가능한 수정·검증→실제 사진/보고서/포스터 반환 순서다. 실제 Fable 모델 선택/라우터 증빙을 요구하고 불가시 모델 의존 검토만 대기로 남긴다.

역사적 Screw clean AUROC0.984218의 n_train320과 새 bank256fit/64cal 차이, Hazelnut CI에0포함의 해석, 교차검증 seed11clean-bank4cell 범위, 품질수치와 queryRGB hash 증빙 차이를 다음 검토에 포함했다. PCB 운영점의 실제 사진 전환과 phone artificialx4/실제 저조도·blur의 근거도 대조하게 했다.

새50장은 주형74dc9fa의 고정v2를 그대로 복사해 전달한다. 이전 CPU초안의 label/group 오류를 주형이 수정했으므로 owner-frozen-photo-plan이 현재 소유자 입력이다. 기본14cycle32장과 작은이물9cycle18장은 별도 집계한다. 새 사진·사람 판독·실제 취득시간·확정 팀정보와 지혁 기본24의6원래반환/미공개코드/선정6Bicubic지도는 외부 입력이다. UNO는 최종 시연 범위 결정에 따른다.

비공개 신규12결정 D-20261117-01..12는 원문 byte copy/수신receipt를 보존하고 기존 private Stage73에 처음 통합했다. 패킷 산문4파일의 숨은 문자와 최종 문장 점검을 마쳤다. 기존 자동화는 PAUSED 상태를 유지한다.

전달 패킷 최종 검증은 25파일/336317bytes, SHA-256 225b7a7d7f801b0d773700f5656505c7b410fbdbf220015257473004fa6c4c77이다. CRC와 인덱싱한24payload 해시가 모두 맞다. ZIP 안 기록은 포장 전 snapshot이고 이 최종 포장 기록은 외부에 남긴다.

### 2026-11-18 · 고정v2의 새50장 촬영 안내판

사용자가 이전24장 안내판처럼 새50장을 정리해 달라고 요청했다. owner74dc9fa의 v2 CSV50행을 그대로 번호화했다. 기본32장/평가14cycle, 작은이물18장/보조9cycle, 전체23cycle이다. 32번만L1대체도흐림이며 작은이물9cycle의L1은모두선명이다.

outputs/phone-capture-guide-50-20261118에 준비·위치PNG, 기본32PNG, 작은이물18PNG, 통합HTML, 간편50행촬영·시간·사람판독표와 owner계획/실행CSV를 준비했다. 기존4사진은구도·흐림예시로동일crop/resize만적용했고밝기·대비·합성흐림은없다. M1=P1,M2=P2,M3=P3는구역제안이며실제빈초록면에놓을점은촬영전에고정·기록한다. 저조도첫사진방조명OFF→평소방조명+선명L1대체로절차를명시했다.

50번호/조건·group·23cycle,owner4파일byte동일성,HTMLlinks,원고Unicode,PNG3장시각확인을마쳤고footer여백/줄바꿈을수정했다. 14개파일/3624030bytes SHAa9e4dc7e7e4e1c0aa5dcd5ea7f41da6a572996bb2406693e507b93bd64c14b44 CRC/receipt해시통과. 새관측사진은0장이고사람판독/실제시간도아직없다. 현재한기판·모사이물의고정촬영입력을50장으로채울수있으며,그뒤복원/검사/사진비교/정책평가가필요하다. 실제균열·단선·납땜결함과다른보드·현장의일반화근거는별도로남는다. 기존실행정책과완료실험은변경하지않았다.

### 2026-11-19 · 주형 반환 검토와 완료 조건 갱신

수신 ZIP의 인덱싱한 439개 파일 해시와 원본 JPEG 50장의 해시·촬영 순서를 확인했다. 촬영자 확인, 사람 판독, 실측 시간은 남아 있다. 저장 표를 다시 집계해 C2의 대체 사진 11건이 고정 v0.3에서 모두 REVIEW였고, 개발 변형의 작은 이물 9건 중 가장 큰 이상 영역의 위치 일치가 3건임을 확인했다. 자동 요약의 위치 미기록이 0으로 들어가는 문제를 표시했다. 실제 평가용 46장의 정렬 성공은 15→38이었다. ×4 위치 비교의 입력은 선명한 L1 9장이다.

Screw 참고 기준선 0.984218의 원 실행에 seed 11이 기록돼 있다. 기준선 원본·Bicubic·SwinIR 3개 반환 unit의 원 예측·results.json·per_image.csv 해시를 로컬 파일과 대조했다. A0 PDF 1쪽을 실제 렌더링했고 포스터의 팀 정보와 최종 제목은 확정 대기다.

사용자 결정으로 Fable 5.2 검토 및 실행 증빙 조건을 종료했다. 11월 18일 Fable 전달용 패킷은 이력이다. 같은 조명 참조 정렬은 v0.4 후보로 채택하며, 현 제출은 50장 고정 결과와 개발 결과를 표시한다. 후보의 독립 성능을 확인할 경우 코드·계획을 먼저 고정한 뒤 56장을 촬영한다. 새로운 검토와 정정 보고서, 50행 촬영 확인표 및 원본 판독표는 `outputs/juhyung-return-check-20261119/`에 있다.

### 2026-11-19 · GitHub 동기화와 지혁 포스터 자료 수신

GitHub 모든 브랜치 참조를 fetch했다. main은 로컬과 원격 모두 ba92bc0이다. outputs/github-sync-20261119에 주형 반환 69ba542, 촬영 실행기 f73bab4, bank 코드 c60dd80의 별도 작업 폴더를 만들고 각 원격 커밋과 일치하며 작업트리가 깨끗함을 확인했다. 현재 exp/profiling-results-demo@79a1c0f와 기존 작업은 보존했다.

지혁의 poster-assets-bank-domain-20261119.zip을 outputs/jihyuk-poster-assets-20261119에 비공개 입력으로 수신했다. 내부 22개 파일과 원래 반환 6개 ZIP의 90개 파일 해시가 맞았다. Screw seed 11의 Bicubic bank 지도 12개도 배열 해시가 맞았다. 주형의 포스터 선택 6사례와 일치하는 샘플은 없다. 24조건 원래 반환 메타데이터는 수신으로 전환했다. 정확한 Figure Z 6사례 지도와 실행 소스 대조는 남아 있다.

### 2026-11-19 · 비공개 결정 통합과 bank 28조건 집계 확인

`notes/RESEARCH_EVOLUTION_LOCAL.md` Stage 75에 주형 11월 19일 결정 8건(D-20261119-01~08)과 현재 판단을 반영했다. 수신 원문과 해시를 별도 보관했다. Fable 검토 종료, 50장 결과의 제출 범위, 56장 재촬영 조건, 최신 GitHub 작업 폴더와 지혁 자료의 수신 상태는 위 기록과 같다.

지혁 원래 반환 6개의 COMPLETE와 결과 파일 해시를 대조했다. Hazelnut·Screw의 seed 11·23·37, bank×query 각 4조건으로 기존 기본 24조건을 확인했다. 저장 영상별 점수로 image AUROC를 다시 계산해 24조건 모두 일치했다. 수신한 기존 확장 4조건을 묶어 `outputs/jihyuk-poster-assets-20261119/bank_domain_28_results.csv`를 만들었다. Pooled AU-PRO와 pixel AUROC는 저장 수치를 사용했다.

남은 일은 촬영 조건의 소유자 확인, 사람 판독과 실측 시간 확인, 28조건과 위치 집계의 제출본 반영, 팀 정보·제목 확정, A0 PDF 출력 확인이다. Figure Z를 유지하면서 Bicubic bank까지 보여줄 때는 동일 샘플 지도가 필요하다. 코드·런타임 출처 대조도 남아 있다. 같은 조명 정렬 후보를 독립 평가하려면 코드를 고정한 뒤 새로 56장을 촬영한다.

### 2026-11-20 · 피드백 대조와 50장 확인 화면

사용자가 포스터 팀 번호를 2번으로 확인했다. 저자·지도교수·소속·최종 제목은 별도 확정 후 A0에 적용한다.

11월 20일 받은 피드백의 수치와 자료를 대조했다. 고정 v0.3의 대체 조명 정렬 실패와 같은 조명 기준 정렬의 개선은 근거가 있다. 전체 정렬 점검 16/49→41/49에는 참조·보정 일부가 포함되며, 평가 사진만 보면 15/46→38/46이다. 개선안은 같은 세션에서 정한 개발 결과다. 작은 이물의 NG 9/9와 가장 큰 영역의 위치 일치 3/9를 함께 쓴다. 상위 3개 영역 출력은 제안이다. 약 −2.7°는 사진 간 정렬 추정치이며 실제 폰 이동은 촬영자가 확인한다.

지혁의 Screw 019·005 지도에서 Bicubic bank 고정 시 SwinIR 입력의 높은 점수가 더 넓게 분포한다. 두 그림에 GT 마스크가 없고 원인 실험이 없어 정상 영역 점수의 정확한 범위나 고주파 질감이 원인이라고 해석하지 않는다. 원 판 Figure Z는 manipulated_front/020.png이고 새 자료의 파일은 023.png다. 지혁 지도 6사례와 주형의 RGB 해시·지도 6사례의 교집합은 0건이다. 새 ZIP은 원래 24조건의 자료를 채웠고, F7의 동일 이미지 RGB 해시 대조와 F8의 동일 사례 지도는 자료가 더 필요하다. PCB 운영점 대표 4개 그림은 주형의 기존 반환에 있다.

`outputs/phone-original-review-20261120/`에 촬영자용 25쌍 확인 화면과 판독자용 원본 50장 화면을 만들었다. 판독 순서는 고정하여 섞었고 CSV도 그 순서로 맞췄다. 원본 50장의 해시, 두 페이지의 파일 링크와 사진 수를 확인했다. 사진에는 GPS 메타데이터가 들어 있다. 31·32번은 계획상 양쪽 모두 흐림이므로 원본에서 초점을 확인한다. 시간이 기록되지 않았다면 미측정으로 표시한다.

### 2026-11-20 · 회전 재시도와 사람 판독의 범위

50장 모두 평가 작업에 들어갔다. 참조 2·보정 2·평가 46장으로 구성되고, C2의 고정 운영 경로는 첫 사진 23장과 대체 사진 11장을 확인했다. 사람 판독은 46장 평가 사진의 검사 가능성을 독립적으로 기록하는 절차다. 운용 시에는 장비가 자동 판정하고 해결되지 않은 건을 사람에게 넘긴다. 사람 판독 화면의 세 기준을 구체화했다.

f73bab4의 기존 정렬과 ROI·자세 조건으로 ±2.7° 재시도를 했다. 같은 조명에서도 실패한 8장 중 41·47번 2장이 정렬됐고, 두 장 모두 기존 품질 판정은 RETAKE였다. L1을 L0에 맞춘 표본 4장은 모두 실패했다. 결과는 `outputs/phone-rotation-probe-20261120/`에 보관했다. 같은 세션에서 시도한 개발 결과다.

### 2026-11-25 · 두 사람의 50장 판독 수신 및 품질 판정 대조

두 사람의 판독표가 원본 50장과 모두 일치한다. 평가용 46장 중 판독 일치 24장, 불일치 22장이다. 잘 보임과 판독 어려움으로 직접 갈린 9장은 모두 첫 L0 사진이고 고정 v0.3에서 품질 PASS다. 두 사람이 잘 보인다고 본 18장의 PASS는 고정 3장, 같은 조명 정렬 개발 17장이다. 두 사람 모두 판독이 어렵다고 본 6장은 두 방법에서 모두 품질 PASS가 아니었다. 사진별 품질 판정과 결함 검사 결과는 분모가 다르다.

판독자·판독 시각·자동 검사 결과 사전 열람 여부는 두 표 모두 미기록이다. 원 판독을 보존하고, 직접 불일치 9장부터 원본을 확인할 수 있도록 표를 만들었다. 촬영 조건 확인 및 실측 시간, 팀 2번의 나머지 포스터 정보, 보고서 및 A0 제출본 갱신은 남아 있다. 결과는 `outputs/phone-human-ratings-20261125/`에 있다.

### 2026-11-25 · 판독 재확인과 제출 작업본

사용자가 두 판독자 모두 검사 결과를 사전에 보지 않았다고 확인했다. 제공 화면은 원본 확대를 안내했으나 실제 배율은 미기록이다. 원 판독 일치 24/46, 불일치 22/46을 보존했다. 촬영 순서 5·13번은 잘 보임, 11·15·19·23번은 판독 어려움으로 사후 반영했다. 7·17번은 개인 편차, 9번은 별도 판단 없음으로 보류했다. 잠정 분포는 잘 보임 20장, 어려움 10장, 보류 16장이다. 잠정 어려움 10장 중 양쪽 품질 변형 PASS가 각각 4장이다.

추가 실험을 중단하고 현재 수신 결과로 제출 작업본을 만들었다. 팀 2번 A0 1쪽 PPTX/PDF와 4쪽 DOCX/PDF(제목은 기존 포스터 문구)다. 저자, 지도교수, 소속, 확정 제목은 입력 대기다. 재확인 자료는 `outputs/phone-human-ratings-20261125/판독_재확인_46장.csv`에 있다.

### 2026-11-25 · 대체 촬영과 복원 근거 구분

첫 사진의 계획 조건이 저조도 또는 흐림인 10쌍을 원 판독 자료와 연결했다. 두 사람 모두 잘 보임은 첫 사진 0장, 대체 사진 5장이며, 둘 다 어려움에서 둘 다 잘 보임으로 바뀐 쌍은 2개다. 고정 C2는 10건 모두 보류, 같은 조명 정렬 개발 변형은 OK 3·NG 6·보류 1이다. 새로 찍은 대체 사진의 근거이며 영상 복원과 구분한다. 첫 사진에 적용한 C1 Bicubic 및 SwinIR의 최종 판정은 23건 모두 직접 검사 C0와 같았다. 별도의 선명 L1 사진 ×4 왕복 위치 일치 결과는 원본 4/9, Bicubic·SwinIR 각 9/9이며 복원본의 사람 판독 결과는 없다. 새 실험 없이 제출 작업본과 집계표를 갱신했다.

### 2026-11-25 · 상세 결과보고서와 추가 실험 판단

팀 2 상세 결과보고서 DOCX와 PDF를 작성했다. 문제 설정, 초기 파일럿과 실패 사례, 복원 모델 선택, 정상 특징 bank 28조건, VisA PCB 운영점, 실물 촬영 24장과 평가 50장, 두 사람의 판독, 대체 촬영과 동일 사진 복원 결과를 실험 선택 순서대로 서술했다. 비율에는 분모를 붙이고 변화량은 퍼센트포인트 또는 건수로 제시했다. 부록에 정상 bank 28조건과 첫 사진·대체 사진 10쌍을 수록했다.

PDF 총 16쪽을 렌더링해 본문·표·그림 3개와 페이지 나눔을 확인했다. 제출 작업본 폴더의 팀2_상세_결과보고서.docx 및 팀2_상세_결과보고서.pdf다. 저자·지도교수·소속과 최종 제목은 제출 전에 확인한다.

현재 보고 범위에는 추가 실험을 필수로 두지 않는다. 동일 원본을 실제로 복원하면 사람과 자동 검사에 모두 도움이 된다는 주장을 추가할 경우, 동일 사진의 열화 입력과 복원본을 짝지어 블라인드 사람 판독과 자동 검사 결과를 비교한다. 같은 조명 정렬 후보의 독립 성능이나 양산 성능을 주장할 경우는 별도 세션이 필요하다. 이번 작성에서는 새 실험을 수행하지 않았다.

### 2026-11-25 · GitHub main 통합과 그림 보강본

공개 main을 ba92bc0에서 3d10197로 갱신하고 원래 로컬 저장소의 main도 맞췄다. 실험·분석 코드를 포함한 기존 원격 브랜치의 커밋을 main 이력에 연결했고, 종료한 전달·초안 브랜치 6개를 커밋 대조와 백업 검증 뒤 정리했다. 원격 브랜치는 27개에서 21개로 줄었다.

results에 실험 흐름, bank 28조건, VisA 운영점, 품질·정렬, 사람 판독, 대체 촬영 10쌍, 사진과 결과 그림 171개를 연결했다. 개발 24장과 평가 50장의 공개용 사본은 식별 스티커와 EXIF를 제거했다. MVTec AD와 VisA 패널은 데이터별 라이선스를 기록했다. 원본 사진과 비공개 결정 기록, 모델 파일, 전체 데이터셋 보관 위치는 기존 로컬 자료를 사용한다.

상세보고서는 25쪽, 그림 24개다. 기존 세 그림에 21개를 보강했고 비교 사진, 지도와 수치표의 링크를 확인했다. 팀 2 A0 포스터 작업본 PDF/PPTX도 공개 자료에 포함했다.
