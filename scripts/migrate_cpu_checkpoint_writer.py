"""Verify a checkpoint-I/O-only source change before resuming a failed CPU RGB cache."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly.cpu_checkpoint_recovery import migrate_writer

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--previous-source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(migrate_writer(args.cache, args.previous_source)))
