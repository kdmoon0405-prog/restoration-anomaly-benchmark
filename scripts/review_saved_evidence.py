"""Read-only timing/split/crop audit; no model imports, fitting or inference."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from skimage.measure import label

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.dataset import VisASplitCSV
from sr_anomaly.fusion import split_train_calibration

PROFILE = ROOT / "analysis/profiling_results_demo/hazelnut-ten-20261015"


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def crop_audit(source):
    """Compare defect pixels/components before vs after the unchanged 224 crop."""
    width, height = source.size
    size = (256, int(256 * height / width)) if width <= height else (int(256 * width / height), 256)
    full = np.asarray(source.convert("L").resize(size, Image.Resampling.NEAREST)) > 0
    left, top = (int(round((side - 224) / 2)) for side in size)
    cropped = full[top:top + 224, left:left + 224]
    components = label(full, connectivity=2)
    before = np.bincount(components.ravel())[1:]
    after = np.bincount(components[top:top + 224, left:left + 224].ravel(), minlength=len(before) + 1)[1:]
    total, retained = int(full.sum()), int(cropped.sum())
    return {"resized_size": list(size), "crop_box": [left, top, left + 224, top + 224],
            "defect_pixels_before_crop": total, "defect_pixels_after_crop": retained,
            "lost_defect_pixels": total - retained,
            "lost_defect_fraction": (total - retained) / total if total else None,
            "empty_after_crop": not bool(cropped.any()), "components_before_crop": len(before),
            "components_fully_removed": int(np.sum(after == 0)),
            "components_partially_cut": int(np.sum((after > 0) & (after < before)))}


def timing_audit(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[f"{row['phase']}/{row['variant']}"].append(row)
    statistics = {}
    for key, selected in groups.items():
        stats = {"observations": len(selected), "unique_samples": len({r["sample"] for r in selected}),
                 "repeats": len({r["repeat"] for r in selected})}
        for field in selected[0]:
            if field.endswith("_seconds") and selected[0][field] != "":
                values = [float(row[field]) for row in selected]
                stats[field] = {"mean": float(np.mean(values)), "median": float(np.median(values)),
                                "min": min(values), "max": max(values)}
        statistics[key] = stats
    residuals = []
    for row in rows:
        if row["phase"] == "instrumented":
            child = sum(float(row[key]) for key in ("backbone_embedding_seconds", "feature_detach_cpu_numpy_seconds",
                        "faiss_search_seconds", "score_map_postprocessing_seconds", "detector_glue_seconds"))
            residuals.append(abs(child - float(row["detector_total_seconds"])))
    return statistics, max(residuals, default=0.)


def write_timing_table(stats, output):
    fields = {"preprocessing": ("image_preprocessing_seconds", "tensor_preprocessing_seconds"),
              "restoration": ("sr_seconds",), "backbone_embedding": ("backbone_embedding_seconds",),
              "feature_detach_cpu_numpy": ("feature_detach_cpu_numpy_seconds",), "faiss": ("faiss_search_seconds",),
              "score_map_postprocessing": ("score_map_postprocessing_seconds",), "detector_glue": ("detector_glue_seconds",),
              "detector_parent_not_additive": ("detector_total_seconds",), "end_to_end_parent_not_additive": ("end_to_end_seconds",)}
    rows = []
    for phase, group in stats.items():
        if phase.startswith("warmup/"):
            continue
        for stage, keys in fields.items():
            rows.append({"phase_variant": phase, "stage": stage,
                         "mean_seconds": sum(group[key]["mean"] for key in keys) if all(key in group for key in keys) else None,
                         "unique_images": group["unique_samples"], "repeats": group["repeats"], "observations": group["observations"]})
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def crop_figure(output):
    """Post-hoc structural illustrations, not selected by detector performance."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    data = ROOT / "data/external/VisA"
    samples = VisASplitCSV(data, data / "split_csv/1cls.csv", "test", "pcb2").samples()
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    for row, filename in enumerate(("023.JPG", "042.JPG")):
        item = next(sample for sample in samples if sample.path.name == filename and sample.metadata["label"])
        with Image.open(item.mask_path) as mask:
            audit = crop_audit(mask)
            full_mask = np.asarray(mask.convert("L").resize(audit["resized_size"], Image.Resampling.NEAREST)) > 0
        with Image.open(item.path) as image:
            full = image.convert("RGB").resize(audit["resized_size"], Image.Resampling.BILINEAR)
        box = audit["crop_box"]
        crops = ((full, full_mask), (full.crop(box), full_mask[box[1]:box[3], box[0]:box[2]]))
        for column, (rgb, mask) in enumerate(crops):
            axis = axes[row, column]
            axis.imshow(rgb)
            axis.contour(mask, levels=[.5], colors=["lime"], linewidths=1)
            axis.axis("off")
        axes[row, 0].add_patch(Rectangle(box[:2], 224, 224, fill=False, edgecolor="red", linewidth=1.5))
        axes[row, 0].set_title(f"pcb2 {filename}: full resized GT + red crop box")
        axes[row, 1].set_title(f"224 crop: loss {audit['lost_defect_fraction']:.1%}; whole components lost {audit['components_fully_removed']}")
    fig.suptitle("Structural examples only; green=GT. No model inference or performance-based selection.")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=140)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "EVIDENCE_AUDIT.json").exists():
        raise FileExistsError("Use a fresh output; retain prior audits")
    source_hashes = {}
    for folder in (PROFILE, ROOT / "analysis/map_gating_feasibility/hazelnut-branchb-20261014"):
        for path in sorted(folder.iterdir()):
            if path.is_file():
                source_hashes[path.relative_to(ROOT).as_posix()] = digest(path)
    manifest = json.loads((PROFILE / "INPUT_MANIFEST.json").read_text(encoding="utf-8"))
    for name, expected in manifest["source_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")
    assert digest(PROFILE / "PROTOCOL.json") == manifest["protocol_sha256"]
    with (PROFILE / "timings.csv").open(encoding="utf-8", newline="") as handle:
        stats, nested_residual = timing_audit(list(csv.DictReader(handle)))
    original = json.loads((PROFILE / "summary.json").read_text(encoding="utf-8"))
    for group, fields in original["statistics"].items():
        for field, values in fields.items():
            if isinstance(values, dict):
                assert np.allclose(list(stats[group][field].values()), list(values.values()), rtol=0, atol=1e-12)
            else:
                assert stats[group][field] == values
    share = {variant: stats[f"instrumented/{variant}"]["faiss_search_seconds"]["mean"] /
             stats[f"instrumented/{variant}"]["detector_total_seconds"]["mean"] for variant in ("degraded", "restored")}
    phase = "end_to_end"
    raw = sum(stats[f"{phase}/degraded"][key]["mean"] for key in ("detector_total_seconds", "tensor_preprocessing_seconds"))
    rest = sum(stats[f"{phase}/restored"][key]["mean"] for key in ("detector_total_seconds", "tensor_preprocessing_seconds"))
    sr = stats[f"{phase}/restored"]["sr_seconds"]["mean"]
    simulation = {"scope": "same separate uninstrumented phase; detector includes tensor prep; shared RGB preprocessing excluded",
                  "raw_detector": raw, "restored_detector": rest, "sr": sr, "always_sr": sr + rest,
                  "break_even_p": (sr + rest - raw) / (sr + rest),
                  "rows": [{"p": p, "conditional": raw + p * (sr + rest)} for p in (0, .25, .5, .75, 1)]}
    data = ROOT / "data/external/VisA"
    split_csv = data / "split_csv/1cls.csv"
    train = VisASplitCSV(data, split_csv, "train", "pcb2").samples()
    test = VisASplitCSV(data, split_csv, "test", "pcb2").samples()
    fit_idx, cal_idx = split_train_calibration(len(train), .8, 11)
    partitions = {"fit": [train[i] for i in fit_idx], "calibration": [train[i] for i in cal_idx], "test": test}
    path_sets = {name: {item.relative_path.as_posix() for item in items} for name, items in partitions.items()}
    assert all(len(path_sets[name]) == len(items) for name, items in partitions.items())
    assert not (path_sets["fit"] & path_sets["calibration"] or path_sets["fit"] & path_sets["test"] or path_sets["calibration"] & path_sets["test"])
    assert all(not item.metadata["label"] for item in train)
    byte_hashes = defaultdict(list)
    for name, items in partitions.items():
        for item in items:
            byte_hashes[digest(item.path)].append({"split": name, "sample": item.relative_path.as_posix()})
    duplicates = [items for items in byte_hashes.values() if len(items) > 1]
    crops = []
    for item in test:
        if item.metadata["label"]:
            with Image.open(item.mask_path) as mask:
                row = crop_audit(mask)
            crops.append({"sample": item.relative_path.as_posix(), **row})
    traces, invalid_json = [], []
    def mentions_category(value):
        if isinstance(value, dict):
            return value.get("category") == "pcb2" or any(mentions_category(v) for v in value.values())
        return isinstance(value, list) and any(mentions_category(v) for v in value)
    for directory in (ROOT / "outputs", ROOT / "checkpoints"):
        for path in directory.rglob("*.json"):
            if path.name not in {"results.json", "metadata.json", "split.json"}:
                continue
            try:
                if mentions_category(json.loads(path.read_text(encoding="utf-8"))):
                    traces.append(path.relative_to(ROOT).as_posix())
            except (ValueError, OSError):
                invalid_json.append(path.relative_to(ROOT).as_posix())
    crop_summary = {"anomalous_images": len(crops), "empty_after_crop": sum(r["empty_after_crop"] for r in crops),
                    "images_with_defect_pixels_cut": sum(r["lost_defect_pixels"] > 0 for r in crops),
                    "images_with_complete_component_loss": sum(r["components_fully_removed"] > 0 for r in crops),
                    "fully_removed_components": sum(r["components_fully_removed"] for r in crops),
                    "partially_cut_components": sum(r["components_partially_cut"] for r in crops),
                    "mean_lost_fraction": float(np.mean([r["lost_defect_fraction"] for r in crops])),
                    "max_lost_fraction": max(r["lost_defect_fraction"] for r in crops)}
    split_manifest = {"official_csv_sha256": digest(split_csv), "seed": 11, "ratio": .8,
                      "partition_paths": {name: sorted(paths) for name, paths in path_sets.items()},
                      "composition": {name: {"normal": sum(not item.metadata["label"] for item in items),
                                              "anomaly": sum(item.metadata["label"] for item in items)} for name, items in partitions.items()},
                      "path_overlap": False, "byte_identical_image_groups": duplicates,
                      "content_duplicate_scope": "Exact file SHA256 only, not perceptual/scene-level duplicate detection"}
    audit = {"timing_statistics_from_csv": stats, "detector_child_sum_max_abs_residual": nested_residual,
             "faiss_fraction_of_detector_parent": share, "conditional_cost_simulation": simulation,
             "source_hashes": source_hashes, "frozen_input_hashes_unchanged": len(manifest["source_sha256"]),
             "pcb_crop_summary": crop_summary, "local_pcb2_execution_traces": traces,
             "unreadable_trace_json": invalid_json, "teammate_prior_use": "unconfirmed"}
    for filename, payload in (("EVIDENCE_AUDIT.json", audit), ("PCB_SPLIT_AUDIT.json", split_manifest)):
        (args.output / filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_timing_table(stats, args.output / "TIMING_RECALCULATED.csv")
    crop_figure(args.output / "screenshots/pcb-crop-structural-examples.png")
    with (args.output / "PCB_CROP_AUDIT.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=crops[0])
        writer.writeheader()
        writer.writerows(crops)
    print(json.dumps({"faiss_fraction": share, "nested_residual": nested_residual,
                      "split": split_manifest["composition"], "duplicates": len(duplicates), "crop": crop_summary,
                      "execution_traces": traces, "unreadable_trace_json": invalid_json}, ensure_ascii=False))


if __name__ == "__main__":
    main()
