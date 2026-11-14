"""Agent C: blends price momentum with news sentiment."""
from __future__ import annotations

from .base_agent import BaseAgent, MarketContext, Signal
from .features import clamp, sentiment_score, technical_score
from .predictions import confidence_for
from ..trading.portfolio import PortfolioState


class CombinedAgent(BaseAgent):
    model_type = "combined"
    entry_threshold = 0.45
    exit_threshold = -0.05
    max_entries = 3
    target_position_pct = 0.13
    target_short_pct = 0.08
    allow_short = False
    sentiment_window_bars = 5  # one trading week of daily headlines
    price_weight = 0.9
    news_weight = 0.1

    def evaluate(self, context: MarketContext, state: PortfolioState) -> list[Signal]:
        signals: list[Signal] = []
        min_bar = max(0, context.bar_index - self.sentiment_window_bars)
        for ticker in sorted(context.bars):
            technical = technical_score(context.bars[ticker])
            if technical is None:
                continue
            sentiment = context.sentiments.get(ticker) or sentiment_score(
                context.news, ticker, min_bar
            )
            news_component = sentiment["score"] * 1.5 if sentiment["count"] else 0.0
            count = sentiment["count"]
            noun = "headline" if count == 1 else "headlines"
            score = clamp(
                self.price_weight * technical["score"] + self.news_weight * news_component,
                -1.0,
                1.0,
            )
            signals.append(
                Signal(
                    ticker=ticker,
                    score=score,
                    confidence=confidence_for(score),
                    rationale=(
                        f"price {technical['score']:+.2f} + news {news_component:+.2f} "
                        f"({count} {noun}) -> {score:+.2f}"
                    ),
                )
            )
        return signals
