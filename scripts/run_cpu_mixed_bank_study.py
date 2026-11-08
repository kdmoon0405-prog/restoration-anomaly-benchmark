"""Evaluate one pre-fixed balanced bank using the existing bank-domain query workers."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import digest, new_output, read_json, write_json
from sr_anomaly.cpu_bank_mix import construct_balanced_bank


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--source-campaign", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if read_json(args.execution / "status.json")["status"] != "CPU_BANK_DOMAIN_COMPLETE":
        raise ValueError("Matched-bank experiment is incomplete")
    new_output(args.output, [args.execution, args.source_campaign, args.cache])
    plan = read_json(args.execution / "PROTOCOL.json")["config"]
    protocol = dict(ratio=0.5, capacity_policy="same reference ordinals and total capacity",
        assignment_seed_policy="study seed plus20261109", query_calibration="normal only, separately per query",
        source_execution_sha256=digest(args.execution / "status.json"),
        constructor_sha256=digest(ROOT / "src/sr_anomaly/cpu_bank_mix.py"))
    write_json(args.output / "PROTOCOL.json", protocol)
    state = dict(status="RUNNING", worker_pid=os.getpid(), completed=[])
    write_json(args.output / "status.json", state)
    cases = []
    for seed in plan["seeds"]:
        for category in plan["categories"]:
            name = f"{category}-seed{seed}"
            previous = args.execution / "runs" / name
            out = args.output / "runs" / name / "balanced_mixed"
            construct_balanced_bank(previous / "bicubic_matched/bank", previous / "swinir_restored/bank", out / "bank")
            reference = args.source_campaign / ("hog-controls" if seed == 11 else f"hog-controls-seed{seed}") / name
            restored_reference = args.source_campaign / "hog-swinir-controls" / name
            cases.append((name, out, reference, restored_reference))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", OPENBLAS_NUM_THREADS="4", OMP_NUM_THREADS="4", MKL_NUM_THREADS="4")
    try:
        for stage in ("infer", "evaluate"):
            for name, out, reference, restored_reference in cases:
                for query in ("bicubic_x4", "swinir_x4"):
                    phase = f"{stage}-{name}-{query}"
                    state.update(phase=phase)
                    write_json(args.output / "status.json", state)
                    command = [sys.executable, "-u", str(ROOT / "scripts/run_cpu_bank_domain_study.py"),
                        "--stage", stage, "--reference", str(reference), "--restored-reference", str(restored_reference),
                        "--cache", str(args.cache), "--bank-directory", str(out / "bank"),
                        "--query-domain", query, "--output", str(out / query)]
                    print("START", phase, flush=True)
                    with (args.output / (phase + ".log")).open("w", encoding="utf-8") as log:
                        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
                    if result.returncode:
                        raise RuntimeError("Mixed-bank worker failed: " + phase)
                    state["completed"].append(phase)
                    write_json(args.output / "status.json", state)
        state.update(status="CPU_MIXED_BANK_COMPLETE", worker_pid=None, constructed_banks=len(cases),
                     new_query_conditions=len(cases) * 2)
        write_json(args.output / "status.json", state)
        print(state["status"])
        return 0
    except BaseException as error:
        state.update(status="FAILED", worker_pid=None, error=f"{type(error).__name__}: {error}")
        write_json(args.output / "status.json", state)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
