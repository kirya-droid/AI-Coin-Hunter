# AI Coin Hunter (MVP)

Сканер аномалий по крипто-монетам с ИИ-объяснениями и уведомлениями в Telegram.

## Быстрый старт

```bash
python -m venv .venv
# Linux/Mac:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# Заполни OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

python -m src.main once   # разовый прогон
python -m src.main interval  # по расписанию (каждые 30 мин)
```

## Настройки
- `config.yaml` — пороги аномалий и расписание.
- БД: `ai_coin_hunter.db` (SQLite).

## Примечание
Для rVOL/ΔV используется прокси-оценка на основе медианы объёмов из CoinGecko (MVP).
