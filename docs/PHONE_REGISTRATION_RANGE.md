# 정렬이 받아들이는 자세 범위 — 합성 측정 (2026-11-15)

- **작성 모델:** Claude Fable 5.2.
- **합성 입력만 썼다.** 800 × 600 기판 무늬를 회전·배율·이동·원근 변환한 뒤, 스테이션과 같은 정렬(ORB + RANSAC homography), 같은 ROI 검증, 같은 자세 허용 범위(회전 5°, 배율 편차 0.10)로 판정했다. ROI는 화면의 0.2–0.8이다.
- 실제 사진의 한계는 재질, 반사, 초점에 따라 달라진다. 이 표는 방법의 동작 범위를 보여 주는 것이고 실물 성능이 아니다.
- 재현: `python scripts/characterize_phone_registration.py --output <새 폴더>`. 회귀 시험은 `tests/test_phone_station.py::test_registration_range_including_perspective`다.

## 결과

| 변환 | ACCEPT (그대로 검사) | REVIEW (정렬은 됐지만 recipe 자세 밖) | RETAKE (정렬 검증 실패) |
| --- | --- | --- | --- |
| 평면 회전 | 0°, 2°, 5° | 10°, 20°, 45°, 90°, 180° | — |
| 배율 | 0.9, 1.1 (경계) | 0.8, 1.25, 1.5 | 0.7, 2.0 (`alignment_below_threshold`) |
| 수평 이동 (화면 폭 대비) | 5 %, 10 %, 20 % | — | 30 %, 40 % (`roi_outside_frame`, coverage 0.83 / 0.67) |
| 원근: 카메라를 기울이고 화면 중심은 유지 | 5° | 10°, 15°, 20°, 30° | 40°, 50° (`alignment_below_threshold`) |
| 원근: 카메라만 기울임 (화면도 밀림) | 5° | — | 10°, 15°, 20° (`roi_outside_frame`), 30° (`alignment_below_threshold`) |

## 읽는 법

- **원근 입력에서 처리 가능한 범위:** 기울기 약 5°까지는 homography가 보정하고 그대로 검사한다. 10–30°는 정렬 자체는 성공하지만(inlier 비율 0.46–0.76, 재투영 오차 0.6–0.7 px), 기울기가 배율 편차로 나타나(0.11–0.61) 자세 허용 범위를 넘으므로 REVIEW로 보낸다. 40° 이상은 정렬이 실패해 RETAKE다.
- **원근 전용 임계값은 추가하지 않았다.** 기존 자세 허용 범위가 10° 이상의 기울기를 걸러냈다. 기울기의 크기는 `perspective_term`(homography의 투영 성분 × 화면 폭)으로 기록한다. 5°에서 0.08, 20°에서 0.34다.
- **배율 0.9와 1.1은 허용 범위 10 %의 경계다.** 측정 오차(±0.001)에 따라 ACCEPT와 REVIEW가 갈릴 수 있다.
- **관찰 부위가 화면 밖으로 나가면** 정렬이 성공해도 RETAKE다. 보정 완료로 처리하지 않는다.
- **배경에만 맞는 정렬:** 배경은 같고 ROI 안의 내용만 다른 합성 입력은 ROI 안 inlier 부족으로 거절된다(`test_roi_checks_separate_pose_lost_fov_background_only_and_failure`).

## 실제 사진에서 관측한 것

- 2026-11-15 세션의 기울임 3장은 회전 약 14°로 측정되어 REVIEW가 됐다. `perspective_term`은 재실행 결과의 `captures_quality.csv`에 있다.
- 예시 6장 중 5장(큰 회전, 배율 변화, 부분 시야, 사선 시점)은 정렬 임계값 미달로 RETAKE가 됐다.
