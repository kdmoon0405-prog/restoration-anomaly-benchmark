import pytest

from sr_anomaly.gpu_return_analysis import exact_ranking, operating_point, paired_summary


def rows():
    return [dict(sample="normal", label="0", per_image_aupro="", roi_bg_gap="", score="0.1"),
            dict(sample="defect", label="1", per_image_aupro="0.8", roi_bg_gap="1", score="0.8")]


def test_exact_ranking_keeps_rounding_tie_separate():
    result = exact_ranking([dict(restorer="swinir", au_pro="0.7726005600552853"),
                           dict(restorer="esrnet", au_pro="0.7725502430519956")])
    assert result["winners"] == "swinir" and result["same_when_rounded_3dp"]
    assert result["margin"] > 0


def test_pair_guards_and_regression_taxonomy():
    candidate = rows()
    candidate[1].update(per_image_aupro="0.6", roi_bg_gap="0.5")
    result = paired_summary(rows(), candidate, repeats=50)
    assert result["anomaly_images"] == 1 and result["suppression"] == 1
    assert result["pooled_ci_computed"] is False
    with pytest.raises(ValueError, match="identities"):
        paired_summary(rows(), candidate[:1])
    candidate[0]["per_image_aupro"] = "0.5"
    with pytest.raises(ValueError, match="N/A"):
        paired_summary(rows(), candidate)


def test_saved_operating_threshold_and_duplicate_guard():
    result = operating_point(rows(), 0.9, "score")
    assert result["fn"] == 1 and result["tn"] == 1 and result["image_f1"] == 0
    with pytest.raises(ValueError, match="Duplicate"):
        operating_point(rows() * 2, 0.5, "score")
