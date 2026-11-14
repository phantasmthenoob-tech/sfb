"""Sector attribution across the competing agent portfolios.

Contribution is measured against each portfolio's starting balance:
``(realized P&L - fees + open unrealized P&L) / starting balance``. This makes
the sector rows additive enough to explain where a portfolio's return came
from without inventing a separate sector-level cash account.
"""
from __future__ import annotations

from collections import defaultdict

from ..database.repositories import Repository
from ..market.universe import INDUSTRY_SECTORS, STOCK_PROFILES
from ..trading.accounting import round_money, unrealized_pnl

SECTOR_EXPOSURES: dict[str, tuple[str, ...]] = {}
for profile in STOCK_PROFILES:
    if profile.sector:
        SECTOR_EXPOSURES.setdefault(profile.sector, ())
        SECTOR_EXPOSURES[profile.sector] = tuple(
            sorted(set(SECTOR_EXPOSURES[profile.sector]) | set(profile.exposures))
        )


def build_sector_performance(repo: Repository, prices: dict[str, float]) -> dict:
    sector_by_ticker = {
        profile.symbol: profile.sector for profile in STOCK_PROFILES if profile.sector
    }
    sector_rows: dict[str, list[dict]] = defaultdict(list)
    agents = []
    for portfolio in repo.list_portfolios():
        if portfolio.get("kind") != "agent":
            continue
        agents.append(
            {
                "id": portfolio.get("agent_id"),
                "name": portfolio.get("agent_name") or portfolio["name"],
                "model_type": portfolio.get("model_type"),
            }
        )
        trades = repo.list_trades(portfolio["id"], limit=100_000)
        positions = repo.list_positions(portfolio["id"])
        realized: dict[str, float] = defaultdict(float)
        fees: dict[str, float] = defaultdict(float)
        trade_counts: dict[str, int] = defaultdict(int)
        for trade in trades:
            sector = sector_by_ticker.get(trade["ticker"], "Unclassified")
            realized[sector] += float(trade.get("realized_pnl") or 0.0)
            fees[sector] += float(trade.get("fees") or 0.0)
            trade_counts[sector] += 1
        unrealized: dict[str, float] = defaultdict(float)
        positions_value: dict[str, float] = defaultdict(float)
        open_counts: dict[str, int] = defaultdict(int)
        for position in positions:
            sector = sector_by_ticker.get(position["ticker"], "Unclassified")
            price = prices.get(position["ticker"], position["average_entry"])
            unrealized[sector] += unrealized_pnl(
                position["quantity"], position["average_entry"], price
            )
            positions_value[sector] += position["quantity"] * price
            open_counts[sector] += 1

        starting = float(portfolio.get("starting_balance") or 0.0)
        for sector in [*INDUSTRY_SECTORS, "Unclassified"]:
            if sector == "Unclassified" and not (
                realized[sector] or unrealized[sector] or positions_value[sector]
            ):
                continue
            net = realized[sector] - fees[sector] + unrealized[sector]
            yield_row = {
                "agent_id": portfolio.get("agent_id"),
                "agent_name": portfolio.get("agent_name") or portfolio["name"],
                "model_type": portfolio.get("model_type"),
                "sector": sector,
                "contribution_pct": round(net / starting * 100.0, 3) if starting else 0.0,
                "realized_pnl": round_money(realized[sector]),
                "unrealized_pnl": round_money(unrealized[sector]),
                "fees": round_money(fees[sector]),
                "positions_value": round_money(positions_value[sector]),
                "trades": trade_counts[sector],
                "open_positions": open_counts[sector],
            }
            sector_rows[sector].append(yield_row)

    sectors = []
    for sector in [*INDUSTRY_SECTORS, "Unclassified"]:
        rows = sector_rows.get(sector, [])
        if not rows:
            continue
        sectors.append(
            {
                "sector": sector,
                "exposures": list(SECTOR_EXPOSURES.get(sector, ())),
                "agents": rows,
            }
        )
    return {
        "agents": agents,
        "sectors": sectors,
        "note": "Contribution is realized P&L minus fees plus open unrealized P&L, divided by starting balance.",
    }
