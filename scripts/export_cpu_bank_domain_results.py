"""Export numeric result tables with relative identifiers, preserving source receipts."""
from pathlib import Path, PureWindowsPath
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import csv_rows, digest, new_output, read_json, write_csv


def portable_row(row):
    row = dict(row)
    if row.get("source_run"):
        row["source_run"] = PureWindowsPath(row["source_run"]).name
    return row


def export(analysis, execution, output):
    analysis, execution = Path(analysis), Path(execution)
    receipt = read_json(analysis / "analysis_manifest.json")
    if receipt["status"] != "COMPLETE":
        raise ValueError("Completed analysis required")
    tables = {}
    for name, sha in receipt["tables"].items():
        if Path(name).name != name or not name.endswith(".csv") or digest(analysis / name) != sha:
            raise ValueError("Analysis table changed or invalid name")
        tables[name] = [portable_row(row) for row in csv_rows(analysis / name)]
    rows = tables["matrix_summary.csv"]
    for row in rows:
        category, seed = row["category"], int(row["seed"])
        bank = execution / "runs" / f"{category}-seed{seed}" / "bicubic_matched/bank/status.json"
        state = read_json(bank)
        if state["status"] != "BANK_COMPLETE" or (state["category"], state["seed"]) != (category, seed):
            raise ValueError("Fit-count source identity mismatch")
        row["train_count"] = state["normal_fit_count"]
        row["reused_clean_anchor"] = row["bank_domain"] == "clean"
    tables["new_conditions_for_master.csv"] = [r for r in rows if not r["reused_clean_anchor"]]
    if (len(rows) != receipt["matrix_rows"]
            or len(tables["new_conditions_for_master.csv"]) != receipt["newly_computed_condition_rows"]):
        raise ValueError("Analysis condition counts differ")
    out = new_output(Path(output), [analysis, execution])
    for name, values in tables.items():
        write_csv(out / name, values)
        path = out / name
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    figures = {}
    if (analysis / "figure_manifest.json").is_file():
        figure_receipt = read_json(analysis / "figure_manifest.json")
        if figure_receipt["source_analysis_sha256"] != digest(analysis / "analysis_manifest.json"):
            raise ValueError("Figure source changed")
        (out / "figures").mkdir()
        for name, sha in figure_receipt["files"].items():
            if Path(name).name != name or digest(analysis / "figures" / name) != sha:
                raise ValueError("Figure changed or invalid name")
            (out / "figures" / name).write_bytes((analysis / "figures" / name).read_bytes())
            figures[name] = sha
    manifest = dict(kind="public_numeric_cpu_bank_domain_results", status="COMPLETE",
        source_analysis_sha256=digest(analysis / "analysis_manifest.json"),
        source_execution_sha256=digest(execution / "status.json"),
        source_analysis_code_sha256=receipt["analysis_code_sha256"],
        export_code_sha256=digest(Path(__file__)), matrix_rows=len(rows),
        new_conditions=len(tables["new_conditions_for_master.csv"]),
        reused_clean_conditions=receipt["reused_clean_condition_rows"],
        bank_domains=receipt.get("bank_domains"), ci_scope=receipt["ci_scope"],
        mixed_protocol=receipt.get("mixed_protocol"), mixed_status_sha256=receipt.get("mixed_status_sha256"),
        input_table_sha256=receipt["tables"],
        tables={name: digest(out / name) for name in tables}, figures=figures,
        raw_arrays_exported=False, detection_metrics_recomputed=False)
    (out / "source_manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export(args.analysis, args.execution, args.output)
    print(json.dumps({k: result[k] for k in ("matrix_rows", "new_conditions", "reused_clean_conditions")}))
