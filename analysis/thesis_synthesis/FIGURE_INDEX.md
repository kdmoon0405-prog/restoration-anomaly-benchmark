# Figure and table index

기존 그림 네 개는 그대로 사용한다. 과거 ROI-score 그림과 qualitative/NN 사례 그림은 core 결론의 증거 우선순위에 올리지 않는다. 실험 family를 caption에 명시한다.

| Placement | Figure/table | Source data | Script/source artifact | Scientific message and allowed caption | Claim limitation |
| --- | --- | --- | --- | --- | --- |
| Core Figure 1 | [controlled_recovery_aupro.png](figures/controlled_recovery_aupro.png) | [Hazelnut](sources/hazelnut_summary.csv), [Screw](sources/screw_summary.csv); MASTER historical rows | `scripts/synthesize_thesis_results.py` | “Historical Pillow x4 조건에서 Clean 대비 localization 저하와 SwinIR의 부분 회복.” | 두 category의 fixed detector 결과; MATLAB endpoint 수치와 섞지 않음 |
| Core Figure 2A | [direct endpoint waterfall](../restoration_objective_full/derived/per_image_aupro_waterfall.png) | Full110 direct RRDB paired deltas; summary와 bootstrap companion | `scripts/analyze_restoration_endpoint_full.py`; [execution record](../restoration_objective_full/EXECUTION_RECORD.md) | “70 anomaly에서 ESRGAN−PSNR per-image AU-PRO 변화의 크기와 방향.” | 순위는 표시용; favorable subset 선택 아님; pooled delta와 다른 estimand |
| Core Figure 2B | [magnitude sensitivity](../restoration_objective_full/derived/regression_sensitivity.png) | [Frozen tau CSV](../restoration_objective_full/derived/magnitude_sensitivity.csv) | 동일 frozen analyzer | “Learned restorers의 MATLAB-Bicubic 대비 음수 delta count는 magnitude band에 따라 달라진다.” | 0.01 등의 tau는 산업 failure threshold가 아님; historical tau는 별도 post-hoc table |
| Core Table B (Figure 3 역할) | [Synthesis endpoint table](THESIS_SYNTHESIS.md#8-table-b-full110-endpoint-comparison) 및 [FULL_RESULT](../restoration_objective_full/FULL_RESULT.md) | Full110 aggregate JSON, bootstrap, D50 | 기존 runner/analyzer의 저장 output을 집계 | “명확한 fidelity–perceptual 품질 차이와 case B/B-uncertain localization 비교.” | Method-level ordering이 per-image 신뢰성을 뜻하지 않음; objective-only causality 없음 |
| Supporting | [PSNR scatter](../restoration_objective_full/derived/quality_localization_psnr.png) | [Paired quality CSV](../restoration_objective_full/derived/quality_localization.csv), summary rho | 기존 frozen analyzer | “각 learned model의 per-image PSNR gain과 AU-PRO gain.” | 평균 ordering·인과·범용 proxy 판정과 구분 |
| Supporting | [LPIPS scatter](../restoration_objective_full/derived/quality_localization_lpips.png) | 같은 paired CSV, LPIPS improvement는 Bicubic−restored | 기존 frozen analyzer | “각 model의 LPIPS improvement와 AU-PRO gain.” | 높은 x는 개선; LPIPS 일반적 무효 주장 금지 |
| Supporting table | [baseline terciles](../restoration_objective_full/derived/baseline_tercile_regression.csv) | Frozen 23/23/24 rows와 summary rho | 기존 frozen analyzer | “높은 baseline에서는 strict-sign 감소가 잦지만 큰 감소 비율은 낮다.” | Descriptive ceiling association; regression-to-the-mean causality 아님 |
| Appendix | [Full taxonomy contingency](../restoration_objective_full/derived/taxonomy_contingency.csv), historical taxonomy | GT-assisted post-inference score/map deltas | 기존 analyzers | “Localization 부호와 ROI-background gap 부호의 2×2 context.” | Mechanism classifier 아님 |
| Appendix | [Hazelnut nine cases](../hazelnut/qualitative_cases/README.md), [Screw six cases](../screw/qualitative_cases/README.md), selected NN summaries | 고정한 사후 선택 사례, stored maps/RGB/NN CSV | `scripts/analyze_patchcore_nn_selected.py`, 기존 qualitative records | “선택된 사례의 map/feature-distance consistency와 한계.” | n=3/subtype; population/independent mechanism 증거 아님 |
| Supporting subsection/appendix | [Fusion alpha plot](../hazelnut/fusion_weight_search/alpha_vs_pooled_au_pro.png), [risk plot](../hazelnut/fusion_weight_search/alpha_vs_regression_risk.png) | 기존 five-point Branch B CSV | `scripts/analyze_fusion_weights.py` | “고정 5점 grid에서 restored-only가 primary metric best.” | Branch A/B bank·calibration이 다름; 전체 fusion family 기각 아님 |

새 그림은 Figure 1 하나뿐이다. 기존 역사적 그림은 ROI 분포/사례 중심이라 두 category의 Clean→Bicubic→SwinIR aggregate를 함께 보여주지 못했다. Figure 1은 CPU에서 저장 표 6행으로만 생성했고 기본 plotting 색상과 0부터 시작하는 AU-PRO 축을 사용한다. 다른 그림은 재생성하지 않았다.

현재 source artifacts만으로 재현 가능한 core 그림/표를 우선한다. 원본 full110 NPZ/RGB가 없는 이 checkout에서 qualitative panel이나 frozen analysis를 새로 실행하지 않는다.

기존 waterfall의 defect-type legend swatch가 모두 같은 파란색으로 표시된다. 막대의 delta 크기·순위는 읽을 수 있지만 legend 색으로 defect type을 식별하지 않는다. 원본 derived PNG는 변경하지 않았다. 논문/발표에서 defect별 색 해석이 필요하면 별도 승인된 표시 정정이 필요하다.
