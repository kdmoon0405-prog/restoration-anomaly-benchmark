# Screw selected-case NN-distance handoff

Run only the six cases already frozen in `analysis/screw/selected_mechanism_cases.csv`: three suppression examples and three success controls. Screw has no geometry candidates under the frozen taxonomy, so none are invented. Do not rerun all 119 anomalous images and do not change the manifest after viewing figures.

Required bank copied from the completed Screw GPU run:

```text
checkpoints/legacy-patchcore/screw-seed11-train320/
  metadata.json
  patchcore_params.pkl
  nnscorer_search_index.faiss
```

The script verifies the bank metadata/checksums against the full-run `results.json`, the pinned PatchCore commit/settings, the 320 normal training paths, and the SwinIR checkpoint SHA256 before selected inference.

From `research_code/` on the NVIDIA PC:

```powershell
git checkout exp/hazelnut-analysis
git pull --ff-only
git submodule update --init
.venv\Scripts\python -X utf8 scripts\analyze_patchcore_nn_selected.py --run-dir outputs\legacy-patchcore\screw-full320-test160 --model-dir checkpoints\legacy-patchcore\screw-seed11-train320 --data-root data\external\MVTecAD --swinir-checkpoint checkpoints\swinir\002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth --selected-cases analysis\screw\selected_mechanism_cases.csv --output-dir analysis\screw --device cuda
```

Outputs:

- `analysis/screw/nn_distance_selected.csv`
- `analysis/screw/nn_distance_selected_summary.md`

For each Bicubic/SwinIR branch the script records official FAISS `IndexFlatL2` squared-L2 patch distances. FAISS remains CPU exact search; the PatchCore backbone and SwinIR use CUDA. GT is mapped to the actual 28x28 feature grid by continuous cell occupancy, matching the Hazelnut definition.

Reported post-hoc quantities are `D_defect`, `D_background`, and `G_feature = D_defect - D_background`, plus SwinIR-minus-Bicubic deltas. No new threshold or case selection is allowed. The result remains selected-case descriptive evidence, not a population estimate or causal proof.

The bank is not present on the current CPU machine and was not included in `screw-full320-test160.zip`; this handoff cannot be executed locally.
