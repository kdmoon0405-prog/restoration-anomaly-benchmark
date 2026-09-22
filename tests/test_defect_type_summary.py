from __future__ import annotations

import csv

import pytest

from scripts.summarize_defect_types import summarize, write_outputs


def test_defect_type_summary_uses_frozen_taxonomy(tmp_path) -> None:
    source = tmp_path / "per_anomaly.csv"
    fields = (
        "defect_type", "regression_type", "delta_per_image_aupro",
        "delta_per_image_pixel_auroc", "delta_roi_bg_gap",
    )
    with source.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"defect_type": "thread", "regression_type": "suppression", "delta_per_image_aupro": -0.2,
             "delta_per_image_pixel_auroc": -0.1, "delta_roi_bg_gap": -0.3},
            {"defect_type": "thread", "regression_type": "improvement_or_tie", "delta_per_image_aupro": 0.4,
             "delta_per_image_pixel_auroc": 0.2, "delta_roi_bg_gap": 0.1},
        ])
    rows = summarize(source)
    assert rows[0]["localization_regression_count"] == 1
    assert rows[0]["suppression_rate"] == 0.5
    assert rows[0]["mean_delta_per_image_aupro"] == pytest.approx(0.1)
    write_outputs(rows, tmp_path / "out")
    assert (tmp_path / "out" / "defect_type_summary.md").is_file()

    text = source.read_text().replace("improvement_or_tie,0.4", "suppression,0.4")
    source.write_text(text)
    with pytest.raises(ValueError, match="zero-cutoff"):
        summarize(source)
