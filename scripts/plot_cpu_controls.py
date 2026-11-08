"""Plot actual CPU-control results with seed and image uncertainty kept distinct."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import csv_rows, digest, read_json, write_json


def plot(directory):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    directory = Path(directory)
    manifest = read_json(directory / "analysis_manifest.json")
    for name, sha in manifest["tables"].items():
        if digest(directory / name) != sha:
            raise ValueError("CPU analysis table changed")
    summary = csv_rows(directory / "control_summary.csv")
    image_means = csv_rows(directory / "image_mean_effects.csv")
    quality = {(r["category"], r["sample"], r["variant"]): r
               for r in csv_rows(directory / "quality_unique.csv")}
    categories = sorted({r["category"] for r in summary})
    variants = ("clean", "bicubic_x4", "unsharp_x4")
    if any(r["variant"] == "swinir_x4" for r in summary):
        variants += ("swinir_x4",)
    candidate = manifest["comparison"].split(" minus ")[0]
    candidate_label = "SwinIR" if candidate == "swinir_x4" else "Unsharp"
    out = directory / "figures"
    out.mkdir()
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, len(categories), figsize=(10, 4), sharey=True, layout="constrained", squeeze=False)
    for ax, category in zip(axes[0], categories, strict=True):
        seeds = sorted({int(r["seed"]) for r in summary if r["category"] == category})
        for i, seed in enumerate(seeds):
            own = {r["variant"]: r for r in summary if r["category"] == category and int(r["seed"]) == seed}
            ax.plot(np.arange(len(variants)) + (i - 1) * 0.035, [float(own[v]["au_pro"]) for v in variants],
                    marker=("o", "s", "^")[i], label=f"seed {seed}")
        ax.set_xticks(range(len(variants)), [v.replace("_x4", " x4").replace("_", " ") for v in variants])
        ax.set_title(category)
        ax.set_ylim(0, 1)
        ax.grid(axis="y", alpha=0.2)
    axes[0, 0].set_ylabel("Dataset pooled AU-PRO@0.3")
    axes[0, -1].legend()
    first = out / "pooled_aupro_by_seed.png"
    fig.savefig(first, dpi=200)
    plt.close(fig)

    fig, axes = plt.subplots(1, len(categories), figsize=(10, 4), layout="constrained", squeeze=False)
    associations = csv_rows(directory / "quality_association.csv")
    for ax, category in zip(axes[0], categories, strict=True):
        own = [r for r in image_means if r["category"] == category]
        x = [float(quality[category, r["sample"], candidate]["psnr"])
             - float(quality[category, r["sample"], "bicubic_x4"]["psnr"]) for r in own]
        y = [float(r["mean_delta_per_image_aupro"]) for r in own]
        ax.scatter(x, y, alpha=0.65, s=22, color="#0072B2")
        rho = next(r["spearman_rho"] for r in associations
                   if r["category"] == category and r["quality_metric"] == "psnr")
        label = f"{float(rho):+.2f}" if rho != "" else "N/A"
        ax.set_title(f"{category}, n={len(own)}, Spearman rho={label}")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.axvline(0, color="gray", linewidth=0.8)
        ax.set_xlabel(candidate_label + " minus Bicubic PSNR (dB)")
        ax.grid(alpha=0.2)
    axes[0, 0].set_ylabel("Mean across 3 fixed seeds\nper-image AU-PRO delta")
    second = out / "quality_localization_association.png"
    fig.savefig(second, dpi=200)
    plt.close(fig)
    write_json(directory / "figure_manifest.json", dict(
        source_analysis_sha256=digest(directory / "analysis_manifest.json"),
        plot_source_sha256=digest(Path(__file__)),
        scope="three fixed bank fits; each anomaly image appears once in the association plot",
        files={p.name: digest(p) for p in (first, second)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    plot(parser.parse_args().run)
