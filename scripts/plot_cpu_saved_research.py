"""Create numeric figures and selected map cases from a completed CPU saved-map study."""
from pathlib import Path
import argparse
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from sr_anomaly.analysis_io import csv_rows, digest, read_json, write_csv, write_json

STYLE = dict(clean=("Clean", "#666666", "o", ":"),
             bicubic_x4=("Bicubic", "#0072B2", "s", "--"),
             swinir_x4=("SwinIR", "#D55E00", "^", "-"))


def plot_study(directory, artifact_root, figures_output=None):
    directory, artifact_root = Path(directory), Path(artifact_root)
    status = read_json(directory / "status.json")
    if status["status"] != "COMPLETE":
        raise ValueError("Figures require a completed study")
    out = Path(figures_output) if figures_output is not None else directory / "figures"
    out.mkdir(exist_ok=False)
    summary = csv_rows(directory / "spatial_summary.csv")
    effects = csv_rows(directory / "paired_budget_effects.csv")
    operating = csv_rows(directory / "operating_points.csv")
    categories = [r["category"] for r in status["settings"]["runs"]]
    made = []
    with plt.rc_context({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(1, len(categories), figsize=(10, 4), sharey=True, layout="constrained", squeeze=False)
        for ax, category in zip(axes[0], categories, strict=True):
            for variant, (label, color, marker, line) in STYLE.items():
                group = sorted([r for r in summary if r["category"] == category
                    and r["variant"] == variant and r["label"] == "1"], key=lambda r: float(r["area_fraction"]))
                ax.plot([100 * float(r["area_fraction"]) for r in group],
                    [float(r["mean_gt_pixel_recall"]) for r in group],
                    label=label, color=color, marker=marker, linestyle=line)
            ax.set(xscale="log", xlabel="Selected image area (%)", title=f"{category} (anomaly images)")
            ax.set_ylim(0, 1)
            ax.grid(alpha=0.2)
        axes[0, 0].set_ylabel("Mean per-image GT pixel recall")
        axes[0, -1].legend()
        path = out / "inspection_area_recall.png"
        fig.savefig(path, dpi=200)
        plt.close(fig)
        made.append(path)
        fig, axes = plt.subplots(1, len(categories), figsize=(10, 4), sharey=True, layout="constrained", squeeze=False)
        for ax, category in zip(axes[0], categories, strict=True):
            group = sorted([r for r in effects if r["category"] == category
                            and r["metric"] == "gt_pixel_recall"], key=lambda r: float(r["area_fraction"]))
            y = np.array([100 * float(r["mean_delta"]) for r in group])
            low = np.array([100 * float(r["ci95_low"]) for r in group])
            high = np.array([100 * float(r["ci95_high"]) for r in group])
            ax.errorbar([100 * float(r["area_fraction"]) for r in group], y,
                        yerr=np.maximum(0, [y - low, high - y]), color="#0072B2", marker="o", capsize=4)
            ax.axhline(0, color="black", linewidth=0.8)
            ax.set(xscale="log", xlabel="Selected image area (%)",
                   title=f"{category}, n={group[0]['n_anomaly_images']}")
            ax.grid(alpha=0.2)
        axes[0, 0].set_ylabel("SwinIR - Bicubic recall (percentage points)\n95% paired-image bootstrap CI")
        path = out / "paired_inspection_recall.png"
        fig.savefig(path, dpi=200)
        plt.close(fig)
        made.append(path)
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
        fig.suptitle("Hazelnut Branch B | 40 normal and 70 anomalous test images")
        labels = [r["method"].replace("_only", "").replace("mean_0.5_0.5", "mean 0.5").replace("_reference", "") for r in operating]
        for ax, metric, title in zip(axes, ("normal_image_fpr", "anomaly_image_sensitivity"),
                                    ("Normal image false-positive rate", "Anomaly image sensitivity"), strict=True):
            y = np.array([float(r[metric]) for r in operating])
            low = np.array([float(r[metric + "_ci95_low"]) for r in operating])
            high = np.array([float(r[metric + "_ci95_high"]) for r in operating])
            ax.errorbar(range(len(labels)), y, yerr=np.maximum(0, [y - low, high - y]),
                        marker="o", linestyle="none", capsize=4, color="#0072B2")
            ax.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
            ax.set(title=title, ylim=(-0.02, 1.02), ylabel="Rate with exact 95% binomial CI")
            ax.grid(axis="y", alpha=0.2)
        path = out / "normal_calibrated_operating_points.png"
        fig.savefig(path, dpi=200)
        plt.close(fig)
        made.append(path)
        deltas = csv_rows(directory / "per_image_budget_deltas.csv")
        selected = []
        fraction = status["settings"]["qualitative_area_fraction"]
        for spec in status["settings"]["runs"]:
            own = [r for r in deltas if r["category"] == spec["category"] and float(r["area_fraction"]) == fraction]
            worst = min(own, key=lambda r: (float(r["delta_gt_pixel_recall"]), r["sample"]))
            best = min(own, key=lambda r: (-float(r["delta_gt_pixel_recall"]), r["sample"]))
            source = artifact_root / spec["directory"]
            paths = read_json(source / "results.json")["test_paths"]
            with np.load(source / "bicubic_x4_predictions.npz", allow_pickle=False) as z:
                bic, masks = z["maps"], z["masks"]
            with np.load(source / "swinir_x4_predictions.npz", allow_pickle=False) as z:
                swin = z["maps"]
            for role, row in (("lowest", worst), ("highest", best)):
                index = paths.index(row["sample"])
                a, b, mask = bic[index], swin[index], masks[index].astype(bool)
                limits = min(float(a.min()), float(b.min())), max(float(a.max()), float(b.max()))
                k = math.ceil(fraction * mask.size)
                alerts = []
                for values in (a, b):
                    alert = np.zeros(mask.shape, dtype=bool)
                    alert.ravel()[np.argsort(-values.ravel(), kind="stable")[:k]] = True
                    alerts.append(alert)
                fig, axes = plt.subplots(1, 5, figsize=(12, 3.5), layout="constrained")
                axes[0].imshow(mask, cmap="gray", vmin=0, vmax=1)
                image = axes[1].imshow(a, vmin=limits[0], vmax=limits[1], cmap="magma")
                axes[2].imshow(b, vmin=limits[0], vmax=limits[1], cmap="magma")
                for ax, alert in zip(axes[3:], alerts, strict=True):
                    ax.imshow(mask, cmap="gray", vmin=0, vmax=1)
                    ax.imshow(np.ma.masked_where(~alert, alert), cmap="autumn", alpha=0.65, vmin=0, vmax=1)
                for ax, title in zip(axes, ("GT", "Bicubic map", "SwinIR map", "Bicubic top 1%", "SwinIR top 1%"), strict=True):
                    ax.set_title(title)
                    ax.axis("off")
                fig.colorbar(image, ax=axes[1:3], shrink=0.7, label="Stored anomaly score")
                fig.suptitle(f"{row['sample']} | paired recall delta {float(row['delta_gt_pixel_recall']):+.3f}\n"
                             "White = GT; yellow overlay = selected inspection area")
                path = out / f"case-{spec['category']}-{role}.png"
                fig.savefig(path, dpi=180)
                plt.close(fig)
                made.append(path)
                selected.append(dict(row, selection=role, figure=path.name))
            del bic, swin, masks
        write_csv(directory / "selected_spatial_cases.csv", selected)
    write_json(directory / "figure_manifest.json", dict(
        plot_code_sha256=digest(Path(__file__)),
        source_status_sha256=digest(directory / "status.json"),
        uncertainty="paired anomalous-image bootstrap for recall deltas; exact binomial CI for image operating rates",
        cases="Exploratory minimum/maximum per-image delta, lexical ties",
        files={p.name: digest(p) for p in made}))
    return made


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--figures-output", type=Path)
    args = parser.parse_args()
    print(json.dumps([str(p) for p in plot_study(args.run, args.artifact_root, args.figures_output)]))
