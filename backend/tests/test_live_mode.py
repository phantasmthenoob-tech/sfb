"""Live mode: real quote parsing, market-hours gating and next-quote fills."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.database.database import Database
from app.database.repositories import Repository
from app.market.live_provider import LiveQuote, LiveSnapshot, market_hours_open, parse_quote
from app.services import simulation_clock
from app.services.simulation_clock import SimulationEngine

from .conftest import make_settings

NEW_YORK = ZoneInfo("America/New_York")


@pytest.fixture
def engine(tmp_path):
    settings = make_settings(tmp_path, universe=("AAPL", "MSFT"))
    db = Database(settings.db_path)
    repo = Repository(db)
    sim = SimulationEngine(repo, settings)
    sim.initialize()
    yield sim
    sim.shutdown()
    db.close()


def live_quote(ticker: str, price: float, previous: float = 100.0) -> LiveQuote:
    return LiveQuote(
        ticker=ticker,
        price=price,
        previous_close=previous,
        day_open=100.0,
        day_high=max(price, 101.0),
        day_low=min(price, 99.0),
        volume=1_000_000,
        market_time=datetime(2026, 9, 16, 10, 30, tzinfo=NEW_YORK),
    )


def fake_snapshot(*, market_open: bool = True, price: float = 101.0) -> LiveSnapshot:
    return LiveSnapshot(
        quotes={"AAPL": live_quote("AAPL", price), "MSFT": live_quote("MSFT", price + 10)},
        fetched_at=datetime(2026, 9, 16, 14, 30, tzinfo=NEW_YORK).isoformat(),
        market_open=market_open,
        session_date="2026-09-16",
        latest_quote_time=datetime(2026, 9, 16, 10, 30, tzinfo=NEW_YORK),
    )


def test_parse_quote_reads_latest_price_and_previous_close():
    result = {
        "meta": {
            "regularMarketPrice": 355.63,
            "chartPreviousClose": 348.51,
            "regularMarketTime": 1794430801,
            "regularMarketDayHigh": 355.9,
            "regularMarketDayLow": 349.33,
            "regularMarketOpen": 350.0,
        },
        "timestamp": [1794427200, 1794430800],
        "indicators": {
            "quote": [
                {
                    "open": [349.9, 350.1],
                    "high": [355.9, 355.8],
                    "low": [349.3, 350.0],
                    "close": [355.5, 355.63],
                    "volume": [100, 200],
                }
            ]
        },
    }
    quote = parse_quote("AAPL", result)
    assert quote.price == 355.63
    assert quote.previous_close == 348.51
    assert quote.day_open == 350.0
    assert quote.day_high == 355.9
    assert quote.volume == 300


def test_market_hours_follow_new_york_weekdays():
    assert market_hours_open(datetime(2026, 9, 15, 10, 0, tzinfo=NEW_YORK)) is True
    assert market_hours_open(datetime(2026, 9, 15, 8, 0, tzinfo=NEW_YORK)) is False
    assert market_hours_open(datetime(2026, 9, 15, 16, 30, tzinfo=NEW_YORK)) is False
    assert market_hours_open(datetime(2026, 9, 19, 12, 0, tzinfo=NEW_YORK)) is False


def test_switch_to_live_adds_todays_bar_and_uses_real_quotes(engine, monkeypatch):
    monkeypatch.setattr(simulation_clock, "fetch_live_quotes", lambda *_a, **_k: fake_snapshot())
    engine.switch_mode("live")

    assert engine.mode == "live"
    assert engine.timeline[-1]["session_date"] == "2026-09-16"
    assert engine.repo.bar("AAPL", engine.cursor)["close"] == 101.0
    quotes = {quote["ticker"]: quote for quote in engine.quotes_payload()}
    assert quotes["AAPL"]["price"] == 101.0
    assert quotes["AAPL"]["previous_close"] == engine.repo.prices_at(engine.cursor - 1)["AAPL"]
    assert engine.status_payload()["live"]["market_open"] is True


def test_live_orders_fill_on_the_next_poll(engine, monkeypatch):
    monkeypatch.setattr(simulation_clock, "fetch_live_quotes", lambda *_a, **_k: fake_snapshot())
    engine.switch_mode("live")
    manual = engine.repo.get_manual_portfolio()
    engine.order_manager.submit(
        portfolio_id=manual["id"],
        ticker="AAPL",
        side="BUY",
        quantity=3,
        source="manual",
        sim_time=engine.timeline[engine.cursor]["ts"],
        submitted_at=engine.timeline[engine.cursor]["ts"],
    )

    monkeypatch.setattr(
        simulation_clock,
        "fetch_live_quotes",
        lambda *_a, **_k: fake_snapshot(price=104.0),
    )
    engine.live_tick()

    order = engine.repo.list_orders(manual["id"])[0]
    assert order["status"] == "FILLED"
    assert order["fill_price"] == pytest.approx(104.0)
    assert engine.repo.load_state(manual["id"]).holdings["AAPL"].quantity == 3


def test_live_tick_outside_hours_does_not_create_a_partial_bar(engine, monkeypatch):
    monkeypatch.setattr(
        simulation_clock,
        "fetch_live_quotes",
        lambda *_a, **_k: fake_snapshot(market_open=False),
    )
    before = engine.total_bars
    engine.switch_mode("live")

    assert engine.mode == "live"
    assert engine.total_bars == before
    assert engine.status_payload()["live"]["market_open"] is False


def test_switching_back_to_replay_drops_the_forming_session(engine, monkeypatch):
    monkeypatch.setattr(simulation_clock, "fetch_live_quotes", lambda *_a, **_k: fake_snapshot())
    monkeypatch.setattr(
        simulation_clock, "last_completed_session", lambda: date(2026, 9, 15)
    )
    engine.switch_mode("live")
    assert engine.repo.market_summary()["end_date"] == "2026-09-16"

    engine.switch_mode("replay")

    assert engine.mode == "replay"
    assert engine.repo.market_summary()["end_date"] != "2026-09-16"
    assert engine.cursor == 0
