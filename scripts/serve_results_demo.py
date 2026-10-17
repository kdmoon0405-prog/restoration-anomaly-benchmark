"""Loopback-only, read-only viewer of stored Branch B results; no model imports."""
from __future__ import annotations

import argparse
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

import matplotlib
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from scripts.analyze_fusion_weights import _load_prediction
from scripts.analyze_map_gating_feasibility import digest, read_json, relative, select_candidate, validate_predictions
from sr_anomaly.map_gating import gated_maps

DEFAULT_ANALYSIS = ROOT / "analysis/map_gating_feasibility/hazelnut-branchb-20261014"
DEFAULT_SOURCE = ROOT / "outputs/fusion-patchcore/hazelnut-313x78-test110"
DEFAULT_RAW = ROOT / "outputs/map-gating-feasibility/hazelnut-branchb-20261014"


def csv_values(path):
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key, value in row.items():
            if value == "":
                row[key] = None
            elif key not in {"sample", "method", "defect_type"}:
                try:
                    row[key] = float(value)
                except ValueError:
                    pass
    return rows


class StoredResults:
    def __init__(self, analysis=DEFAULT_ANALYSIS, source=DEFAULT_SOURCE, raw=DEFAULT_RAW):
        self.analysis, self.source, self.raw = analysis, source, raw
        self.protocol = read_json(analysis / "PROTOCOL.json")
        self.result = read_json(source / "results.json")
        raw_meta = read_json(raw / "results.json")
        self.paths = self.result["test_paths"]
        if (self.protocol["model_spec"] != self.result["model_spec"] or self.protocol["cohort"] != self.paths
                or self.protocol["calibration"] != self.result["fusion_calibration"]
                or raw_meta["test_paths"] != self.paths or digest(analysis / "PROTOCOL.json") != raw_meta["protocol_sha256"]):
            raise ValueError("Viewer source/bank/cohort/protocol provenance mismatch")
        self.predictions = {name: _load_prediction(source / f"{name}_predictions.npz") for name in
                            ("degraded_only", "restored_only", "mean_0.5_0.5", "max")}
        validate_predictions(self.predictions, self.paths)
        self.calibration = self.result["fusion_calibration"]
        self.tau_deg, self.tau_rest = (self.calibration["pixel_thresholds"][name] for name in ("degraded_only", "restored_only"))
        expected = gated_maps(self.predictions["degraded_only"]["maps"], self.predictions["restored_only"]["maps"], self.tau_deg, self.tau_rest)
        reference = self.predictions["restored_only"]
        for name in ("candidate_1", "candidate_2"):
            item = _load_prediction(raw / f"{name}_predictions.npz")
            if not np.array_equal(item["maps"], expected[name]) or any(not np.array_equal(item[key], reference[key]) for key in ("labels", "scores", "masks")):
                raise ValueError(f"Candidate stored maps/labels/masks/scores disagree: {name}")
            self.predictions[name] = item
        self.summary = csv_values(analysis / "summary.csv")
        self.per_image = {(row["sample"], row["method"]): row for row in csv_values(analysis / "per_image.csv")}
        self.quality = {row["sample"]: row for row in csv_values(source / "per_image.csv")}
        if len(self.per_image) != len(self.paths) * len(self.predictions):
            raise ValueError("Per-image CSV must cover every sample and method")
        self.rgb_root = ROOT / "outputs/partial-restoration-feasibility/pilot10"
        self.rgb_paths = []
        if (self.rgb_root / "protocol.json").exists():
            pilot = read_json(self.rgb_root / "protocol.json")["inputs"]
            hashes = {k.replace("\\", "/"): v for k, v in pilot["source_sha256"].items()}
            if (pilot["model_spec"] == self.result["model_spec"]
                    and hashes.get(relative(source / "results.json")) == digest(source / "results.json")):
                self.rgb_paths = pilot["cohort"]

    def catalog(self):
        if getattr(self, "unavailable", None):
            return {"blocked": self.unavailable}
        selected = select_candidate(self.summary)
        return {"samples": [{"index": i, "sample": sample, "category": self.result["model_spec"]["category"],
                             "defect_type": Path(sample).parts[-2], "label": int(self.predictions["restored_only"]["labels"][i])}
                            for i, sample in enumerate(self.paths)],
                "variants": list(self.predictions), "summary": self.summary, "source_run": relative(self.source),
                "colormap_stops": [matplotlib.colors.to_hex(color) for color in matplotlib.colormaps["viridis"](np.linspace(0, 1, 17))],
                "analysis": relative(self.analysis), "raw_candidate_run": relative(self.raw),
                "scope": self.protocol["scope"], "selection": (
                    "Negative feasibility: neither candidate exceeds restored_only; no selected candidate" if selected is None
                    else f"Stored development selection: {selected}; not independent validation"),
                "limitations": "Development data; no candidate F1/calibrated FPR; no live/verified risk alarm; map scores are not probabilities. GT is evaluation overlay only."}

    def sample(self, index, variant):
        if not 0 <= index < len(self.paths) or variant not in self.predictions:
            raise ValueError("Unknown sample index or variant")
        maps = [item["maps"][index] for item in self.predictions.values()]
        sample = self.paths[index]
        row = self.per_image[sample, variant]
        quality = self.quality[sample]
        return {"sample": sample, "variant": variant, "per_image": row,
                "scale": {"vmin": float(min(m.min() for m in maps)), "vmax": float(max(m.max() for m in maps))},
                "discrepancy_scale": {"vmin": 0., "vmax": float(np.maximum(
                    self.predictions["degraded_only"]["maps"][index] - self.predictions["restored_only"]["maps"][index], 0).max())},
                "units": "per-branch normal-calibration median/IQR normalized anomaly score; stored map coordinates",
                "tau_deg": self.tau_deg, "tau_rest": self.tau_rest, "gate_uses_gt": False,
                "rgb_available": {kind: self.rgb_file(index, kind) is not None for kind in ("degraded_rgb", "restored_rgb")},
                "rgb_provenance": "Historical partial pilot10 subset; identical Branch B bank/source identity verified. Other samples unavailable; never inferred by viewer.",
                "quality": {key: quality.get(key) for key in ("psnr_bicubic", "ssim_bicubic", "psnr_swinir", "ssim_swinir")},
                "quality_note": "Stored baseline quality only (PSNR in dB; SSIM dimensionless). Candidate map gates create no RGB, PSNR/SSIM/LPIPS or new image scores."}

    def rgb_file(self, index, kind):
        sample = self.paths[index]
        if sample not in self.rgb_paths:
            return None
        suffix = {"degraded_rgb": "bicubic", "restored_rgb": "full_swinir"}.get(kind)
        if suffix is None:
            return None
        path = self.rgb_root / f"{Path(sample).parts[-2]}-{Path(sample).stem}-{suffix}.png"
        return path if path.is_file() else None

    def panel(self, index, kind, overlay=False):
        if not 0 <= index < len(self.paths):
            raise ValueError("Unknown sample index")
        if kind in {"degraded_rgb", "restored_rgb"}:
            path = self.rgb_file(index, kind)
            return path.read_bytes() if path else None
        degraded = self.predictions["degraded_only"]["maps"][index]
        restored = self.predictions["restored_only"]["maps"][index]
        mask = self.predictions["restored_only"]["masks"][index].astype(bool)
        if kind in self.predictions:
            values = self.predictions[kind]["maps"][index]
            scale = self.sample(index, kind)["scale"]
            lo, hi = scale["vmin"], scale["vmax"]
        elif kind == "discrepancy":
            values = np.maximum(degraded - restored, 0)
            lo, hi = 0., float(values.max())
        elif kind in {"gate_1", "gate_2", "gt"}:
            values = (degraded > self.tau_deg) if kind == "gate_1" else (
                (degraded > self.tau_deg) & (restored <= self.tau_rest) if kind == "gate_2" else mask)
            lo, hi = 0., 1.
        else:
            raise ValueError("Unknown panel")
        unit = np.clip((values - lo) / (hi - lo), 0, 1) if hi > lo else np.zeros_like(values)
        rgb = (matplotlib.colormaps["viridis"](unit)[..., :3] * 255).astype(np.uint8)
        if overlay:
            padded = np.pad(mask, 1)
            interior = mask & padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
            rgb[mask & ~interior] = (255, 40, 40)
        buffer = BytesIO()
        Image.fromarray(rgb).save(buffer, format="PNG")
        return buffer.getvalue()


def handler_for(state):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in allowed:
                self.send_error(403)
                return
            request = urlparse(self.path)
            query = parse_qs(request.query)
            try:
                if request.path == "/":
                    data, mime = (ROOT / "demo_results/index.html").read_bytes(), "text/html; charset=utf-8"
                elif request.path == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                    return
                elif request.path == "/api/catalog":
                    data, mime = json.dumps(state.catalog(), ensure_ascii=False, allow_nan=False).encode(), "application/json"
                elif request.path in {"/api/sample", "/api/panel"}:
                    if getattr(state, "unavailable", None):
                        self.send_error(503, "Required saved artifacts unavailable")
                        return
                    index = int(query.get("index", ["0"])[0])
                    if request.path == "/api/sample":
                        payload = state.sample(index, query.get("variant", ["restored_only"])[0])
                        data, mime = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(), "application/json"
                    else:
                        data = state.panel(index, query.get("kind", ["restored_only"])[0], query.get("overlay", ["0"])[0] == "1")
                        mime = "image/png"
                        if data is None:
                            self.send_error(404, "Saved RGB unavailable")
                            return
                elif request.path == "/export/summary.csv":
                    if getattr(state, "unavailable", None):
                        self.send_error(503, "Required saved artifacts unavailable")
                        return
                    data, mime = (state.analysis / "summary.csv").read_bytes(), "text/csv; charset=utf-8"
                else:
                    self.send_error(404)
                    return
            except (ValueError, IndexError, KeyError) as error:
                self.send_error(400, str(error))
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            self.send_error(405, "Read-only viewer")
        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--raw-run", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        state = StoredResults(args.analysis, args.source_run, args.raw_run)
    except (OSError, KeyError, TypeError, ValueError) as error:
        state = StoredResults.__new__(StoredResults)
        state.unavailable = str(error).replace(str(ROOT), "repository").replace(ROOT.as_posix(), "repository")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(state))
    print(f"Read-only local results: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
