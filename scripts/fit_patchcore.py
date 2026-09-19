from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys

import numpy as np
from PIL import Image

from sr_anomaly.real_models import PatchCoreTorchAdapter


MVTEC_ARCHIVE_SHA256 = "cf4313b13603bec67abb49ca959488f7eedce2a9f7795ec54446c649ac98cd3d"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit and export a CPU PatchCore model for one MVTec AD category")
    parser.add_argument("--data-root", type=Path, default=Path("data/external/MVTecAD"))
    parser.add_argument("--category", default="bottle")
    parser.add_argument("--output-dir", type=Path, default=Path("checkpoints/patchcore/bottle-seed11"))
    parser.add_argument("--run-dir", type=Path, default=Path("outputs/patchcore-fit-bottle-seed11"))
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--normal-quantile", type=float, default=0.99)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--coreset-ratio", type=float, default=0.1)
    parser.add_argument("--evaluation-size", type=int, default=256)
    parser.add_argument("--checkpoint", type=Path, help="Resume export and calibration from an existing Lightning checkpoint")
    args = parser.parse_args()

    if not 0 < args.val_ratio < 1:
        parser.error("--val-ratio must be in (0, 1)")
    if not 0 < args.normal_quantile < 1:
        parser.error("--normal-quantile must be in (0, 1)")
    output_dir = args.output_dir.resolve()
    run_dir = args.run_dir.resolve()
    artifact = output_dir / "weights" / "torch" / f"patchcore_{args.category}.pt"
    if output_dir.exists() and any(output_dir.iterdir()) and not (args.checkpoint and artifact.is_file()):
        raise FileExistsError(f"Refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    import anomalib
    import lightning
    import torch
    import torchvision
    from anomalib.data import MVTecAD
    from anomalib.data.utils import ValSplitMode
    from anomalib.deploy import ExportType
    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    lightning.seed_everything(args.seed, workers=True)
    datamodule = MVTecAD(
        # Anomalib 2.6.2 rejects non-ASCII absolute paths before resolving them.
        # Keeping the CLI default relative also works when the repository path is Korean.
        root=args.data_root,
        category=args.category,
        train_batch_size=args.batch_size,
        eval_batch_size=args.batch_size,
        num_workers=0,
        val_split_mode=ValSplitMode.FROM_TRAIN,
        val_split_ratio=args.val_ratio,
        seed=args.seed,
    )
    model = Patchcore(
        backbone="wide_resnet50_2",
        layers=("layer2", "layer3"),
        coreset_sampling_ratio=args.coreset_ratio,
        num_neighbors=9,
        evaluator=False,
        visualizer=False,
    )
    engine = Engine(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        logger=False,
        default_root_dir=run_dir,
        enable_model_summary=False,
        enable_progress_bar=False,
        limit_val_batches=0,
        num_sanity_val_steps=0,
    )
    if args.checkpoint is None:
        engine.fit(model=model, datamodule=datamodule)
    else:
        datamodule.prepare_data()
        datamodule.setup("fit")
    if not artifact.is_file():
        artifact = engine.export(
            model=model,
            export_type=ExportType.TORCH,
            export_root=output_dir,
            model_file_name=f"patchcore_{args.category}",
            datamodule=datamodule,
            ckpt_path=args.checkpoint,
        )
    if artifact is None or not artifact.is_file():
        raise RuntimeError("Anomalib did not return a Torch export artifact")
    artifact = artifact.resolve()

    train_paths = _dataset_paths(datamodule.train_data)
    validation_paths = _dataset_paths(datamodule.val_data)
    if not validation_paths:
        raise RuntimeError("Normal validation split is empty")
    detector = PatchCoreTorchAdapter(artifact, align_to_input=False, trusted_local_artifact=True)
    validation_scores: list[float] = []
    validation_pixels: list[np.ndarray] = []
    for path in validation_paths:
        with Image.open(path) as opened:
            prediction = detector.predict(opened.convert("RGB"))
        validation_scores.append(float(prediction.image_score))
        validation_pixels.append(_resize_map(prediction.pixel_map, args.evaluation_size).ravel())
    image_threshold = float(np.quantile(validation_scores, args.normal_quantile))
    pixel_threshold = float(np.quantile(np.concatenate(validation_pixels), args.normal_quantile))

    split = {
        "seed": args.seed,
        "validation_ratio": args.val_ratio,
        "train": [_portable(path, args.data_root.resolve()) for path in train_paths],
        "validation": [_portable(path, args.data_root.resolve()) for path in validation_paths],
    }
    (output_dir / "split.json").write_text(json.dumps(split, indent=2), encoding="utf-8")
    calibration = {
        "source": "held-out normal training images",
        "quantile": args.normal_quantile,
        "evaluation_size": [args.evaluation_size, args.evaluation_size],
        "image_threshold": image_threshold,
        "pixel_threshold": pixel_threshold,
        "validation_image_scores": validation_scores,
    }
    (output_dir / "calibration.json").write_text(json.dumps(calibration, indent=2), encoding="utf-8")
    metadata = {
        "artifact": artifact.relative_to(output_dir).as_posix(),
        "artifact_sha256": _sha256(artifact),
        "category": args.category,
        "seed": args.seed,
        "train_count": len(train_paths),
        "validation_count": len(validation_paths),
        "coreset_sampling_ratio": args.coreset_ratio,
        "backbone": "wide_resnet50_2",
        "layers": ["layer2", "layer3"],
        "dataset_archive_sha256": MVTEC_ARCHIVE_SHA256,
        "dataset_source": "https://www.mvtec.com/research-teaching/datasets/mvtec-ad",
        "dataset_license": "CC BY-NC-SA 4.0",
        "python": platform.python_version(),
        "anomalib": anomalib.__version__,
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "command": [sys.executable, *sys.argv],
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(artifact)


def _dataset_paths(dataset: object) -> list[Path]:
    samples = getattr(dataset, "samples", None)
    if samples is not None and hasattr(samples, "columns") and "image_path" in samples.columns:
        return [Path(value).resolve() for value in samples["image_path"].tolist()]
    paths: list[Path] = []
    for item in dataset:  # type: ignore[union-attr]
        value = getattr(item, "image_path", None)
        if value is None:
            raise RuntimeError("Cannot recover image paths from Anomalib dataset")
        paths.append(Path(value).resolve())
    return paths


def _resize_map(anomaly_map: np.ndarray | None, size: int) -> np.ndarray:
    if anomaly_map is None:
        raise ValueError("PatchCore did not return an anomaly map")
    return np.asarray(Image.fromarray(anomaly_map.astype(np.float32), mode="F").resize((size, size), Image.Resampling.BILINEAR))


def _portable(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
