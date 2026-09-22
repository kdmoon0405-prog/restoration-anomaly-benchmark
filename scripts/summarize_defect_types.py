"""Summarize frozen cross-category per-anomaly rows by defect type."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median


FIELDS = (
    "defect_type", "n", "localization_regression_count", "localization_regression_rate",
    "suppression_count", "suppression_rate", "geometry_candidate_count",
    "geometry_candidate_rate", "mean_delta_per_image_aupro",
    "median_delta_per_image_aupro", "mean_delta_per_image_pixel_auroc",
    "mean_delta_roi_bg_gap",
)


def summarize(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        source = list(csv.DictReader(handle))
    required = {
        "defect_type", "regression_type", "delta_per_image_aupro",
        "delta_per_image_pixel_auroc", "delta_roi_bg_gap",
    }
    if not source or not required <= set(source[0]):
        raise ValueError(f"per_anomaly.csv is empty or missing fields: {sorted(required)}")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in source:
        delta = float(row["delta_per_image_aupro"])
        expected = "improvement_or_tie" if delta >= 0 else row["regression_type"]
        if expected not in {"improvement_or_tie", "suppression", "geometry_candidate"}:
            raise ValueError(f"Invalid frozen regression type: {row['regression_type']}")
        if (delta >= 0) != (row["regression_type"] == "improvement_or_tie"):
            raise ValueError("regression_type disagrees with the frozen zero-cutoff taxonomy")
        grouped[row["defect_type"]].append(row)

    output = []
    for defect_type in sorted(grouped):
        rows = grouped[defect_type]
        n = len(rows)
        regression = sum(float(row["delta_per_image_aupro"]) < 0 for row in rows)
        suppression = sum(row["regression_type"] == "suppression" for row in rows)
        geometry = sum(row["regression_type"] == "geometry_candidate" for row in rows)
        output.append({
            "defect_type": defect_type,
            "n": n,
            "localization_regression_count": regression,
            "localization_regression_rate": regression / n,
            "suppression_count": suppression,
            "suppression_rate": suppression / n,
            "geometry_candidate_count": geometry,
            "geometry_candidate_rate": geometry / n,
            "mean_delta_per_image_aupro": fmean(float(row["delta_per_image_aupro"]) for row in rows),
            "median_delta_per_image_aupro": median(float(row["delta_per_image_aupro"]) for row in rows),
            "mean_delta_per_image_pixel_auroc": fmean(
                float(row["delta_per_image_pixel_auroc"]) for row in rows
            ),
            "mean_delta_roi_bg_gap": fmean(float(row["delta_roi_bg_gap"]) for row in rows),
        })
    return output


def write_outputs(rows: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "defect_type_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Screw defect-type descriptive summary", "",
        "Saved per-anomaly predictions only. Rates and deltas are descriptive within Screw; they do not establish that a defect type is generally vulnerable to SR.", "",
        "| Defect type | N | Regression | Suppression | Geometry | Mean ΔAU-PRO | Median ΔAU-PRO | Mean ΔPixel AUROC | Mean ΔROI-bg gap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['defect_type']} | {row['n']} | "
            f"{row['localization_regression_count']} ({row['localization_regression_rate']:.1%}) | "
            f"{row['suppression_count']} ({row['suppression_rate']:.1%}) | "
            f"{row['geometry_candidate_count']} ({row['geometry_candidate_rate']:.1%}) | "
            f"{row['mean_delta_per_image_aupro']:+.6f} | {row['median_delta_per_image_aupro']:+.6f} | "
            f"{row['mean_delta_per_image_pixel_auroc']:+.6f} | {row['mean_delta_roi_bg_gap']:+.6f} |"
        )
    (output_dir / "defect_type_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = summarize(args.input)
    write_outputs(rows, args.output_dir)
    print(f"Wrote {len(rows)} defect types to {args.output_dir}")


if __name__ == "__main__":
    main()
