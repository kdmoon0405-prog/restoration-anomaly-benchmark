# PCB full-board geometry protocol v0.1

상태: **DRAFT / BLOCKED_GEOMETRY**. 작성 완료 2026-10-16 (KST).
이 문서는 GPU pilot 실행 허가나 평가 가능한 전처리의 확정이 아니다.

## 평가 범위와 단일 초안

목표는 central ROI가 아닌 pcb2 full-board FOV 평가다. 첫 구조 검증 대상은
`pcb_full_frame_224_bilinear_nearest_v0_1`이다. 원본 전체 RGB를 Pillow BILINEAR로
224×224에 직접 resize하고, `GT > 0` 이진 마스크를 NEAREST로 resize한다.
Crop/padding은 없다. 기존 canonical 함수와 과거 실험은 변경하지 않았다.
향후 연결한다면 fit/calibration/test와 Clean/Bicubic/SwinIR 모두 같은 geometry를 쓴다.
지금은 별도 geometry API/manifest만 있으며 runner에는 연결하지 않았다.

초안 선택 이유는 전체 FOV를 포함하면서 기존 224 입력 크기와 bilinear 방식을 유지하는
최소 변경을 점검하기 위해서다. 최선의 전처리라는 뜻은 아니다.
원본 1404×1070이 224×224가 되므로 종횡비가 변한다. 전체 좌표 영역을 포함해도
작은 결함, 형상, 경계 정보가 모두 보존되지는 않는다.

좌표는 x=열, y=행이다. 원본 W×H에 대해 edge 변환은
`(x*224/W, y*224/H)`, 정수 index로 표현한 pixel center 변환은
`((x+0.5)*224/W-0.5, (y+0.5)*224/H-0.5)`이다.
원본/출력 크기, 정/역 affine, 보간법은 manifest에 기록한다.
향후 x4 조건은 **canonical 224 → LR 56 → output 224**다.
이번 작업에서는 실제 RGB에 LR degradation/모델 추론을 실행하지 않았다.

## 고정된 구조 검증과 결과

실행 규칙과 코드 SHA는 `analysis/pcb_geometry/pcb2-full-frame224-20261015/PROTOCOL.json`에
2026-10-15 23:56:43 KST, 실제 점검 전에 저장됐다. 이 문서는 그 실행 후 판정을 기록한다.

- 전체 1,101장의 크기/geometry 점검, 실제 anomaly GT 100장 점검.
- 입력/정렬 오류 0, 변환 후 완전히 빈 anomaly GT 0.
- 원본 GT의 8-connected 연결요소 324개 중 305개가 target에 나타나고 19개가 사라짐.
- 연결요소 소실 영상 9/100장. 사라진 요소의 원본 면적은 1~28 source pixels.

연결요소는 **원본 해상도에서** `GT > 0`를 8-connectivity로 label한 ID다.
이 int32 ID map을 동일한 Pillow NEAREST로 resize해 각 원본 ID의 target sample 수를 센다.
`sampled IDs > 0`와 변환한 binary GT가 정확히 같은지 확인한다.
이는 물리적 결함 개수가 아니며, target 연결요소 수와 원본 ID 수를 혼동하지 않는다.
원본 pixel 수와 target sample 수는 다른 단위다. 그 비율을 보존율로 쓰지 않는다.
ID가 남아 있어도 형상/미세구조가 보존됐다는 판정은 아니다.

공식 normal에는 mask 파일이 없다. Label에 따른 implicit background로 기록하며,
빈 normal mask의 변환은 synthetic test로 점검했다. 실제 normal GT 파일을 읽었다고 하지 않는다.
Synthetic test는 비정방형, 모서리/경계, 작은 요소, 여러 요소, RGB/GT 좌표 정렬,
결정성, 빈 mask와 잘못된 입력을 포함한다.

기존 crop 점검의 9장 pixel loss/3장 component loss는 **335×256 resize 이후 crop 전후**의
비교였다. 이번 9장/19개는 **원본 ID의 resize aliasing**이다. 두 검사는 기준 격자와
소실 원인이 다르며, 숫자만으로 전처리가 개선됐다고 비교하지 않는다.

판정은 `BLOCKED_GEOMETRY`다. 빈 mask가 없어도 원본 요소 소실 때문에 통과시키지 않는다.
Anomaly/작은 GT 제외, dilation, adaptive crop, GT 기반 입력 보정은 하지 않았다.
고해상도 full-FOV 또는 coverage가 고정된 tiling은 수정안으로만 남긴다.
자동 해상도/전처리 탐색이나 모델 실행은 하지 않는다. 수정안은 별도 버전에서 구조 규칙부터 고정해야 한다.

## 분할과 재현성

공식 VisA `split_csv/1cls.csv`, 기존 seed 11 / fit ratio 0.8 분할을 재사용했다.
721 fit-normal / 180 calibration-normal / test 100 normal + 100 anomaly이며,
이전 split audit의 경로 집합과 정확히 같다. 분할 간 path overlap 0,
byte-identical image SHA 그룹 0이다. 후자는 장면/유사 이미지 중복이 없다는 증명은 아니다.

공식 CSV SHA256:
`a48557e6033318cb90556f706196bc9d247a776a23ea51aecee5a80dd0332995`.
`INPUTS.csv`에는 모든 분할 경로/label, 원본 RGB/GT SHA, 크기, geometry key가 있고,
`MANIFEST.json`은 CSV/실행 protocol SHA와 좌표 metadata를 연결한다.
경로는 VisA root 상대 경로다. 팀원의 과거 pcb2 사용은 **미확인**이며 연락하지 않았다.

PCB 전용 bank와 정상 calibration은 이 protocol에서 **아직 생성하지 않았다**.
Hazelnut bank/threshold를 PCB에 재사용하지 않는다. Calibration normal과 bank fit normal은 분리한다.

## 향후 baseline 계획과 사용 제한

구조 문제가 해소된 새 protocol을 동결한 뒤 Clean / Bicubic-x4 / SwinIR-S-x4를 비교한다.
Primary는 dataset-level pooled AU-PRO@0.3 하나다. Secondary는 Pixel AUROC,
Image AUROC, PSNR, SSIM이다. 이번 구조 점검은 anomaly 성능 지표를 계산하지 않았다.

Test GT는 구조 검증과 evaluation에만 사용한다. 이번에 GT 구조를 이미 점검했으므로
GT까지 untouched인 외부 검증이라고 부르지 않는다. Test 성능으로 checkpoint,
전처리, threshold, fusion weight를 재선택하지 않는다. Threshold는 별도의 정상 calibration에서 고정한다.
이 full-frame family는 과거 center-crop family와 다르다. 과거 지표/bank/calibration과 섞지 않는다.
기존 negative gating 및 full110 B/B-uncertain 판정은 유지한다.

실제 pilot 전 prerequisites:

1. 단일 수정 geometry의 별도 protocol 버전과 구조 검증 통과. 미세 정보 보존 한계도 명시.
2. 모든 분할/method에 같은 geometry를 적용하는 VisA runner 연결과 CPU integration test.
3. PCB 전용 정상 bank/calibration 계획, checkpoint SHA/모델 설정/평가 규칙 동결,
   팀원 사용 이력 확인, NVIDIA 실제 머신의 별도 자원/device smoke.

세부 CSV, 실행 보고서, 직접 확인한 local-only PNG는
`analysis/pcb_geometry/pcb2-full-frame224-20261015/`와 `VERIFICATION.md`를 참조한다.
