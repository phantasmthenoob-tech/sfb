"""Live neural-network agent backed by the persisted ModelRegistry."""
from __future__ import annotations

from .base_agent import BaseAgent, MarketContext, Signal
from .predictions import confidence_for
from ..trading.portfolio import PortfolioState


class NeuralAgent(BaseAgent):
    """Rank stocks with a trained MLP and trade the top cross-sectional scores.

    The offline experiment evaluates scores as percentiles. The live agent
    converts the model output to the same 0..1 percentile scale, then maps it to
    [-1, 1] so the existing order engine and forecast recorder remain unchanged.
    """

    model_type = "neural"
    entry_threshold = 0.64  # 82nd percentile
    exit_threshold = 0.0  # 50th percentile
    max_entries = 10
    target_position_pct = 0.10
    target_short_pct = 0.0
    allow_short = False

    def evaluate(self, context: MarketContext, state: PortfolioState) -> list[Signal]:
        scorer = self.models
        if scorer is None or not hasattr(scorer, "score_context"):
            return []
        raw_scores = scorer.score_context(context)
        if not raw_scores:
            return []
        ranked = sorted(raw_scores.items(), key=lambda item: (item[1], item[0]))
        denominator = max(1, len(ranked) - 1)
        signals: list[Signal] = []
        for rank, (ticker, raw) in enumerate(ranked):
            percentile = rank / denominator
            score = percentile * 2.0 - 1.0
            signals.append(
                Signal(
                    ticker=ticker,
                    score=score,
                    confidence=confidence_for(score),
                    rationale=(
                        f"neural percentile {percentile:.2f}; "
                        f"raw prediction {raw:+.3f}"
                    ),
                )
            )
        return signals
