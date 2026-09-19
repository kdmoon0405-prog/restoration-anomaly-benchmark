from pathlib import Path

import pytest

from scripts.run_legacy_patchcore import _balanced_test, _delta, _select_indices
from sr_anomaly.dataset import ImageSample


def test_legacy_subset_is_deterministic_and_balanced() -> None:
    assert _select_indices(20, 5, 11) == _select_indices(20, 5, 11)
    assert len(_select_indices(20, 5, 11)) == 5
    assert _select_indices(3, 0, 11) == [0, 1, 2]
    with pytest.raises(ValueError):
        _select_indices(3, -1, 11)
    samples = [ImageSample(str(index), Path(str(index)), Path(str(index)), metadata={"label": index % 2}) for index in range(10)]
    chosen = _balanced_test(samples, 4, 11)
    assert sum(sample.metadata["label"] for sample in chosen) == 2
    assert len(chosen) == 4
    assert _delta(2.0, 1.0) == 1.0
    assert _delta(None, 1.0) is None
