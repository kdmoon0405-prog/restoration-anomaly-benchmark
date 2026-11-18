"""DEVELOPMENT variant of the phone station: register each photo to the reference taken under its expected light.

Candidate change "v0.4-candidate same-light registration", chosen AFTER the fixed v0.3 evaluation of session
2026-11-18 showed that every L1 photo failed to register to the L0 anchor (lighting change, not pose change).
Results of this script on that session are development evidence; the candidate has to be evaluated on a new session.

What changes: phone_capture.align is called by the unchanged station runner with (anchor luma, photo luma); this
wrapper replaces the first argument by the luma of the sheet's reference photo for the photo's expected light
(L1 rows -> reference L1; L0 and other lights -> reference L0). Everything else is the unchanged runner: quality v0.3,
golden-reference inspection, normal-only calibration, cycle logic, outputs.
Assumption (recorded in the manifest): the L0 and L1 references share the camera pose (fixed phone, only the lamp
moved), so the recipe ROI fractions apply in both reference frames and the inspection frames are the references'.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("station_runner", HERE / "run_phone_station_compare.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
pc = runner.pc
VARIANT = "v0.4-candidate same-light registration (development)"


def install(folder: Path, plan_refs: dict[str, str]) -> dict:
    """Map each photo's working luma bytes to the luma of its same-light reference."""
    rows = list(csv.DictReader(open(folder / "capture_sheet.csv", encoding="utf-8")))
    ref_luma = {light: pc.luma(pc.working(pc.decode(folder / f)[0])[0]) for light, f in plan_refs.items()}
    target = {}
    for r in rows:
        light = r["light"] if r["light"] in ref_luma else "L0"
        y = pc.luma(pc.working(pc.decode(folder / r["file"])[0])[0])
        target[sha256(y.tobytes()).hexdigest()] = (light, r["file"])
    original_align = pc.align
    used = {}

    def align(reference_y, moving_y):
        key = sha256(moving_y.tobytes()).hexdigest()
        light, name = target.get(key, ("L0", None))
        used[name] = light
        return original_align(ref_luma[light], moving_y)

    pc.align = align
    return used


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    folder = Path(argv[argv.index("--input") + 1])
    output = Path(argv[argv.index("--output") + 1])
    rows = list(csv.DictReader(open(folder / "capture_sheet.csv", encoding="utf-8")))
    refs = {r["light"]: r["file"] for r in rows if r.get("station_role") == "reference"}
    used = install(folder, refs)
    code = runner.main(argv)
    m = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    m["development_variant"] = dict(name=VARIANT, registration_reference_by_light=refs, photos_registered_to=used,
                                    assumption="L0 and L1 references share the camera pose; ROI fractions applied in each reference frame",
                                    evidence_kind="development (method chosen after the fixed v0.3 evaluation of the same session)",
                                    wrapper=Path(__file__).name, wrapper_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    (output / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    report = output / "report.html"
    if report.is_file():
        t = report.read_text(encoding="utf-8")
        report.write_text(t.replace("<h1>", "<p class=\"note\"><b>DEVELOPMENT VARIANT</b>: " + VARIANT +
                                    " - not the fixed evaluation method.</p><h1>", 1), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
