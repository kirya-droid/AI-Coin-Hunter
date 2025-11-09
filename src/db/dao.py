import sqlite3, pathlib, datetime as dt
from typing import Iterable, Dict, Any, List, Optional

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
CREATE TABLE IF NOT EXISTS signal_performance (
  signal_id INTEGER PRIMARY KEY,
  asset_id TEXT,
  symbol TEXT,
  price_at_signal REAL,
  price_after_window REAL,
  roi_pct REAL,
  window_hours INTEGER,
  evaluated_at TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_snapshots_asset_created ON snapshots(asset_id, created_at);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_signal_perf_pending ON signal_performance(window_hours, evaluated_at);
"""

class DB:
    def __init__(self, path: pathlib.Path = _DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Apply lightweight migrations for backward compatibility."""
        cur = self.conn.execute("PRAGMA table_info(signal_performance)")
        cols = {row[1] for row in cur.fetchall()}
        if "price_at_signal" not in cols:
            self.conn.execute("ALTER TABLE signal_performance ADD COLUMN price_at_signal REAL")
        if "price_after_window" not in cols:
            self.conn.execute("ALTER TABLE signal_performance ADD COLUMN price_after_window REAL")
        if "roi_pct" not in cols:
            self.conn.execute("ALTER TABLE signal_performance ADD COLUMN roi_pct REAL")
        if "window_hours" not in cols:
            self.conn.execute("ALTER TABLE signal_performance ADD COLUMN window_hours INTEGER")
        if "evaluated_at" not in cols:
            self.conn.execute("ALTER TABLE signal_performance ADD COLUMN evaluated_at TEXT")
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc:
                self.conn.rollback()
        finally:
            self.close()

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    def run_start(self) -> int:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO runs(started_at, status) VALUES(?, ?)", (dt.datetime.utcnow().isoformat(), "running"))
        self.conn.commit()
        return cur.lastrowid

    def run_finish(self, run_id: int, status: str = "ok"):
        self.conn.execute(
            "UPDATE runs SET finished_at=?, status=? WHERE run_id=?",
            (dt.datetime.utcnow().isoformat(), status, run_id),
        )
        self.conn.commit()

    def insert_snapshots(self, run_id: int, rows: Iterable[Dict[str, Any]], *, created_at: Optional[dt.datetime] = None):
        created_iso = (created_at or dt.datetime.utcnow()).isoformat()
        self.conn.executemany(
            """
            INSERT INTO snapshots(run_id, asset_id, symbol, price, price_change_24h, volume_24h, volume_change_24h, rvol, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            [(
                run_id, r["asset_id"], r["symbol"].upper(), r.get("current_price", 0.0), r.get("price_change_percentage_24h", 0.0),
                r.get("total_volume", 0.0), r.get("volume_change_24h_pct", 0.0), r.get("rvol", 0.0), created_iso
            ) for r in rows]
        )
        self.conn.commit()

    def insert_signal(
        self,
        run_id: int,
        asset_id: str,
        symbol: str,
        reason: str,
        summary: str,
        risk: str,
        score: float,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO signals(run_id, asset_id, symbol, reason, llm_summary, risk_note, score, created_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (run_id, asset_id, symbol, reason, summary, risk, score, dt.datetime.utcnow().isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def ensure_signal_performance(
        self, signal_id: int, asset_id: str, symbol: str, price_at_signal: float, window_hours: int = 24
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO signal_performance(signal_id, asset_id, symbol, price_at_signal, window_hours)
            VALUES(?,?,?,?,?)
            ON CONFLICT(signal_id) DO UPDATE SET
                asset_id=excluded.asset_id,
                symbol=excluded.symbol,
                price_at_signal=COALESCE(NULLIF(signal_performance.price_at_signal, 0), excluded.price_at_signal),
                window_hours=excluded.window_hours
            """,
            (signal_id, asset_id, symbol, price_at_signal, window_hours),
        )
        self.conn.commit()

    def get_latest_snapshot_stats(self) -> Dict[str, Dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT s.asset_id, s.volume_24h, s.created_at
            FROM snapshots s
            JOIN (
                SELECT asset_id, MAX(created_at) AS max_created
                FROM snapshots
                GROUP BY asset_id
            ) latest
            ON latest.asset_id = s.asset_id AND latest.max_created = s.created_at
            """
        )
        result: Dict[str, Dict[str, Any]] = {}
        for row in cur.fetchall():
            result[row["asset_id"]] = {
                "volume_24h": float(row["volume_24h"]) if row["volume_24h"] is not None else 0.0,
                "created_at": row["created_at"],
            }
        return result

    def get_latest_volumes(self) -> Dict[str, float]:
        """Backward compatible helper returning only volume."""
        stats = self.get_latest_snapshot_stats()
        return {asset_id: data.get("volume_24h", 0.0) for asset_id, data in stats.items()}

    def get_signals_ready_for_evaluation(self) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT sp.signal_id, sp.asset_id, sp.symbol, sp.price_at_signal, sp.window_hours,
                   sig.created_at as signal_created_at,
                   sig.risk_note, sig.score, sig.llm_summary
            FROM signal_performance sp
            JOIN signals sig ON sig.id = sp.signal_id
            WHERE sp.price_at_signal IS NOT NULL
              AND (sp.price_after_window IS NULL OR sp.evaluated_at IS NULL)
              AND datetime(sig.created_at, '+' || COALESCE(sp.window_hours, 24) || ' hours') <= datetime('now')
            """
        )
        rows = [dict(row) for row in cur.fetchall()]
        return rows

    def get_snapshot_price_after(self, asset_id: str, after_iso: str) -> Optional[float]:
        cur = self.conn.execute(
            """
            SELECT price FROM snapshots
            WHERE asset_id=? AND created_at >= ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (asset_id, after_iso),
        )
        row = cur.fetchone()
        return float(row["price"]) if row else None

    def update_signal_performance(
        self, signal_id: int, price_after_window: float, roi_pct: float, evaluated_at: dt.datetime
    ) -> None:
        self.conn.execute(
            """
            UPDATE signal_performance
            SET price_after_window=?, roi_pct=?, evaluated_at=?
            WHERE signal_id=?
            """,
            (price_after_window, roi_pct, evaluated_at.isoformat(), signal_id),
        )
        self.conn.commit()
