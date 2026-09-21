"""Render nine preselected Hazelnut cases using saved PatchCore maps.

Only the SwinIR RGB panel is reconstructed; no PatchCore fit or inference runs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter

import matplotlib
import numpy as np

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_hazelnut_failures import _load_npz, _render_cases


# Chosen before rendering, from the existing Branch A per-defect analysis.
CASES = {
    "geometry": (("crack/013.png", "geometry_candidate"),
                 ("crack/015.png", "geometry_candidate"),
                 ("print/005.png", "geometry_candidate")),
    "suppression": (("crack/001.png", "suppression"),
                    ("crack/017.png", "suppression"),
                    ("hole/014.png", "suppression")),
    "controls": (("crack/006.png", "improvement_or_tie"),
                 ("cut/003.png", "improvement_or_tie"),
                 ("hole/006.png", "improvement_or_tie")),
}

FIELDS = ("sample", "defect_type", "regression_type", "delta_per_image_aupro",
          "delta_per_image_pixel_auroc", "delta_roi_bg_gap")

OBSERVATIONS = {
    "crack/013.png": "The SwinIR map has a brighter lower crack response, while the upper thin GT branch remains diffuse; AU-PRO falls despite a larger ROI-background gap.",
    "crack/015.png": "Both maps emphasize the thick right-hand defect. The thin lower-left GT tail remains weak in both, and SwinIR AU-PRO is lower even as Pixel AUROC rises.",
    "print/005.png": "Both maps peak near the top print defect. The SwinIR peak looks more compact, but its AU-PRO and Pixel AUROC are slightly lower.",
    "crack/001.png": "The right-hand defect hotspot is less bright in the SwinIR map on the shared scale; the gap and localization metrics both fall.",
    "crack/017.png": "The two maps look similar at this display scale. The gap change is very small, so the image does not support a strong visual mechanism claim.",
    "hole/014.png": "The SwinIR hotspot at the right-hand hole is weaker on the shared scale. The thin GT extension is weak in both maps.",
    "crack/006.png": "The lower-right defect response is brighter in the SwinIR map; the saved AU-PRO improves.",
    "cut/003.png": "The narrow central cut is more distinct relative to surrounding response in the SwinIR map; AU-PRO and Pixel AUROC improve.",
    "hole/006.png": "Both maps retain the small hole hotspot. AU-PRO improves even though the average ROI-background gap falls, showing that gap direction alone does not track localization here.",
}


def select_cases(rows: list[dict[str, str]], test_paths: list[str], labels: np.ndarray) -> dict[str, list[dict]]:
    by_sample = {row["sample"]: row for row in rows}
    if len(by_sample) != len(rows):
        raise ValueError("Duplicate samples in per-defect analysis")
    path_index = {path: index for index, path in enumerate(test_paths)}
    groups: dict[str, list[dict]] = {}
    for group, cases in CASES.items():
        groups[group] = []
        for suffix, expected_type in cases:
            sample = f"hazelnut/test/{suffix}"
            if sample not in by_sample or sample not in path_index:
                raise ValueError(f"Preselected sample missing from saved analysis/run: {sample}")
            row = dict(by_sample[sample])
            index = path_index[sample]
            if int(row["index"]) != index or int(labels[index]) != 1 or row["regression_type"] != expected_type:
                raise ValueError(f"Preselected case metadata mismatch: {sample}")
            row["index"] = index
            for field in FIELDS[3:]:
                row[field] = float(row[field])
            groups[group].append(row)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "outputs" / "legacy-patchcore" / "hazelnut-full391-test110-repro")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints" / "swinir" / "002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth")
    parser.add_argument("--analysis-csv", type=Path, default=ROOT / "analysis" / "hazelnut" / "hazelnut_per_defect.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis" / "hazelnut" / "qualitative_cases")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    data_root = args.data_root.resolve()
    checkpoint = args.checkpoint.resolve()
    output_dir = args.output_dir.resolve()
    result = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    test_paths = list(result["test_paths"])
    bic = _load_npz(run_dir / "bicubic_x4_predictions.npz")
    swin = _load_npz(run_dir / "swinir_x4_predictions.npz")
    if len(test_paths) != len(bic["labels"]) or not np.array_equal(bic["labels"], swin["labels"]) or not np.array_equal(bic["masks"], swin["masks"]):
        raise ValueError("Saved predictions/test paths are not paired")
    with args.analysis_csv.open(encoding="utf-8", newline="") as handle:
        groups = select_cases(list(csv.DictReader(handle)), test_paths, bic["labels"])
    for selected in groups.values():
        for row in selected:
            if not (data_root / row["sample"]).is_file():
                raise FileNotFoundError(data_root / row["sample"])
    if not checkpoint.is_file():
        raise FileNotFoundError(f"SwinIR RGB cannot be reconstructed without checkpoint: {checkpoint}")
    with checkpoint.open("rb") as handle:
        checkpoint_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    if checkpoint_hash != result["restoration"]["checkpoint_sha256"]:
        raise ValueError("SwinIR checkpoint hash differs from the saved prediction run")

    output_dir.mkdir(parents=True, exist_ok=True)
    start = perf_counter()
    _render_cases([], run_dir, data_root, output_dir, 1, checkpoint, selected_groups=groups)
    elapsed = perf_counter() - start
    with (output_dir / "selected_cases.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("group", *FIELDS))
        writer.writeheader()
        for group, selected in groups.items():
            writer.writerows({"group": group, **{field: row[field] for field in FIELDS}} for row in selected)

    lines = [
        "# Preselected Hazelnut qualitative cases",
        "",
        "Branch A saved anomaly maps/scores and GT masks; only the SwinIR RGB panel was reconstructed from the fixed x4 checkpoint for these nine images. No PatchCore fit/inference was rerun.",
        "",
        "The nine cases were fixed before rendering. Taxonomy and map differences are descriptive, not proof of feature suppression or geometric causality. Each pair of anomaly maps uses a shared color scale within its figure.",
        "All metric deltas are SwinIR minus Bicubic. The reconstructed RGB panel uses the checkpoint hash recorded in the source run.",
        "",
        "| Group | Sample | ΔAU-PRO@0.3 | ΔPixel AUROC | ΔROI-bg gap |",
        "|---|---|---:|---:|---:|",
    ]
    for group, selected in groups.items():
        for row in selected:
            lines.append(f"| {group} | {row['sample']} | {row['delta_per_image_aupro']:+.6f} | "
                         f"{row['delta_per_image_pixel_auroc']:+.6f} | {row['delta_roi_bg_gap']:+.6f} |")
    lines.extend(["", "## Figure observations", ""])
    for group, selected in groups.items():
        for rank, row in enumerate(selected, 1):
            suffix = row["sample"].split("test/", 1)[1]
            filename = f"{rank:02d}_{Path(row['sample']).with_suffix('').as_posix().replace('/', '__')}.png"
            lines.append(f"- [{row['sample']}]({group}/{filename}): {OBSERVATIONS[suffix]}")
    lines.extend(["", f"Rendering time: {elapsed:.1f} seconds on this machine.", ""])
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Rendered 9 cases in {elapsed:.1f}s: {output_dir}")


if __name__ == "__main__":
    main()
