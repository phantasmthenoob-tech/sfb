"""Correlation diagnostics for a large stock universe.

Twenty names in one sector are often one risk factor, not twenty independent
opportunities. This computes pairwise return correlations from the same visible
daily bars while keeping the response small enough for the dashboard.
"""
from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

from ..database.repositories import Repository
from ..market.universe import STOCK_PROFILES

SECTOR_BY_TICKER = {
    profile.symbol: profile.sector for profile in STOCK_PROFILES if profile.sector
}


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_var = sum((a - left_mean) ** 2 for a in left)
    right_var = sum((b - right_mean) ** 2 for b in right)
    denominator = math.sqrt(left_var * right_var)
    return numerator / denominator if denominator else None


def build_correlation_summary(
    repo: Repository, cursor: int, *, window: int = 60, top: int = 8
) -> dict:
    rows = repo.bars_window(max(0, cursor - window), cursor)
    closes: dict[str, dict[int, float]] = defaultdict(dict)
    for row in rows:
        if row["ticker"] in SECTOR_BY_TICKER:
            closes[row["ticker"]][row["bar_index"]] = float(row["close"])
    indices = sorted({index for series in closes.values() for index in series})
    returns: dict[str, list[float]] = {}
    for ticker, series in closes.items():
        values = [series[index] for index in indices if index in series]
        if len(values) < 3:
            continue
        changes = [
            values[i] / values[i - 1] - 1.0
            for i in range(1, len(values))
            if values[i - 1]
        ]
        if len(changes) >= 3:
            returns[ticker] = changes

    pairs = []
    values = []
    for left, right in combinations(sorted(returns), 2):
        correlation = _correlation(returns[left], returns[right])
        if correlation is None:
            continue
        pairs.append((correlation, left, right))
        values.append(correlation)
    pairs.sort(reverse=True)
    average = sum(values) / len(values) if values else 0.0
    same_sector = [
        value
        for value, left, right in pairs
        if SECTOR_BY_TICKER.get(left) == SECTOR_BY_TICKER.get(right)
    ]
    cross_sector = [
        value
        for value, left, right in pairs
        if SECTOR_BY_TICKER.get(left) != SECTOR_BY_TICKER.get(right)
    ]
    return {
        "window_sessions": window,
        "tickers": len(returns),
        "pairs": len(pairs),
        "average_pairwise_correlation": round(average, 4),
        "same_sector_average": round(sum(same_sector) / len(same_sector), 4)
        if same_sector
        else None,
        "cross_sector_average": round(sum(cross_sector) / len(cross_sector), 4)
        if cross_sector
        else None,
        "top_pairs": [
            {"left": left, "right": right, "correlation": round(value, 4)}
            for value, left, right in pairs[:top]
        ],
        "bottom_pairs": [
            {"left": left, "right": right, "correlation": round(value, 4)}
            for value, left, right in pairs[-top:]
        ],
        "note": "Daily close-to-close correlations; high values mean duplicated risk, not independent ideas.",
    }
