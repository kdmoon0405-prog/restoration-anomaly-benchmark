"""Re-aggregate stored post-processed maps into image scores (protocol docs/IMAGE_SCORE_AGGREGATION_V0.1.md).

Reads existing realistic v1/v2 unit payloads read-only, one unit at a time. No model/bank/FAISS/GT/RGB.
Writes per-unit receipts + per-image rows, then summary.csv with all 40 units x 5 rules.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

import numpy as np
from numpy.lib import format as npy_format

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import image_score_aggregation as agg  # noqa: E402
from sr_anomaly.pcb_board_analysis import _budget  # noqa: E402

SPEC = "docs/IMAGE_SCORE_AGGREGATION_V0.1.md"
CODE = ("scripts/run_image_score_aggregation.py", "src/sr_anomaly/image_score_aggregation.py",
        "src/sr_anomaly/fusion.py", "src/sr_anomaly/evaluation.py", "src/sr_anomaly/pcb_board_analysis.py", SPEC)
PUBLIC_RECORD = {"realistic_lr_v1": "exp/pcb-full-cohort-juhyung@4c2fc40:analysis/realistic_degradation",
                 "realistic_lr_noise_v2": "handoff/juhyung:handoff/returns/juhyung/realistic-noise-v2-{category}-noise{noise_seed}"}
ANCHOR_A_KEYS = ("image_auroc", "image_f1", "image_threshold", "image_false_alarm_rate_test_normal", "image_miss_rate_test_anomaly")


def checksum(path: Path) -> str:
    h = sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def source_state(root=ROOT) -> dict:
    def git(*a):
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()
    status = git("status", "--porcelain", "--untracked-files=no")
    untracked = [line for line in git("status", "--porcelain", "--untracked-files=normal").splitlines() if line.startswith("??")]
    return dict(source_commit=git("rev-parse", "HEAD"), source_branch=git("rev-parse", "--abbrev-ref", "HEAD"),
                tracked_worktree_dirty=bool(status), tracked_dirty_paths=status.splitlines(),
                source_worktree_dirty=bool(status) or bool(untracked), untracked_paths=untracked)


def npz_shapes(path: Path) -> dict:
    """Shapes/dtypes from .npy headers without loading arrays."""
    out = {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            with z.open(info) as f:
                version = npy_format.read_magic(f)
                reader = npy_format.read_array_header_1_0 if version == (1, 0) else npy_format.read_array_header_2_0
                shape, fortran, dtype = reader(f)
                out[info.filename[:-4]] = (tuple(shape), str(dtype), bool(fortran))
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class AnchorMismatch(RuntimeError):
    pass


def _expected_schema(shapes):
    need = {"calibration_maps", "test_maps", "calibration_scores", "test_scores"}
    if set(shapes) != need:
        raise ValueError(f"unexpected npz members {sorted(shapes)}")
    (nc, h, w), (nt, h2, w2) = shapes["calibration_maps"][0], shapes["test_maps"][0]
    if (h, w) != (h2, w2) or shapes["calibration_scores"][0] != (nc,) or shapes["test_scores"][0] != (nt,):
        raise ValueError("npz shapes are not aligned")
    if shapes["calibration_maps"][1] != "float32" or shapes["test_maps"][1] != "float32" \
            or shapes["calibration_scores"][1] != "float64" or shapes["test_scores"][1] != "float64":
        raise ValueError(f"unexpected npz dtypes {shapes}")
    return nc, nt, h, w


def process_unit(spec: dict, data_root: Path, *, guard=_budget, log=print) -> tuple[dict, list[dict]]:
    run = data_root / spec["run_dir"]
    stem = run / "units" / spec["unit"]
    receipt_path, npz_path, csv_path, protocol_path = (stem.with_suffix(".json"), stem.with_suffix(".npz"),
                                                       stem.with_suffix(".csv"), run / "PROTOCOL.json")
    for p in (receipt_path, npz_path, csv_path, protocol_path):
        if not p.is_file():
            raise FileNotFoundError(f"MISSING_INPUT {spec['run_dir']}/{p.relative_to(run).as_posix()}")
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    shas = {"npz": checksum(npz_path), "csv": checksum(csv_path), "protocol": checksum(protocol_path),
            "receipt": sha256(receipt_bytes).hexdigest()}
    if receipt["files"].get(f"units/{spec['unit']}.npz") != shas["npz"] or receipt["files"].get(f"units/{spec['unit']}.csv") != shas["csv"]:
        raise ValueError(f"{spec['unit_id']}: payload SHA differs from receipt")
    if receipt["protocol_sha256"] != shas["protocol"]:
        raise ValueError(f"{spec['unit_id']}: run PROTOCOL SHA differs from receipt")
    if (receipt["condition"], receipt["restorer"]) != (spec["condition"], spec["restorer"]):
        raise ValueError(f"{spec['unit_id']}: receipt identity mismatch")
    if spec["noise_seed"] is not None and (receipt.get("noise_seed"), receipt.get("split_seed")) != (spec["noise_seed"], 11):
        raise ValueError(f"{spec['unit_id']}: seed mismatch")
    shapes = npz_shapes(npz_path)
    nc, nt, h, w = _expected_schema(shapes)
    plan = agg.payload_plan_bytes(nc, nt, h, w)
    guard(plan, None)  # fixed 2 GiB reserve inside; raises MemoryError("BLOCKED_MEMORY ...")

    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    cal_rows, test_rows = rows[:nc], rows[nc:]
    if len(rows) != nc + nt or any(r["split"] != "calibration" or r["label"] != "0" for r in cal_rows) \
            or any(r["split"] != "test" for r in test_rows):
        raise ValueError(f"{spec['unit_id']}: CSV rows do not align with npz")
    t0 = time.perf_counter()
    with np.load(npz_path, allow_pickle=False) as z:  # read-only file handle; arrays frozen below
        arrays = {k: z[k] for k in ("calibration_maps", "test_maps", "calibration_scores", "test_scores")}
    for a in arrays.values():
        a.setflags(write=False)
    if [float(r["image_score"]) for r in cal_rows] != arrays["calibration_scores"].tolist() or \
            [float(r["image_score"]) for r in test_rows] != arrays["test_scores"].tolist():
        raise ValueError(f"{spec['unit_id']}: CSV image_score differs from npz scores")
    labels = np.asarray([int(r["label"]) for r in test_rows])

    # Anchor B (map payload): refit stored pixel calibration from calibration maps.
    pix = agg.pixel_anchor(arrays["calibration_maps"])
    anchor_b = {"pixel_params_equal": pix["params"] == receipt["calibration"]["pixel"],
                "pixel_threshold_equal": pix["threshold"] == receipt["calibration"]["pixel_threshold"]}
    # Anchor A (original image score) and all rules.
    results, per_image, scores = {}, [], {}
    for rule in agg.RULES:
        cal = agg.aggregate(rule, arrays["calibration_maps"], arrays["calibration_scores"])
        test = agg.aggregate(rule, arrays["test_maps"], arrays["test_scores"])
        scores[rule] = (cal, test)
        res = agg.evaluate_rule(cal, test, labels)
        if rule == "original":
            stored = receipt["metrics"]
            diffs = {k: [res["metrics"][k], stored[k]] for k in ANCHOR_A_KEYS if res["metrics"][k] != stored[k]}
            if res["params"] != receipt["calibration"]["image"]:
                diffs["image_params"] = [res["params"], receipt["calibration"]["image"]]
            if res["threshold"] != receipt["calibration"]["image_threshold"]:
                diffs["calibration.image_threshold"] = [res["threshold"], receipt["calibration"]["image_threshold"]]
            if diffs:
                raise AnchorMismatch(f"{spec['unit_id']}: original-score anchor differs {diffs}")
            if not all(anchor_b.values()):
                raise AnchorMismatch(f"{spec['unit_id']}: map-payload anchor differs {anchor_b} {pix}")
        results[rule] = res
        for split, block, raw, normed in (("calibration", cal_rows, cal, res["normalized_calibration"]),
                                          ("test", test_rows, test, res["normalized_test"])):
            for r, x, z in zip(block, raw, normed):
                per_image.append(dict(unit_id=spec["unit_id"], category=spec["category"], family=spec["family"],
                                      noise_seed="" if spec["noise_seed"] is None else spec["noise_seed"],
                                      condition=spec["condition"], restorer=spec["restorer"], sample=r["sample"],
                                      split=split, label=int(r["label"]), defect_type=r.get("defect_type", ""), rule=rule,
                                      raw_score=repr(float(x)), normalized_score=repr(float(z)),
                                      threshold=repr(res["threshold"]), flagged=int(z >= res["threshold"]),
                                      source_npz_sha256=shas["npz"]))
    orig_cal, orig_test = scores["original"]
    max_cal, max_test = scores["map_max"]
    both_o, both_m = np.concatenate([orig_cal, orig_test]), np.concatenate([max_cal, max_test])
    record = {
        "unit_id": spec["unit_id"], **{k: spec[k] for k in ("category", "family", "noise_seed", "split_seed", "condition",
                                                             "restorer", "run_dir", "unit")},
        "source_public_record": PUBLIC_RECORD[spec["family"]].format(**spec),
        "source_sha256": {"npz": shas["npz"], "per_image_csv": shas["csv"], "receipt": shas["receipt"], "run_protocol": shas["protocol"]},
        "npz_schema": {k: {"shape": list(v[0]), "dtype": v[1]} for k, v in shapes.items()},
        "memory_plan_bytes": plan,
        "counts": {"calibration": nc, "test_normal": int((labels == 0).sum()), "test_anomaly": int((labels == 1).sum())},
        "k": {rule: agg.top_k(f, h, w) for rule, f in agg.TOP_FRACTIONS.items()},
        "anchor_a_original": "EXACT", "anchor_b_map_payload": {**anchor_b, "npz_sha256_equal": True},
        "original_vs_map_max": {"images": int(both_o.size), "exactly_equal": int((both_o == both_m).sum()),
                                "mean_original_minus_map_max": float((both_o - both_m).mean()),
                                "pearson": float(np.corrcoef(both_o, both_m)[0, 1])},
        "reference_stored": {k: receipt["metrics"][k] for k in ("au_pro", "pixel_auroc")},
        "rules": {rule: {"calibration": r["params"], "threshold": r["threshold"], "metrics": r["metrics"]}
                  for rule, r in results.items()},
        "seconds": time.perf_counter() - t0,
    }
    del arrays, scores
    return record, per_image


def summary_rows(records: list[dict]) -> list[dict]:
    out = []
    for rec in records:
        for rule, r in rec["rules"].items():
            out.append(dict(unit_id=rec["unit_id"], category=rec["category"], family=rec["family"],
                            noise_seed="" if rec["noise_seed"] is None else rec["noise_seed"], split_seed=rec["split_seed"],
                            condition=rec["condition"], restorer=rec["restorer"], rule=rule,
                            k="" if rule not in rec["k"] else rec["k"][rule],
                            n_calibration=rec["counts"]["calibration"], n_test_normal=rec["counts"]["test_normal"],
                            n_test_anomaly=rec["counts"]["test_anomaly"],
                            image_auroc=r["metrics"]["image_auroc"], image_f1=r["metrics"]["image_f1"],
                            image_threshold_normalized=r["threshold"],
                            image_false_alarm_rate_test_normal=r["metrics"]["image_false_alarm_rate_test_normal"],
                            image_miss_rate_test_anomaly=r["metrics"]["image_miss_rate_test_anomaly"],
                            calibration_median_raw=r["calibration"]["median"], calibration_scale_raw=r["calibration"]["scale"],
                            calibration_scale_method=r["calibration"]["method"],
                            reference_au_pro=rec["reference_stored"]["au_pro"],
                            reference_pixel_auroc=rec["reference_stored"]["pixel_auroc"],
                            anchor_a_original=rec["anchor_a_original"], source_public_record=rec["source_public_record"],
                            source_npz_sha256=rec["source_sha256"]["npz"], source_receipt_sha256=rec["source_sha256"]["receipt"],
                            source_run_protocol_sha256=rec["source_sha256"]["run_protocol"]))
    return out


def run(data_root: Path, output: Path, *, units=None, select=None, guard=_budget, log=print, root=ROOT) -> dict:
    """units: the full fixed plan recorded in PROTOCOL (default: 40 units); select: unit_ids processed now."""
    data_root, output = Path(data_root).resolve(), Path(output)
    (output / "units").mkdir(parents=True, exist_ok=True)
    full = agg.unit_plan() if units is None else units
    plan = full if select is None else [u for u in full if u["unit_id"] in set(select)]
    protocol = {"protocol": SPEC, "rules": list(agg.RULES), "top_fractions": agg.TOP_FRACTIONS, "quantile": agg.QUANTILE,
                "units_planned": len(full), "unit_ids": [u["unit_id"] for u in full],
                "inputs": "repository-relative run_dir under the GPU checkout; read-only",
                "code_sha256": {p: checksum(root / p) for p in CODE if (root / p).is_file()}}
    protocol_path = output / "PROTOCOL.json"
    text = json.dumps(protocol, indent=1)
    if protocol_path.is_file() and protocol_path.read_text(encoding="utf-8") != text:
        raise ValueError("Existing PROTOCOL differs; use a new output directory")
    protocol_path.write_text(text, encoding="utf-8")
    protocol_sha = checksum(protocol_path)
    session = {"start": datetime.now().astimezone().isoformat(timespec="seconds"), **source_state(root),
               "argv": sys.argv[1:] if __name__ == "__main__" else [], "units": {}}
    records = []
    for spec in plan:
        receipt_path = output / "units" / f"{spec['unit_id']}.json"
        csv_path = output / "units" / f"{spec['unit_id']}.csv"
        if receipt_path.is_file():
            rec = json.loads(receipt_path.read_text(encoding="utf-8"))
            if rec["protocol_sha256"] != protocol_sha or rec["per_image_csv_sha256"] != checksum(csv_path):
                raise ValueError(f"{spec['unit_id']}: existing result differs; resume refused")
            records.append(rec)
            session["units"][spec["unit_id"]] = "SKIPPED_VERIFIED"
            continue
        try:
            rec, per_image = process_unit(spec, data_root, guard=guard, log=log)
        except MemoryError as e:
            session["units"][spec["unit_id"]] = f"BLOCKED_MEMORY: {e}"
            log(json.dumps({"unit": spec["unit_id"], "status": "BLOCKED_MEMORY"}))
            continue
        except FileNotFoundError as e:
            session["units"][spec["unit_id"]] = str(e)
            log(json.dumps({"unit": spec["unit_id"], "status": "MISSING_INPUT"}))
            continue
        write_csv(csv_path, per_image)
        rec.update(protocol_sha256=protocol_sha, per_image_csv_sha256=checksum(csv_path))
        receipt_path.write_text(json.dumps(rec, indent=1), encoding="utf-8")  # written last
        records.append(rec)
        session["units"][spec["unit_id"]] = "COMPLETE"
        log(json.dumps({"unit": spec["unit_id"], "auroc": {r: round(v["metrics"]["image_auroc"], 4) for r, v in rec["rules"].items()},
                        "seconds": round(rec["seconds"], 2)}))
    # summary.csv covers every completed unit in this output (all sessions), in fixed plan order; no filtering.
    done = {}
    for u in full:
        p = output / "units" / f"{u['unit_id']}.json"
        if p.is_file():
            done[u["unit_id"]] = json.loads(p.read_text(encoding="utf-8"))
    write_csv(output / "summary.csv", summary_rows(list(done.values())))
    session.update(end=datetime.now().astimezone().isoformat(timespec="seconds"), units_selected=len(plan),
                   units_complete=sum(v in ("COMPLETE", "SKIPPED_VERIFIED") for v in session["units"].values()),
                   units_complete_in_output=len(done), units_planned=len(full),
                   cells_in_output=sum(len(r["rules"]) for r in done.values()))
    sessions = output / "sessions"
    sessions.mkdir(exist_ok=True)
    (sessions / f"{len(list(sessions.glob('*.json'))):03d}.json").write_text(json.dumps(session, indent=1), encoding="utf-8")
    return session


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, required=True, help="GPU checkout holding outputs/realistic-*/ (read-only)")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--categories", nargs="+", choices=agg.CATEGORIES, default=list(agg.CATEGORIES))
    a = p.parse_args(argv)
    select = [u["unit_id"] for u in agg.unit_plan() if u["category"] in a.categories]
    s = run(a.data_root, a.output, select=select)
    print(json.dumps({k: s[k] for k in ("units_selected", "units_complete", "units_complete_in_output", "units_planned",
                                        "cells_in_output")}))
    return 0 if s["units_complete"] == s["units_selected"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
