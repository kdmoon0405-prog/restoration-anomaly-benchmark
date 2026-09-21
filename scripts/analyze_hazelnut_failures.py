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


def _regression_type(delta_aupro: float, delta_gap: float) -> str:
    if delta_aupro >= 0:
        return "improvement_or_tie"
    return "suppression" if delta_gap < 0 else "geometry_candidate"


def _case_groups(rows: list[dict], count: int) -> dict[str, list[dict]]:
    ordered = sorted(rows, key=lambda row: (row["delta_per_image_aupro"], row["sample"]))
    return {"worst": ordered[:count], "best": list(reversed(ordered[-count:])) if count else []}


def _screening_oracle(rows: list[dict], metric: str) -> dict:
    bic = np.asarray([row[f"bicubic_per_image_{metric}"] for row in rows], dtype=np.float64)
    swin = np.asarray([row[f"swinir_per_image_{metric}"] for row in rows], dtype=np.float64)
    if not np.isfinite(bic).all() or not np.isfinite(swin).all():
        raise ValueError(f"Per-image {metric} contains non-finite values")
    best = np.maximum(bic, swin)
    return {
        "bicubic_wins": int(np.count_nonzero(bic > swin)),
        "swinir_wins": int(np.count_nonzero(swin > bic)),
        "ties": int(np.count_nonzero(bic == swin)),
        "mean_bicubic": float(bic.mean()),
        "mean_swinir": float(swin.mean()),
        "mean_oracle": float(best.mean()),
        "headroom_vs_restored": float(best.mean() - swin.mean()),
    }


def _select_whole_maps(rows: list[dict], bic: dict[str, np.ndarray], swin: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, int]:
    scores = np.array(swin["scores"], copy=True)
    maps = np.array(swin["maps"], copy=True)
    bicubic_wins = 0
    for row in rows:
        if row["bicubic_per_image_aupro"] > row["swinir_per_image_aupro"]:
            index = int(row["index"])
            scores[index] = bic["scores"][index]
            maps[index] = bic["maps"][index]
            bicubic_wins += 1
    return scores, maps, bicubic_wins


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


def _render_cases(rows: list[dict], run_dir: Path, data_root: Path, output_dir: Path, count: int, swinir_checkpoint: Path | None,
                  selected_groups: dict[str, list[dict]] | None = None) -> None:
    if count <= 0:
        return
    if swinir_checkpoint is None:
        raise ValueError("Rendering the SwinIR image requires --swinir-checkpoint; use --render-cases 0 for NPZ-only analysis")
    import matplotlib.pyplot as plt
    bic_npz = _load_npz(run_dir / "bicubic_x4_predictions.npz")
    swin_npz = _load_npz(run_dir / "swinir_x4_predictions.npz")
    canonical = _canonical_transform()
    if not swinir_checkpoint.is_file():
        raise FileNotFoundError(f"SwinIR checkpoint not found: {swinir_checkpoint}")
    from sr_anomaly.real_models import SwinIRLightweight
    restorer = SwinIRLightweight(ROOT / "third_party" / "SwinIR", swinir_checkpoint, scale=4, tile=56, tile_overlap=0, device="cpu")

    groups = selected_groups if selected_groups is not None else _case_groups(rows, count)
    for group, selected in groups.items():
        group_dir = output_dir / (group if selected_groups is not None else f"{group}_{count}")
        group_dir.mkdir(parents=True, exist_ok=True)
        for rank, row in enumerate(selected, 1):
            i = int(row["index"])
            source_path = data_root / row["sample"]
            with Image.open(source_path) as source:
                clean = canonical(source.convert("RGB"))
            lr = clean.resize((56, 56), Image.Resampling.BICUBIC)
            bicubic = lr.resize((224, 224), Image.Resampling.BICUBIC)
            restored = restorer.restore(lr)
            mask = bic_npz["masks"][i].astype(bool)
            bic_map = bic_npz["maps"][i]
            swin_map = swin_npz["maps"][i]
            map_vmin = float(min(bic_map.min(), swin_map.min()))
            map_vmax = float(max(bic_map.max(), swin_map.max()))

            fig = plt.figure(figsize=(18, 6))
            panels = [
                ("Clean", np.asarray(clean), None),
                ("Bicubic x4", np.asarray(bicubic), None),
                ("SwinIR x4", np.asarray(restored), None),
                ("GT mask", mask, "gray"),
                ("Bicubic anomaly map", bic_map, "viridis"),
                ("SwinIR anomaly map", swin_map, "viridis"),
            ]
            for p, (title, image, cmap) in enumerate(panels, 1):
                ax = fig.add_subplot(2, 3, p)
                ax.imshow(image, cmap=cmap, vmin=map_vmin if cmap == "viridis" else None,
                          vmax=map_vmax if cmap == "viridis" else None)
                ax.set_title(title)
                ax.axis("off")
            pixel_delta = row.get("delta_per_image_pixel_auroc")
            pixel_text = f" | delta Pixel AUROC={pixel_delta:+.6f}" if pixel_delta is not None else ""
            fig.suptitle(f"{group.upper()} #{rank} | {row['sample']} | {row['defect_type']} | {row.get('regression_type', '')}\n"
                         f"delta AU-PRO={row['delta_per_image_aupro']:+.6f}{pixel_text} | "
                         f"delta ROI-bg gap={row['delta_roi_bg_gap']:+.6f}")
            plt.tight_layout()
            safe_name = Path(row["sample"]).with_suffix("").as_posix().replace("/", "__")
            fig.savefig(group_dir / f"{rank:02d}_{safe_name}.png", dpi=150)
            plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hazelnut SwinIR-vs-bicubic failure analysis from saved PatchCore predictions.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "external" / "MVTecAD")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis" / "hazelnut")
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--select-cases", type=int, default=10, help="worst and best cases to list by per-image AU-PRO change")
    parser.add_argument("--render-cases", type=int, default=10)
    parser.add_argument("--swinir-checkpoint", type=Path)
    args = parser.parse_args()
    if args.select_cases < 0 or args.render_cases < 0:
        raise ValueError("Case counts must be nonnegative")

    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve()
    if args.render_cases and args.swinir_checkpoint is None:
        raise ValueError("Rendering requires --swinir-checkpoint; use --render-cases 0 for NPZ-only analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / "results.json"
    if not result_path.is_file():
        raise FileNotFoundError(f"results.json not found in {run_dir}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    test_paths = list(result["test_paths"])
    source_run = str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir)

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
        if not mask.any() or mask.all():
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
        delta_gap = (swin_roi_mean - swin_bg_mean) - (bic_roi_mean - bic_bg_mean)
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
            "delta_roi_bg_gap": delta_gap,
            "bicubic_roi_bg_ratio": _safe_ratio(bic_roi_mean, bic_bg_mean),
            "swinir_roi_bg_ratio": _safe_ratio(swin_roi_mean, swin_bg_mean),
            "map_pearson_corr": corr,
            "bicubic_per_image_pixel_auroc": bic_auc,
            "swinir_per_image_pixel_auroc": swin_auc,
            "delta_per_image_pixel_auroc": swin_auc - bic_auc,
            "bicubic_per_image_aupro": bic_pro,
            "swinir_per_image_aupro": swin_pro,
            "delta_per_image_aupro": swin_pro - bic_pro,
            "regression_type": _regression_type(swin_pro - bic_pro, delta_gap),
        })
    if not rows:
        raise ValueError("No anomalous test images with nonempty masks were found")

    csv_path = output_dir / "hazelnut_per_defect.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    case_fields = ["sample", "defect_type", "regression_type", "delta_per_image_aupro",
                   "delta_per_image_pixel_auroc", "delta_roi_mean", "delta_roi_bg_gap", "defect_area_ratio"]
    with (output_dir / "regression_taxonomy.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=case_fields)
        writer.writeheader()
        writer.writerows({key: row[key] for key in case_fields} for row in rows)
    with (output_dir / "selected_cases.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["selection_group", "rank", *case_fields])
        writer.writeheader()
        for group, selected in _case_groups(rows, args.select_cases).items():
            writer.writerows({"selection_group": group, "rank": rank,
                              **{key: row[key] for key in case_fields}} for rank, row in enumerate(selected, 1))
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

    oracle_scores, oracle_maps, bic_chosen = _select_whole_maps(rows, bic, swin)
    oracle_eval = evaluate_predictions(labels=swin["labels"], scores=oracle_scores, masks=swin["masks"], anomaly_maps=oracle_maps)
    restored_eval = evaluate_predictions(labels=swin["labels"], scores=swin["scores"], masks=swin["masks"], anomaly_maps=swin["maps"])
    oracle = {
        "source_run": source_run,
        "definition": "GT-assisted, non-deployable post-hoc selection upper bound",
        "selection_rule": "For each anomalous image, choose the branch with higher per-image AU-PRO@0.3; ties and normal images keep SwinIR.",
        "caveat": "The screening mean of per-image maxima bounds choosing one of these two existing branches per image; it does not bound a new fused map. Pooled whole-map AU-PRO and AUROC are recalculated outcomes, not guaranteed upper bounds or deployable results.",
        "screening_oracle": {
            "per_image_aupro": _screening_oracle(rows, "aupro"),
            "per_image_pixel_auroc": _screening_oracle(rows, "pixel_auroc"),
        },
        "whole_map_selection": {
            "bicubic_selected_anomaly_images": bic_chosen,
            "normal_image_policy": "keep SwinIR scores and maps",
            "restored_only": restored_eval,
            "selected": oracle_eval,
            "delta_vs_restored": {
                "image_auroc": oracle_eval["classification"]["image_auroc"] - restored_eval["classification"]["image_auroc"],
                "pixel_auroc": oracle_eval["localization"]["pixel_auroc"] - restored_eval["localization"]["pixel_auroc"],
                "pooled_au_pro": oracle_eval["localization"]["au_pro"] - restored_eval["localization"]["au_pro"],
            },
        },
    }
    (output_dir / "oracle_localization_headroom.json").write_text(json.dumps(oracle, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {name: sum(row["regression_type"] == name for row in rows)
              for name in ("improvement_or_tie", "suppression", "geometry_candidate")}
    regression_deltas = np.asarray([row["delta_per_image_aupro"] for row in rows if row["delta_per_image_aupro"] < 0])
    area = np.asarray([row["defect_area_ratio"] for row in rows], dtype=float)
    rho = _spearman(area, np.asarray([row["delta_roi_mean"] for row in rows], dtype=float))
    bic_aggregate = result["variants"]["bicubic_x4"]
    swin_aggregate = result["variants"]["swinir_x4"]
    bic_eval = bic_aggregate["evaluation"]
    swin_eval = swin_aggregate["evaluation"]
    aupro_screen = oracle["screening_oracle"]["per_image_aupro"]
    pixel_screen = oracle["screening_oracle"]["per_image_pixel_auroc"]
    pooled_delta = oracle["whole_map_selection"]["delta_vs_restored"]
    summary = f"""# Hazelnut restoration failure analysis

## Scope
- Source run: `{source_run}`
- Anomalous test images analyzed: {len(rows)}
- Comparison: SwinIR-S x4 minus Bicubic x4
- No model or hyperparameter tuning was performed.

## Aggregate performance (110 test images)
- Bicubic: PSNR {bic_aggregate['mean_psnr']:.4f}, SSIM {bic_aggregate['mean_ssim']:.5f}, image AUROC {bic_eval['classification']['image_auroc']:.6f}, pixel AUROC {bic_eval['localization']['pixel_auroc']:.6f}, AU-PRO@0.3 {bic_eval['localization']['au_pro']:.6f}.
- SwinIR: PSNR {swin_aggregate['mean_psnr']:.4f}, SSIM {swin_aggregate['mean_ssim']:.5f}, image AUROC {swin_eval['classification']['image_auroc']:.6f}, pixel AUROC {swin_eval['localization']['pixel_auroc']:.6f}, AU-PRO@0.3 {swin_eval['localization']['au_pro']:.6f}.
- Pooled AU-PRO delta (SwinIR − Bicubic): {swin_eval['localization']['au_pro'] - bic_eval['localization']['au_pro']:+.6f}.

## Sample-level localization regression (70 anomalous images)
- Per-image AU-PRO decreased: {len(regression_deltas)}/{len(rows)}; mean delta among regressions {regression_deltas.mean():+.6f}, range [{regression_deltas.min():+.6f}, {regression_deltas.max():+.6f}].
- Suppression-type (AU-PRO↓ and ROI-background gap↓): {counts['suppression']}.
- Geometry-type candidate (AU-PRO↓ and ROI-background gap≥0): {counts['geometry_candidate']}.
- Improvement or tie: {counts['improvement_or_tie']}.
- These labels describe map-score patterns; they do not establish a feature-space cause.

## Oracle headroom
- Per-image AU-PRO screening: Bicubic wins {aupro_screen['bicubic_wins']}, SwinIR wins {aupro_screen['swinir_wins']}, ties {aupro_screen['ties']}; mean Bicubic {aupro_screen['mean_bicubic']:.6f}, SwinIR {aupro_screen['mean_swinir']:.6f}, oracle {aupro_screen['mean_oracle']:.6f}; headroom vs restored {aupro_screen['headroom_vs_restored']:+.6f}.
- Per-image pixel AUROC screening headroom vs restored: {pixel_screen['headroom_vs_restored']:+.6f}.
- Whole-map post-hoc selection delta vs restored: image AUROC {pooled_delta['image_auroc']:+.6f}, pixel AUROC {pooled_delta['pixel_auroc']:+.6f}, pooled AU-PRO {pooled_delta['pooled_au_pro']:+.6f}.
- This GT-assisted selection is non-deployable. Per-image mean headroom is an upper bound for two-branch screening; pooled metrics need not improve.

## Defect-size hypothesis
- Spearman(defect area ratio, ROI-mean delta): {rho if rho is not None else 'N/A'}
- The current hazelnut analysis does not support the simple smaller-defect → stronger-failure hypothesis. Size is not used to define regression.

## Interpretation limits
- GT masks were used only after inference. `preliminary_roi_mean_oracle.json` is a deprecated historical artifact, not a localization upper bound.
- `bootstrap_ci.json` intervals for pixel AUROC/AU-PRO concern mean per-image paired deltas, not pooled dataset metrics.
- `regression_taxonomy.csv`, `selected_cases.csv`, and `oracle_localization_headroom.json` retain the exact magnitudes and selection outcomes.
- Coarse fusion-weight search remains a later option on hazelnut development data only if oracle complementarity justifies it; no weight is chosen here.
"""
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")

    _render_cases(rows, run_dir, args.data_root.resolve(), output_dir, args.render_cases, args.swinir_checkpoint.resolve() if args.swinir_checkpoint else None)
    print(f"Analysis complete: {output_dir}")
    print(f"Per-defect CSV: {csv_path}")
    print(f"Per-image AU-PRO regressions: {len(regression_deltas)}/{len(rows)}")
    print(f"Suppression: {counts['suppression']}; geometry candidate: {counts['geometry_candidate']}")
    print(f"Per-image AU-PRO screening headroom: {aupro_screen['headroom_vs_restored']:+.6f}")


if __name__ == "__main__":
    main()
