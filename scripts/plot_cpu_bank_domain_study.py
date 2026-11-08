"""Plot pooled bank/query results and distinct conditional image-level effects."""
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
    rows = csv_rows(directory / "matrix_summary.csv")
    effects = csv_rows(directory / "seed_summary.csv")
    categories = sorted({row["category"] for row in rows})
    banks = ("clean", "bicubic_matched", "swinir_restored")
    if any(r["bank_domain"] == "balanced_mixed" for r in rows):
        banks += ("balanced_mixed",)
    queries = ("bicubic_x4", "swinir_x4")
    out = directory / "figures"
    out.mkdir()
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, len(categories), figsize=(10, 5), layout="constrained", squeeze=False)
    for ax, category in zip(axes[0], categories, strict=True):
        values = [[np.mean([float(r["pooled_aupro"]) for r in rows
                   if (r["category"], r["bank_domain"], r["query_domain"]) == (category, bank, query)])
                   for query in queries] for bank in banks]
        image = ax.imshow(values, vmin=0, vmax=1, cmap="viridis", aspect="auto")
        for i, bank in enumerate(banks):
            for j, query in enumerate(queries):
                seeds = [float(r["pooled_aupro"]) for r in rows
                         if (r["category"], r["bank_domain"], r["query_domain"]) == (category, bank, query)]
                ax.text(j, i, f"{np.mean(seeds):.3f}\n[{min(seeds):.3f}, {max(seeds):.3f}]",
                        ha="center", va="center", color="white" if values[i][j] < 0.55 else "black")
        ax.set_xticks(range(2), ("Bicubic query", "SwinIR query"))
        labels = {"clean": "Clean bank", "bicubic_matched": "Bicubic bank",
                  "swinir_restored": "SwinIR bank", "balanced_mixed": "50:50 bank"}
        ax.set_yticks(range(len(banks)), [labels[bank] for bank in banks])
        ax.set_title(category)
    fig.suptitle("Pooled AU-PRO@0.3 | mean and range across 3 fixed seeds")
    fig.colorbar(image, ax=axes[0].tolist(), label="Dataset pooled AU-PRO@0.3", shrink=0.8)
    first = out / "bank_query_matrix.png"
    fig.savefig(first, dpi=200)
    plt.close(fig)
    contrasts = [
        ("bicubic_matched:bicubic_x4_minus_clean:bicubic_x4", "Bicubic bank / Bicubic query"),
        ("swinir_restored:bicubic_x4_minus_clean:bicubic_x4", "SwinIR bank / Bicubic query"),
        ("bicubic_matched:swinir_x4_minus_clean:swinir_x4", "Bicubic bank / SwinIR query"),
        ("swinir_restored:swinir_x4_minus_clean:swinir_x4", "SwinIR bank / SwinIR query"),
        ("swinir_restored:swinir_x4_minus_bicubic_matched:bicubic_x4", "Matched SwinIR minus matched Bicubic")]
    if "balanced_mixed" in banks:
        contrasts[-1:-1] = [
            ("balanced_mixed:bicubic_x4_minus_bicubic_matched:bicubic_x4", "50:50 minus Bicubic bank / Bicubic query"),
            ("balanced_mixed:swinir_x4_minus_swinir_restored:swinir_x4", "50:50 minus SwinIR bank / SwinIR query")]
    fig, axes = plt.subplots(len(categories), 1, figsize=(11, 7), sharex=True, layout="constrained", squeeze=False)
    fig.suptitle("Bank minus clean (first four rows) | matched references below", fontsize=14)
    for ax, category in zip(axes[:, 0], categories, strict=True):
        for i, (contrast, label) in enumerate(contrasts):
            row = next(r for r in effects if r["category"] == category and r["contrast"] == contrast)
            mean, low, high = (float(row[k]) for k in ("conditional_mean_per_image_delta", "conditional_ci95_low", "conditional_ci95_high"))
            ax.errorbar(mean, i, xerr=np.maximum(0, [[mean - low], [high - mean]]),
                        marker="o", capsize=4, color="#D55E00" if row["axis"] == "pipeline" else "#0072B2")
        ax.set_yticks(range(len(contrasts)), [c[1] for c in contrasts])
        ax.invert_yaxis()
        ax.axvline(0, color="black", linewidth=0.8)
        ax.grid(axis="x", alpha=0.2)
        ax.set_title(category)
    axes[-1, 0].set_xlabel("Mean per-image AU-PRO delta, averaged over 3 fixed fits\n95% image-unit bootstrap CI conditional on those fits")
    second = out / "conditional_bank_effects.png"
    fig.savefig(second, dpi=200)
    plt.close(fig)
    write_json(directory / "figure_manifest.json", dict(source_analysis_sha256=digest(directory / "analysis_manifest.json"),
        code_sha256=digest(Path(__file__)), files={p.name: digest(p) for p in (first, second)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    plot(parser.parse_args().run)
