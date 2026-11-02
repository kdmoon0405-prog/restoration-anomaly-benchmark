"""Check a metadata ZIP once and cache its receipt by content hash."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.artifact_receipts import review_archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = review_archive(args.archive, args.cache)
        print(json.dumps({k: receipt[k] for k in ("status", "archive_sha256", "cache_hit",
                                                "manifest_entries_verified")}))
        return 0
    except (ValueError, OSError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
