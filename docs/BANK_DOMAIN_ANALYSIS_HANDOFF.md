# Bank-domain 분석과 GPU 담당자 인터페이스

이 코드는 저장된 결과만 분석한다. PatchCore/SwinIR 실행, 이미지·GT·prediction 배열 로딩은 하지 않는다. 실행 경로는 손지혁, PCB 실행 경로는 심주형, 이 분석·통합 reporting은 CPU 담당 소유다.

## 생산자가 저장할 다섯 파일

실제 실행 directory에 다음 파일을 저장한다. 새 GPU runner가 아직 없다면 이 계약에 맞춰 작성하면 된다. 분석 script가 GPU 실행을 대신 구현한 것은 아니다.

| 파일 | 내용 |
|---|---|
| bank_domain_manifest.json | schema_version=1, kind=bank_domain_study_results, status, evidence_kind와 네 파일의 byte SHA256 |
| config.json | study_family, category, seed, protocol |
| provenance.json | 실행 code·입력·분할·bank 출처와 GT/split 조건 |
| summary.csv | 네 bank/query 셀의 저장 dataset metric |
| per_image.csv | 같은 test sample의 네 셀 결과와 quality |

Manifest status는 COMPLETE, PARTIAL, FAILED, PREFLIGHT_PASS다. 완료 전 세 상태는 숫자 집계에서 제외된다. COMPLETE인데 네 셀·파일·sample이 빠졌으면 오류로 처리한다. evidence_kind는 실제 실행의 model_predictions, 테스트의 synthetic_fixture를 구분한다. 합성 입력은 --allow-synthetic을 명시해야 하고 실제 결과와 같은 분석에 섞이지 않는다.

Manifest의 files는 summary.csv/per_image.csv/config.json/provenance.json 네 이름과 SHA256의 object다. 외부 JSON에 적힌 원격 절대 경로를 자동으로 읽지 않는다.

## Config와 출처

config.json의 protocol은 아래 필드를 포함한다.

- dataset, geometry_id, degradation_id, detector_id, restorer_id.
- bank_spec: 실제 feature dimension/layers/sampler/선택 규칙 등 공통 bank 조건 object.
- checkpoints_sha256: 사용한 backbone/restoration checkpoint의 실제 digest object.
- calibration_source: normal_calibration_only.
- metric_definition: primary=pooled_aupro, max_fpr=0.3, num_thresholds=200, connectivity=4.

Protocol 전체와 execution code digest를 묶어 protocol_sha256을 만든다. Geometry/kernel/checkpoint/실행 source가 다른 결과는 자동으로 다른 protocol 그룹에 남는다. Source commit이 달라도 관련 code bytes가 같으면 commit 문자열만으로 거부하지 않는다.

provenance.json은 다음 필드를 기록한다.

- source_commit(40자리), source_worktree_dirty(bool), code_sha256(POSIX 상대 파일명→digest).
- normal_fit_calibration_disjoint=true, test_gt_used_for_selection=false.
- input_manifest_sha256, split_manifest_sha256, test_manifest_sha256, query_manifest_sha256.
- bank_manifest_sha256: clean/swinir_restored 두 bank receipt의 digest.
- bank_vector_counts: 두 bank의 양의 실제 벡터 수. 같은 크기여야 한다.

Digest와 선언은 실행 출처를 연결하는 기록이다. Raw 배열을 받지 않은 CPU가 원격 실행을 독립 관찰했다는 뜻은 아니다. --source-root를 명시할 때만 해당 source bytes도 직접 대조한다. 다른 revision을 가리키는 JSON 경로를 자동으로 열지 않는다.

## CSV

summary.csv 필수 열:

    bank_domain,query_domain,n_test,n_anomaly,pooled_aupro,pixel_auroc,image_auroc,mean_psnr,mean_ssim

bank_domain은 clean/swinir_restored, query_domain은 bicubic_x4/swinir_x4다. 조합은 정확히 네 셀이다. Dataset pooled AU-PRO는 저장 값을 사용하고 per-image 평균으로 바꾸지 않는다.

per_image.csv 필수 열:

    sample,defect_type,label,bank_domain,query_domain,per_image_aupro,roi_bg_gap,psnr,ssim

Sample은 POSIX 상대 식별자이고 행 순서는 자유다. 동일 test의 sample/label/defect는 네 셀에서 같아야 한다. 정상 영상의 per-image AU-PRO는 빈 값/NA다. Anomaly는 기존 evaluator로 계산한 per-image AU-PRO와 ROI-background gap을 저장한다. GT는 그 평가 과정에서만 사용한다.

동일 query의 PSNR/SSIM은 bank 사이에서 같아야 한다. 분석은 이 수치를 대조하고 quality를 한 번만 집계한다. Quality 일치가 원본 RGB bytes의 직접 검증을 대신하지는 않는다. Inf PSNR은 보존하며 잘 정의되지 않는 Inf−Inf query 차이는 빈 값으로 둔다. 같은 query의 bank 변경은 quality 변화0으로 기록한다.

## 실행

아래 run directory는 앞으로 GPU producer가 반환할 경로 예다. 실제 저장 이름이 다르면 해당 경로를 명시한다.

    .venv\Scripts\python.exe scripts/analyze_bank_domain_study.py --run outputs/bank-domain-study/hazelnut-seed11 --output analysis/bank-domain/hazelnut-seed11

여러 seed는 --run을 반복해 전달한다. 입력 directory 내부를 output으로 쓰거나 기존 output을 덮어쓰지 않는다. 실제 실행 source를 이 PC에서 보유할 때만 --source-root로 그 checkout을 명시한다.

## 생성 표와 통계

- bank_domain_summary.csv: family/protocol/category/seed/네 셀의 저장 metric.
- bank_effects.csv: 같은 query에서 restored bank−clean bank.
- query_effects.csv: 같은 bank에서 SwinIR query−Bicubic query.
- per_image_deltas.csv: anomaly별 paired delta/gap/taxonomy.
- quality_by_query.csv: bank 중복을 제거한 quality.
- seed_summary.csv: seed별 primary delta의 mean/min/max/SD. Cross-seed CI는 계산하지 않는다.
- analysis_manifest.json, SUMMARY.md: 입력 digest, 제외/중복, 검증 범위와 요약.

Taxonomy는 delta per-image AU-PRO<0이면 localization regression이며, gap delta<0은 suppression, 나머지는 geometry_candidate다. 각 표의 reference/candidate 축을 구분한다. 새로운 magnitude cutoff나 weight 선택을 하지 않는다.

Bootstrap은 기존 Hazelnut helper를 작은 공통 모듈로 옮겨 그대로 공유한다. 기본 config는 repeats2000/seed11이다. CI는 seed별 anomaly image의 paired 평균 delta에만 적용한다. Pooled AU-PRO CI와 다른 통계다. 같은 이미지의 세 seed를 독립210개 표본으로 늘리지 않는다.

동일 condition의 같은 payload는 한 번만 집계하고, 값이 충돌하는 중복 run은 명시적 선택을 요구한다. 모든 동일 source/hash를 다시 연구 검토하는 대신 receipt cache를 사용한다. 실제 bank-domain artifact가 아직 없으므로 새 연구 숫자와 그림은 생성하지 않았다.
