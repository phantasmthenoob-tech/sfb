"""Money and P&L helpers shared by the trading engine and competition metrics.

Conventions
-----------
* Share quantities are signed: positive = long, negative = short.
* Realized P&L is reported gross of transaction fees. Fees are tracked
  separately and are already reflected in cash, so the invariant below holds:

      equity == starting_balance + realized_pnl + unrealized_pnl
                - fees_paid - borrow_fees
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def round_money(value: float) -> float:
    """Round to cents using half-up, avoiding binary float surprises."""
    return float(Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP))


def trade_fee(notional: float, fee_bps: float) -> float:
    if notional <= 0:
        return 0.0
    return round_money(abs(notional) * fee_bps / 10_000.0)


def market_value(quantity: int, price: float) -> float:
    return round_money(quantity * price)


def unrealized_pnl(quantity: int, average_entry: float, price: float) -> float:
    """Works for shorts too: a negative quantity flips the price difference."""
    if quantity == 0:
        return 0.0
    return round_money((price - average_entry) * quantity)


def borrow_fee(quantity: int, price: float, annual_rate: float, days: float = 1.0) -> float:
    """Cost of borrowing shares for a short position, charged per simulated day."""
    if quantity >= 0 or days <= 0:
        return 0.0
    exposure = abs(quantity) * price
    return round_money(exposure * annual_rate * days / 360.0)


def blended_entry(old_quantity: int, old_average: float, added: int, price: float) -> float:
    new_quantity = old_quantity + added
    if new_quantity == 0:
        return 0.0
    total_cost = old_quantity * old_average + added * price
    return round_money(total_cost / new_quantity)
