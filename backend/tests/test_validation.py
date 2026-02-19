from backend.validation import normalize_sensor_payload


def test_normalize_accepts_current_keys_and_clamps():
    n = normalize_sensor_payload({"distance_cm": 12.3, "rain_analog": 9999, "float_status": 2})
    assert n.payload["distance_cm"] == 12.3
    assert n.payload["rain_analog"] == 1023
    assert n.payload["float_status"] in (0, 1)
    assert "rain_clamped_high" in n.warnings
    assert "float_status_coerced" in n.warnings


def test_normalize_accepts_legacy_keys():
    n = normalize_sensor_payload({"height": 55, "rain": 42, "float": 1})
    assert n.payload == {"distance_cm": 55.0, "rain_analog": 42, "float_status": 1}
