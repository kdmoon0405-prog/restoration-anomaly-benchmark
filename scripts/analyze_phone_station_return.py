"""Recount a phone-station development return from saved metadata only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import csv_rows, digest, new_output, read_json, write_csv, write_json

CONDITIONS = (
    "C0_direct", "C1_bicubic_x4", "C1_swinir_x4", "C2_policy_v0.1_roi",
    "C2_policy_v0.2", "C3_two_lights",
)
STATES = ("OK", "NG", "REVIEW", "ERROR", "NA", "PENDING")


def load_return(folder):
    plan = read_json(folder / "plan.json")
    manifest = read_json(folder / "manifest.json")
    if (manifest["conditions"] != list(CONDITIONS)
            or manifest["plan_sha256"] != digest(folder / "plan.json")):
        raise ValueError("Condition contract or plan hash differs")
    known_files = manifest["input"]["files"]
    reserved = set(plan["references"].values()) | set(plan["calibration"].values())
    cycles = {c["cycle_id"]: c for c in plan["cycles"]}
    if not cycles or len(cycles) != len(plan["cycles"]) or not reserved <= known_files.keys():
        raise ValueError("Empty/duplicate cycles or unknown reference/calibration files")
    for cycle in cycles.values():
        names = {cycle["first"], cycle.get("alternate")} - {None}
        if (cycle["label"] not in ("normal", "simulated_defect")
                or not names <= known_files.keys()):
            raise ValueError("Unknown label or planned image")
    rows = csv_rows(folder / "cycles.csv", required=(
        "cycle_id", "condition", "kind", "label", "first_file", "alternate_file",
        "final_state", "captures_used", "retake_requested",
    ))
    cells = {(r["cycle_id"], r["condition"]): r for r in rows}
    expected = {(cycle, condition) for cycle in cycles for condition in CONDITIONS}
    if len(cells) != len(rows) or set(cells) != expected:
        raise ValueError("Duplicate or missing cycle-condition cell")
    for row in rows:
        cycle = cycles[row["cycle_id"]]
        if (row["first_file"] != cycle["first"]
                or row["alternate_file"] != (cycle.get("alternate") or "")
                or row["label"] != cycle["label"] or row["kind"] != cycle["kind"]):
            raise ValueError("Cycle identity differs between conditions or plan")
        if (row["final_state"] not in STATES or row["captures_used"] not in ("0", "1", "2")
                or row["retake_requested"] not in ("True", "False")):
            raise ValueError("Invalid state, capture budget, or boolean")
        if row["captures_used"] == "2" and not cycle.get("alternate"):
            raise ValueError("Two image accesses require an alternate")
        if row["condition"] == "C3_two_lights":
            has_pair = bool(cycle.get("alternate"))
            if (row["captures_used"] != ("2" if has_pair else "0")
                    or (row["final_state"] == "NA") == has_pair):
                raise ValueError("C3 pair availability/state/count mismatch")
        elif row["condition"].startswith(("C0_", "C1_")):
            if row["captures_used"] != "1":
                raise ValueError("Single-view condition must access one image")
        elif row["captures_used"] not in ("1", "2"):
            raise ValueError("Conditional policy must access its first image")
    summary = csv_rows(folder / "summary.csv", required=(
        "condition", "cycles", "captures_total", "retakes_requested", *STATES,
    ))
    if len(summary) != len(CONDITIONS) or {r["condition"] for r in summary} != set(CONDITIONS):
        raise ValueError("Missing or duplicated source summary condition")
    for source in summary:
        group = [r for r in rows if r["condition"] == source["condition"]]
        counts = Counter(r["final_state"] for r in group)
        values = dict(cycles=len(group), captures_total=sum(int(r["captures_used"]) for r in group),
                      retakes_requested=sum(r["retake_requested"] == "True" for r in group))
        values.update({state: counts[state] for state in STATES})
        if any(int(source[k]) != value for k, value in values.items()):
            raise ValueError("Source summary disagrees with cycle rows")
    return plan, manifest, rows, reserved


def recount(rows, ids, cohort):
    result = []
    for condition in CONDITIONS:
        group = [r for r in rows if r["cycle_id"] in ids and r["condition"] == condition]
        counts = Counter(r["final_state"] for r in group)
        normal = [r for r in group if r["label"] == "normal"]
        simulated = [r for r in group if r["label"] == "simulated_defect"]
        accessed = set()
        for row in group:
            if int(row["captures_used"]) >= 1:
                accessed.add(row["first_file"])
            if row["captures_used"] == "2":
                accessed.add(row["alternate_file"])
        result.append(dict(
            cohort=cohort, condition=condition, cycles=len(group),
            **{state: counts[state] for state in STATES},
            logical_image_accesses=sum(int(r["captures_used"]) for r in group),
            unique_source_files_accessed=len(accessed),
            retakes_requested=sum(r["retake_requested"] == "True" for r in group),
            normal_labelled_cycles=len(normal),
            normal_labelled_NG=sum(r["final_state"] == "NG" for r in normal),
            simulated_cycles=len(simulated),
            simulated_NG=sum(r["final_state"] == "NG" for r in simulated),
        ))
    return result


def analyze(folder, output):
    folder = Path(folder).resolve()
    plan, manifest, rows, reserved = load_return(folder)
    cycles = plan["cycles"]
    cohorts = {
        "all_planned": {c["cycle_id"] for c in cycles},
        "paired_available": {c["cycle_id"] for c in cycles if c.get("alternate")},
        "paired_without_reference_calibration": {
            c["cycle_id"] for c in cycles if c.get("alternate")
            and not {c["first"], c["alternate"]} & reserved
        },
    }
    summaries = [r for name, ids in cohorts.items() for r in recount(rows, ids, name)]
    roles = defaultdict(list)
    for role in ("references", "calibration"):
        for light, filename in plan[role].items():
            roles[filename].append(f"{role}/{light}")
    for cycle in cycles:
        for role in ("first", "alternate"):
            if cycle.get(role):
                roles[cycle[role]].append(f"cycle/{cycle['cycle_id']}/{role}")
    reuse = [dict(file=name, roles=" | ".join(uses), role_count=len(uses))
             for name, uses in sorted(roles.items()) if len(uses) > 1]
    cells = {(r["cycle_id"], r["condition"]): r for r in rows}
    disagreements = [c["cycle_id"] for c in cycles
                     if cells[c["cycle_id"], "C1_bicubic_x4"]["final_state"]
                     != cells[c["cycle_id"], "C1_swinir_x4"]["final_state"]]
    report = dict(
        schema_version=1, source_commit=manifest["source_commit"],
        source_sha256={name: digest(folder / name) for name in
                       ("plan.json", "manifest.json", "cycles.csv", "summary.csv")},
        analysis_script_sha256=digest(Path(__file__)),
        session_role=manifest["session_role"],
        cohort_role="post-hoc development diagnostics; no policy selection",
        count_unit="logical accesses to existing photos in offline replay",
        physical_capture_time=manifest["physical_capture_time"],
        restoration_family=manifest["restoration_family"],
        independent_boards=None, human_legibility_labels=None,
        cohort_cycle_ids={name: sorted(ids) for name, ids in cohorts.items()},
        bicubic_swinir_verdict_disagreements=disagreements,
        summaries=summaries, source_reuse=reuse,
    )
    output = new_output(output, inputs=(folder,))
    write_json(output / "analysis.json", report)
    write_csv(output / "cohort_summary.csv", summaries)
    write_csv(output / "source_reuse.csv", reuse, fields=("file", "roles", "role_count"))
    membership = [dict(cycle_id=c["cycle_id"], **{
        name: c["cycle_id"] in ids for name, ids in cohorts.items()}) for c in cycles]
    write_csv(output / "cohort_membership.csv", membership)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = analyze(args.input, args.output)
    print(f"Recounted {len(result['cohort_cycle_ids']['all_planned'])} cycles across {len(CONDITIONS)} conditions")


if __name__ == "__main__":
    main()
