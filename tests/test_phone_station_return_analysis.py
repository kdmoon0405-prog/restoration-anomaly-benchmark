"""Saved metadata recount and denominator guards, using fabricated input only."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/analyze_phone_station_return.py"
spec = importlib.util.spec_from_file_location("phone_return_analysis", PATH)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def packet(tmp_path):
    folder = tmp_path / "input"
    folder.mkdir()
    cycles = [dict(cycle_id=name, kind="normal", label="normal", first=first, alternate=alt)
              for name, first, alt in (("a", "a.jpg", "shared.jpg"),
                                       ("b", "b.jpg", "ref.jpg"),
                                       ("c", "c.jpg", None),
                                       ("d", "d.jpg", "shared.jpg"))]
    plan = dict(references={"L0": "ref.jpg"}, calibration={"L0": "cal.jpg"}, cycles=cycles)
    (folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    manifest = dict(conditions=list(analysis.CONDITIONS),
                    plan_sha256=hashlib.sha256((folder / "plan.json").read_bytes()).hexdigest(),
                    input={"files": dict.fromkeys(("a.jpg", "b.jpg", "c.jpg", "d.jpg", "shared.jpg", "ref.jpg", "cal.jpg"), "fake")},
                    source_commit="synthetic", session_role="synthetic development fixture",
                    physical_capture_time="not measured", restoration_family="synthetic")
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rows = []
    for cycle in cycles:
        for condition in analysis.CONDITIONS:
            is_two = condition == "C3_two_lights"
            rows.append(dict(cycle_id=cycle["cycle_id"], kind=cycle["kind"], label=cycle["label"],
                             condition=condition, first_file=cycle["first"],
                             alternate_file=cycle["alternate"] or "", retake_requested="False",
                             final_state="NA" if is_two and not cycle["alternate"] else "OK",
                             captures_used=("2" if cycle["alternate"] else "0") if is_two else "1"))
    write_csv(folder / "cycles.csv", rows)
    summaries = analysis.recount(rows, {c["cycle_id"] for c in cycles}, "all")
    summary = [dict(condition=r["condition"], cycles=r["cycles"],
                    captures_total=r["logical_image_accesses"], retakes_requested=r["retakes_requested"],
                    **{state: r[state] for state in analysis.STATES}) for r in summaries]
    write_csv(folder / "summary.csv", summary)
    return folder


def test_cohorts_reuse_and_no_overwrite(packet, tmp_path):
    output = tmp_path / "out"
    report = analysis.analyze(packet, output)
    assert [len(ids) for ids in report["cohort_cycle_ids"].values()] == [4, 3, 2]
    all_two = next(r for r in report["summaries"] if r["cohort"] == "all_planned" and r["condition"] == "C3_two_lights")
    assert (all_two["cycles"], all_two["NA"], all_two["logical_image_accesses"], all_two["unique_source_files_accessed"]) == (4, 1, 6, 5)
    assert {r["file"] for r in report["source_reuse"]} == {"ref.jpg", "shared.jpg"}
    assert report["bicubic_swinir_verdict_disagreements"] == []
    with pytest.raises(FileExistsError):
        analysis.analyze(packet, output)
    with pytest.raises(ValueError, match="outside"):
        analysis.analyze(packet, packet / "derived")
    assert not (packet / "derived").exists()


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "identity", "state", "budget", "boolean", "c3", "summary"])
def test_rejects_inconsistent_return(packet, tmp_path, mutation):
    path = packet / ("summary.csv" if mutation == "summary" else "cycles.csv")
    rows = analysis.csv_rows(path)
    if mutation == "duplicate":
        rows.append(dict(rows[0]))
    elif mutation == "missing":
        rows.pop()
    elif mutation == "summary":
        rows[0]["cycles"] = "99"
    else:
        field, value = {"identity": ("alternate_file", "other.jpg"), "state": ("final_state", "PASS"),
                        "budget": ("captures_used", "3"), "boolean": ("retake_requested", "maybe"),
                        "c3": ("captures_used", "1")}[mutation]
        target = next(r for r in rows if r["condition"] == "C3_two_lights") if mutation == "c3" else rows[0]
        target[field] = value
    write_csv(path, rows)
    with pytest.raises(ValueError):
        analysis.analyze(packet, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()
