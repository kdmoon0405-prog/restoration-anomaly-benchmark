# Selected-case PatchCore NN distances

Exploratory 6 cases fixed from the saved screw analysis; no causal or population-level claim.
Source predictions: `outputs/legacy-patchcore/screw-full320-test160`; unchanged 320-image bank: `checkpoints/legacy-patchcore/screw-seed11-train320`.
Distances are official FAISS IndexFlatL2 squared L2 values (not smoothed anomaly-map scores).
GT occupancy is the positive-pixel fraction of each nonoverlapping cell after the original 256-resize/224-center-crop; cells align to the actual PatchCore feature grid. The 3x3 feature patches and backbone receptive fields exceed these cells, so this is an approximate ROI assignment.
GT was used only for post-hoc evaluation. Each recomputed map matched its saved prediction before distances were recorded.

| Subtype | n | Mean ΔAU-PRO | Mean Δmap gap | Mean ΔD_defect | Mean ΔD_background | Mean Δfeature gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| suppression | 3 | -0.147568 | -1.180901 | -1.824677 | -0.565741 | -1.258936 |
| success_control | 3 | +0.307945 | +0.208704 | -0.292801 | -0.620176 | +0.327375 |

Cases with both ΔD_defect < 0 and Δfeature gap < 0: suppression 3/3, success_control 0/3.
Descriptive selected cases only; feature-distance patterns are not necessarily subtype-specific, and the map-level names are not proven mechanisms.
