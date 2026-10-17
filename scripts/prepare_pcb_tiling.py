"""CPU-only native PCB tiling audit and arithmetic resource plan, not inference."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import platform
import subprocess
import sys
import importlib.metadata

import numpy as np
from PIL import Image
from skimage.measure import label, regionprops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import pcb_tiling as geometry
from sr_anomaly.dataset import safe_component
from scripts.prepare_pcb_geometry import REFERENCE, partitions_for, sha, write_csv, write_json

PRIOR = ROOT / "analysis/pcb_geometry/pcb2-full-frame224-20261015"
PROFILE = ROOT / "analysis/profiling_results_demo/hazelnut-ten-20261015"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def check_equal(actual, expected, message):
    if not np.array_equal(actual, expected):
        raise ValueError(message)


def render_figures(out, payloads, selection):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    figures = out / "figures"
    figures.mkdir()
    normal = next((v for v in payloads.values() if not v["label"]), None)
    chosen = ([normal] if normal else []) + [payloads[r["sample"]] for r in selection[:1] if r["sample"] in payloads]
    fig, axes = plt.subplots(len(chosen), 3, figsize=(13, 3.7 * len(chosen)), squeeze=False)
    for row, p in enumerate(chosen):
        axes[row, 0].imshow(p["rgb"])
        for x0, y0, x1, y1 in p["boxes"]:
            axes[row, 0].add_patch(Rectangle((x0-.5, y0-.5), x1-x0, y1-y0, fill=False, edgecolor="cyan", linewidth=.45))
        axes[row, 0].set_title(f"{Path(p['sample']).name}: {len(p['boxes'])} native tiles; label={p['label']}")
        im = axes[row, 1].imshow(p["coverage"], vmin=1, vmax=max(1, int(p["coverage"].max())), cmap="viridis", interpolation="nearest")
        fig.colorbar(im, ax=axes[row, 1], label="coverage count")
        axes[row, 1].set_title("Full source coverage; no resizing")
        axes[row, 2].imshow(p["rebuilt_rgb"])
        axes[row, 2].set_title("Reassembled RGB: exact equality, max byte difference=0")
        for a in axes[row]:
            a.axis("off")
    fig.suptitle("Geometry only, no model / degradation. Cyan = tile boundaries; RGB is local-only.")
    fig.tight_layout()
    fig.savefig(figures / "tiling_overview.png", dpi=140)
    plt.close(fig)

    chosen = [r for r in selection if r["sample"] in payloads]
    if chosen:
        fig, axes = plt.subplots(len(chosen), 3, figsize=(11, 3.5 * len(chosen)), squeeze=False)
        for row, selected in enumerate(chosen):
            p = payloads[selected["sample"]]
            component = selected["illustrated_source_component_id"]
            ys, xs = np.nonzero(p["ids"] == component)
            x0, x1 = max(0, int(xs.min())-12), min(p["ids"].shape[1], int(xs.max())+13)
            y0, y1 = max(0, int(ys.min())-12), min(p["ids"].shape[0], int(ys.max())+13)
            source = p["ids"][y0:y1, x0:x1] == component
            rebuilt = p["rebuilt_ids"][y0:y1, x0:x1] == component
            axes[row, 0].imshow(p["rgb"][y0:y1, x0:x1], interpolation="nearest")
            axes[row, 0].contour(source, levels=[.5], colors=["lime"], linewidths=.8)
            axes[row, 0].set_title(f"{Path(p['sample']).name}: original ID {component}; {len(xs)} source px")
            axes[row, 1].imshow(source, cmap="gray", vmin=0, vmax=1, interpolation="nearest")
            axes[row, 1].set_title("Original selected GT ID (source coordinates)")
            axes[row, 2].imshow(rebuilt, cmap="gray", vmin=0, vmax=1, interpolation="nearest")
            axes[row, 2].set_title("Reassembled same ID: difference pixels=0")
            for a in axes[row]:
                a.axis("off")
        fig.suptitle("Historical examples fixed before this audit; zooms are figures, never adaptive model inputs.")
        fig.tight_layout()
        fig.savefig(figures / "component_reassembly.png", dpi=140)
        plt.close(fig)
    return {path.name: sha(path) for path in sorted(figures.glob("*.png"))}


def audit(root, out, prior_dir=PRIOR, reference=REFERENCE, profile=PROFILE):
    prior_manifest = json.loads((prior_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    if sha(prior_dir / "INPUTS.csv") != prior_manifest["inputs_csv_sha256"] or sha(prior_dir / "PROTOCOL.json") != prior_manifest["protocol_sha256"]:
        raise ValueError("Prior frozen audit hash mismatch")
    prior_inputs = {r["sample"]: r for r in read_csv(prior_dir / "INPUTS.csv")}
    previous_components = read_csv(prior_dir / "components.csv")
    previous_lost = {(r["sample"], int(r["component_id"])): int(r["source_area_pixels"]) for r in previous_components if r["represented"] == "False"}
    selection = json.loads((prior_dir / "selected_examples.json").read_text(encoding="utf-8"))
    previous_summary = json.loads((prior_dir / "summary.json").read_text(encoding="utf-8"))
    if len(previous_lost) != previous_summary["lost_source_components"]:
        raise ValueError("Prior lost-ID inventory mismatch")
    split_path = reference / "PCB_SPLIT_AUDIT.json"
    prior_split = json.loads(split_path.read_text(encoding="utf-8"))
    groups = partitions_for(root, prior_split)
    if {s.relative_path.as_posix() for samples in groups.values() for s in samples} != set(prior_inputs):
        raise ValueError("Prior input inventory differs from official/reference partitions")
    spec = json.loads((profile / "PROTOCOL.json").read_text(encoding="utf-8"))["model_spec"]
    bank_memory = json.loads((profile / "summary.json").read_text(encoding="utf-8"))["bank_memory"]
    code_paths = ["scripts/prepare_pcb_tiling.py", "src/sr_anomaly/pcb_tiling.py", "scripts/prepare_pcb_geometry.py",
                  "src/sr_anomaly/dataset.py", "src/sr_anomaly/fusion.py", "scripts/run_legacy_patchcore.py",
                  "scripts/run_fusion_patchcore.py", "src/sr_anomaly/evaluation.py",
                  "third_party/patchcore-inspection/src/patchcore/patchcore.py",
                  "third_party/patchcore-inspection/src/patchcore/common.py"]
    protocol = {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "geometry_id": geometry.GEOMETRY_ID, "tile_wh": [224, 224], "maximum_stride": 192,
        "axis_rule": "n=ceil((L-224)/192)+1; starts=round_half_up(i*(L-224)/(n-1)); L=224 -> [0]",
        "rounding": "integer exact: (2*i*span+intervals)//(2*intervals); ties upward, no floats",
        "small_input_policy": "reject any axis <224; never implicitly resize/pad",
        "native_slices_only": True, "tile_order": "row-major y then x; GT-independent",
        "component_reference": "original binary GT 8-connected IDs, reconstruct IDs at source coordinates, not physical defects",
        "normal_gt_policy": "Official normal masks absent; use explicit implicit-zero array for geometry audit only, not a read GT file",
        "readiness": "geometry identity pass is NOT GPU/pilot readiness; no fit, inference, degradation or anomaly metric",
        "figure_selection": "reuse prior selected examples; plus lexical first normal test sample; no tile selection by GT",
        "pending": ["anomaly-map overlap merger", "board score aggregation", "normal calibration stage/domain", "tile-wise x4 protocol", "resource feasibility", "runner integration", "checkpoint/device smoke"],
        "official_csv_sha256": prior_split["official_csv_sha256"], "seed": 11, "fit_ratio": .8,
        "reference_split_sha256": sha(split_path),
        "prior_artifact_sha256": {name: sha(prior_dir / name) for name in ("PROTOCOL.json", "INPUTS.csv", "components.csv", "summary.json", "selected_examples.json")},
        "resource_reference_sha256": {name: sha(profile / name) for name in ("PROTOCOL.json", "summary.json")},
        "code_sha256": {p: sha(ROOT / p) for p in code_paths},
        "python": platform.python_version(), "versions": {n: importlib.metadata.version(n) for n in ("numpy", "Pillow", "scikit-image")},
    }
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "PROTOCOL.json", protocol)
    inputs, records, components, recovered, errors = [], [], [], [], []
    layouts, coverage_cache, payloads = {}, {}, {}
    counts = {name: 0 for name in groups}
    selected_samples = {r["sample"] for r in selection}
    normal_sample = min(s.relative_path.as_posix() for s in groups["test"] if s.metadata["label"] == 0)
    test_pixels = eval_regions = region_mask_pixels = 0
    for partition, samples in groups.items():
        for item in samples:
            sample = item.relative_path.as_posix()
            row = {"sample": sample, "partition": partition, "label": item.metadata["label"], "error": ""}
            old = prior_inputs[sample]
            raw = item.path.read_bytes()
            raw_mask = item.mask_path.read_bytes() if item.mask_path else None
            if hashlib.sha256(raw).hexdigest() != old["image_sha256"] or (hashlib.sha256(raw_mask).hexdigest() if raw_mask else "") != old["mask_sha256"]:
                raise ValueError(f"Source inputs changed since resize audit: {sample}")
            record = dict(old)
            try:
                with Image.open(BytesIO(raw)) as image:
                    rgb = np.asarray(image.convert("RGB"))
                h, w = rgb.shape[:2]
                if raw_mask:
                    with Image.open(BytesIO(raw_mask)) as image:
                        values = np.asarray(image)
                    if values.ndim != 2 or values.shape != (h, w) or values.dtype.kind not in "biu" or (values < 0).any():
                        raise ValueError("Invalid native image/GT dimensions or dtype")
                    mask = values > 0
                    if not mask.any() or mask.all() or not row["label"]:
                        raise ValueError("Invalid anomaly GT or unexpected normal mask")
                else:
                    if row["label"]:
                        raise ValueError("Anomalous GT missing")
                    mask = np.zeros((h, w), dtype=bool)
                key = f"{w}x{h}"
                boxes = geometry.tile_boxes((w, h))
                if boxes != geometry.tile_boxes((w, h)):
                    raise ValueError("Nondeterministic layout")
                if key not in layouts:
                    coverage_cache[key] = geometry.coverage_map((w, h), boxes)
                    layouts[key] = {"source_wh": [w, h], "tile_wh": [224, 224], "boxes_xyxy": boxes,
                                    "x_starts": geometry.axis_starts(w), "y_starts": geometry.axis_starts(h),
                                    "coordinate_transform": "tile(u,v) -> source(x0+u,y0+v); inverse translation, no resampling",
                                    "coverage_min": int(coverage_cache[key].min()), "coverage_max": int(coverage_cache[key].max())}
                rebuilt = {}
                ids = label(mask, connectivity=2, background=0)
                for name, source in (("rgb", rgb), ("mask", mask), ("ids", ids)):
                    def checked_tiles():
                        for tile, (x0, y0, x1, y1) in zip(geometry.extract_tiles(source, boxes), boxes, strict=True):
                            check_equal(tile, source[y0:y1, x0:x1], f"{name} native tile slice mismatch")
                            yield tile
                    rebuilt[name] = geometry.reassemble_exact(checked_tiles(), boxes, source.shape)
                    check_equal(rebuilt[name], source, f"{name} reconstruction differs")
                row.update({"tile_count": len(boxes), "coverage_min": layouts[key]["coverage_min"], "coverage_max": layouts[key]["coverage_max"],
                            "rgb_exact": True, "gt_exact": True, "ids_exact": True, "source_components": int(ids.max()), "lost_components": 0,
                            "gt_source": "official_file" if raw_mask else "implicit_zero_from_normal_label"})
                id_counts = np.bincount(rebuilt["ids"].ravel())
                for region in regionprops(ids):
                    count = int(id_counts[region.label])
                    component = {"sample": sample, "component_id": int(region.label), "source_area_pixels": int(region.area),
                                 "reassembled_area_pixels": count, "preserved_exactly": count == int(region.area)}
                    components.append(component)
                    previous = previous_lost.get((sample, int(region.label)))
                    if previous is not None:
                        if previous != int(region.area) or count != previous:
                            raise ValueError("Historical lost-ID identity/area changed")
                        recovered.append(component)
                if partition == "test":
                    test_pixels += w * h
                    # Evaluation.py uses 4-connectivity, unlike this 8-connected geometry taxonomy.
                    regions4 = int(label(mask, connectivity=1, background=0).max())
                    eval_regions += regions4
                    region_mask_pixels += regions4 * w * h
                counts[partition] += len(boxes)
                record.update({"geometry_key": key, "tile_count": len(boxes)})
                if sample in selected_samples or sample == normal_sample:
                    payloads[sample] = {"sample": sample, "label": row["label"], "rgb": rgb, "rebuilt_rgb": rebuilt["rgb"],
                                        "ids": ids, "rebuilt_ids": rebuilt["ids"], "boxes": boxes, "coverage": coverage_cache[key]}
            except (ValueError, OSError) as error:
                row["error"] = str(error)
                errors.append({"sample": sample, "error": str(error)})
            records.append(row)
            inputs.append(record)
    recovered_all = len(recovered) == len(previous_lost)
    summary = {"geometry_status": "GEOMETRY_IDENTITY_PASS" if not errors and recovered_all else "BLOCKED_GEOMETRY",
               "pilot_status": "NOT_READY_FOR_PILOT", "input_images": len(records),
               "official_anomaly_masks": sum(r["label"] for r in records), "implicit_normal_masks": sum(not r["label"] for r in records),
               "errors": errors, "all_covered": not errors, "rgb_exact_images": sum(r.get("rgb_exact", False) for r in records),
               "gt_exact_images": sum(r.get("gt_exact", False) for r in records), "source_components_8connected": len(components),
               "lost_components": sum(not r["preserved_exactly"] for r in components),
               "historical_lost_components": len(previous_lost), "historical_lost_ids_recovered_exactly": len(recovered),
               "tile_counts": counts, "no_scientific_metric_or_model_execution": True,
               "bank_created": False, "calibration_created": False, "teammate_prior_use": "unconfirmed"}
    write_csv(out / "INPUTS.csv", inputs, list(dict.fromkeys(k for r in inputs for k in r)))
    write_csv(out / "per_image_geometry.csv", records, list(dict.fromkeys(k for r in records for k in r)))
    fields = ["sample", "component_id", "source_area_pixels", "reassembled_area_pixels", "preserved_exactly"]
    write_csv(out / "components.csv", components, fields)
    write_csv(out / "previously_lost_ids.csv", recovered, fields)
    write_json(out / "layouts.json", layouts)
    write_json(out / "summary.json", summary)
    estimate = geometry.estimate_resources(counts, test_pixels, eval_regions, region_mask_pixels, spec, bank_memory)
    estimate["valid_for_complete_cohort"] = not errors
    estimate["reference_model_spec"] = {k: v for k, v in spec.items() if k not in ("train_paths", "calibration_paths")}
    write_json(out / "resource_estimate.json", estimate)
    manifest = {"geometry_id": geometry.GEOMETRY_ID, "partitions": prior_split["composition"], "partition_overlap": False,
                "input_inventory_matches_previous": True, "all_input_hashes_match_previous": True,
                "protocol_sha256": sha(out / "PROTOCOL.json"), "inputs_csv_sha256": sha(out / "INPUTS.csv"),
                "layouts_sha256": sha(out / "layouts.json"), "path_base": "VisA root relative",
                "pcb_bank": "not_created", "pcb_calibration": "not_created", "reuse_hazelnut_bank_or_threshold": False}
    write_json(out / "MANIFEST.json", manifest)
    if not errors:
        write_json(out / "FIGURE_MANIFEST.json", {"rgb_local_only": True, "sha256": render_figures(out, payloads, selection)})
    (out / "REPORT.md").write_text(
        f"# Native PCB tiling geometry\n\n{json.dumps(summary, indent=2)}\n\n"
        f"Index vectors only: {estimate['cpu_exact_index_vector_bytes']/2**30:.3f} GiB. "
        f"Potential three simultaneous vector payloads during unchanged fit: {estimate['fit_features_plus_scorer_copy_plus_index_vector_bytes']/2**30:.3f} GiB. "
        "Arithmetic payload estimates, NOT measured RSS/runtime/VRAM; see resource_estimate.json.\n\n"
        "No resize/pad/GT selection; original 8-connected IDs are reconstructed exactly, not physical-defect counts. "
        "Geometry pass does not establish detector or RGB quality after x4. Tile boundaries limit context. "
        "Raw RGB/GT identity reassembly is NOT an anomaly-map merger. Map overlap, board score, calibration domain, "
        "tile-wise x4, resource feasibility, runner and device/checkpoint smoke remain unfrozen. "
        "This is a separate family from center-crop/full-frame224. Negative gating/full110 B/B-uncertain are unchanged. "
        "Figures contain local-only RGB. No pilot/model/metric execution was performed.\n", encoding="utf-8")
    print(json.dumps(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/external/VisA")
    args = parser.parse_args()
    audit(args.data_root, ROOT / "analysis/pcb_geometry" / safe_component(args.run_id, "run-id"))


if __name__ == "__main__":
    main()
