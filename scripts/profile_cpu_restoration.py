"""Measure three fixed normal-calibration SwinIR CPU queries using the existing adapter."""
from pathlib import Path
import argparse
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import digest, new_output, read_json, relative_source, write_csv, write_json
from sr_anomaly.pcb_native_memory import available_ram, process_memory

CHECKPOINT_SHA256 = "09fad24e32ae62722e1a055efde9921328f4137981bab0a42a4a3a806306c58e"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-run", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = read_json(args.control_run / "status.json")
    if state["status"] != "EVALUATED_COMPLETE":
        raise ValueError("CPU control reference is incomplete")
    if digest(args.checkpoint) != CHECKPOINT_SHA256:
        raise ValueError("Expected the fixed SwinIR-S x4 checkpoint")
    network = args.repository / "models/network_swinir.py"
    source_sha = digest(network)
    receipts = read_json(args.control_run / "rgb_receipts.json")
    samples = sorted(read_json(args.control_run / "split.json")["calibration_paths"])[:3]
    if len(samples) != 3:
        raise ValueError("Need three distinct normal-calibration inputs")
    required = 1280 * 1024**2
    available = available_ram()
    out = new_output(args.output, [args.control_run, args.repository])
    status = dict(status="PREFLIGHT_PASS" if available >= required else "BLOCKED_MEMORY",
        scope="three normal-calibration CPU restoration queries; no detector or test selection",
        requested_device="cpu", sample_paths=samples,
        required_available_bytes=required, available_before_bytes=available,
        checkpoint_sha256=CHECKPOINT_SHA256, network_sha256=source_sha,
        adapter_sha256=digest(ROOT / "src/sr_anomaly/real_models.py"),
        source_status_sha256=digest(args.control_run / "status.json"),
        code_sha256=digest(Path(__file__)))
    write_json(out / "status.json", status)
    if available < required:
        return 2
    import torch
    from PIL import Image
    from sr_anomaly.real_models import SwinIRLightweight
    from sr_anomaly.metrics import psnr, ssim
    torch.set_num_threads(4)
    started = time.perf_counter()
    model = SwinIRLightweight(args.repository, args.checkpoint, device="cpu", scale=4)
    status["initialization_seconds"] = time.perf_counter() - started
    rows = []
    for sample in samples:
        source = relative_source(args.control_run / "canonical", sample)
        if digest(source) != receipts[sample]["canonical_file_sha256"]:
            raise ValueError("Canonical input cache changed")
        with Image.open(source) as image:
            clean = image.convert("RGB")
        low = clean.resize((56, 56), Image.Resampling.BICUBIC)
        started = time.perf_counter()
        restored = model.restore(low)
        seconds = time.perf_counter() - started
        if restored.size != (224, 224):
            raise ValueError("SwinIR output is not canonical224")
        destination = out / (str(len(rows)) + ".png")
        restored.save(destination)
        rows.append(dict(sample=sample, input_sha256=digest(source), output_sha256=digest(destination),
            restoration_seconds=seconds, psnr=psnr(clean, restored), ssim=ssim(clean, restored)))
    write_csv(out / "queries.csv", rows)
    status.update(status="CPU_SWINIR_THREE_QUERY_COMPLETE", queries=len(rows),
        process_memory=process_memory(), torch_version=torch.__version__, actual_device="cpu",
        available_after_bytes=available_ram(), query_csv_sha256=digest(out / "queries.csv"))
    write_json(out / "status.json", status)
    print(status["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
