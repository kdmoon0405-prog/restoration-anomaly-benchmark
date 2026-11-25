"""Analyze a saved Screw restoration-endpoint run with the frozen Hazelnut helpers; never run inference.

Rules: docs/RESTORATION_ENDPOINT_SCREW.md. The frozen `analyze()` computes every shared table; this wrapper only
registers the Screw manifest, removes Hazelnut-pilot-only fields, applies the Screw A/B/C rule (no D50 analogue), and
adds the defect-type table and the Hazelnut direction comparison.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import analyze_restoration_endpoint_full as frozen  # noqa: E402

STUDY = "restoration_objective_screw"
SCREW_MANIFEST = ("analysis/restoration_objective_screw/full_manifest.csv",
                  "b680d6714fd9e1ca222ef4a5192478fd970c0b2dc70c5672d9c7aeb7e2bd51ec", 160, 41, 119)
HAZELNUT_DERIVED = ROOT / "analysis" / "restoration_objective_full" / "derived" / "analysis_summary.json"
COMPARED = ("mean_psnr", "mean_ssim", "mean_lpips", "au_pro", "pixel_auroc", "image_auroc")


def _sign(value: float | None) -> str | None:
    return None if value is None else "+" if value > 0 else "-" if value < 0 else "0"


def defect_table(run_dir: Path) -> list[dict]:
    pair = frozen._read_csv(run_dir / "objective_pair_per_image.csv", ("sample", "defect_type", "label", "delta_per_image_aupro_esrgan_minus_psnr"))
    rows = []
    for defect in sorted({row["defect_type"] for row in pair if row["label"] == "1"}):
        group = [row for row in pair if row["defect_type"] == defect]
        values = np.asarray([frozen._number(row, "delta_per_image_aupro_esrgan_minus_psnr") for row in group])
        rows.append({"defect_type": defect, **frozen.sign_summary(values),
                     **{f"mean_delta_{key}_esrgan_minus_psnr": float(np.mean([frozen._number(row, f"delta_{key}_esrgan_minus_psnr") for row in group]))
                        for key in ("psnr", "ssim", "lpips", "per_image_pixel_auroc", "roi_bg_gap")}})
    return rows


def compare_hazelnut(screw: dict, hazelnut: dict) -> list[dict]:
    def deltas(analysis):
        by = {row["variant"]: row for row in analysis["aggregate_methods"]}
        return {key: float(by["rrdb_esrgan_x4"][key]) - float(by["rrdb_psnr_x4"][key]) for key in COMPARED}
    s, h = deltas(screw), deltas(hazelnut)
    rows = [{"quantity": f"delta_{key}_esrgan_minus_psnr", "hazelnut": h[key], "screw": s[key],
             "hazelnut_sign": _sign(h[key]), "screw_sign": _sign(s[key]),
             "direction": "agree" if _sign(h[key]) == _sign(s[key]) else "disagree"} for key in COMPARED]
    hm, sm = hazelnut["direct_per_image_aupro"]["mean"], screw["direct_per_image_aupro"]["mean"]
    rows.append({"quantity": "mean_paired_per_image_aupro_delta_D", "hazelnut": hm, "screw": sm, "hazelnut_sign": _sign(hm),
                 "screw_sign": _sign(sm), "direction": "agree" if _sign(hm) == _sign(sm) else "disagree"})
    rows.append({"quantity": "localization_case", "hazelnut": hazelnut["localization_case"], "screw": screw["localization_case"],
                 "hazelnut_sign": None, "screw_sign": None,
                 "direction": "agree" if hazelnut["localization_case"] == screw["localization_case"] else "disagree"})
    return rows


def analyze(run_dir: Path) -> tuple[dict, dict, dict[str, list[dict]], dict]:
    frozen.MANIFESTS[STUDY] = SCREW_MANIFEST
    analysis, boot, tables, plot_data = frozen.analyze(run_dir)
    if analysis["study"] != STUDY:
        raise ValueError("Not a Screw endpoint run")
    for row in tables["quality_localization"]:
        row.pop("pilot_overlap")  # Hazelnut pilot field; meaningless for Screw.
    tables["endpoint_pair_sensitivity"] = [r for r in tables["endpoint_pair_sensitivity"] if r["subset"] == "all_anomalies"]
    ci = tuple(boot["ci95"])
    mean = analysis["direct_per_image_aupro"]["mean"]
    case = frozen.classify_case(analysis["pooled_delta_aupro_esrgan_minus_psnr"], mean, ci, mean)  # D stands in for D50.
    for key in ("pilot_overlap_reproducibility", "pilot_unseen_within_category", "pilot_unseen85"):
        analysis.pop(key)
    tables["defect_type_endpoint"] = defect_table(run_dir)
    analysis.update(localization_case=case, localization_b_description=frozen.b_description(ci) if case == "B" else None,
                    case_rule="A: P>0,D>0,CI.lower>0; C: P<0,D<0,CI.upper<0; else B (no D50 analogue)",
                    sensitivity_status="pre-registered in docs/RESTORATION_ENDPOINT_SCREW.md before Screw inference",
                    defect_type_endpoint=tables["defect_type_endpoint"])
    hazelnut = json.loads(HAZELNUT_DERIVED.read_text(encoding="utf-8"))
    tables["hazelnut_direction"] = compare_hazelnut(analysis, hazelnut)
    analysis["hazelnut_direction"] = tables["hazelnut_direction"]
    return analysis, boot, tables, plot_data


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Analysis output directory is not empty: {output}")
    analysis, boot, tables, plot_data = analyze(args.run_dir.resolve())
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis_summary.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "endpoint_bootstrap.json").write_text(json.dumps(boot, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, rows in tables.items():
        frozen._write_csv(output / f"{name}.csv", rows)
    frozen._figures(output, tables, plot_data)
    print(json.dumps({"study": STUDY, "output": str(output), "localization_case": analysis["localization_case"],
                      "direct_per_image_aupro": analysis["direct_per_image_aupro"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
