from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import pandas as pd

from .feature_engineering import FEATURE_BUFFER


_MODEL = None
_META = None


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    model_path = Path(__file__).resolve().parent.parent / "ml" / "Model" / "flood_model.pkl"
    _MODEL = joblib.load(str(model_path))
    return _MODEL


def _load_meta() -> Dict[str, Any]:
    global _META
    if _META is not None:
        return _META

    meta_path = Path(__file__).resolve().parent.parent / "ml" / "Model" / "flood_model_meta.pkl"
    _META = joblib.load(str(meta_path))
    return _META


def _normalize_raw(sensor_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "distance_cm": sensor_data.get("distance_cm", sensor_data.get("height")),
        "rain_analog": sensor_data.get("rain_analog", sensor_data.get("rain")),
        "float_status": sensor_data.get("float_status", sensor_data.get("float")),
    }


def predict_risk(sensor_data: Dict[str, Any]) -> Tuple[int, float]:
    """Return (risk_class, probability).

    Uses the exported feature list from flood_model_meta.pkl.
    """
    model = _load_model()
    meta = _load_meta()
    features = meta.get("features")
    if not features:
        raise RuntimeError("Model metadata missing 'features'")

    raw = _normalize_raw(sensor_data)
    engineered = FEATURE_BUFFER.build_features(raw)

    row = pd.DataFrame([engineered])
    row = row.reindex(columns=features, fill_value=0.0)

    prediction = int(model.predict(row)[0])
    probas = model.predict_proba(row)[0]
    probability = float(probas[prediction])
    return prediction, probability


def predict_risk_safe(sensor_data: Dict[str, Any]) -> Tuple[int | None, float | None, str | None]:
    try:
        risk, prob = predict_risk(sensor_data)
        return risk, prob, None
    except Exception as e:
        return None, None, str(e)
