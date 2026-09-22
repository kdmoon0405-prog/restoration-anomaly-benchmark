# Screw frozen selected cases

These figures use saved PatchCore maps and GT masks plus the source clean image and deterministic Bicubic x4 input. No PatchCore or SwinIR inference was run. The two anomaly maps share one color scale within each sample.

Cases were fixed by per-image AU-PRO ranking before rendering. They are qualitative/NN follow-up candidates, not population estimates.

- suppression_examples: `screw/test/thread_side/019.png` → `01_screw__test__thread_side__019.png`
- suppression_examples: `screw/test/thread_side/010.png` → `02_screw__test__thread_side__010.png`
- suppression_examples: `screw/test/scratch_head/005.png` → `03_screw__test__scratch_head__005.png`
- success_controls: `screw/test/manipulated_front/023.png` → `04_screw__test__manipulated_front__023.png`
- success_controls: `screw/test/scratch_neck/000.png` → `05_screw__test__scratch_neck__000.png`
- success_controls: `screw/test/scratch_neck/006.png` → `06_screw__test__scratch_neck__006.png`
