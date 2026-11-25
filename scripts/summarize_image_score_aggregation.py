"""Derived tables from an image-score aggregation summary.csv (all rows kept; nothing selected).

auroc_by_rule.csv: one row per unit, image AUROC per rule and rule - original.
restorer_contrasts_by_rule.csv: SwinIR - Bicubic (primary) and RealESRNet/RealESRGAN - SwinIR per realization and rule.
"""
import argparse
import csv
from pathlib import Path

RULES = ("original", "map_max", "top0.1pct_mean", "top0.5pct_mean", "top1pct_mean")
CONTRASTS = (("swinir_x4", "bicubic_x4"), ("realesrnet_x4plus", "swinir_x4"), ("realesrgan_x4plus", "swinir_x4"))
METRICS = ("image_auroc", "image_f1", "image_false_alarm_rate_test_normal", "image_miss_rate_test_anomaly")


def load(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def realization(r):
    return "v1" if r["family"] == "realistic_lr_v1" else f"noise{r['noise_seed']}"


def write(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def derive(summary):
    cells = {(r["category"], realization(r), r["condition"], r["restorer"], r["rule"]): r for r in summary}
    units = list(dict.fromkeys(k[:4] for k in cells))
    by_rule = []
    for u in units:
        row = dict(zip(("category", "realization", "condition", "restorer"), u))
        row["reference_au_pro"] = cells[(*u, "original")]["reference_au_pro"]
        for m in METRICS:
            for rule in RULES:
                row[f"{m}__{rule}"] = cells[(*u, rule)][m]
        for rule in RULES[1:]:
            row[f"image_auroc_delta_vs_original__{rule}"] = float(cells[(*u, rule)]["image_auroc"]) - float(cells[(*u, "original")]["image_auroc"])
        by_rule.append(row)
    contrasts = []
    for cat, real, cond in dict.fromkeys(u[:3] for u in units):
        for a, b in CONTRASTS:
            if (cat, real, cond, a, "original") not in cells or (cat, real, cond, b, "original") not in cells:
                continue
            row = dict(category=cat, realization=real, condition=cond, contrast=f"{a} - {b}",
                       primary=int((a, b) == CONTRASTS[0]))
            for rule in RULES:
                row[f"image_auroc_delta__{rule}"] = float(cells[(cat, real, cond, a, rule)]["image_auroc"]) - float(cells[(cat, real, cond, b, rule)]["image_auroc"])
            row["reference_au_pro_delta"] = float(cells[(cat, real, cond, a, "original")]["reference_au_pro"]) - float(cells[(cat, real, cond, b, "original")]["reference_au_pro"])
            contrasts.append(row)
    return by_rule, contrasts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    a.output.mkdir(parents=True, exist_ok=True)
    by_rule, contrasts = derive(load(a.summary))
    write(a.output / "auroc_by_rule.csv", by_rule)
    write(a.output / "restorer_contrasts_by_rule.csv", contrasts)
    print(len(by_rule), len(contrasts))


if __name__ == "__main__":
    main()
