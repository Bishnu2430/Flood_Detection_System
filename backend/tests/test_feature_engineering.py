import pytest

from backend.feature_engineering import FeatureBuffer


def test_build_features_update_state_false_does_not_mutate_samples():
    fb = FeatureBuffer()
    raw = {"distance_cm": 100.0, "rain_analog": 123, "float_status": 0}

    fb.build_features(raw, update_state=False)
    assert len(fb._samples) == 0  # internal state should not change

    fb.build_features(raw, update_state=True)
    assert len(fb._samples) == 1


def test_build_features_rejects_invalid_distance():
    fb = FeatureBuffer()
    raw = {"distance_cm": -1.0, "rain_analog": 0, "float_status": 0}
    with pytest.raises(ValueError):
        fb.build_features(raw)
