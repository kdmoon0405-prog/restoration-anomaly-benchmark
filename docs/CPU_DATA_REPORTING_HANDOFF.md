# CPU 입력 전달·receipt·master reporting

## 현재 실제 입력

2026-11-01 원본 MVTecAD 폴더에서 확인했다. 아래 수는 파일/공식 폴더 구분이며 새로운 모델 실험 결과가 아니다.

| category | normal train | normal test | anomaly test | seed11 fit/calibration |
|---|---:|---:|---:|---:|
| hazelnut | 391 | 40 | 70 | 313/78 |
| screw | 320 | 41 | 119 | 256/64 |
| capsule | 219 | 23 | 109 | 175/44 |

기존 fusion.split_train_calibration과 lexical train 순서로11/23/37의 split JSON을 생성한다. Test는 fit/calibration에 포함되지 않는다. 이미 받은 category만 선택해 검증할 수 있다.

## 공식 배포와 비공개 전달

MVTec AD의 공식 페이지에서 category 배포를 받는 경로를 우선한다. 이 PC가 보유한 파일을 전달할 때는 원본 license.txt/readme.txt, 출처·파일·분할 manifest를 함께 보존한다. 원본 RGB/GT bytes는 수정하지 않는다.

데이터는 CC BY-NC-SA 4.0이며 비상업적 이용, 출처 표시, 변경 표시와 동일 조건 적용 등 실제 license 조건을 따른다. 아래 공식 출처를 2026-11-01 확인했다.

- [MVTec AD 공식 배포·license](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)
- [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

Git에는 dataset을 올리지 않는다. 팀원에게 category ZIP을 비공개 파일 전달/이동식 저장장치 등으로 전달한다. 우리 프로젝트의 local-only 전달 정책이 license 자체의 추가 법적 제한이라는 뜻은 아니다. 원본 MVTec attribution과 논문 인용 안내를 보존한다.

준비 명령:

    .venv\Scripts\python.exe scripts/prepare_mvtec_transfer.py --data-root data/external/MVTecAD --output outputs/mvtec-team-inputs --pack

수신자는 archive를 같은 상위 폴더에 풀어 MVTecAD/category와 transfer_metadata를 얻는다. 중복 notice/metadata는 내용이 같은지 확인하며 합친다. 지혁은 Hazelnut/Screw부터 받고 Capsule은 이후 추가해도 된다.

    .venv\Scripts\python.exe scripts/prepare_mvtec_transfer.py --verify transfer_metadata/input_manifest.json --data-root MVTecAD --category hazelnut --category screw

이는 file hash 검증이다. RGB/mask decode·geometry·모델 검증으로 표시하지 않는다. 새 checkout에 데이터/weights/venv가 따라오지 않는다. 기존 Python 환경은 명시적으로 재사용한다.

## ZIP receipt cache

    .venv\Scripts\python.exe scripts/cache_artifact_receipt.py --archive outputs/received/review.zip --cache outputs/evidence-receipts

ZIP hash와 policy version으로 receipt를 재사용한다. 같은 bytes의 두 번째 확인은 내부 manifest를 다시 검사하지 않는다. 최초에는 안전한 경로·중복 entry·metadata 크기 예산과 제공 SHA256SUMS를 확인한다. Extract하지 않으며 JSON 내부의 원격 경로를 열지 않는다.

Status는 METADATA_INVENTORY_CHECKED다. Raw array 내용, 원격 실행, 실제 model source를 독립 검증했다고 승격하지 않는다. Array가 제공됐는지와 내용 검증 여부를 구분한다. Manifest가 없는 ZIP도 inventory 범위만 기록하며 hash 검증 항목 수는0이다. Source/model/metric acceptance는 별도 전문 검토 결과와 연결한다.

## Master table과 근거 index

기본 catalog는 이미 저장된 thesis_synthesis/master_results.csv만 읽는다. Historical Pillow family와 Matlab-compatible endpoint family를 그대로 나눠 현재 실제 수치를 복사한다.

    .venv\Scripts\python.exe scripts/build_research_master_table.py --output analysis/reporting-master

Bank-domain 결과가 오면 먼저 분석한 directory를 --bank-analysis로 추가한다. analysis_manifest가 bind한 summary table의 hash를 확인한다. 실제 새 결과가 없으면 새 category·method 행을 생성하지 않는다.

다른 PCB/native/realistic family는 config catalog의 sources에 실제 저장 table과 status, family/protocol/category 열 또는 identity metadata를 선언해 연결한다. column_map으로 기존 열 이름을 대응시킨다. source의 sha256을 제공하면 대조하고, 모든 실제 source digest는 출력에 기록한다. 실행 module을 수정할 필요 없다.

출력은 master_results.csv/md, claim_evidence_index.csv, report_manifest.json이다. Source condition이 같고 값도 같으면 한 번만 집계하며 충돌하는 동일 condition은 오류로 반환한다. Partial/failed source·row는 집계하지 않는다. Family와 seed를 가로질러 평균을 내지 않는다.

Claim index는 저장 metric과 source의 연결이며 인과·우월성 결론을 자동 생성하지 않는다. 원격 배열을 받지 않았다면 그 범위를 남긴다. 실제 bank-domain 결과가 오기 전에는 해당 그림을 만들지 않는다.

## 검증·공개 범위

Tiny CSV/JSON과 프로그램 생성 이미지로 aggregation, paired join, missing cell, duplicate condition, normal AU-PRO NA, quality dedup, source/출력 safety와 cache를 테스트한다. 분석에서 Torch/FAISS를 import하지 않는다.

공개 branch에는 code/tests/config/docs와 필요한 작은 기존 helper 이동만 포함한다. Dataset ZIP, 실제 입력 inventory, weights/bank/raw/RGB, .venv와 private research note는 제외한다. 분석 실행은 원본 결과를 변경하지 않는다.
