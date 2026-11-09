import importlib.util
import json
from pathlib import Path

import pytest

from sr_anomaly.inspection_station import InspectionStation


@pytest.fixture
def device():
    now = [0.0]
    station = InspectionStation(clock=lambda: now[0], clock_kind="simulation_seconds")
    return station, now


def send(station, command, **values):
    return station.handle(dict(request_id="request", command=command, **values))


def start(station, cycle="cycle"):
    return send(station, "start", cycle_id=cycle, part_id="part", recipe_id="recipe", image_ref="image")


def complete(station, cycle="cycle", verdict="OK", **values):
    return send(station, "complete", cycle_id=cycle, verdict=verdict,
                prediction_ref="prediction", result_source="fake_detector", **values)


@pytest.mark.parametrize("verdict", ["OK", "NG", "REVIEW", "ERROR"])
def test_cycle_outcomes_and_ack(device, verdict):
    station, now = device
    assert not start(station)["accepted"]
    send(station, "connect")
    assert start(station)["state"] == "BUSY"
    now[0] = .5
    result = complete(station, verdict=verdict, error="fake_failure" if verdict == "ERROR" else None)
    assert result["state"] == verdict
    assert result["cycle"]["completed_at_seconds"] == .5
    assert not start(station, "second")["accepted"]
    assert send(station, "acknowledge", cycle_id="cycle")["state"] == "READY"


def test_duplicate_conflict_and_result_aliasing(device):
    station, _ = device
    send(station, "connect")
    response = start(station)
    response["cycle"]["part_id"] = "external_mutation"
    duplicate = start(station)
    assert duplicate["code"] == "duplicate_start" and not duplicate["fake_actions"]
    conflict = send(station, "start", cycle_id="cycle", part_id="different",
                    recipe_id="recipe", image_ref="image")
    assert conflict["code"] == "cycle_id_conflict"
    assert complete(station)["state"] == "OK"
    assert not complete(station)["fake_actions"]
    assert complete(station, verdict="NG")["code"] == "result_conflict"
    send(station, "acknowledge", cycle_id="cycle")
    start(station, "second")
    assert send(station, "acknowledge", cycle_id="cycle")["state"] == "BUSY"
    assert complete(station)["active_cycle_id"] == "second"


def test_timeout_boundary_late_result_and_new_cycle(device):
    station, now = device
    send(station, "connect")
    start(station)
    now[0] = 5
    late = complete(station)
    assert late["state"] == "ERROR" and late["code"] == "stale_result"
    assert late["cycle"]["reason"] == "timeout"
    send(station, "acknowledge", cycle_id="cycle")
    start(station, "second")
    assert complete(station)["state"] == "BUSY"
    assert complete(station)["code"] == "stale_result"


def test_reconnection_preserves_error_until_ack(device):
    station, now = device
    send(station, "connect")
    start(station)
    now[0] = 1
    send(station, "disconnect")
    assert not start(station, "second")["accepted"]
    response = send(station, "connect")
    assert response["state"] == "ERROR"
    assert response["cycle"]["reason"] == "connection_lost"
    assert complete(station)["code"] == "stale_result"
    send(station, "acknowledge", cycle_id="cycle")
    assert start(station, "second")["state"] == "BUSY"


@pytest.mark.parametrize("result", [dict(verdict="OK"), dict(verdict="UNKNOWN"),
                                    dict(verdict="OK", prediction_ref="prediction")])
def test_missing_or_invalid_prediction_cannot_pass(device, result):
    station, _ = device
    send(station, "connect")
    start(station)
    response = send(station, "complete", cycle_id="cycle", **result)
    assert response["state"] == "ERROR"
    assert response["fake_actions"][0]["kind"] == "fake_hold"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True])
def test_invalid_clock_rejected(device, bad):
    station, now = device
    now[0] = bad
    with pytest.raises(ValueError, match="Clock"):
        send(station, "connect")


def test_controller_cli_outputs_and_no_overwrite(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/simulate_inspection_station.py"
    spec = importlib.util.spec_from_file_location("station_demo", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path / "run"
    state = module.run(out)
    assert state["status"] == "COMPLETE" and state["cycles"] == 6
    assert state["fake_inspection_dispatches"] == 6
    assert state["physical_hardware_tested"] is False and state["research_metrics"] is None
    logs = [json.loads(line) for line in (out / "events.jsonl").read_text('utf-8').splitlines()]
    assert any(row["response"]["code"] == "stale_result" for row in logs)
    with pytest.raises(FileExistsError):
        module.run(out)
    failed = tmp_path / "failed"
    with pytest.raises(KeyError):
        module.run(failed, [dict(command="connect")])
    assert json.loads((failed / "manifest.json").read_text('utf-8'))["status"] == "FAILED"


def test_clock_backwards_and_bad_request_do_not_dispatch(device):
    station, now = device
    now[0] = 2
    assert send(station, "connect")["state"] == "READY"
    assert station.handle({"command": "start"})["code"] == "invalid_request_id"
    assert not send(station, "start", cycle_id="missing_fields")["accepted"]
    assert not station.cycles
    now[0] = 1
    with pytest.raises(ValueError, match="Clock"):
        send(station, "status")


def test_saved_score_replay_ignores_labels_and_preserves_threshold(tmp_path, monkeypatch):
    from sr_anomaly.analysis_io import digest, write_csv, write_json
    script = Path(__file__).resolve().parents[1] / "scripts/simulate_inspection_station.py"
    spec = importlib.util.spec_from_file_location("station_replay", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = tmp_path / "package"
    table = package / "pcb/postprocess/perboard-bicubic_x4/per_board.csv"
    calibration = package / "pcb/postprocess/calibration/bicubic_x4.json"
    for directory in (table.parent, calibration.parent, tmp_path / "analysis/gpu_return_20261109"):
        directory.mkdir(parents=True)
    write_csv(table, [dict(sample="a", variant="bicubic_x4", normalized_image_score="2", label="0"),
                      dict(sample="b", variant="bicubic_x4", normalized_image_score="1", label="1")])
    write_json(calibration, dict(image_threshold=2))
    write_json(tmp_path / "analysis/gpu_return_20261109/analysis_manifest.json",
               dict(sources={p.relative_to(package).as_posix(): digest(p) for p in (table, calibration)}))
    monkeypatch.setattr(module, "ROOT", tmp_path)
    events, evidence = module.saved_pcb_events(package, "bicubic_x4")
    assert [e["verdict"] for e in events if e["command"] == "complete"] == ["NG", "OK"]
    assert evidence["labels_used_for_verdict"] is False and evidence["image_threshold"] == 2
    with table.open('a') as stream:
        stream.write(' ')
    with pytest.raises(ValueError, match="reviewed return"):
        module.saved_pcb_events(package, "bicubic_x4")
