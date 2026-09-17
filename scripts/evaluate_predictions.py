from argparse import ArgumentParser
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.evaluation import evaluate_predictions  # noqa: E402


def main() -> int:
    parser = ArgumentParser(description="Evaluate image scores and optional pixel anomaly maps from an NPZ file")
    parser.add_argument("predictions", type=Path, help="NPZ keys: labels, scores, and optionally masks, anomaly_maps")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-threshold", type=float)
    parser.add_argument("--pixel-threshold", type=float)
    parser.add_argument("--max-fpr", type=float, default=0.3)
    args = parser.parse_args()
    with np.load(args.predictions, allow_pickle=False) as data:
        result = evaluate_predictions(
            data["labels"],
            data["scores"],
            data["masks"] if "masks" in data else None,
            data["anomaly_maps"] if "anomaly_maps" in data else None,
            args.image_threshold,
            args.pixel_threshold,
            args.max_fpr,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

