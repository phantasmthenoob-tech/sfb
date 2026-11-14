"""Leakage and portfolio-metric tests for the walk-forward experiment."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from tools.experiment import (
    HORIZON,
    _percentile_scores,
    _risk_metrics,
    build_feature_rows,
    build_folds,
    simulate_ranked,
    training_rows,
)


def weekdays(start: date, count: int) -> list[str]:
    days: list[str] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def bars_for(dates: list[str], tickers=("AAPL", "MSFT", "SPY")) -> dict[str, dict[int, dict]]:
    bars = {}
    for offset, day in enumerate(dates):
        for number, ticker in enumerate(tickers):
            price = 100.0 + number * 10 + offset * 0.25
            bars.setdefault(ticker, {})[offset] = {
                "session_date": day,
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price + 0.1,
                "volume": 1_000_000 + offset * 1000,
            }
    return bars


def test_training_rows_purge_the_validation_period():
    dates = weekdays(date(2024, 1, 2), 90)
    bars = bars_for(dates)
    rows = build_feature_rows(
        dates=dates,
        bars=bars,
        news_by_offset=[{} for _ in dates],
        tickers=("AAPL", "MSFT"),
    )
    cutoff = 70
    train = training_rows(rows, cutoff)
    assert train
    assert max(row.offset + HORIZON for row in train) <= cutoff - 1
    assert all(row.offset + HORIZON < cutoff for row in train)
    assert any(row.offset + HORIZON >= cutoff for row in rows)


def test_folds_are_expanding_and_cover_the_evaluation_period():
    dates = weekdays(date(2015, 1, 2), 2800)
    folds = build_folds(dates, evaluation_years=5)
    assert len(folds) == 5
    assert folds[0].start_offset > 20
    assert folds[-1].end_offset == len(dates) - 1
    for previous, current in zip(folds, folds[1:]):
        assert current.start_offset == previous.end_offset + 1
        assert current.start_date == dates[current.start_offset]
    assert all(fold.start_offset < fold.end_offset for fold in folds)


def test_percentile_scores_are_cross_sectional_and_ordered():
    scores = {
        "A": [1.0, 0.0],
        "B": [2.0, 0.0],
        "C": [3.0, 0.0],
    }
    ranked = _percentile_scores(scores, range(2))
    assert ranked["A"][0] == 0.0
    assert ranked["B"][0] == 0.5
    assert ranked["C"][0] == 1.0
    assert ranked["A"][1] == 0.5


def test_risk_metrics_include_drawdown_and_target():
    metrics = _risk_metrics([10_000, 12_000, 9_000, 21_000])
    assert metrics["final_equity"] == 21_000
    assert metrics["total_return_pct"] == 110.0
    assert metrics["max_drawdown_pct"] == 25.0
    assert metrics["target_reached"] is True
    assert metrics["sharpe_ratio"] > 0


def test_identical_trading_rule_is_deterministic():
    dates = weekdays(date(2024, 1, 2), 90)
    bars = bars_for(dates)
    scores = {
        ticker: [0.9 - number * 0.1 for _ in dates]
        for number, ticker in enumerate(("AAPL", "MSFT", "SPY"))
    }
    first = simulate_ranked(
        dates=dates, bars=bars, scores=scores, start_offset=30
    )
    second = simulate_ranked(
        dates=dates, bars=bars, scores=scores, start_offset=30
    )
    assert first["metrics"] == second["metrics"]
    assert first["metrics"]["trades"] > 0
