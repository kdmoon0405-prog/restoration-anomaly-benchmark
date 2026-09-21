# Preselected Hazelnut qualitative cases

Branch A saved anomaly maps/scores and GT masks; only the SwinIR RGB panel was reconstructed from the fixed x4 checkpoint for these nine images. No PatchCore fit/inference was rerun.

The nine cases were fixed before rendering. Taxonomy and map differences are descriptive, not proof of feature suppression or geometric causality. Each pair of anomaly maps uses a shared color scale within its figure.
All metric deltas are SwinIR minus Bicubic. The reconstructed RGB panel uses the checkpoint hash recorded in the source run.

| Group | Sample | ΔAU-PRO@0.3 | ΔPixel AUROC | ΔROI-bg gap |
|---|---|---:|---:|---:|
| geometry | hazelnut/test/crack/013.png | -0.076146 | +0.004057 | +0.423456 |
| geometry | hazelnut/test/crack/015.png | -0.037417 | +0.007070 | +0.327292 |
| geometry | hazelnut/test/print/005.png | -0.015967 | -0.007083 | +0.146054 |
| suppression | hazelnut/test/crack/001.png | -0.022354 | -0.006696 | -0.199984 |
| suppression | hazelnut/test/crack/017.png | -0.013378 | -0.004003 | -0.002317 |
| suppression | hazelnut/test/hole/014.png | -0.010259 | -0.002452 | -0.537295 |
| controls | hazelnut/test/crack/006.png | +0.212322 | +0.001492 | +0.396311 |
| controls | hazelnut/test/cut/003.png | +0.105456 | +0.031705 | +1.190920 |
| controls | hazelnut/test/hole/006.png | +0.139957 | +0.000865 | -0.370210 |

## Figure observations

- [hazelnut/test/crack/013.png](geometry/01_hazelnut__test__crack__013.png): The SwinIR map has a brighter lower crack response, while the upper thin GT branch remains diffuse; AU-PRO falls despite a larger ROI-background gap.
- [hazelnut/test/crack/015.png](geometry/02_hazelnut__test__crack__015.png): Both maps emphasize the thick right-hand defect. The thin lower-left GT tail remains weak in both, and SwinIR AU-PRO is lower even as Pixel AUROC rises.
- [hazelnut/test/print/005.png](geometry/03_hazelnut__test__print__005.png): Both maps peak near the top print defect. The SwinIR peak looks more compact, but its AU-PRO and Pixel AUROC are slightly lower.
- [hazelnut/test/crack/001.png](suppression/01_hazelnut__test__crack__001.png): The right-hand defect hotspot is less bright in the SwinIR map on the shared scale; the gap and localization metrics both fall.
- [hazelnut/test/crack/017.png](suppression/02_hazelnut__test__crack__017.png): The two maps look similar at this display scale. The gap change is very small, so the image does not support a strong visual mechanism claim.
- [hazelnut/test/hole/014.png](suppression/03_hazelnut__test__hole__014.png): The SwinIR hotspot at the right-hand hole is weaker on the shared scale. The thin GT extension is weak in both maps.
- [hazelnut/test/crack/006.png](controls/01_hazelnut__test__crack__006.png): The lower-right defect response is brighter in the SwinIR map; the saved AU-PRO improves.
- [hazelnut/test/cut/003.png](controls/02_hazelnut__test__cut__003.png): The narrow central cut is more distinct relative to surrounding response in the SwinIR map; AU-PRO and Pixel AUROC improve.
- [hazelnut/test/hole/006.png](controls/03_hazelnut__test__hole__006.png): Both maps retain the small hole hotspot. AU-PRO improves even though the average ROI-background gap falls, showing that gap direction alone does not track localization here.

Rendering time: 25.3 seconds on this machine.
