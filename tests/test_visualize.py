from pathlib import Path

from PIL import Image

from sr_anomaly.visualize import degradation_contact_sheet


def test_contact_sheet_is_written(tmp_path: Path) -> None:
    output = tmp_path / "sheet.png"
    result = degradation_contact_sheet(
        Image.new("RGB", (24, 16), "gray"),
        output,
        degradations=["gaussian_blur", "gaussian_noise"],
        severities=[1, 3],
        seed=4,
        cell_size=64,
    )
    assert result == output
    with Image.open(output) as sheet:
        assert sheet.size == (278, 156)

