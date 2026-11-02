"""Small file helpers shared by read-only reporting and transfer tools."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path, PurePosixPath


def digest(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative_source(root: Path, name: str) -> Path:
    value = PurePosixPath(name)
    if (not name or "\\" in name or value.is_absolute()
            or any(p in (".", "..") or ":" in p for p in value.parts)):
        raise ValueError(f"Expected a safe POSIX relative path: {name}")
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path escapes its root: {name}")
    return path


def read_json(path: Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value) -> None:
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")


def csv_rows(path: Path, required=()) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if (reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames)
                or not set(required) <= set(reader.fieldnames)):
            raise ValueError(f"CSV columns missing or duplicated: {path}")
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError(f"Malformed CSV row: {path}")
    return rows


def write_csv(path: Path, rows: list[dict], fields=None) -> None:
    fields = list(fields or dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def new_output(path: Path, inputs=()) -> Path:
    path = Path(path).resolve()
    if any(path == Path(p).resolve() or path.is_relative_to(Path(p).resolve()) for p in inputs):
        raise ValueError("Output must be outside the input artifact directories")
    if path.exists():
        raise FileExistsError(f"Output already exists; choose a new directory: {path}")
    path.mkdir(parents=True)
    return path
