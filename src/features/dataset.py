from __future__ import annotations

import pathlib
from typing import Optional

import pandas as pd

from ..db.dao import DB, _DB_PATH


def collect_signal_dataset(db: DB) -> pd.DataFrame:
    """Return a dataframe combining signals, snapshots at trigger time and performance."""

    query = """
    SELECT
        sig.id AS signal_id,
        sig.asset_id,
        sig.symbol,
        sig.created_at AS signal_created_at,
        sig.reason,
        sig.llm_summary,
        sig.risk_note,
        sig.score,
        snap.price AS price_at_signal,
        snap.price_change_24h,
        snap.price_change_7d,
        snap.price_change_30d,
        snap.volume_24h,
        snap.volume_change_24h AS volume_change_24h_pct,
        snap.rvol,
        snap.intraday_range_pct,
        snap.volatility_annualized_pct,
        snap.news_count,
        snap.news_sentiment,
        perf.window_hours,
        perf.price_after_window,
        perf.roi_pct,
        perf.evaluated_at
    FROM signals sig
    LEFT JOIN signal_performance perf ON perf.signal_id = sig.id
    LEFT JOIN snapshots snap ON snap.id = (
        SELECT s2.id
        FROM snapshots s2
        WHERE s2.asset_id = sig.asset_id
          AND s2.created_at <= sig.created_at
        ORDER BY s2.created_at DESC
        LIMIT 1
    )
    ORDER BY sig.created_at
    """

    cur = db.conn.execute(query)
    rows = [dict(row) for row in cur.fetchall()]
    return pd.DataFrame(rows)


def export_signal_dataset(path: pathlib.Path, db_path: Optional[pathlib.Path] = None) -> pathlib.Path:
    """Export dataset into Parquet (preferred) or CSV when Parquet is unavailable."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with DB(path=db_path or _DB_PATH) as db:
        df = collect_signal_dataset(db)
    if df.empty:
        path.touch()
        return path
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    else:
        try:
            df.to_parquet(path, index=False)
        except Exception:
            fallback = path.with_suffix(".csv")
            df.to_csv(fallback, index=False)
            return fallback
    return path
