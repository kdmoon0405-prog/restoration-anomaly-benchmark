from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.evaluation import binary_roc_auc, area_under_per_region_overlap, evaluate_predictions


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(f"Prediction file not found: {path}")
    with np.load(path, allow_pickle=False) as data:
        required = {"labels", "scores", "masks", "maps"}
        missing = required - set(data.files)
        if missing:
            raise ValueError(f"{path.name} missing keys: {sorted(missing)}")
        return {key: np.asarray(data[key]) for key in required}


def _percentile_ci(values: np.ndarray, alpha: float = 0.05) -> list[float]:
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return [float("nan"), float("nan")]
    lo, hi = np.quantile(values, [alpha / 2.0, 1.0 - alpha / 2.0])
    return [float(lo), float(hi)]


def _rankdata(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=np.float64)
    start = 0
    while start < values.size:
        end = start + 1
        while end < values.size and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1) + 1.0
        start = end
    return ranks


def _spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 3 or np.all(x == x[0]) or np.all(y == y[0]):
        return None
    return float(np.corrcoef(_rankdata(x), _rankdata(y))[0, 1])


def _safe_ratio(num: float, den: float) -> float | None:
    if abs(den) < 1e-12:
        return None
    return float(num / den)


def _defect_type(path_text: str) -> str:
    parts = Path(path_text).parts
    try:
        index = parts.index("test")
        return parts[index + 1]
    except (ValueError, IndexError):
        return "unknown"


def _per_image_pixel_metrics(mask: np.ndarray, bic_map: np.ndarray, swin_map: np.ndarray) -> tuple[float, float, float, float]:
    binary = np.asarray(mask, dtype=bool)
    if not binary.any() or binary.all():
        return (float("nan"), float("nan"), float("nan"), float("nan"))
    labels = binary.ravel().astype(np.uint8)
    bic_auc = binary_roc_auc(labels, bic_map.ravel())
    swin_auc = binary_roc_auc(labels, swin_map.ravel())
    bic_pro = area_under_per_region_overlap(binary[None, ...], bic_map[None, ...], max_fpr=0.3, num_thresholds=200)
    swin_pro = area_under_per_region_overlap(binary[None, ...], swin_map[None, ...], max_fpr=0.3, num_thresholds=200)
    return float(bic_auc), float(swin_auc), float(bic_pro), float(swin_pro)


def _bootstrap_mean_delta(deltas: np.ndarray, repeats: int, rng: np.random.Generator) -> dict:
    deltas = np.asarray(deltas, dtype=np.float64)
    deltas = deltas[np.isfinite(deltas)]
    if deltas.size == 0:
        return {"estimate": None, "ci95": [None, None], "n": 0}
    draws = np.empty(repeats, dtype=np.float64)
    n = deltas.size
    for i in range(repeats):
        idx = rng.integers(0, n, n)
        draws[i] = deltas[idx].mean()
    return {"estimate": float(deltas.mean()), "ci95": _percentile_ci(draws), "n": int(n)}


def _bootstrap_image_auroc_delta(labels, bic_scores, swin_scores, repeats: int, rng: np.random.Generator) -> dict:
    labels = np.asarray(labels)
    bic_scores = np.asarray(bic_scores, dtype=np.float64)
    swin_scores = np.asarray(swin_scores, dtype=np.float64)
    n = labels.size
    draws = []
    attempts = 0
    max_attempts = repeats * 20
    while len(draws) < repeats and attempts < max_attempts:
        idx = rng.integers(0, n, n)
        sampled_labels = labels[idx]
        attempts += 1
        if np.unique(sampled_labels).size < 2:
            continue
        draws.append(binary_roc_auc(sampled_labels, swin_scores[idx]) - binary_roc_auc(sampled_labels, bic_scores[idx]))
    if not draws:
        return {"estimate": None, "ci95": [None, None], "valid_bootstraps": 0}
    estimate = binary_roc_auc(labels, swin_scores) - binary_roc_auc(labels, bic_scores)
    return {"estimate": float(estimate), "ci95": _percentile_ci(np.asarray(draws)), "valid_bootstraps": len(draws)}


def _plot_outputs(rows: list[dict], output_dir: Path) -> None:
    import matplotlib.pyplot as plt
    area = np.asarray([row["defect_area_ratio"] for row in rows], dtype=float)
    delta_mean = np.asarray([row["delta_roi_mean"] for row in rows], dtype=float)
    delta_max = np.asarray([row["delta_roi_max"] for row in rows], dtype=float)

    fig = plt.figure(figsize=(7, 5))
    plt.scatter(area, delta_mean, alpha=0.75)
    plt.axhline(0.0, linewidth=1)
    plt.xlabel("Defect area ratio")
    plt.ylabel("SwinIR - Bicubic defect ROI mean")
    plt.title("Defect size vs ROI-mean change")
    plt.tight_layout()
    fig.savefig(output_dir / "defect_area_vs_delta_roi_mean.png", dpi=180)
    plt.close(fig)

    fig = plt.figure(figsize=(7, 5))
    plt.scatter(area, delta_max, alpha=0.75)
    plt.axhline(0.0, linewidth=1)
    plt.xlabel("Defect area ratio")
    plt.ylabel("SwinIR - Bicubic defect ROI max")
    plt.title("Defect size vs ROI-max change")
    plt.tight_layout()
    fig.savefig(output_dir / "defect_area_vs_delta_roi_max.png", dpi=180)
    plt.close(fig)

    fig = plt.figure(figsize=(7, 5))
    plt.hist(delta_mean, bins=min(20, max(5, len(rows) // 3)))
    plt.axvline(0.0, linewidth=1)
    plt.xlabel("SwinIR - Bicubic defect ROI mean")
    plt.ylabel("Number of anomalous images")
    plt.title("Distribution of defect-evidence change")
    plt.tight_layout()
    fig.savefig(output_dir / "delta_roi_mean_histogram.png", dpi=180)
    plt.close(fig)


def _canonical_transform():
    from torchvision import transforms
    from torchvision.transforms import InterpolationMode
    resize = transforms.Resize(256, interpolation=InterpolationMode.BILINEAR)
    crop = transforms.CenterCrop(224)
    return lambda image: crop(resize(image))


def _render_cases(rows: list[dict], run_dir: Path, data_root: Path, output_dir: Path, count: int, swinir_checkpoint: Path | None) -> None:
    if count <= 0:
        return
    import matplotlib.pyplot as plt
    bic_npz = _load_npz(run_dir / "bicubic_x4_predictions.npz")
    swin_npz = _load_npz(run_dir / "swinir_x4_predictions.npz")
    canonical = _canonical_transform()
    restorer = None
    if swinir_checkpoint is not None:
        if not swinir_checkpoint.is_file():
            raise FileNotFoundError(f"SwinIR checkpoint not found: {swinir_checkpoint}")
        from sr_anomaly.real_models import SwinIRLightweight
        restorer = SwinIRLightweight(ROOT / "third_party" / "SwinIR", swinir_checkpoint, scale=4, tile=56, tile_overlap=0, device="cpu")

    ordered = sorted(rows, key=lambda row: row["delta_roi_mean"])
    groups = {"worst": ordered[: min(count, len(ordered))], "best": list(reversed(ordered[-min(count, len(ordered)):]))}
    for group, selected in groups.items():
        group_dir = output_dir / f"{group}_{count}"
        group_dir.mkdir(parents=True, exist_ok=True)
        for rank, row in enumerate(selected, 1):
            i = int(row["index"])
            source_path = data_root / row["sample"]
            with Image.open(source_path) as source:
                clean = canonical(source.convert("RGB"))
            lr = clean.resize((56, 56), Image.Resampling.BICUBIC)
            bicubic = lr.resize((224, 224), Image.Resampling.BICUBIC)
            restored = restorer.restore(lr) if restorer is not None else None
            mask = bic_npz["masks"][i].astype(bool)
            bic_map = bic_npz["maps"][i]
            swin_map = swin_npz["maps"][i]

            fig = plt.figure(figsize=(18, 6))
            panels = [
                ("Clean", np.asarray(clean), None),
                ("Bicubic x4", np.asarray(bicubic), None),
                ("SwinIR x4" if restored is not None else "SwinIR image not rendered", np.asarray(restored) if restored is not None else np.zeros((224, 224)), None if restored is not None else "gray"),
                ("GT mask", mask, "gray"),
                ("Bicubic anomaly map", bic_map, "viridis"),
                ("SwinIR anomaly map", swin_map, "viridis"),
            ]
            for p, (title, image, cmap) in enumerate(panels, 1):
                ax = fig.add_subplot(2, 3, p)
                ax.imshow(image, cmap=cmap)
                ax.set_title(title)
                ax.axis("off")
            fig.suptitle(f"{group.upper()} #{rank} | {row['sample']} | delta ROI mean={row['delta_roi_mean']:.6f}")
            plt.tight_layout()
            safe_name = row["sample"].replace("/", "__").replace("\\", "__")
            fig.savefig(group_dir / f"{rank:02d}_{safe_name}.png", dpi=150)
            plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hazelnut SwinIR-vs-bicubic failure analysis from saved PatchCore predictions.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis" / "hazelnut")
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--render-cases", type=int, default=10)
    parser.add_argument("--swinir-checkpoint", type=Path)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / "results.json"
    if not result_path.is_file():
        raise FileNotFoundError(f"results.json not found in {run_dir}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    test_paths = list(result["test_paths"])

    bic = _load_npz(run_dir / "bicubic_x4_predictions.npz")
    swin = _load_npz(run_dir / "swinir_x4_predictions.npz")
    n = len(test_paths)
    for name, item in (("bicubic", bic), ("swinir", swin)):
        if len(item["labels"]) != n:
            raise ValueError(f"{name} prediction count {len(item['labels'])} != test_paths {n}")
    if not np.array_equal(bic["labels"], swin["labels"]) or not np.array_equal(bic["masks"], swin["masks"]):
        raise ValueError("Bicubic and SwinIR predictions are not paired on identical labels/masks")

    rows = []
    per_image_pixel_auc_delta = []
    per_image_aupro_delta = []
    for i, (path_text, label) in enumerate(zip(test_paths, bic["labels"])):
        if int(label) != 1:
            continue
        mask = np.asarray(bic["masks"][i], dtype=bool)
        if not mask.any():
            continue
        bic_map = np.asarray(bic["maps"][i], dtype=np.float64)
        swin_map = np.asarray(swin["maps"][i], dtype=np.float64)
        background = ~mask
        bic_roi_mean = float(bic_map[mask].mean())
        swin_roi_mean = float(swin_map[mask].mean())
        bic_roi_max = float(bic_map[mask].max())
        swin_roi_max = float(swin_map[mask].max())
        bic_bg_mean = float(bic_map[background].mean())
        swin_bg_mean = float(swin_map[background].mean())
        corr = float(np.corrcoef(bic_map.ravel(), swin_map.ravel())[0, 1]) if np.std(bic_map) > 0 and np.std(swin_map) > 0 else None
        bic_auc, swin_auc, bic_pro, swin_pro = _per_image_pixel_metrics(mask, bic_map, swin_map)
        per_image_pixel_auc_delta.append(swin_auc - bic_auc)
        per_image_aupro_delta.append(swin_pro - bic_pro)
        area = int(mask.sum())
        rows.append({
            "index": i,
            "sample": path_text,
            "defect_type": _defect_type(path_text),
            "defect_area": area,
            "defect_area_ratio": float(area / mask.size),
            "bicubic_roi_mean": bic_roi_mean,
            "swinir_roi_mean": swin_roi_mean,
            "delta_roi_mean": swin_roi_mean - bic_roi_mean,
            "bicubic_roi_max": bic_roi_max,
            "swinir_roi_max": swin_roi_max,
            "delta_roi_max": swin_roi_max - bic_roi_max,
            "bicubic_background_mean": bic_bg_mean,
            "swinir_background_mean": swin_bg_mean,
            "bicubic_roi_bg_gap": bic_roi_mean - bic_bg_mean,
            "swinir_roi_bg_gap": swin_roi_mean - swin_bg_mean,
            "delta_roi_bg_gap": (swin_roi_mean - swin_bg_mean) - (bic_roi_mean - bic_bg_mean),
            "bicubic_roi_bg_ratio": _safe_ratio(bic_roi_mean, bic_bg_mean),
            "swinir_roi_bg_ratio": _safe_ratio(swin_roi_mean, swin_bg_mean),
            "map_pearson_corr": corr,
            "bicubic_per_image_pixel_auroc": bic_auc,
            "swinir_per_image_pixel_auroc": swin_auc,
            "delta_per_image_pixel_auroc": swin_auc - bic_auc,
            "bicubic_per_image_aupro": bic_pro,
            "swinir_per_image_aupro": swin_pro,
            "delta_per_image_aupro": swin_pro - bic_pro,
        })
    if not rows:
        raise ValueError("No anomalous test images with nonempty masks were found")

    csv_path = output_dir / "hazelnut_per_defect.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    _plot_outputs(rows, output_dir)

    rng = np.random.default_rng(args.seed)
    bootstrap = {
        "method": "Paired image-resampling bootstrap. Image-AUROC delta is recomputed from resampled image scores. Pixel-AUROC and AU-PRO intervals bootstrap the mean of per-anomalous-image paired metric deltas; they are not pooled-pixel dataset-level bootstrap intervals.",
        "repeats": args.bootstrap,
        "seed": args.seed,
        "image_auroc_delta_swinir_minus_bicubic": _bootstrap_image_auroc_delta(bic["labels"], bic["scores"], swin["scores"], args.bootstrap, rng),
        "mean_per_anomaly_pixel_auroc_delta": _bootstrap_mean_delta(np.asarray(per_image_pixel_auc_delta), args.bootstrap, rng),
        "mean_per_anomaly_aupro_delta": _bootstrap_mean_delta(np.asarray(per_image_aupro_delta), args.bootstrap, rng),
        "mean_defect_roi_delta": _bootstrap_mean_delta(np.asarray([row["delta_roi_mean"] for row in rows]), args.bootstrap, rng),
    }
    (output_dir / "bootstrap_ci.json").write_text(json.dumps(bootstrap, ensure_ascii=False, indent=2), encoding="utf-8")

    oracle_scores = np.array(swin["scores"], dtype=np.float64, copy=True)
    oracle_maps = np.array(swin["maps"], dtype=np.float64, copy=True)
    bic_chosen = 0
    for row in rows:
        i = int(row["index"])
        if row["bicubic_roi_mean"] > row["swinir_roi_mean"]:
            oracle_scores[i] = bic["scores"][i]
            oracle_maps[i] = bic["maps"][i]
            bic_chosen += 1
    oracle_eval = evaluate_predictions(labels=swin["labels"], scores=oracle_scores, masks=swin["masks"], anomaly_maps=oracle_maps)
    restored_eval = evaluate_predictions(labels=swin["labels"], scores=swin["scores"], masks=swin["masks"], anomaly_maps=swin["maps"])
    oracle = {
        "definition": "Post-hoc, non-deployable upper bound: on anomalous images only, select the whole Bicubic or SwinIR prediction using whichever has the larger GT defect-ROI mean. Normal images keep SwinIR.",
        "bicubic_selected_anomaly_images": bic_chosen,
        "total_anomaly_images": len(rows),
        "restored_only": restored_eval,
        "oracle": oracle_eval,
    }
    (output_dir / "oracle_headroom.json").write_text(json.dumps(oracle, ensure_ascii=False, indent=2), encoding="utf-8")

    improved = sum(row["delta_roi_mean"] > 0 for row in rows)
    worsened = sum(row["delta_roi_mean"] < 0 for row in rows)
    tied = len(rows) - improved - worsened
    area = np.asarray([row["defect_area_ratio"] for row in rows], dtype=float)
    delta = np.asarray([row["delta_roi_mean"] for row in rows], dtype=float)
    rho = _spearman(area, delta)
    summary = f"""# Hazelnut restoration failure analysis

## Scope
- Source run: `{run_dir}`
- Anomalous test images analyzed: {len(rows)}
- Comparison: SwinIR-S x4 minus Bicubic x4
- No model or hyperparameter tuning was performed.

## Defect-ROI evidence
- Improved ROI mean: {improved}/{len(rows)} ({100.0*improved/len(rows):.1f}%)
- Decreased ROI mean: {worsened}/{len(rows)} ({100.0*worsened/len(rows):.1f}%)
- Tied: {tied}/{len(rows)} ({100.0*tied/len(rows):.1f}%)
- Mean ROI-mean delta: {delta.mean():.6f}
- Median ROI-mean delta: {np.median(delta):.6f}
- Spearman(defect area ratio, ROI-mean delta): {rho if rho is not None else 'N/A'}

## Interpretation rules
- Positive delta means SwinIR produced stronger anomaly-map evidence inside the GT defect ROI than Bicubic.
- Negative delta is a candidate restoration-induced anomaly suppression case.
- GT masks are used only after inference for post-hoc evaluation.
- See `bootstrap_ci.json` for paired uncertainty estimates.
- See `oracle_headroom.json` for a deliberately non-deployable GT-assisted upper bound.

## Next decision
- If negative-ROI cases concentrate in small defects or a specific defect type, prioritize feature-space NN-distance analysis on those cases.
- If failures are rare and unstructured, do not expand fusion-weight search; proceed to the preselected cross-category stress tests.
"""
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")

    _render_cases(rows, run_dir, args.data_root.resolve(), output_dir, args.render_cases, args.swinir_checkpoint.resolve() if args.swinir_checkpoint else None)
    print(f"Analysis complete: {output_dir}")
    print(f"Per-defect CSV: {csv_path}")
    print(f"Improved: {improved}/{len(rows)} ({100.0*improved/len(rows):.1f}%)")
    print(f"Worsened: {worsened}/{len(rows)} ({100.0*worsened/len(rows):.1f}%)")
    print(f"Spearman area-vs-delta: {rho}")


if __name__ == "__main__":
    main()
