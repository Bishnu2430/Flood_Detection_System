from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class NormalizedPayload:
    payload: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def normalize_sensor_payload(raw: Dict[str, Any]) -> NormalizedPayload:
    """Normalize incoming sensor payload for storage + inference.

    Supports both the current Arduino keys and legacy keys:
    - distance_cm OR height
    - rain_analog OR rain
    - float_status OR float

    Returns a NormalizedPayload with:
    - payload: normalized dict with keys distance_cm, rain_analog, float_status
    - errors: issues that make the sample unusable for ML/SHAP (but still storable)
    - warnings: non-fatal issues (clamping, coercion)
    """

    errors: List[str] = []
    warnings: List[str] = []

    distance = _to_float(raw.get("distance_cm", raw.get("height")))
    rain = _to_int(raw.get("rain_analog", raw.get("rain")))
    float_status = _to_int(raw.get("float_status", raw.get("float")))

    if distance is None:
        errors.append("missing_distance")
        distance = -1.0
    elif distance < 0:
        errors.append("invalid_distance")

    if rain is None:
        errors.append("missing_rain")
        rain = 0

    if rain < 0:
        warnings.append("rain_clamped_low")
        rain = 0
    if rain > 1023:
        warnings.append("rain_clamped_high")
        rain = 1023

    if float_status is None:
        errors.append("missing_float_status")
        float_status = 0

    if float_status not in (0, 1):
        warnings.append("float_status_coerced")
        float_status = 1 if float_status else 0

    return NormalizedPayload(
        payload={
            "distance_cm": float(distance),
            "rain_analog": int(rain),
            "float_status": int(float_status),
        },
        errors=errors,
        warnings=warnings,
    )
