"""Create one SwinIR cache or query one existing CPU HOG bank in a separate process."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("cache", "infer", "evaluate"), required=True)
    parser.add_argument("--reference", type=Path, action="append", default=[])
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--include-fit", action="store_true")
    parser.add_argument("--reuse-cache", type=Path)
    args = parser.parse_args()
    if args.stage == "cache":
        if not args.reference or args.repository is None or args.checkpoint is None:
            parser.error("Cache requires --reference, --repository and --checkpoint")
        from sr_anomaly.cpu_restoration_control import cache_restoration
        result = cache_restoration(args.reference, args.output, args.repository, args.checkpoint,
            resume=args.resume, include_fit=args.include_fit, reuse_cache=args.reuse_cache)
    elif args.stage == "infer":
        if len(args.reference) != 1 or args.cache is None:
            parser.error("Inference requires one --reference and --cache")
        from sr_anomaly.cpu_restoration_control import infer_restored_control
        result = infer_restored_control(args.reference[0], args.cache, args.output)
    else:
        from sr_anomaly.cpu_hog_control import evaluate_category
        result = evaluate_category(args.output)
    print(json.dumps({k: result[k] for k in ("status",)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
