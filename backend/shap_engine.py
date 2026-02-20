from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import joblib
import numpy as np
import pandas as pd


@dataclass
class ShapExplanation:
    predicted_class: int
    predicted_label: str
    probability: float
    target_class: int
    target_label: str
    target_probability: float
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


def _normalize_label(label: object) -> str:
    return str(label).strip().lower()


def _choose_risk_class(meta: Dict[str, Any], *, fallback: int) -> int:
    """Pick a class index that best represents 'risk' for explainability.

    Preference order:
    - label contains 'critical'
    - label contains 'warning'
    - label contains 'risk' or 'flood'
    - fallback
    """
    label_map = meta.get("label_map") or {}
    if isinstance(label_map, dict):
        normalized: List[tuple[int, str]] = []
        for k, v in label_map.items():
            try:
                idx = int(k)
            except Exception:
                continue
            normalized.append((idx, _normalize_label(v)))

        for needle in ("critical", "warning", "risk", "flood", "high"):
            for idx, lab in normalized:
                if needle in lab:
                    return idx

        # If label_map exists but doesn't contain recognizable labels,
        # use the numerically highest class index (common for ordinal classes).
        if normalized:
            return max(idx for idx, _ in normalized)

    return int(fallback)


def _shap_values_for_class(shap_values: object, class_index: int) -> np.ndarray:
    """Return the per-feature SHAP values for df[0] and the given class."""
    if isinstance(shap_values, list):
        if not shap_values:
            raise RuntimeError("Empty SHAP values")
        ci = int(max(0, min(class_index, len(shap_values) - 1)))
        return np.asarray(shap_values[ci])[0]

    arr = np.asarray(shap_values)
    if arr.ndim == 2:
        # Binary models sometimes return (n_samples, n_features).
        return arr[0]
    if arr.ndim == 3:
        ci = int(max(0, min(class_index, arr.shape[0] - 1)))
        return arr[ci, 0]
    raise RuntimeError(f"Unexpected SHAP values shape: {arr.shape}")


def explain_row(
    feature_row: Dict[str, Any],
    top_k: int = 6,
    *,
    target: Literal["predicted", "risk"] = "risk",
) -> ShapExplanation:
    """Return a SHAP explanation for a single row of model features.

    Notes on direction semantics:
    - We default to explaining a 'risk' class (e.g. Critical) so that a positive
      SHAP value can be interpreted as *increasing flood risk*.
    - If target='predicted', SHAP values explain the predicted class instead.

    feature_row should contain (at least) the keys in meta['features'].
    """
    model, meta = _load_model_and_meta()
    features = meta.get("features")
    label_map = meta.get("label_map", {})
    if not features:
        raise RuntimeError("Model metadata missing 'features'")

    df = pd.DataFrame([feature_row]).reindex(columns=features, fill_value=0.0)

    predicted_class = int(model.predict(df)[0])
    probas = np.asarray(model.predict_proba(df)[0], dtype=float)
    predicted_probability = float(probas[predicted_class])
    predicted_label = str(label_map.get(predicted_class, predicted_class))

    # Choose a class whose probability we want to explain.
    if target == "predicted":
        target_class = predicted_class
    else:
        fallback_risk = int(probas.shape[0] - 1) if probas.ndim == 1 else int(predicted_class)
        target_class = _choose_risk_class(meta, fallback=fallback_risk)
        # Clamp to available classes.
        target_class = int(max(0, min(target_class, int(probas.shape[0] - 1))))

    target_probability = float(probas[target_class])
    target_label = str(label_map.get(target_class, target_class))

    explainer = _get_explainer(model)
    shap_values = explainer.shap_values(df)

    values = _shap_values_for_class(shap_values, target_class)
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
        probability=predicted_probability,
        target_class=target_class,
        target_label=target_label,
        target_probability=target_probability,
        top_features=top_features,
    )
