from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd


@dataclass
class ShapExplanation:
    predicted_class: int
    predicted_label: str
    probability: float
    top_features: List[Dict[str, Any]]


_MODEL = None
_META: Optional[Dict[str, Any]] = None
_EXPLAINER = None


def _load_model_and_meta():
    global _MODEL, _META
    if _MODEL is not None and _META is not None:
        return _MODEL, _META

    model_path = Path(__file__).resolve().parent.parent / "ml" / "Model" / "flood_model.pkl"
    meta_path = Path(__file__).resolve().parent.parent / "ml" / "Model" / "flood_model_meta.pkl"

    _MODEL = joblib.load(str(model_path))
    _META = joblib.load(str(meta_path))
    return _MODEL, _META


def _get_explainer(model):
    global _EXPLAINER
    if _EXPLAINER is not None:
        return _EXPLAINER

    import shap  # local import so backend can still boot if shap isn't installed

    # TreeExplainer supports RandomForestClassifier.
    _EXPLAINER = shap.TreeExplainer(model)
    return _EXPLAINER


def explain_row(feature_row: Dict[str, Any], top_k: int = 6) -> ShapExplanation:
    """Return a SHAP explanation for a single row of model features.

    feature_row should contain (at least) the keys in meta['features'].
    """
    model, meta = _load_model_and_meta()
    features = meta.get("features")
    label_map = meta.get("label_map", {})
    if not features:
        raise RuntimeError("Model metadata missing 'features'")

    df = pd.DataFrame([feature_row]).reindex(columns=features, fill_value=0.0)

    predicted_class = int(model.predict(df)[0])
    proba = float(model.predict_proba(df)[0][predicted_class])
    predicted_label = str(label_map.get(predicted_class, predicted_class))

    explainer = _get_explainer(model)
    shap_values = explainer.shap_values(df)

    # For multiclass, shap_values is typically a list/array per class.
    if isinstance(shap_values, list):
        values = np.asarray(shap_values[predicted_class])[0]
    else:
        arr = np.asarray(shap_values)
        # Expected shapes:
        # - (n_samples, n_features) for binary
        # - (n_classes, n_samples, n_features) for multiclass
        if arr.ndim == 2:
            values = arr[0]
        else:
            values = arr[predicted_class, 0]

    values = np.asarray(values, dtype=float)
    feature_values = df.iloc[0].to_dict()

    # Rank by absolute contribution.
    idx = np.argsort(np.abs(values))[::-1][: max(int(top_k), 1)]
    top_features: List[Dict[str, Any]] = []
    for i in idx:
        name = features[int(i)]
        top_features.append(
            {
                "feature": name,
                "value": float(feature_values.get(name, 0.0)),
                "shap": float(values[int(i)]),
                "direction": "increases_risk" if values[int(i)] > 0 else "decreases_risk",
            }
        )

    return ShapExplanation(
        predicted_class=predicted_class,
        predicted_label=predicted_label,
        probability=proba,
        top_features=top_features,
    )
