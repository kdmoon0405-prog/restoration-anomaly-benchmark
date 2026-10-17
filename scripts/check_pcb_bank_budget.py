"""Freeze a PCB index-only resource plan and exercise synthetic feature streams."""
from __future__ import annotations

import argparse
from bisect import bisect_right
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import bounded_bank as bounded
from sr_anomaly.dataset import safe_component

GEOMETRY = ROOT / "analysis/pcb_geometry/pcb2-native224-tiling-20261016"


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def synthetic_stream(n, d, chunk_size):
    for start in range(0, n, chunk_size):
        yield np.arange(start, min(n, start+chunk_size), dtype=np.float32)[:, None] + np.arange(d, dtype=np.float32)[None, :] * .25


def run(run_id):
    run_id = safe_component(run_id, "run-id")
    out = ROOT / "analysis/pcb_bank_budget" / run_id
    payload = ROOT / "outputs/pcb-bank-budget" / run_id
    if out.exists() or payload.exists():
        raise FileExistsError("Never overwrite an existing report or payload run")
    manifest = json.loads((GEOMETRY / "MANIFEST.json").read_text(encoding="utf-8"))
    for filename, key in (("PROTOCOL.json", "protocol_sha256"), ("INPUTS.csv", "inputs_csv_sha256"), ("layouts.json", "layouts_sha256")):
        if bounded.file_sha256(GEOMETRY / filename) != manifest[key]:
            raise ValueError("Frozen geometry provenance mismatch")
    with (GEOMETRY / "INPUTS.csv").open(encoding="utf-8", newline="") as handle:
        inputs = list(csv.DictReader(handle))
    fit = [r for r in inputs if r["partition"] == "fit"]
    if any(r["label"] != "0" for r in fit) or len({r["sample"] for r in fit}) != len(fit):
        raise ValueError("Fit must contain unique normal parent paths only")
    if len(fit) != manifest["partitions"]["fit"]["normal"]:
        raise ValueError("Fit composition changed")
    old = json.loads((GEOMETRY / "resource_estimate.json").read_text(encoding="utf-8"))
    layouts = json.loads((GEOMETRY / "layouts.json").read_text(encoding="utf-8"))
    offsets = [0]
    for row in fit:
        count = int(row["tile_count"])
        if len(layouts[row["geometry_key"]]["boxes_xyxy"]) != count:
            raise ValueError("Per-parent tile inventory mismatch")
        offsets.append(offsets[-1] + count * old["patches_per_224_tile"])
    if offsets[-1] != old["embedding_vectors"]["fit"]:
        raise ValueError("Expected feature count differs from geometry resource plan")
    code = ["src/sr_anomaly/bounded_bank.py", "scripts/check_pcb_bank_budget.py",
            "third_party/patchcore-inspection/src/patchcore/patchcore.py",
            "third_party/patchcore-inspection/src/patchcore/common.py",
            "scripts/run_fusion_patchcore.py"]
    protocol = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "scope": "index-only planning + synthetic bank; no real feature/model/FAISS/metric execution",
                "implementation_id": bounded.IMPLEMENTATION_ID, "geometry_id": manifest["geometry_id"],
                "settings": {"total_vectors": offsets[-1], "capacity": 262144, "dimension": 1024, "seed": 11, "max_chunk_vectors": 8192},
                "global_order": "fit INPUTS.csv order -> layout boxes row-major -> _embed batch-major, patch-y then patch-x (width fastest)",
                "patch_grid": [28, 28], "patch_grid_evidence": "784 from saved bank shape; Unfold/reshape ordering read statically; actual native-runner integration still pending",
                "geometry_references": {name: bounded.file_sha256(GEOMETRY / name) for name in ("MANIFEST.json", "PROTOCOL.json", "INPUTS.csv", "layouts.json", "resource_estimate.json")},
                "code_sha256": {name: bounded.file_sha256(ROOT / name) for name in code},
                "python": sys.version.split()[0], "numpy": np.__version__,
                "pending": ["map merger", "board score", "normal calibration stage", "tile-wise x4/boundaries", "native evaluation memory", "PCB runner wiring", "checkpoint/device smoke"],
                "pcb_bank": "NOT_CREATED", "pcb_calibration": "NOT_CREATED", "pilot": "NOT_READY_FOR_PILOT"}
    out.mkdir(parents=True)
    write_json(out / "PROTOCOL.json", protocol)
    payload.mkdir(parents=True)
    cfg, selected = bounded.selection_plan(**protocol["settings"])
    selection_file = payload / "planned_global_indices.npy"
    with selection_file.open("xb") as handle:
        np.save(handle, selected, allow_pickle=False)
    examples = []
    for global_id in list(map(int, selected[:3])) + list(map(int, selected[-3:])):
        parent = bisect_right(offsets, global_id)-1
        tile, patch = divmod(global_id-offsets[parent], old["patches_per_224_tile"])
        examples.append({"global_index": global_id, "fit_parent_index": parent, "sample": fit[parent]["sample"],
                         "tile_index": tile, "tile_xyxy": layouts[fit[parent]["geometry_key"]]["boxes_xyxy"][tile],
                         "patch_index": patch, "patch_y": patch//28, "patch_x": patch%28})
    write_json(out / "selection_examples.json", examples)
    plan = {"status": "INDICES_ONLY_NO_PCB_FEATURES", **cfg, "selected_count": len(selected),
            "selection_indices_sha256": bounded.index_sha256(selected), "index_file_sha256": bounded.file_sha256(selection_file),
            "index_file": selection_file.relative_to(ROOT).as_posix(), "geometry_id": manifest["geometry_id"],
            "fit_parent_order_reference": "INPUTS.csv fit rows; no re-sorting", "pcb_observed_vectors": 0,
            "pcb_bank": "NOT_CREATED", "pcb_calibration": "NOT_CREATED"}
    write_json(out / "selection_plan.json", plan)
    # Small bank only; a million rows are generated lazily, never held as an NxD matrix.
    n, d, k = 1_000_003, 8, 257
    synthetic = payload / "synthetic-bank"
    state = bounded.save_bank(synthetic_stream(n, d, 8192), synthetic,
                             provenance={"input_kind": "synthetic", "geometry_id": "NOT_APPLICABLE",
                                         "source_commit": protocol["source_commit"], "code_sha256": protocol["code_sha256"],
                                         "formula": "feature[row,col] = float32(row) + float32(col)*0.25"},
                             total_vectors=n, dimension=d, capacity=k, seed=11)
    bank, ids, metadata = bounded.load_complete_bank(synthetic)
    expected = ids[:, None].astype(np.float32) + np.arange(d, dtype=np.float32)[None, :] * .25
    if not np.array_equal(bank, expected):
        raise AssertionError("Synthetic selected feature identity mismatch")
    write_json(out / "synthetic_validation.json", {"status": "SYNTHETIC_COMPLETE_NOT_PCB", "observed_vectors": metadata["progress"]["observed_vectors"],
               "stored_vectors": len(ids), "dimension": d, "bank_payload_bytes": int(bank.nbytes),
               "index_payload_bytes": int(ids.nbytes), "max_chunk_vectors_seen": state["progress"]["max_chunk_vectors_seen"],
               "reference_equality": True, "state_file": (synthetic / "status.json").relative_to(ROOT).as_posix(),
               "state_file_sha256": bounded.file_sha256(synthetic / "status.json"),
               "pcb_bank": "NOT_CREATED", "pcb_calibration": "NOT_CREATED", "pilot": "NOT_READY_FOR_PILOT"})
    bank_bytes = len(selected)*cfg["dimension"]*4
    chunk_bytes = cfg["max_chunk_vectors"]*cfg["dimension"]*4
    resource = {"planning_only_not_RSS_or_VRAM": True,
                "old_full_bank_vector_bytes": old["cpu_exact_index_vector_bytes"], "bounded_bank_vector_bytes": bank_bytes,
                "selected_int64_index_bytes": int(selected.nbytes), "input_chunk_payload_limit_bytes": chunk_bytes,
                "finite_check_bool_temporary_limit_bytes": cfg["max_chunk_vectors"]*cfg["dimension"],
                "selected_rows_gather_temporary_limit_bytes": chunk_bytes,
                "selection_python_list_set_overhead": "O(min(N,K)); not measured; CPython sample/sort list objects coexist transiently",
                "hypothetical_three_bank_payload_fit_bytes": 3*bank_bytes,
                "hypothetical_scorer_plus_CPU_index_payload_bytes": 2*bank_bytes,
                "faiss_created": False, "PCB_features_extracted": False,
                "native_evaluation_payloads_unchanged": {key: old[key] for key in ("test_float32_maps_one_method_bytes", "test_float64_score_copy_bytes", "one_full_length_int64_sort_or_rank_array_bytes", "aupro_retained_region_bool_masks_bytes")},
                "limits": "Buffer scenarios overlap, do not sum as measured peaks. Excludes upstream model/producer buffering, Python/runtime/allocator, filesystem cache and FAISS workspace. Artifact loader hashes sequentially then mmaps; no bank-sized tobytes. No real PCB bounded bank or hardware feasibility demonstrated."}
    write_json(out / "resource_plan.json", resource)
    (out / "REPORT.md").write_text(
        "# Bounded PCB bank CPU draft\n\nIndex-only plan: 262,144 / 27,132,672 normal-fit patch IDs, seed 11. "
        "No actual PCB features. New uniform sampled bank, not IdentitySampler or greedy coreset.\n\n"
        "Synthetic lazy stream: 1,000,003 rows, D=8, K=257; selected values match formula exactly. "
        "Synthetic bank COMPLETE is NOT a PCB bank. Actual PCB bank/calibration NOT_CREATED; pilot NOT_READY_FOR_PILOT.\n\n"
        "Planned payloads: bank 1 GiB, int64 indices 2 MiB, input chunk <=32 MiB, gather <=32 MiB, "
        "finite check <=8 MiB. Python sample/sort overhead O(K) excluded. These are payload bounds, not measured RSS/VRAM. "
        "Index/scorer copies and native evaluation remain separate unresolved budgets.\n\n"
        "Selection is uniform over the overlapping-tile patch pool, NOT over physical pixels; rare normal modes may be missed. "
        "Geometry/split/old metrics and existing runners are unchanged. See protocol and resource_plan.json.\n", encoding="utf-8")
    print(json.dumps({"plan": plan["status"], "synthetic": "COMPLETE", "pcb_bank": "NOT_CREATED", "pilot": "NOT_READY_FOR_PILOT"}))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    run(parser.parse_args().run_id)
