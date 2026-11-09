"""Plot saved operating points and degradation-specific localization deltas."""
from pathlib import Path
import argparse
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import csv_rows, digest, read_json, write_json


def plot(directory):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    directory = Path(directory)
    manifest = read_json(directory / "analysis_manifest.json")
    for name, sha in manifest["tables"].items():
        if digest(directory / name) != sha:
            raise ValueError("Analysis table changed")
    out = directory / "figures"
    out.mkdir()
    points = csv_rows(directory / "pcb_operating_points.csv")
    rows = [r for r in csv_rows(directory / "new_master_conditions.csv")
            if r["study_family"] == "realistic_lr_degradation_v1"]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), layout="constrained")
    labels = [r["variant"] for r in points]
    for ax, key, caption in zip(axes, ("fn", "fp"), ("Missed defect boards / 100", "False alarms / 100 normal boards")):
        values = [int(r[key]) for r in points]
        ax.bar(labels, values, color=("#777777", "#0072B2", "#D55E00"))
        for i, value in enumerate(values):
            ax.text(i, value + 0.8, str(value), ha="center")
        ax.set_ylim(0, max(values) * 1.2 + 3)
        ax.set_ylabel(caption)
    fig.suptitle("PCB frozen normal-calibrated operating points | 200 test boards")
    first = out / "pcb_operating_points.png"
    fig.savefig(first, dpi=180)
    plt.close(fig)
    conditions = ("none", "noise_s5", "noise_s15", "blur_s0.8", "blur_s1.6", "jpeg_q90", "jpeg_q50")
    methods = ("swinir_x4", "realesrnet_x4plus", "realesrgan_x4plus")
    matrices = []
    for category in ("hazelnut", "screw"):
        cells = {(r["variant"].split("/")[0], r["variant"].split("/")[1]): float(r["au_pro"])
                 for r in rows if r["category"] == category}
        matrices.append(np.array([[cells[c, m] - cells[c, "bicubic_x4"] for m in methods] for c in conditions]))
    limit = max(float(np.abs(a).max()) for a in matrices)
    fig, axes = plt.subplots(1, 2, figsize=(10, 6), layout="constrained")
    for ax, category, values in zip(axes, ("hazelnut", "screw"), matrices):
        image = ax.imshow(values, cmap="RdBu", vmin=-limit, vmax=limit, aspect="auto")
        for i in range(len(conditions)):
            for j in range(len(methods)):
                ax.text(j, i, f"{values[i, j]:+.4f}", ha="center", va="center",
                        color="white" if abs(values[i, j]) > limit * .6 else "black")
        ax.set_xticks(range(3), ("SwinIR", "RealESRNet", "RealESRGAN"))
        ax.set_yticks(range(len(conditions)), conditions)
        ax.set_title(category)
    fig.suptitle("Pooled AU-PRO@0.3 delta vs same-condition Bicubic | one fit per category")
    fig.colorbar(image, ax=list(axes), label="Pooled AU-PRO delta", shrink=.8)
    second = out / "degradation_localization_deltas.png"
    fig.savefig(second, dpi=180)
    plt.close(fig)
    write_json(directory / "figure_manifest.json", dict(analysis_sha256=digest(directory / "analysis_manifest.json"),
        plot_source_sha256=digest(Path(__file__)), files={p.name: digest(p) for p in (first, second)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    plot(parser.parse_args().analysis)
