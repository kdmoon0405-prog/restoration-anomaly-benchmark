"""Exercise a fake inspection controller without models, GT or hardware."""
from pathlib import Path
import argparse
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import csv_rows, digest, new_output, read_json, write_csv, write_json
from sr_anomaly.inspection_station import InspectionStation


def default_events():
    events = [dict(at=0, command="connect")]
    for i, verdict in enumerate(("OK", "NG", "REVIEW")):
        start = dict(at=i, command="start", cycle_id=f"cycle-{i}", part_id=f"part-{i}",
                     recipe_id="synthetic-recipe-v1", image_ref=f"synthetic-image-{i}")
        result = dict(at=i + .1, command="complete", cycle_id=f"cycle-{i}", verdict=verdict,
                      prediction_ref=f"synthetic-prediction-{i}", result_source="fake_detector")
        events.extend([start, dict(start), result, dict(result),
                       dict(at=i + .2, command="acknowledge", cycle_id=f"cycle-{i}")])
    events.extend([
        dict(at=3, command="start", cycle_id="missing", part_id="part-3",
             recipe_id="synthetic-recipe-v1", image_ref="synthetic-image-3"),
        dict(at=3.1, command="complete", cycle_id="missing", verdict="OK", result_source="fake_detector"),
        dict(at=3.2, command="acknowledge", cycle_id="missing"),
        dict(at=4, command="start", cycle_id="timeout", part_id="part-4",
             recipe_id="synthetic-recipe-v1", image_ref="synthetic-image-4"),
        dict(at=9, command="status"),
        dict(at=9.1, command="complete", cycle_id="timeout", verdict="OK",
             prediction_ref="late-prediction", result_source="fake_detector"),
        dict(at=9.2, command="acknowledge", cycle_id="timeout"),
        dict(at=10, command="start", cycle_id="disconnect", part_id="part-5",
             recipe_id="synthetic-recipe-v1", image_ref="synthetic-image-5"),
        dict(at=10.1, command="disconnect"), dict(at=10.2, command="connect"),
        dict(at=10.3, command="acknowledge", cycle_id="disconnect")])
    return events


def saved_pcb_events(package, variant):
    """Replay the fixed recorded threshold; labels/GT never determine a verdict."""
    expected = read_json(ROOT / "analysis/gpu_return_20261109/analysis_manifest.json")["sources"]
    table = f"pcb/postprocess/perboard-{variant}/per_board.csv"
    calibration = f"pcb/postprocess/calibration/{variant}.json"
    for name in (table, calibration):
        if digest(package / name) != expected[name]:
            raise ValueError("Replay source differs from reviewed return")
    threshold = read_json(package / calibration)["image_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
        raise ValueError("Finite saved threshold required")
    rows = csv_rows(package / table, ("sample", "variant", "normalized_image_score"))
    if not rows or len({r["sample"] for r in rows}) != len(rows):
        raise ValueError("Nonempty unique replay samples required")
    events = [dict(at=0, command="connect")]
    for i, row in enumerate(rows):
        score = float(row["normalized_image_score"])
        if not math.isfinite(score) or row["variant"] != variant:
            raise ValueError("Invalid replay score/variant")
        cycle_id = f"replay-{variant}-{i}"
        events.extend([
            dict(at=i, command="start", part_id=row["sample"], cycle_id=cycle_id,
                 recipe_id=f"pcb-v0.6-{variant}", image_ref=row["sample"]),
            dict(at=i + .1, command="complete", cycle_id=cycle_id,
                 verdict="NG" if score >= threshold else "OK", prediction_ref=table + "#" + row["sample"],
                 result_source="saved_scalar_prediction_software_replay"),
            dict(at=i + .2, command="acknowledge", cycle_id=cycle_id)])
    return events, dict(kind="software_replay_of_saved_scores", source_files={n: expected[n] for n in (table, calibration)},
                        image_threshold=threshold, score_comparison=">=", labels_used_for_verdict=False)


def run(output, events=None, *, evidence=None):
    events = default_events() if events is None else events
    if not isinstance(events, list):
        raise ValueError("events must be a JSON list")
    output = new_output(output)
    state = dict(kind=evidence["kind"] if evidence else "synthetic_controller_simulation", status="BUILDING",
        physical_hardware_tested=False, research_metrics=None, clock_kind="simulation_seconds",
        detector_inference_executed=False, evidence=evidence,
        source_sha256={str(path.relative_to(ROOT).as_posix()): digest(path) for path in
            (ROOT / "src/sr_anomaly/inspection_station.py", Path(__file__))})
    write_json(output / "manifest.json", state)
    moment = [0.0]
    station = InspectionStation(clock=lambda: moment[0], clock_kind="simulation_seconds")
    dispatches = 0
    try:
        with (output / "events.jsonl").open("w", encoding="utf-8") as log:
            for i, event in enumerate(events):
                message = dict(event)
                moment[0] = message.pop("at")
                message.setdefault("request_id", f"request-{i}")
                response = station.handle(message)
                dispatches += sum(a["kind"] == "fake_inspection_request" for a in response["fake_actions"])
                log.write(json.dumps(dict(at=moment[0], command=message, response=response),
                                     ensure_ascii=False, allow_nan=False) + "\n")
        rows = []
        for cycle in station.cycles.values():
            row = {k: v for k, v in cycle.items() if k != "result"}
            row.update(cycle["result"] or {})
            # A rejected OK payload must not replace the controller's ERROR outcome.
            row["verdict"] = cycle["verdict"]
            rows.append(row)
        write_csv(output / "cycles.csv", rows, fields=["part_id", "cycle_id", "recipe_id", "image_ref", "started_at_seconds",
                  "deadline_seconds", "completed_at_seconds", "clock_kind", "verdict", "reason",
                  "acknowledged", "prediction_ref", "result_source", "error"])
        state.update(status="COMPLETE", cycles=len(rows), fake_inspection_dispatches=dispatches,
                     final_state=station.state, connected=station.connected,
                     files={name: digest(output / name) for name in ("events.jsonl", "cycles.csv")})
    except Exception as error:
        state.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        write_json(output / "manifest.json", state)
        raise
    write_json(output / "manifest.json", state)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--saved-pcb-return", type=Path)
    parser.add_argument("--variant", choices=("clean", "bicubic_x4", "swinir_x4"), default="bicubic_x4")
    args = parser.parse_args(argv)
    if args.scenario and args.saved_pcb_return:
        parser.error("Choose a synthetic scenario or saved-score replay")
    try:
        events = read_json(args.scenario)["events"] if args.scenario else None
        evidence = None
        if args.saved_pcb_return:
            events, evidence = saved_pcb_events(args.saved_pcb_return, args.variant)
        state = run(args.output, events, evidence=evidence)
        print(json.dumps({key: state[key] for key in ("status", "cycles", "fake_inspection_dispatches")}))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
