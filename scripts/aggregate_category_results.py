"""Aggregate stored category artifacts into paper-ready CSV and Markdown tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = (
    "category", "train_count", "test_count",
    "bicubic_psnr", "bicubic_ssim", "swinir_psnr", "swinir_ssim", "delta_psnr", "delta_ssim",
    "bicubic_image_auroc", "bicubic_pixel_auroc", "bicubic_au_pro",
    "swinir_image_auroc", "swinir_pixel_auroc", "swinir_au_pro",
    "delta_image_auroc", "delta_pixel_auroc", "delta_au_pro",
    "localization_regression_count", "localization_regression_rate",
    "suppression_count", "suppression_rate", "geometry_candidate_count", "geometry_candidate_rate",
)


def _json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Required artifact not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required artifact not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    name_field = "method" if rows and "method" in rows[0] else "variant"
    if not rows or name_field not in rows[0]:
        raise ValueError(f"summary.csv requires a method or variant column: {path}")
    by_name = {row[name_field]: row for row in rows}
    if len(by_name) != len(rows):
        raise ValueError(f"Duplicate methods/variants in summary.csv: {path}")
    return by_name


def _value(row: dict, key: str, cast=float):
    value = row.get(key)
    if value is None or value == "":
        return None
    return cast(value)


def extract_category(run_dir: Path, cross_summary_path: Path) -> dict:
    run_dir = Path(run_dir)
    result = _json(run_dir / "results.json")
    summary = _summary(run_dir / "summary.csv")
    cross = _json(Path(cross_summary_path))
    category = result.get("model_spec", {}).get("category")
    if not category or category != cross.get("category"):
        raise ValueError("Run and cross-category summary category mismatch")
    if not {"bicubic_x4", "swinir_x4"} <= set(summary):
        raise ValueError("summary.csv requires bicubic_x4 and swinir_x4 rows")
    bic, swin = summary["bicubic_x4"], summary["swinir_x4"]
    if any(bic.get(key) != swin.get(key) for key in ("train_count", "test_count")):
        raise ValueError("Bicubic and SwinIR summary counts do not match")
    delta = result.get("comparison_vs_bicubic_x4", {})
    required_deltas = {"delta_psnr", "delta_ssim", "delta_image_auroc", "delta_pixel_auroc", "delta_au_pro"}
    if not required_deltas <= set(delta):
        raise ValueError("results.json is missing stored Bicubic comparison deltas")
    return {
        "category": category,
        "train_count": _value(bic, "train_count", int),
        "test_count": _value(bic, "test_count", int),
        "bicubic_psnr": _value(bic, "mean_psnr"),
        "bicubic_ssim": _value(bic, "mean_ssim"),
        "swinir_psnr": _value(swin, "mean_psnr"),
        "swinir_ssim": _value(swin, "mean_ssim"),
        "delta_psnr": delta["delta_psnr"],
        "delta_ssim": delta["delta_ssim"],
        "bicubic_image_auroc": _value(bic, "image_auroc"),
        "bicubic_pixel_auroc": _value(bic, "pixel_auroc"),
        "bicubic_au_pro": _value(bic, "au_pro"),
        "swinir_image_auroc": _value(swin, "image_auroc"),
        "swinir_pixel_auroc": _value(swin, "pixel_auroc"),
        "swinir_au_pro": _value(swin, "au_pro"),
        "delta_image_auroc": delta["delta_image_auroc"],
        "delta_pixel_auroc": delta["delta_pixel_auroc"],
        "delta_au_pro": delta["delta_au_pro"],
        **{key: cross[key] for key in (
            "localization_regression_count", "localization_regression_rate",
            "suppression_count", "suppression_rate", "geometry_candidate_count", "geometry_candidate_rate",
        )},
    }


def _format(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _table(rows: list[dict], columns: tuple[str, ...]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(_format(row[column]) for column in columns) + " |" for row in rows]
    return "\n".join((header, separator, *body))


def write_report(rows: list[dict], output: Path) -> None:
    if not rows:
        raise ValueError("At least one complete category entry is required")
    if len({row["category"] for row in rows}) != len(rows):
        raise ValueError("Duplicate categories are not allowed")
    rows = sorted(rows, key=lambda row: row["category"])
    output.mkdir(parents=True, exist_ok=True)
    with (output / "category_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    overview = ("category", "train_count", "test_count")
    quality = ("category", "bicubic_psnr", "swinir_psnr", "delta_psnr",
               "bicubic_ssim", "swinir_ssim", "delta_ssim")
    detection = ("category", "bicubic_image_auroc", "swinir_image_auroc", "delta_image_auroc",
                 "bicubic_pixel_auroc", "swinir_pixel_auroc", "delta_pixel_auroc",
                 "bicubic_au_pro", "swinir_au_pro", "delta_au_pro")
    taxonomy = ("category", "localization_regression_count", "localization_regression_rate",
                "suppression_count", "suppression_rate", "geometry_candidate_count", "geometry_candidate_rate")
    markdown = "\n\n".join((
        "# Category result summary",
        _table(rows, overview),
        "## Image quality\n\n" + _table(rows, quality),
        "## Detection\n\n" + _table(rows, detection),
        "## Regression taxonomy\n\n" + _table(rows, taxonomy),
        "Only categories supplied with both completed run artifacts and a cross-category summary are included.",
    )) + "\n"
    (output / "category_summary.md").write_text(markdown, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", nargs=2, action="append", required=True,
                        metavar=("RUN_DIR", "CROSS_CATEGORY_SUMMARY"))
    parser.add_argument("--output", type=Path, default=Path("analysis/reporting"))
    args = parser.parse_args()
    rows = [extract_category(Path(run), Path(summary)) for run, summary in args.entry]
    write_report(rows, args.output)
    print(json.dumps({"categories": [row["category"] for row in rows], "output": str(args.output)}))


if __name__ == "__main__":
    main()
