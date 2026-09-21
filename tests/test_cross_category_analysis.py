from __future__ import annotations

import numpy as np
import pytest

from scripts.analyze_cross_category import (
    _regression_type,
    analyze_predictions,
    load_run,
    select_cases,
    validate_predictions,
)


def _predictions() -> tuple[dict, list[str]]:
    paths = ["widget/test/good/000.png", "widget/test/crack/b.png", "widget/test/crack/a.png"]
    labels = np.array([0, 1, 1])
    masks = np.zeros((3, 4, 4), dtype=bool)
    masks[1:, :2, :2] = True
    bicubic = np.zeros((3, 4, 4), dtype=float)
    bicubic[1:, :2, :2] = 1.0
    swinir = bicubic.copy()
    swinir[1, :2, :2] = 0.5
    swinir[2, :2, :2] = 1.5

    def item(maps):
        return {"labels": labels.copy(), "scores": np.array([0.1, 0.8, 0.9]),
                "masks": masks.copy(), "maps": maps.copy()}

    return {"clean": item(bicubic), "bicubic_x4": item(bicubic), "swinir_x4": item(swinir)}, paths


def test_regression_classification_and_invalid_predictions() -> None:
    assert _regression_type(-0.1, -0.01) == "suppression"
    assert _regression_type(-0.1, 0.0) == "geometry_candidate"
    assert _regression_type(0.0, -1.0) == "improvement_or_tie"
    predictions, paths = _predictions()
    rows = analyze_predictions(predictions, paths)
    assert len(rows) == 2
    predictions["swinir_x4"]["maps"] = predictions["swinir_x4"]["maps"][:2]
    with pytest.raises(ValueError, match="unpaired, misshaped, or non-finite"):
        validate_predictions(predictions, paths)


def test_missing_prediction_guard(tmp_path) -> None:
    (tmp_path / "results.json").write_text(
        '{"model_spec":{"category":"screw"},"test_paths":["screw/test/good/000.png"]}',
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError, match="Prediction file"):
        load_run(tmp_path)


def test_selected_case_ranking_and_lexical_ties() -> None:
    rows = [
        {"sample": "z.png", "delta_per_image_aupro": -0.4, "regression_type": "suppression"},
        {"sample": "a.png", "delta_per_image_aupro": -0.4, "regression_type": "geometry_candidate"},
        {"sample": "g.png", "delta_per_image_aupro": -0.2, "regression_type": "geometry_candidate"},
        {"sample": "s2.png", "delta_per_image_aupro": 0.3, "regression_type": "improvement_or_tie"},
        {"sample": "s1.png", "delta_per_image_aupro": 0.3, "regression_type": "improvement_or_tie"},
        {"sample": "tie.png", "delta_per_image_aupro": 0.0, "regression_type": "improvement_or_tie"},
    ]
    selected = select_cases(rows)
    assert [row["sample"] for row in selected["worst_localization_regression"]] == ["a.png", "z.png", "g.png"]
    assert [row["sample"] for row in selected["geometry_examples"]] == ["a.png", "g.png"]
    assert [row["sample"] for row in selected["success_controls"]] == ["s1.png", "s2.png", "tie.png"]
