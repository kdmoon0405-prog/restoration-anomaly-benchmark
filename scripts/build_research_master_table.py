"""Combine stored reporting sources without merging distinct experiment families."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.research_reporting import build_master


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--catalog", type=Path, default=ROOT / "configs/research_reporting_sources.json")
    parser.add_argument("--bank-analysis", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_master(args.catalog, args.root, args.output,
            bank_analyses=args.bank_analysis, allow_synthetic=args.allow_synthetic)
        print(json.dumps({k: result[k] for k in ("rows", "protocol_groups")}))
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
