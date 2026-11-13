"""Database access for portfolios, orders, trades, market data and the clock."""
from __future__ import annotations

from typing import Iterable

from ..config import Settings
from ..trading.accounting import round_money
from ..trading.portfolio import Holding, PortfolioState
from .database import Database


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------ setup
    def seed_accounts(self, settings: Settings, now: str) -> None:
        existing = self.db.query_one("SELECT COUNT(*) AS n FROM portfolios")
        if existing and existing["n"]:
            return

        agents = [
            ("Price AI", "price", "Technical signals from historical prices, volume and momentum."),
            ("News AI", "news", "Sentiment signals derived from financial headlines."),
            ("Combined AI", "combined", "Blends price momentum with news sentiment."),
        ]
        with self.db.transaction() as conn:
            for name, model_type, description in agents:
                conn.execute(
                    "INSERT INTO agents (name, model_type, description, created_at) VALUES (?, ?, ?, ?)",
                    (name, model_type, description, now),
                )
                agent_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                conn.execute(
                    "INSERT INTO portfolios (agent_id, name, kind, starting_balance, cash, created_at)"
                    " VALUES (?, ?, 'agent', ?, ?, ?)",
                    (agent_id, name, settings.starting_balance, settings.starting_balance, now),
                )
            conn.execute(
                "INSERT INTO portfolios (agent_id, name, kind, starting_balance, cash, created_at)"
                " VALUES (NULL, 'Your portfolio', 'manual', ?, ?, ?)",
                (settings.starting_balance, settings.starting_balance, now),
            )

    def get_simulation(self) -> dict | None:
        return self.db.query_one("SELECT * FROM simulation_runs WHERE id = 1")

    def upsert_simulation(
        self,
        *,
        status: str,
        mode: str = "replay",
        speed: int,
        start_date: str,
        end_date: str,
        cursor: int,
        total_bars: int,
        updated_at: str,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO simulation_runs (id, status, mode, speed, start_date, end_date, cursor, total_bars, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    mode = excluded.mode,
                    speed = excluded.speed,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    cursor = excluded.cursor,
                    total_bars = excluded.total_bars,
                    updated_at = excluded.updated_at
                """,
                (status, mode, speed, start_date, end_date, cursor, total_bars, updated_at),
            )

    # --------------------------------------------------------------- accounts
    def list_agents(self) -> list[dict]:
        return self.db.query(
            "SELECT id, name, model_type, description FROM agents ORDER BY id"
        )

    def get_agent(self, agent_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM agents WHERE id = ?", (agent_id,))

    def list_portfolios(self) -> list[dict]:
        rows = self.db.query(
            """
            SELECT p.*, a.name AS agent_name, a.model_type
            FROM portfolios p LEFT JOIN agents a ON a.id = p.agent_id
            ORDER BY CASE p.kind WHEN 'agent' THEN 0 ELSE 1 END, p.id
            """
        )
        return rows

    def get_portfolio(self, portfolio_id: int) -> dict | None:
        return self.db.query_one(
            """
            SELECT p.*, a.name AS agent_name, a.model_type
            FROM portfolios p LEFT JOIN agents a ON a.id = p.agent_id
            WHERE p.id = ?
            """,
            (portfolio_id,),
        )

    def get_portfolio_by_agent(self, agent_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM portfolios WHERE agent_id = ?", (agent_id,))

    def get_manual_portfolio(self) -> dict | None:
        return self.db.query_one("SELECT * FROM portfolios WHERE kind = 'manual' ORDER BY id LIMIT 1")

    def update_cash(self, portfolio_id: int, cash: float, borrow_fees: float) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE portfolios SET cash = ?, borrow_fees = ? WHERE id = ?",
                (round_money(cash), round_money(borrow_fees), portfolio_id),
            )

    def load_state(self, portfolio_id: int) -> PortfolioState:
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            raise KeyError(f"Unknown portfolio {portfolio_id}")
        state = PortfolioState(
            portfolio_id=portfolio["id"],
            name=portfolio["name"],
            kind=portfolio["kind"],
            starting_balance=portfolio["starting_balance"],
            cash=portfolio["cash"],
            borrow_fees=portfolio["borrow_fees"],
        )
        for row in self.db.query("SELECT * FROM positions WHERE portfolio_id = ?", (portfolio_id,)):
            state.holdings[row["ticker"]] = Holding(
                ticker=row["ticker"],
                quantity=row["quantity"],
                average_entry=row["average_entry"],
                realized_pnl=row["realized_pnl"],
                borrow_fees=row["borrow_fees"],
            )
        return state

    def save_state(self, state: PortfolioState) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE portfolios SET cash = ?, borrow_fees = ? WHERE id = ?",
                (round_money(state.cash), round_money(state.borrow_fees), state.portfolio_id),
            )
            for ticker, holding in state.holdings.items():
                if holding.quantity == 0:
                    conn.execute(
                        "DELETE FROM positions WHERE portfolio_id = ? AND ticker = ?",
                        (state.portfolio_id, ticker),
                    )
                    continue
                conn.execute(
                    """
                    INSERT INTO positions (portfolio_id, ticker, quantity, average_entry, realized_pnl, borrow_fees)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(portfolio_id, ticker) DO UPDATE SET
                        quantity = excluded.quantity,
                        average_entry = excluded.average_entry,
                        realized_pnl = excluded.realized_pnl,
                        borrow_fees = excluded.borrow_fees
                    """,
                    (
                        state.portfolio_id,
                        ticker,
                        holding.quantity,
                        holding.average_entry,
                        round_money(holding.realized_pnl),
                        round_money(holding.borrow_fees),
                    ),
                )

    def list_positions(self, portfolio_id: int) -> list[dict]:
        return self.db.query(
            "SELECT ticker, quantity, average_entry, realized_pnl, borrow_fees FROM positions"
            " WHERE portfolio_id = ? AND quantity != 0 ORDER BY ticker",
            (portfolio_id,),
        )

    # ----------------------------------------------------------------- orders
    def insert_order(
        self,
        *,
        portfolio_id: int,
        ticker: str,
        side: str,
        quantity: int,
        source: str,
        submitted_at: str,
        sim_time: str,
    ) -> dict:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO orders (portfolio_id, ticker, side, quantity, status, source, submitted_at, sim_time)
                VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?)
                """,
                (portfolio_id, ticker, side, quantity, source, submitted_at, sim_time),
            )
            order_id = cursor.lastrowid
        return self.get_order(order_id)  # type: ignore[return-value]

    def get_order(self, order_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM orders WHERE id = ?", (order_id,))

    def list_orders(self, portfolio_id: int | None = None, limit: int = 50) -> list[dict]:
        if portfolio_id is None:
            return self.db.query(
                """
                SELECT o.*, p.name AS portfolio_name
                FROM orders o JOIN portfolios p ON p.id = o.portfolio_id
                ORDER BY o.id DESC LIMIT ?
                """,
                (limit,),
            )
        return self.db.query(
            """
            SELECT o.*, p.name AS portfolio_name
            FROM orders o JOIN portfolios p ON p.id = o.portfolio_id
            WHERE o.portfolio_id = ? ORDER BY o.id DESC LIMIT ?
            """,
            (portfolio_id, limit),
        )

    def list_pending_orders(self) -> list[dict]:
        return self.db.query("SELECT * FROM orders WHERE status = 'PENDING' ORDER BY id")

    def mark_order_filled(self, order_id: int, price: float, fees: float, sim_time: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE orders SET status = 'FILLED', fill_price = ?, fees = ?, filled_at = ? WHERE id = ?",
                (round_money(price), round_money(fees), sim_time, order_id),
            )

    def cancel_pending_orders(self, reason: str) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE orders SET status = 'CANCELLED', reason = ? WHERE status = 'PENDING'",
                (reason,),
            )
            return cursor.rowcount

    def mark_order_rejected(self, order_id: int, reason: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE orders SET status = 'REJECTED', reason = ? WHERE id = ?",
                (reason, order_id),
            )

    def insert_trade(
        self,
        *,
        order_id: int,
        portfolio_id: int,
        ticker: str,
        side: str,
        quantity: int,
        price: float,
        fees: float,
        realized_pnl: float,
        sim_time: str,
    ) -> dict:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO trades (order_id, portfolio_id, ticker, side, quantity, price, fees, realized_pnl, sim_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    portfolio_id,
                    ticker,
                    side,
                    quantity,
                    round_money(price),
                    round_money(fees),
                    round_money(realized_pnl),
                    sim_time,
                ),
            )
            trade_id = cursor.lastrowid
        return self.db.query_one("SELECT * FROM trades WHERE id = ?", (trade_id,))  # type: ignore[return-value]

    def list_trades(self, portfolio_id: int | None = None, limit: int = 50) -> list[dict]:
        if portfolio_id is None:
            return self.db.query(
                """
                SELECT t.*, p.name AS portfolio_name
                FROM trades t JOIN portfolios p ON p.id = t.portfolio_id
                ORDER BY t.id DESC LIMIT ?
                """,
                (limit,),
            )
        return self.db.query(
            """
            SELECT t.*, p.name AS portfolio_name
            FROM trades t JOIN portfolios p ON p.id = t.portfolio_id
            WHERE t.portfolio_id = ? ORDER BY t.id DESC LIMIT ?
            """,
            (portfolio_id, limit),
        )

    # ------------------------------------------------------------ predictions
    def insert_prediction(
        self,
        *,
        agent_id: int,
        ticker: str,
        horizon: str,
        direction: str,
        confidence: float,
        expected_pct: float = 0.0,
        price: float = 0.0,
        rationale: str,
        sim_time: str,
        bar_index: int = 0,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO predictions
                    (agent_id, ticker, horizon, direction, confidence, expected_pct, price, rationale, sim_time, bar_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    ticker,
                    horizon,
                    direction,
                    round(confidence, 3),
                    round(expected_pct, 2),
                    round(price, 2),
                    rationale,
                    sim_time,
                    bar_index,
                ),
            )

    def replace_predictions(self, *, agent_id: int, rows: Iterable[dict]) -> None:
        """Replace one agent's calls for a bar with its new top five."""
        batch = list(rows)
        if not batch:
            return
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM predictions WHERE agent_id = ? AND bar_index = ?",
                (agent_id, batch[0]["bar_index"]),
            )
            conn.executemany(
                """
                INSERT INTO predictions
                    (agent_id, ticker, horizon, direction, confidence, expected_pct, price, rationale, sim_time, bar_index)
                VALUES (:agent_id, :ticker, :horizon, :direction, :confidence, :expected_pct, :price, :rationale, :sim_time, :bar_index)
                """,
                batch,
            )

    def latest_forecasts(self, bar_index: int, per_agent: int = 5) -> list[dict]:
        """The latest batch of calls per agent, biggest expected move first."""
        rows = self.db.query(
            """
            SELECT pr.*, a.name AS agent_name, a.model_type
            FROM predictions pr JOIN agents a ON a.id = pr.agent_id
            JOIN (
                SELECT agent_id, MAX(bar_index) AS bar_index
                FROM predictions WHERE bar_index <= ? GROUP BY agent_id
            ) latest
              ON latest.agent_id = pr.agent_id AND latest.bar_index = pr.bar_index
            ORDER BY pr.agent_id, ABS(pr.expected_pct) DESC, pr.id DESC
            """,
            (bar_index,),
        )
        counts: dict[int, int] = {}
        selected: list[dict] = []
        for row in rows:
            used = counts.get(row["agent_id"], 0)
            if used >= per_agent:
                continue
            counts[row["agent_id"]] = used + 1
            selected.append(row)
        return selected

    def latest_predictions(self, bar_index: int) -> list[dict]:
        """Each agent's most recent call at or before the clock, biggest estimate first."""
        return self.db.query(
            """
            SELECT pr.*, a.name AS agent_name, a.model_type
            FROM predictions pr JOIN agents a ON a.id = pr.agent_id
            WHERE pr.id IN (
                SELECT MAX(id) FROM predictions WHERE bar_index <= ? GROUP BY agent_id
            )
            ORDER BY ABS(pr.expected_pct) DESC, pr.confidence DESC
            """,
            (bar_index,),
        )

    def list_predictions(self, agent_id: int | None = None, limit: int = 50) -> list[dict]:
        if agent_id is None:
            return self.db.query(
                """
                            SELECT pr.*, a.name AS agent_name, a.model_type
            FROM predictions pr JOIN agents a ON a.id = pr.agent_id
            ORDER BY pr.bar_index DESC, ABS(pr.expected_pct) DESC, pr.id DESC
            LIMIT ?
            """,
                (limit,),
            )
        return self.db.query(
            """
            SELECT pr.*, a.name AS agent_name, a.model_type
            FROM predictions pr JOIN agents a ON a.id = pr.agent_id
            WHERE pr.agent_id = ?
            ORDER BY pr.bar_index DESC, ABS(pr.expected_pct) DESC, pr.id DESC
            LIMIT ?
            """,
            (agent_id, limit),
        )

    # ------------------------------------------------------------ market data
    def count_bars(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS n FROM market_data")
        return int(row["n"]) if row else 0

    def bulk_insert_bars(self, bars: Iterable[dict]) -> None:
        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO market_data
                    (ticker, ts, session_date, bar_index, open, high, low, close, volume)
                VALUES (:ticker, :ts, :session_date, :bar_index, :open, :high, :low, :close, :volume)
                """,
                list(bars),
            )

    def bulk_insert_news(self, items: Iterable[dict]) -> None:
        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO news (ticker, headline, source, sentiment, ts, bar_index)
                VALUES (:ticker, :headline, :source, :sentiment, :ts, :bar_index)
                """,
                list(items),
            )

    def get_data_cache(self) -> dict | None:
        return self.db.query_one("SELECT * FROM data_cache WHERE id = 1")

    def save_data_cache(
        self,
        *,
        source: str,
        interval: str,
        fetched_at: str,
        last_bar_date: str,
        tickers: Iterable[str],
        bar_count: int,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO data_cache (id, source, interval, fetched_at, last_bar_date, tickers, bar_count)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source = excluded.source,
                    interval = excluded.interval,
                    fetched_at = excluded.fetched_at,
                    last_bar_date = excluded.last_bar_date,
                    tickers = excluded.tickers,
                    bar_count = excluded.bar_count
                """,
                (source, interval, fetched_at, last_bar_date, ",".join(tickers), bar_count),
            )

    def market_summary(self) -> dict:
        row = self.db.query_one(
            """
            SELECT COUNT(*) AS bar_count,
                   COUNT(DISTINCT session_date) AS sessions,
                   MIN(session_date) AS start_date,
                   MAX(session_date) AS end_date,
                   COUNT(DISTINCT ticker) AS tickers
            FROM market_data
            """
        )
        return row or {
            "bar_count": 0,
            "sessions": 0,
            "start_date": None,
            "end_date": None,
            "tickers": 0,
        }

    def plan_new_sessions(self, session_dates: Iterable[str]) -> list[tuple[str, int]]:
        """Map new session dates onto the next available bar indices."""
        existing = {
            row["session_date"]
            for row in self.db.query("SELECT DISTINCT session_date FROM market_data")
        }
        max_row = self.db.query_one("SELECT COALESCE(MAX(bar_index), -1) AS idx FROM market_data")
        next_index = int(max_row["idx"]) + 1 if max_row else 0
        plan: list[tuple[str, int]] = []
        for day in sorted(set(session_dates)):
            if day in existing:
                continue
            plan.append((day, next_index))
            next_index += 1
        return plan

    def append_market_data(
        self,
        *,
        bars: Iterable[dict],
        sessions: list[tuple[str, int]],
        news: Iterable[dict] = (),
    ) -> int:
        """Insert bars/news for planned sessions only; existing rows stay untouched."""
        if not sessions:
            return 0
        index_for = dict(sessions)
        rows = [
            {**bar, "bar_index": index_for[bar["session_date"]]}
            for bar in bars
            if bar["session_date"] in index_for
        ]
        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO market_data
                    (ticker, ts, session_date, bar_index, open, high, low, close, volume)
                VALUES (:ticker, :ts, :session_date, :bar_index, :open, :high, :low, :close, :volume)
                """,
                rows,
            )
            news_rows = list(news)
            if news_rows:
                conn.executemany(
                    """
                    INSERT INTO news (ticker, headline, source, sentiment, ts, bar_index)
                    VALUES (:ticker, :headline, :source, :sentiment, :ts, :bar_index)
                    """,
                    news_rows,
                )
        return len(sessions)

    def upsert_bars(self, bars: Iterable[dict]) -> None:
        """Insert bars, updating the row when the (ticker, ts) already exists."""
        rows = list(bars)
        if not rows:
            return
        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO market_data
                    (ticker, ts, session_date, bar_index, open, high, low, close, volume)
                VALUES (:ticker, :ts, :session_date, :bar_index, :open, :high, :low, :close, :volume)
                ON CONFLICT(ticker, ts) DO UPDATE SET
                    session_date = excluded.session_date,
                    bar_index = excluded.bar_index,
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
                """,
                rows,
            )

    def delete_session(self, session_date: str) -> int:
        """Remove one session's bars and headlines (used when leaving live mode)."""
        with self.db.transaction() as conn:
            indices = [
                row["bar_index"]
                for row in conn.execute(
                    "SELECT DISTINCT bar_index FROM market_data WHERE session_date = ?",
                    (session_date,),
                )
            ]
            conn.execute("DELETE FROM market_data WHERE session_date = ?", (session_date,))
            for index in indices:
                conn.execute("DELETE FROM news WHERE bar_index = ?", (index,))
        return len(indices)

    def replace_market_data(self, bars: list[dict], news: list[dict]) -> int:
        """Replace the whole dataset, honouring each bar's existing bar_index."""
        bar_rows = list(bars)
        news_rows = list(news)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM news")
            conn.execute("DELETE FROM market_data")
            conn.executemany(
                """
                INSERT INTO market_data
                    (ticker, ts, session_date, bar_index, open, high, low, close, volume)
                VALUES (:ticker, :ts, :session_date, :bar_index, :open, :high, :low, :close, :volume)
                """,
                bar_rows,
            )
            if news_rows:
                conn.executemany(
                    """
                    INSERT INTO news (ticker, headline, source, sentiment, ts, bar_index)
                    VALUES (:ticker, :headline, :source, :sentiment, :ts, :bar_index)
                    """,
                    news_rows,
                )
        return len({bar["session_date"] for bar in bar_rows})

    def timeline(self) -> list[dict]:
        rows = self.db.query(
            "SELECT DISTINCT bar_index, ts, session_date FROM market_data ORDER BY bar_index"
        )
        return rows

    def last_bar_index(self) -> int:
        row = self.db.query_one("SELECT COALESCE(MAX(bar_index), -1) AS idx FROM market_data")
        return int(row["idx"]) if row else -1

    def bars_at(self, bar_index: int) -> list[dict]:
        return self.db.query(
            "SELECT ticker, ts, open, high, low, close, volume FROM market_data WHERE bar_index = ?",
            (bar_index,),
        )

    def bar(self, ticker: str, bar_index: int) -> dict | None:
        return self.db.query_one(
            "SELECT * FROM market_data WHERE ticker = ? AND bar_index = ?",
            (ticker, bar_index),
        )

    def bars_for(self, ticker: str, up_to: int, limit: int = 200) -> list[dict]:
        rows = self.db.query(
            "SELECT ts, session_date, bar_index, open, high, low, close, volume"
            " FROM market_data WHERE ticker = ? AND bar_index <= ?"
            " ORDER BY bar_index DESC LIMIT ?",
            (ticker, up_to, limit),
        )
        return list(reversed(rows))

    def bars_range(self, ticker: str, from_bar: int, to_bar: int) -> list[dict]:
        return self.db.query(
            "SELECT * FROM market_data WHERE ticker = ? AND bar_index BETWEEN ? AND ? ORDER BY bar_index",
            (ticker, from_bar, to_bar),
        )

    def prices_at(self, bar_index: int) -> dict[str, float]:
        rows = self.db.query(
            "SELECT ticker, close FROM market_data WHERE bar_index = ?", (bar_index,)
        )
        return {row["ticker"]: row["close"] for row in rows}

    def opens_at(self, bar_index: int) -> dict[str, float]:
        rows = self.db.query(
            "SELECT ticker, open FROM market_data WHERE bar_index = ?", (bar_index,)
        )
        return {row["ticker"]: row["open"] for row in rows}

    def session_open_prices(self, session_date: str) -> dict[str, float]:
        rows = self.db.query(
            """
            SELECT m.ticker, m.open FROM market_data m
            JOIN (SELECT ticker, MIN(bar_index) AS b FROM market_data WHERE session_date = ? GROUP BY ticker) x
              ON x.ticker = m.ticker AND x.b = m.bar_index
            """,
            (session_date,),
        )
        return {row["ticker"]: row["open"] for row in rows}

    def news_up_to(self, bar_index: int, ticker: str | None = None, limit: int = 20) -> list[dict]:
        if ticker:
            return self.db.query(
                "SELECT * FROM news WHERE bar_index <= ? AND (ticker = ? OR ticker IS NULL)"
                " ORDER BY bar_index DESC, id DESC LIMIT ?",
                (bar_index, ticker, limit),
            )
        return self.db.query(
            "SELECT * FROM news WHERE bar_index <= ? ORDER BY bar_index DESC, id DESC LIMIT ?",
            (bar_index, limit),
        )

    # -------------------------------------------------------------- snapshots
    def insert_snapshot(
        self, portfolio_id: int, ts: str, bar_index: int, cash: float, positions_value: float, equity: float
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_snapshots (portfolio_id, ts, bar_index, cash, positions_value, equity)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (portfolio_id, ts, bar_index, round_money(cash), round_money(positions_value), round_money(equity)),
            )

    def snapshots(self, portfolio_id: int, limit: int = 400) -> list[dict]:
        rows = self.db.query(
            "SELECT ts, bar_index, cash, positions_value, equity FROM portfolio_snapshots"
            " WHERE portfolio_id = ? ORDER BY bar_index DESC LIMIT ?",
            (portfolio_id, limit),
        )
        return list(reversed(rows))

    def latest_snapshot(self, portfolio_id: int) -> dict | None:
        return self.db.query_one(
            "SELECT ts, bar_index, cash, positions_value, equity FROM portfolio_snapshots"
            " WHERE portfolio_id = ? ORDER BY bar_index DESC LIMIT 1",
            (portfolio_id,),
        )

    def trade_stats(self, portfolio_id: int) -> dict:
        row = self.db.query_one(
            """
            SELECT
                COUNT(*) AS total_trades,
                COALESCE(SUM(CASE WHEN side IN ('SELL', 'COVER') THEN 1 ELSE 0 END), 0) AS closed_trades,
                COALESCE(SUM(CASE WHEN side IN ('SELL', 'COVER') AND realized_pnl > 0 THEN 1 ELSE 0 END), 0) AS wins,
                COALESCE(SUM(realized_pnl), 0) AS realized_pnl,
                COALESCE(SUM(fees), 0) AS fees
            FROM trades WHERE portfolio_id = ?
            """,
            (portfolio_id,),
        )
        return row or {
            "total_trades": 0,
            "closed_trades": 0,
            "wins": 0,
            "realized_pnl": 0.0,
            "fees": 0.0,
        }

    # ------------------------------------------------------------- housekeeping
    def reset_trading(self) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM portfolio_snapshots")
            conn.execute("DELETE FROM trades")
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM predictions")
            conn.execute("DELETE FROM positions")

    def reset_accounts(self, settings: Settings, now: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE portfolios SET cash = ?, borrow_fees = 0",
                (settings.starting_balance,),
            )
        self.reset_trading()
