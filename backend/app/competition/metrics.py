"""Performance metrics derived from trades, positions and equity snapshots."""
from __future__ import annotations

from ..trading.accounting import round_money, unrealized_pnl as compute_unrealized


def max_drawdown_pct(equity_series: list[float]) -> float:
    """Largest peak-to-trough decline, returned as a positive percentage."""
    peak = 0.0
    worst = 0.0
    for equity in equity_series:
        peak = max(peak, equity)
        if peak <= 0:
            continue
        decline = (peak - equity) / peak
        worst = max(worst, decline)
    return round(worst * 100.0, 2)


def win_rate_pct(wins: int, closed_trades: int) -> float:
    if closed_trades <= 0:
        return 0.0
    return round(wins / closed_trades * 100.0, 1)


def total_return_pct(equity: float, starting_balance: float) -> float:
    if starting_balance <= 0:
        return 0.0
    return round((equity / starting_balance - 1.0) * 100.0, 2)


def portfolio_metrics(
    *,
    portfolio: dict,
    positions: list[dict],
    prices: dict[str, float],
    trade_stats: dict,
    equity_series: list[float],
    equity: float,
    cash: float,
    borrow_fees: float,
) -> dict:
    unrealized = 0.0
    for position in positions:
        price = prices.get(position["ticker"], position["average_entry"])
        unrealized += compute_unrealized(position["quantity"], position["average_entry"], price)
    series = equity_series + [equity] if equity_series else [equity]
    return {
        "equity": round_money(equity),
        "cash": round_money(cash),
        "starting_balance": round_money(portfolio["starting_balance"]),
        "total_return_pct": total_return_pct(equity, portfolio["starting_balance"]),
        "realized_pnl": round_money(float(trade_stats.get("realized_pnl", 0.0))),
        "unrealized_pnl": round_money(unrealized),
        "win_rate_pct": win_rate_pct(
            int(trade_stats.get("wins", 0)), int(trade_stats.get("closed_trades", 0))
        ),
        "max_drawdown_pct": max_drawdown_pct(series),
        "total_trades": int(trade_stats.get("total_trades", 0)),
        "closed_trades": int(trade_stats.get("closed_trades", 0)),
        "fees_paid": round_money(float(trade_stats.get("fees", 0.0))),
        "borrow_fees": round_money(borrow_fees),
    }
