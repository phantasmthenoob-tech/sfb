"""Feature extraction shared by the three strategies.

Everything here is computed only from data at or before the current replay bar.
"""
from __future__ import annotations

import math

from ..market.data_processor import clamp


def sma(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def pct_return(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or values[-periods - 1] == 0:
        return None
    return values[-1] / values[-periods - 1] - 1.0


def realized_volatility(values: list[float], window: int = 20) -> float | None:
    if len(values) < window + 1:
        return None
    returns = [
        values[i] / values[i - 1] - 1.0
        for i in range(len(values) - window, len(values))
        if values[i - 1]
    ]
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((ret - mean) ** 2 for ret in returns) / len(returns)
    return math.sqrt(variance)


def technical_score(bars: list[dict]) -> dict | None:
    """Score in [-1, 1] from an SMA cross plus 10-bar momentum."""
    closes = [bar["close"] for bar in bars]
    fast = sma(closes, 5)
    slow = sma(closes, 20)
    momentum = pct_return(closes, 10)
    if fast is None or slow is None or momentum is None or slow == 0:
        return None

    cross = fast / slow - 1.0
    trend_component = math.tanh(cross * 120.0)
    momentum_component = math.tanh(momentum * 25.0)
    score = 0.6 * trend_component + 0.4 * momentum_component
    return {
        "score": clamp(score, -1.0, 1.0),
        "fast_sma": round(fast, 2),
        "slow_sma": round(slow, 2),
        "momentum": momentum,
        "volatility": realized_volatility(closes),
        "close": closes[-1],
    }


def sentiment_score(news_items: list[dict], ticker: str, min_bar: int) -> dict:
    """Average headline sentiment for a ticker inside the replay window."""
    relevant = [
        item
        for item in news_items
        if item["bar_index"] >= min_bar
        and (item["ticker"] == ticker or item["ticker"] is None)
    ]
    if not relevant:
        return {"score": 0.0, "count": 0, "headline": None}
    total = 0.0
    weight = 0.0
    for item in relevant:
        item_weight = 1.0 if item["ticker"] == ticker else 0.35
        total += item["sentiment"] * item_weight
        weight += item_weight
    average = total / weight if weight else 0.0
    return {
        "score": clamp(average, -1.0, 1.0),
        "count": len(relevant),
        "headline": max(relevant, key=lambda item: (item["bar_index"], item["id"]))["headline"],
    }
