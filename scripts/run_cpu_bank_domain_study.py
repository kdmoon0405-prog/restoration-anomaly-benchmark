"""Fit fixed normal-bank controls and run all queries before any new GT evaluation."""
from pathlib import Path
import argparse
import importlib.metadata
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.analysis_io import digest, new_output, read_json, write_json
from sr_anomaly.cpu_bank_domain import (DomainInputs, NEW_BANKS, QUERIES, source_hashes,
    fit_domain_bank, infer_domain_query, evaluate_domain_query, export_core_matrix)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("full", "fit", "infer", "evaluate", "export"), default="full")
    parser.add_argument("--source-campaign", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--restored-reference", type=Path)
    parser.add_argument("--bank-directory", type=Path)
    parser.add_argument("--bank-domain", choices=NEW_BANKS)
    parser.add_argument("--query-domain", choices=QUERIES)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/cpu_bank_domain_study.json")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.stage != "full":
        if args.reference is None or args.restored_reference is None:
            parser.error("Worker needs --reference and --restored-reference")
        inputs = DomainInputs(args.reference, args.restored_reference, args.cache)
        if args.stage == "fit":
            result = fit_domain_bank(inputs, args.bank_domain, args.output)
        elif args.stage == "infer":
            result = infer_domain_query(inputs, args.bank_directory, args.query_domain, args.output)
        elif args.stage == "evaluate":
            result = evaluate_domain_query(inputs, args.output)
        else:
            result = export_core_matrix(inputs, args.bank_directory, args.output)
        print(json.dumps(dict(status=result["status"])))
        return 0
    if args.source_campaign is None:
        parser.error("Full study needs --source-campaign")
    config = read_json(args.config)
    if (tuple(config["new_bank_domains"]) != NEW_BANKS or tuple(config["query_domains"]) != QUERIES
            or config["normal_quantile"] != 0.99 or len(config["seeds"]) != len(set(config["seeds"]))
            or len(config["categories"]) != len(set(config["categories"]))):
        raise ValueError("Expected the fixed bank/query matrix and normal quantile")
    expected = read_json(ROOT / "analysis/cpu_research_20261108/environment.json")["packages"]
    for name in ("numpy", "scipy", "Pillow", "scikit-image", "scikit-learn", "torch", "timm"):
        if importlib.metadata.version(name) != expected[name]:
            raise ValueError("Prior bank/cache reuse needs the recorded environment: " + name)
    protocol = dict(config=config, code_sha256=source_hashes(),
        cache_status_sha256=digest(args.cache / "status.json"), source_campaign=str(args.source_campaign.resolve()))
    if args.resume:
        if read_json(args.output / "PROTOCOL.json") != protocol:
            raise ValueError("Resume protocol/source/cache changed")
        state = read_json(args.output / "status.json")
    else:
        new_output(args.output, [args.source_campaign, args.cache])
        write_json(args.output / "PROTOCOL.json", protocol)
        state = dict(status="RUNNING", worker_pid=os.getpid(), completed={})
    cases = []
    for seed in config["seeds"]:
        for category in config["categories"]:
            reference = args.source_campaign / ("hog-controls" if seed == 11 else f"hog-controls-seed{seed}") / f"{category}-seed{seed}"
            restored = args.source_campaign / "hog-swinir-controls" / reference.name
            cases.append((reference, restored, args.output / "runs" / reference.name))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", OPENBLAS_NUM_THREADS="4", OMP_NUM_THREADS="4", MKL_NUM_THREADS="4")
    try:
        for stage in ("fit", "infer", "evaluate", "export"):
            for reference, restored, run in cases:
                banks = NEW_BANKS if stage != "export" else (None,)
                for bank in banks:
                    queries = QUERIES if stage in ("infer", "evaluate") else (None,)
                    for query in queries:
                        name = "-".join(str(x) for x in (stage, reference.name, bank, query) if x is not None)
                        if name in state["completed"]:
                            receipt = state["completed"][name]
                            if digest(Path(receipt["file"])) != receipt["sha256"]:
                                raise ValueError("Completed study worker artifact changed")
                            continue
                        target = (run / bank / "bank") if stage == "fit" else (run / bank / query) if stage in ("infer", "evaluate") else args.output / "core-results" / reference.name
                        command = [sys.executable, "-u", str(Path(__file__).resolve()), "--stage", stage,
                            "--reference", str(reference), "--restored-reference", str(restored),
                            "--cache", str(args.cache), "--output", str(target)]
                        if bank is not None:
                            command += ["--bank-domain", bank, "--bank-directory", str(run / bank / "bank")]
                        else:
                            command += ["--bank-directory", str(run)]
                        if query is not None:
                            command += ["--query-domain", query]
                        state.update(status="RUNNING", worker_pid=os.getpid(), phase=name)
                        write_json(args.output / "status.json", state)
                        print("START", name, flush=True)
                        with (args.output / (name + ".log")).open("w", encoding="utf-8") as log:
                            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
                        if result.returncode:
                            raise RuntimeError(f"Worker {name} failed with exit {result.returncode}")
                        receipt = target / ("bank_domain_manifest.json" if stage == "export" else
                                            "query_predictions.npz" if stage == "infer" else "status.json")
                        state["completed"][name] = dict(file=str(receipt), sha256=digest(receipt))
                        write_json(args.output / "status.json", state)
        state.update(status="CPU_BANK_DOMAIN_COMPLETE", worker_pid=None,
            newly_fitted_banks=len(cases) * len(NEW_BANKS),
            new_query_conditions=len(cases) * len(NEW_BANKS) * len(QUERIES),
            reused_clean_conditions=len(cases) * len(QUERIES),
            matrix_conditions=len(cases) * (len(NEW_BANKS) + 1) * len(QUERIES))
        write_json(args.output / "status.json", state)
        print(state["status"])
        return 0
    except BaseException as error:
        state.update(status="FAILED", worker_pid=None, error=f"{type(error).__name__}: {error}")
        write_json(args.output / "status.json", state)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
