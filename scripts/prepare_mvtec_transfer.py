"""Prepare or verify a category-only, noncommercial MVTec AD input transfer."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.mvtec_transfer import prepare_transfer, verify_transfer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--category", action="append")
    parser.add_argument("--seed", type=int, action="append")
    parser.add_argument("--pack", action="store_true")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.verify:
            result = verify_transfer(args.verify, args.data_root, categories=args.category)
        else:
            if args.output is None:
                parser.error("--output is required for preparation")
            result = prepare_transfer(args.data_root, args.output,
                categories=args.category or ("hazelnut", "screw", "capsule"),
                seeds=args.seed or (11, 23, 37), pack=args.pack)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
