from typing import Mapping, Sequence
import datetime as dt
import pandas as pd


def build_features(
    market_df: pd.DataFrame,
    previous_snapshots: Mapping[str, Mapping[str, float | str]] | None = None,
    price_history: Mapping[str, Sequence[tuple[str, float]]] | None = None,
    *,
    current_time: dt.datetime | None = None,
) -> pd.DataFrame:
    df = market_df.copy()
    if "price_change_percentage_24h" not in df:
        df["price_change_percentage_24h"] = 0.0

    prev_data = previous_snapshots or {}
    now = current_time or dt.datetime.utcnow()

    def _vol_change(row: pd.Series) -> float:
        asset_id = row.get("asset_id")
        current = float(row.get("total_volume", 0.0) or 0.0)
        prev_entry = prev_data.get(asset_id) if asset_id else None
        if not prev_entry:
            return 0.0
        previous = float(prev_entry.get("volume_24h", 0.0) or 0.0)
        if previous <= 0.0:
            return 0.0
        prev_ts_raw = prev_entry.get("created_at")
        prev_ts = None
        if prev_ts_raw:
            try:
                prev_ts = dt.datetime.fromisoformat(str(prev_ts_raw))
            except ValueError:
                prev_ts = None
        delta_hours = None
        if prev_ts:
            delta_hours = (now - prev_ts).total_seconds() / 3600.0
        if not delta_hours or delta_hours <= 0:
            delta_hours = 24.0
        scale = 24.0 / max(delta_hours, 1.0)
        raw_change = ((current - previous) / previous) * 100.0
        return raw_change * scale

    df["volume_change_24h_pct"] = df.apply(_vol_change, axis=1)

    # Momentum metrics from CoinGecko payload
    for horizon in ("7d", "30d"):
        col = f"price_change_percentage_{horizon}"
        if col not in df:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0)

    if {"high_24h", "low_24h", "current_price"}.issubset(df.columns):
        with pd.option_context("mode.use_inf_as_na", True):
            df["intraday_range_pct"] = ((df["high_24h"] - df["low_24h"]) / df["current_price"].replace(0, pd.NA)) * 100.0
    else:
        df["intraday_range_pct"] = 0.0
    df["intraday_range_pct"] = df["intraday_range_pct"].fillna(0.0)

    history = price_history or {}

    def _realized_vol(row: pd.Series) -> float:
        asset_id = row.get("asset_id")
        series = history.get(asset_id) if asset_id else None
        if not series or len(series) < 3:
            return 0.0
        prices: list[float] = []
        for raw_ts, price in series:
            try:
                dt.datetime.fromisoformat(str(raw_ts))
            except ValueError:
                continue
            try:
                prices.append(float(price))
            except (TypeError, ValueError):
                continue
        if len(prices) < 3:
            return 0.0
        returns = []
        for prev, curr in zip(prices, prices[1:]):
            if prev <= 0:
                continue
            returns.append((curr - prev) / prev)
        if not returns:
            return 0.0
        series_vol = pd.Series(returns)
        std = float(series_vol.std(ddof=0))
        if not std:
            return 0.0
        # Annualize assuming 24 samples per day * 365 days when using hourly-ish snapshots
        return std * (24 * 365) ** 0.5 * 100.0

    df["volatility_annualized_pct"] = df.apply(_realized_vol, axis=1)
    df["volatility_annualized_pct"] = df["volatility_annualized_pct"].fillna(0.0)
    return df
