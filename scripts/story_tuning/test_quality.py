from quality import promotion_allowed


def test_promotion_needs_strict_gain_and_no_regression():
    baseline = {'valid_decision/mean':1.0,'teaching_policy/mean':1.0,'concise_activity/mean':0.5}
    assert promotion_allowed(baseline, {**baseline,'concise_activity/mean':1.0})
    assert not promotion_allowed(baseline, baseline)
    assert not promotion_allowed(baseline, {**baseline,'teaching_policy/mean':0.9,'concise_activity/mean':1.0})
    assert not promotion_allowed(baseline, {})


def test_train_heldout_inputs_disjoint():
    from cases import records
    train, heldout = records('train'), records('heldout')
    assert len(train)==15 and len(heldout)==27
    assert all(len(r['inputs']['request']['events'])==3 for r in heldout)


def test_gate_returns_json_boolean_for_mlflow_numeric_metrics():
    import json
    import numpy as np
    metrics = {key:np.float64(1) for key in ('valid_decision/mean','teaching_policy/mean','concise_activity/mean')}
    allowed = promotion_allowed(metrics, metrics)
    assert allowed is False
    assert json.dumps({'promoted':allowed}) == '{"promoted": false}'
