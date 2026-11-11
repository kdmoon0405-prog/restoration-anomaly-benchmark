"""Join stored result tables while retaining their protocol families and source receipts."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

from .analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json

FIELDS = ("entry_id", "study_family", "protocol_id", "dataset", "category", "seed", "noise_seed",
          "bank_domain", "query_domain", "variant", "train_count", "test_count", "n_anomaly",
          "psnr", "ssim", "lpips", "image_auroc", "pixel_auroc", "pooled_aupro",
          "evidence_kind", "source_table", "source_sha256", "source_run", "reported_source_artifact")
NUMERIC = ("psnr", "ssim", "lpips", "image_auroc", "pixel_auroc", "pooled_aupro")
COUNT = ("train_count", "test_count", "n_anomaly", "seed", "noise_seed")
KEY = ("study_family", "protocol_id", "dataset", "category", "seed",
       "bank_domain", "query_domain", "variant")


def _normalize(row, source, table, sha):
    mapping = source.get("column_map", {})
    result = {name: row.get(mapping.get(name, name), "") for name in FIELDS}
    for field in ("study_family", "protocol_id", "category"):
        result[field] = source.get("identity", {}).get(field) or row.get(source.get(field + "_column", ""), "")
        if not result[field]:
            raise ValueError(f"Missing {field} in stored reporting table")
    result["dataset"] = source.get("identity", {}).get("dataset") or source.get("dataset_id", result["dataset"])
    result["evidence_kind"] = row.get("evidence_kind") or source["evidence_kind"]
    result.update(source_table=str(table), source_sha256=sha,
                  reported_source_artifact=row.get("source_artifact", ""))
    for field in NUMERIC:
        if result[field] != "":
            value = float(result[field])
            if math.isnan(value) or (not math.isfinite(value) and field != "psnr"):
                raise ValueError(f"Invalid stored metric: {field}")
            if field in ("image_auroc", "pixel_auroc", "pooled_aupro") and not 0 <= value <= 1:
                raise ValueError("Stored AUROC/AU-PRO is out of range")
            result[field] = value
    for field in COUNT:
        if result[field] != "":
            number = float(result[field])
            if not math.isfinite(number) or int(number) != number or number < 0:
                raise ValueError("Invalid stored count/seed")
            result[field] = int(number)
    result["entry_id"] = hashlib.sha256(
        json.dumps([result[k] for k in KEY], ensure_ascii=False).encode()).hexdigest()[:16]
    return result


def build_master(catalog, root, output, *, bank_analyses=(), allow_synthetic=False):
    root, catalog = Path(root).resolve(), Path(catalog).resolve()
    config = read_json(catalog)
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported reporting catalog")
    portable = config.get("portable_paths", False)
    def display(path):
        return Path(path).resolve().relative_to(root).as_posix() if portable else str(path)
    sources = []
    skipped = []
    for source in config.get("sources", []):
        if source.get("status") in ("PARTIAL", "FAILED"):
            skipped.append(dict(source=source["table"], status=source["status"]))
            continue
        if source.get("status") != "COMPLETE":
            raise ValueError("Reporting source needs an explicit completion status")
        path = relative_source(root, source["table"])
        sources.append((source, path))
    for directory in bank_analyses:
        directory = Path(directory).resolve()
        receipt = read_json(directory / "analysis_manifest.json")
        if receipt.get("kind") != "read_only_bank_domain_analysis":
            raise ValueError("Not a bank-domain analysis receipt")
        if receipt["status"] == "NO_COMPLETE_INPUTS":
            skipped.append(dict(source=str(directory), status=receipt["status"]))
            continue
        if receipt["status"] != "COMPLETE":
            raise ValueError("Incomplete bank-domain analysis")
        path = directory / "bank_domain_summary.csv"
        if digest(path) != receipt["tables"]["bank_domain_summary.csv"]:
            raise ValueError("Bank-domain analysis output changed")
        sources.append((dict(study_family_column="study_family", protocol_id_column="protocol_sha256",
            category_column="category", evidence_kind="model_predictions",
            column_map=dict(test_count="n_test", psnr="mean_psnr", ssim="mean_ssim")), path))
    rows, duplicates = {}, []
    for source, path in sources:
        sha = digest(path)
        if source.get("sha256") and sha != source["sha256"]:
            raise ValueError("Stored reporting source digest changed")
        required = [source[k + "_column"] for k in ("study_family", "protocol_id", "category")
                    if k not in source.get("identity", {})]
        for raw in csv_rows(path, required):
            if raw.get("status", "COMPLETE") != "COMPLETE":
                skipped.append(dict(source=str(path), status=raw["status"], scope="table row"))
                continue
            row = _normalize(raw, source, display(path), sha)
            if row["evidence_kind"] == "synthetic_fixture" and not allow_synthetic:
                raise ValueError("Synthetic data cannot enter a real master table without explicit opt-in")
            key = tuple(row[k] for k in KEY)
            if key in rows:
                compare = (*NUMERIC, "train_count", "test_count", "n_anomaly", "evidence_kind", "noise_seed")
                if any(rows[key][k] != row[k] for k in compare):
                    raise ValueError("Conflicting duplicate master-table condition")
                duplicates.append(dict(entry_id=row["entry_id"], duplicate_source=display(path)))
                continue
            rows[key] = row
    ordered = sorted(rows.values(), key=lambda r: tuple(str(r[k]) for k in KEY))
    out = new_output(Path(output), [p for _, p in sources])
    write_csv(out / "master_results.csv", ordered, FIELDS)
    evidence = [dict(entry_id=r["entry_id"], study_family=r["study_family"], protocol_id=r["protocol_id"],
        category=r["category"], seed=r["seed"],
        statement=f"Stored pooled AU-PRO@0.3={r['pooled_aupro']} for "
                  f"{r['variant'] or r['bank_domain'] + '/' + r['query_domain']}",
        claim_scope="descriptive stored metric; no causal or superiority inference",
        source_table=r["source_table"], source_sha256=r["source_sha256"],
        raw_prediction_arrays_checked=False) for r in ordered]
    write_csv(out / "claim_evidence_index.csv", evidence,
              fields=None if evidence else ["entry_id", "statement", "source_table"])
    groups = defaultdict(list)
    for row in ordered:
        groups[(row["study_family"], row["protocol_id"])].append(row)
    lines = ["# Stored research results", "",
        "Each table retains one protocol family. No metric is averaged across families or seeds.", ""]
    for (family, protocol), group in sorted(groups.items()):
        lines += [f"## {family}", "", f"Protocol: {protocol}", "",
            "| category | bank/split seed | noise seed | condition | pooled AU-PRO | Pixel AUROC | PSNR | SSIM |",
            "|---|---:|---:|---|---:|---:|---:|---:|"]
        for r in group:
            values = [r["category"], r["seed"], r["noise_seed"], r["variant"] or r["bank_domain"] + "/" + r["query_domain"],
                      r["pooled_aupro"], r["pixel_auroc"], r["psnr"], r["ssim"]]
            lines.append("| " + " | ".join(str(v) if v != "" else "N/A" for v in values) + " |")
        lines.append("")
    lines += ["Source CSVs and their SHA256 are retained per row. Array-level or remote-execution validation is separate.",
              "Absent experiments do not create numeric rows. Partial/failed sources are excluded.", ""]
    (out / "master_results.md").write_text("\n".join(lines), encoding="utf-8")
    if portable:
        for name in ("master_results.csv", "claim_evidence_index.csv", "master_results.md"):
            path = out / name
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    receipt = dict(kind="stored_research_master_table", schema_version=1,
        rows=len(ordered), protocol_groups=len(groups), duplicates_removed=duplicates, skipped=skipped,
        catalog_sha256=digest(catalog), sources=[dict(table=display(p), sha256=digest(p)) for _, p in sources],
        raw_prediction_arrays_checked=False, detection_metrics_recomputed=False,
        tables={n: digest(out / n) for n in ("master_results.csv", "claim_evidence_index.csv")})
    write_json(out / "report_manifest.json", receipt)
    if portable:
        path = out / "report_manifest.json"
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    return receipt
