"""Single-cycle fake controller. It never opens references or drives hardware."""
from __future__ import annotations

from copy import deepcopy
import math
import time


TERMINAL = frozenset({"OK", "NG", "REVIEW", "ERROR"})
REQUEST_FIELDS = ("part_id", "cycle_id", "recipe_id", "image_ref")


def _text(value):
    return (isinstance(value, str) and 0 < len(value) <= 1024
            and value == value.strip() and value.isprintable())


class InspectionStation:
    """Synchronous controller; call status regularly to observe timeout expiry."""

    def __init__(self, *, timeout_seconds=5.0, clock=time.monotonic,
                 clock_kind="monotonic_seconds"):
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("Positive finite timeout required")
        if not _text(clock_kind):
            raise ValueError("clock_kind required")
        self.timeout_seconds = float(timeout_seconds)
        self.clock, self.clock_kind = clock, clock_kind
        self.connected = False
        self.state = "READY"
        self.active_cycle_id = None
        self.cycles = {}
        self.last_time = None

    def _finish(self, verdict, now, *, reason=None, result=None):
        cycle = self.cycles[self.active_cycle_id]
        cycle.update(verdict=verdict, completed_at_seconds=now, reason=reason, result=result)
        self.state = verdict
        return {"kind": "fake_route" if verdict in {"OK", "NG"} else "fake_hold",
                "cycle_id": self.active_cycle_id, "verdict": verdict}

    def handle(self, message):
        now = self.clock()
        if (isinstance(now, bool) or not isinstance(now, (int, float))
                or not math.isfinite(now) or now < 0
                or (self.last_time is not None and now < self.last_time)):
            raise ValueError("Clock must be finite, nonnegative and nondecreasing")
        self.last_time = now
        actions = []
        if self.state == "BUSY" and now >= self.cycles[self.active_cycle_id]["deadline_seconds"]:
            actions.append(self._finish("ERROR", now, reason="timeout"))

        def reply(accepted, code, cycle=None):
            if cycle is None and self.active_cycle_id is not None:
                cycle = self.cycles[self.active_cycle_id]
            return deepcopy(dict(request_id=message.get("request_id") if isinstance(message, dict) else None,
                accepted=accepted, code=code, state=self.state, connected=self.connected,
                active_cycle_id=self.active_cycle_id, cycle=cycle, fake_actions=actions))

        if not isinstance(message, dict) or not _text(message.get("request_id")):
            return reply(False, "invalid_request_id")
        command = message.get("command")
        if command == "connect":
            self.connected = True
            return reply(True, "connected")
        if command == "status":
            return reply(True, "status")
        if command == "disconnect":
            self.connected = False
            if self.state == "BUSY":
                actions.append(self._finish("ERROR", now, reason="connection_lost"))
            return reply(True, "disconnected")
        if not self.connected:
            return reply(False, "not_connected")

        cycle_id = message.get("cycle_id")
        if not _text(cycle_id):
            return reply(False, "invalid_cycle_id")
        cycle = self.cycles.get(cycle_id)
        if command == "start":
            if not all(_text(message.get(key)) for key in REQUEST_FIELDS):
                return reply(False, "invalid_cycle_request")
            request = {key: message[key] for key in REQUEST_FIELDS}
            if cycle is not None:
                same = all(cycle[key] == value for key, value in request.items())
                return reply(same, "duplicate_start" if same else "cycle_id_conflict", cycle)
            if self.state != "READY":
                return reply(False, "not_ready")
            cycle = dict(request, started_at_seconds=now,
                deadline_seconds=now + self.timeout_seconds, completed_at_seconds=None,
                clock_kind=self.clock_kind, verdict=None, reason=None, result=None,
                acknowledged=False)
            self.cycles[cycle_id] = cycle
            self.active_cycle_id, self.state = cycle_id, "BUSY"
            actions.append(dict(kind="fake_inspection_request", cycle_id=cycle_id))
            return reply(True, "started")

        if command == "complete":
            result = {key: message.get(key) for key in
                      ("verdict", "prediction_ref", "result_source", "error")}
            if cycle is not None and cycle["result"] is not None:
                same = cycle["result"] == result
                return reply(same, "duplicate_result" if same else "result_conflict", cycle)
            if cycle_id != self.active_cycle_id or self.state != "BUSY":
                return reply(False, "stale_result", cycle)
            verdict = result["verdict"]
            valid = (isinstance(verdict, str) and verdict in TERMINAL
                     and _text(result["result_source"]))
            if verdict == "ERROR":
                valid = valid and _text(result["error"])
            else:
                valid = valid and _text(result["prediction_ref"])
            reason = result["error"] if verdict == "ERROR" and valid else None
            if not valid:
                verdict, reason = "ERROR", "invalid_or_missing_prediction"
            actions.append(self._finish(verdict, now, reason=reason, result=deepcopy(result)))
            return reply(True, "completed" if valid else "failed_invalid_result")

        if command == "acknowledge":
            if cycle is not None and cycle["acknowledged"]:
                return reply(True, "duplicate_acknowledge", cycle)
            if cycle_id != self.active_cycle_id or self.state not in TERMINAL:
                return reply(False, "not_terminal", cycle)
            cycle["acknowledged"] = True
            self.active_cycle_id, self.state = None, "READY"
            return reply(True, "acknowledged", cycle)
        return reply(False, "unknown_command")
