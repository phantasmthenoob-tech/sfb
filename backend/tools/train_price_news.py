"""Walk-forward trainer for a small price/news direction model.

The model is deliberately dependency-free: standardized features and logistic
regression trained with mini-batch gradient descent. It predicts whether the
close five sessions later will be above today's close. The final section can
save the weights for an agent to load, but training and evaluation are separate
from the live simulation.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.ai.features import clamp, technical_score
from app.config import DEFAULT_UNIVERSE
from app.market.news_provider import generate_news_for_dates
from app.market.yahoo_provider import fetch_daily_bars

FEATURES = (
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
)


@dataclass
class Dataset:
    rows: list[list[float]]
    labels: list[int]
    offsets: list[int]
    tickers: list[str]


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def load_features(range_: str, tickers: tuple[str, ...], seed: int = 20260914) -> Dataset:
    dataset = fetch_daily_bars(tickers, range_=range_, timeout=30)
    indices = sorted({bar["bar_index"] for bar in dataset.bars})
    bars = defaultdict(dict)
    for bar in dataset.bars:
        bars[bar["ticker"]][bar["bar_index"]] = bar
    dated = sorted({(bar["session_date"], bar["bar_index"]) for bar in dataset.bars})
    news = generate_news_for_dates(
        tickers,
        [(date.fromisoformat(day), index) for day, index in dated],
        seed=seed,
    )
    news_by_bar = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    for item in news:
        key = item["ticker"] or "__MARKET__"
        cell = news_by_bar[item["bar_index"]][key]
        cell[0] += item["sentiment"]
        cell[1] += 1

    def sentiment_at(ticker: str, index: int, window: int = 5) -> dict:
        total = 0.0
        weight = 0.0
        count = 0
        for day in range(max(0, index - window), index + 1):
            for key, item_weight in ((ticker, 1.0), ("__MARKET__", 0.35)):
                score, items = news_by_bar[day].get(key, (0.0, 0))
                if items:
                    total += score * item_weight
                    weight += items * item_weight
                    count += items
        return {"score": total / weight if weight else 0.0, "count": count}

    spy = [bars["SPY"][index]["close"] for index in indices if index in bars.get("SPY", {})]
    spy_trend: list[float | None] = [None] * len(indices)
    for offset in range(len(indices)):
        if offset >= 50 and offset < len(spy):
            fast = sum(spy[offset - 19 : offset + 1]) / 20.0
            slow = sum(spy[offset - 49 : offset + 1]) / 50.0
            if slow:
                spy_trend[offset] = clamp(math.tanh((fast / slow - 1.0) * 60.0), -1.0, 1.0)

    rows: list[list[float]] = []
    labels: list[int] = []
    offsets: list[int] = []
    names: list[str] = []
    for ticker in tickers:
        ticker_bars = [bars[ticker][index] for index in indices if index in bars[ticker]]
        if len(ticker_bars) < len(indices):
            continue
        closes = [bar["close"] for bar in ticker_bars]
        for offset in range(20, len(indices) - 5):
            technical = technical_score(ticker_bars[: offset + 1][-120:])
            if technical is None:
                continue
            sentiment = sentiment_at(ticker, indices[offset])
            news_score = clamp(sentiment["score"] * 1.5, -1.0, 1.0)
            fast = technical["fast_sma"]
            slow = technical["slow_sma"]
            cross = (fast / slow - 1.0) if slow else 0.0
            returns = [
                closes[i] / closes[i - 1] - 1.0
                for i in range(offset - 19, offset + 1)
                if closes[i - 1]
            ]
            mean = sum(returns) / len(returns) if returns else 0.0
            variance = (
                sum((value - mean) ** 2 for value in returns) / len(returns)
                if returns
                else 0.0
            )
            vol = math.sqrt(variance)
            ret5 = closes[offset] / closes[offset - 5] - 1.0 if closes[offset - 5] else 0.0
            ret20 = closes[offset] / closes[offset - 20] - 1.0 if closes[offset - 20] else 0.0
            forward = closes[offset + 5] / closes[offset] - 1.0
            rows.append(
                [
                    technical["score"],
                    technical["momentum"],
                    cross,
                    vol,
                    ret5,
                    ret20,
                    news_score,
                    min(sentiment["count"], 5) / 5.0,
                    technical["score"] * news_score,
                    spy_trend[offset] or 0.0,
                ]
            )
            labels.append(1 if forward > 0 else 0)
            offsets.append(offset)
            names.append(ticker)
    # Keep rows ordered by time so a cutoff is a genuine walk-forward split.
    order = sorted(range(len(rows)), key=lambda row: (offsets[row], names[row]))
    return Dataset(
        [rows[row] for row in order],
        [labels[row] for row in order],
        [offsets[row] for row in order],
        [names[row] for row in order],
    )


def standardize(train: list[list[float]], test: list[list[float]]):
    width = len(train[0])
    means = [sum(row[index] for row in train) / len(train) for index in range(width)]
    scales = []
    for index in range(width):
        variance = sum((row[index] - means[index]) ** 2 for row in train) / len(train)
        scales.append(math.sqrt(variance) or 1.0)

    def transform(rows):
        return [
            [(row[index] - means[index]) / scales[index] for index in range(width)]
            for row in rows
        ]

    return transform(train), transform(test), means, scales


def fit_logistic(
    train: list[list[float]],
    labels: list[int],
    *,
    epochs: int = 30,
    learning_rate: float = 0.08,
    l2: float = 0.002,
    seed: int = 7,
) -> tuple[list[float], float]:
    rng = random.Random(seed)
    width = len(train[0])
    weights = [0.0] * width
    bias = 0.0
    order = list(range(len(train)))
    for _epoch in range(epochs):
        rng.shuffle(order)
        for position in order:
            row = train[position]
            target = labels[position]
            probability = sigmoid(bias + sum(weights[i] * row[i] for i in range(width)))
            error = probability - target
            for index in range(width):
                weights[index] -= learning_rate * (error * row[index] + l2 * weights[index])
            bias -= learning_rate * error
    return weights, bias


def predict(rows: list[list[float]], weights: list[float], bias: float) -> list[float]:
    return [sigmoid(bias + sum(weights[i] * row[i] for i in range(len(weights)))) for row in rows]


def accuracy(probabilities: list[float], labels: list[int]) -> float:
    hits = sum((probability >= 0.5) == bool(label) for probability, label in zip(probabilities, labels))
    return hits / len(labels) * 100.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", default="10y")
    parser.add_argument("--split", type=float, default=0.6)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--save", default="")
    args = parser.parse_args()
    tickers = DEFAULT_UNIVERSE
    data = load_features(args.range, tickers)
    sessions = sorted(set(data.offsets))
    cutoff = sessions[int(len(sessions) * args.split)]
    train_positions = [i for i, offset in enumerate(data.offsets) if offset < cutoff - 5]
    test_positions = [i for i, offset in enumerate(data.offsets) if offset >= cutoff]
    train_rows, test_rows, means, scales = standardize(
        [data.rows[i] for i in train_positions],
        [data.rows[i] for i in test_positions],
    )
    weights, bias = fit_logistic(
        train_rows, [data.labels[i] for i in train_positions], epochs=args.epochs
    )
    test_probabilities = predict(test_rows, weights, bias)
    test_labels = [data.labels[i] for i in test_positions]
    print(
        f"rows {len(data.rows)} cutoff {cutoff} train {len(train_positions)} "
        f"test {len(test_positions)}"
    )
    print(f"test accuracy {accuracy(test_probabilities, test_labels):.2f}%")
    for name, weight in zip(FEATURES, weights):
        print(f"  {name:<12} {weight:+.4f}")
    if args.save:
        payload = {
            "features": list(FEATURES),
            "weights": weights,
            "bias": bias,
            "means": means,
            "scales": scales,
            "range": args.range,
            "trained_rows": len(train_positions),
            "test_rows": len(test_positions),
            "cutoff_offset": cutoff,
            "split": args.split,
        }
        with open(args.save, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"saved {args.save}")


if __name__ == "__main__":
    main()
