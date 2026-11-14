"""Real daily-data import, caching and daily-session behaviour."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.database.database import Database
from app.database.repositories import Repository
from app.market import yahoo_provider
from app.market.data_processor import quote_payload
from app.market.yahoo_provider import DailyDataset, fetch_daily_bars
from app.services import simulation_clock
from app.services.simulation_clock import SimulationEngine

from .conftest import make_settings

TICKERS = ("AAPL", "MSFT")


def weekdays(count: int, start: date = date(2025, 1, 2)) -> list[date]:
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def fake_series(days: int = 70) -> dict[str, dict[date, dict]]:
    dates = weekdays(days)
    series: dict[str, dict[date, dict]] = {}
    for offset, ticker in enumerate(TICKERS):
        daily: dict[date, dict] = {}
        for index, day in enumerate(dates):
            if offset == 1 and index == 10:  # simulate a one-day halt
                continue
            price = 100.0 + offset * 20 + index
            daily[day] = {
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price + 0.5,
                "volume": 1000 + index,
            }
        series[ticker] = daily
    return series


def dataset(days: int = 70) -> DailyDataset:
    series = fake_series(days)
    calendar = sorted({day for daily in series.values() for day in daily})
    bars: list[dict] = []
    last_close: dict[str, float] = {}
    for bar_index, day in enumerate(calendar):
        for ticker in TICKERS:
            daily = series[ticker].get(day)
            if daily is None:
                previous = last_close.get(ticker)
                if previous is None:
                    continue
                daily = {"open": previous, "high": previous, "low": previous, "close": previous, "volume": 0}
            last_close[ticker] = daily["close"]
            bars.append(
                {
                    "ticker": ticker,
                    "ts": f"{day.isoformat()}T16:00:00",
                    "session_date": day.isoformat(),
                    "bar_index": bar_index,
                    "open": round(daily["open"], 2),
                    "high": round(daily["high"], 2),
                    "low": round(daily["low"], 2),
                    "close": round(daily["close"], 2),
                    "volume": daily["volume"],
                }
            )
    return DailyDataset(
        bars=bars,
        tickers=TICKERS,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        last_bar_date=calendar[-1].isoformat(),
    )


def test_yahoo_fetch_aligns_calendars_and_forward_fills(monkeypatch):
    series = fake_series()
    monkeypatch.setattr(yahoo_provider, "_ticker_days", lambda ticker, *_args: series[ticker])
    result = fetch_daily_bars(TICKERS, range_="1y")

    sessions = sorted({bar["session_date"] for bar in result.bars})
    assert len(sessions) == 70
    assert result.last_bar_date == sessions[-1]
    assert all(bar["ts"].endswith("T16:00:00") for bar in result.bars)

    # The halted MSFT session is forward-filled from the prior close.
    gap_day = weekdays(70)[10].isoformat()
    msft_gap = next(
        bar for bar in result.bars if bar["ticker"] == "MSFT" and bar["session_date"] == gap_day
    )
    assert msft_gap["volume"] == 0
    assert msft_gap["open"] == msft_gap["close"]


def test_repository_merge_is_idempotent(tmp_path):
    settings = make_settings(tmp_path)
    db = Database(settings.db_path)
    repo = Repository(db)
    first = dataset(70)
    repo.replace_market_data(first.bars, [])
    assert repo.market_summary()["sessions"] == 70

    plan = repo.plan_new_sessions({bar["session_date"] for bar in first.bars})
    assert plan == []  # existing sessions never shift bar indices

    extra = dataset(71)
    plan = repo.plan_new_sessions({bar["session_date"] for bar in extra.bars})
    assert len(plan) == 1
    assert plan[0][1] == 70
    repo.append_market_data(bars=extra.bars, sessions=plan)
    assert repo.market_summary()["sessions"] == 71
    db.close()


def _engine(tmp_path, monkeypatch, fetches: list[DailyDataset]) -> SimulationEngine:
    settings = make_settings(
        tmp_path, data_source="yahoo", data_refresh_hours=24, universe=TICKERS
    )
    db = Database(settings.db_path)
    repo = Repository(db)

    def fake_fetch(*_args, **_kwargs):
        return fetches.pop(0) if fetches else dataset()

    monkeypatch.setattr(simulation_clock, "fetch_daily_bars", fake_fetch)
    engine = SimulationEngine(repo, settings)
    engine.initialize()
    return engine


def test_engine_imports_real_daily_sessions_and_caches(tmp_path, monkeypatch):
    engine = _engine(tmp_path, monkeypatch, [dataset(70)])
    assert engine.total_bars == 70
    assert engine.data_info["source"] == "yahoo"
    assert engine.data_info["label"] == "Yahoo Finance"
    assert engine.status_payload()["sim_time"].endswith("T16:00:00")

    # A restart within the refresh window reuses the cache instead of refetching.
    monkeypatch.setattr(
        simulation_clock,
        "fetch_daily_bars",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not refetch")),
    )
    engine.shutdown()
    again = SimulationEngine(engine.repo, engine.settings)
    again.initialize()
    assert again.total_bars == 70
    assert again.data_info["source"] == "yahoo"
    again.shutdown()


def test_daily_refresh_appends_new_sessions(tmp_path, monkeypatch):
    engine = _engine(tmp_path, monkeypatch, [dataset(70)])
    old_total = engine.total_bars
    engine.play()

    extended = dataset(71)
    monkeypatch.setattr(simulation_clock, "fetch_daily_bars", lambda *_a, **_k: extended)
    engine.repo.save_data_cache(
        source="yahoo",
        interval="1d",
        fetched_at="2020-01-01T00:00:00+00:00",  # stale on purpose
        last_bar_date=engine.data_info["last_bar_date"],
        tickers=engine.settings.universe,
        bar_count=engine.total_bars,
        history_range=engine.settings.history_range,
    )
    engine.refresh_data_if_due()

    assert engine.total_bars == old_total + 1
    assert engine.repo.market_summary()["sessions"] == old_total + 1
    assert engine.data_info["bar_count"] == len(extended.bars)
    engine.shutdown()


def test_yahoo_failure_falls_back_to_sample_data(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, data_source="yahoo")
    db = Database(settings.db_path)
    repo = Repository(db)
    monkeypatch.setattr(
        simulation_clock,
        "fetch_daily_bars",
        lambda *_a, **_k: (_ for _ in ()).throw(yahoo_provider.MarketDataError("offline")),
    )
    engine = SimulationEngine(repo, settings)
    engine.initialize()
    assert engine.data_info["source"] == "synthetic"
    assert engine.data_info["label"] == "Sample data"
    assert engine.total_bars == settings.replay_sessions * settings.bars_per_session
    engine.shutdown()
    db.close()


def test_daily_quote_change_is_measured_from_previous_close():
    bar = {
        "ts": "2026-01-05T16:00:00",
        "open": 101.0,
        "high": 106.0,
        "low": 100.0,
        "close": 105.0,
        "volume": 123,
    }
    payload = quote_payload("AAPL", bar, 100.0)
    assert payload["change"] == 5.0
    assert payload["change_pct"] == 5.0
    assert payload["previous_close"] == 100.0
