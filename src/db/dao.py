import sqlite3, pathlib, json, datetime as dt
from typing import Iterable, Dict, Any

_DB_PATH = pathlib.Path("ai_coin_hunter.db")

SCHEMA = """
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
"""

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
            """
            INSERT INTO snapshots(run_id, asset_id, symbol, price, price_change_24h, volume_24h, volume_change_24h, rvol, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            [(
                run_id, r["asset_id"], r["symbol"].upper(), r.get("current_price", 0.0), r.get("price_change_percentage_24h", 0.0),
                r.get("total_volume", 0.0), r.get("volume_change_24h_pct", 0.0), r.get("rvol", 0.0), dt.datetime.utcnow().isoformat()
            ) for r in rows]
        )
        self.conn.commit()

    def insert_signal(self, run_id: int, asset_id: str, symbol: str, reason: str, summary: str, risk: str, score: float):
        self.conn.execute(
            """
            INSERT INTO signals(run_id, asset_id, symbol, reason, llm_summary, risk_note, score, created_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (run_id, asset_id, symbol, reason, summary, risk, score, dt.datetime.utcnow().isoformat())
        )
        self.conn.commit()
