# VisA PCB readiness only

| Category | Train normal | Test normal/anomaly | Total | Proposed fit/cal | Complete | Invalid/misaligned/cropped-empty masks | Local traces |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| pcb1 | 904 | 100/100 | 1104 | 723/181 | yes | 0/0/0 | 0 |
| pcb2 | 901 | 100/100 | 1101 | 721/180 | yes | 0/0/0 | 0 |
| pcb3 | 905 | 101/100 | 1106 | 724/181 | yes | 0/0/0 | 0 |
| pcb4 | 904 | 101/100 | 1105 | 723/181 | yes | 0/0/0 | 0 |

Recommend **pcb2** using the rule saved before the file audit in [PCB_SELECTION_RULE.json](PCB_SELECTION_RULE.json): complete official category with no observed local execution trace, minimum train+test count, lexical tie. This is not performance-based selection. [PCB_INVENTORY.json](PCB_INVENTORY.json) is the actual file/mask audit. Official `data/external/VisA/split_csv/1cls.csv` and `VisASplitCSV` are used; all training labels are normal, split paths disjoint, all listed images/masks readable. Image dimensions: 1404x1070. Mask dimensions/nonempty checks and nearest-resize/crop survival passed; pixel-level human semantic alignment was not established.

Local trace search covered category fields in results/metadata/split JSON under local outputs/checkpoints. No trace was observed, but the search is not proof about Git history, alternate schemas, other folders or teammate machines. **Ask both GPU operators about prior PCB use before calling it untouched or independent validation.** No test performance was inspected or computed.

## Ready / still missing

- Ready: raw data, official split CSV, test GT paths, existing VisA adapter, reusable x4 geometry and cached SwinIR/backbone checkpoints. Proposed official-training split: 721 fit / 180 normal calibration, fixed seed 11 and ratio 0.8; test 200. These are planning counts, not a fitted PCB bank or measured experiment.
- Still missing: teammate usage confirmation; a frozen standalone PCB protocol/manifest; actual PCB normal bank and normal-calibration artifacts; adapter wiring into the MVTec-specific runner; hardware smoke/runtime/peak-memory measurement. The generic data adapter exists, but the current frozen runner cannot simply be given `--category pcb2`. Do not offer an untested execution command.
- Recommended question for a separately authorized study: does fixed Bicubic-x4 versus SwinIR-S-x4 quality/localization behavior transfer to PCB, with the same PatchCore and post-hoc strict-sign taxonomy? Start with Clean/Bicubic/SwinIR baselines, not failed map gates. Fit only PCB normal training data; calibrate only held-out PCB normal training data. Test GT is evaluation only. No threshold/weight tuning after test inspection; do not reuse Hazelnut's fitted bank/normalization thresholds as PCB calibration. Primary metric remains pooled AU-PRO@0.3 if that protocol is approved. No result is asserted here; Capsule stays untouched.

## Planning estimates, not measurements

Same 224 canonical / 56 LR / x4 restoration geometry, WRN50-2 layers and original patch settings. Current bank has 245,392 vectors for 313 fit images. Assuming unchanged patch count and no coreset, proposed PCB bank: 565,264 vectors of dimension 1024; float32 vectors alone 2,315,321,344 bytes (2.156 GiB), 2.304x current vector storage. Index/feature-array copies, Python/Torch/model buffers and image queues need extra CPU RAM; this is not peak RSS/VRAM. Actual GPU VRAM is unknown; no GPU allocation was measured.

Rough CPU reference from instrumented means only: `T_detector = current non-FAISS mean + current FAISS mean * (PCB_fit/current_fit)` = 19.180 s/image/path. For 380 calibration+test images, three detector paths (clean/degraded/restored) plus one SR/image gives about 6.21 h, excluding decode, bank build, calibration/evaluation and IO. Fit embedding batch1-equivalent reference 521.3 s is NOT batch8 fit throughput or full fitting time. This is a simple linear bank-size extrapolation, not a measured PCB duration or confidence interval; cache/memory pressure and the observed timing drift may invalidate it. It must not be converted into a GPU speedup estimate. GPU runtime/VRAM requires separately authorized actual-hardware smoke before budgeting a full run.
