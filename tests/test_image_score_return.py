import numpy as np
import pytest
from sr_anomaly.image_score_return import paired_auc_intervals


def test_paired_auc_identical_rules_and_seed():
    labels = np.asarray([0, 0, 0, 1, 1, 1])
    scores = np.tile(np.asarray([1, 2, 2, 2, 3, 4])[:, None], (1, 5))
    first = paired_auc_intervals(labels, scores, repeats=32)
    assert first == paired_auc_intervals(labels, scores, repeats=32)
    assert all(row['delta_vs_original'] == row['ci_low'] == row['ci_high'] == 0 for row in first)


def test_paired_auc_rank_reversal():
    labels = np.asarray([0, 0, 1, 1])
    scores = np.tile(labels[:, None], (1, 5)).astype(float)
    scores[:, 1:] = 1 - scores[:, 1:]
    assert all(row['delta_vs_original'] == row['ci_low'] == row['ci_high'] == -1
               for row in paired_auc_intervals(labels, scores, repeats=16))


@pytest.mark.parametrize('labels,scores', [([0, 0], np.zeros((2, 5))),
    ([0, 1], np.full((2, 5), np.nan)), ([0, 1], np.zeros((3, 5))),
    ([0, 2], np.zeros((2, 5)))])
def test_invalid_paired_input(labels, scores):
    with pytest.raises(ValueError):
        paired_auc_intervals(labels, scores, repeats=4)


@pytest.fixture
def scalar_fixture():
    from sr_anomaly.image_score_return import RULES
    from sr_anomaly.fusion import robust_params, normalize, quantile_threshold
    from sr_anomaly.evaluation import classification_metrics
    raw = np.asarray([0., 1., 2., 0., 1., 2., 3.])
    labels = np.asarray([0, 0, 1, 1])
    params = robust_params(raw[:3])
    normalized = normalize(raw, params)
    threshold = quantile_threshold(normalized[:3], .99)
    metrics = classification_metrics(labels, normalized[3:], threshold)
    metrics.update(image_false_alarm_rate_test_normal=float((normalized[3:5] >= threshold).mean()),
                   image_miss_rate_test_anomaly=float((normalized[5:] < threshold).mean()))
    unit = dict(unit_id='tiny', category='hazelnut', counts=dict(calibration=3, test_normal=2, test_anomaly=2),
        anchor_a_original='EXACT', anchor_b_map_payload=dict(pixel_params_equal=True,
            pixel_threshold_equal=True, npz_sha256_equal=True),
        k={'top0.1pct_mean':51,'top0.5pct_mean':251,'top1pct_mean':502},
        source_sha256={'npz':'a'*64}, rules={rule:dict(calibration=params,threshold=threshold,metrics=metrics) for rule in RULES})
    rows = [dict(rule=rule, sample=str(i), split='calibration' if i<3 else 'test',
            label=str(0 if i<3 else labels[i-3]), unit_id='tiny',category='hazelnut',
            source_npz_sha256='a'*64, raw_score=str(raw[i]),normalized_score=str(normalized[i]),
            threshold=str(threshold), flagged=str(int(normalized[i]>=threshold)))
            for rule in RULES for i in range(7)]
    return unit, rows


def test_scalar_calibration_and_decisions(scalar_fixture):
    from sr_anomaly.image_score_return import verify_scalar_unit
    unit, rows = scalar_fixture
    samples, labels, scores, summary = verify_scalar_unit(unit, rows)
    assert len(samples)==4 and labels.tolist()==[0,0,1,1]
    assert scores.shape==(4,5) and len(summary)==5


@pytest.mark.parametrize('change', ['duplicate','label','anchor','source','decision'])
def test_scalar_boundary_rejection(scalar_fixture, change):
    from sr_anomaly.image_score_return import verify_scalar_unit
    unit, rows = scalar_fixture
    if change=='duplicate': rows.append(rows[0].copy())
    elif change=='label': rows[0]['label']='1'
    elif change=='anchor': unit['anchor_b_map_payload']={}
    elif change=='source': rows[0]['source_npz_sha256']='b'*64
    elif change=='decision': rows[0]['flagged']='1'
    with pytest.raises(ValueError):
        verify_scalar_unit(unit, rows)
