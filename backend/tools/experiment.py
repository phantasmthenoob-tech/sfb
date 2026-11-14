"""Walk-forward experiment for price, news, hybrid and ML strategies.

The experiment deliberately differs from the live simulation in one way: it
uses a single, identical cross-sectional trading rule for every model. Each
model only supplies a daily score; scores are converted to a percentile rank
across the stock universe, and the same top-five / 5 bps-per-side rule is
applied to all six models.

Walk-forward protocol
---------------------
The evaluation is the last five years of the dataset. Model fitting starts with
all data before that period and expands by one year at a time:

    train: first session .. validation_start - 1
    validation: one calendar year
    next fold: add the prior validation year to the training window

A training row's five-session label must finish before the validation period
starts. This purge is what prevents the model from learning from a label whose
future overlaps the unseen period. Features at time t also only use bars,
volume and headlines at or before t.

Run with the experiment dependencies::

    pip install -r requirements-experiments.txt
    python -m tools.experiment --range 10y --output artifacts/experiments/results.json
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.ai.features import clamp, technical_score
from app.config import DEFAULT_UNIVERSE, FORECAST_HORIZON_SESSIONS
from app.market.news_provider import generate_news_for_dates
from app.market.yahoo_provider import fetch_daily_bars

START_CAPITAL = 10_000.0
TARGET_EQUITY = 20_000.0
FEE_RATE = 0.0005  # 5 bps per side, matching the live simulator
HORIZON = FORECAST_HORIZON_SESSIONS
MAX_POSITIONS = 5
TARGET_POSITION_PCT = 0.18
ENTRY_PERCENTILE = 0.80
EXIT_PERCENTILE = 0.55
TRADING_DAYS_PER_YEAR = 252

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
)


@dataclass(frozen=True)
class Sample:
    offset: int
    ticker: str
    features: tuple[float, ...]
    label: float | None
    price_score: float
    news_score: float
    combined_score: float


@dataclass(frozen=True)
class Fold:
    index: int
    start_offset: int
    end_offset: int
    start_date: str
    end_date: str
    train_samples: int = 0
    validation_samples: int = 0


def _parse(day: str) -> date:
    return date.fromisoformat(day[:10])


def _return(closes: list[float], offset: int, periods: int) -> float:
    if offset < periods or not closes[offset - periods]:
        return 0.0
    return closes[offset] / closes[offset - periods] - 1.0


def _rsi(closes: list[float], offset: int, window: int = 14) -> float:
    if offset < window:
        return 0.0
    gains = 0.0
    losses = 0.0
    for index in range(offset - window + 1, offset + 1):
        change = closes[index] - closes[index - 1]
        if change > 0:
            gains += change
        else:
            losses -= change
    if losses == 0:
        return 1.0
    ratio = gains / losses
    return clamp((100.0 - 100.0 / (1.0 + ratio)) / 50.0 - 1.0, -1.0, 1.0)


def _volume_trend(volumes: list[int], offset: int, window: int = 20) -> float:
    if offset < window:
        return 0.0
    average = sum(volumes[offset - window : offset]) / window
    if not average:
        return 0.0
    return clamp(math.tanh((volumes[offset] / average - 1.0) * 2.0), -1.0, 1.0)


def _market_trend(closes: list[float | None], offset: int) -> float:
    if offset < 49:
        return 0.0
    window = closes[offset - 49 : offset + 1]
    if len(window) < 50 or any(value is None for value in window):
        return 0.0
    fast = sum(window[-20:]) / 20.0
    slow = sum(window) / 50.0
    if not slow:
        return 0.0
    return clamp(math.tanh((fast / slow - 1.0) * 60.0), -1.0, 1.0)


def build_feature_rows(
    *,
    dates: list[str],
    bars: dict[str, dict[int, dict]],
    news_by_offset: list[dict[str, tuple[float, int]]],
    tickers: tuple[str, ...],
    horizon: int = HORIZON,
) -> list[Sample]:
    """Build one row per ticker/session from information available at that close."""
    if not dates:
        return []
    count = len(dates)
    market_closes: list[float | None] = [
        bars.get("SPY", {}).get(offset, {}).get("close") for offset in range(count)
    ]
    market_trend = [_market_trend(market_closes, offset) for offset in range(count)]

    def sentiment_at(ticker: str, offset: int, window: int = 5) -> tuple[float, int]:
        total = 0.0
        weight = 0.0
        headlines = 0
        for day in range(max(0, offset - window), offset + 1):
            cell = news_by_offset[day].get(ticker)
            if cell:
                score, items = cell
                total += score * 1.0
                weight += items * 1.0
                headlines += items
            market = news_by_offset[day].get("__MARKET__")
            if market:
                score, items = market
                total += score * 0.35
                weight += items * 0.35
                headlines += items
        return (total / weight if weight else 0.0, headlines)

    rows: list[Sample] = []
    for ticker in tickers:
        series = bars.get(ticker)
        if not series:
            continue
        # Only use an aligned series; a missing session would shift labels and
        # silently create a false future-looking feature.
        if any(offset not in series for offset in range(count)):
            continue
        ticker_bars = [series[offset] for offset in range(count)]
        closes = [bar["close"] for bar in ticker_bars]
        volumes = [int(bar["volume"] or 0) for bar in ticker_bars]
        for offset in range(20, count):
            technical = technical_score(ticker_bars[max(0, offset - 119) : offset + 1])
            if technical is None:
                continue
            sentiment, headlines = sentiment_at(ticker, offset)
            news_component = clamp(sentiment * 1.5, -1.0, 1.0)
            price_score = technical["score"]
            news_score = news_component
            if news_component * price_score <= 0:
                news_score *= 0.25
            elif abs(price_score) < 0.12:
                news_score *= 0.6
            combined_score = clamp(0.9 * price_score + 0.1 * news_component, -1.0, 1.0)
            cross = (
                technical["fast_sma"] / technical["slow_sma"] - 1.0
                if technical["slow_sma"]
                else 0.0
            )
            rows.append(
                Sample(
                    offset=offset,
                    ticker=ticker,
                    features=(
                        technical["score"],
                        technical["momentum"],
                        cross,
                        technical["volatility"] or 0.0,
                        _return(closes, offset, 5),
                        _return(closes, offset, 20),
                        news_component,
                        min(headlines, 5) / 5.0,
                        price_score * news_component,
                        market_trend[offset],
                        _volume_trend(volumes, offset),
                    ),
                    label=(
                        clamp(
                            closes[offset + horizon] / closes[offset] - 1.0,
                            -0.25,
                            0.25,
                        )
                        if offset + horizon < count
                        else None
                    ),
                    price_score=price_score,
                    news_score=news_score,
                    combined_score=combined_score,
                )
            )
    return rows


def training_rows(rows: list[Sample], validation_start: int, horizon: int = HORIZON) -> list[Sample]:
    """Rows whose entire label window ends before a validation period starts."""
    latest_label_offset = validation_start - 1
    return [
        row
        for row in rows
        if row.label is not None and row.offset + horizon <= latest_label_offset
    ]


def build_folds(
    dates: list[str], *, evaluation_years: int = 5, fold_days: int = 365
) -> list[Fold]:
    """Create expanding-window validation folds ending at the newest session."""
    if len(dates) < 2:
        raise ValueError("Need at least two sessions")
    latest = _parse(dates[-1])
    target = latest - timedelta(days=evaluation_years * 365)
    start = next(
        (index for index, day in enumerate(dates) if _parse(day) >= target),
        len(dates) - 1,
    )
    if start <= 20:
        raise ValueError(
            "Not enough leading history for an initial training window; use a longer --range"
        )
    starts = [start]
    for number in range(1, evaluation_years + 1):
        boundary = _parse(dates[start]) + timedelta(days=number * fold_days)
        index = next(
            (i for i, day in enumerate(dates) if _parse(day) >= boundary),
            len(dates),
        )
        if index < len(dates) and index > starts[-1]:
            starts.append(index)
    if len(starts) > 1 and starts[-1] == len(dates) - 1:
        starts.pop()
    folds: list[Fold] = []
    for number, begin in enumerate(starts):
        end = (starts[number + 1] - 1) if number + 1 < len(starts) else len(dates) - 1
        if end <= begin:
            continue
        folds.append(
            Fold(
                index=number + 1,
                start_offset=begin,
                end_offset=end,
                start_date=dates[begin],
                end_date=dates[end],
            )
        )
    return folds


def _percentile_scores(
    scores: dict[str, list[float | None]], offsets: range
) -> dict[str, list[float | None]]:
    ranked: dict[str, list[float | None]] = {
        ticker: [None] * len(next(iter(scores.values()))) for ticker in scores
    }
    for offset in offsets:
        values = [
            (value, ticker)
            for ticker, series in scores.items()
            if (value := series[offset]) is not None
        ]
        if len(values) < 2:
            continue
        values.sort(key=lambda item: (item[0], item[1]))
        denominator = len(values) - 1
        start = 0
        while start < len(values):
            end = start
            while end + 1 < len(values) and values[end + 1][0] == values[start][0]:
                end += 1
            percentile = ((start + end) / 2.0) / denominator
            for _, ticker in values[start : end + 1]:
                ranked[ticker][offset] = percentile
            start = end + 1
    return ranked


def _fit_ml_models(rows: list[Sample], seed: int) -> dict[str, object]:
    """Fit the three ML baselines on an already-purged training set."""
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.neural_network import MLPRegressor

    matrix = np.asarray([row.features for row in rows], dtype=float)
    labels = np.asarray([row.label for row in rows if row.label is not None], dtype=float)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales == 0] = 1.0
    normalized = (matrix - means) / scales
    models: dict[str, object] = {
        "Random Forest": RandomForestRegressor(
            n_estimators=140,
            max_depth=8,
            min_samples_leaf=40,
            max_features=0.7,
            n_jobs=-1,
            random_state=seed,
        ),
        "Gradient Boosting": HistGradientBoostingRegressor(
            max_iter=160,
            learning_rate=0.05,
            max_leaf_nodes=31,
            l2_regularization=0.1,
            early_stopping=True,
            validation_fraction=0.1,
            random_state=seed,
        ),
        "Neural Network": MLPRegressor(
            hidden_layer_sizes=(48, 24),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            batch_size=512,
            learning_rate_init=1e-3,
            max_iter=120,
            early_stopping=True,
            n_iter_no_change=8,
            random_state=seed,
        ),
    }
    for name, model in models.items():
        started = time.time()
        model.fit(normalized, labels)
        print(f"    fitted {name} on {len(rows):,} rows in {time.time() - started:.1f}s", flush=True)
    return {"models": models, "means": means, "scales": scales, "feature_names": FEATURE_NAMES}


def _predict_ml(
    fitted: dict[str, object], rows: list[Sample]
) -> dict[str, list[float]]:
    import numpy as np

    matrix = np.asarray([row.features for row in rows], dtype=float)
    normalized = (matrix - fitted["means"]) / fitted["scales"]
    predictions: dict[str, list[float]] = {}
    for name, model in fitted["models"].items():
        predictions[name] = [
            float(value) if math.isfinite(float(value)) else 0.0
            for value in model.predict(normalized)
        ]
    return predictions


def _ranked_score_maps(
    rows: list[Sample],
    folds: list[Fold],
    seed: int,
    eval_offsets: range,
    dates: list[str],
) -> tuple[dict[str, dict[str, list[float | None]]], list[dict]]:
    """Build model scores without ever fitting on a validation row."""
    count = max(row.offset for row in rows) + 1
    names = ("Price AI", "News AI", "Combined AI", "Random Forest", "Gradient Boosting", "Neural Network")
    raw: dict[str, dict[str, list[float | None]]] = {
        name: {ticker: [None] * count for ticker in DEFAULT_UNIVERSE} for name in names
    }
    for row in rows:
        raw["Price AI"][row.ticker][row.offset] = row.price_score
        raw["News AI"][row.ticker][row.offset] = row.news_score
        raw["Combined AI"][row.ticker][row.offset] = row.combined_score

    fold_summaries: list[dict] = []
    for fold in folds:
        train = training_rows(rows, fold.start_offset)
        validation = [
            row
            for row in rows
            if fold.start_offset <= row.offset <= fold.end_offset
        ]
        if not train or not validation:
            raise ValueError(f"Fold {fold.index} has no train/validation rows")
        print(
            f"  fold {fold.index}: train {len(train):,} rows through {train[-1].offset} "
            f"validation {fold.start_date} -> {fold.end_date} ({len(validation):,} rows)",
            flush=True,
        )
        fitted = _fit_ml_models(train, seed)
        predictions = _predict_ml(fitted, validation)
        for name, values in predictions.items():
            for row, value in zip(validation, values):
                raw[name][row.ticker][row.offset] = value
        fold_summaries.append(
            {
                "fold": fold.index,
                "train_start": dates[min(row.offset for row in train)],
                "train_end": dates[fold.start_offset - 1],
                "validation_start": fold.start_date,
                "validation_end": fold.end_date,
                "train_rows": len(train),
                "validation_rows": len(validation),
                "train_last_label_offset": max(row.offset + HORIZON for row in train),
                "validation_start_offset": fold.start_offset,
            }
        )

    return (
        {name: _percentile_scores(scores, eval_offsets) for name, scores in raw.items()},
        fold_summaries,
    )


def _max_drawdown(values: list[float]) -> float:
    peak = values[0] if values else 0.0
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            drawdown = max(drawdown, (peak - value) / peak * 100.0)
    return drawdown


def _risk_metrics(equity: list[float], starting: float = START_CAPITAL) -> dict:
    returns = [
        equity[index] / equity[index - 1] - 1.0
        for index in range(1, len(equity))
        if equity[index - 1]
    ]
    final = equity[-1] if equity else starting
    mean = statistics.mean(returns) if returns else 0.0
    volatility = statistics.pstdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR) if returns else 0.0
    sharpe = (
        (mean / statistics.pstdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR))
        if len(returns) > 1 and statistics.pstdev(returns)
        else 0.0
    )
    annualized = (
        (final / starting) ** (TRADING_DAYS_PER_YEAR / max(1, len(equity))) - 1.0
        if final > 0
        else -1.0
    )
    drawdown = _max_drawdown(equity)
    return {
        "starting_equity": round(starting, 2),
        "final_equity": round(final, 2),
        "total_return_pct": round((final / starting - 1.0) * 100.0, 2),
        "annualized_return_pct": round(annualized * 100.0, 2),
        "volatility_pct": round(volatility * 100.0, 2),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown_pct": round(drawdown, 2),
        "calmar_ratio": round((annualized * 100.0 / drawdown), 3) if drawdown else None,
        "days": len(equity),
        "target_reached": final >= TARGET_EQUITY,
        "return_multiple": round(final / starting, 3),
    }


def simulate_ranked(
    *,
    dates: list[str],
    bars: dict[str, dict[int, dict]],
    scores: dict[str, list[float | None]],
    start_offset: int,
    fee_rate: float = FEE_RATE,
) -> dict:
    """Run the identical top-five rule on one model's percentile scores."""
    cash = START_CAPITAL
    positions: dict[str, int] = {}
    pending: list[tuple[str, str, int]] = []
    equity_curve: list[float] = []
    equity_by_offset: dict[int, float] = {}
    traded_notional = 0.0
    trades = 0
    exposure_total = 0.0
    for offset in range(start_offset, len(dates)):
        for side, ticker, quantity in pending:
            bar = bars[ticker].get(offset)
            if not bar:
                continue
            price = bar["open"]
            if not price:
                continue
            notional = quantity * price
            fee = notional * fee_rate
            if side == "BUY":
                if notional + fee > cash:
                    continue
                cash -= notional + fee
                positions[ticker] = positions.get(ticker, 0) + quantity
            else:
                if positions.get(ticker, 0) < quantity:
                    continue
                cash += notional - fee
                positions[ticker] -= quantity
                if positions[ticker] == 0:
                    positions.pop(ticker, None)
            trades += 1
            traded_notional += notional
        pending.clear()

        equity = cash
        for ticker, quantity in positions.items():
            bar = bars[ticker].get(offset)
            if bar:
                equity += quantity * bar["close"]
        equity_curve.append(equity)
        equity_by_offset[offset] = equity
        if equity:
            exposure_total += sum(
                quantity * (bars[ticker].get(offset, {}).get("close") or 0.0)
                for ticker, quantity in positions.items()
            ) / equity
        if offset == len(dates) - 1:
            break

        ranked = [
            (value, ticker)
            for ticker, series in scores.items()
            if (value := series[offset]) is not None
        ]
        ranked.sort(reverse=True)
        active_tickers = {ticker for _, ticker in ranked}
        exiting: set[str] = set()
        for value, ticker in ranked:
            if positions.get(ticker, 0) > 0 and value < EXIT_PERCENTILE:
                pending.append(("SELL", ticker, positions[ticker]))
                exiting.add(ticker)
        for ticker in positions:
            if ticker not in active_tickers and ticker not in exiting:
                pending.append(("SELL", ticker, positions[ticker]))
                exiting.add(ticker)

        available = cash
        entries = 0
        for value, ticker in ranked:
            if value < ENTRY_PERCENTILE or entries >= MAX_POSITIONS:
                break
            if ticker in positions or ticker in exiting:
                continue
            bar = bars[ticker].get(offset)
            if not bar or not bar["close"]:
                continue
            price = bar["close"]
            budget = min(equity * TARGET_POSITION_PCT, available * 0.95)
            quantity = int(budget / price)
            if quantity < 1:
                continue
            pending.append(("BUY", ticker, quantity))
            available -= quantity * price * (1.0 + fee_rate)
            entries += 1

    metrics = _risk_metrics(equity_curve)
    metrics.update(
        {
            "trades": trades,
            "turnover_x": round(traded_notional / max(1.0, (START_CAPITAL + equity_curve[-1]) / 2), 2),
            "average_exposure_pct": round(exposure_total / max(1, len(equity_curve)) * 100.0, 2),
        }
    )
    return {"metrics": metrics, "equity_by_offset": equity_by_offset}


def _spy_regime(
    dates: list[str], bars: dict[str, dict[int, dict]], start_offset: int
) -> dict[int, str]:
    series = bars.get("SPY", {})
    closes = [
        series[offset]["close"]
        for offset in range(len(dates))
        if offset in series
    ]
    regime: dict[int, str] = {}
    for offset in range(start_offset, len(dates)):
        if offset not in series:
            regime[offset] = "sideways"
            continue
        if offset >= 199:
            average = sum(closes[offset - 199 : offset + 1]) / 200.0
            regime[offset] = "bull" if series[offset]["close"] >= average else "bear"
        else:
            regime[offset] = "sideways"
    return regime


def _regime_metrics(
    equity_by_offset: dict[int, float], regime: dict[int, str]
) -> dict:
    by_regime: dict[str, list[float]] = defaultdict(list)
    offsets = sorted(equity_by_offset)
    for previous, current in zip(offsets, offsets[1:]):
        if previous in equity_by_offset and equity_by_offset[previous]:
            by_regime[regime.get(current, "sideways")].append(
                equity_by_offset[current] / equity_by_offset[previous] - 1.0
            )
    result: dict[str, dict] = {}
    for name, returns in by_regime.items():
        if not returns:
            continue
        cumulative = math.prod(1.0 + value for value in returns) - 1.0
        volatility = statistics.pstdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR)
        sharpe = (
            statistics.mean(returns)
            / statistics.pstdev(returns)
            * math.sqrt(TRADING_DAYS_PER_YEAR)
            if len(returns) > 1 and statistics.pstdev(returns)
            else 0.0
        )
        result[name] = {
            "days": len(returns),
            "total_return_pct": round(cumulative * 100.0, 2),
            "volatility_pct": round(volatility * 100.0, 2),
            "sharpe_ratio": round(sharpe, 3),
        }
    return result


def _benchmark(
    dates: list[str], bars: dict[str, dict[int, dict]], start_offset: int
) -> dict:
    series = bars.get("SPY", {})
    available = [offset for offset in range(start_offset, len(dates)) if offset in series]
    if len(available) < 2:
        return {"name": "SPY buy-and-hold", "total_return_pct": 0.0}
    first = series[available[0]]["close"]
    last = series[available[-1]]["close"]
    gross = last / first - 1.0 if first else 0.0
    after_costs = gross - 2.0 * FEE_RATE
    return {
        "name": "SPY buy-and-hold (one entry and exit, 5 bps each)",
        "start_date": dates[available[0]],
        "end_date": dates[available[-1]],
        "total_return_pct": round(after_costs * 100.0, 2),
        "gross_return_pct": round(gross * 100.0, 2),
        "cost_pct": round(2.0 * FEE_RATE * 100.0, 2),
    }


def _fold_metrics(
    fold: Fold,
    equity_by_offset: dict[int, float],
    benchmark: dict,
) -> dict:
    start = equity_by_offset.get(fold.start_offset)
    end = equity_by_offset.get(fold.end_offset)
    value = (end / start - 1.0) * 100.0 if start and end is not None else 0.0
    return {
        "fold": fold.index,
        "start_date": fold.start_date,
        "end_date": fold.end_date,
        "return_pct": round(value, 2),
        "benchmark_spy_return_pct": benchmark.get("fold_returns", {}).get(fold.index),
    }


def run_experiment(
    *,
    range_: str = "10y",
    seed: int = 20260914,
    output: str | None = None,
) -> dict:
    started = time.time()
    tickers = DEFAULT_UNIVERSE
    print(f"Downloading {len(tickers)} tickers for {range_}...", flush=True)
    dataset = fetch_daily_bars(tickers, range_=range_, timeout=30)
    dates = sorted({bar["session_date"] for bar in dataset.bars})
    index_for_date = {day: index for index, day in enumerate(dates)}
    bars: dict[str, dict[int, dict]] = defaultdict(dict)
    for bar in dataset.bars:
        bars[bar["ticker"]][index_for_date[bar["session_date"]]] = bar
    dated = [( _parse(day), index) for day, index in index_for_date.items()]
    news = generate_news_for_dates(tickers, dated, seed=seed)
    news_by_offset: list[dict[str, tuple[float, int]]] = [
        defaultdict(lambda: (0.0, 0)) for _ in dates
    ]
    for item in news:
        key = item["ticker"] or "__MARKET__"
        score, count = news_by_offset[item["bar_index"]][key]
        news_by_offset[item["bar_index"]][key] = (score + item["sentiment"], count + 1)
    print(
        f"Loaded {len(dates):,} sessions, {len(tickers)} tickers and {len(news):,} "
        f"headlines in {time.time() - started:.1f}s",
        flush=True,
    )

    folds = build_folds(dates)
    eval_start = folds[0].start_offset
    eval_offsets = range(eval_start, len(dates))
    print(
        f"Walk-forward evaluation: {folds[0].start_date} -> {folds[-1].end_date}; "
        f"{len(folds)} unseen periods",
        flush=True,
    )
    rows = build_feature_rows(
        dates=dates, bars=bars, news_by_offset=news_by_offset, tickers=tickers
    )
    print(f"Built {len(rows):,} feature rows", flush=True)
    scores, fold_summaries = _ranked_score_maps(rows, folds, seed, eval_offsets, dates)
    benchmark = _benchmark(dates, bars, eval_start)
    regime = _spy_regime(dates, bars, eval_start)

    spy_fold_returns: dict[int, float] = {}
    spy_series = bars.get("SPY", {})
    for fold in folds:
        start = spy_series.get(fold.start_offset)
        end = spy_series.get(fold.end_offset)
        if start and end:
            spy_fold_returns[fold.index] = round((end["close"] / start["close"] - 1.0) * 100.0, 2)
    benchmark["fold_returns"] = spy_fold_returns

    results: dict[str, dict] = {}
    for name, model_scores in scores.items():
        simulation = simulate_ranked(
            dates=dates,
            bars=bars,
            scores=model_scores,
            start_offset=eval_start,
        )
        metrics = simulation["metrics"]
        folds_payload = [
            _fold_metrics(fold, simulation["equity_by_offset"], benchmark) for fold in folds
        ]
        for fold in folds_payload:
            fold["regime"] = (
                "bull"
                if (fold["benchmark_spy_return_pct"] or 0.0) > 10.0
                else "bear"
                if (fold["benchmark_spy_return_pct"] or 0.0) < -10.0
                else "sideways"
            )
        metrics["folds"] = folds_payload
        metrics["regimes"] = _regime_metrics(simulation["equity_by_offset"], regime)
        results[name] = metrics

    success = {
        "target_20k": {name: bool(value["target_reached"]) for name, value in results.items()},
        "beats_100pct": {name: value["total_return_pct"] >= 100.0 for name, value in results.items()},
        "beats_spy": {
            name: value["total_return_pct"] > benchmark["total_return_pct"]
            for name, value in results.items()
        },
        "multiple_100pct_folds": {
            name: sum(1 for fold in value["folds"] if fold["return_pct"] >= 100.0) >= 2
            for name, value in results.items()
        },
        "drawdown_under_25": {
            name: value["max_drawdown_pct"] < 25.0 for name, value in results.items()
        },
    }
    output_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "range": range_,
            "seed": seed,
            "starting_capital": START_CAPITAL,
            "target_equity": TARGET_EQUITY,
            "fee_bps_per_side": FEE_RATE * 10_000,
            "horizon_sessions": HORIZON,
            "max_positions": MAX_POSITIONS,
            "target_position_pct": TARGET_POSITION_PCT,
            "entry_percentile": ENTRY_PERCENTILE,
            "exit_percentile": EXIT_PERCENTILE,
            "rule": "Long-only, top-five percentile ranks, next-open fills; identical for every model.",
        },
        "versions": {
            "python": __import__("sys").version.split()[0],
            "numpy": importlib.metadata.version("numpy"),
            "scikit-learn": importlib.metadata.version("scikit-learn"),
        },
        "data": {
            "source": dataset.source,
            "interval": dataset.interval,
            "fetched_at": dataset.fetched_at,
            "tickers": list(tickers),
            "first_session": dates[0],
            "last_session": dates[-1],
            "sessions": len(dates),
            "bars": len(dataset.bars),
            "feature_rows": len(rows),
            "features": list(FEATURE_NAMES),
        },
        "folds": fold_summaries,
        "benchmark": benchmark,
        "models": results,
        "success": success,
    }
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
        print(f"Wrote {path}", flush=True)

    print("\nModel results (5-year evaluation, after 5 bps/side costs):")
    print(f"{'Model':<20} {'Return':>9} {'CAGR':>8} {'Sharpe':>8} {'MaxDD':>8} {'Final':>12} {'Trades':>7}")
    for name, value in results.items():
        print(
            f"{name:<20} {value['total_return_pct']:>8.2f}% "
            f"{value['annualized_return_pct']:>7.2f}% {value['sharpe_ratio']:>8.2f} "
            f"{value['max_drawdown_pct']:>7.2f}% ${value['final_equity']:>11,.0f} "
            f"{value['trades']:>7}"
        )
    print(f"\nSPY benchmark: {benchmark['total_return_pct']:+.2f}% after costs")
    return output_payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", default="10y", help="Yahoo chart range (default: 10y)")
    parser.add_argument("--seed", type=int, default=20260914)
    parser.add_argument("--output", default="../artifacts/experiments/results.json")
    args = parser.parse_args()
    try:
        run_experiment(range_=args.range, seed=args.seed, output=args.output)
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"Missing experimental dependency: {exc.name}. "
            "Install with: pip install -r requirements-experiments.txt"
        ) from exc


if __name__ == "__main__":
    main()
