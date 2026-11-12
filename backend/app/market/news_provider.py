"""Synthetic financial headlines with sentiment scores.

Each session gives every ticker a coherent "mood" so a news-driven strategy has
something to trade on, while individual headlines jitter around that mood. All
items carry the replay bar index at which they become visible, so the clock can
enforce that no agent sees tomorrow's news.
"""
from __future__ import annotations

import random
from datetime import date

from .data_provider import bar_times, session_dates

SOURCES = ("MarketWire", "FinPress", "StreetScope", "TapeDaily", "CapitalPost")

POSITIVE = (
    "{ticker} beats revenue expectations as demand accelerates",
    "Analysts raise {ticker} price target after strong guidance",
    "{ticker} announces expanded buyback and upbeat outlook",
    "Institutional buyers add to {ticker} on margin momentum",
    "{ticker} lands major contract, shares jump in premarket",
)

NEGATIVE = (
    "{ticker} misses earnings estimates as costs climb",
    "Regulators open probe into {ticker} business practices",
    "{ticker} guidance cut sparks analyst downgrades",
    "Supply constraints weigh on {ticker} quarterly shipments",
    "Insiders trim {ticker} stakes after weak demand data",
)

NEUTRAL = (
    "{ticker} to report quarterly results next week",
    "{ticker} schedules investor day; analysts stay mixed",
    "Options activity picks up in {ticker} ahead of earnings",
)

MARKET_HEADLINES = (
    "Broad market drifts as traders await inflation data",
    "Tech shares lead modest rebound in afternoon session",
    "Volatility cools as bond yields stabilise",
)


def generate_news_for_dates(
    tickers: tuple[str, ...],
    dated_bars: list[tuple[date, int]],
    *,
    seed: int,
) -> list[dict]:
    """Simulated headlines for real trading dates.

    Prices are real; free historical headline feeds are not available, so the
    news agent competes on deterministic simulated sentiment instead.
    """
    items: list[dict] = []
    for session_date, bar_index in dated_bars:
        rng = random.Random(f"{seed}:news:{session_date.isoformat()}")
        clock = "16:00:00"
        items.append(
            {
                "ticker": None,
                "headline": rng.choice(MARKET_HEADLINES),
                "source": rng.choice(SOURCES),
                "sentiment": round(rng.gauss(0.05, 0.3), 2),
                "ts": f"{session_date.isoformat()}T{clock}",
                "bar_index": bar_index,
            }
        )
        for ticker in tickers:
            mood = max(-0.95, min(0.95, rng.gauss(0.0, 0.55)))
            for _ in range(rng.randint(1, 3)):
                if mood > 0.18:
                    template = rng.choice(POSITIVE)
                elif mood < -0.18:
                    template = rng.choice(NEGATIVE)
                else:
                    template = rng.choice(NEUTRAL)
                sentiment = max(-1.0, min(1.0, mood + rng.gauss(0.0, 0.18)))
                if template in NEUTRAL:
                    sentiment *= 0.35
                items.append(
                    {
                        "ticker": ticker,
                        "headline": template.format(ticker=ticker),
                        "source": rng.choice(SOURCES),
                        "sentiment": round(sentiment, 2),
                        "ts": f"{session_date.isoformat()}T{clock}",
                        "bar_index": bar_index,
                    }
                )
    return items


def generate_news(
    tickers: tuple[str, ...],
    *,
    sessions: int,
    bars_per_session: int,
    seed: int,
    start: date = date(2026, 9, 14),
) -> list[dict]:
    rng = random.Random(f"{seed}:news")
    dates = session_dates(start, sessions)
    times = bar_times(bars_per_session)
    items: list[dict] = []

    for session_number, session_date in enumerate(dates):
        base_index = session_number * bars_per_session

        # One market-wide item per session.
        clock = times[rng.randrange(5, max(bars_per_session - 5, 6))]
        items.append(
            {
                "ticker": None,
                "headline": rng.choice(MARKET_HEADLINES),
                "source": rng.choice(SOURCES),
                "sentiment": round(rng.gauss(0.05, 0.3), 2),
                "ts": f"{session_date.isoformat()}T{clock}",
                "bar_index": base_index + times.index(clock),
            }
        )

        for ticker in tickers:
            mood = max(-0.95, min(0.95, rng.gauss(0.0, 0.55)))
            for _ in range(rng.randint(1, 3)):
                roll = rng.random()
                if mood > 0.18:
                    template = rng.choice(POSITIVE)
                elif mood < -0.18:
                    template = rng.choice(NEGATIVE)
                else:
                    template = rng.choice(NEUTRAL)
                sentiment = max(-1.0, min(1.0, mood + rng.gauss(0.0, 0.18)))
                if template in NEUTRAL:
                    sentiment *= 0.35
                clock = times[rng.randrange(3, max(bars_per_session - 3, 4))]
                items.append(
                    {
                        "ticker": ticker,
                        "headline": template.format(ticker=ticker),
                        "source": rng.choice(SOURCES),
                        "sentiment": round(sentiment, 2),
                        "ts": f"{session_date.isoformat()}T{clock}",
                        "bar_index": base_index + times.index(clock),
                    }
                )

    items.sort(key=lambda item: (item["bar_index"], item["ts"]))
    return items
