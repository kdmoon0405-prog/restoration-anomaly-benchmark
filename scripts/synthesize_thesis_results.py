"""Read-only synthesis of stored evidence; no models, fitting, or inference."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from aggregate_category_results import _json, _summary, _table, _value  # noqa: E402

DESTINATION = ROOT / "analysis/thesis_synthesis"
FULL = ROOT / "analysis/restoration_objective_full/derived"
FIELDS = ("study_family", "dataset", "variant", "degradation_protocol", "train_count", "test_count",
          "psnr", "ssim", "lpips", "image_auroc", "pixel_auroc", "aupro", "source_artifact", "notes")
QUALITY = {"psnr": "mean_psnr", "ssim": "mean_ssim", "lpips": "mean_lpips",
           "image_auroc": "image_auroc", "pixel_auroc": "pixel_auroc", "aupro": "au_pro"}
TAUS = (0, 0.005, 0.01, 0.02, 0.05)


def csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def magnitude_counts(values: list[float]) -> dict:
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("Magnitude reporting requires finite nonempty deltas")
    return {"n": len(values), **{f"loss_gt_{tau:g}": sum(value < -tau for value in values) for tau in TAUS},
            "absolute_delta_le_0.01": sum(abs(value) <= 0.01 for value in values)}


def master_rows() -> list[dict]:
    rows = []
    reporting = {row["category"]: row for row in csv_rows(ROOT / "analysis/reporting/category_summary.csv")}
    for category, train, test in (("hazelnut", 391, 110), ("screw", 320, 160)):
        source = DESTINATION / "sources" / f"{category}_summary.csv"
        summary = _summary(source)
        if set(summary) != {"clean", "bicubic_x4", "swinir_x4"}:
            raise ValueError(f"Unexpected historical variants: {category}")
        for variant, stored in summary.items():
            if (int(stored["train_count"]), int(stored["test_count"])) != (train, test):
                raise ValueError(f"Historical cohort mismatch: {category}")
            values = {name: _value(stored, field) for name, field in QUALITY.items()}
            if variant != "clean":
                prefix = "bicubic" if variant == "bicubic_x4" else "swinir"
                for metric, source_metric in (("psnr", "psnr"), ("ssim", "ssim"), ("image_auroc", "image_auroc"),
                                              ("pixel_auroc", "pixel_auroc"), ("aupro", "au_pro")):
                    if not math.isclose(values[metric], float(reporting[category][f"{prefix}_{source_metric}"]), abs_tol=1e-12, rel_tol=0):
                        raise ValueError(f"Historical snapshot/report disagreement: {category} {variant} {metric}")
            rows.append({"study_family": "historical_recovery", "dataset": category, "variant": variant,
                         "degradation_protocol": "none" if variant == "clean" else "Pillow bicubic x4 224->56->224",
                         "train_count": train, "test_count": test, **values,
                         "source_artifact": source.relative_to(ROOT).as_posix(),
                         "notes": "Branch A category-specific bank; LPIPS not measured; Clean quality not applicable" if variant == "clean"
                         else "Branch A category-specific bank; LPIPS not measured; do not mix with MATLAB-Bicubic"})
    full = _json(FULL / "analysis_summary.json")
    if (full["study"], full["anomalous_images"]) != ("restoration_objective_full", 70):
        raise ValueError("Unexpected endpoint study")
    for stored in full["aggregate_methods"]:
        if tuple(int(stored[key]) for key in ("test_count", "normal_count", "anomaly_count")) != (110, 40, 70):
            raise ValueError("Endpoint cohort mismatch")
        rows.append({"study_family": "endpoint_full110", "dataset": "hazelnut", "variant": stored["variant"],
                     "degradation_protocol": "BasicSR MATLAB-compatible bicubic x4 224->56->224",
                     "train_count": 391, "test_count": 110,
                     **{name: _value(stored, field) for name, field in QUALITY.items()},
                     "source_artifact": "analysis/restoration_objective_full/derived/analysis_summary.json",
                     "notes": "Frozen reused 391-normal bank; no fit; no Clean fifth endpoint; F1/threshold absent"})
    if len(rows) != 10 or len({(row["study_family"], row["dataset"], row["variant"]) for row in rows}) != 10:
        raise ValueError("Master table requires six historical and four endpoint rows")
    return rows


def recovery_rows(rows: list[dict]) -> list[dict]:
    result = []
    for category in ("hazelnut", "screw"):
        variants = {row["variant"]: row for row in rows if row["study_family"] == "historical_recovery" and row["dataset"] == category}
        clean, bic, swin = (variants[name] for name in ("clean", "bicubic_x4", "swinir_x4"))
        loss, recovery = clean["aupro"] - bic["aupro"], swin["aupro"] - bic["aupro"]
        result.append({"category": category,
                       **{f"{label}_{key}": variant[key] for label, variant in (("clean", clean), ("bicubic", bic), ("swinir", swin))
                          for key in ("image_auroc", "pixel_auroc", "aupro")},
                       "degradation_loss": loss, "restoration_delta": recovery,
                       "fraction_of_loss_recovered": recovery / loss if loss > 0 else None})
    return result


def synthesis(rows: list[dict]) -> str:
    full = _json(FULL / "analysis_summary.json")
    boot = _json(FULL / "endpoint_bootstrap.json")
    endpoint = [row for row in rows if row["study_family"] == "endpoint_full110"]
    magnitude = []
    historical_cells = []
    for category in ("hazelnut", "screw"):
        data = csv_rows(ROOT / "analysis" / category / "regression_taxonomy.csv")
        magnitude.append({"study": f"historical {category}", "variant": "swinir_x4", "status": "POST-HOC MAGNITUDE SENSITIVITY",
                          **magnitude_counts([float(row["delta_per_image_aupro"]) for row in data])})
        delta_gap = [(float(row["delta_per_image_aupro"]), float(row["delta_roi_bg_gap"])) for row in data]
        historical_cells.append({"study": category, "regression_gap_negative": sum(delta < 0 and gap < 0 for delta, gap in delta_gap),
                                 "regression_gap_nonnegative": sum(delta < 0 and gap >= 0 for delta, gap in delta_gap),
                                 "non_regression_gap_negative": sum(delta >= 0 and gap < 0 for delta, gap in delta_gap),
                                 "non_regression_gap_nonnegative": sum(delta >= 0 and gap >= 0 for delta, gap in delta_gap)})
    for dist in csv_rows(FULL / "localization_delta_distribution.csv"):
        sensitivity = [row for row in csv_rows(FULL / "magnitude_sensitivity.csv") if row["variant"] == dist["variant"]]
        magnitude.append({"study": "endpoint full110", "variant": dist["variant"], "status": "preregistered",
                          "n": int(dist["anomaly_count"]),
                          **{f"loss_gt_{float(row['tau']):g}": int(row["count_delta_lt_minus_tau"]) for row in sensitivity},
                          "absolute_delta_le_0.01": int(dist["absolute_delta_le_0_01_count"])})
    rho = [{"variant": variant, "psnr_gain_rho": values["psnr_gain_vs_bicubic"],
            "lpips_improvement_rho": values["lpips_improvement_vs_bicubic"],
            "baseline_aupro_delta_rho": full["baseline_aupro_vs_delta_spearman_descriptive"][variant]}
           for variant, values in full["spearman_descriptive"].items()]
    fusion = csv_rows(ROOT / "analysis/hazelnut/fusion_weight_search/fusion_weight_search.csv")
    fusion_table = [{"alpha": float(row["alpha"]), "pooled_aupro": float(row["pooled_au_pro"]),
                     "delta_vs_restored": float(row["delta_pooled_au_pro_vs_restored"])} for row in fusion]
    return f"""# Thesis synthesis

작성일: 2026-10-03. 결과 기준 commit: `2dcac3f2c0c8418e2909641c473cd9498600929e`. 실험 단계는 종료됐다. 이 문서와 master CSV는 기존 저장 표에서 집계했으며 inference·metric implementation·분석 규칙을 바꾸지 않았다.

## 1. 최종 연구 질문

검사 전 영상 복원에서 화질 개선과 이상 localization 개선이 이미지마다 일치하지 않을 때, 복원 성능을 어떻게 평가해야 하는가? 범위는 MVTec AD의 고정 x4 해상도 저하와 고정 PatchCore다.

## 2. 연구 방향의 변화

초기에는 복원이 결함 증거를 약화할 수 있다는 가설을 검토했다. Hazelnut에서 평균 localization 개선과 개별 음수 delta가 함께 관측됐다. 작은 oracle headroom과 고정 global fusion의 음성 결과는 단순 branch 결합의 한계를 남겼다. 사전 지정 Screw stress test도 평균 회복과 음수 delta의 공존을 보였지만 magnitude와 taxonomy 구성은 달랐다. 선택 NN-distance 분석은 독립 mechanism 증거가 아니라 consistency diagnostic으로 제한했다. RRDB pilot의 품질 차이와 작은 혼합 localization 신호를 full110에서 확인한 결과는 B/B-uncertain이었다. 최종 기여는 regression 존재 자체보다 변화의 크기·분포·baseline 연관과 quality–localization 관계를 함께 보고하는 평가 구성이다.

## 3. 두 실험 family와 데이터 범위

- A, historical recovery: Pillow bicubic `224→56→224`, Clean/Bicubic/SwinIR. Hazelnut 391 train/110 test, Screw 320 train/160 test. 카테고리마다 별도 normal bank이며 각 paired 비교 안에서는 동일 bank다. Clean은 이 family의 no-degradation reference다.
- B, endpoint full110: BasicSR MATLAB-compatible bicubic, Bicubic/SwinIR/RRDB-PSNR/RRDB-ESRGAN. Hazelnut 110 test(40 normal/70 anomaly), 기존 391-normal bank 재사용, fit 없음. 같은 LR bytes를 모든 learned model에 입력했다.

두 Bicubic kernel의 수치를 합치거나 서로 빼지 않는다. Historical Clean은 B의 byte-proven 다섯 번째 method가 아니다. Branch B fusion(313 fit/78 calibration)은 A와 다른 bank의 별도 supporting ablation이다. 모델 source·checkpoint·bank·manifest 해시는 기존 protocol/execution record를 따른다. Primary는 pooled AU-PRO@0.3(기존 200 thresholds), secondary는 Image/Pixel AUROC와 화질이다. GT는 inference 이후 evaluation에만 사용했다.

## 4. Table A: historical controlled degradation/recovery

{_table(recovery_rows(rows), tuple(recovery_rows(rows)[0]))}

`degradation_loss = Clean − Bicubic`, `restoration_delta = SwinIR − Bicubic`이며 둘 다 pooled AU-PRO 단위다. `fraction_of_loss_recovered = restoration_delta/degradation_loss`는 분모가 양수일 때만 계산한 descriptive fraction이다. 표준 문헌 metric이나 통계검정이 아니다. 두 카테고리에서 SwinIR이 저하된 localization의 일부를 평균적으로 회복했지만 Clean 수준에는 도달하지 않았다. 이 설정 밖의 전체 SR 성능으로 일반화하지 않는다.

숫자의 직접 입력은 [보존 Hazelnut summary](sources/hazelnut_summary.csv), [보존 Screw summary](sources/screw_summary.csv)다. 작은 원본 CSV 사본의 row 값은 기존 [reporting CSV](../reporting/category_summary.csv)와 대조했다. 원본 summary SHA-256: Hazelnut `05c12b549783733e98e5835a94a9408b2a6cc645bf7e6a4da38ad39b525fb78f`; Screw `9f0087fdb538c4a5c2f9f271229492909405e6c524b919b8a14ba125c6e118af`(기존 Screw ledger와 일치). 사본의 line endings는 Git에서 달라질 수 있으며 위 digest를 사본 hash라고 부르지 않는다. NPZ는 포함하지 않았다.

## 5. Sample-level 변화와 magnitude

{_table(magnitude, tuple(magnitude[0]))}

`loss_gt_tau`는 `delta < -tau`, 마지막 열은 `|delta| <= 0.01`의 이미지 수다. 각 행의 n은 anomalous-image denominator다. Historical tau 집계는 tracked per-image CSV에서 계산한 **post-hoc** sensitivity이며, full110 tau는 결과 전에 고정됐다. 0.01을 검증된 산업 failure threshold로 취급하지 않는다. Hazelnut의 많은 strict-sign 감소가 작은 크기에 머무는 반면 Screw에는 더 큰 음수 tail이 있다. Screw의 strict-sign 비율이 더 낮다는 사실과 큰 감소의 존재를 함께 보고한다. 두 카테고리의 공식적인 분포 차이 검정이나 일반 defect 위험도 추정은 하지 않았다.

Full110의 [delta distribution](../restoration_objective_full/derived/localization_delta_distribution.csv)은 min/Q25/median/Q75/max와 near-zero 비율을 기록한다. 평균 pooled 회복은 모든 이미지의 개선을 보장하지 않는다. Pooled AU-PRO와 mean per-image AU-PRO는 서로 다른 estimand다.

## 6. Baseline/ceiling association

{_table(csv_rows(FULL / 'baseline_tercile_regression.csv'), ('variant', 'baseline_group', 'image_count', 'mean_bicubic_per_image_aupro', 'mean_delta_per_image_aupro', 'strict_regression_rate', 'delta_lt_minus_0_01_rate'))}

이미지는 Bicubic per-image AU-PRO와 lexical path 순으로 나누었고 group 크기는 23/23/24다. 높은 baseline group은 개선 여지가 작고 strict-sign 감소 비율이 높다. 하지만 큰 감소(`delta < -0.01`)의 비율은 높은 baseline group에서 낮다. 부호만으로 practical failure를 주장할 수 없다. 이는 descriptive baseline/ceiling association이며 regression-to-the-mean causality나 mechanism 증거가 아니다.

## 7. Quality와 localization의 관계

{_table(rho, tuple(rho[0]))}

Anomaly 70장의 모델별 PSNR gain/LPIPS improvement와 AU-PRO gain의 Spearman이다. Baseline rho도 descriptive다. 이 controlled setup에서 개별 이미지의 화질 개선은 localization 개선과 일관되게 동행하지 않았다. 네 method의 평균 ordering은 per-image predictive reliability가 아니다. rho 성공 임계값, 인과 해석, PSNR/LPIPS가 일반적으로 무효라는 주장은 없다. Source: [summary JSON](../restoration_objective_full/derived/analysis_summary.json), [paired quality CSV](../restoration_objective_full/derived/quality_localization.csv).

## 8. Table B: full110 endpoint comparison

{_table(endpoint, ('variant', 'psnr', 'ssim', 'lpips', 'image_auroc', 'pixel_auroc', 'aupro'))}

RRDB-ESRGAN minus RRDB-PSNR: `P={full['pooled_delta_aupro_esrgan_minus_psnr']:+.9f}`, `D70={full['direct_per_image_aupro']['mean']:+.9f}`, paired CI `[{boot['ci95'][0]:+.9f}, {boot['ci95'][1]:+.9f}]`, `D50={full['pilot_unseen_within_category']['mean']:+.9f}`.

판정은 **{full['localization_case']} / {full['localization_b_description']}**다. P/D70/D50의 방향은 양수지만 CI가 0을 포함한다. 이는 ESRGAN localization 우월성도 equivalence도 입증하지 않는다. B-small이 아닌 이유는 CI 전체가 ±0.01 안에 들어오지 않기 때문이다. P는 point estimate이며 CI는 D70의 uncertainty다.

품질 trade-off는 별도 재현됐다: mean ΔPSNR `{full['mean_delta_psnr_esrgan_minus_psnr']:+.6f} dB`, mean ΔLPIPS `{full['mean_delta_lpips_esrgan_minus_psnr']:+.6f}`. 낮은 LPIPS가 더 좋다. 공식 checkpoint는 objective와 학습 데이터(DF2K/DF2K+OST)가 모두 달라 objective-only 인과 분리가 아니다. 품질 특성 차이는 관측됐지만 안정적인 localization ranking은 확립되지 않았다.

## 9. Overlap와 unseen subset

Pilot20 overlap은 {full['pilot_overlap_reproducibility']['compared_values']}개 값을 비교했고 max absolute difference `{full['pilot_overlap_reproducibility']['max_absolute_difference']:.3g}`, 허용오차 `atol=rtol=1e-5`에서 mismatch {full['pilot_overlap_reproducibility']['mismatch_count']}개다. Bitwise 동일이 아니라 numerical tolerance 내 재현이다. Pilot-unseen50 D50은 같은 방향이고 unseen85(35 normal/50 anomaly) direct pooled delta는 `{full['pilot_unseen85']['pooled_delta_aupro_esrgan_minus_psnr']:+.9f}`다. 둘 다 같은 development category 내부이며 독립 외부 검증이 아니다. 25장 pilot과 full110은 overlap 때문에 독립된 두 반복으로 세지 않는다.

## 10. Supporting negative ablation과 map diagnostics

{_table(fusion_table, tuple(fusion_table[0]))}

Branch B의 사전 고정 5점 alpha(0은 restored-only)에서 primary pooled AU-PRO 최선은 alpha=0이었다. 내부 fusion weight들은 복원 단독을 넘지 못했다. 단순 global scalar 결합의 feasibility ablation은 음성 결과였으나 모든 fusion 방법이 불가능하다는 뜻은 아니다. 기존 max 결과도 restored-only를 넘지 못했다는 기록은 [PROGRESS](../../PROGRESS.md)의 Branch B에 있다. Fine search와 gating을 다시 열지 않는다.

Historical supporting 2×2(행: regression/non-regression, 열: negative/nonnegative gap):

{_table(historical_cells, tuple(historical_cells[0]))}

Full110 supporting 2×2:

{_table(csv_rows(FULL / 'taxonomy_contingency.csv'), ('variant', 'regression_gap_negative', 'regression_gap_nonnegative', 'non_regression_gap_negative', 'non_regression_gap_nonnegative'))}

Taxonomy는 post-inference anomaly-map pattern이다. Gap 감소가 non-regression에서도 나타나므로 regression-specific mechanism 분류가 아니다. [Hazelnut selected NN](../hazelnut/nn_distance_selected_summary.md)은 subtype별 n=3에서 완전한 분리를 보이지 않았고, [Screw selected NN](../screw/nn_distance_selected_summary.md)의 n=3 suppression 패턴은 relative feature normalization과 일치하는 selected-case 관측이다. Anomaly map 자체가 NN 거리에서 만들어지므로 독립 mechanism 증거가 아니다. Population/causal 결론이나 추가 NN 분석으로 확장하지 않는다.

## 11. 지지되는 주장과 한계

이 설정에서 x4 resolution loss는 localization을 낮추고 SwinIR은 그 일부를 평균적으로 회복했다. 평균 회복과 heterogeneous sample-level delta는 함께 존재한다. Magnitude·baseline·category 맥락을 포함해야 strict-sign count를 practical failure rate로 오해하지 않는다. Endpoint 품질 차이는 재현됐지만 stable downstream superiority는 확립되지 않았다. 각 주장의 근거와 표현 범위는 [claim matrix](CLAIM_EVIDENCE_MATRIX.md)에 연결한다.

Real-camera/industrial acquisition 검증, 다른 detector, untouched category final validation은 없다. Hazelnut은 development, Screw는 사전 지정 stress category다. Capsule은 사용하지 않았다. Category-specific bank 한 개씩과 seed 11의 fixed setup이며 seed/bank uncertainty를 추정하지 않았다. [limitations](LIMITATIONS_AND_BOUNDARIES.md)에 전체 경계를 기록한다. 신뢰구간이 0을 포함한다는 사실은 두 endpoint가 같다는 증거가 아니다.

## 12. 최종 기여와 논문/발표 구성

Controlled resolution degradation에서 복원은 평균 anomaly localization을 회복하면서 이미지별로 서로 다른 변화를 만든다. 검사 전 복원 평가는 평균 화질·localization뿐 아니라 sample-level localization 변화의 크기와 분포를 함께 보고해야 한다. 후속 endpoint 비교는 fidelity–perceptual 품질 차이를 재현했으나 안정적인 localization ranking을 확립하지 못했다. 새로운 detector나 mitigation method를 제안한 연구로 포장하지 않는다.

발표 순서: 연구 질문/고정 detector → Table A와 recovery figure → delta waterfall/magnitude → baseline와 quality association → 별도 Table B와 case B → supporting negative ablation → limitations/최종 기여. Taxonomy/NN 상세는 appendix에 둔다. [Figure index](FIGURE_INDEX.md)의 caption/제한을 따른다.

제목 후보(추천 순):

1. 제어된 해상도 저하에서 영상 복원과 이상 localization의 평균 및 이미지별 변화 평가
2. 이상 검사를 위한 영상 복원 평가: 화질과 localization 변화의 크기 및 분포
3. 고정 PatchCore 검사에서 영상 복원의 품질–localization 관계 분석

## 13. 재현과 연구 종료

`python scripts/synthesize_thesis_results.py`는 tracked CSV/JSON만 읽고 master 표, 이 문서, recovery figure를 만든다. 기존 inference/분석 artifact는 바꾸지 않는다. Runtime 문단 정정은 서로 다른 timing scope를 섞은 설명만 고친 것이며 metric/hash/provenance/case는 유지했다. 원본 full110 NPZ는 이 checkout에 전달되지 않아 독립 재검증하지 않았고, 실행 머신의 tracked 검증 기록과 derived 결과를 대조했다.

No additional research experiment was run. The experimental phase remains closed. 후속 업무는 논문·발표 작성과 저장 evidence 검토뿐이다.
"""


def recovery_figure(rows: list[dict], destination: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, ax = plt.subplots(figsize=(8, 4.5))
    for index, variant in enumerate(("clean", "bicubic_x4", "swinir_x4")):
        values = [next(row["aupro"] for row in rows if row["study_family"] == "historical_recovery" and row["dataset"] == category and row["variant"] == variant)
                  for category in ("hazelnut", "screw")]
        bars = ax.bar([category + (index - 1) * 0.24 for category in (0, 1)], values, width=0.24, label=variant)
        ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
    ax.set(xticks=[0, 1], xticklabels=["Hazelnut", "Screw"], ylim=(0, 1.06), ylabel="Pooled AU-PRO@0.3",
           title="Historical Pillow x4 degradation and recovery")
    ax.legend(loc="lower right")
    figure.tight_layout()
    destination.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination / "controlled_recovery_aupro.png", dpi=160)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DESTINATION)
    args = parser.parse_args()
    rows = master_rows()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "MASTER_RESULTS.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "THESIS_SYNTHESIS.md").write_text(synthesis(rows), encoding="utf-8")
    recovery_figure(rows, args.output / "figures")
    print(json.dumps({"master_rows": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
