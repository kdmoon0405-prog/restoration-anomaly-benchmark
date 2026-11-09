import importlib.util
from pathlib import Path

import pytest

script = Path(__file__).resolve().parents[1] / 'scripts/analyze_score_diagnosis.py'
spec = importlib.util.spec_from_file_location('score_diagnosis', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_same_fpr_has_more_than_one_tpr():
    result = module.plateau([4, 3, 2, 1], [3.5, 2.5, 0], 1)
    assert result == dict(attainable=True, tpr_low=0, tpr_high=pytest.approx(1 / 3))


def test_tied_normals_can_make_target_fp_unattainable():
    assert module.plateau([4, 4, 2, 1], [5, 3, 1], 1)['attainable'] is False
    with pytest.raises(ValueError):
        module.plateau([4, 3], [float('nan')], 1)
