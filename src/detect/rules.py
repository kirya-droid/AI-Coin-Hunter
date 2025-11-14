import pandas as pd
from typing import List, Dict, Any

def detect_by_rules(df: pd.DataFrame, *,
                    min_price_change_24h_pct: float,
                    min_volume_change_24h_pct: float,
                    min_rvol: float,
                    min_market_cap_usd: float) -> List[Dict[str, Any]]:
    mask = (
        (df["market_cap"].fillna(0) >= min_market_cap_usd) &
        (df["price_change_percentage_24h"].fillna(0) >= min_price_change_24h_pct) &
        (df["volume_change_24h_pct"].fillna(-1e9) >= min_volume_change_24h_pct) &
        (df["rvol"].fillna(0) >= min_rvol)
    )
    cols = [
        "asset_id",
        "symbol",
        "name",
        "current_price",
        "market_cap",
        "price_change_percentage_24h",
        "price_change_percentage_7d",
        "price_change_percentage_30d",
        "total_volume",
        "volume_change_24h_pct",
        "rvol",
        "intraday_range_pct",
        "volatility_annualized_pct",
    ]
    out = df.loc[mask, cols].sort_values("price_change_percentage_24h", ascending=False)
    return out.to_dict(orient="records")
