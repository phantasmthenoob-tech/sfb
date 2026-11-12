"""Order lifecycle: validation, queueing, and next-bar fills.

Orders are separate from trades. An order is what an account asked for; a trade
is what the simulated exchange actually filled. Manual and AI orders share this
path, and both fill at the next session's open price.
"""
from __future__ import annotations

from ..config import Settings
from ..database.repositories import Repository
from .exchange import Exchange
from .risk_limits import SIDES, OrderRejected


class OrderManager:
    def __init__(self, repo: Repository, exchange: Exchange, settings: Settings) -> None:
        self.repo = repo
        self.exchange = exchange
        self.settings = settings

    def submit(
        self,
        *,
        portfolio_id: int,
        ticker: str,
        side: str,
        quantity: int,
        source: str,
        sim_time: str,
        submitted_at: str,
    ) -> dict:
        ticker = ticker.upper().strip()
        side = side.upper().strip()
        if side not in SIDES:
            raise OrderRejected("invalid_side", f"Side must be one of {', '.join(SIDES)}")
        if ticker not in self.settings.universe:
            raise OrderRejected(
                "unknown_ticker",
                f"{ticker} is not part of this replay universe",
            )
        if not isinstance(quantity, int) or quantity <= 0:
            raise OrderRejected("invalid_quantity", "Quantity must be a positive integer")
        portfolio = self.repo.get_portfolio(portfolio_id)
        if not portfolio:
            raise OrderRejected("unknown_portfolio", f"Unknown portfolio {portfolio_id}")

        return self.repo.insert_order(
            portfolio_id=portfolio_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            source=source,
            submitted_at=submitted_at,
            sim_time=sim_time,
        )

    def fill_pending(self, fill_prices: dict[str, float], sim_time: str) -> list[dict]:
        """Fill every pending order at the next session's open price."""
        results: list[dict] = []
        for order in self.repo.list_pending_orders():
            price = fill_prices.get(order["ticker"])
            if price is None:
                self.repo.mark_order_rejected(order["id"], "no_replay_price")
                continue
            try:
                result = self.exchange.execute_order(
                    order, fill_price=price, prices=fill_prices, sim_time=sim_time
                )
                results.append({"order_id": order["id"], "status": "FILLED", **result})
            except OrderRejected as exc:
                self.repo.mark_order_rejected(order["id"], f"{exc.reason}: {exc.detail}")
                results.append(
                    {"order_id": order["id"], "status": "REJECTED", "reason": exc.reason}
                )
        return results
