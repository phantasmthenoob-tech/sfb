"""HTTP and websocket contract tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import cors_origins, create_app

from .conftest import make_settings


@pytest.fixture
def client(tmp_path):
    settings = make_settings(tmp_path, replay_sessions=2, bars_per_session=30, agent_decision_every=5)
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_simulation_status(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["simulation"]["total_bars"] == 60
    assert body["settings"]["starting_balance"] == 10000.0

    status = client.get("/api/simulation/status").json()
    assert status["status"] in {"paused", "running"}


def test_leaderboard_starts_with_four_equal_accounts(client):
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 4
    assert [entry["rank"] for entry in entries] == [1, 2, 3, 4]
    assert all(entry["starting_balance"] == 10000.0 for entry in entries)
    assert all(entry["equity"] == 10000.0 for entry in entries)
    kinds = {entry["kind"] for entry in entries}
    assert kinds == {"agent", "manual"}


def test_universe_has_twelve_sectors_and_separate_etfs(client):
    meta = client.get("/api/market/universe").json()
    assert len(meta["stocks"]) == 120
    assert len(meta["etfs"]) == 8
    assert len(meta["sectors"]) == 13
    assert all(item["kind"] == "stock" for item in meta["stocks"])
    assert all(item["kind"] == "etf" for item in meta["etfs"])
    assert "Political" not in meta["sectors"]
    assert "AI adoption" in meta["exposures"]
    assert "China exposure" in meta["exposures"]


def test_market_endpoints_payloads(client):
    overview = client.get("/api/market/overview").json()
    assert {quote["ticker"] for quote in overview["quotes"]} == set(overview["universe"])
    assert len(overview["indices"]) == 2
    assert isinstance(overview["forecasts"], list)
    assert overview["forecast_meta"]["news_lookback_sessions"] == 5

    refreshed = client.post("/api/market/forecasts/refresh")
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert isinstance(refreshed_body["forecasts"], list)
    assert refreshed_body["forecast_meta"]["forecast_horizon_sessions"] == 5

    scorecard = client.get("/api/market/forecasts/scorecard")
    assert scorecard.status_code == 200
    scorecard_body = scorecard.json()
    assert scorecard_body["horizon_sessions"] == 5
    assert len(scorecard_body["agents"]) == 3

    quote = client.get("/api/market/quote/AAPL").json()
    assert quote["price"] > 0
    assert "change_pct" in quote

    history = client.get("/api/market/history/AAPL?limit=10").json()
    assert 1 <= len(history["bars"]) <= 10
    assert history["bars"][-1]["bar_index"] == 0

    news = client.get("/api/market/news/ALL").json()
    assert isinstance(news["news"], list)

    sectors = client.get("/api/market/sectors")
    assert sectors.status_code == 200
    assert sectors.json()["sectors"]

    correlations = client.get("/api/market/correlations?window=20")
    assert correlations.status_code == 200
    assert correlations.json()["window_sessions"] == 20

    assert client.get("/api/market/quote/NOPE").status_code == 404


def test_agents_endpoint_exposes_three_independent_portfolios(client):
    agents = client.get("/api/agents").json()["agents"]
    assert len(agents) == 3
    assert {agent["model_type"] for agent in agents} == {"price", "news", "combined"}
    portfolio_ids = {agent["portfolio"]["id"] for agent in agents}
    assert len(portfolio_ids) == 3
    for agent in agents:
        assert agent["portfolio"]["starting_balance"] == 10000.0


def test_manual_order_queues_then_fills_on_next_tick(client):
    engine = client.app.state.engine
    engine.play()
    ticker = "AAPL"
    response = client.post(
        "/api/orders", json={"ticker": ticker, "side": "BUY", "quantity": 3}
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "PENDING"
    assert payload["order"]["status"] == "PENDING"

    orders = client.get("/api/orders").json()["orders"]
    assert orders[0]["status"] == "PENDING"

    engine.tick()
    engine.pause()

    orders = client.get("/api/orders").json()["orders"]
    assert orders[0]["status"] == "FILLED"
    assert orders[0]["fill_price"] > 0
    trades = client.get("/api/trades").json()["trades"]
    assert trades[0]["side"] == "BUY"

    manual = client.get("/api/portfolios/manual").json()
    assert manual["positions"][0]["ticker"] == ticker
    assert manual["positions"][0]["quantity"] == 3
    assert manual["cash"] < 10000.0


def test_ai_portfolios_reject_manual_orders(client):
    agents = client.get("/api/agents").json()["agents"]
    agent_portfolio_id = agents[0]["portfolio"]["id"]
    response = client.post(
        "/api/orders",
        json={
            "ticker": "AAPL",
            "side": "BUY",
            "quantity": 1,
            "portfolio_id": agent_portfolio_id,
        },
    )
    assert response.status_code == 400


def test_invalid_order_returns_reason(client):
    response = client.post(
        "/api/orders", json={"ticker": "WOOF", "side": "BUY", "quantity": 1}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["reason"] == "unknown_ticker"


def test_speed_control_validation(client):
    assert client.post("/api/simulation/speed", json={"speed": 5}).status_code == 200
    assert client.post("/api/simulation/speed", json={"speed": 7}).status_code == 400


def test_replay_range_endpoint_and_validation(client):
    response = client.post("/api/simulation/range", json={"preset": "1w"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["simulation"]["replay_preset"] == "1w"
    assert payload["simulation"]["range_bars"] > 0
    assert payload["snapshot"]["data"]["recording"]["enabled"] is True

    bad = client.post("/api/simulation/range", json={"preset": "nope"})
    assert bad.status_code == 400


def test_simulation_reset_restores_accounts(client):
    engine = client.app.state.engine
    engine.play()
    client.post("/api/orders", json={"ticker": "MSFT", "side": "BUY", "quantity": 2})
    engine.tick()
    engine.pause()

    client.post("/api/simulation/reset")
    manual = client.get("/api/portfolios/manual").json()
    assert manual["cash"] == 10000.0
    assert manual["positions"] == []
    assert client.get("/api/trades").json()["trades"] == []


def test_websocket_sends_snapshot(client):
    with client.websocket_connect("/ws/market") as websocket:
        payload = websocket.receive_json()
    assert payload["type"] == "snapshot"
    assert len(payload["leaderboard"]) == 4
    assert payload["simulation"]["total_bars"] == 60
    assert payload["manual"]["id"] > 0


def test_cors_allows_configured_static_origins(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        " https://dashboard.example.com/ , https://preview.example.com ",
    )
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        preflight = client.options(
            "/api/leaderboard",
            headers={
                "Origin": "https://dashboard.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 200
        assert (
            preflight.headers["access-control-allow-origin"]
            == "https://dashboard.example.com"
        )

        allowed = client.get(
            "/api/leaderboard", headers={"Origin": "https://preview.example.com"}
        )
        assert (
            allowed.headers["access-control-allow-origin"]
            == "https://preview.example.com"
        )

        blocked = client.get(
            "/api/leaderboard", headers={"Origin": "https://evil.example.com"}
        )
        assert "access-control-allow-origin" not in blocked.headers


def test_cors_origins_default_to_wildcard(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert cors_origins() == ["*"]

    monkeypatch.setenv("CORS_ORIGINS", " , ")
    assert cors_origins() == ["*"]
