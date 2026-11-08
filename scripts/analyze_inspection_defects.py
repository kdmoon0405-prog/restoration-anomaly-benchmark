"""Exploratory defect-type summaries from the already computed inspection-budget deltas."""
from collections import defaultdict
from pathlib import Path
import argparse
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import csv_rows, digest, new_output, read_json, write_csv, write_json
from sr_anomaly.analysis_statistics import paired_bootstrap_mean_delta


def summarize(run, output):
    run = Path(run)
    status = read_json(run / "status.json")
    if status["status"] != "COMPLETE":
        raise ValueError("Inspection analysis is incomplete")
    source = run / "per_image_budget_deltas.csv"
    rows = csv_rows(source)
    keys = [(r["category"], r["sample"], r["area_fraction"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate image/budget delta")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["category"], row["defect_type"], float(row["area_fraction"])].append(
            float(row["delta_gt_pixel_recall"]))
    summary = []
    for (category, defect, fraction), values in sorted(grouped.items()):
        values = np.array(values)
        if not np.isfinite(values).all() or (np.abs(values) > 1).any():
            raise ValueError("Invalid paired recall delta")
        boot = paired_bootstrap_mean_delta(values, status["settings"]["bootstrap_repeats"],
                                          np.random.default_rng(status["settings"]["bootstrap_seed"]))
        summary.append(dict(category=category, defect_type=defect, area_fraction=fraction,
            n_anomaly_images=boot["n"], mean_delta_gt_pixel_recall=boot["estimate"],
            ci95_low=boot["ci95"][0], ci95_high=boot["ci95"][1],
            decreases=int((values < 0).sum()), ties=int((values == 0).sum()), increases=int((values > 0).sum())))
    out = new_output(Path(output), [run])
    write_csv(out / "defect_budget_effects.csv", summary)
    write_json(out / "analysis_manifest.json", dict(status="COMPLETE",
        scope="post-hoc exploratory subtype analysis; pointwise image bootstrap intervals",
        source_sha256=digest(source), settings=status["settings"],
        code_sha256=digest(Path(__file__)), result_sha256=digest(out / "defect_budget_effects.csv")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summarize(args.run, args.output)
