"""The simulated exchange: fills orders and mutates portfolios.

This module is intentionally independent of any AI or HTTP code. Strategies only
express intent; every fill goes through `Exchange.execute_order`.
"""
from __future__ import annotations

from ..config import Settings
from ..database.repositories import Repository
from .accounting import blended_entry, borrow_fee, round_money, trade_fee
from .portfolio import PortfolioState
from .risk_limits import OrderCheck, OrderRejected, validate_order


class Exchange:
    def __init__(self, repo: Repository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def execute_order(
        self,
        order: dict,
        *,
        fill_price: float,
        prices: dict[str, float],
        sim_time: str,
    ) -> dict:
        state = self.repo.load_state(order["portfolio_id"])
        side = order["side"]
        ticker = order["ticker"]
        quantity = int(order["quantity"])

        validate_order(
            state,
            OrderCheck(side=side, ticker=ticker, quantity=quantity, fill_price=fill_price),
            prices,
            self.settings,
        )

        notional = round_money(quantity * fill_price)
        fees = trade_fee(notional, self.settings.fee_bps)
        holding = state.holding(ticker)
        realized_pnl = 0.0

        if side == "BUY":
            state.cash -= notional + fees
            holding.average_entry = blended_entry(
                holding.quantity, holding.average_entry, quantity, fill_price
            )
            holding.quantity += quantity
        elif side == "SELL":
            realized_pnl = round_money((fill_price - holding.average_entry) * quantity)
            state.cash += notional - fees
            holding.realized_pnl += realized_pnl
            holding.quantity -= quantity
            if holding.quantity == 0:
                holding.average_entry = 0.0
        elif side == "SHORT":
            state.cash += notional - fees
            holding.average_entry = blended_entry(
                abs(holding.quantity), holding.average_entry, quantity, fill_price
            )
            holding.quantity -= quantity
        elif side == "COVER":
            realized_pnl = round_money((holding.average_entry - fill_price) * quantity)
            state.cash -= notional + fees
            holding.realized_pnl += realized_pnl
            holding.quantity += quantity
            if holding.quantity == 0:
                holding.average_entry = 0.0
        else:  # pragma: no cover - validate_order guards this
            raise OrderRejected("invalid_side", f"Unknown side {side!r}")

        state.cash = round_money(state.cash)
        self.repo.save_state(state)
        self.repo.mark_order_filled(order["id"], fill_price, fees, sim_time)
        trade = self.repo.insert_trade(
            order_id=order["id"],
            portfolio_id=order["portfolio_id"],
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=fill_price,
            fees=fees,
            realized_pnl=realized_pnl,
            sim_time=sim_time,
        )
        return {"trade": trade, "state": state, "fees": fees, "realized_pnl": realized_pnl}

    def accrue_borrow_fees(
        self, portfolio_id: int, prices: dict[str, float], days: float = 1.0
    ) -> float:
        """Charge short sellers for borrowed shares once per simulated session."""
        state = self.repo.load_state(portfolio_id)
        charged = 0.0
        for ticker, holding in state.holdings.items():
            if holding.quantity >= 0:
                continue
            price = prices.get(ticker, holding.average_entry)
            fee = borrow_fee(holding.quantity, price, self.settings.borrow_rate_annual, days)
            if fee <= 0:
                continue
            holding.borrow_fees = round_money(holding.borrow_fees + fee)
            state.borrow_fees = round_money(state.borrow_fees + fee)
            state.cash = round_money(state.cash - fee)
            charged = round_money(charged + fee)
        if charged:
            self.repo.save_state(state)
        return charged

    @staticmethod
    def state_summary(state: PortfolioState, prices: dict[str, float]) -> dict:
        return {
            "portfolio_id": state.portfolio_id,
            "cash": round_money(state.cash),
            "positions_value": state.positions_value(prices),
            "equity": state.equity(prices),
        }
