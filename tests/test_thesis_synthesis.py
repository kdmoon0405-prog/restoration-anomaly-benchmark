import csv

import pytest

from scripts import synthesize_thesis_results as synthesis


def test_tracked_master_sources_keep_protocol_families_separate():
    rows = synthesis.master_rows()
    assert len(rows) == 10
    assert sum(row["study_family"] == "historical_recovery" for row in rows) == 6
    assert sum(row["study_family"] == "endpoint_full110" for row in rows) == 4
    historical = next(row for row in rows if row["study_family"] == "historical_recovery" and row["dataset"] == "hazelnut" and row["variant"] == "bicubic_x4")
    endpoint = next(row for row in rows if row["study_family"] == "endpoint_full110" and row["variant"] == "bicubic_x4")
    assert historical["degradation_protocol"] != endpoint["degradation_protocol"]
    assert historical["aupro"] != endpoint["aupro"]
    recoveries = synthesis.recovery_rows(rows)
    assert all(0 < row["fraction_of_loss_recovered"] < 1 for row in recoveries)
    assert all(row["degradation_loss"] > 0 and row["restoration_delta"] > 0 for row in recoveries)
    text = synthesis.synthesis(rows)
    assert "B / B-uncertain" in text
    assert "POST-HOC MAGNITUDE SENSITIVITY" in text
    assert "No additional research experiment was run." in text
    assert not any("\u3040" <= char <= "\u30ff" for char in text)


def test_magnitude_counts_preserve_strict_boundaries():
    result = synthesis.magnitude_counts([-0.05, -0.02, -0.01, -0.005, 0, 0.01])
    assert [result[f"loss_gt_{tau:g}"] for tau in synthesis.TAUS] == [4, 3, 2, 1, 0]
    assert result["absolute_delta_le_0.01"] == 4
    with pytest.raises(ValueError):
        synthesis.magnitude_counts([float("nan")])


def test_master_csv_matches_generated_values():
    with (synthesis.DESTINATION / "MASTER_RESULTS.csv").open(encoding="utf-8", newline="") as handle:
        stored = list(csv.DictReader(handle))
    expected = synthesis.master_rows()
    assert len(stored) == len(expected)
    for actual, row in zip(stored, expected):
        for field in synthesis.FIELDS:
            assert actual[field] == ("" if row[field] is None else str(row[field]))
