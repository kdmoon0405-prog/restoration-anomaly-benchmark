from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sr_anomaly.runner import run_experiment  # noqa: E402


def main() -> int:
    scratch_root = ROOT / "outputs"
    scratch_root.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="sr-anomaly-smoke-", dir=scratch_root) as temporary:
        root = Path(temporary)
        image_dir = root / "images"
        image_dir.mkdir()
        y, x = np.mgrid[:24, :24]
        array = np.stack(((x * 11) % 256, (y * 13) % 256, ((x + y) * 7) % 256), axis=-1).astype(np.uint8)
        Image.fromarray(array, "RGB").save(image_dir / "synthetic.png")
        config = {
            "experiment": {"id": "smoke", "seed": 7},
            "dataset": {"root": "images", "recursive": True},
            "degradations": [{"name": "gaussian_noise", "severity": 1}],
            "restoration": {"name": "identity"},
            "anomaly_detector": {"name": "noop"},
            "metrics": ["psnr", "ssim"],
            "output_root": "outputs",
        }
        config_path = root / "smoke.yaml"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        run_dir = run_experiment(config_path)
        rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert {row["variant"] for row in rows} == {"no_restoration", "restored"}
        print(f"CPU smoke test passed: {len(rows)} result rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
