"""Fast offline backtest for the long-only price/news strategies.

This intentionally avoids the SQLite simulation loop so parameter sweeps and
walk-forward experiments can run in seconds instead of minutes. It uses the same
feature functions and next-open execution convention as the live engine.
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.ai.features import clamp, technical_score
from app.config import DEFAULT_UNIVERSE
from app.market.news_provider import generate_news_for_dates
from app.market.yahoo_provider import fetch_daily_bars

FEE_RATE = 0.0005


@dataclass
class Result:
    return_pct: float
    max_drawdown_pct: float
    trades: int
    bars: int


def load_market(range_: str, tickers: tuple[str, ...], seed: int = 20260914):
    dataset = fetch_daily_bars(tickers, range_=range_, timeout=30)
    indices = sorted({bar["bar_index"] for bar in dataset.bars})
    index_set = set(indices)
    bars = defaultdict(dict)
    for bar in dataset.bars:
        bars[bar["ticker"]][bar["bar_index"]] = bar
    dates = sorted({(bar["session_date"], bar["bar_index"]) for bar in dataset.bars})
    news = generate_news_for_dates(
        tickers,
        [(date.fromisoformat(day), index) for day, index in dates],
        seed=seed,
    )
    return indices, bars, news


def build_scores(indices, bars, news, tickers):
    """Precompute price, news-confirmed and blended scores for every bar."""
    count = len(indices)
    price_scores = {ticker: [None] * count for ticker in tickers}
    news_scores = {ticker: [None] * count for ticker in tickers}
    blended_scores = {ticker: [None] * count for ticker in tickers}
    news_by_bar = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    for item in news:
        key = item["ticker"] or "__MARKET__"
        cell = news_by_bar[item["bar_index"]][key]
        cell[0] += item["sentiment"]
        cell[1] += 1

    def sentiment_at(ticker: str, index: int, window: int = 5) -> dict:
        total = 0.0
        weight = 0.0
        headlines = 0
        for day in range(max(0, index - window), index + 1):
            for key, item_weight in ((ticker, 1.0), ("__MARKET__", 0.35)):
                score, items = news_by_bar[day].get(key, (0.0, 0))
                if items:
                    total += score * item_weight
                    weight += items * item_weight
                    headlines += items
        return {
            "score": total / weight if weight else 0.0,
            "count": headlines,
        }

    for ticker in tickers:
        ticker_bars = [bars[ticker][index] for index in indices if index in bars[ticker]]
        for offset, index in enumerate(indices):
            if offset < 20:
                continue
            technical = technical_score(ticker_bars[: offset + 1][-120:])
            if technical is None:
                continue
            sentiment = sentiment_at(ticker, index)
            news_component = clamp(sentiment["score"] * 1.5, -1.0, 1.0)
            price_scores[ticker][offset] = technical["score"]
            news_score = news_component
            if news_component * technical["score"] <= 0:
                news_score *= 0.25
            elif abs(technical["score"]) < 0.12:
                news_score *= 0.6
            news_scores[ticker][offset] = news_score
            blended_scores[ticker][offset] = clamp(
                0.9 * technical["score"] + 0.1 * news_component, -1.0, 1.0
            )
    return price_scores, news_scores, blended_scores


def simulate(
    *,
    indices,
    bars,
    scores,
    tickers,
    entry: float,
    exit_threshold: float,
    max_entries: int,
    target_position_pct: float,
    fee_rate: float = FEE_RATE,
) -> Result:
    count = len(indices)
    cash = 10_000.0
    positions: dict[str, int] = {}
    pending: list[tuple[str, str, int]] = []
    equity_curve: list[float] = []
    trades = 0
    peak = cash
    max_drawdown = 0.0

    for offset, index in enumerate(indices):
        # Orders submitted on the previous close fill at this bar's open.
        for side, ticker, quantity in pending:
            open_price = bars[ticker].get(index, {}).get("open")
            if not open_price:
                continue
            notional = quantity * open_price
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
        pending.clear()

        equity = cash
        for ticker, quantity in positions.items():
            close = bars[ticker].get(index, {}).get("close")
            if close:
                equity += quantity * close
        equity_curve.append(equity)
        peak = max(peak, equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100.0)
        if offset == count - 1:
            break

        ranked = [
            (scores[ticker][offset], ticker)
            for ticker in tickers
            if scores[ticker][offset] is not None
        ]
        ranked.sort(reverse=True)
        exiting = set()
        for score, ticker in ranked:
            quantity = positions.get(ticker, 0)
            if quantity > 0 and score <= exit_threshold:
                pending.append(("SELL", ticker, quantity))
                exiting.add(ticker)

        available = cash
        entries = 0
        for score, ticker in ranked:
            if score < entry or entries >= max_entries:
                break
            if ticker in positions or ticker in exiting:
                continue
            price = bars[ticker].get(index, {}).get("close")
            if not price:
                continue
            budget = min(equity * target_position_pct, available * 0.95)
            quantity = int(budget / price)
            if quantity < 1:
                continue
            pending.append(("BUY", ticker, quantity))
            available -= quantity * price * (1.0 + fee_rate)
            entries += 1

    final = equity_curve[-1] if equity_curve else 10_000.0
    return Result(
        return_pct=(final / 10_000.0 - 1.0) * 100.0,
        max_drawdown_pct=max_drawdown,
        trades=trades,
        bars=count,
    )


def current_configs(scores):
    return {
        "Price AI": (scores[0], 0.45, -0.05, 2, 0.16),
        "News AI": (scores[1], 0.35, -0.05, 2, 0.16),
        "Combined AI": (scores[2], 0.45, -0.05, 3, 0.13),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", default="10y", help="Yahoo chart range (default: 10y)")
    parser.add_argument("--tickers", default=",".join(DEFAULT_UNIVERSE))
    args = parser.parse_args()
    tickers = tuple(ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip())
    started = time.time()
    indices, bars, news = load_market(args.range, tickers)
    scores = build_scores(indices, bars, news, tickers)
    print(
        f"Loaded {len(indices)} sessions, {len(tickers)} tickers and {len(news)} headlines "
        f"in {time.time() - started:.1f}s"
    )
    for name, (score_set, entry, exit_threshold, max_entries, target) in current_configs(scores).items():
        result = simulate(
            indices=indices,
            bars=bars,
            scores=score_set,
            tickers=tickers,
            entry=entry,
            exit_threshold=exit_threshold,
            max_entries=max_entries,
            target_position_pct=target,
        )
        print(
            f"{name:<12} {result.return_pct:+8.2f}%  "
            f"max DD {result.max_drawdown_pct:5.2f}%  trades {result.trades:5d}"
        )


if __name__ == "__main__":
    main()
