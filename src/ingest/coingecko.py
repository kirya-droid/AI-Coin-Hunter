import requests
import pandas as pd

CG_BASE = "https://api.coingecko.com/api/v3/coins/markets"
CG_SIMPLE_PRICE = "https://api.coingecko.com/api/v3/simple/price"

HEADERS = {"Accept": "application/json", "User-Agent": "ai-coin-hunter/0.1"}


def fetch_top_markets(top_n: int = 200, vs_currency: str = "usd") -> pd.DataFrame:
    if top_n <= 0:
        return pd.DataFrame()
    per_page = min(250, max(1, top_n))
    pages = max(1, (top_n + per_page - 1) // per_page)
    frames = []
    fetched = 0
    for p in range(1, pages + 1):
        remaining = max(0, top_n - fetched)
        if remaining == 0:
            break
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": min(per_page, remaining),
            "page": p,
            "price_change_percentage": "24h",
        }
        r = requests.get(CG_BASE, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        frames.append(pd.DataFrame(data))
        fetched += len(data)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if len(df) > top_n:
        df = df.iloc[:top_n]
    vol = df["total_volume"].astype(float)
    median_vol = vol.median() if not vol.empty else 0.0
    if median_vol <= 0:
        df["rvol"] = 0.0
    else:
        df["rvol"] = (vol / median_vol).clip(lower=0)
    df.rename(columns={"id": "asset_id"}, inplace=True)
    return df


def fetch_simple_price(asset_id: str, vs_currency: str = "usd") -> float | None:
    params = {"ids": asset_id, "vs_currencies": vs_currency}
    r = requests.get(CG_SIMPLE_PRICE, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    payload = r.json()
    data = payload.get(asset_id)
    if not data:
        return None
    price = data.get(vs_currency)
    if price is None:
        return None
    try:
        return float(price)
    except (TypeError, ValueError):
        return None
