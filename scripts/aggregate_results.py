from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.reporting import aggregate_results  # noqa: E402


def main() -> int:
    parser = ArgumentParser(description="Aggregate result CSV files and build a comparison table")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    combined, comparison = aggregate_results(args.inputs, args.output_dir)
    print(combined)
    print(comparison)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

