"""Fixed ten-image Branch B RGB partial-restoration feasibility experiment.

No fitting, recalibration, mask tuning, or independent-validation claim.
Run --prepare-only first, then --smoke, then the default ten-image run.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import run_fusion_patchcore as branch_b
from sr_anomaly.dataset import MVTecADFolder
from sr_anomaly.device import start_timer, elapsed_seconds
from sr_anomaly.evaluation import area_under_per_region_overlap, evaluate_predictions
from sr_anomaly.fusion import normalize
from sr_anomaly.metrics import compute_quality_metrics
from sr_anomaly.real_models import SwinIRLightweight

BASE_COMMIT = "01a03840730836a76b92eca37b22fc8713b979b8"
BANK = ROOT / "checkpoints/fusion-patchcore/hazelnut-seed11-train313"
ANCHORS = ROOT / "outputs/fusion-patchcore/hazelnut-313x78-test110"
CHECKPOINT = ROOT / "checkpoints/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x4.pth"
PROTOCOL = ROOT / "analysis/partial_restoration_feasibility/PROTOCOL.json"
METHODS = ("bicubic", "full_swinir", "partial", "uniform")
STRATA = ("good", "crack", "cut", "hole", "print")
ANCHOR_ATOL = 1e-5


def compose_rgb(bicubic: Image.Image, restored: Image.Image, protection: np.ndarray):
    """Hard spatial selection and area-matched uniform RGB mixing (uint8 rounding)."""
    b, r = np.asarray(bicubic), np.asarray(restored)
    m = np.asarray(protection)
    if (b.shape != r.shape or b.ndim != 3 or b.shape[-1] != 3
            or b.dtype != np.uint8 or r.dtype != np.uint8
            or m.dtype != bool or m.shape != b.shape[:2]):
        raise ValueError("Expected paired uint8 RGB images and an aligned boolean protection mask")
    alpha = float(m.mean())
    partial = np.where(m[..., None], b, r)
    uniform = np.rint(alpha * b.astype(np.float64) + (1 - alpha) * r).astype(np.uint8)
    return Image.fromarray(partial), Image.fromarray(uniform), alpha


def self_check():
    b = Image.fromarray(np.full((4, 4, 3), 10, dtype=np.uint8))
    r = Image.fromarray(np.full((4, 4, 3), 210, dtype=np.uint8))
    for flag, expected in ((False, r), (True, b)):
        p, u, alpha = compose_rgb(b, r, np.full((4, 4), flag, dtype=bool))
        assert np.array_equal(p, expected) and np.array_equal(u, expected)
        assert alpha == float(flag)
    m = np.zeros((4, 4), dtype=bool)
    m[:2] = True
    p, u, alpha = compose_rgb(b, r, m)
    assert alpha == 0.5 and np.all(np.asarray(u) == 110)
    assert np.all(np.asarray(p)[m] == 10) and np.all(np.asarray(p)[~m] == 210)
    try:
        compose_rgb(b, r, m.astype(float))
    except ValueError:
        pass
    else:
        raise AssertionError("Non-boolean mask accepted")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def frozen_inputs(data_root: Path) -> dict:
    """Select by filename only, then fingerprint every source used by this pilot."""
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD"], check=True)
    metadata = _read_json(BANK / "metadata.json")
    recorded = _read_json(ANCHORS / "results.json")
    split = _read_json(ANCHORS / "split.json")
    spec = metadata["spec"]
    if (spec != recorded["model_spec"] or spec["category"] != "hazelnut"
            or len(spec["train_paths"]) != 313 or len(spec["calibration_paths"]) != 78
            or spec["train_paths"] != split["train_paths"]
            or spec["calibration_paths"] != split["calibration_paths"]
            or set(spec["train_paths"]) & set(spec["calibration_paths"])
            or spec["source_commit"] != branch_b.EXPECTED_PATCHCORE_COMMIT
            or spec["backbone"] != "wideresnet50" or spec["layers"] != ["layer2", "layer3"]
            or spec["sampler"] != "IdentitySampler" or spec["resize"] != 256 or spec["center_crop"] != 224):
        raise ValueError("Frozen 313/78 Branch B model/split mismatch")
    calibration = recorded["fusion_calibration"]
    if calibration["quantile"] != 0.99:
        raise ValueError("Expected the existing normal-only 99% calibration")
    for name, digest in metadata["artifact_sha256"].items():
        if branch_b._checksum(BANK / name) != digest:
            raise ValueError(f"Bank checksum mismatch: {name}")
    if branch_b._checksum(CHECKPOINT) != branch_b.EXPECTED_SWINIR_X4_SHA256:
        raise ValueError("SwinIR x4 checkpoint checksum mismatch")
    samples = MVTecADFolder(data_root, "hazelnut").samples()
    cohort = []
    for stratum in STRATA:
        first_two = sorted((s for s in samples if s.relative_path.parts[-2] == stratum),
                           key=lambda s: s.path.name)[:2]
        if len(first_two) != 2:
            raise ValueError(f"Two images required in {stratum}")
        cohort.extend(s.relative_path.as_posix() for s in first_two)
    paths = [BANK / "metadata.json", BANK / "patchcore_params.pkl", BANK / "nnscorer_search_index.faiss",
             CHECKPOINT, ANCHORS / "results.json", ANCHORS / "split.json",
             ANCHORS / "degraded_only_predictions.npz", ANCHORS / "restored_only_predictions.npz",
             ROOT / "scripts/run_fusion_patchcore.py", ROOT / "src/sr_anomaly/real_models.py",
             ROOT / "src/sr_anomaly/evaluation.py", ROOT / "src/sr_anomaly/fusion.py"]
    paths += [data_root / name for name in cohort]
    paths += [s.mask_path for s in samples if s.relative_path.as_posix() in cohort and s.mask_path]
    return {
        "base_commit": BASE_COMMIT, "cohort": cohort, "selection": "first two filenames per stratum",
        "smoke_sample": cohort[2], "model_spec": spec, "fusion_calibration": calibration,
        "protection": "saved normalized degraded-only map > existing 99% pixel threshold",
        "dilation_pixels": 0, "feather_pixels": 0, "mask_ground_truth_use": "evaluation only",
        "methods": list(METHODS), "partial": "M*B + (1-M)*R; M=1 preserves Bicubic",
        "uniform": "round(mean(M)*B + (1-mean(M))*R), uint8 RGB",
        "preprocessing": "Pillow: bilinear resize 256 / center crop 224 / bicubic 224->56->224",
        "swinir": {"scale": 4, "tile": 56, "tile_overlap": 0},
        "au_pro": {"max_fpr": 0.3, "num_thresholds": 200, "normal_per_image": None},
        "quality": ["psnr", "ssim"], "anchor_check_atol": ANCHOR_ATOL,
        "scope": "Existing development data, exploratory feasibility; not independent validation",
        "no_fit_or_recalibration": True,
        "source_sha256": {str(p.relative_to(ROOT)): branch_b._checksum(p) for p in paths},
    }


def load_frozen_bank(torch, common, patchcore, device):
    """Load only; there is intentionally no fit fallback for missing bank files."""
    model = patchcore.PatchCore(device)
    with branch_b._faiss_staging() as staging:
        for name in ("patchcore_params.pkl", "nnscorer_search_index.faiss"):
            shutil.copy2(BANK / name, Path(staging) / name)
        model.load_from_path(staging, device, nn_method=common.FaissNN(False, 4))
    return model


def _save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def _panel(path, images, protection, mask, maps, rows, sample):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 6, figsize=(16, 7))
    top = [images["clean"], images["bicubic"], images["full_swinir"], protection,
           images["partial"], images["uniform"]]
    titles = ["Clean reference", "Bicubic input", "Full SwinIR", "Protected input pixels", "Partial", "Uniform"]
    lower = [mask, maps["bicubic"], maps["full_swinir"], None, maps["partial"], maps["uniform"]]
    lo = min(float(m.min()) for m in maps.values())
    hi = max(float(m.max()) for m in maps.values())
    for j, (img, title, amap) in enumerate(zip(top, titles, lower)):
        axes[0, j].imshow(img, cmap="gray" if j == 3 else None)
        axes[0, j].set_title(title)
        if j == 0:
            axes[1, j].imshow(mask, cmap="gray", vmin=0, vmax=1)
            axes[1, j].set_title("GT (evaluation only)")
        elif amap is not None:
            plotted = axes[1, j].imshow(amap, cmap="inferno", vmin=lo, vmax=hi)
            method = {1: "bicubic", 2: "full_swinir", 4: "partial", 5: "uniform"}[j]
            value = rows[method]["per_image_au_pro"]
            axes[1, j].set_title("AU-PRO n/a (normal)" if value is None else f"AU-PRO {value:.4f}")
        else:
            axes[1, j].text(.05, .5, f"Protected area: {protection.mean():.2%}\nSame raw-map color scale\nHard selection, no dilation", fontsize=10)
        for ax in axes[:, j]:
            ax.axis("off")
    fig.suptitle(sample)
    fig.subplots_adjust(left=.01, right=.99, top=.9, bottom=.14, wspace=.08, hspace=.25)
    color_ax = fig.add_axes((.38, .055, .25, .02))
    fig.colorbar(plotted, cax=color_ax, orientation="horizontal", label="Raw PatchCore anomaly score")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def summarize(rows, predictions):
    summary = []
    for method in METHODS:
        selected = [r for r in rows if r["method"] == method]
        anomalous = [r for r in selected if r["label"]]
        deltas = np.asarray([r["delta_au_pro_vs_bicubic"] for r in anomalous])
        item = predictions[method]
        evaluation = (evaluate_predictions(item["labels"], item["scores"], item["masks"], item["maps"])
                      if len(np.unique(item["labels"])) == 2 else None)
        summary.append({
            "method": method, "test_count": len(selected), "anomalous_count": len(anomalous),
            "pooled_au_pro": evaluation["localization"]["au_pro"] if evaluation else None,
            "mean_per_image_au_pro": float(np.mean([r["per_image_au_pro"] for r in anomalous])) if anomalous else None,
            "mean_delta_vs_bicubic": float(deltas.mean()) if anomalous else None,
            "minimum_delta_vs_bicubic": float(deltas.min()) if anomalous else None,
            "negative_count_vs_bicubic": int((deltas < 0).sum()),
            "below_minus_0_01_count": int((deltas < -.01).sum()),
            "mean_psnr": float(np.mean([r["psnr"] for r in selected])),
            "mean_ssim": float(np.mean([r["ssim"] for r in selected])),
            "inference_seconds_sum": float(sum(r["inference_seconds"] for r in selected)),
        })
    a = {r["sample"]: r for r in rows if r["method"] == "full_swinir" and r["label"]}
    comparisons = {}
    for method in ("partial", "uniform"):
        pairs = [r for r in rows if r["method"] == method and r["label"]]
        values = np.asarray([r["delta_au_pro_vs_full"] for r in pairs])
        full_gains = [r for r in pairs if a[r["sample"]]["delta_au_pro_vs_bicubic"] > 0]
        full_losses = [r for r in pairs if a[r["sample"]]["delta_au_pro_vs_bicubic"] < 0]
        comparisons[method] = {
            "mean_delta_vs_full": float(values.mean()) if pairs else None,
            "better_than_full_count": int((values > 0).sum()), "worse_than_full_count": int((values < 0).sum()),
            "full_gain_images_count": len(full_gains),
            "full_gain_images_worsened_count": sum(r["delta_au_pro_vs_full"] < 0 for r in full_gains),
            "summed_gain_sacrifice_on_full_gain_images": sum(max(-r["delta_au_pro_vs_full"], 0) for r in full_gains),
            "full_loss_images_count": len(full_losses),
            "full_loss_images_improved_count": sum(r["delta_au_pro_vs_full"] > 0 for r in full_losses),
        }
    p = [r["delta_au_pro_vs_uniform"] for r in rows if r["method"] == "partial" and r["label"]]
    comparisons["partial_vs_uniform"] = {
        "mean_delta": float(np.mean(p)) if p else None,
        "better_count": sum(v > 0 for v in p), "worse_count": sum(v < 0 for v in p),
    }
    return summary, comparisons


def write_report(out, result, rows):
    """Small numerical report; interpretation stays within this fixed pilot."""
    table = ["| 조건 | 평균 per-image AU-PRO (결함) | pooled AU-PRO | 평균 PSNR | 최악 ΔAU-PRO vs 입력 |",
             "|---|---:|---:|---:|---:|"]
    def fmt(value):
        return "n/a" if value is None else f"{value:.6f}"
    for item in result["summary"]:
        table.append(f"| {item['method']} | {fmt(item['mean_per_image_au_pro'])} | {fmt(item['pooled_au_pro'])} | "
                     f"{item['mean_psnr']:.3f} | {fmt(item['minimum_delta_vs_bicubic'])} |")
    comparisons = result["comparisons"]
    p, u = comparisons["partial"], comparisons["partial_vs_uniform"]
    text = ["# 부분 복원 feasibility 결과", "",
            "기존 개발 데이터의 고정 표본이다. 독립 검증이나 운영 안전성 검증이 아니다.", "",
            f"표본 {len(result['test_paths'])}장. CPU wall time {result['wall_seconds']:.3f}초 "
            f"(초기화 {result['initialization_seconds']:.3f}초 포함). 재학습 0회, 재보정 0회.", "",
            *table, "",
            f"부분 복원 − 전체 복원: 평균 per-image ΔAU-PRO {fmt(p['mean_delta_vs_full'])}. "
            f"좋아진 결함 영상 {p['better_than_full_count']}장, 나빠진 영상 {p['worse_than_full_count']}장.",
            f"부분 복원 − 균일 혼합: 평균 per-image ΔAU-PRO {fmt(u['mean_delta'])}. "
            f"좋아진 영상 {u['better_count']}장, 나빠진 영상 {u['worse_count']}장.", "",
            f"전체 복원이 입력보다 좋아졌던 {p['full_gain_images_count']}장 중 "
            f"{p['full_gain_images_worsened_count']}장에서 부분 복원이 그 이득을 줄였다. "
            f"이 영상들의 AU-PRO 감소량 합은 {p['summed_gain_sacrifice_on_full_gain_images']:.6f}이다.",
            f"전체 복원이 입력보다 나빠졌던 {p['full_loss_images_count']}장 중 "
            f"{p['full_loss_images_improved_count']}장은 부분 복원이 전체 복원보다 높았다.", ""]
    candidates = [r for r in rows if r["method"] == "partial" and r["label"]]
    if candidates:
        text += ["변화가 큰 두 사례를 결과 확인 후 설명용으로 골랐다. 실험 표본 선택은 바꾸지 않았다.", ""]
        for r in (max(candidates, key=lambda r: r["delta_au_pro_vs_full"]),
                  min(candidates, key=lambda r: r["delta_au_pro_vs_full"])):
            full = next(x for x in rows if x["sample"] == r["sample"] and x["method"] == "full_swinir")
            text.append(f"- `{r['sample']}`: 전체 {full['per_image_au_pro']:.6f} → 부분 "
                        f"{r['per_image_au_pro']:.6f}, Δ {r['delta_au_pro_vs_full']:+.6f}.")
    text += ["", "평균 per-image AU-PRO와 pooled AU-PRO는 서로 다른 집계다. 한쪽 증가를 다른 쪽 증가로 표현하지 않는다.",
             "정상 영상에는 per-image AU-PRO를 부여하지 않았다. -0.01은 기술적 손실 크기이며 허용 기준이 아니다.",
             "새 조건의 정상 보정을 하지 않았으므로 F1 또는 고정 FPR의 안전성을 주장하지 않는다.",
             "", "보호 영역과 RGB 구성에 GT를 사용하지 않았다. 두 baseline의 기존 저장 map 재현을 확인했다.",
             "임계값·표본·보호 영역을 결과에 맞춰 변경하지 않았다. 추가 실험은 자동으로 수행하지 않는다."]
    (out / "REPORT.md").write_text("\n".join(text) + "\n", encoding="utf-8")


def run(args, protocol):
    started = perf_counter()
    program_sha256 = branch_b._checksum(Path(__file__))
    torch, transforms, interpolation, _, common, patchcore, _, mvtec = branch_b._official_imports()
    device = torch.device("cpu")
    torch.set_num_threads(min(4, torch.get_num_threads()))
    actual_source = subprocess.check_output(["git", "-C", str(branch_b.PATCHCORE_SOURCE.parent),
                                             "rev-parse", "HEAD"], text=True).strip()
    if actual_source != branch_b.EXPECTED_PATCHCORE_COMMIT:
        raise ValueError("PatchCore source revision mismatch")
    out = args.output_dir or ROOT / "outputs/partial-restoration-feasibility" / ("smoke" if args.smoke else "pilot10")
    out.mkdir(parents=True, exist_ok=False)
    _save_json(out / "protocol.json", protocol)
    shutil.copy2(Path(__file__), out / "program.py")
    print(json.dumps({"stage": "load_frozen_bank", "output": str(out)}), flush=True)
    model = load_frozen_bank(torch, common, patchcore, device)
    restorer = SwinIRLightweight(ROOT / "third_party/SwinIR", CHECKPOINT, device="cpu", scale=4, tile=56, tile_overlap=0)
    resize = transforms.Resize(256, interpolation=interpolation.BILINEAR)
    mask_resize = transforms.Resize(256, interpolation=interpolation.NEAREST)
    crop = transforms.CenterCrop(224)
    tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mvtec.IMAGENET_MEAN, mvtec.IMAGENET_STD)])
    initialization_seconds = perf_counter() - started
    recorded = _read_json(ANCHORS / "results.json")
    calibration = protocol["inputs"]["fusion_calibration"]
    cohort = [protocol["inputs"]["smoke_sample"]] if args.smoke else protocol["inputs"]["cohort"]
    indices = [recorded["test_paths"].index(s) for s in cohort]
    cached = {}
    for name in ("degraded_only", "restored_only"):
        with np.load(ANCHORS / f"{name}_predictions.npz", allow_pickle=False) as archive:
            cached[name] = {key: archive[key][indices] for key in ("maps", "masks", "labels")}
    if not np.array_equal(cached["degraded_only"]["masks"], cached["restored_only"]["masks"]):
        raise ValueError("Unpaired saved GT masks")
    samples = {s.relative_path.as_posix(): s for s in MVTecADFolder(args.data_root, "hazelnut").samples()}
    rows, protection_masks, replay_checks = [], [], []
    predictions = {method: {key: [] for key in ("labels", "scores", "masks", "maps")} for method in METHODS}
    (out / "figures").mkdir()
    for index, name in enumerate(cohort):
        sample_started = perf_counter()
        sample = samples[name]
        with Image.open(sample.path) as source:
            clean = branch_b._canonical(source.convert("RGB"), resize, crop)
        low = clean.resize((56, 56), Image.Resampling.BICUBIC)
        bicubic = low.resize((224, 224), Image.Resampling.BICUBIC)
        timed = start_timer(torch, device)
        restored = restorer.restore(low)
        restoration_seconds = elapsed_seconds(torch, device, timed)
        protection = cached["degraded_only"]["maps"][index] > calibration["pixel_thresholds"]["degraded_only"]
        timed = perf_counter()
        partial, uniform, alpha = compose_rgb(bicubic, restored, protection)
        composition_seconds = perf_counter() - timed
        images = dict(zip(METHODS, (bicubic, restored, partial, uniform)))
        maps, scores, detector_times = {}, {}, {}
        # GT is opened only after the protection mask and both RGB candidates exist.
        if sample.mask_path:
            with Image.open(sample.mask_path) as source:
                mask = np.asarray(branch_b._canonical(source.convert("L"), mask_resize, crop)) > 0
        else:
            mask = np.zeros((224, 224), dtype=bool)
        label = int(sample.metadata["label"])
        if (not np.array_equal(mask, cached["degraded_only"]["masks"][index])
                or label != cached["degraded_only"]["labels"][index]):
            raise ValueError(f"GT/label replay mismatch: {name}")
        for method in METHODS:
            timed = start_timer(torch, device)
            scores[method], maps[method] = branch_b._predict(model, tensor, images[method])
            detector_times[method] = elapsed_seconds(torch, device, timed)
            if method in ("bicubic", "full_swinir"):
                anchor = "degraded_only" if method == "bicubic" else "restored_only"
                params = calibration["pixel"]["degraded" if method == "bicubic" else "restored"]
                difference = np.abs(normalize(maps[method], params) - cached[anchor]["maps"][index])
                if float(difference.max()) > ANCHOR_ATOL:
                    raise ValueError(f"Baseline map replay failed: {name} {method}: {difference.max()}")
                replay_checks.append({"sample": name, "method": method, "max_abs_normalized_map_diff": float(difference.max())})
        metrics = {method: area_under_per_region_overlap(mask[None], maps[method][None], .3, 200)
                   if label else None for method in METHODS}
        sample_rows = {}
        for method in METHODS:
            value = metrics[method]
            row = {"sample": name, "defect_type": sample.relative_path.parts[-2], "label": label,
                   "method": method, "per_image_au_pro": value,
                   "delta_au_pro_vs_full": value - metrics["full_swinir"] if label else None,
                   "delta_au_pro_vs_bicubic": value - metrics["bicubic"] if label else None,
                   "delta_au_pro_vs_uniform": value - metrics["uniform"] if label else None,
                   "protected_fraction": alpha, "image_score_raw": scores[method],
                   **compute_quality_metrics(clean, images[method], ("psnr", "ssim")),
                   "detector_seconds": detector_times[method],
                   "restoration_seconds": 0.0 if method == "bicubic" else restoration_seconds,
                   "composition_seconds_pair": composition_seconds if method in ("partial", "uniform") else 0.0,
                   "selection_detector_seconds": detector_times["bicubic"] if method in ("partial", "uniform") else 0.0,
                   "inference_seconds": detector_times[method] + (restoration_seconds if method != "bicubic" else 0)
                       + (composition_seconds + detector_times["bicubic"] if method in ("partial", "uniform") else 0)}
            rows.append(row)
            sample_rows[method] = row
            for key, val in (("labels", label), ("scores", scores[method]), ("masks", mask), ("maps", maps[method])):
                predictions[method][key].append(val)
        protection_masks.append(protection)
        slug = f"{sample.relative_path.parts[-2]}-{sample.path.stem}"
        for method, image in images.items():
            image.save(out / f"{slug}-{method}.png")
        Image.fromarray(protection.astype(np.uint8) * 255).save(out / f"{slug}-protection.png")
        _panel(out / "figures" / f"{slug}.png", {"clean": clean, **images}, protection, mask, maps, sample_rows, name)
        _write_csv(out / "per_image.csv", rows)
        print(json.dumps({"sample": name, "completed": index + 1, "total": len(cohort),
                          "protected_fraction": alpha, "au_pro": metrics,
                          "sample_wall_seconds": perf_counter() - sample_started}), flush=True)
    predictions = {method: {k: np.asarray(v) for k, v in values.items()} for method, values in predictions.items()}
    for method, values in predictions.items():
        np.savez_compressed(out / f"{method}_predictions.npz", **values)
    np.savez_compressed(out / "protection_masks.npz", masks=np.asarray(protection_masks), samples=np.asarray(cohort))
    summary, comparisons = summarize(rows, predictions)
    _write_csv(out / "summary.csv", summary)
    result = {"scope": protocol["inputs"]["scope"], "smoke": args.smoke,
              "protocol_sha256": branch_b._checksum(PROTOCOL), "program_sha256": program_sha256,
              "actual_device": "cpu", "torch_version": torch.__version__, "initialization_seconds": initialization_seconds,
              "wall_seconds": perf_counter() - started, "fit_seconds_this_run": 0, "calibration_seconds_this_run": 0,
              "prediction_scale": "raw scores, same frozen detector; normalization used only for saved protection/anchor checks",
              "cost_note": "Includes Bicubic selection inference for partial/uniform, shared SwinIR cost; composition times cover both RGB candidates. Cached selection used in this run. Wall time includes initialization, evaluation and plots.",
              "f1_note": "No F1/operating-point safety claim: no new-condition calibration performed",
              "test_paths": cohort, "replay_checks": replay_checks, "summary": summary, "comparisons": comparisons}
    _save_json(out / "results.json", result)
    write_report(out, result, rows)
    print(json.dumps({"stage": "completed", "output": str(out), "comparisons": comparisons}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/external/MVTecAD")
    parser.add_argument("--output-dir", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--smoke", action="store_true")
    modes.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check()
    if args.self_check:
        print("RGB composition endpoint and area-matched control checks passed")
        return
    inputs = frozen_inputs(args.data_root)
    if args.prepare_only:
        PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
        with PROTOCOL.open("x", encoding="utf-8") as handle:
            json.dump({"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "inputs": inputs},
                      handle, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps({"protocol": str(PROTOCOL), "cohort": inputs["cohort"]}), flush=True)
        return
    protocol = _read_json(PROTOCOL)
    if protocol["inputs"] != inputs:
        raise ValueError("Frozen protocol/source fingerprints changed; do not silently reselect or recalibrate")
    run(args, protocol)


if __name__ == "__main__":
    main()
