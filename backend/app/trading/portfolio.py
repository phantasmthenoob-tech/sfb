"""In-memory representation of a portfolio used while executing an order."""
from __future__ import annotations

from dataclasses import dataclass, field

from .accounting import market_value, round_money, unrealized_pnl


@dataclass
class Holding:
    ticker: str
    quantity: int = 0
    average_entry: float = 0.0
    realized_pnl: float = 0.0
    borrow_fees: float = 0.0

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0


@dataclass
class PortfolioState:
    portfolio_id: int
    name: str
    kind: str
    starting_balance: float
    cash: float
    borrow_fees: float = 0.0
    holdings: dict[str, Holding] = field(default_factory=dict)

    def holding(self, ticker: str) -> Holding:
        if ticker not in self.holdings:
            self.holdings[ticker] = Holding(ticker=ticker)
        return self.holdings[ticker]

    def prices_with(self, ticker: str, price: float, prices: dict[str, float]) -> dict[str, float]:
        merged = dict(prices)
        merged[ticker] = price
        return merged

    def positions_value(self, prices: dict[str, float]) -> float:
        total = 0.0
        for ticker, holding in self.holdings.items():
            if holding.quantity == 0:
                continue
            price = prices.get(ticker, holding.average_entry)
            total += market_value(holding.quantity, price)
        return round_money(total)

    def equity(self, prices: dict[str, float]) -> float:
        return round_money(self.cash + self.positions_value(prices))

    def gross_long_exposure(self, prices: dict[str, float]) -> float:
        total = 0.0
        for ticker, holding in self.holdings.items():
            if holding.quantity > 0:
                total += market_value(holding.quantity, prices.get(ticker, holding.average_entry))
        return round_money(total)

    def gross_short_exposure(self, prices: dict[str, float]) -> float:
        total = 0.0
        for ticker, holding in self.holdings.items():
            if holding.quantity < 0:
                total += market_value(holding.quantity, prices.get(ticker, holding.average_entry))
        return round_money(total)

    def position_value(self, ticker: str, prices: dict[str, float]) -> float:
        holding = self.holding(ticker)
        price = prices.get(ticker, holding.average_entry)
        return market_value(holding.quantity, price)

    def unrealized_pnl(self, prices: dict[str, float]) -> float:
        total = 0.0
        for ticker, holding in self.holdings.items():
            if holding.quantity == 0:
                continue
            price = prices.get(ticker, holding.average_entry)
            total += unrealized_pnl(holding.quantity, holding.average_entry, price)
        return round_money(total)

    def realized_pnl(self) -> float:
        return round_money(sum(holding.realized_pnl for holding in self.holdings.values()))
