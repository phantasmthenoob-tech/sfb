"""Replay clock behaviour: next-bar fills, gated data, and agent competition."""
from __future__ import annotations

import pytest

from app.competition.leaderboard import build_leaderboard
from app.database.database import Database
from app.database.repositories import Repository
from app.services.simulation_clock import SimulationEngine

from .conftest import make_settings


@pytest.fixture
def engine(tmp_path):
    settings = make_settings(tmp_path)
    db = Database(settings.db_path)
    repo = Repository(db)
    sim = SimulationEngine(repo, settings)
    sim.initialize()
    yield sim
    sim.shutdown()
    db.close()


def test_self_keepalive_url_resolution(engine, monkeypatch):
    monkeypatch.delenv("KEEPALIVE_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    assert engine._keepalive_url() is None

    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://demo.onrender.com/")
    assert engine._keepalive_url() == "https://demo.onrender.com/api/health"

    monkeypatch.setenv("KEEPALIVE_URL", "https://monitor.example.com/ping")
    assert engine._keepalive_url() == "https://monitor.example.com/ping"


def test_market_orders_fill_at_next_bar_open(engine):
    repo = engine.repo
    engine.play()
    manual = repo.get_manual_portfolio()
    next_open = repo.opens_at(1)["AAPL"]

    engine.order_manager.submit(
        portfolio_id=manual["id"],
        ticker="AAPL",
        side="BUY",
        quantity=5,
        source="manual",
        sim_time=engine.timeline[0]["ts"],
        submitted_at=engine.timeline[0]["ts"],
    )
    assert engine.tick() is True

    orders = repo.list_orders(manual["id"])
    assert orders[0]["status"] == "FILLED"
    assert orders[0]["fill_price"] == pytest.approx(next_open)
    trades = repo.list_trades(manual["id"])
    assert trades[0]["price"] == pytest.approx(next_open)
    state = repo.load_state(manual["id"])
    assert state.holdings["AAPL"].quantity == 5
    assert state.cash < engine.settings.starting_balance


def test_data_is_gated_by_the_clock(engine):
    repo = engine.repo
    total_bars = engine.total_bars
    assert total_bars == engine.settings.replay_sessions * engine.settings.bars_per_session

    engine.play()
    engine.tick()
    engine.tick()
    bars = repo.bars_for("AAPL", up_to=engine.cursor, limit=500)
    assert len(bars) == engine.cursor + 1
    assert all(bar["bar_index"] <= engine.cursor for bar in bars)
    # News is only visible once its bar has been reached.
    news = repo.news_up_to(engine.cursor)
    assert all(item["bar_index"] <= engine.cursor for item in news)
    assert engine.status_payload()["sim_time"] == engine.timeline[engine.cursor]["ts"]


def test_pause_blocks_time_and_reset_restores_capital(engine):
    engine.play()
    engine.tick()
    engine.pause()
    cursor = engine.cursor
    assert engine.tick() is False
    assert engine.cursor == cursor

    engine.reset()
    assert engine.cursor == 0
    assert engine.status == "paused"
    manual = engine.repo.get_manual_portfolio()
    assert manual["cash"] == pytest.approx(engine.settings.starting_balance)
    assert engine.repo.list_trades(manual["id"]) == []
    assert engine.repo.list_orders(manual["id"]) == []


def test_borrow_fees_accrue_when_a_new_session_starts(engine):
    repo = engine.repo
    engine.play()
    manual = repo.get_manual_portfolio()
    engine.order_manager.submit(
        portfolio_id=manual["id"],
        ticker="AAPL",
        side="SHORT",
        quantity=5,
        source="manual",
        sim_time=engine.timeline[0]["ts"],
        submitted_at=engine.timeline[0]["ts"],
    )
    # Advance to the first bar of the second replay session.
    while engine.cursor < engine.settings.bars_per_session:
        assert engine.tick() is True
    portfolio = repo.get_portfolio(manual["id"])
    assert portfolio["borrow_fees"] > 0
    assert repo.list_trades(manual["id"])[0]["side"] == "SHORT"


def test_agents_compete_with_identical_starting_capital(tmp_path):
    settings = make_settings(
        tmp_path,
        replay_sessions=3,
        bars_per_session=40,
        agent_decision_every=5,
    )
    db = Database(settings.db_path)
    repo = Repository(db)
    engine = SimulationEngine(repo, settings)
    engine.initialize()
    strategies = {agent.model_type: agent for agent in engine.competition.agents}
    assert strategies["price"].entry_threshold == pytest.approx(0.45)
    assert strategies["news"].entry_threshold == pytest.approx(0.35)
    assert strategies["combined"].entry_threshold == pytest.approx(0.45)
    assert not any(agent.allow_short for agent in strategies.values())
    assert len(settings.stock_universe) == 120
    assert "SPY" in settings.etf_universe
    assert "SPY" not in settings.stock_universe
    engine.play()
    while engine.tick():
        pass
    assert engine.status == "completed"

    leaderboard = build_leaderboard(repo, engine.last_prices)
    assert len(leaderboard) == 4  # three AI agents plus the manual portfolio
    agent_rows = [row for row in leaderboard if row["kind"] == "agent"]
    assert {row["model_type"] for row in agent_rows} == {"price", "news", "combined"}
    for row in agent_rows:
        assert row["starting_balance"] == pytest.approx(10000.0)
        assert row["total_trades"] > 0, f"{row['name']} never traded"
        assert row["max_drawdown_pct"] >= 0
    # Rankings are ordered by total return.
    returns = [row["total_return_pct"] for row in leaderboard]
    assert returns == sorted(returns, reverse=True)
    engine.shutdown()
    db.close()


def test_replay_range_presets_limit_the_clock_and_persist(tmp_path):
    settings = make_settings(
        tmp_path,
        replay_sessions=10,
        bars_per_session=12,
        agent_decision_every=50,
    )
    db = Database(settings.db_path)
    repo = Repository(db)
    engine = SimulationEngine(repo, settings)
    engine.initialize()
    try:
        engine.set_replay_range("1w")
        status = engine.status_payload()
        assert status["replay_preset"] == "1w"
        assert 0 < status["range_start_bar"] < status["range_end_bar"]
        assert status["range_bars"] < engine.total_bars
        assert engine.cursor == status["range_start_bar"]
        assert status["progress_pct"] > 0
        assert status["start_date"] < status["end_date"]

        engine.play()
        while engine.tick():
            pass
        assert engine.status == "completed"
        assert engine.cursor == status["range_end_bar"]

        engine.reset()
        assert engine.cursor == status["range_start_bar"]
        manual = repo.get_manual_portfolio()
        assert manual["cash"] == pytest.approx(settings.starting_balance)

        engine.shutdown()
        again = SimulationEngine(repo, settings)
        again.initialize()
        assert again.status_payload()["replay_preset"] == "1w"
        assert again.status_payload()["range_start_bar"] == status["range_start_bar"]
        again.shutdown()
    finally:
        engine.shutdown()
        db.close()


def test_replay_range_rejects_unknown_presets(engine):
    with pytest.raises(ValueError):
        engine.set_replay_range("decade")


def test_finished_replay_has_no_dangling_orders_and_can_restart(engine):
    engine.play()
    while engine.tick():
        pass
    assert engine.status == "completed"
    assert engine.repo.list_pending_orders() == []

    engine.play()  # starting a completed replay begins a fresh one
    assert engine.status == "running"
    assert engine.cursor == 0
    manual = engine.repo.get_manual_portfolio()
    assert manual["cash"] == pytest.approx(engine.settings.starting_balance)
