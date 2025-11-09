from typing import Mapping
import datetime as dt
import pandas as pd


def build_features(
    market_df: pd.DataFrame,
    previous_snapshots: Mapping[str, Mapping[str, float | str]] | None = None,
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
    return df
