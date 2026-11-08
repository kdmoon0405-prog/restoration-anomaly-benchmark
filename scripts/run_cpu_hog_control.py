"""Run real CPU HOG controls with inference/evaluation process separation."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("full", "infer", "evaluate"), default="full")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--category")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/cpu_hog_control.json")
    parser.add_argument("--input-manifest", type=Path)
    parser.add_argument("--campaign-status", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    settings = json.loads(args.config.read_text(encoding="utf-8"))
    if args.stage == "full":
        args.output.mkdir(parents=True, exist_ok=args.resume)
        for category in settings["categories"]:
            out = args.output / (category + "-seed" + str(settings["seed"]))
            previous = json.loads((out / "status.json").read_text(encoding="utf-8")) if (out / "status.json").exists() else None
            if previous is not None:
                if not args.resume or previous["settings"] != settings:
                    raise ValueError("Existing run needs explicit resume with the same settings")
                expected = hashlib.sha256((ROOT / "src/sr_anomaly/cpu_hog_control.py").read_bytes()).hexdigest()
                if previous.get("source_code_sha256") != expected:
                    raise ValueError("Existing run source differs or inference is incomplete")
                if previous["status"] == "EVALUATED_COMPLETE":
                    for name, sha in previous["artifact_sha256"].items():
                        if hashlib.sha256((out / name).read_bytes()).hexdigest() != sha:
                            raise ValueError("Completed result changed")
                    continue
            common = [sys.executable, "-u", str(Path(__file__).resolve()), "--output", str(out),
                      "--config", str(args.config.resolve())]
            infer = [*common, "--stage", "infer", "--category", category, "--data-root", str(args.data_root)]
            if args.input_manifest:
                infer += ["--input-manifest", str(args.input_manifest.resolve())]
            for stage, command in (("infer", infer), ("evaluate", [*common, "--stage", "evaluate"])):
                if stage == "infer" and previous is not None and previous["status"] == "INFERENCE_COMPLETE":
                    continue
                with (args.output / f"{category}-{stage}.log").open("w", encoding="utf-8") as log:
                    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                    if args.campaign_status:
                        args.campaign_status.write_text(json.dumps(dict(status="RUNNING", stage="cpu_hog_control",
                            worker_pid=os.getpid(), child_pid=child.pid, category=category, phase=stage,
                            output=str(args.output), completed=["spatial_budget_analysis", "normal_calibrated_operating_points"]),indent=2)+"\n",encoding="utf-8")
                    code = child.wait()
                if code:
                    if args.campaign_status:
                        args.campaign_status.write_text(json.dumps(dict(status="PHASE_FAILED",
                            worker_pid=None, category=category, phase=stage, output=str(args.output),
                            exit_code=code, log=str(args.output / f"{category}-{stage}.log")),indent=2)+"\n",encoding="utf-8")
                    print(json.dumps(dict(status="PHASE_FAILED", category=category, stage=stage, exit_code=code)))
                    return code
        if args.campaign_status:
            args.campaign_status.write_text(json.dumps(dict(status="CPU_HOG_COMPLETE",
                worker_pid=None, completed=["spatial_budget_analysis", "normal_calibrated_operating_points", "cpu_hog_control"],
                hog_output=str(args.output), next_action="Final figures, report and source publication"),indent=2)+"\n",encoding="utf-8")
        print(json.dumps(dict(status="CPU_HOG_COMPLETE", categories=settings["categories"])))
        return 0
    from sr_anomaly.cpu_hog_control import infer_category, evaluate_category
    if args.stage == "infer":
        if not args.data_root or not args.category:
            parser.error("Inference requires --data-root and --category")
        result = infer_category(args.data_root, args.output, settings, args.category,
                                input_manifest=args.input_manifest)
    else:
        result = evaluate_category(args.output)
    print(json.dumps({k: result[k] for k in ("status", "category", "test_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
