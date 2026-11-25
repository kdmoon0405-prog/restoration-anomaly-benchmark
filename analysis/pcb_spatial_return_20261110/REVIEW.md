# 선택 PCB 9사례 공간 분석 반환 검토

주형 반환 commit 52b4c23e61f5dd06e438604f533a9c03ea500328의 두 receipt와 공개 파일 6개가 일치했다. 공간 분석은 suppression 3, geometry_candidate 3, success_control 3의 사전 선택 보드와 3 variant를 사용했다. CSV에는 27개 board/variant 행과 4-connectivity GT 연결요소 36개가 있다. 연결요소 수는 물리적 결함 개수와 구분한다.

선택 CSV, map 27개의 경로·해시, 원본 RGB/GT 파일 해시, 정상 calibration, 분석 코드 두 파일 SHA가 고정 기록과 일치했다. Component 면적 합, 면적 가중 ROI mean, ROI–배경 gap, centroid 거리와 variant 차이를 CSV에서 다시 계산했다. 수신 결과의 scalar 정합성 검증을 통과했다.

## 단위를 함께 비교한 결과

각 수치는 선택된 보드 9개에서의 최솟값–최댓값이다. 통계적 신뢰구간이나 population 추정은 계산하지 않았다.

| Variant | 보정 map의 seam gradient | Raw map의 seam gradient | Seam/non-seam 비율 |
| --- | --- | --- | --- |
| Clean | 0.4424–0.6039 | 0.1679–0.2292 | 16.63–18.92 |
| Bicubic | 0.5737–0.7385 | 0.3169–0.4080 | 21.24–24.24 |
| SwinIR | 0.6311–0.7915 | 0.3093–0.3878 | 20.06–22.33 |

보정 map에서 SwinIR의 seam gradient는 Bicubic보다 9/9개가 크다. Raw 단위와 seam/non-seam 비율에서는 9/9개가 작다. Positive affine 보정에서 gradient는 pixel scale의 역수로 변한다. Bicubic의 pixel scale은 0.5524178743, SwinIR은 0.4900140762다. Variant별 단위 차이를 포함한 보정 gradient 크기만으로 SwinIR의 seam 반응이 더 커졌다고 해석하지 않는다.

Seam/non-seam 비율은 이 보정에 불변이다. 같은 variant 내 고정 tile 경계에서 평균 gradient가 크게 관측됐다는 설명은 가능하다. 이 선택 사례만으로 overlap-mean 조립의 인과 효과나 전체 cohort의 성능 손실을 정량화하지 않는다.

기존 geometry_candidate 3개 중 036과 045는 raw ROI–배경 gap이 각각 -0.237735, -0.227339 감소했다. 보정 gap 차이는 +0.090151, +0.018711이다. 기존 taxonomy는 보정 gap을 사용하므로 분류는 그대로 유지한다. 이 두 후보를 공간 왜곡만으로 설명하기에는 raw 반응 감소가 함께 관측된다.

006 후보는 centroid 이동이 0.853 native pixel이고 per-image AU-PRO 차이는 -0.018325다. Success control 068의 이동은 17.192pixel이다. 여기서 centroid는 전체 map의 background 초과 양수 질량 중심이다. GT와의 결함 위치 오차를 측정한 값과 구분한다. 실제 defect 주변 이동·blur에 대한 해석에는 사례 그림이 추가로 필요하다.

## 출처와 확인 범위

Manifest의 runtime_source_commit 54cf3c7과 dirty=true는 원본 prediction provenance에서 복사된 값이다. 해당 필드 이름을 분석 checkout의 실행 commit으로 읽으면 출처를 잘못 연결하게 된다. 별도 RUN_RECORD는 분석 source를 1e6c6bc로 기록했고, manifest의 두 source SHA는 그 commit의 파일 bytes와 일치했다. 실제 원격 실행 당시 Git 상태의 독립 관찰 여부는 false로 기록했다. Review JSON에는 두 출처의 역할을 명시했다. 원본 manifest는 보존했다.

로컬에서는 CSV·metadata를 검증했다. Native map의 파일 무결성은 이전 27개 array receipt를 연결했으며, 이번에 native map이나 GT를 다시 decode하지 않았다. 당시 로컬 가용 RAM은 839507968bytes로 기존 2570139136bytes 요구에 미달했다. 가드는 유지했다.

주형의 RGB/GT 사례 PNG 9개는 해시만 전달됐다. 주형은 3개를 직접 확인했다고 기록했다. 이 PC에서 해당 PNG를 열어 본 수는 0개다. 새 selected_descriptors.png는 반환 scalar로 만든 그림이며 직접 열어 점과 범례·단위·축·라벨을 확인했다.

진단 addendum은 FPR plateau, affine normalization, peak-in-GT와 matched-bank 원인 해석의 한계를 반영했다. 위 단위 비교는 addendum의 보정 seam gradient 해석을 보완한다. Geometry 후보의 명칭은 hypothesis screening을 위한 기존 표기로 유지한다.

Master는 기존 133조건/9 protocol groups를 유지한다. 이번 선택 사례는 신규 detector 조건이나 독립 cohort로 집계하지 않는다. 다음 통합 대상은 지혁의 bank-domain 24+4조건과 주형의 noise 32조건이며 해당 결과는 아직 이 반환에 포함되지 않았다.

재현 CLI는 scripts/review_pcb_spatial_return.py다. --spatial-run과 --addendum-run에 두 receipt 폴더, --metadata-root에 기존 handoff/metadata, --analysis-source-commit에 1e6c6bcd0e59ed91c6c3e6eb0e078f8d75b8bf39, --output에 새 경로를 지정한다. 공개 표는 per_case_review.csv와 gradient_units.csv, 검증 범위는 review.json에 있다.
