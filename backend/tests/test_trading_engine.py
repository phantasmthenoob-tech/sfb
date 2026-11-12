"""Accounting and risk-rule tests for the paper-trading engine."""
from __future__ import annotations

import pytest

from app.competition.metrics import max_drawdown_pct, win_rate_pct
from app.trading.accounting import round_money
from app.trading.exchange import Exchange
from app.trading.order_manager import OrderManager
from app.trading.risk_limits import OrderRejected

SIM_TIME = "2026-09-14T09:35:00"


def submit_and_fill(repo, settings, side: str, quantity: int, price: float, ticker: str = "AAPL"):
    manual = repo.get_manual_portfolio()
    exchange = Exchange(repo, settings)
    manager = OrderManager(repo, exchange, settings)
    order = manager.submit(
        portfolio_id=manual["id"],
        ticker=ticker,
        side=side,
        quantity=quantity,
        source="test",
        sim_time=SIM_TIME,
        submitted_at=SIM_TIME,
    )
    return exchange.execute_order(
        order, fill_price=price, prices={ticker: price}, sim_time=SIM_TIME
    )


def assert_equity_invariant(repo, settings, prices: dict[str, float]) -> None:
    state = repo.load_state(repo.get_manual_portfolio()["id"])
    stats = repo.trade_stats(state.portfolio_id)
    expected = round_money(
        state.starting_balance
        + stats["realized_pnl"]
        + state.unrealized_pnl(prices)
        - stats["fees"]
        - state.borrow_fees
    )
    assert state.equity(prices) == pytest.approx(expected, abs=0.01)


def test_buy_then_partial_sell_accounting(repo, settings):
    result = submit_and_fill(repo, settings, "BUY", 10, 100.0)
    assert result["trade"]["fees"] == 0.5
    state = repo.load_state(repo.get_manual_portfolio()["id"])
    assert state.cash == pytest.approx(8999.50)
    assert state.holdings["AAPL"].quantity == 10
    assert state.holdings["AAPL"].average_entry == pytest.approx(100.0)
    assert_equity_invariant(repo, settings, {"AAPL": 100.0})

    result = submit_and_fill(repo, settings, "SELL", 4, 110.0)
    assert result["realized_pnl"] == pytest.approx(40.0)
    state = repo.load_state(repo.get_manual_portfolio()["id"])
    assert state.cash == pytest.approx(9439.28)  # 8999.50 + 440 - 0.22
    assert state.holdings["AAPL"].quantity == 6
    assert state.holdings["AAPL"].average_entry == pytest.approx(100.0)
    assert_equity_invariant(repo, settings, {"AAPL": 110.0})
    assert repo.trade_stats(state.portfolio_id)["realized_pnl"] == pytest.approx(40.0)


def test_average_entry_blends_on_add(repo, settings):
    submit_and_fill(repo, settings, "BUY", 10, 100.0)
    submit_and_fill(repo, settings, "BUY", 10, 120.0)
    state = repo.load_state(repo.get_manual_portfolio()["id"])
    assert state.holdings["AAPL"].quantity == 20
    assert state.holdings["AAPL"].average_entry == pytest.approx(110.0)
    assert_equity_invariant(repo, settings, {"AAPL": 120.0})


def test_short_and_cover_accounting(repo, settings):
    submit_and_fill(repo, settings, "SHORT", 10, 50.0)
    state = repo.load_state(repo.get_manual_portfolio()["id"])
    assert state.holdings["AAPL"].quantity == -10
    assert state.holdings["AAPL"].average_entry == pytest.approx(50.0)
    assert state.cash == pytest.approx(10499.75)
    # Short positions lose when price rises.
    assert state.unrealized_pnl({"AAPL": 55.0}) == pytest.approx(-50.0)
    assert_equity_invariant(repo, settings, {"AAPL": 55.0})

    result = submit_and_fill(repo, settings, "COVER", 10, 40.0)
    assert result["realized_pnl"] == pytest.approx(100.0)
    state = repo.load_state(repo.get_manual_portfolio()["id"])
    assert state.holdings.get("AAPL") is None
    assert state.cash == pytest.approx(10099.55)  # 10499.75 - 400 - 0.20
    assert_equity_invariant(repo, settings, {"AAPL": 40.0})


def test_borrow_fees_are_charged_on_shorts(repo, settings):
    submit_and_fill(repo, settings, "SHORT", 10, 100.0)
    exchange = Exchange(repo, settings)
    charged = exchange.accrue_borrow_fees(
        repo.get_manual_portfolio()["id"], {"AAPL": 100.0}, days=1.0
    )
    assert charged == pytest.approx(0.22)  # 1000 * 8% / 360
    state = repo.load_state(repo.get_manual_portfolio()["id"])
    assert state.borrow_fees == pytest.approx(0.22)
    assert state.holdings["AAPL"].borrow_fees == pytest.approx(0.22)
    assert_equity_invariant(repo, settings, {"AAPL": 100.0})


@pytest.mark.parametrize(
    ("side", "quantity", "price", "reason"),
    [
        ("SELL", 1, 100.0, "no_long_position"),
        ("COVER", 1, 100.0, "no_short_position"),
        ("BUY", 100_000, 100.0, "insufficient_buying_power"),
        ("SHORT", 21, 100.0, "short_position_limit"),
    ],
)
def test_invalid_orders_are_rejected(repo, settings, side, quantity, price, reason):
    manual = repo.get_manual_portfolio()
    exchange = Exchange(repo, settings)
    manager = OrderManager(repo, exchange, settings)
    order = manager.submit(
        portfolio_id=manual["id"],
        ticker="AAPL",
        side=side,
        quantity=quantity,
        source="test",
        sim_time=SIM_TIME,
        submitted_at=SIM_TIME,
    )
    with pytest.raises(OrderRejected) as excinfo:
        exchange.execute_order(order, fill_price=price, prices={"AAPL": price}, sim_time=SIM_TIME)
    assert excinfo.value.reason == reason
    # A rejected order must never move cash or create a position.
    state = repo.load_state(manual["id"])
    assert state.cash == pytest.approx(settings.starting_balance)
    assert not state.holdings


def test_cannot_hold_both_sides(repo, settings):
    submit_and_fill(repo, settings, "BUY", 5, 100.0)
    manual = repo.get_manual_portfolio()
    exchange = Exchange(repo, settings)
    manager = OrderManager(repo, exchange, settings)
    order = manager.submit(
        portfolio_id=manual["id"],
        ticker="AAPL",
        side="SHORT",
        quantity=5,
        source="test",
        sim_time=SIM_TIME,
        submitted_at=SIM_TIME,
    )
    with pytest.raises(OrderRejected) as excinfo:
        exchange.execute_order(order, fill_price=100.0, prices={"AAPL": 100.0}, sim_time=SIM_TIME)
    assert excinfo.value.reason == "conflicting_position"


def test_overselling_a_long_is_rejected(repo, settings):
    submit_and_fill(repo, settings, "BUY", 5, 100.0)
    manual = repo.get_manual_portfolio()
    exchange = Exchange(repo, settings)
    manager = OrderManager(repo, exchange, settings)
    order = manager.submit(
        portfolio_id=manual["id"],
        ticker="AAPL",
        side="SELL",
        quantity=6,
        source="test",
        sim_time=SIM_TIME,
        submitted_at=SIM_TIME,
    )
    with pytest.raises(OrderRejected) as excinfo:
        exchange.execute_order(order, fill_price=100.0, prices={"AAPL": 100.0}, sim_time=SIM_TIME)
    assert excinfo.value.reason == "insufficient_long_position"
    state = repo.load_state(manual["id"])
    assert state.holdings["AAPL"].quantity == 5


def test_unknown_ticker_rejected_at_submission(repo, settings):
    manual = repo.get_manual_portfolio()
    exchange = Exchange(repo, settings)
    manager = OrderManager(repo, exchange, settings)
    with pytest.raises(OrderRejected) as excinfo:
        manager.submit(
            portfolio_id=manual["id"],
            ticker="WOOF",
            side="BUY",
            quantity=1,
            source="test",
            sim_time=SIM_TIME,
            submitted_at=SIM_TIME,
        )
    assert excinfo.value.reason == "unknown_ticker"


def test_competition_metrics():
    assert max_drawdown_pct([10000, 11000, 9000, 12000]) == pytest.approx(18.18)
    assert max_drawdown_pct([10000, 10100]) == pytest.approx(0.0)
    assert win_rate_pct(2, 3) == pytest.approx(66.7)
    assert win_rate_pct(0, 0) == 0.0


def test_pending_order_does_not_change_state(repo, settings):
    exchange = Exchange(repo, settings)
    manager = OrderManager(repo, exchange, settings)
    manual = repo.get_manual_portfolio()
    order = manager.submit(
        portfolio_id=manual["id"],
        ticker="AAPL",
        side="BUY",
        quantity=3,
        source="manual",
        sim_time=SIM_TIME,
        submitted_at=SIM_TIME,
    )
    assert order["status"] == "PENDING"
    state = repo.load_state(manual["id"])
    assert state.cash == pytest.approx(settings.starting_balance)
    assert not state.holdings
