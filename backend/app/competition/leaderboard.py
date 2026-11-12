"""Rankings and portfolio views shared by the REST API and the websocket."""
from __future__ import annotations

from ..database.repositories import Repository
from ..trading.accounting import market_value, round_money, unrealized_pnl
from .metrics import portfolio_metrics


def build_portfolio_view(
    repo: Repository,
    portfolio: dict,
    prices: dict[str, float],
    *,
    include_history: bool = False,
) -> dict:
    positions = repo.list_positions(portfolio["id"])
    position_rows = []
    for position in positions:
        price = prices.get(position["ticker"], position["average_entry"])
        quantity = position["quantity"]
        value = market_value(quantity, price)
        pnl = unrealized_pnl(quantity, position["average_entry"], price)
        position_rows.append(
            {
                "ticker": position["ticker"],
                "quantity": quantity,
                "side": "LONG" if quantity > 0 else "SHORT",
                "average_entry": position["average_entry"],
                "price": price,
                "market_value": value,
                "unrealized_pnl": pnl,
                "unrealized_pct": round(
                    (price / position["average_entry"] - 1.0) * 100.0
                    if position["average_entry"]
                    else 0.0,
                    2,
                )
                * (1 if quantity > 0 else -1),
            }
        )

    positions_value = round_money(sum(row["market_value"] for row in position_rows))
    equity = round_money(portfolio["cash"] + positions_value)
    trade_stats = repo.trade_stats(portfolio["id"])
    snapshots = repo.snapshots(portfolio["id"], limit=500)
    metrics = portfolio_metrics(
        portfolio=portfolio,
        positions=positions,
        prices=prices,
        trade_stats=trade_stats,
        equity_series=[snapshot["equity"] for snapshot in snapshots],
        equity=equity,
        cash=portfolio["cash"],
        borrow_fees=portfolio["borrow_fees"],
    )
    short_exposure = round_money(
        sum(row["market_value"] for row in position_rows if row["quantity"] < 0)
    )
    view = {
        "id": portfolio["id"],
        "name": portfolio["name"],
        "kind": portfolio["kind"],
        "agent_id": portfolio["agent_id"],
        "model_type": portfolio.get("model_type"),
        "cash": metrics["cash"],
        "positions_value": positions_value,
        "equity": metrics["equity"],
        "starting_balance": metrics["starting_balance"],
        "total_return_pct": metrics["total_return_pct"],
        "realized_pnl": metrics["realized_pnl"],
        "unrealized_pnl": metrics["unrealized_pnl"],
        "win_rate_pct": metrics["win_rate_pct"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "total_trades": metrics["total_trades"],
        "closed_trades": metrics["closed_trades"],
        "fees_paid": metrics["fees_paid"],
        "borrow_fees": metrics["borrow_fees"],
        "short_exposure": short_exposure,
        "positions": position_rows,
    }
    if include_history:
        view["equity_curve"] = [
            {"ts": snapshot["ts"], "bar_index": snapshot["bar_index"], "equity": snapshot["equity"]}
            for snapshot in snapshots
        ]
    return view


def build_leaderboard(repo: Repository, prices: dict[str, float]) -> list[dict]:
    entries = []
    for portfolio in repo.list_portfolios():
        view = build_portfolio_view(repo, portfolio, prices)
        view.pop("positions", None)
        entries.append(view)
    entries.sort(key=lambda entry: (-entry["total_return_pct"], entry["max_drawdown_pct"]))
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
    return entries
