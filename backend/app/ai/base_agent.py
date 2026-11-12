"""Strategy interface shared by the three AI agents.

Agents produce signals and order intents only. They never touch cash, positions
or the exchange directly: the trading engine validates and fills every intent.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal

from ..config import Settings
from ..database.repositories import Repository
from ..trading.accounting import round_money
from ..trading.portfolio import PortfolioState
from .predictions import direction_for


@dataclass(frozen=True)
class MarketContext:
    """A read-only slice of the replay, cut at the current simulated bar."""

    sim_time: str
    bar_index: int
    prices: dict[str, float]
    bars: dict[str, list[dict]]
    news: list[dict]


@dataclass(frozen=True)
class OrderIntent:
    ticker: str
    side: str
    quantity: int


@dataclass
class Signal:
    ticker: str
    score: float
    confidence: float
    rationale: str


@dataclass
class BaseAgent(ABC):
    agent_id: int
    name: str
    portfolio_id: int
    repo: Repository
    settings: Settings
    model_type: str = "base"
    entry_threshold: float = 0.35
    exit_threshold: float = 0.05
    max_entries: int = 2
    target_position_pct: float = 0.15
    target_short_pct: float = 0.10
    _last_scores: dict[str, float] = field(default_factory=dict, init=False)

    # -------------------------------------------------------------- strategy
    @abstractmethod
    def evaluate(self, context: MarketContext, state: PortfolioState) -> list[Signal]:
        """Return one score per ticker, roughly in [-1, 1]."""

    # ------------------------------------------------------------------ loop
    def step(self, context: MarketContext) -> list[OrderIntent]:
        state = self.repo.load_state(self.portfolio_id)
        signals = [signal for signal in self.evaluate(context, state) if signal.ticker in context.prices]
        signals.sort(key=lambda signal: signal.score, reverse=True)
        self._last_scores = {signal.ticker: signal.score for signal in signals}
        self._record_prediction(context, signals)
        return self._signals_to_intents(signals, context, state)

    def _record_prediction(self, context: MarketContext, signals: list[Signal]) -> None:
        if not signals:
            return
        best = max(signals, key=lambda signal: abs(signal.score))
        self.repo.insert_prediction(
            agent_id=self.agent_id,
            ticker=best.ticker,
            horizon="short",
            direction=direction_for(best.score, self.entry_threshold),
            confidence=best.confidence,
            rationale=best.rationale,
            sim_time=context.sim_time,
        )

    def _signals_to_intents(
        self, signals: list[Signal], context: MarketContext, state: PortfolioState
    ) -> list[OrderIntent]:
        equity = state.equity(context.prices)
        if equity <= 0:
            return []
        intents: list[OrderIntent] = []
        entries = 0

        for signal in signals:
            holding = state.holdings.get(signal.ticker)
            quantity = holding.quantity if holding else 0
            price = context.prices[signal.ticker]

            if quantity > 0 and signal.score <= self.exit_threshold:
                intents.append(OrderIntent(signal.ticker, "SELL", quantity))
                continue
            if quantity < 0 and signal.score >= -self.exit_threshold:
                intents.append(OrderIntent(signal.ticker, "COVER", abs(quantity)))
                continue
            if quantity != 0 or entries >= self.max_entries:
                continue

            if signal.score >= self.entry_threshold:
                budget = min(equity * self.target_position_pct, state.cash * 0.95)
                shares = self._shares_for(budget, price)
                if shares > 0:
                    intents.append(OrderIntent(signal.ticker, "BUY", shares))
                    entries += 1
            elif signal.score <= -self.entry_threshold:
                shares = self._shares_for(equity * self.target_short_pct, price)
                if shares > 0:
                    intents.append(OrderIntent(signal.ticker, "SHORT", shares))
                    entries += 1
        return intents

    @staticmethod
    def _shares_for(budget: float, price: float) -> int:
        if budget <= 0 or price <= 0:
            return 0
        return max(0, int(Decimal(str(budget / price)).quantize(Decimal("1"), rounding=ROUND_FLOOR)))

    # ------------------------------------------------------------- utilities
    @staticmethod
    def position_snapshot(state: PortfolioState, prices: dict[str, float]) -> dict:
        return {
            "cash": round_money(state.cash),
            "equity": state.equity(prices),
            "realized_pnl": state.realized_pnl(),
        }
