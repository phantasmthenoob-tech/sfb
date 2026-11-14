"""SQLite connection handling and schema."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    model_type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER REFERENCES agents(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('agent', 'manual')),
    starting_balance REAL NOT NULL,
    cash REAL NOT NULL,
    borrow_fees REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    average_entry REAL NOT NULL,
    realized_pnl REAL NOT NULL DEFAULT 0,
    borrow_fees REAL NOT NULL DEFAULT 0,
    UNIQUE (portfolio_id, ticker)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL', 'SHORT', 'COVER')),
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'FILLED', 'REJECTED', 'CANCELLED')),
    reason TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    submitted_at TEXT NOT NULL,
    sim_time TEXT NOT NULL,
    fill_price REAL,
    filled_at TEXT,
    fees REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    fees REAL NOT NULL,
    realized_pnl REAL NOT NULL DEFAULT 0,
    sim_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    horizon TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence REAL NOT NULL,
    expected_pct REAL NOT NULL DEFAULT 0,
    price REAL NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL DEFAULT '',
    sim_time TEXT NOT NULL,
    bar_index INTEGER NOT NULL DEFAULT 0,
    settled_bar_index INTEGER,
    actual_pct REAL,
    actual_price REAL,
    outcome TEXT
);

CREATE TABLE IF NOT EXISTS market_data (
    ticker TEXT NOT NULL,
    ts TEXT NOT NULL,
    session_date TEXT NOT NULL,
    bar_index INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    PRIMARY KEY (ticker, ts)
);

CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    headline TEXT NOT NULL,
    source TEXT NOT NULL,
    sentiment REAL NOT NULL,
    ts TEXT NOT NULL,
    bar_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'replay',
    speed INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    cursor INTEGER NOT NULL,
    total_bars INTEGER NOT NULL,
    replay_preset TEXT NOT NULL DEFAULT 'all',
    range_start_date TEXT,
    range_end_date TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_cache (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    source TEXT NOT NULL,
    interval TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    last_bar_date TEXT NOT NULL,
    tickers TEXT NOT NULL,
    bar_count INTEGER NOT NULL,
    history_range TEXT NOT NULL DEFAULT '1y'
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    bar_index INTEGER NOT NULL,
    cash REAL NOT NULL,
    positions_value REAL NOT NULL,
    equity REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions (portfolio_id);
CREATE INDEX IF NOT EXISTS idx_orders_portfolio ON orders (portfolio_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_trades_portfolio ON trades (portfolio_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_news_bar ON news (bar_index);
CREATE INDEX IF NOT EXISTS idx_snapshots_portfolio ON portfolio_snapshots (portfolio_id, bar_index);
CREATE INDEX IF NOT EXISTS idx_market_data_bar ON market_data (bar_index);
"""


class Database:
    """Small SQLite helper with a single serialized connection.

    The simulation loop and the HTTP handlers share one connection guarded by a
    re-entrant lock. This is enough for a single-process demo deployment and
    keeps transactions explicit.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        with self._lock:
            self._conn.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(simulation_runs)")
            }
            if "mode" not in columns:
                self._conn.execute(
                    "ALTER TABLE simulation_runs ADD COLUMN mode TEXT NOT NULL DEFAULT 'replay'"
                )
            for name, definition in (
                ("replay_preset", "TEXT NOT NULL DEFAULT 'all'"),
                ("range_start_date", "TEXT"),
                ("range_end_date", "TEXT"),
            ):
                if name not in columns:
                    self._conn.execute(
                        f"ALTER TABLE simulation_runs ADD COLUMN {name} {definition}"
                    )
            prediction_columns = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(predictions)")
            }
            if "expected_pct" not in prediction_columns:
                self._conn.execute(
                    "ALTER TABLE predictions ADD COLUMN expected_pct REAL NOT NULL DEFAULT 0"
                )
            if "bar_index" not in prediction_columns:
                self._conn.execute(
                    "ALTER TABLE predictions ADD COLUMN bar_index INTEGER NOT NULL DEFAULT 0"
                )
            if "price" not in prediction_columns:
                self._conn.execute(
                    "ALTER TABLE predictions ADD COLUMN price REAL NOT NULL DEFAULT 0"
                )
            for name, definition in (
                ("settled_bar_index", "INTEGER"),
                ("actual_pct", "REAL"),
                ("actual_price", "REAL"),
                ("outcome", "TEXT"),
            ):
                if name not in prediction_columns:
                    self._conn.execute(
                        f"ALTER TABLE predictions ADD COLUMN {name} {definition}"
                    )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_predictions_settlement "
                "ON predictions (settled_bar_index)"
            )
            cache_columns = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(data_cache)")
            }
            if "history_range" not in cache_columns:
                self._conn.execute(
                    "ALTER TABLE data_cache ADD COLUMN history_range TEXT NOT NULL DEFAULT '1y'"
                )
            self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        with self._lock:
            row = self._conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()
