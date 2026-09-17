from __future__ import annotations

import csv
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
import re
from typing import Any, Protocol, runtime_checkable


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class ImageSample:
    sample_id: str
    path: Path
    relative_path: Path
    mask_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DatasetAdapter(Protocol):
    def samples(self) -> list[ImageSample]: ...


@dataclass(frozen=True)
class GenericImageFolder:
    root: Path
    recursive: bool = True

    def samples(self) -> list[ImageSample]:
        return discover_images(self.root, self.recursive)


@dataclass(frozen=True)
class MVTecADFolder:
    root: Path
    category: str
    split: str = "test"
    require_masks: bool = True

    def samples(self) -> list[ImageSample]:
        return _mvtec_labeled_samples(self.root, self.category, self.split, self.require_masks)


@dataclass(frozen=True)
class MVTecAD2Folder:
    root: Path
    category: str
    split: str = "test_public"
    require_masks: bool = True

    def samples(self) -> list[ImageSample]:
        if self.split not in {"train", "validation", "test_public", "test_private", "test_private_mixed"}:
            raise ValueError(f"Unsupported MVTec AD 2 split: {self.split}")
        if "private" not in self.split:
            return _mvtec_labeled_samples(self.root, self.category, self.split, self.require_masks)
        category_root = safe_join(self.root, safe_component(self.category, "dataset category"))
        image_root = safe_join(category_root, safe_component(self.split, "dataset split"))
        paths = _image_paths(image_root, recursive=False)
        return [
            ImageSample(
                _sample_id(path.relative_to(self.root.resolve())),
                path,
                path.relative_to(self.root.resolve()),
                metadata={"category": self.category, "split": self.split, "label": None, "defect_type": None},
            )
            for path in paths
        ]


@dataclass(frozen=True)
class VisASplitCSV:
    root: Path
    split_csv: Path
    split: str = "test"
    category: str | None = None
    require_masks: bool = True

    def samples(self) -> list[ImageSample]:
        root = self.root.resolve()
        samples: list[ImageSample] = []
        with self.split_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            for line_number, row in enumerate(reader, 2):
                if len(row) != 5:
                    raise ValueError(f"VisA split row {line_number} must have 5 columns")
                category, split, label_name, image_value, mask_value = (value.strip() for value in row)
                if split != self.split or (self.category is not None and category != self.category):
                    continue
                image_path = safe_join(root, image_value)
                if not image_path.is_file():
                    raise FileNotFoundError(f"VisA image not found: {image_path}")
                label = 0 if label_name.lower() in {"normal", "good"} else 1
                mask_path = safe_join(root, mask_value) if label and mask_value else None
                if label and self.require_masks and (mask_path is None or not mask_path.is_file()):
                    raise FileNotFoundError(f"VisA anomaly mask not found for {image_path}")
                relative = image_path.relative_to(root)
                samples.append(
                    ImageSample(
                        _sample_id(relative),
                        image_path,
                        relative,
                        mask_path,
                        {"category": category, "split": split, "label": label, "defect_type": "bad" if label else "good"},
                    )
                )
        return sorted(samples, key=lambda sample: sample.relative_path.as_posix())


def discover_images(root: str | Path, recursive: bool = True) -> list[ImageSample]:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {root_path}")
    iterator = root_path.rglob("*") if recursive else root_path.glob("*")
    paths = sorted(path for path in iterator if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    return [ImageSample(_sample_id(path.relative_to(root_path)), path, path.relative_to(root_path)) for path in paths]


def build_dataset_adapter(config: dict[str, Any], root: Path, config_dir: Path) -> DatasetAdapter:
    adapter = str(config.get("adapter", "folder"))
    if adapter == "folder":
        return GenericImageFolder(root, bool(config.get("recursive", True)))
    category = config.get("category")
    if adapter in {"mvtec_ad", "mvtec_ad2"} and not isinstance(category, str):
        raise ValueError(f"dataset.category is required for {adapter}")
    if adapter == "mvtec_ad":
        return MVTecADFolder(root, category, str(config.get("split", "test")), bool(config.get("require_masks", True)))
    if adapter == "mvtec_ad2":
        return MVTecAD2Folder(
            root,
            category,
            str(config.get("split", "test_public")),
            bool(config.get("require_masks", True)),
        )
    if adapter == "visa_csv":
        split_value = config.get("split_csv")
        if not isinstance(split_value, str):
            raise ValueError("dataset.split_csv is required for visa_csv")
        split_path = Path(split_value)
        if not split_path.is_absolute():
            split_path = (config_dir / split_path).resolve()
        return VisASplitCSV(
            root,
            split_path,
            str(config.get("split", "test")),
            category if isinstance(category, str) else None,
            bool(config.get("require_masks", True)),
        )
    raise ValueError(f"Unknown dataset adapter: {adapter}")


def safe_join(root: str | Path, relative: str | Path) -> Path:
    root_path = Path(root).resolve()
    candidate = (root_path / Path(relative)).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"Path escapes root: {relative}") from exc
    return candidate


def safe_component(value: str, field: str = "path component") -> str:
    if not value or value in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError(f"Invalid {field}: {value!r}")
    return value


def _sample_id(relative_path: Path) -> str:
    portable = relative_path.as_posix()
    readable = re.sub(r"[^A-Za-z0-9._-]+", "-", relative_path.with_suffix("").as_posix()).strip("-._")
    readable = readable[-60:] or "image"
    return f"{readable}-{sha1(portable.encode('utf-8')).hexdigest()[:8]}"


def _mvtec_labeled_samples(root: Path, category: str, split: str, require_masks: bool) -> list[ImageSample]:
    root = root.resolve()
    category_root = safe_join(root, safe_component(category, "dataset category"))
    image_root = safe_join(category_root, safe_component(split, "dataset split"))
    if not image_root.is_dir():
        raise FileNotFoundError(f"Dataset split directory not found: {image_root}")
    samples: list[ImageSample] = []
    for path in _image_paths(image_root, recursive=True):
        defect_type = path.parent.name
        label = 0 if defect_type == "good" else 1
        mask_path = _find_mvtec_mask(category_root, defect_type, path) if label else None
        if label and require_masks and mask_path is None:
            raise FileNotFoundError(f"Anomaly mask not found for {path}")
        relative = path.relative_to(root)
        samples.append(
            ImageSample(
                _sample_id(relative),
                path,
                relative,
                mask_path,
                {"category": category, "split": split, "label": label, "defect_type": defect_type},
            )
        )
    return samples


def _find_mvtec_mask(category_root: Path, defect_type: str, image_path: Path) -> Path | None:
    mask_root = safe_join(category_root, Path("ground_truth") / defect_type)
    for filename in (f"{image_path.stem}_mask.png", image_path.name, f"{image_path.stem}.png"):
        candidate = safe_join(mask_root, filename)
        if candidate.is_file():
            return candidate
    return None


def _image_paths(root: Path, recursive: bool) -> list[Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"Image directory not found: {root}")
    iterator = root.rglob("*") if recursive else root.glob("*")
    return sorted(path for path in iterator if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
