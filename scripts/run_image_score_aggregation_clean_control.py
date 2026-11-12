"""v0.2 clean control (docs/IMAGE_SCORE_AGGREGATION_V0.2_CLEAN_CONTROL.md): five fixed rules on stored
historical Screw clean/bicubic_x4/swinir_x4 predictions. Image AUROC only (the source run has no calibration).
Read-only, one unit at a time; no model/bank/FAISS. GT masks only for the pixel-AUROC payload anchor.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import image_score_aggregation as agg  # noqa: E402
from sr_anomaly.evaluation import binary_roc_auc, classification_metrics  # noqa: E402
from sr_anomaly.pcb_board_analysis import _budget  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_agg_v01", ROOT / "scripts/run_image_score_aggregation.py")
v01 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v01)

SPEC = "docs/IMAGE_SCORE_AGGREGATION_V0.2_CLEAN_CONTROL.md"
RUN_DIR = "outputs/legacy-patchcore/screw-full320-test160"
VARIANTS = ("clean", "bicubic_x4", "swinir_x4")
FAMILY = "historical_recovery"
CODE = ("scripts/run_image_score_aggregation_clean_control.py", "scripts/run_image_score_aggregation.py",
        "src/sr_anomaly/image_score_aggregation.py", "src/sr_anomaly/evaluation.py", "src/sr_anomaly/pcb_board_analysis.py", SPEC)


class AnchorMismatch(RuntimeError):
    pass


def plan_bytes(n, h, w):
    pixels = n * h * w
    return pixels * 4 + pixels + pixels * 8 * 3 + 64 * 1024**2  # maps f32, masks bool, f64 copy + argsort/ranks, headroom


def process(data_root: Path, variant: str, reference_order: list[str] | None, *, guard=_budget) -> tuple[dict, list[dict]]:
    run = data_root / RUN_DIR
    npz, results_path, per_image_path = run / f"{variant}_predictions.npz", run / "results.json", run / "per_image.csv"
    for p in (npz, results_path, per_image_path):
        if not p.is_file():
            raise FileNotFoundError(f"MISSING_INPUT {RUN_DIR}/{p.name}")
    shapes = v01.npz_shapes(npz)
    if set(shapes) != {"labels", "scores", "masks", "maps"}:
        raise ValueError(f"unexpected npz members {sorted(shapes)}")
    n, h, w = shapes["maps"][0]
    if shapes["maps"][1] != "float32" or shapes["scores"][0] != (n,) or shapes["masks"][0] != (n, h, w):
        raise ValueError(f"unexpected npz schema {shapes}")
    plan = plan_bytes(n, h, w)
    guard(plan, None)
    results = json.loads(results_path.read_bytes())
    stored = results["variants"][variant]["evaluation"]
    with open(per_image_path, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["variant"] == variant]
    t0 = time.perf_counter()
    with np.load(npz, allow_pickle=False) as z:
        arrays = {k: z[k] for k in ("labels", "scores", "masks", "maps")}
    for a in arrays.values():
        a.setflags(write=False)
    if len(rows) != n or [float(r["image_score"]) for r in rows] != arrays["scores"].tolist() \
            or [int(r["label"]) for r in rows] != arrays["labels"].tolist():
        raise ValueError(f"{variant}: per_image.csv differs from npz scores/labels")
    if reference_order is not None and [r["sample"] for r in rows] != reference_order:
        raise ValueError(f"{variant}: test order differs from the realistic Screw test order")
    labels = arrays["labels"]
    # Anchor A
    original_auroc = classification_metrics(labels, arrays["scores"])["image_auroc"]
    if original_auroc != stored["classification"]["image_auroc"]:
        raise AnchorMismatch(f"{variant}: original AUROC {original_auroc} != stored {stored['classification']['image_auroc']}")
    # Anchor B (GT used only to verify the payload)
    pixel_auroc = binary_roc_auc((arrays["masks"] > 0).ravel(), np.asarray(arrays["maps"], dtype=np.float64).ravel())
    if pixel_auroc != stored["localization"]["pixel_auroc"]:
        raise AnchorMismatch(f"{variant}: pixel AUROC {pixel_auroc} != stored {stored['localization']['pixel_auroc']}")
    npz_sha = v01.checksum(npz)
    rules, per_image = {}, []
    for rule in agg.RULES:
        s = agg.aggregate(rule, arrays["maps"], arrays["scores"])
        rules[rule] = {"image_auroc": classification_metrics(labels, s)["image_auroc"],
                       "image_f1": None, "image_false_alarm_rate_test_normal": None, "image_miss_rate_test_anomaly": None}
        for r, x in zip(rows, s):
            per_image.append(dict(unit_id=f"screw__{FAMILY}__{variant}", category="screw", family=FAMILY, variant=variant,
                                  sample=r["sample"], split="test", label=int(r["label"]), rule=rule, raw_score=repr(float(x)),
                                  source_npz_sha256=npz_sha))
    o, m = arrays["scores"].astype(np.float64), agg.aggregate("map_max", arrays["maps"], arrays["scores"])
    record = {"unit_id": f"screw__{FAMILY}__{variant}", "category": "screw", "family": FAMILY, "variant": variant,
              "run_dir": RUN_DIR, "source_public_record": "master historical_recovery (analysis/thesis_synthesis/MASTER_RESULTS.csv)",
              "source_sha256": {"npz": npz_sha, "results_json": v01.checksum(results_path), "per_image_csv": v01.checksum(per_image_path)},
              "npz_schema": {k: {"shape": list(v[0]), "dtype": v[1]} for k, v in shapes.items()}, "memory_plan_bytes": plan,
              "counts": {"calibration": 0, "test_normal": int((labels == 0).sum()), "test_anomaly": int((labels == 1).sum())},
              "k": {r: agg.top_k(f, h, w) for r, f in agg.TOP_FRACTIONS.items()},
              "anchor_a_original_auroc": "EXACT", "anchor_b_pixel_auroc": "EXACT",
              "original_vs_map_max": {"images": n, "exactly_equal": int((o == m).sum()), "pearson": float(np.corrcoef(o, m)[0, 1])},
              "reference_stored": {"au_pro": stored["localization"]["au_pro"], "pixel_auroc": stored["localization"]["pixel_auroc"]},
              "calibration": "none in source run; F1/FPR/miss undefined", "rules": rules, "seconds": time.perf_counter() - t0}
    del arrays
    return record, per_image


def run(data_root: Path, output: Path, *, guard=_budget, reference_csv: Path | None = None, root=ROOT, log=print) -> dict:
    data_root, output = Path(data_root).resolve(), Path(output)
    if output.exists():
        raise FileExistsError("Use a new output directory")
    (output / "units").mkdir(parents=True)
    reference_order = None
    if reference_csv is not None:
        with open(reference_csv, encoding="utf-8", newline="") as f:
            reference_order = [r["sample"] for r in csv.DictReader(f) if r["split"] == "test"]
    protocol = {"protocol": SPEC, "rules": list(agg.RULES), "top_fractions": agg.TOP_FRACTIONS, "units": list(VARIANTS),
                "run_dir": RUN_DIR, "family": FAMILY, "metric_primary": "image_auroc", "calibration": None,
                "reference_order_csv": None if reference_csv is None else "outputs/realistic-degradation/screw-v1/units/none__swinir_x4.csv",
                "code_sha256": {p: v01.checksum(root / p) for p in CODE if (root / p).is_file()}}
    (output / "PROTOCOL.json").write_text(json.dumps(protocol, indent=1), encoding="utf-8")
    session = {"start": datetime.now().astimezone().isoformat(timespec="seconds"), **v01.source_state(root), "units": {}}
    summary = []
    for variant in VARIANTS:
        try:
            rec, per_image = process(data_root, variant, reference_order, guard=guard)
        except MemoryError as e:
            session["units"][variant] = f"BLOCKED_MEMORY: {e}"
            continue
        except FileNotFoundError as e:
            session["units"][variant] = str(e)
            continue
        v01.write_csv(output / "units" / f"{rec['unit_id']}.csv", per_image)
        rec["per_image_csv_sha256"] = v01.checksum(output / "units" / f"{rec['unit_id']}.csv")
        (output / "units" / f"{rec['unit_id']}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        session["units"][variant] = "COMPLETE"
        for rule, r in rec["rules"].items():
            summary.append(dict(unit_id=rec["unit_id"], category="screw", family=FAMILY, variant=variant, rule=rule,
                                k=rec["k"].get(rule, ""), n_test_normal=rec["counts"]["test_normal"],
                                n_test_anomaly=rec["counts"]["test_anomaly"], image_auroc=r["image_auroc"],
                                image_auroc_delta_vs_original=r["image_auroc"] - rec["rules"]["original"]["image_auroc"],
                                image_f1="", reference_au_pro=rec["reference_stored"]["au_pro"],
                                anchor_a=rec["anchor_a_original_auroc"], anchor_b=rec["anchor_b_pixel_auroc"],
                                source_npz_sha256=rec["source_sha256"]["npz"]))
        log(json.dumps({"unit": rec["unit_id"], "auroc": {k: round(v["image_auroc"], 4) for k, v in rec["rules"].items()},
                        "seconds": round(rec["seconds"], 2)}))
    v01.write_csv(output / "summary.csv", summary)
    session.update(end=datetime.now().astimezone().isoformat(timespec="seconds"),
                   units_complete=sum(v == "COMPLETE" for v in session["units"].values()), units_planned=len(VARIANTS),
                   cells=len(summary))
    (output / "sessions").mkdir()
    (output / "sessions" / "000.json").write_text(json.dumps(session, indent=1), encoding="utf-8")
    return session


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--reference-test-csv", type=Path, help="realistic Screw per-image CSV whose test order must match")
    a = p.parse_args(argv)
    s = run(a.data_root, a.output, reference_csv=a.reference_test_csv)
    print(json.dumps({k: s[k] for k in ("units_complete", "units_planned", "cells")}))
    return 0 if s["units_complete"] == s["units_planned"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
