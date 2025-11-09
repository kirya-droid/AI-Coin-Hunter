from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
from joblib import load as joblib_load
from loguru import logger


@dataclass
class ModelBundle:
    model: Any
    feature_columns: Sequence[str]
    threshold: float
    metadata: Dict[str, Any]


def load_model_bundle(path: str | pathlib.Path | None) -> ModelBundle | None:
    if not path:
        return None
    model_path = pathlib.Path(path)
    if not model_path.exists():
        logger.warning("ML model path {} not found", model_path)
        return None
    payload = joblib_load(model_path)
    if isinstance(payload, dict):
        model = payload.get("model")
        feature_columns = payload.get("feature_columns") or []
        threshold = float(payload.get("threshold", 0.5))
        metadata = {k: v for k, v in payload.items() if k not in {"model", "feature_columns", "threshold"}}
    else:
        model = payload
        feature_columns = []
        threshold = 0.5
        metadata = {}
    if model is None:
        logger.warning("Loaded ML payload without model object from {}", model_path)
        return None
    return ModelBundle(model=model, feature_columns=tuple(feature_columns), threshold=threshold, metadata=metadata)


def _predict_probabilities(model: Any, features: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(features)
        if isinstance(proba, list):
            proba = np.asarray(proba)
        if proba.ndim == 2 and proba.shape[1] >= 2:
            return proba[:, 1]
        if proba.ndim == 1:
            return proba
    if hasattr(model, "decision_function"):
        scores = model.decision_function(features)
        if isinstance(scores, list):
            scores = np.asarray(scores)
        return 1 / (1 + np.exp(-scores))
    preds = model.predict(features)
    if isinstance(preds, list):
        preds = np.asarray(preds)
    return preds.astype(float)


def score_candidates(
    bundle: ModelBundle,
    items: Iterable[Dict[str, Any]],
    feature_override: Sequence[str] | None = None,
) -> List[float]:
    feats = list(feature_override or bundle.feature_columns)
    if not feats:
        feats = [
            "price_change_percentage_24h",
            "price_change_percentage_7d",
            "price_change_percentage_30d",
            "volume_change_24h_pct",
            "rvol",
            "intraday_range_pct",
            "volatility_annualized_pct",
        ]
    rows: List[List[float]] = []
    for it in items:
        row = []
        for col in feats:
            try:
                row.append(float(it.get(col, 0.0) or 0.0))
            except (TypeError, ValueError):
                row.append(0.0)
        rows.append(row)
    if not rows:
        return []
    X = np.asarray(rows, dtype=float)
    probs = _predict_probabilities(bundle.model, X)
    return probs.tolist()
