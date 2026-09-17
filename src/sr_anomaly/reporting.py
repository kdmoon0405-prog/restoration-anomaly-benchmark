from __future__ import annotations

from collections import defaultdict
import csv
from pathlib import Path
from statistics import fmean
from typing import Iterable


GROUP_FIELDS = ["degradation", "severity", "variant", "restoration_model", "anomaly_detector"]
MEAN_FIELDS = ["psnr", "ssim", "lpips", "anomaly_score", "total_ms"]


def aggregate_results(inputs: Iterable[str | Path], output_dir: str | Path) -> tuple[Path, Path]:
    paths = [Path(path) for path in inputs]
    if not paths:
        raise ValueError("At least one results.csv path is required")
    rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"CSV has no header: {path}")
            if fieldnames is None:
                fieldnames = reader.fieldnames
            elif reader.fieldnames != fieldnames:
                raise ValueError(f"CSV schema mismatch: {path}")
            rows.extend(reader)
    if not rows or fieldnames is None:
        raise ValueError("No result rows found")

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    combined_path = destination / "combined_results.csv"
    with combined_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    comparison_path = destination / "comparison_table.csv"
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in GROUP_FIELDS)].append(row)
    summary_fields = [*GROUP_FIELDS, "count", *(f"{field}_mean" for field in MEAN_FIELDS)]
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields)
        writer.writeheader()
        for key, group_rows in sorted(groups.items()):
            summary = dict(zip(GROUP_FIELDS, key))
            summary["count"] = str(len(group_rows))
            for field in MEAN_FIELDS:
                values = [_float(row[field]) for row in group_rows]
                available = [value for value in values if value is not None]
                summary[f"{field}_mean"] = round(fmean(available), 6) if available else ""
            writer.writerow(summary)
    return combined_path, comparison_path


def _float(value: str) -> float | None:
    if value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None

