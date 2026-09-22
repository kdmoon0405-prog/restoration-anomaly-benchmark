"""Render frozen selected cases from saved anomaly maps without model inference."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import matplotlib
import numpy as np
from PIL import Image

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_hazelnut_failures import _canonical_transform, _load_npz


def render_cases(run_dir: Path, data_root: Path, manifest: Path, output_dir: Path) -> int:
    result = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    paths = list(result["test_paths"])
    indices = {sample: index for index, sample in enumerate(paths)}
    bic = _load_npz(run_dir / "bicubic_x4_predictions.npz")
    swin = _load_npz(run_dir / "swinir_x4_predictions.npz")
    if (len(indices) != len(paths) or len(paths) != len(bic["labels"])
            or not np.array_equal(bic["labels"], swin["labels"])
            or not np.array_equal(bic["masks"], swin["masks"])):
        raise ValueError("Saved predictions and test paths are not paired")
    with manifest.open(encoding="utf-8", newline="") as handle:
        selected = list(csv.DictReader(handle))
    if not selected or len({row["sample"] for row in selected}) != len(selected):
        raise ValueError("Selected-case manifest must be nonempty and unique")

    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    canonical = _canonical_transform()
    rendered = []
    for rank, row in enumerate(selected, 1):
        sample = row["sample"]
        if sample not in indices:
            raise ValueError(f"Selected sample is absent from the source run: {sample}")
        index = indices[sample]
        if int(bic["labels"][index]) != 1:
            raise ValueError(f"Selected sample is not anomalous: {sample}")
        source_path = data_root / sample
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        with Image.open(source_path) as source:
            clean = canonical(source.convert("RGB"))
        low_resolution = clean.resize((56, 56), Image.Resampling.BICUBIC)
        bicubic = low_resolution.resize((224, 224), Image.Resampling.BICUBIC)
        bic_map, swin_map = bic["maps"][index], swin["maps"][index]
        vmin, vmax = float(min(bic_map.min(), swin_map.min())), float(max(bic_map.max(), swin_map.max()))
        panels = (
            ("Clean", np.asarray(clean), None),
            ("Bicubic x4", np.asarray(bicubic), None),
            ("GT mask", bic["masks"][index], "gray"),
            ("Bicubic anomaly map", bic_map, "viridis"),
            ("SwinIR anomaly map", swin_map, "viridis"),
        )
        fig = plt.figure(figsize=(18, 6))
        for panel, (title, image, cmap) in enumerate(panels, 1):
            axis = fig.add_subplot(2, 3, panel)
            axis.imshow(image, cmap=cmap, vmin=vmin if cmap == "viridis" else None,
                        vmax=vmax if cmap == "viridis" else None)
            axis.set_title(title)
            axis.axis("off")
        fig.suptitle(
            f"{sample} | {row['defect_type']} | {row['regression_type']}\n"
            f"delta AU-PRO={float(row['delta_aupro']):+.6f} | "
            f"delta Pixel AUROC={float(row['delta_pixel_auroc']):+.6f} | "
            f"delta ROI-bg gap={float(row['delta_roi_bg_gap']):+.6f}"
        )
        fig.tight_layout()
        filename = f"{rank:02d}_{Path(sample).with_suffix('').as_posix().replace('/', '__')}.png"
        fig.savefig(output_dir / filename, dpi=150)
        plt.close(fig)
        rendered.append((row["selection_reason"], sample, filename))

    lines = [
        "# Screw frozen selected cases", "",
        "These figures use saved PatchCore maps and GT masks plus the source clean image and deterministic Bicubic x4 input. No PatchCore or SwinIR inference was run. The two anomaly maps share one color scale within each sample.", "",
        "Cases were fixed by per-image AU-PRO ranking before rendering. They are qualitative/NN follow-up candidates, not population estimates.", "",
    ]
    lines.extend(f"- {reason}: `{sample}` → `{filename}`" for reason, sample, filename in rendered)
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rendered)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    count = render_cases(args.run_dir, args.data_root, args.manifest, args.output_dir)
    print(f"Rendered {count} saved-map cases to {args.output_dir}")


if __name__ == "__main__":
    main()
