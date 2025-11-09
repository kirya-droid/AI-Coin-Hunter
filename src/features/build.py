import pandas as pd

def build_features(market_df: pd.DataFrame) -> pd.DataFrame:
    df = market_df.copy()
    if "price_change_percentage_24h" not in df:
        df["price_change_percentage_24h"] = 0.0
    df["volume_change_24h_pct"] = (df["rvol"] * 100) - 100
    return df
