import numpy as np
import pytest

from scripts.render_hazelnut_qualitative_cases import CASES, select_cases


def test_preselected_cases_are_fixed_and_validate_saved_metadata() -> None:
    entries = [(group, f"hazelnut/test/{suffix}", taxonomy)
               for group, cases in CASES.items() for suffix, taxonomy in cases]
    paths = [sample for _, sample, _ in entries]
    rows = [{"index": str(i), "sample": sample, "defect_type": sample.split("/")[-2],
             "regression_type": taxonomy, "delta_per_image_aupro": "-0.1",
             "delta_per_image_pixel_auroc": "0.01", "delta_roi_bg_gap": "0.02"}
            for i, (_, sample, taxonomy) in enumerate(entries)]
    groups = select_cases(rows, paths, np.ones(len(paths), dtype=np.int64))
    assert {group: len(selected) for group, selected in groups.items()} == {"geometry": 3, "suppression": 3, "controls": 3}
    assert groups["geometry"][0]["sample"] == "hazelnut/test/crack/013.png"

    rows[0]["regression_type"] = "suppression"
    with pytest.raises(ValueError, match="metadata mismatch"):
        select_cases(rows, paths, np.ones(len(paths), dtype=np.int64))
