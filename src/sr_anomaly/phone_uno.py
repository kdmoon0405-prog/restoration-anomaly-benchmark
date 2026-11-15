"""Status-LED frames for an Arduino UNO from phone-station events (software path; hardware not tested here).

One ASCII byte per state change. The same frames go to a real serial port or to FakeSerial. The mapping follows the
existing InspectionStation states plus the station's retake request; it drives no actuator.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

BAUD = 115200
FRAMES = {"READY": b"R", "BUSY": b"B", "RETAKE_REQUEST": b"T", "OK": b"O", "NG": b"N", "REVIEW": b"V", "ERROR": b"E"}
LED_MEANING = {"READY": "off", "BUSY": "on", "RETAKE_REQUEST": "slow blink (1 Hz)", "OK": "one long pulse then off",
               "NG": "three short pulses", "REVIEW": "fast blink (5 Hz)", "ERROR": "on, steady"}


class FakeSerial:
    """Stand-in for serial.Serial: records written bytes."""

    def __init__(self):
        self.written = bytearray()
        self.closed = False

    def write(self, data: bytes) -> int:
        if self.closed:
            raise OSError("port closed")
        self.written += data
        return len(data)

    def close(self) -> None:
        self.closed = True


def frames_from_events(events: list[dict]) -> list[tuple[str, str]]:
    """(cycle_id, state) sequence from station_events.jsonl records, in order."""
    out = []
    for e in events:
        if e.get("kind") == "controller":
            command, response = e["command"], e["response"]
            if not response.get("accepted"):
                continue
            if command["command"] == "start":
                out.append((command["cycle_id"], "BUSY"))
            elif command["command"] == "complete":
                out.append((command["cycle_id"], response["state"]))
            elif command["command"] == "acknowledge":
                out.append((command["cycle_id"], "READY"))
        elif e.get("kind") == "station_event" and e.get("event") == "retake_requested":
            out.append((e["cycle_id"], "RETAKE_REQUEST"))
    unknown = sorted({s for _, s in out} - set(FRAMES))
    if unknown:
        raise ValueError(f"states without a frame: {unknown}")
    return out


def replay(events_path: Path, port, *, delay_seconds: float = 0.0, sleep=time.sleep) -> list[tuple[str, str]]:
    """Write one frame per state change to `port` (anything with write()). Returns the sequence sent."""
    events = [json.loads(line) for line in Path(events_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    sequence = frames_from_events(events)
    for _, state in sequence:
        port.write(FRAMES[state])
        if delay_seconds:
            sleep(delay_seconds)
    return sequence
