import requests, math
import pandas as pd

CG_BASE = "https://api.coingecko.com/api/v3/coins/markets"

HEADERS = {"Accept": "application/json", "User-Agent": "ai-coin-hunter/0.1"}

def fetch_top_markets(top_n: int = 200, vs_currency: str = "usd") -> pd.DataFrame:
    per_page = 250
    pages = max(1, (top_n + per_page - 1) // per_page)
    frames = []
    for p in range(1, pages + 1):
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": min(per_page, top_n),
            "page": p,
            "price_change_percentage": "24h",
        }
        r = requests.get(CG_BASE, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        frames.append(pd.DataFrame(r.json()))
    df = pd.concat(frames, ignore_index=True)
    vol = df["total_volume"].astype(float)
    df["rvol"] = (vol / vol.median()).clip(lower=0)
    df.rename(columns={"id": "asset_id"}, inplace=True)
    return df
