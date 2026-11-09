"""Read the previously fixed nine PCB cases. No model or threshold fitting."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json
from sr_anomaly.pcb_selected_spatial import VARIANTS, describe_maps, load_map, render_case


def verify_metadata(metadata, selected):
    bundle = ROOT / "analysis/gpu_return_20261109"
    selection = read_json(bundle / "selected_cases_manifest.json")
    analysis = read_json(bundle / "analysis_manifest.json")
    if (digest(bundle / "analysis_manifest.json") != selection["source_analysis_sha256"]
            or digest(selected) != selection["table_sha256"]):
        raise ValueError("Fixed selection/analysis changed")
    needed = ["pcb/raw-run/PROTOCOL.json", *[f"pcb/postprocess/calibration/{v}.json" for v in VARIANTS]]
    for name in needed:
        if digest(relative_source(metadata, name)) != analysis["sources"][name]:
            raise ValueError("Metadata differs from reviewed return")
    raw_root = metadata / "pcb/raw-run"
    raw = read_json(raw_root / "status.json")
    protocol = read_json(raw_root / "PROTOCOL.json")
    bank = read_json(raw_root / "bank_status.json")
    calibration = read_json(metadata / "pcb/postprocess/calibration/status.json")
    if (raw["status"] != "COMPLETE" or raw["scope"] != "full-pilot-raw"
            or not raw["bank_unchanged"] or not raw["actual_bank_reused"]
            or raw["protocol_sha256"] != digest(raw_root / "PROTOCOL.json")
            or raw["units_manifest_sha256"] != digest(raw_root / "units_manifest.csv")
            or raw["bank_artifact_sha256"] != protocol["bank_copy_sha256"]
            or raw["bank_artifact_sha256"]["status.json"] != digest(raw_root / "bank_status.json")
            or bank["provenance"] != raw["provenance"]
            or calibration["status"] != "COMPLETE"
            or calibration["raw_status_sha256"] != digest(raw_root / "status.json")):
        raise ValueError("Raw/bank/calibration metadata binding mismatch")
    units = csv_rows(raw_root / "units_manifest.csv")
    index = {(row["sample"], row["variant"]): row for row in units}
    if len(index) != len(units):
        raise ValueError("Duplicate raw units")
    cases = csv_rows(selected)
    if len(cases) != 9 or len({row["sample"] for row in cases}) != 9:
        raise ValueError("Expected fixed nine unique cases")
    for row in cases:
        for variant in VARIANTS:
            unit = index[(row["sample"], variant)]
            if (unit["split"] != "test" or unit["label"] != "1"
                    or unit["file"] != row[f"{variant}_file"]
                    or unit["sha256"] != row[f"{variant}_sha256"]):
                raise ValueError("Selected identity/path/hash mismatch")
    return cases, raw, protocol


def run(maps_root, metadata, data_root, output):
    selected = ROOT / "analysis/gpu_return_20261109/selected_native_map_cases.csv"
    cases, raw, protocol = verify_metadata(metadata, selected)
    output = new_output(output, inputs=(maps_root, metadata, data_root))
    state = dict(kind="exploratory_selected_native_map_analysis", status="BUILDING",
        research_metrics_recomputed=False, population_estimate=False,
        bank_payload_bytes_verified=False, native_gt_verified=False,
        raw_map_bytes_verified=0, runtime_source_commit=protocol["source_commit"],
        runtime_source_worktree_dirty=protocol["source_worktree_dirty"],
        selection_sha256=digest(selected), gt_use="posthoc_spatial_evaluation_only",
        source_sha256={str(path.relative_to(ROOT).as_posix()): digest(path) for path in
            (ROOT / "src/sr_anomaly/pcb_selected_spatial.py", Path(__file__))})
    write_json(output / "manifest.json", state)
    try:
        missing = [row[f"{v}_file"] for row in cases for v in VARIANTS
                   if not relative_source(maps_root, row[f"{v}_file"]).is_file()]
        if missing:
            state.update(status="WAITING_FOR_SELECTED_MAPS", missing_files=missing, maps_analyzed=0)
            write_json(output / "manifest.json", state)
            return state
        from sr_anomaly.pcb_input_binding import FrozenPCBInputs
        from sr_anomaly.pcb_board_analysis import _budget
        inputs = FrozenPCBInputs(ROOT, data_root)
        for name, expected in protocol["references_sha256"].items():
            if digest(relative_source(ROOT, name)) != expected:
                raise ValueError("Frozen reference differs from execution")
        parents = {p.sample: p for p in inputs.parents}
        if raw["parents"] != [dict(sample=p.sample, split=p.split, label=p.label,
                                   size_wh=list(p.size_wh)) for p in inputs.parents]:
            raise ValueError("Frozen parent inventory mismatch")
        params = {v: read_json(metadata / f"pcb/postprocess/calibration/{v}.json") for v in VARIANTS}
        board_rows, component_rows, file_receipts = [], [], []
        for i, row in enumerate(cases):
            parent = parents[row["sample"]]
            # Includes three raw/normalized maps, labels, gradients and rendering headroom.
            payload_plan = parent.size_wh[0] * parent.size_wh[1] * 8 * 24 + 128 * 1024**2
            _budget(payload_plan, None)
            maps = {v: load_map(maps_root, row[f"{v}_file"], row[f"{v}_sha256"], parent.size_wh[::-1])
                    for v in VARIANTS}
            mask = inputs.evaluation_mask(parent)
            if not mask.any():
                raise ValueError("Selected anomaly GT is empty")
            result, normalized, seam = describe_maps(maps, mask, params)
            common = {key: row[key] for key in ("sample", "selection_group", "regression_type")}
            for variant in VARIANTS:
                board_rows.append(dict(common, variant=variant, **result["variants"][variant],
                    **result["comparison"], gt_area_pixels=result["gt_area_pixels"],
                    gt_on_seam_pixels=result["gt_on_seam_pixels"], gt_on_seam_ratio=result["gt_on_seam_ratio"]))
                file_receipts.append(dict(sample=parent.sample, variant=variant,
                    sha256=row[f"{variant}_sha256"], file=row[f"{variant}_file"]))
            component_rows.extend(dict(common, **component) for component in result["components"])
            render_case(output / f"case-{i:02d}.png", parent.sample, inputs.rgb(parent), mask, normalized, seam)
            del maps, mask, normalized, seam, result
        write_csv(output / "spatial_descriptors.csv", board_rows)
        write_csv(output / "component_descriptors.csv", component_rows)
        write_json(output / "input_receipts.json", dict(maps=file_receipts, gt=inputs.gt_receipts,
                                                        rgb=inputs.rgb_receipts))
        state.update(status="COMPLETE", boards_analyzed=9, maps_analyzed=27, connectivity=4,
            native_gt_verified=True, raw_map_bytes_verified=27,
            files={p.name: digest(p) for p in sorted(output.iterdir()) if p.name != "manifest.json"},
            payload_plan_last_board_bytes=payload_plan, payload_plan_is_measured_peak=False,
            original_arrays_rewritten=False)
    except Exception as error:
        state.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        write_json(output / "manifest.json", state)
        raise
    write_json(output / "manifest.json", state)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maps-root", type=Path, required=True)
    parser.add_argument("--metadata-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        state = run(args.maps_root, args.metadata_root, args.data_root, args.output)
        print(json.dumps({k: state[k] for k in ("status", "maps_analyzed")}))
        return 0 if state["status"] == "COMPLETE" else 2
    except (ValueError, KeyError, OSError, TypeError, MemoryError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
