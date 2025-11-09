#!/usr/bin/env python

"""Train a baseline gradient boosting model on stored signal outcomes."""

import argparse
import json
import pathlib
from typing import List

import numpy as np
import pandas as pd
from joblib import dump as joblib_dump
from loguru import logger
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from src.features.dataset import collect_signal_dataset
from src.db.dao import DB, _DB_PATH


DEFAULT_FEATURES: List[str] = [
    "price_change_24h",
    "price_change_7d",
    "price_change_30d",
    "volume_change_24h_pct",
    "rvol",
    "intraday_range_pct",
    "volatility_annualized_pct",
    "news_count",
    "news_sentiment",
]


def _prepare_dataframe(df: pd.DataFrame, roi_threshold: float) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["roi_pct"])
    df["roi_positive"] = (df["roi_pct"] >= roi_threshold).astype(int)
    return df


def _select_features(df: pd.DataFrame, features: List[str]) -> np.ndarray:
    matrix = []
    for _, row in df.iterrows():
        matrix.append([float(row.get(col, 0.0) or 0.0) for col in features])
    return np.asarray(matrix, dtype=float)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=pathlib.Path, default=None, help="Path to SQLite database")
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("models/baseline.joblib"))
    parser.add_argument("--roi-threshold", type=float, default=5.0, help="ROI%% threshold for a positive outcome")
    parser.add_argument("--feature", action="append", dest="features", help="Override feature list")
    args = parser.parse_args()

    with DB(path=args.db or _DB_PATH) as db:
        df = collect_signal_dataset(db)

    if df.empty:
        logger.error("Dataset is empty; run the pipeline to accumulate signals first")
        raise SystemExit(1)

    features = args.features or DEFAULT_FEATURES
    df = _prepare_dataframe(df, roi_threshold=args.roi_threshold)

    X = _select_features(df, features)
    y = df["roi_positive"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    model = GradientBoostingClassifier(random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    report = classification_report(y_test, y_pred, output_dict=True)
    auc = roc_auc_score(y_test, y_prob)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "feature_columns": features,
        "threshold": 0.5,
        "roi_threshold": args.roi_threshold,
        "report": report,
        "roc_auc": float(auc),
    }
    joblib_dump(payload, args.output)

    logger.success("Model saved to {}", args.output)
    logger.info("ROC-AUC: {:.4f}", auc)
    logger.info("Classification report:\n{}", json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
