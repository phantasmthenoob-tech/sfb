"""Agent A: technical signals from price history and volume only."""
from __future__ import annotations

from .base_agent import BaseAgent, MarketContext, Signal
from .features import technical_score
from .predictions import confidence_for
from ..trading.portfolio import PortfolioState


class PriceAgent(BaseAgent):
    model_type = "price"
    entry_threshold = 0.30
    exit_threshold = 0.05
    max_entries = 2
    target_position_pct = 0.16
    target_short_pct = 0.10

    def evaluate(self, context: MarketContext, state: PortfolioState) -> list[Signal]:
        signals: list[Signal] = []
        for ticker in sorted(context.bars):
            technical = technical_score(context.bars[ticker])
            if technical is None:
                continue
            rationale = (
                f"SMA5 {technical['fast_sma']:.2f} vs SMA20 {technical['slow_sma']:.2f}; "
                f"10-bar momentum {technical['momentum'] * 100:+.2f}%"
            )
            signals.append(
                Signal(
                    ticker=ticker,
                    score=technical["score"],
                    confidence=confidence_for(technical["score"]),
                    rationale=rationale,
                )
            )
        return signals
