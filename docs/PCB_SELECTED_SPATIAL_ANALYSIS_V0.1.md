# PCB 선택 map 공간 분석 초안

구현 전에 2026-11-09에 다음 descriptor를 명시한다. 이미 선택된 9개 board의 regression 정보를 확인한 뒤 작성한 exploratory 분석이다. 새 방법의 사전 등록 검정이나 population estimate로 사용하지 않는다. Selection은 기존 selected_native_map_cases.csv의 suppression 3개, geometry_candidate 3개, success control 3개를 유지한다. 분석 축은 SwinIR−Bicubic이며 clean도 비교 그림에 포함한다.

## 정의

- Raw map은 전달된 float32 native map이다. Normalized map은 기존 variant별 calibration map median/scale을 기존 normalize()로 적용한 값이다. Score threshold는 분석에서 재선택하지 않는다.
- ROI는 binary GT, background는 그 여집합이다. ROI mean−background mean과 그 delta를 raw/normalized 각각 기록한다. GT는 이 post-hoc descriptor와 그림에서만 사용한다.
- Map Pearson correlation은 전체 board pixel의 동일 좌표 두 map에 적용한다. 상수 map이면 NA다. Correlation만으로 공간 왜곡을 확정하지 않는다.
- Positive-excess centroid는 w(p)=max(A_normalized(p)−mean_background(A_normalized),0)의 가중 좌표 평균이다. 좌표는 원본 pixel center의 x/y index다. Sum(w)=0이면 NA다. SwinIR−Bicubic centroid displacement는 Euclidean pixel 거리다. Board 중심 이동의 기술통계이며 결함 위치 오차와 동일시하지 않는다.
- GT 연결요소는 기존 evaluator와 같은 4-connectivity로 label한다. 각 component의 면적, normalized map mean·max와 delta를 기록한다. 물리 결함 수로 해석하지 않는다. Native geometry 보존 audit의 8-connectivity와 구분한다.
- Tile seam은 기존 고정 tile_boxes()의 내부 시작/종료 좌표를 지나는 가로·세로선으로 정의한다. 선의 인접 두 pixel 간 |차이|를 모아 평균한다. 그 외 모든 인접 pair의 평균도 별도 기록한다. Border transition은 tile 합성 경계의 기술통계이며 불연속 원인 추정이나 성능 metric이 아니다. GT ROI와 seam mask가 겹치는 pixel 수/비율도 기록한다. Seam의 두 인접 pixel을 mask로 표시하며 임의 폭 탐색은 하지 않는다.

## 입력과 검증

--maps-root는 전달된 predictions/가 있는 directory, --metadata-root는 기존 return-package-20261109의 root다. --data-root는 로컬 VisA root다. 원격 JSON의 절대 경로는 따라가지 않는다. 선택 CSV의 상대 경로·SHA가 raw units_manifest.csv와 일치해야 한다. Raw status의 provenance/bank hash와 calibration provenance를 대조하고 frozen geometry/reference 및 GT 파일 hash를 기존 FrozenPCBInputs로 확인한다. np.load는 allow_pickle=False, mmap_mode=r로 수행하고 shape/dtype/finite를 검증한다.

Map은 한 board의 세 variant만 동시에 유지한다. 원본·calibration을 덮어쓰지 않고 고유 output에 저장한다. 같은 sample의 raw map은 하나의 공통 color scale, normalized map도 하나의 공통 color scale을 사용한다. RGB/GT overlay PNG는 local-only로 저장하고 이미지 보기로 확인한다. 배열 미수신이면 실제 사례 수치를 생성하지 않고 synthetic 테스트까지만 수행한다.

실제 27개 map이 아직 없으므로 이번 문서는 descriptor와 입력 계약을 고정한 상태다. 기존 pooled 연구 지표와 taxonomy 정의는 유지한다.

2026-11-10 수신 기록.27개 원본 map의 무결성을 확인했다. 위 정의는 수신 전 작성한 상태를 유지한다. Actual spatial analysis는 고정 메모리 기준 미달로 BLOCKED_MEMORY이며32GB 호스트 전달을 준비했다. 원본 결과·taxonomy를 보존하고 GT 용도는 post-hoc 공간 분석으로 고정했다.
