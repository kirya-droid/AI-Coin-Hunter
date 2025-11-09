#!/usr/bin/env python3
"""
Installer for AI Coin Hunter (MVP).
Creates the project structure with correct indentation and file contents.
Usage:
  python setup_ai_coin_hunter.py
"""
import os, pathlib, sys, textwrap

FILES = {
  "requirements.txt": """apscheduler
python-dotenv
requests
pandas
numpy
scikit-learn
pydantic
pyyaml
aiogram
loguru
openai
""",
  ".env.example": """OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=-100123456789
CRYPTOPANIC_API_KEY=
""",
  "config.yaml": """app:
  base_currency: USDT
  network_timeout_s: 20
sources:
  coingecko:
    enabled: true
    top_n: 200
  news:
    enabled: false   # включим позже
anomaly:
  mode: rules
  rules:
    min_price_change_24h_pct: 15
    min_volume_change_24h_pct: 200
    min_rvol: 3
    min_market_cap_usd: 5000000
notify:
  telegram:
    enabled: true
schedule:
  interval_minutes: 30
""",
  "Dockerfile": """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "src.main", "interval"]
""",
  "Makefile": """.PHONY: venv install run-once run-interval

venv:
\tpython -m venv .venv

install:
\t. .venv/bin/activate || . .venv/Scripts/activate && pip install -r requirements.txt

run-once:
\tpython -m src.main once

run-interval:
\tpython -m src.main interval
""",
  "README.md": """# AI Coin Hunter (MVP)

Сканер аномалий по крипто-монетам с ИИ-объяснениями и уведомлениями в Telegram.

## Быстрый старт

```bash
python -m venv .venv
# Linux/Mac:
source .venv/bin/activate
# Windows:
# .venv\\Scripts\\activate

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
""",
  "src/__init__.py": "",
  "src/config.py": """from __future__ import annotations
from pydantic import BaseModel
import yaml, os

class RulesCfg(BaseModel):
    min_price_change_24h_pct: float = 15
    min_volume_change_24h_pct: float = 200
    min_rvol: float = 3
    min_market_cap_usd: float = 5_000_000

class AnomalyCfg(BaseModel):
    mode: str = "rules"
    rules: RulesCfg = RulesCfg()

class NotifyTelegramCfg(BaseModel):
    enabled: bool = True

class NotifyCfg(BaseModel):
    telegram: NotifyTelegramCfg = NotifyTelegramCfg()

class SourcesCfg(BaseModel):
    coingecko: dict
    news: dict

class AppCfg(BaseModel):
    base_currency: str = "USDT"
    network_timeout_s: int = 20

class ScheduleCfg(BaseModel):
    interval_minutes: int = 30

class Cfg(BaseModel):
    app: AppCfg
    sources: SourcesCfg
    anomaly: AnomalyCfg
    notify: NotifyCfg
    schedule: ScheduleCfg

_def_path = os.environ.get("CONFIG_PATH", "config.yaml")

def load_config(path: str | None = None) -> Cfg:
    with open(path or _def_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Cfg(**raw)
""",
  "src/utils/logging.py": """from loguru import logger
import sys

def setup_logging():
    logger.remove()
    logger.add(sys.stdout, level="INFO", enqueue=True, colorize=True,
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")
    return logger
""",
  "src/db/dao.py": """import sqlite3, pathlib, datetime as dt
from typing import Iterable, Dict, Any

_DB_PATH = pathlib.Path("ai_coin_hunter.db")

SCHEMA = \"\"\"
CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT,
  finished_at TEXT,
  status TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER,
  asset_id TEXT,
  symbol TEXT,
  price REAL,
  price_change_24h REAL,
  volume_24h REAL,
  volume_change_24h REAL,
  rvol REAL,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER,
  asset_id TEXT,
  symbol TEXT,
  reason TEXT,
  llm_summary TEXT,
  risk_note TEXT,
  score REAL,
  created_at TEXT
);
\"\"\"

class DB:
    def __init__(self, path: pathlib.Path = _DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(SCHEMA)

    def run_start(self) -> int:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO runs(started_at, status) VALUES(?, ?)", (dt.datetime.utcnow().isoformat(), "running"))
        self.conn.commit()
        return cur.lastrowid

    def run_finish(self, run_id: int, status: str = "ok"):
        self.conn.execute("UPDATE runs SET finished_at=?, status=? WHERE run_id=?", (dt.datetime.utcnow().isoformat(), status, run_id))
        self.conn.commit()

    def insert_snapshots(self, run_id: int, rows: Iterable[Dict[str, Any]]):
        self.conn.executemany(
            \"\"\"
            INSERT INTO snapshots(run_id, asset_id, symbol, price, price_change_24h, volume_24h, volume_change_24h, rvol, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            \"\"\" ,
            [(
                run_id, r["asset_id"], r["symbol"].upper(), r.get("current_price", 0.0), r.get("price_change_percentage_24h", 0.0),
                r.get("total_volume", 0.0), r.get("volume_change_24h_pct", 0.0), r.get("rvol", 0.0), dt.datetime.utcnow().isoformat()
            ) for r in rows]
        )
        self.conn.commit()

    def insert_signal(self, run_id: int, asset_id: str, symbol: str, reason: str, summary: str, risk: str, score: float):
        self.conn.execute(
            \"\"\"
            INSERT INTO signals(run_id, asset_id, symbol, reason, llm_summary, risk_note, score, created_at)
            VALUES(?,?,?,?,?,?,?,?)
            \"\"\" ,
            (run_id, asset_id, symbol, reason, summary, risk, score, dt.datetime.utcnow().isoformat())
        )
        self.conn.commit()
""",
  "src/ingest/coingecko.py": """import requests, math
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
""",
  "src/features/build.py": """import pandas as pd

def build_features(market_df: pd.DataFrame) -> pd.DataFrame:
    df = market_df.copy()
    if "price_change_percentage_24h" not in df:
        df["price_change_percentage_24h"] = 0.0
    df["volume_change_24h_pct"] = (df["rvol"] * 100) - 100
    return df
""",
  "src/detect/rules.py": """import pandas as pd
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
        "asset_id", "symbol", "name", "current_price", "market_cap",
        "price_change_percentage_24h", "total_volume", "volume_change_24h_pct", "rvol"
    ]
    out = df.loc[mask, cols].sort_values("price_change_percentage_24h", ascending=False)
    return out.to_dict(orient="records")
""",
  "src/llm/prompt_templates.py": """SUMMARY_PROMPT = (
    "Ты — аналитик крипторынка. Отвечай кратко и по делу.\\n"
    "Монета: {symbol}. ΔP24h={dprice:.1f}% ΔV24h≈{dvol:.0f}% rVOL={rvol:.2f}.\\n"
    "Дай: 1) главную причину роста (гипотеза: листинг/новости/соцсети/манипуляции), 2) риски, 3) вывод (наблюдать/осторожно входить).\\n"
    "Формат: 'Причина: ... | Риски: ... | Вывод: ...'"
)
""",
  "src/llm/explain.py": """from openai import OpenAI
from .prompt_templates import SUMMARY_PROMPT
import os

_client = None

def _client_once():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

def explain_signal(item: dict) -> tuple[str, str, float]:
    \\"\\\"Возвращает (summary, risk, score).\\"\\\"
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
""",
  "src/notify/telegram_bot.py": """import os
from aiogram import Bot

async def send_signal_async(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    bot = Bot(token=token)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True)

import asyncio

def send_signal(text: str):
    asyncio.run(send_signal_async(text))
""",
  "src/pipeline.py": """from loguru import logger
from .config import load_config
from .db.dao import DB
from .ingest.coingecko import fetch_top_markets
from .features.build import build_features
from .detect.rules import detect_by_rules
from .llm.explain import explain_signal
from .notify.telegram_bot import send_signal

def format_card(item: dict, summary: str) -> str:
    return (
        f"<b>🔥 Аномалия:</b> ${item['symbol'].upper()} — {item['name']}\\n"
        f"📈 ΔP 24ч: <b>{item['price_change_percentage_24h']:.1f}%</b> | ΔV≈ <b>{item['volume_change_24h_pct']:.0f}%</b> | rVOL: <b>{item['rvol']:.2f}</b>\\n"
        f"💰 Цена: {item['current_price']} | Cap: {int(item['market_cap']):,}\\n"
        f"🧠 {summary}"
    )

def pipeline_once():
    cfg = load_config()
    db = DB()
    run_id = db.run_start()
    try:
        markets = fetch_top_markets(top_n=cfg.sources["coingecko"]["top_n"], vs_currency="usd")
        feats = build_features(markets)
        candidates = detect_by_rules(
            feats,
            min_price_change_24h_pct=cfg.anomaly.rules.min_price_change_24h_pct,
            min_volume_change_24h_pct=cfg.anomaly.rules.min_volume_change_24h_pct,
            min_rvol=cfg.anomaly.rules.min_rvol,
            min_market_cap_usd=cfg.anomaly.rules.min_market_cap_usd,
        )
        db.insert_snapshots(run_id, feats.to_dict(orient="records"))
        logger.info(f"Найдено кандидатов: {len(candidates)}")
        for it in candidates:
            summary, risk, score = explain_signal(it)
            db.insert_signal(run_id, it["asset_id"], it["symbol"], reason="rules", summary=summary, risk=risk, score=score)
            send_signal(format_card(it, summary))
        db.run_finish(run_id, status="ok")
    except Exception as e:
        logger.exception(e)
        db.run_finish(run_id, status=f"error: {e}")
        raise
""",
  "src/scheduler.py": """from apscheduler.schedulers.blocking import BlockingScheduler
from .pipeline import pipeline_once
from .config import load_config
from .utils.logging import setup_logging

def run_once():
    setup_logging()
    pipeline_once()

def run_interval():
    setup_logging()
    cfg = load_config()
    minutes = cfg.schedule.interval_minutes
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(pipeline_once, "interval", minutes=minutes, max_instances=1, coalesce=True)
    sched.start()
""",
  "src/main.py": """import argparse
from .scheduler import run_once, run_interval

def main():
    ap = argparse.ArgumentParser(description="AI Coin Hunter")
    ap.add_argument("cmd", choices=["once", "interval"], help="Запустить разово или по расписанию")
    args = ap.parse_args()
    if args.cmd == "once":
        run_once()
    else:
        run_interval()

if __name__ == "__main__":
    main()
"""
}

def main():
    root = pathlib.Path.cwd() / "ai-coin-hunter"
    for path, content in FILES.items():
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    print(f"✅ Project created at: {root.resolve()}")
    print("Next steps:")
    print("  1) cd ai-coin-hunter")
    print("  2) python -m venv .venv && (activate)")
    print("  3) pip install -r requirements.txt")
    print("  4) cp .env.example .env  # и заполнить ключи")
    print("  5) python -m src.main once")

if __name__ == "__main__":
    main()
