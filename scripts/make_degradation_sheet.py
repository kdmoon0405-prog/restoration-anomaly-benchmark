from argparse import ArgumentParser
from pathlib import Path
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.visualize import degradation_contact_sheet  # noqa: E402


def main() -> int:
    parser = ArgumentParser(description="Render all degradation severities for visual inspection")
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    with Image.open(args.image) as image:
        print(degradation_contact_sheet(image, args.output, seed=args.seed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

