"""Order validation rules.

The trading engine is deliberately strict for the first version:

* SELL only reduces an existing long; use SHORT to open the other side.
* COVER only reduces an existing short; use BUY to open the other side.
* Every order is checked against buying power, per-position limits and total
  short exposure using the fill price, never a price from an earlier bar.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from .accounting import round_money
from .portfolio import PortfolioState

SIDES = ("BUY", "SELL", "SHORT", "COVER")


class OrderRejected(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


@dataclass(frozen=True)
class OrderCheck:
    side: str
    ticker: str
    quantity: int
    fill_price: float


def validate_order(state: PortfolioState, check: OrderCheck, prices: dict[str, float], settings: Settings) -> None:
    if check.side not in SIDES:
        raise OrderRejected("invalid_side", f"Unknown side {check.side!r}")
    if check.quantity <= 0:
        raise OrderRejected("invalid_quantity", "Quantity must be a positive number of shares")
    if check.fill_price <= 0:
        raise OrderRejected("no_price", f"No replay price available for {check.ticker}")

    relevant = state.prices_with(check.ticker, check.fill_price, prices)
    equity = state.equity(relevant)
    if equity <= 0:
        raise OrderRejected("account_depleted", "Portfolio equity is not positive")

    notional = round_money(check.quantity * check.fill_price)
    holding = state.holding(check.ticker)

    if check.side == "BUY":
        if holding.quantity < 0:
            raise OrderRejected("conflicting_position", "Cover the short position before buying")
        cost = round_money(notional + notional * settings.fee_bps / 10_000.0)
        if cost > state.cash + 1e-9:
            raise OrderRejected(
                "insufficient_buying_power",
                f"Order needs ${cost:,.2f} but only ${state.cash:,.2f} cash is available",
            )
        _check_order_notional(notional, equity, settings)
        resulting = round_money((holding.quantity + check.quantity) * check.fill_price)
        if resulting > round_money(settings.max_position_pct * equity) + 1e-9:
            raise OrderRejected(
                "position_limit",
                f"Long position would be ${resulting:,.2f} of ${equity:,.2f} equity "
                f"(limit {settings.max_position_pct:.0%})",
            )

    elif check.side == "SELL":
        if holding.quantity <= 0:
            raise OrderRejected("no_long_position", f"No long position in {check.ticker} to sell")
        if check.quantity > holding.quantity:
            raise OrderRejected(
                "insufficient_long_position",
                f"Cannot sell {check.quantity} shares; only {holding.quantity} held long",
            )

    elif check.side == "SHORT":
        if holding.quantity > 0:
            raise OrderRejected("conflicting_position", "Sell the long position before opening a short")
        _check_order_notional(notional, equity, settings)
        resulting_short = round_money((abs(holding.quantity) + check.quantity) * check.fill_price)
        if resulting_short > round_money(settings.max_short_position_pct * equity) + 1e-9:
            raise OrderRejected(
                "short_position_limit",
                f"Short position would be ${resulting_short:,.2f} of ${equity:,.2f} equity "
                f"(limit {settings.max_short_position_pct:.0%})",
            )
        total_short = round_money(state.gross_short_exposure(relevant) + notional)
        if total_short > round_money(settings.max_total_short_pct * equity) + 1e-9:
            raise OrderRejected(
                "short_exposure_limit",
                f"Total short exposure would be ${total_short:,.2f} of ${equity:,.2f} equity "
                f"(limit {settings.max_total_short_pct:.0%})",
            )

    elif check.side == "COVER":
        if holding.quantity >= 0:
            raise OrderRejected("no_short_position", f"No short position in {check.ticker} to cover")
        if check.quantity > abs(holding.quantity):
            raise OrderRejected(
                "insufficient_short_position",
                f"Cannot cover {check.quantity} shares; only {abs(holding.quantity)} shares short",
            )
        cost = round_money(notional + notional * settings.fee_bps / 10_000.0)
        if cost > state.cash + 1e-9:
            raise OrderRejected(
                "insufficient_buying_power",
                f"Cover needs ${cost:,.2f} but only ${state.cash:,.2f} cash is available",
            )


def _check_order_notional(notional: float, equity: float, settings: Settings) -> None:
    """Cap orders that increase exposure. Exits are never blocked by this cap."""
    if notional > round_money(settings.max_order_notional_pct * equity) + 1e-9:
        raise OrderRejected(
            "order_size_limit",
            f"Order notional ${notional:,.2f} exceeds {settings.max_order_notional_pct:.0%} of equity",
        )
