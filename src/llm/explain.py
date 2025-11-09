from openai import OpenAI
from .prompt_templates import SUMMARY_PROMPT
import os

_client = None

def _client_once():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

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
        text = f"LLM недоступен: {e}. Гипотеза: технический рост на высоком rVOL; Риск: волатильность; Вывод: наблюдать."
    summary = text
    risk = ""
    score = 0.5
    return summary, risk, score
