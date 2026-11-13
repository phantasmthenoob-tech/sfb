"""Agent forecasts: expected move, top five calls per AI, snapshot wiring."""
from __future__ import annotations

import pytest

from app.ai.features import expected_move_pct
from app.database.database import Database
from app.database.repositories import Repository
from app.services.simulation_clock import SimulationEngine

from .conftest import make_settings


@pytest.fixture
def engine(tmp_path):
    settings = make_settings(tmp_path, agent_decision_every=5)
    db = Database(settings.db_path)
    repo = Repository(db)
    sim = SimulationEngine(repo, settings)
    sim.initialize()
    yield sim
    sim.shutdown()
    db.close()


def bars_from(closes: list[float]) -> list[dict]:
    return [{"close": close} for close in closes]


def test_expected_move_follows_direction_and_is_bounded():
    rising = bars_from([100 + index * 0.8 for index in range(30)])
    choppy = bars_from([100 + (index % 5) * 2 for index in range(30)])

    assert expected_move_pct(rising, 0.6) > 0
    assert expected_move_pct(rising, -0.6) < 0
    assert abs(expected_move_pct(choppy, 1.0)) <= 15.0
    assert expected_move_pct([], 0.5) == 1.5


def test_agents_record_top_five_forecasts(engine):
    engine.play()
    for _ in range(21):
        engine.tick()

    groups = engine.snapshot()["forecasts"]
    assert len(groups) == 3
    assert {group["agent_name"] for group in groups} == {
        "Price AI",
        "News AI",
        "Combined AI",
    }
    assert any(len(group["calls"]) == 5 for group in groups)
    for group in groups:
        calls = group["calls"]
        assert 1 <= len(calls) <= 5
        assert [call["rank"] for call in calls] == list(range(1, len(calls) + 1))
        moves = [abs(call["expected_pct"]) for call in calls]
        assert moves == sorted(moves, reverse=True)
        for call in calls:
            assert call["ticker"] in engine.settings.universe
            assert call["bar_index"] <= engine.cursor
            assert call["price"] > 0
            assert call["expected_usd"] == pytest.approx(
                call["price"] * call["expected_pct"] / 100.0, abs=0.01
            )


def test_manual_refresh_records_forecasts_without_orders(engine):
    engine.play()
    for _ in range(21):
        engine.tick()
    engine.pause()

    orders_before = len(engine.repo.list_orders(limit=1000))
    result = engine.refresh_forecasts()

    assert len(result["forecasts"]) == 3
    assert result["forecast_meta"]["news_lookback_sessions"] == 5
    assert result["forecast_meta"]["price_lookback_sessions"] == 20
    assert all(1 <= len(group["calls"]) <= 5 for group in result["forecasts"])
    assert len(engine.repo.list_orders(limit=1000)) == orders_before


def test_latest_prediction_per_agent_is_used(engine):
    engine.play()
    for _ in range(21):
        engine.tick()
    first = {row["agent_id"]: row["id"] for row in engine.repo.latest_predictions(engine.cursor)}

    for _ in range(2):
        engine.tick()
    latest = engine.repo.latest_predictions(engine.cursor)

    assert len(latest) == 3
    assert {row["agent_id"] for row in latest} == set(first)
    assert all(row["id"] >= first[row["agent_id"]] for row in latest)
    assert all(row["bar_index"] <= engine.cursor for row in latest)
