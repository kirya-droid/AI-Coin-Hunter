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

## Как подтянуть последние изменения

```bash
git fetch origin                 # забираем свежие коммиты с сервера
git checkout <нужная_ветка>      # переходим на нужную ветку, если ещё нет
git pull --ff-only origin <нужная_ветка>
```

- Если локальные правки конфликтуют с обновлениями, сначала зафиксируй их (`git commit` или `git stash`), затем повтори `git pull`.
- Команда `git status` подскажет, есть ли незакоммиченные файлы перед тем, как тянуть изменения.

## Настройки
- `config.yaml` — пороги аномалий и расписание.
- БД: `ai_coin_hunter.db` (SQLite).

### Новости CryptoPanic
- Включи блок `sources.cryptopanic.enabled: true`, чтобы подтягивать свежие заголовки и их сентимент в карточки сигналов.
- Токен не обязателен, но если он есть, укажи `sources.cryptopanic.auth_token` — фильтрация по тикерам станет точнее.
- Для старых конфигов можно оставить `sources.news.enabled: true` — бот автоматически переключится на новый клиент.

## Примечание
Для rVOL/ΔV используется прокси-оценка на основе медианы объёмов из CoinGecko (MVP).
