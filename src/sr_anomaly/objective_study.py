from __future__ import annotations

import csv
from hashlib import sha256
from pathlib import Path

from .dataset import MVTecADFolder


PILOT_STRATA = ("normal", "crack", "cut", "hole", "print")
PILOT_PER_STRATUM = 5
MANIFEST_FIELDS = (
    "sample",
    "mask",
    "label",
    "defect_type",
    "stratum",
    "stratum_rank",
    "selection_rule",
    "image_sha256",
    "mask_sha256",
)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_pilot_manifest(data_root: Path, category: str = "hazelnut") -> list[dict[str, str | int]]:
    samples = MVTecADFolder(data_root, category).samples()
    grouped = {stratum: [] for stratum in PILOT_STRATA}
    for sample in samples:
        defect_type = str(sample.metadata["defect_type"])
        stratum = "normal" if defect_type == "good" else defect_type
        if stratum in grouped:
            grouped[stratum].append(sample)
    missing = [name for name, values in grouped.items() if len(values) < PILOT_PER_STRATUM]
    if missing:
        raise ValueError(f"Pilot requires at least {PILOT_PER_STRATUM} images in each stratum; missing: {missing}")

    rows: list[dict[str, str | int]] = []
    for stratum in PILOT_STRATA:
        selected = sorted(grouped[stratum], key=lambda sample: sample.relative_path.as_posix())[:PILOT_PER_STRATUM]
        for rank, sample in enumerate(selected, 1):
            rows.append({
                "sample": sample.relative_path.as_posix(),
                "mask": sample.mask_path.relative_to(data_root.resolve()).as_posix() if sample.mask_path else "",
                "label": int(sample.metadata["label"]),
                "defect_type": str(sample.metadata["defect_type"]),
                "stratum": stratum,
                "stratum_rank": rank,
                "selection_rule": "lexical_first_5_within_test_stratum",
                "image_sha256": file_sha256(sample.path),
                "mask_sha256": file_sha256(sample.mask_path) if sample.mask_path else "",
            })
    return rows


def write_pilot_manifest(rows: list[dict[str, str | int]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_pilot_manifest(path: Path, data_root: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
            raise ValueError("Pilot manifest fields changed")
        rows = list(reader)
    expected = [
        {key: str(value) for key, value in row.items()}
        for row in build_pilot_manifest(data_root)
    ]
    if rows != expected:
        raise ValueError("Pilot manifest selection, metadata, or file contents are missing or changed")
    return rows


def regression_type(delta_aupro: float, delta_gap: float) -> str:
    if delta_aupro >= 0:
        return "improvement_or_tie"
    return "suppression" if delta_gap < 0 else "geometry_candidate"
