# Synthetic tiled CPU integration

PASS: 2 fit / 1 normal calibration / 2 test synthetic parents; 32 feature vectors ->17 stored, D=4; six parent/variant maps saved and exactly reloaded. All values/scores independently recomputed from dummy tile outputs; bank files unchanged.

Map rule: canonical tile-ID float64 sum / geometry coverage, float32 output. Score rule: max tile image score, not map max. GT only validates coordinates. No normalization/calibration values, image quality or anomaly metrics are computed.

Callbacks still require real _embed/model/checkpoint/device integration. Actual PCB bank/calibration NOT_CREATED; pilot NOT_READY_FOR_PILOT. This is separate from historical protocol families. See v0.4 draft, memory_plan.json and tests. No actual dataset RGB/GT read.
