"""Replay phone-station events as status-LED frames to an Arduino UNO, or to a fake port.

--fake needs no hardware and no pyserial. --port COMx needs pyserial and a UNO running
docs/examples/phone_station_status_led/phone_station_status_led.ino. No actuator is driven.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import phone_uno  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", type=Path, required=True, help="station_events.jsonl from run_phone_station_compare.py")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--fake", action="store_true")
    group.add_argument("--port")
    p.add_argument("--delay", type=float, default=0.0, help="seconds between frames (use about 1.5 for a visible demo)")
    a = p.parse_args(argv)
    if a.fake:
        port, kind = phone_uno.FakeSerial(), "fake_serial_simulation"
    else:
        try:
            import serial
        except ImportError:
            print("pyserial is not installed in this environment; use --fake or install pyserial on the demo PC")
            return 2
        port, kind = serial.Serial(a.port, phone_uno.BAUD, timeout=1), f"serial:{a.port}"
    try:
        sequence = phone_uno.replay(a.events, port, delay_seconds=a.delay)
    finally:
        port.close()
    print(json.dumps(dict(kind=kind, frames=len(sequence), states=[s for _, s in sequence][:12],
                          physical_hardware_tested=not a.fake)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
