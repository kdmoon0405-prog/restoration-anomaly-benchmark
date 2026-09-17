from pathlib import Path

from PIL import Image
import pytest

from sr_anomaly.dataset import MVTecAD2Folder, MVTecADFolder, VisASplitCSV, discover_images, safe_component, safe_join


def test_discovery_is_sorted_and_ids_are_unique(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    Image.new("RGB", (8, 8), "red").save(tmp_path / "b.png")
    Image.new("RGB", (8, 8), "blue").save(tmp_path / "nested" / "a.jpg")
    samples = discover_images(tmp_path)
    assert [sample.relative_path.as_posix() for sample in samples] == ["b.png", "nested/a.jpg"]
    assert len({sample.sample_id for sample in samples}) == 2


def test_safe_join_rejects_escape(tmp_path: Path) -> None:
    assert safe_join(tmp_path, "nested/file.txt").is_relative_to(tmp_path.resolve())
    with pytest.raises(ValueError, match="escapes root"):
        safe_join(tmp_path, "../outside.txt")


@pytest.mark.parametrize("value", ["../bad", "a/b", "", ".."])
def test_safe_component_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        safe_component(value)


def test_mvtec_ad_adapter_reads_labels_and_masks(tmp_path: Path) -> None:
    category = tmp_path / "bottle"
    (category / "test" / "good").mkdir(parents=True)
    (category / "test" / "crack").mkdir(parents=True)
    (category / "ground_truth" / "crack").mkdir(parents=True)
    Image.new("RGB", (8, 8), "white").save(category / "test" / "good" / "000.png")
    Image.new("RGB", (8, 8), "black").save(category / "test" / "crack" / "001.png")
    Image.new("L", (8, 8), 255).save(category / "ground_truth" / "crack" / "001_mask.png")
    samples = MVTecADFolder(tmp_path, "bottle").samples()
    assert [sample.metadata["label"] for sample in samples] == [1, 0]
    assert samples[0].mask_path is not None
    assert samples[1].mask_path is None


def test_mvtec_ad2_private_labels_remain_hidden(tmp_path: Path) -> None:
    private = tmp_path / "can" / "test_private"
    private.mkdir(parents=True)
    Image.new("RGB", (8, 8), "white").save(private / "001.png")
    sample = MVTecAD2Folder(tmp_path, "can", "test_private").samples()[0]
    assert sample.metadata["label"] is None
    assert sample.mask_path is None


def test_visa_csv_adapter_uses_official_split_rows(tmp_path: Path) -> None:
    normal = tmp_path / "candle" / "Data" / "Images" / "Normal" / "000.JPG"
    anomaly = tmp_path / "candle" / "Data" / "Images" / "Anomaly" / "001.JPG"
    mask = tmp_path / "candle" / "Data" / "Masks" / "Anomaly" / "001.png"
    normal.parent.mkdir(parents=True)
    anomaly.parent.mkdir(parents=True)
    mask.parent.mkdir(parents=True)
    Image.new("RGB", (8, 8), "white").save(normal)
    Image.new("RGB", (8, 8), "black").save(anomaly)
    Image.new("L", (8, 8), 255).save(mask)
    split_csv = tmp_path / "1cls.csv"
    split_csv.write_text(
        "object,set,label,image_path,mask_path\n"
        "candle,test,normal,candle/Data/Images/Normal/000.JPG,\n"
        "candle,test,anomaly,candle/Data/Images/Anomaly/001.JPG,candle/Data/Masks/Anomaly/001.png\n",
        encoding="utf-8",
    )
    samples = VisASplitCSV(tmp_path, split_csv, category="candle").samples()
    assert [sample.metadata["label"] for sample in samples] == [1, 0]
    assert samples[0].mask_path == mask
