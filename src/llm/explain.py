from __future__ import annotations

import os
from typing import Tuple

from openai import OpenAI

from .prompt_templates import SUMMARY_PROMPT

_client: OpenAI | None = None


def _client_once() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def _parse_sections(text: str) -> Tuple[str, float]:
    risk = ""
    score = 0.5
    conclusion = ""
    for part in text.split("|"):
        chunk = part.strip()
        low = chunk.lower()
        if low.startswith("риски:"):
            risk = chunk.split(":", 1)[1].strip() if ":" in chunk else chunk
        elif low.startswith("вывод:"):
            conclusion = chunk.split(":", 1)[1].strip() if ":" in chunk else chunk
    if conclusion:
        low_conc = conclusion.lower()
        if any(word in low_conc for word in ("наблюдай", "наблюдать")):
            score = min(score, 0.45)
        if any(word in low_conc for word in ("осторож", "риск", "коротк")):
            score = min(score, 0.3)
        if any(word in low_conc for word in ("частично фикс", "фиксируй", "take profit")):
            score = min(score, 0.35)
        if any(word in low_conc for word in ("вход", "покуп", "long", "bull", "усилить")):
            score = max(score, 0.7)
        if any(word in low_conc for word in ("фикс", "продаж", "sell", "short", "избег")):
            score = min(score, 0.2)
    return risk, score


def _format_number(value: float | None, *, precision: int = 2, default: str = "—") -> str:
    if value is None:
        return default
    try:
        return f"{float(value):.{precision}f}"
    except (TypeError, ValueError):
        return default


def _build_clues(item: dict) -> str:
    clues: list[str] = []
    price_change = float(item.get("price_change_percentage_24h", 0.0) or 0.0)
    volume_change = float(item.get("volume_change_24h_pct", 0.0) or 0.0)
    rvol = float(item.get("rvol", 0.0) or 0.0)
    market_cap = float(item.get("market_cap", 0.0) or 0.0)
    price_change_7d = float(item.get("price_change_percentage_7d", 0.0) or 0.0)
    price_change_30d = float(item.get("price_change_percentage_30d", 0.0) or 0.0)
    intraday_range = float(item.get("intraday_range_pct", 0.0) or 0.0)
    volatility = float(item.get("volatility_annualized_pct", 0.0) or 0.0)
    news_count = int(item.get("news_count", 0) or 0)
    news_sentiment = float(item.get("news_sentiment", 0.0) or 0.0)
    if abs(price_change) >= 20:
        trend = "рост" if price_change > 0 else "падение"
        clues.append(f"Цена показала {trend} на {price_change:+.1f}% за сутки")
    if abs(price_change_7d) >= 30:
        clues.append(f"На горизонте 7д изменение {price_change_7d:+.1f}%")
    if abs(price_change_30d) >= 60:
        clues.append(f"30-дневная динамика {price_change_30d:+.1f}% ⇒ долгосрочный тренд")
    if abs(volume_change) >= 500:
        clues.append(f"Объём вырос примерно на {volume_change:+.0f}% относительно предыдущего периода")
    if rvol >= 10:
        clues.append(f"rVOL {rvol:.1f} ⇒ обороты значительно выше среднего")
    if intraday_range >= 15:
        clues.append(f"Диапазон суток {intraday_range:.1f}% ⇒ резкие движения")
    if volatility >= 150:
        clues.append(f"Оценочная волатильность {volatility:.0f}% годовых ⇒ высокая рискованность")
    if market_cap and market_cap < 1_000_000_000:
        clues.append("Относительно небольшая капитализация ⇒ возможна манипулятивность")
    if market_cap and market_cap > 10_000_000_000:
        clues.append("Крупная капитализация ⇒ вероятны институциональные драйверы")
    if news_count:
        sentiment_hint = "" if abs(news_sentiment) < 0.2 else ("позитивный" if news_sentiment > 0 else "негативный")
        clues.append(
            f"За последние сутки найдено {news_count} релевантных новостей"
            + (f", общий тон: {sentiment_hint}" if sentiment_hint else "")
        )
    return "; ".join(clues) if clues else "дополнительных подсказок нет"


def explain_signal(
    item: dict,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    window_hours: int | None = None,
    news_brief: str | None = None,
) -> tuple[str, str, float]:
    """Возвращает (summary, risk, score)."""

    prompt = SUMMARY_PROMPT.format(
        symbol=item.get("symbol", "?"),
        name=item.get("name", "?"),
        price=_format_number(item.get("current_price"), precision=4),
        market_cap=f"{float(item.get('market_cap', 0.0) or 0.0):,.0f}",
        dprice=float(item.get("price_change_percentage_24h", 0.0) or 0.0),
        dprice7=float(item.get("price_change_percentage_7d", 0.0) or 0.0),
        dprice30=float(item.get("price_change_percentage_30d", 0.0) or 0.0),
        dvol=float(item.get("volume_change_24h_pct", 0.0) or 0.0),
        rvol=float(item.get("rvol", 0.0) or 0.0),
        window_hours=window_hours or 24,
        range24=float(item.get("intraday_range_pct", 0.0) or 0.0),
        volatility=float(item.get("volatility_annualized_pct", 0.0) or 0.0),
        news_brief=news_brief or "нет подтверждённых новостей",
        clues=_build_clues(item),
    )
    req_model = model or "gpt-5-nano"
    req_temperature = 0.35 if temperature is None else temperature
    req_max_tokens = 220 if max_tokens is None else max_tokens

    try:
        client = _client_once()
        resp = client.chat.completions.create(
            model=req_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=req_temperature,
            max_tokens=req_max_tokens,
        )
        text = resp.choices[0].message.content.strip()
    except Exception as e:
        text = (
            "LLM недоступен: {err}. Причины: технический всплеск объёмов | "
            "Риски: возможна фиксация прибыли и манипуляции | Вывод: наблюдать."
        ).format(err=e)

    risk, score = _parse_sections(text)
    return text, risk, score
