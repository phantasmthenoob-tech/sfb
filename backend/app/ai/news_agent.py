"""Agent B: headline sentiment only, with a rolling visibility window."""
from __future__ import annotations

from .base_agent import BaseAgent, MarketContext, Signal
from .features import clamp, sentiment_score
from .predictions import confidence_for
from ..trading.portfolio import PortfolioState


class NewsAgent(BaseAgent):
    model_type = "news"
    entry_threshold = 0.22
    exit_threshold = 0.02
    max_entries = 2
    target_position_pct = 0.16
    target_short_pct = 0.10
    sentiment_window_bars = 5  # one trading week of daily headlines

    def evaluate(self, context: MarketContext, state: PortfolioState) -> list[Signal]:
        signals: list[Signal] = []
        min_bar = max(0, context.bar_index - self.sentiment_window_bars)
        for ticker in sorted(context.bars):
            sentiment = sentiment_score(context.news, ticker, min_bar)
            score = clamp(sentiment["score"] * 1.5, -1.0, 1.0)
            headline = sentiment["headline"] or "no fresh headlines"
            count = sentiment["count"]
            noun = "headline" if count == 1 else "headlines"
            signals.append(
                Signal(
                    ticker=ticker,
                    score=score,
                    confidence=confidence_for(score) if sentiment["count"] else 0.5,
                    rationale=f"{count} {noun}, avg sentiment {sentiment['score']:+.2f}; latest: {headline}",
                )
            )
        return signals
