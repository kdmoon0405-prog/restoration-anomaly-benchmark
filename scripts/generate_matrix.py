from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.matrix import generate_experiment_matrix  # noqa: E402


def main() -> int:
    parser = ArgumentParser(description="Generate bounded experiment configs")
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    generated = generate_experiment_matrix(args.matrix, args.output_dir)
    print(f"Generated {len(generated)} configs in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

