"""Point-in-time feature extraction for the live neural-network agent.

The training pipeline builds the same 26 columns from full history. This module
rebuilds one row per ticker from the 120-bar context available at the current
decision, using only information visible at that close.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

from ..market.universe import PROFILE_BY_SYMBOL
from .base_agent import MarketContext
from .features import clamp, technical_score

FEATURE_NAMES = (
    "trend",
    "momentum",
    "cross",
    "volatility",
    "return_5",
    "return_20",
    "news",
    "news_count",
    "price_news",
    "market_trend",
    "volume_trend",
    "rsi14",
    "range_pos_20",
    "dist_sma20",
    "dist_sma50",
    "return_1",
    "return_3",
    "return_10",
    "vol_ratio_5_20",
    "market_return_5",
    "market_return_20",
    "market_vol_20",
    "relative_strength_20",
    "sector_relative_20",
    "market_breadth",
    "news_1d",
)


def _return(values: list[float], periods: int) -> float:
    if len(values) <= periods or not values[-periods - 1]:
        return 0.0
    return values[-1] / values[-periods - 1] - 1.0


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _realized_vol(values: list[float], window: int) -> float:
    if len(values) < window + 1:
        return 0.0
    returns = [
        values[index] / values[index - 1] - 1.0
        for index in range(len(values) - window, len(values))
        if values[index - 1]
    ]
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    return math.sqrt(sum((value - mean) ** 2 for value in returns) / len(returns))


def _rsi(values: list[float], window: int = 14) -> float:
    if len(values) < window + 1:
        return 0.0
    gains = losses = 0.0
    for index in range(len(values) - window, len(values)):
        change = values[index] - values[index - 1]
        if change > 0:
            gains += change
        else:
            losses -= change
    if losses == 0:
        return 1.0
    ratio = gains / losses
    return clamp((100.0 - 100.0 / (1.0 + ratio)) / 50.0 - 1.0, -1.0, 1.0)


def _volume_trend(volumes: list[int]) -> float:
    if len(volumes) < 21:
        return 0.0
    average = sum(volumes[-21:-1]) / 20.0
    if not average:
        return 0.0
    return clamp(math.tanh((volumes[-1] / average - 1.0) * 2.0), -1.0, 1.0)


def _market_trend(closes: list[float]) -> float:
    if len(closes) < 50:
        return 0.0
    fast = sum(closes[-20:]) / 20.0
    slow = sum(closes[-50:]) / 50.0
    if not slow:
        return 0.0
    return clamp(math.tanh((fast / slow - 1.0) * 60.0), -1.0, 1.0)


def _one_day_news(
    own: dict[str, tuple[float, float]],
    market_total: float,
    market_weight: float,
    ticker: str,
) -> float:
    ticker_total, ticker_weight = own.get(ticker, (0.0, 0.0))
    total = ticker_total + market_total * 0.35
    weight = ticker_weight + market_weight * 0.35
    return clamp((total / weight if weight else 0.0) * 1.5, -1.0, 1.0)


def build_live_features(context: MarketContext) -> dict[str, tuple[float, ...]]:
    """Return one 26-value feature vector per ticker with enough history."""
    # Index the current bar's headlines once. Scanning all 4,000 visible news
    # rows once per ticker made a single live score take over a second.
    news_own: dict[str, tuple[float, float]] = {}
    market_total = market_weight = 0.0
    for item in context.news:
        if int(item.get("bar_index", -1)) != context.bar_index:
            continue
        sentiment = float(item["sentiment"])
        ticker = item.get("ticker")
        if ticker is None:
            market_total += sentiment
            market_weight += 1.0
        else:
            total, weight = news_own.get(ticker, (0.0, 0.0))
            news_own[ticker] = (total + sentiment, weight + 1.0)

    stock_tickers = [
        ticker
        for ticker in context.bars
        if (profile := PROFILE_BY_SYMBOL.get(ticker)) is not None
        and profile.kind == "stock"
    ]
    closes_by_ticker: dict[str, list[float]] = {}
    volumes_by_ticker: dict[str, list[int]] = {}
    for ticker in stock_tickers:
        bars = context.bars[ticker]
        # A ticker with missing sessions would shift every lag; skip it.
        if len(bars) < 21:
            continue
        closes_by_ticker[ticker] = [float(bar["close"]) for bar in bars]
        volumes_by_ticker[ticker] = [int(bar.get("volume") or 0) for bar in bars]

    market_closes = [float(bar["close"]) for bar in context.market_bars]
    market_returns_5 = _return(market_closes, 5) if market_closes else 0.0
    market_returns_20 = _return(market_closes, 20) if market_closes else 0.0
    market_vol = _realized_vol(market_closes, 20) if market_closes else 0.0
    market_trend = _market_trend(market_closes)

    sectors: dict[str, list[str]] = defaultdict(list)
    for ticker, closes in closes_by_ticker.items():
        profile = PROFILE_BY_SYMBOL.get(ticker)
        if profile and profile.sector:
            sectors[profile.sector].append(ticker)
    sector_returns: dict[str, float] = {}
    for sector, members in sectors.items():
        returns = [_return(closes_by_ticker[ticker], 20) for ticker in members]
        sector_returns[sector] = statistics.mean(returns) if returns else 0.0

    breadth = 0.5
    if closes_by_ticker:
        above = 0
        for closes in closes_by_ticker.values():
            average = _sma(closes, 20)
            if average is not None:
                above += closes[-1] > average
        breadth = above / len(closes_by_ticker) - 0.5

    features: dict[str, tuple[float, ...]] = {}
    for ticker, closes in closes_by_ticker.items():
        bars = context.bars[ticker]
        technical = (
            context.technicals[ticker]
            if ticker in context.technicals
            else technical_score(bars)
        )
        if technical is None:
            continue
        volumes = volumes_by_ticker[ticker]
        sentiment = context.sentiments.get(ticker) or {"score": 0.0, "count": 0}
        news_component = clamp(float(sentiment["score"]) * 1.5, -1.0, 1.0)
        count = int(sentiment.get("count") or 0)
        average20 = _sma(closes, 20)
        average50 = _sma(closes, 50)
        window = closes[-20:]
        low, high = min(window), max(window)
        range_pos = (closes[-1] - low) / (high - low) - 0.5 if high > low else 0.0
        vol5 = _realized_vol(closes, 5)
        vol20 = _realized_vol(closes, 20)
        profile = PROFILE_BY_SYMBOL.get(ticker)
        sector = profile.sector if profile else None
        ret20 = _return(closes, 20)
        news_1d = _one_day_news(news_own, market_total, market_weight, ticker)
        features[ticker] = (
            technical["score"],
            technical["momentum"],
            technical["fast_sma"] / technical["slow_sma"] - 1.0
            if technical["slow_sma"]
            else 0.0,
            technical["volatility"] or 0.0,
            _return(closes, 5),
            ret20,
            news_component,
            min(count, 5) / 5.0,
            technical["score"] * news_component,
            market_trend,
            _volume_trend(volumes),
            _rsi(closes),
            clamp(range_pos * 2.0, -1.0, 1.0),
            math.tanh((closes[-1] / average20 - 1.0) * 30.0)
            if average20
            else 0.0,
            math.tanh((closes[-1] / average50 - 1.0) * 20.0)
            if average50
            else 0.0,
            _return(closes, 1),
            _return(closes, 3),
            _return(closes, 10),
            clamp(vol5 / vol20 - 1.0, -3.0, 3.0) if vol20 else 0.0,
            market_returns_5,
            market_returns_20,
            market_vol,
            clamp(ret20 - market_returns_20, -0.5, 0.5),
            clamp(ret20 - sector_returns.get(sector, 0.0), -0.5, 0.5)
            if sector
            else 0.0,
            breadth,
            news_1d,
        )
    return features
