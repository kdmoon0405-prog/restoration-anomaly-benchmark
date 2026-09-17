from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from .degradations import apply_degradation


DEFAULT_DEGRADATIONS = (
    "gaussian_blur",
    "motion_blur",
    "gaussian_noise",
    "jpeg_compression",
    "brightness",
    "contrast",
    "low_resolution",
)


def degradation_contact_sheet(
    image: Image.Image,
    output_path: str | Path,
    degradations: Iterable[str] = DEFAULT_DEGRADATIONS,
    severities: Iterable[int] = range(1, 6),
    seed: int = 0,
    cell_size: int = 128,
) -> Path:
    names = list(degradations)
    levels = list(severities)
    if not names or not levels or cell_size < 32:
        raise ValueError("Contact sheet needs degradations, severities, and cell_size >= 32")
    label_width = 150
    header_height = 28
    sheet = Image.new("RGB", (label_width + cell_size * len(levels), header_height + cell_size * len(names)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for column, severity in enumerate(levels):
        draw.text((label_width + column * cell_size + 6, 8), f"severity {severity}", fill="black", font=font)
    source = image.convert("RGB")
    for row, name in enumerate(names):
        y = header_height + row * cell_size
        draw.text((6, y + 6), name, fill="black", font=font)
        for column, severity in enumerate(levels):
            degraded = apply_degradation(source, name, severity, seed).image
            thumbnail = degraded.copy()
            thumbnail.thumbnail((cell_size, cell_size), Image.Resampling.LANCZOS)
            x = label_width + column * cell_size + (cell_size - thumbnail.width) // 2
            offset_y = y + (cell_size - thumbnail.height) // 2
            sheet.paste(thumbnail, (x, offset_y))
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
    return destination

