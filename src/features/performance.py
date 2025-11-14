import datetime as dt
from typing import List

from loguru import logger

from ..db.dao import DB
from ..ingest.coingecko import fetch_simple_price


def evaluate_signal_performance(db: DB, base_currency: str = "usd") -> List[dict]:
    """Evaluate signals that are older than their window and store ROI."""
    pending = db.get_signals_ready_for_evaluation()
    if not pending:
        return []

    updates: List[dict] = []
    for row in pending:
        price_at_signal = float(row.get("price_at_signal") or 0.0)
        if price_at_signal <= 0:
            logger.debug("Skipping signal %s: no price at signal", row.get("signal_id"))
            continue

        signal_time = dt.datetime.fromisoformat(row["signal_created_at"])
        target_time = signal_time + dt.timedelta(hours=row.get("window_hours") or 24)
        snapshot_price = db.get_snapshot_price_after(row["asset_id"], target_time.isoformat())

        price_after = snapshot_price
        if price_after is None:
            price_after = fetch_simple_price(row["asset_id"], vs_currency=base_currency)

        if price_after is None or price_after <= 0:
            logger.debug("No price data to evaluate signal %s", row.get("signal_id"))
            continue

        roi_pct = ((price_after - price_at_signal) / price_at_signal) * 100.0
        db.update_signal_performance(row["signal_id"], price_after, roi_pct, dt.datetime.utcnow())
        updates.append(
            {
                "signal_id": row["signal_id"],
                "symbol": row["symbol"],
                "asset_id": row["asset_id"],
                "price_at_signal": price_at_signal,
                "price_after": price_after,
                "roi_pct": roi_pct,
                "window_hours": row.get("window_hours") or 24,
                "risk_note": row.get("risk_note") or "",
                "score": float(row.get("score") or 0.0),
                "llm_summary": row.get("llm_summary") or "",
                "signal_created_at": signal_time,
            }
        )
    return updates
