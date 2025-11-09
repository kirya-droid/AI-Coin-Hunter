from __future__ import annotations

import datetime as dt
from typing import Dict, List, Any, Iterable, Sequence

import requests
from loguru import logger

from ..config import CryptoPanicCfg

API_URL = "https://cryptopanic.com/api/v1/posts/"
UTC = dt.timezone.utc


def _chunked(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _build_params(cfg: CryptoPanicCfg, symbols: Iterable[str]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "kind": "news",
        "public": "true",
    }
    currency_list = [sym.upper() for sym in symbols if sym]
    if currency_list:
        params["currencies"] = ",".join(sorted(currency_list))
    if cfg.auth_token:
        params["auth_token"] = cfg.auth_token
    return params


def fetch_asset_news(symbols: Iterable[str], cfg: CryptoPanicCfg) -> Dict[str, Dict[str, Any]]:
    """Fetch recent news headlines for provided tickers using CryptoPanic."""

    if not cfg.enabled:
        return {}

    unique_symbols = sorted({sym.upper() for sym in symbols if sym})
    if not unique_symbols:
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    logger.info(
        f"CryptoPanic: всего уникальных тикеров={len(unique_symbols)} "
        f"(max_headlines={cfg.max_headlines}, lookback={cfg.lookback_hours}h)"
    )
    max_headlines = cfg.max_headlines if cfg.max_headlines and cfg.max_headlines > 0 else None
    cutoff = dt.datetime.now(UTC) - dt.timedelta(hours=max(1, cfg.lookback_hours))

    for batch in _chunked(unique_symbols, 40):
        params = _build_params(cfg, batch)
        try:
            resp = requests.get(API_URL, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Failed to fetch news from CryptoPanic (symbols={}): {}",
                ",".join(batch),
                exc,
            )
            continue

        payload = resp.json()
        items: List[dict[str, Any]] = payload.get("results", []) if isinstance(payload, dict) else []

        if not items and "currencies" in params:
            # Some accounts require auth for per-currency filtering — retry without the filter.
            fallback_params = {k: v for k, v in params.items() if k != "currencies"}
            try:
                resp = requests.get(API_URL, params=fallback_params, timeout=15)
                resp.raise_for_status()
                payload = resp.json()
                items = payload.get("results", []) if isinstance(payload, dict) else []
            except Exception as exc:
                logger.warning("Fallback CryptoPanic request failed: {}", exc)
                continue

        for item in items:
            currencies = item.get("currencies") or []
            if not currencies:
                continue
            published_at = item.get("published_at") or item.get("created_at")
            if published_at:
                try:
                    published_dt = dt.datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
                except ValueError:
                    published_dt = None
                if published_dt:
                    if published_dt.tzinfo is None:
                        published_dt = published_dt.replace(tzinfo=UTC)
                    published_dt = published_dt.astimezone(UTC)
                    if published_dt < cutoff:
                        continue
            votes = int(item.get("votes", {}).get("total", 0)) if isinstance(item.get("votes"), dict) else 0
            if votes < cfg.min_votes:
                continue
            sentiment = item.get("sentiment") or "neutral"
            for currency in currencies:
                code = currency.get("code") if isinstance(currency, dict) else None
                if not code:
                    continue
                bucket = results.setdefault(
                    code.upper(),
                    {"headlines": [], "sentiment_counts": {"positive": 0, "negative": 0, "neutral": 0}},
                )
                if max_headlines is not None and len(bucket["headlines"]) >= max_headlines:
                    continue
                title = item.get("title") or item.get("slug") or ""
                url = item.get("url") or item.get("source", {}).get("url") if isinstance(item.get("source"), dict) else None
                bucket["headlines"].append({"title": title, "url": url})
                bucket["sentiment_counts"][sentiment] = bucket["sentiment_counts"].get(sentiment, 0) + 1

    for sym, data in results.items():
        counts = data.get("sentiment_counts", {})
        total = sum(counts.values()) or 1
        score = (counts.get("positive", 0) - counts.get("negative", 0)) / total
        data["sentiment_score"] = score
        data["headline_summary"] = "; ".join(
            f"{idx+1}) {head['title']}" + (f" ({head['url']})" if head.get("url") else "")
            for idx, head in enumerate(data.get("headlines", []))
        )

    return results
