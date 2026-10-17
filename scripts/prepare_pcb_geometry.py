"""Audit one fixed PCB full-FOV geometry on CPU; never fit/infer/degrade images."""
from __future__ import annotations

import argparse
from collections import defaultdict
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.dataset import VisASplitCSV, safe_component
from sr_anomaly.fusion import split_train_calibration
from sr_anomaly import pcb_geometry as geometry

REFERENCE = ROOT / "analysis/profiling_results_demo/review-7ee19a9"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def partitions_for(root, prior):
    csv_path = root / "split_csv/1cls.csv"
    if sha(csv_path) != prior["official_csv_sha256"] or prior["seed"] != 11 or prior["ratio"] != .8:
        raise ValueError("Official split/seed/ratio differs from the prior readiness record")
    train = VisASplitCSV(root, csv_path, "train", "pcb2").samples()
    test = VisASplitCSV(root, csv_path, "test", "pcb2").samples()
    if not train or not test or any(item.metadata["label"] for item in train):
        raise ValueError("Nonempty official split and normal-only training required")
    fit, cal = split_train_calibration(len(train), .8, 11)
    groups = {"fit": [train[i] for i in fit], "calibration": [train[i] for i in cal], "test": test}
    seen = set()
    for name, items in groups.items():
        paths = [item.relative_path.as_posix() for item in items]
        if len(paths) != len(set(paths)) or seen.intersection(paths):
            raise ValueError("Repeated/overlapping partition paths")
        if paths != prior["partition_paths"][name]:
            raise ValueError(f"Prior partition paths changed: {name}")
        composition = {"normal": sum(item.metadata["label"] == 0 for item in items),
                       "anomaly": sum(item.metadata["label"] == 1 for item in items)}
        if composition != prior["composition"][name]:
            raise ValueError(f"Partition composition changed: {name}")
        seen.update(paths)
    return groups


def plot_examples(out, root, groups, image_rows, components):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    items = {item.relative_path.as_posix(): item for item in groups["test"] if item.metadata["label"]}
    valid = [row for row in image_rows if row.get("partition") == "test" and row.get("label") == 1
             and not row.get("error") and row.get("source_component_count", 0) > 0]
    losses = sorted((row for row in valid if row["lost_source_components"]),
                    key=lambda row: (-row["lost_source_component_area_pixels"], row["sample"]))
    controls = sorted((row for row in valid if not row["lost_source_components"]), key=lambda row: row["sample"])
    selected = (losses[:2] + controls[:1]) or valid[:3]
    if not selected:
        return []
    fig, axes = plt.subplots(len(selected), 3, figsize=(12, 3.7 * len(selected)), squeeze=False)
    selection = []
    for index, row in enumerate(selected):
        item = items[row["sample"]]
        with Image.open(item.path) as image, Image.open(item.mask_path) as mask:
            original = image.convert("RGB")
            binary = np.asarray(mask) > 0
            resized, target, _ = geometry.resize_full_frame(image, mask)
        axes[index, 0].imshow(original)
        axes[index, 0].contour(binary, levels=[.5], colors=["lime"], linewidths=.7)
        axes[index, 0].set_title(f"{item.path.name}: full source RGB + GT")
        axes[index, 1].imshow(resized)
        if np.asarray(target).any():
            axes[index, 1].contour(np.asarray(target) > 0, levels=[.5], colors=["lime"], linewidths=.7)
        axes[index, 1].set_title(f"224 full FOV: source IDs lost {row['lost_source_components']}/{row['source_component_count']}")
        lost = sorted((c for c in components if c["sample"] == row["sample"] and not c["represented"]),
                      key=lambda c: (-c["source_area_pixels"], c["component_id"]))
        source_component = lost[0] if lost else next(c for c in components if c["sample"] == row["sample"])
        x0, y0, x1, y1 = source_component["source_bbox_xyxy"]
        box = [max(0, x0 - 12), max(0, y0 - 12), min(original.width, x1 + 12), min(original.height, y1 + 12)]
        axes[index, 2].imshow(original.crop(box), interpolation="nearest")
        axes[index, 2].contour(binary[box[1]:box[3], box[0]:box[2]], levels=[.5], colors=["lime"], linewidths=.8)
        axes[index, 2].set_title(f"Source zoom ONLY: ID {source_component['component_id']}, area {source_component['source_area_pixels']} source px")
        axes[index, 0].add_patch(Rectangle((x0, y0), max(1, x1-x0), max(1, y1-y0), fill=False, edgecolor="red", linewidth=1))
        for axis in axes[index]:
            axis.axis("off")
        selection.append({"sample": row["sample"], "illustrated_source_component_id": source_component["component_id"],
                          "selection": "largest total lost source area, lexical ties; then lexical no-loss control; explanatory only"})
    fig.suptitle("Fixed geometry audit, not model inference. Green=GT. Zooms are figures only, never model inputs.")
    fig.tight_layout()
    (out / "figures").mkdir()
    fig.savefig(out / "figures/geometry_examples.png", dpi=140)
    plt.close(fig)
    return selection


def audit(root, out, reference=REFERENCE):
    prior_path = reference / "PCB_SPLIT_AUDIT.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    groups = partitions_for(root, prior)
    old_crop_path = reference / "PCB_CROP_AUDIT.csv"
    with old_crop_path.open(encoding="utf-8", newline="") as handle:
        old_crop = list(csv.DictReader(handle))
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    protocol = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "source_commit": commit,
                "category": "pcb2", "geometry_id": geometry.GEOMETRY_ID, "scope": "one draft geometry audit only; no degradation/fit/inference/performance metric",
                "target_wh": list(geometry.TARGET_SIZE), "image_interpolation": "BILINEAR", "gt_interpolation": "binary >0 then NEAREST",
                "crop": None, "padding": None, "seed": 11, "fit_ratio": .8,
                "official_csv_sha256": prior["official_csv_sha256"],
                "reference_split_sha256": sha(prior_path), "historical_crop_csv_sha256": sha(old_crop_path),
                "code_sha256": {"scripts/prepare_pcb_geometry.py": sha(Path(__file__)),
                                "src/sr_anomaly/pcb_geometry.py": sha(Path(geometry.__file__))},
                "component_tracking": "Label original binary GT with 8-connectivity; resize int32 label IDs by the same Pillow NEAREST; count each original ID's target samples; IDs>0 must equal transformed binary GT",
                "readiness_rule": "BLOCKED_GEOMETRY if no anomalous cases, any input/size/alignment error, nonempty normal GT, empty/full anomaly GT or any original GT component not sampled. Passing is only a presence/alignment guard, never proof of shape/accuracy preservation.",
                "normal_gt_policy": "Official normals have no mask file; implicit all-background. Empty-mask transform is tested synthetically, not inferred from a fabricated file.",
                "pixel_units": "Do not divide target pixel counts by original pixel counts as a retention ratio",
                "figure_selection": "Up to two anomalous images with largest total lost source-component area, lexical path ties; one lexical no-loss control. Within image largest lost source area then ID. Figures only, not population estimates or adaptive model inputs.",
                "versions": {name: importlib.metadata.version(name) for name in ("numpy", "Pillow", "scikit-image")},
                "python": platform.python_version(), "future_x4": "canonical224 -> LR56 -> output224, planned only",
                "teammate_prior_use": "unconfirmed", "no_new_search_or_model_execution": True}
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "PROTOCOL.json", protocol)  # Rules frozen before examining actual image/GT geometry.
    input_rows, image_rows, component_rows, summaries, errors = [], [], [], [], []
    by_size, hashes = {}, defaultdict(list)
    for partition, items in groups.items():
        for item in items:
            sample = item.relative_path.as_posix()
            image_bytes = item.path.read_bytes()
            mask_bytes = item.mask_path.read_bytes() if item.mask_path else None
            image_sha = hashlib.sha256(image_bytes).hexdigest()
            hashes[image_sha].append({"partition": partition, "sample": sample})
            record = {"partition": partition, "sample": sample, "label": item.metadata["label"],
                      "mask": item.mask_path.relative_to(root).as_posix() if item.mask_path else "",
                      "image_sha256": image_sha, "mask_sha256": hashlib.sha256(mask_bytes).hexdigest() if mask_bytes else ""}
            row = {"sample": sample, "partition": partition, "label": item.metadata["label"], "error": ""}
            try:
                with Image.open(BytesIO(image_bytes)) as image:
                    mask = Image.open(BytesIO(mask_bytes)) if mask_bytes else None
                    try:
                        rgb, target, metadata = geometry.resize_full_frame(image, mask)
                        assert rgb.size == geometry.TARGET_SIZE
                        key = f"{image.width}x{image.height}"
                        by_size[key] = metadata
                        record.update({"source_width": image.width, "source_height": image.height, "geometry_key": key})
                        if mask is not None:
                            result, components = geometry.component_sampling_audit(mask, target)
                            summaries.append(result)
                            row.update({k: v for k, v in result.items() if k not in {"component_reference", "pixel_count_units"}})
                            component_rows.extend({"sample": sample, **component} for component in components)
                    finally:
                        if mask is not None:
                            mask.close()
            except (OSError, ValueError, AssertionError) as error:
                row["error"] = str(error)
                errors.append({"sample": sample, "error": str(error)})
            input_rows.append(record)
            image_rows.append(row)
    fields = list(dict.fromkeys(key for row in input_rows for key in row))
    write_csv(out / "INPUTS.csv", input_rows, fields)
    write_csv(out / "per_image_geometry.csv", image_rows, list(dict.fromkeys(key for row in image_rows for key in row)))
    write_csv(out / "components.csv", component_rows, ["sample", "component_id", "source_area_pixels", "source_bbox_xyxy", "target_positive_samples", "represented"])
    duplicates = [rows for rows in hashes.values() if len(rows) > 1]
    manifest = {"protocol_sha256": sha(out / "PROTOCOL.json"), "inputs_csv": "INPUTS.csv", "inputs_csv_sha256": sha(out / "INPUTS.csv"),
                "input_rows": len(input_rows), "input_path_base": "VisA data root; paths portable relative to this root",
                "partitions": prior["composition"], "partition_paths_exactly_match_reference": True,
                "partition_path_overlap": False, "byte_identical_groups": duplicates,
                "duplicate_scope": "file SHA256 only, not scene/perceptual duplicates", "geometry_by_source_size": by_size,
                "pcb_bank": {"status": "not_created_for_this_protocol", "reuse_hazelnut_bank": False},
                "pcb_calibration": {"status": "not_created_for_this_protocol", "reuse_hazelnut_thresholds": False},
                "runner_integration": "not yet connected to a model runner; geometry API/manifest only", "teammate_prior_use": "unconfirmed"}
    write_json(out / "MANIFEST.json", manifest)
    lost = [row for row in component_rows if not row["represented"]]
    summary = {"status": geometry.readiness_status(summaries, dimension_errors=len(errors)),
               "geometry_id": geometry.GEOMETRY_ID, "full_fov_domain_included": True,
               "all_input_images_geometry_checked": len(image_rows), "anomalous_gt_checked": len(summaries),
               "input_or_alignment_errors": errors, "empty_target_anomaly_images": sum(row["target_empty"] for row in summaries),
               "images_with_lost_source_components": sum(row["lost_source_components"] > 0 for row in summaries),
               "source_components": len(component_rows), "represented_source_components": len(component_rows) - len(lost),
               "lost_source_components": len(lost), "lost_component_source_area_min": min((r["source_area_pixels"] for r in lost), default=None),
               "lost_component_source_area_max": max((r["source_area_pixels"] for r in lost), default=None),
               "historical_crop_reference": {"basis": "same 335x256 resized GT before/after 224 center crop; not original-ID aliasing audit",
                                            "images_with_pixels_cut": sum(int(r["lost_defect_pixels"]) > 0 for r in old_crop),
                                            "images_with_components_lost": sum(int(r["components_fully_removed"]) > 0 for r in old_crop),
                                            "components_lost": sum(int(r["components_fully_removed"]) for r in old_crop)},
               "scientific_inference_or_metric_performed": False, "normal_mask_policy": protocol["normal_gt_policy"],
               "bank_created": False, "calibration_created": False, "independent_validation_claim": False}
    write_json(out / "summary.json", summary)
    selection = plot_examples(out, root, groups, image_rows, component_rows)
    write_json(out / "selected_examples.json", selection)
    report = f"""# PCB full-FOV 224 draft geometry

Status: **{summary['status']}**. One pre-fixed draft, not a method search. No model, degradation, fitting, calibration or anomaly metric was executed.

Official split: {prior['composition']}. Exact reference paths and CSV SHA matched; no partition overlap. Byte-identical groups: {len(duplicates)} (not a perceptual duplicate check). INPUTS.csv stores all {len(input_rows)} portable paths, labels, source sizes and input/mask hashes; MANIFEST.json references its hash and coordinate metadata. PCB bank/calibration for this geometry do not exist. Teammate past use is unconfirmed.

## Geometry and actual checks

`{geometry.GEOMETRY_ID}`: entire source field resized directly to 224x224, RGB bilinear, binary GT nearest. No crop/padding. Non-square images are anisotropically transformed. Metadata records edge and pixel-center affine/inverse coordinates. Future x4 is 224->56->224, NOT executed here.

- Input image transforms checked: {len(image_rows)}; anomalous GT checked: {len(summaries)}.
- Input/size/alignment errors: {len(errors)}.
- Empty target anomaly masks: {summary['empty_target_anomaly_images']}.
- Original-resolution 8-connected GT components: {len(component_rows)}; represented {len(component_rows)-len(lost)}, lost {len(lost)} across {summary['images_with_lost_source_components']} images.
- Lost component original areas: min {summary['lost_component_source_area_min']}, max {summary['lost_component_source_area_max']} source pixels. No arbitrary small-defect cutoff was used.

Original GT IDs are resized with the SAME nearest sampler; IDs>0 must exactly match transformed binary GT. These are connected regions in annotation, not physical defect counts. Target connected-component counts alone are not an ID survival check because regions can merge/split. Source areas and target sample counts have different units; no cross-resolution pixel-count retention ratio is reported. Presence does not prove shape/fidelity preservation.

Historical crop audit has {summary['historical_crop_reference']['images_with_pixels_cut']} images losing GT pixels and {summary['historical_crop_reference']['components_lost']} resized-GT components lost across {summary['historical_crop_reference']['images_with_components_lost']} images. Its reference is the resized 335x256 raster, while this audit references ORIGINAL component IDs. These numbers are NOT a before/after improvement comparison. Old CSV and scientific results are unchanged.

## Boundary

Full FOV is not preservation of every small annotation. The frozen rule blocks any original component disappearing, any empty/full anomalous mask or alignment error. This is a structural guard, not an anomaly-performance threshold. If blocked, no pilot is authorized: describe higher-resolution full-FOV or coverage-defined tiling as future options only; do not search resolutions, drop cases, dilate GT or change sampling to force a pass. If the guard passes, a separately frozen VisA runner/bank/calibration/checkpoint/hardware plan is still required before an actual pilot. Capsule/negative gates/full110 B/B-uncertain stay unchanged.

Figures are local-only under figures/. The selection rule was stored before audit: two maximum lost-source-area examples and one lexical no-loss control, with lexical/ID ties. Green contours are GT; source zooms are explanatory only, not adaptive model inputs. They are not population estimates.

Reproduce CPU audit from repository root with a NEW run-id:

```powershell
.venv\\Scripts\\python scripts/prepare_pcb_geometry.py --run-id pcb2-full-frame224-replay
.venv\\Scripts\\python -m pytest -q tests/test_pcb_geometry.py
```

Existing output is never overwritten. Protocol/input/source hashes are preserved. No alternative geometry or GPU command is generated automatically.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/external/VisA")
    args = parser.parse_args()
    audit(args.data_root, ROOT / "analysis/pcb_geometry" / safe_component(args.run_id, "run-id"))


if __name__ == "__main__":
    main()
