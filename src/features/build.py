from typing import Mapping
import pandas as pd


def build_features(market_df: pd.DataFrame, previous_volume: Mapping[str, float] | None = None) -> pd.DataFrame:
    df = market_df.copy()
    if "price_change_percentage_24h" not in df:
        df["price_change_percentage_24h"] = 0.0

    prev_volume = previous_volume or {}

    def _vol_change(row: pd.Series) -> float:
        asset_id = row.get("asset_id")
        current = float(row.get("total_volume", 0.0) or 0.0)
        previous = float(prev_volume.get(asset_id, 0.0) or 0.0)
        if previous <= 0.0:
            return 0.0
        return ((current - previous) / previous) * 100.0

    df["volume_change_24h_pct"] = df.apply(_vol_change, axis=1)
    return df
