"""Read stored 2x2 results; no model, image, GT or raw prediction loading."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.bank_domain_analysis import analyze_runs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/bank_domain_analysis.json")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = analyze_runs(args.run, args.output, config=args.config,
            allow_synthetic=args.allow_synthetic, source_root=args.source_root)
        print(json.dumps({k: report[k] for k in ("status", "complete_unique_runs", "evidence_kinds")}))
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
