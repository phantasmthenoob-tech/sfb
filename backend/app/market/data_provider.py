"""Deterministic historical replay data.

The first version ships a *synthetic* market so the simulator runs without an
external data vendor: same seed + same universe always produces the same bars,
which keeps leaderboard results reproducible and tests stable.

To use real data later, implement `load_bars` against a vendor API or a CSV
export and keep the same shape (ticker, ts, session_date, bar_index, OHLCV).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, timedelta

BASE_PRICES: dict[str, float] = {
    "AAPL": 275.40,
    "MSFT": 510.20,
    "NVDA": 178.50,
    "TSLA": 420.10,
    "AMZN": 228.40,
    "GOOGL": 205.60,
    "META": 612.30,
    "AMD": 155.20,
    "JPM": 315.40,
    "XOM": 118.70,
    "LLY": 940.20,
    "AVGO": 385.60,
    "WMT": 112.30,
    "SPY": 690.00,
    "QQQ": 625.00,
    "IWM": 248.00,
    "EFA": 96.20,
    "EEM": 57.40,
    "GLD": 405.00,
    "TLT": 94.50,
    "DIA": 465.00,
}


def _stable_base_price(ticker: str) -> float:
    """A deterministic fallback so synthetic runs do not depend on hash salt."""
    seed = sum((index + 1) * ord(char) for index, char in enumerate(ticker.upper()))
    return 40.0 + (seed % 400)


BASE_VOLUME: dict[str, int] = {
    "AAPL": 4_200_000,
    "MSFT": 2_100_000,
    "NVDA": 6_400_000,
    "TSLA": 7_800_000,
    "AMZN": 3_400_000,
    "GOOGL": 2_600_000,
    "META": 1_900_000,
    "AMD": 5_100_000,
    "JPM": 9_000_000,
    "XOM": 15_000_000,
    "LLY": 3_000_000,
    "AVGO": 22_000_000,
    "WMT": 8_000_000,
    "SPY": 70_000_000,
    "QQQ": 35_000_000,
    "IWM": 25_000_000,
    "EFA": 12_000_000,
    "EEM": 20_000_000,
    "GLD": 9_000_000,
    "TLT": 35_000_000,
    "DIA": 4_000_000,
}

SESSION_START = (9, 30)
SESSION_MINUTES = 390  # 09:30 -> 16:00


@dataclass(frozen=True)
class ReplayWindow:
    start_date: str
    end_date: str
    total_bars: int


def next_business_day(day: date) -> date:
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def session_dates(first: date, sessions: int) -> list[date]:
    dates: list[date] = []
    current = first
    while current.weekday() >= 5:
        current += timedelta(days=1)
    for _ in range(sessions):
        dates.append(current)
        current = next_business_day(current)
    return dates


def bar_times(bars_per_session: int) -> list[str]:
    step = SESSION_MINUTES / bars_per_session
    times: list[str] = []
    for i in range(bars_per_session):
        minutes = int(round(i * step))
        hour = SESSION_START[0] + (SESSION_START[1] + minutes) // 60
        minute = (SESSION_START[1] + minutes) % 60
        times.append(f"{hour:02d}:{minute:02d}:00")
    return times


def generate_bars(
    tickers: tuple[str, ...],
    *,
    sessions: int,
    bars_per_session: int,
    seed: int,
    start: date = date(2026, 9, 14),
) -> tuple[list[dict], ReplayWindow]:
    """Generate aligned OHLCV bars for every ticker on a shared bar index."""
    dates = session_dates(start, sessions)
    times = bar_times(bars_per_session)
    bars: list[dict] = []
    bar_index = 0

    for session_date in dates:
        for t_index, clock in enumerate(times):
            for ticker in tickers:
                bars.append(
                    {
                        "ticker": ticker,
                        "ts": f"{session_date.isoformat()}T{clock}",
                        "session_date": session_date.isoformat(),
                        "bar_index": bar_index,
                        "open": 0.0,
                        "high": 0.0,
                        "low": 0.0,
                        "close": 0.0,
                        "volume": 0,
                    }
                )
            bar_index += 1

    by_key = {(bar["ticker"], bar["bar_index"]): bar for bar in bars}

    for ticker in tickers:
        price_rng = random.Random(f"{seed}:{ticker}")
        base = BASE_PRICES.get(ticker, _stable_base_price(ticker))
        volume_base = BASE_VOLUME.get(ticker, 1_000_000)
        price = base
        daily_vol = price_rng.uniform(0.0012, 0.0028)
        for session_number, _session_date in enumerate(dates):
            drift = price_rng.gauss(0.0004, 0.0045)
            for t_index in range(bars_per_session):
                bar_index = session_number * bars_per_session + t_index
                open_price = price
                # Slight U-shaped intraday activity plus a random shock.
                intraday_weight = 1.0 + 0.6 * abs((t_index / max(bars_per_session - 1, 1)) - 0.5) * 2
                shock = price_rng.gauss(0.0, daily_vol) * intraday_weight
                close_price = open_price * math.exp(shock + drift / bars_per_session)
                wick = abs(price_rng.gauss(0.0, daily_vol)) * 0.8
                high = max(open_price, close_price) * (1.0 + wick)
                low = min(open_price, close_price) * (1.0 - wick)
                volume = int(volume_base * (0.45 + price_rng.random()) * intraday_weight)
                bar = by_key[(ticker, bar_index)]
                bar["open"] = round(open_price, 2)
                bar["high"] = round(max(high, open_price, close_price), 2)
                bar["low"] = round(min(low, open_price, close_price), 2)
                bar["close"] = round(close_price, 2)
                bar["volume"] = volume
                price = close_price

    bars.sort(key=lambda bar: (bar["bar_index"], bar["ticker"]))
    window = ReplayWindow(
        start_date=dates[0].isoformat(),
        end_date=dates[-1].isoformat(),
        total_bars=len(dates) * bars_per_session,
    )
    return bars, window


def index_levels(
    prices: dict[str, float], session_opens: dict[str, float], tickers: tuple[str, ...]
) -> list[dict]:
    """Synthetic S&P/NASDAQ-style indices derived from the replay universe."""
    def weighted_change(weights: dict[str, float]) -> float:
        total_weight = 0.0
        change = 0.0
        for ticker, weight in weights.items():
            if ticker not in prices or ticker not in session_opens or not session_opens[ticker]:
                continue
            change += (prices[ticker] / session_opens[ticker] - 1.0) * weight
            total_weight += weight
        return change / total_weight if total_weight else 0.0

    universe = list(tickers)
    sp_weights = {ticker: 1.0 for ticker in universe}
    nasdaq_weights = {ticker: 2.0 if ticker in {"NVDA", "MSFT", "AAPL", "META", "AMD"} else 0.5 for ticker in universe}
    return [
        {"symbol": "SPX", "name": "S&P 500 (sim)", "level": 6850.0, "change_pct": round(weighted_change(sp_weights) * 100.0, 2)},
        {"symbol": "IXIC", "name": "NASDAQ (sim)", "level": 23100.0, "change_pct": round(weighted_change(nasdaq_weights) * 100.0, 2)},
    ]

