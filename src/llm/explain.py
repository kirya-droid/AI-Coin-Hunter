from openai import OpenAI
from .prompt_templates import SUMMARY_PROMPT
import os

_client = None


def _client_once():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def _parse_sections(text: str) -> tuple[str, float]:
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
            score = 0.4
        if any(word in low_conc for word in ("осторож", "риск")):
            score = min(score, 0.3)
        if any(word in low_conc for word in ("вход", "покуп", "long", "bull")):
            score = max(score, 0.7)
        if any(word in low_conc for word in ("фикс", "продаж", "sell", "short")):
            score = min(score, 0.2)
    return risk, score


def explain_signal(item: dict) -> tuple[str, str, float]:
    """Возвращает (summary, risk, score)."""
    prompt = SUMMARY_PROMPT.format(
        symbol=item.get("symbol", "?"),
        dprice=item.get("price_change_percentage_24h", 0.0),
        dvol=item.get("volume_change_24h_pct", 0.0),
        rvol=item.get("rvol", 0.0),
    )
    try:
        client = _client_once()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=180,
        )
        text = resp.choices[0].message.content.strip()
    except Exception as e:
        text = (
            f"LLM недоступен: {e}. Причина: технический рост на высоком rVOL | Риски: волатильность | Вывод: наблюдать."
        )
    risk, score = _parse_sections(text)
    return text, risk, score
