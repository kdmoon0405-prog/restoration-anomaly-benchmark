# Qualitative observations

The six cases were fixed before rendering. Bicubic and SwinIR maps use the same color limits within each image.

- In the three suppression examples (`thread_side/019`, `thread_side/010`, `scratch_head/005`), the SwinIR map has a visibly lower response than the Bicubic map over much of the screw. Their small GT regions do not become more distinct, consistent with the negative AU-PRO and ROI-background-gap deltas.
- The three success controls also show lower broad object response after SwinIR, but their AU-PRO improves by about 0.29 to 0.32. For `scratch_neck/000` and `scratch_neck/006`, the ROI-background gap increases despite the lower overall display intensity.
- The anomaly maps are spatially coarse relative to the small GT defects and often cover a long part of the screw. The figures therefore cannot establish whether the regressions originate in feature evidence or later spatial scoring.

The overlap between visible attenuation in failures and controls means that absolute map attenuation alone does not separate the two groups. The frozen selected-case NN-distance check is needed before making any feature-space interpretation.
