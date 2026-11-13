"""The replay clock. Every price, news item, prediction and fill is gated by it."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import date, datetime, timezone

from ..competition.leaderboard import build_leaderboard, build_portfolio_view
from ..competition.manager import CompetitionManager
from ..config import SPEED_OPTIONS, Settings
from ..database.repositories import Repository
from ..market import data_provider
from ..market.data_processor import quote_payload
from ..market.live_provider import LiveSnapshot, fetch_live_quotes
from ..market.news_provider import generate_news, generate_news_for_dates
from ..market.yahoo_provider import DailyDataset, fetch_daily_bars, last_completed_session
from ..trading.exchange import Exchange
from ..trading.order_manager import OrderManager
from .event_manager import EventManager

logger = logging.getLogger(__name__)

STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"

MODE_REPLAY = "replay"
MODE_LIVE = "live"
MODES = (MODE_REPLAY, MODE_LIVE)


class SimulationEngine:
    def __init__(
        self, repo: Repository, settings: Settings, events: EventManager | None = None
    ) -> None:
        self.repo = repo
        self.settings = settings
        self.events = events
        self.exchange = Exchange(repo, settings)
        self.order_manager = OrderManager(repo, self.exchange, settings)
        self.competition = CompetitionManager(repo, settings, self.order_manager)

        self.timeline: list[dict] = []
        self.total_bars = 0
        self.cursor = 0
        self.speed = settings.default_speed
        self.status = STATUS_PAUSED
        self.mode = settings.default_mode if settings.default_mode in MODES else MODE_REPLAY
        self.last_prices: dict[str, float] = {}
        self.data_info: dict = {}
        self.live_info: dict = self._empty_live_info()
        self.live_quotes: dict = {}
        self._last_live_poll = 0.0
        self._last_live_decision = 0.0
        self._live_lock = threading.RLock()
        self._task: asyncio.Task | None = None
        self._shutdown = False

    def _empty_live_info(self) -> dict:
        return {
            "market_open": False,
            "last_poll": None,
            "session_date": None,
            "poll_seconds": self.settings.live_poll_seconds,
            "decision_seconds": self.settings.live_decision_seconds,
            "last_decision": None,
            "error": None,
        }

    # ------------------------------------------------------------- lifecycle
    def initialize(self) -> None:
        replaced = self._ensure_market_data()
        self.timeline = self.repo.timeline()
        self.total_bars = len(self.timeline)
        if not self.total_bars:
            raise RuntimeError("Replay data could not be loaded")

        now = datetime.now(timezone.utc).isoformat()
        self.repo.seed_accounts(self.settings, now)
        self.competition.load_agents()

        run = self.repo.get_simulation()
        if run and str(run.get("mode") or "").lower() in MODES:
            self.mode = str(run["mode"]).lower()

        reset = replaced or run is None or (
            self.mode == MODE_REPLAY and int(run["total_bars"]) != self.total_bars
        )
        if reset:
            self.repo.reset_accounts(self.settings, now)
            self.cursor = 0 if self.mode == MODE_REPLAY else self.total_bars - 1
            self.speed = self.settings.default_speed
            self.status = (
                STATUS_RUNNING
                if self.mode == MODE_LIVE or self.settings.autostart
                else STATUS_PAUSED
            )
            self.last_prices = self.repo.prices_at(self.cursor)
            self._take_snapshots(self.timeline[self.cursor]["ts"])
            self._persist()
            return

        self.cursor = min(int(run["cursor"]), self.total_bars - 1)
        self.speed = int(run["speed"]) if int(run["speed"]) in SPEED_OPTIONS else self.settings.default_speed
        self.status = run["status"]
        if self.mode == MODE_LIVE:
            if self.status == STATUS_COMPLETED:
                self.status = STATUS_RUNNING
            self.cursor = self.total_bars - 1
        self.last_prices = self.repo.prices_at(self.cursor)
        manual = self.repo.get_manual_portfolio()
        if manual and not self.repo.latest_snapshot(manual["id"]):
            self._take_snapshots(self.timeline[self.cursor]["ts"])

    def _ensure_market_data(self) -> bool:
        """Load cached prices or refresh them. Returns True if the dataset changed."""
        cache = self.repo.get_data_cache()
        summary = self.repo.market_summary()
        has_data = summary["bar_count"] > 0

        if self.settings.data_source != "yahoo":
            if has_data and cache and cache["source"] == "synthetic":
                self._set_data_info_from_cache(cache, summary)
                return False
            return self._seed_synthetic()

        if has_data and cache and cache["source"] == "yahoo":
            if self._cache_age_hours(cache) < self.settings.data_refresh_hours:
                self._set_data_info_from_cache(cache, summary)
                return False
            try:
                dataset = fetch_daily_bars(
                    self.settings.universe, range_=self.settings.history_range
                )
            except Exception as exc:
                logger.warning("Yahoo Finance refresh failed (%s); using cached daily bars", exc)
                self._set_data_info_from_cache(cache, summary, stale=True)
                return False
            appended = self._append_dataset(dataset)
            self._store_cache(dataset)
            self._set_data_info_from_cache(self.repo.get_data_cache(), self.repo.market_summary())
            if appended:
                logger.info("Appended %s new daily session(s) from Yahoo Finance", appended)
            return False

        # No usable daily cache yet: import real records, else fall back to samples.
        try:
            dataset = fetch_daily_bars(
                self.settings.universe, range_=self.settings.history_range
            )
        except Exception as exc:
            logger.warning("Yahoo Finance unavailable (%s); using synthetic sample data", exc)
            return self._seed_synthetic()
        self._replace_dataset(dataset)
        return True

    def _seed_synthetic(self) -> bool:
        start = date(2026, 9, 14)
        bars, window = data_provider.generate_bars(
            self.settings.universe,
            sessions=self.settings.replay_sessions,
            bars_per_session=self.settings.bars_per_session,
            seed=self.settings.seed,
            start=start,
        )
        news = generate_news(
            self.settings.universe,
            sessions=self.settings.replay_sessions,
            bars_per_session=self.settings.bars_per_session,
            seed=self.settings.seed,
            start=start,
        )
        self.repo.replace_market_data(bars, news)
        self.repo.save_data_cache(
            source="synthetic",
            interval="5m",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            last_bar_date=window.end_date,
            tickers=self.settings.universe,
            bar_count=len(bars),
        )
        self._set_data_info_from_cache(self.repo.get_data_cache(), self.repo.market_summary())
        logger.info(
            "Seeded synthetic sample replay: %s bars across %s sessions (%s -> %s)",
            len(bars),
            self.settings.replay_sessions,
            window.start_date,
            window.end_date,
        )
        return True

    def _replace_dataset(self, dataset: DailyDataset) -> None:
        dated = sorted({(bar["session_date"], bar["bar_index"]) for bar in dataset.bars})
        news = generate_news_for_dates(
            self.settings.universe,
            [(date.fromisoformat(day), index) for day, index in dated],
            seed=self.settings.seed,
        )
        self.repo.replace_market_data(dataset.bars, news)
        self._store_cache(dataset)
        self._set_data_info_from_cache(self.repo.get_data_cache(), self.repo.market_summary())
        logger.info(
            "Imported %s real daily bars (%s -> %s) from Yahoo Finance",
            len(dataset.bars),
            dated[0][0],
            dated[-1][0],
        )

    def _append_dataset(self, dataset: DailyDataset) -> int:
        sessions = self.repo.plan_new_sessions({bar["session_date"] for bar in dataset.bars})
        if not sessions:
            return 0
        news = generate_news_for_dates(
            self.settings.universe,
            [(date.fromisoformat(day), index) for day, index in sessions],
            seed=self.settings.seed,
        )
        self.repo.append_market_data(bars=dataset.bars, sessions=sessions, news=news)
        return len(sessions)

    def _store_cache(self, dataset: DailyDataset) -> None:
        summary = self.repo.market_summary()
        self.repo.save_data_cache(
            source=dataset.source,
            interval=dataset.interval,
            fetched_at=dataset.fetched_at,
            last_bar_date=dataset.last_bar_date,
            tickers=dataset.tickers,
            bar_count=summary["bar_count"],
        )

    def _set_data_info_from_cache(
        self, cache: dict | None, summary: dict, *, stale: bool = False
    ) -> None:
        if not cache:
            self.data_info = {
                "source": "unknown",
                "label": "Unknown",
                "interval": "1d",
                "bar_count": summary.get("bar_count", 0),
                "fetched_at": None,
                "last_bar_date": summary.get("end_date"),
                "refresh_hours": self.settings.data_refresh_hours,
                "note": "Market data source not recorded.",
                "stale": True,
            }
            return
        real = cache["source"] == "yahoo"
        self.data_info = {
            "source": cache["source"],
            "label": "Yahoo Finance" if real else "Sample data",
            "interval": cache["interval"],
            "bar_count": summary.get("bar_count") or cache["bar_count"],
            "fetched_at": cache["fetched_at"],
            "last_bar_date": summary.get("end_date") or cache["last_bar_date"],
            "refresh_hours": self.settings.data_refresh_hours,
            "note": (
                "Real daily closes from Yahoo Finance. Headlines are simulated."
                if real
                else "Synthetic sample prices (Yahoo Finance unavailable). Headlines are simulated."
            ),
            "stale": stale,
        }

    @staticmethod
    def _cache_age_hours(cache: dict) -> float:
        try:
            fetched = datetime.fromisoformat(cache["fetched_at"])
        except (KeyError, TypeError, ValueError):
            return float("inf")
        return (datetime.now(timezone.utc) - fetched).total_seconds() / 3600.0

    def data_payload(self) -> dict:
        if not self.data_info:
            self._set_data_info_from_cache(
                self.repo.get_data_cache(), self.repo.market_summary()
            )
        payload = dict(self.data_info)
        if self.mode == MODE_LIVE:
            payload["note"] = (
                f"Live quotes from Yahoo Finance, polled every "
                f"{int(self.settings.live_poll_seconds)}s during the US session. "
                "Headlines are simulated."
            )
            payload["live"] = dict(self.live_info)
        return payload

    def refresh_data_if_due(self) -> None:
        """Append newly completed real sessions at most once per refresh window."""
        if self.settings.data_source != "yahoo":
            return
        cache = self.repo.get_data_cache()
        if not cache or cache["source"] != "yahoo":
            return
        if self._cache_age_hours(cache) < self.settings.data_refresh_hours:
            return
        dataset = fetch_daily_bars(
            self.settings.universe, range_=self.settings.history_range
        )
        appended = self._append_dataset(dataset)
        self._store_cache(dataset)
        self._set_data_info_from_cache(self.repo.get_data_cache(), self.repo.market_summary())
        if appended:
            self._reload_timeline()
            logger.info("Market data refreshed: %s new daily session(s)", appended)
            self._publish()

    # --------------------------------------------------------------- controls
    def play(self) -> dict:
        if self.mode == MODE_REPLAY and self.status == STATUS_COMPLETED:
            self.reset()
        self.status = STATUS_RUNNING
        self._persist()
        self._publish()
        return self.status_payload()

    def pause(self) -> dict:
        if self.status == STATUS_RUNNING:
            self.status = STATUS_PAUSED
        self._persist()
        self._publish()
        return self.status_payload()

    def reset(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        self.repo.reset_accounts(self.settings, now)
        self.cursor = 0 if self.mode == MODE_REPLAY else self.total_bars - 1
        self.status = STATUS_PAUSED if self.mode == MODE_REPLAY else STATUS_RUNNING
        self.last_prices = self.repo.prices_at(self.cursor)
        self._take_snapshots(self.timeline[self.cursor]["ts"])
        self._persist()
        self._publish()
        return self.status_payload()

    def switch_mode(self, mode: str) -> dict:
        """Switch between historical replay and live quotes. Both reset trading."""
        if mode not in MODES:
            raise ValueError(f"Mode must be one of {MODES}")
        with self._live_lock:
            return self._switch_mode(mode)

    def _switch_mode(self, mode: str) -> dict:
        if mode == self.mode:
            return self.status_payload()

        now = datetime.now(timezone.utc).isoformat()
        self.repo.cancel_pending_orders("mode_switch")
        self.repo.reset_accounts(self.settings, now)
        self.mode = mode
        self.live_quotes = {}
        self._last_live_decision = 0.0

        if mode == MODE_REPLAY:
            # Drop a still-forming live session so it cannot leak into the replay.
            if self.timeline:
                last_session = self.timeline[-1]["session_date"]
                if last_session > last_completed_session().isoformat():
                    self.repo.delete_session(last_session)
                    self._reload_timeline()
            self.cursor = 0
            self.status = STATUS_PAUSED
            self.last_prices = self.repo.prices_at(0)
            self.live_info = self._empty_live_info()
            self._take_snapshots(self.timeline[0]["ts"])
        else:
            self._reload_timeline()
            self.cursor = self.total_bars - 1
            self.status = STATUS_RUNNING
            self.last_prices = self.repo.prices_at(self.cursor)
            self.live_info = self._empty_live_info()
            self._take_snapshots(self.timeline[self.cursor]["ts"])
            try:
                self.live_tick()
            except Exception:  # pragma: no cover - network failures are non-fatal
                logger.warning("Initial live poll failed", exc_info=True)

        self._persist()
        self._publish()
        return self.status_payload()

    def set_speed(self, speed: int) -> dict:
        if speed not in SPEED_OPTIONS:
            raise ValueError(f"Speed must be one of {SPEED_OPTIONS}")
        self.speed = speed
        self._persist()
        return self.status_payload()

    @property
    def interval_seconds(self) -> float:
        return max(0.01, self.settings.bar_interval_seconds / max(1, self.speed))

    # ------------------------------------------------------------------- tick
    def tick(self) -> bool:
        """Advance exactly one replay bar. Returns True when time moved."""
        if self.mode != MODE_REPLAY or self.status != STATUS_RUNNING:
            return False
        if self.cursor >= self.total_bars - 1:
            self._complete()
            return False

        next_index = self.cursor + 1
        bar = self.timeline[next_index]
        sim_time = bar["ts"]
        opens = self.repo.opens_at(next_index)

        # Fills use the next bar's open, never the price the decision was based on.
        self.order_manager.fill_pending(opens, sim_time)

        previous_session = self.timeline[self.cursor]["session_date"]
        self.cursor = next_index
        self.last_prices = self.repo.prices_at(next_index)

        if bar["session_date"] != previous_session:
            for portfolio in self.repo.list_portfolios():
                self.exchange.accrue_borrow_fees(portfolio["id"], self.last_prices)

        if (
            next_index % self.settings.agent_decision_every == 0
            and next_index < self.total_bars - 1
        ):
            self.competition.run_decisions(
                bar_index=next_index, sim_time=sim_time, prices=self.last_prices
            )

        self._take_snapshots(sim_time)
        self._persist()
        if next_index >= self.total_bars - 1:
            self._complete()
        return True

    # ------------------------------------------------------------------- live
    def live_tick(self) -> bool:
        """Poll real quotes, update today's live bar and mark the portfolios."""
        if self.mode != MODE_LIVE:
            return False
        with self._live_lock:
            if self.mode != MODE_LIVE:
                return False
            return self._live_tick()

    def _live_tick(self) -> bool:
        try:
            snapshot: LiveSnapshot = fetch_live_quotes(self.settings.universe)
        except Exception as exc:
            self.live_info.update(
                market_open=False,
                last_poll=datetime.now(timezone.utc).isoformat(),
                error=str(exc),
            )
            logger.info("Live poll failed: %s", exc)
            self._last_live_poll = time.monotonic()
            self._persist()
            return False

        self.live_quotes = snapshot.quotes
        self.live_info.update(
            market_open=snapshot.market_open,
            last_poll=snapshot.fetched_at,
            session_date=snapshot.session_date,
            error=(
                f"No quote for {', '.join(sorted(snapshot.errors))}"
                if snapshot.errors
                else None
            ),
        )

        if snapshot.market_open and snapshot.session_date:
            created = self._ensure_live_session(snapshot)
            prices = {
                ticker: quote.price
                for ticker, quote in snapshot.quotes.items()
                if ticker in self.settings.universe
            }
            if prices:
                self.last_prices = {**self.last_prices, **prices}
            sim_time = self.timeline[self.cursor]["ts"]
            if prices:
                self.order_manager.fill_pending(prices, sim_time)
            if prices and (
                created
                or time.monotonic() - self._last_live_decision
                >= self.settings.live_decision_seconds
            ):
                self._last_live_decision = time.monotonic()
                self.competition.run_decisions(
                    bar_index=self.cursor,
                    sim_time=sim_time,
                    prices=self.last_prices,
                )
                self.live_info["last_decision"] = datetime.now(timezone.utc).isoformat()
            self._take_snapshots(sim_time)

        self._last_live_poll = time.monotonic()
        self._persist()
        self._publish()
        return True

    def _ensure_live_session(self, snapshot: LiveSnapshot) -> bool:
        """Create or update one forming bar for today's session."""
        session_date = snapshot.session_date
        if not session_date:
            return False
        latest = snapshot.latest_quote_time or datetime.now(timezone.utc)
        existing = self.timeline[-1] if self.timeline else None

        if existing and existing["session_date"] == session_date:
            index = int(existing["bar_index"])
            ts = existing["ts"]
            bars = []
            for ticker in self.settings.universe:
                quote = snapshot.quotes.get(ticker)
                if quote is None:
                    continue
                current = self.repo.bar(ticker, index)
                open_price = (
                    (current["open"] if current else None)
                    or quote.day_open
                    or quote.price
                )
                high = max(
                    value
                    for value in (
                        quote.day_high or quote.price,
                        quote.price,
                        current["high"] if current else quote.price,
                    )
                )
                low = min(
                    value
                    for value in (
                        quote.day_low or quote.price,
                        quote.price,
                        current["low"] if current else quote.price,
                    )
                )
                bars.append(
                    {
                        "ticker": ticker,
                        "ts": ts,
                        "session_date": session_date,
                        "bar_index": index,
                        "open": round(float(open_price), 2),
                        "high": round(float(high), 2),
                        "low": round(float(low), 2),
                        "close": quote.price,
                        "volume": quote.volume,
                    }
                )
            self.repo.upsert_bars(bars)
            self._reload_timeline()
            return False

        index = self.repo.last_bar_index() + 1
        ts = latest.strftime("%Y-%m-%dT%H:%M:%S")
        bars = []
        for ticker in self.settings.universe:
            quote = snapshot.quotes.get(ticker)
            if quote is None:
                continue
            open_price = quote.day_open or quote.price
            bars.append(
                {
                    "ticker": ticker,
                    "ts": ts,
                    "session_date": session_date,
                    "bar_index": index,
                    "open": round(float(open_price), 2),
                    "high": round(float(quote.day_high or quote.price), 2),
                    "low": round(float(quote.day_low or quote.price), 2),
                    "close": quote.price,
                    "volume": quote.volume,
                }
            )
        if not bars:
            return False

        news = generate_news_for_dates(
            self.settings.universe,
            [(date.fromisoformat(session_date), index)],
            seed=self.settings.seed,
        )
        self.repo.append_market_data(bars=bars, sessions=[(session_date, index)], news=news)
        for portfolio in self.repo.list_portfolios():
            self.exchange.accrue_borrow_fees(
                portfolio["id"], {bar["ticker"]: bar["close"] for bar in bars}
            )
        self._reload_timeline()
        self.cursor = index
        self.last_prices = {bar["ticker"]: bar["close"] for bar in bars}
        logger.info("Live session %s opened at bar %s", session_date, index)
        return True

    def _reload_timeline(self) -> None:
        self.timeline = self.repo.timeline()
        self.total_bars = len(self.timeline)
        if self.mode == MODE_LIVE:
            self.cursor = max(0, self.total_bars - 1)
        elif self.cursor >= self.total_bars:
            self.cursor = max(0, self.total_bars - 1)
        self.last_prices = self.repo.prices_at(self.cursor) or self.last_prices
        self._persist()

    def _complete(self) -> None:
        if self.mode != MODE_REPLAY or self.status == STATUS_COMPLETED:
            return
        self.status = STATUS_COMPLETED
        self.repo.cancel_pending_orders("replay_finished")
        self._persist()
        logger.info("Replay complete at bar %s/%s", self.cursor + 1, self.total_bars)

    async def run_loop(self) -> None:
        last_publish = 0.0
        last_data_check = time.monotonic()
        while not self._shutdown:
            if self.mode == MODE_LIVE:
                await asyncio.sleep(1.0)
                now = time.monotonic()
                if (
                    self.status == STATUS_RUNNING
                    and now - self._last_live_poll >= self.settings.live_poll_seconds
                ):
                    try:
                        await asyncio.to_thread(self.live_tick)
                    except Exception:  # pragma: no cover - keep the demo alive
                        logger.exception("Live tick failed")
            else:
                await asyncio.sleep(self.interval_seconds)
                if self.mode != MODE_REPLAY:
                    continue
                try:
                    advanced = self.tick()
                except Exception:  # pragma: no cover - keep the demo alive on bad data
                    logger.exception("Simulation tick failed")
                    self.status = STATUS_PAUSED
                    self._persist()
                    continue
                now = time.monotonic()
                if advanced and now - last_publish >= 0.1:
                    last_publish = now
                    self._publish()
            if time.monotonic() - last_data_check >= 900:
                last_data_check = time.monotonic()
                try:
                    await asyncio.to_thread(self.refresh_data_if_due)
                except Exception:  # pragma: no cover - network failures are non-fatal
                    logger.warning("Daily market data refresh failed", exc_info=True)

    def shutdown(self) -> None:
        self._shutdown = True
        if self._task:
            self._task.cancel()

    # --------------------------------------------------------------- payloads
    def status_payload(self) -> dict:
        if not self.timeline:
            return {
                "status": self.status,
                "mode": self.mode,
                "speed": self.speed,
                "speed_options": list(SPEED_OPTIONS),
                "progress_pct": 0.0,
            }
        bar = self.timeline[self.cursor]
        payload = {
            "status": self.status,
            "mode": self.mode,
            "speed": self.speed,
            "speed_options": list(SPEED_OPTIONS),
            "bar_index": self.cursor,
            "total_bars": self.total_bars,
            "sim_time": bar["ts"],
            "session_date": bar["session_date"],
            "start_date": self.timeline[0]["session_date"],
            "end_date": self.timeline[-1]["session_date"],
            "progress_pct": round((self.cursor + 1) / self.total_bars * 100.0, 1),
            "decision_every_bars": self.settings.agent_decision_every,
            "autostart": self.settings.autostart,
        }
        if self.mode == MODE_LIVE:
            elapsed = time.monotonic() - self._last_live_poll
            payload["live"] = {
                **self.live_info,
                "next_poll_in": max(0, round(self.settings.live_poll_seconds - elapsed, 1)),
                "reference": "Yahoo Finance",
            }
        return payload

    def reference_prices(self) -> dict[str, float]:
        """Previous session's closes (the reference for a daily move)."""
        if self.cursor > 0:
            previous = self.repo.prices_at(self.cursor - 1)
            if previous:
                return previous
        return self.repo.opens_at(self.cursor)

    def quotes_payload(self) -> list[dict]:
        if not self.timeline:
            return []
        previous = self.reference_prices()
        quotes = []
        for ticker in self.settings.universe:
            bar = self.repo.bar(ticker, self.cursor)
            if bar:
                quotes.append(quote_payload(ticker, bar, previous.get(ticker)))
        return quotes

    @staticmethod
    def forecast_meta() -> dict:
        """Describe the history windows behind every forecast."""
        return {
            "price_lookback_sessions": 20,
            "momentum_lookback_sessions": 10,
            "news_lookback_sessions": 5,
            "volatility_lookback_sessions": 20,
            "forecast_horizon_sessions": 5,
            "max_bars_loaded": 120,
            "note": "Uses only bars and headlines at or before the current simulation time.",
        }

    def refresh_forecasts(self) -> dict:
        """Run all three agents now and return fresh predictions without trading."""
        if not self.timeline:
            return {
                "forecasts": [],
                "forecast_meta": self.forecast_meta(),
                "sim_time": None,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        with self._live_lock:
            prices = {quote["ticker"]: quote["price"] for quote in self.quotes_payload()}
            prices = prices or self.last_prices
            sim_time = self.timeline[self.cursor]["ts"]
            if prices:
                self.competition.run_forecasts(
                    bar_index=self.cursor, sim_time=sim_time, prices=prices
                )
                self._publish()
        return {
            "forecasts": self.forecasts_payload(),
            "forecast_meta": self.forecast_meta(),
            "sim_time": sim_time,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def forecasts_payload(self) -> list[dict]:
        """Each AI's top five expected moves, largest first, for the dashboard."""
        if not self.timeline:
            return []
        groups: dict[int, dict] = {}
        for row in self.repo.latest_forecasts(self.cursor):
            group = groups.setdefault(
                row["agent_id"],
                {
                    "agent_id": row["agent_id"],
                    "agent_name": row.get("agent_name") or "AI",
                    "model_type": row.get("model_type") or "",
                    "calls": [],
                },
            )
            price = float(row["price"] or 0.0)
            expected = float(row["expected_pct"] or 0.0)
            group["calls"].append(
                {
                    "rank": len(group["calls"]) + 1,
                    "ticker": row["ticker"],
                    "direction": row["direction"],
                    "expected_pct": expected,
                    "price": round(price, 2),
                    "expected_usd": round(price * expected / 100.0, 2),
                    "confidence": row["confidence"],
                    "rationale": row["rationale"],
                    "sim_time": row["sim_time"],
                    "bar_index": row["bar_index"],
                }
            )
        return [groups[agent_id] for agent_id in sorted(groups)]

    def snapshot(self) -> dict:
        status = self.status_payload()
        quotes = self.quotes_payload()
        prices = {quote["ticker"]: quote["price"] for quote in quotes} or self.last_prices
        leaderboard = build_leaderboard(self.repo, prices)
        manual_row = self.repo.get_manual_portfolio()
        manual = (
            build_portfolio_view(self.repo, manual_row, prices) if manual_row else None
        )
        indices = data_provider.index_levels(
            prices, self.reference_prices(), self.settings.universe
        )
        return {
            "type": "snapshot",
            "simulation": status,
            "quotes": quotes,
            "indices": indices,
            "forecasts": self.forecasts_payload(),
            "forecast_meta": self.forecast_meta(),
            "leaderboard": leaderboard,
            "manual": manual,
            "data": self.data_payload(),
            "server_time": datetime.now(timezone.utc).isoformat(),
        }

    def _publish(self) -> None:
        if self.events:
            self.events.publish(self.snapshot())

    # ------------------------------------------------------------- persistence
    def _take_snapshots(self, sim_time: str) -> None:
        for portfolio in self.repo.list_portfolios():
            state = self.repo.load_state(portfolio["id"])
            self.repo.insert_snapshot(
                portfolio_id=portfolio["id"],
                ts=sim_time,
                bar_index=self.cursor,
                cash=state.cash,
                positions_value=state.positions_value(self.last_prices),
                equity=state.equity(self.last_prices),
            )

    def _persist(self) -> None:
        if not self.timeline:
            return
        self.repo.upsert_simulation(
            status=self.status,
            mode=self.mode,
            speed=self.speed,
            start_date=self.timeline[0]["session_date"],
            end_date=self.timeline[-1]["session_date"],
            cursor=self.cursor,
            total_bars=self.total_bars,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
