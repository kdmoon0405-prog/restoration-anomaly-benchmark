"""Dummy tiled CPU integration only: no dataset images, model, FAISS or metrics."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import bounded_bank as bounded
from sr_anomaly import pcb_tiling as geometry
from sr_anomaly.dataset import safe_component
from sr_anomaly.tiled_cpu_pipeline import Parent, iter_saved_predictions, run_cpu_pipeline

PRIOR = ROOT / "analysis/pcb_bank_budget/pcb2-uniform-cap262144-20261016"
NATIVE = ROOT / "analysis/pcb_geometry/pcb2-native224-tiling-20261016"


def dummy_fixture():
    parents = [Parent("synthetic/fit-a", "fit", 0, (336, 224)),
               Parent("synthetic/fit-b", "fit", 0, (448, 336)),
               Parent("synthetic/cal-a", "calibration", 0, (336, 224)),
               Parent("synthetic/test-a", "test", 0, (336, 224)),
               Parent("synthetic/test-b", "test", 1, (448, 336))]
    codes = {p.sample: i+1 for i, p in enumerate(parents)}
    def loader(parent):
        x, y = np.meshgrid(np.arange(parent.size_wh[0]), np.arange(parent.size_wh[1]))
        code = codes[parent.sample]
        return np.stack(((x+17*code)%256, (y+29*code)%256, (x+y+13*code)%256), axis=-1).astype(np.uint8)
    def extractor(batch):
        base = batch[:, 0, 0, 0].astype(np.float32)[:, None, None, None]
        return (base + np.arange(2, dtype=np.float32)[None, :, None, None]*10
                + np.arange(2, dtype=np.float32)[None, None, :, None]
                + np.arange(4, dtype=np.float32)[None, None, None, :]*.125)
    def predictor(offset):
        def predict(tile, bank):
            values = tile.mean(axis=2, dtype=np.float32)/np.float32(255)
            values += np.float32(float(bank.mean())*.0001+offset)
            return values, float(tile[0, 0, 1])+100+offset
        return predict
    annotations = {p.sample: np.zeros(p.size_wh[::-1], dtype=bool) for p in parents}
    annotations[parents[-1].sample][-2:, -2:] = True
    return parents, loader, extractor, {"dummy_a": predictor(0.), "dummy_b": predictor(.5)}, annotations


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def memory_case(w, h):
    count = len(geometry.tile_boxes((w, h)))
    return {"source_wh": [w, h], "tiles": count, "one_RGB_board_bytes": w*h*3,
            "owned_tile_map_buffer_bytes": count*224*224*4, "float64_accumulator_bytes": w*h*8,
            "uint32_coverage_bytes": w*h*4, "float32_output_bytes": w*h*4,
            "reload_finite_check_bool_bytes": w*h, "map_lifetime": "one parent/variant, never dataset stack"}


def run(run_id):
    run_id = safe_component(run_id, "run-id")
    out = ROOT / "analysis/pcb_cpu_integration" / run_id
    payload = ROOT / "outputs/pcb-cpu-integration" / run_id
    if out.exists() or payload.exists():
        raise FileExistsError("Existing report/payload output is never overwritten")
    parents, loader, extractor, predictors, gt = dummy_fixture()
    sources = ["src/sr_anomaly/tiled_cpu_pipeline.py", "scripts/check_tiled_cpu_integration.py",
               "src/sr_anomaly/bounded_bank.py", "src/sr_anomaly/pcb_tiling.py"]
    protocol = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "scope": "SYNTHETIC CPU integration; real PCB/model/FAISS/degradation/calibration/metrics forbidden",
                "geometry_id": geometry.GEOMETRY_ID, "map_merger": "float64 sum in canonical tile-ID order / uint32 coverage -> float32",
                "board_score": "max original tile image scores; NOT max assembled map",
                "synthetic_settings": {"patch_shape": [2, 2], "dimension": 4, "capacity": 17, "batch_tiles": 2, "seed": 11},
                "gt_policy": "coordinate/binary validation only, never forwarded to extractor/predictor",
                "prior_budget_references": {n: bounded.file_sha256(PRIOR/n) for n in ("PROTOCOL.json", "selection_plan.json", "resource_plan.json")},
                "code_sha256": {n: bounded.file_sha256(ROOT/n) for n in sources},
                "python": platform.python_version(), "numpy": np.__version__,
                "pending": ["real _embed adapter and runtime ordering proof", "normalization/calibration stage/formula",
                            "180-normal calibration usage", "tile-wise x4 boundaries", "quality overlap accounting",
                            "native evaluation memory", "checkpoint/device smoke"],
                "actual_pcb_bank": "NOT_CREATED", "actual_pcb_calibration": "NOT_CREATED", "pilot": "NOT_READY_FOR_PILOT"}
    out.mkdir(parents=True)
    write_json(out / "PROTOCOL.json", protocol)
    provenance = {"input_kind": "synthetic", "source_commit": protocol["source_commit"], "code_sha256": protocol["code_sha256"],
                  "integration_protocol_sha256": bounded.file_sha256(out / "PROTOCOL.json")}
    try:
        state = run_cpu_pipeline(parents, loader, extractor, predictors, payload,
                                 annotations=gt, provenance=provenance, **protocol["synthetic_settings"])
        bank, ids, bank_state = bounded.load_complete_bank(payload / "synthetic-bank")
        inventory = {p.sample: p for p in parents}
        rows = []
        for row, values in iter_saved_predictions(payload):
            parent = inventory[row["sample"]]
            rgb = loader(parent)
            expected = np.zeros(parent.size_wh[::-1], dtype=np.float64)
            count = np.zeros(parent.size_wh[::-1], dtype=np.uint32)
            scores = []
            for x0, y0, x1, y1 in geometry.tile_boxes(parent.size_wh):
                tile_map, tile_score = predictors[row["variant"]](rgb[y0:y1, x0:x1], bank)
                expected[y0:y1, x0:x1] += tile_map
                count[y0:y1, x0:x1] += 1
                scores.append(tile_score)
            expected /= count
            if not np.array_equal(values, expected.astype(np.float32)) or row["score"] != max(scores):
                raise AssertionError("Saved dummy board identity/value mismatch")
            rows.append({"sample": row["sample"], "split": row["split"], "label": row["label"], "variant": row["variant"],
                         "dummy_board_score": row["score"], "width": parent.size_wh[0], "height": parent.size_wh[1],
                         "coverage_min": row["coverage_min"], "coverage_max": row["coverage_max"], "reload_exact": True})
            del values, expected, count, rgb
        result = {"synthetic_integration": "PASS", "parents": len(parents), "fit_parents": 2, "calibration_parents": 1,
                  "test_parents": 2, "saved_parent_variants": len(rows), "feature_vectors_expected": 32,
                  "feature_vectors_observed": bank_state["progress"]["observed_vectors"], "stored_vectors": len(ids),
                  "dimension": 4, "reload_exact": True, "bank_unchanged": state["bank_unchanged"],
                  "payload_status": (payload / "status.json").relative_to(ROOT).as_posix(),
                  "payload_status_sha256": bounded.file_sha256(payload / "status.json"),
                  "actual_pcb_bank": "NOT_CREATED", "actual_pcb_calibration": "NOT_CREATED", "pilot": "NOT_READY_FOR_PILOT"}
        with (out / "dummy_boards.csv").open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        write_json(out / "result.json", result)
    except BaseException as error:
        write_json(out / "result.json", {"synthetic_integration": "FAIL", "error": str(error),
                   "actual_pcb_bank": "NOT_CREATED", "actual_pcb_calibration": "NOT_CREATED", "pilot": "NOT_READY_FOR_PILOT"})
        raise
    native = json.loads((NATIVE / "layouts.json").read_text(encoding="utf-8"))
    old = json.loads((PRIOR / "resource_plan.json").read_text(encoding="utf-8"))
    memory = {"payload_estimates_only_not_RSS_or_VRAM": True,
              "bank_and_feature_stage": {k: old[k] for k in ("bounded_bank_vector_bytes", "selected_int64_index_bytes",
                  "input_chunk_payload_limit_bytes", "finite_check_bool_temporary_limit_bytes", "selected_rows_gather_temporary_limit_bytes")},
              "synthetic_boards": [memory_case(*p.size_wh) for p in parents],
              "native_board_scenarios": [memory_case(*v["source_wh"]) for v in native.values()],
              "native_evaluation_payloads_unchanged": old["native_evaluation_payloads_unchanged"],
              "RGB_feature_batch": "B*224*224*3 bytes for copied tiles, plus same-size stack while callback runs; B*Py*Px<=8192",
              "I_O": "np.save contiguous one-board output; streaming hashes; read-only mmap load + one-board finite bool check",
              "limits": "Per-board map buffer/accumulator/count/output coexist during assembly, but feature-stage buffers and reload scenarios differ. Do not sum all fields as measured peak. Callback internals/model/FAISS/upstream prefetch/allocator/OS cache and full evaluation remain unmeasured."}
    write_json(out / "memory_plan.json", memory)
    (out / "REPORT.md").write_text(
        "# Synthetic tiled CPU integration\n\nPASS: 2 fit / 1 normal calibration / 2 test synthetic parents; "
        "32 feature vectors ->17 stored, D=4; six parent/variant maps saved and exactly reloaded. "
        "All values/scores independently recomputed from dummy tile outputs; bank files unchanged.\n\n"
        "Map rule: canonical tile-ID float64 sum / geometry coverage, float32 output. "
        "Score rule: max tile image score, not map max. GT only validates coordinates. "
        "No normalization/calibration values, image quality or anomaly metrics are computed.\n\n"
        "Callbacks still require real _embed/model/checkpoint/device integration. Actual PCB bank/calibration "
        "NOT_CREATED; pilot NOT_READY_FOR_PILOT. This is separate from historical protocol families. "
        "See v0.4 draft, memory_plan.json and tests. No actual dataset RGB/GT read.\n", encoding="utf-8")
    print(json.dumps(result))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    run(parser.parse_args().run_id)
