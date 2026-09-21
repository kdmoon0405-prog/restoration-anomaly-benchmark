# Selected-case PatchCore NN distances

Exploratory nine cases selected after Hazelnut results; no causal or population-level claim.
Source predictions: `outputs/legacy-patchcore/hazelnut-full391-test110-repro`; unchanged 391-image bank: `checkpoints/legacy-patchcore/hazelnut-seed11-train391`.
Distances are official FAISS IndexFlatL2 squared L2 values (not smoothed anomaly-map scores).
GT occupancy is the positive-pixel fraction of each nonoverlapping cell after the original 256-resize/224-center-crop; cells align to the actual PatchCore feature grid. The 3x3 feature patches and backbone receptive fields exceed these cells, so this is an approximate ROI assignment.
GT was used only for post-hoc evaluation. Each recomputed map matched its saved prediction before distances were recorded.

| Subtype | n | Mean ΔAU-PRO | Mean Δmap gap | Mean ΔD_defect | Mean ΔD_background | Mean Δfeature gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| suppression | 3 | -0.015330 | -0.246532 | -0.612300 | -0.363200 | -0.249100 |
| geometry_candidate | 3 | -0.043177 | +0.298934 | +0.004376 | -0.346242 | +0.350618 |
| success_control | 3 | +0.152578 | +0.405674 | +0.134499 | -0.323525 | +0.458024 |

Cases with both ΔD_defect < 0 and Δfeature gap < 0: suppression 2/3, geometry_candidate 0/3, success_control 1/3.
Descriptive only: n=3 per subtype; feature-distance patterns are not perfectly subtype-specific, and the map-level names are not proven mechanisms.
