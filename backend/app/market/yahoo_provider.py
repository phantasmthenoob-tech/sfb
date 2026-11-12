"""Real daily OHLCV bars from Yahoo Finance's public chart endpoint.

Only completed trading sessions are used: while the US market is open the
current (partial) day is dropped, so portfolio values can only move on a
finished day's close. The endpoint is unofficial, so failures are handled by the
simulation engine with a cached dataset or the synthetic fallback.
"""
from __future__ import annotations

import logging
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from .yahoo_http import HOSTS, request_json

logger = logging.getLogger(__name__)

NEW_YORK = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 5)


class MarketDataError(Exception):
    """Raised when a real market dataset cannot be built."""


@dataclass(frozen=True)
class DailyDataset:
    bars: list[dict]
    tickers: tuple[str, ...]
    fetched_at: str
    last_bar_date: str
    interval: str = "1d"
    source: str = "yahoo"


def last_completed_session() -> date:
    """The newest session whose close is known, in US/Eastern time."""
    now = datetime.now(NEW_YORK)
    if now.time() >= MARKET_CLOSE:
        return now.date()
    return now.date() - timedelta(days=1)


def _request(ticker: str, range_: str, timeout: float) -> dict:
    errors: list[str] = []
    for host in HOSTS:
        url = (
            f"{host}/v8/finance/chart/{ticker}"
            f"?range={range_}&interval=1d&includePrePost=false&events=div%2Csplits"
        )
        try:
            payload = request_json(url, timeout=timeout)
            if payload.get("chart", {}).get("error"):
                raise MarketDataError(str(payload["chart"]["error"]))
            return payload["chart"]["result"][0]
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            errors.append(f"{host}: {exc}")
            logger.info("Yahoo request failed for %s via %s: %s", ticker, host, exc)
    raise MarketDataError(f"{ticker}: " + " | ".join(errors))


def _ticker_days(ticker: str, range_: str, timeout: float) -> dict[date, dict]:
    result = _request(ticker, range_, timeout)
    timestamps = result.get("timestamp") or []
    quotes = result.get("indicators", {}).get("quote") or [{}]
    quote = quotes[0]
    closes = quote.get("close") or []
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    volumes = quote.get("volume") or []

    cutoff = last_completed_session()
    days: dict[date, dict] = {}
    for index, stamp in enumerate(timestamps):
        close = closes[index] if index < len(closes) else None
        if close is None or close <= 0:
            continue
        day = datetime.fromtimestamp(stamp, tz=timezone.utc).astimezone(NEW_YORK).date()
        if day > cutoff:
            continue
        open_price = opens[index] if index < len(opens) and opens[index] else close
        high = highs[index] if index < len(highs) and highs[index] else max(open_price, close)
        low = lows[index] if index < len(lows) and lows[index] else min(open_price, close)
        volume = volumes[index] if index < len(volumes) and volumes[index] else 0
        days[day] = {
            "open": float(open_price),
            "high": float(max(high, open_price, close)),
            "low": float(min(low, open_price, close)),
            "close": float(close),
            "volume": int(volume),
        }
    if not days:
        raise MarketDataError(f"{ticker}: no completed daily bars returned")
    return days


def fetch_daily_bars(
    tickers: Iterable[str],
    *,
    range_: str = "1y",
    timeout: float = 20.0,
    max_workers: int = 4,
) -> DailyDataset:
    """Download daily bars for every ticker and align them on one calendar."""
    symbols = [ticker.upper() for ticker in tickers]
    series: dict[str, dict[date, dict]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(symbols)))) as pool:
        futures = {
            pool.submit(_ticker_days, symbol, range_, timeout): symbol for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            series[symbol] = future.result()

    calendar = sorted({day for days in series.values() for day in days})
    if len(calendar) < 60:
        raise MarketDataError(f"Only {len(calendar)} trading days returned; refusing partial data")
    for symbol, days in series.items():
        if len(days) < len(calendar) * 0.5:
            raise MarketDataError(f"{symbol} is missing too many sessions for a fair replay")

    bars: list[dict] = []
    last_close: dict[str, float] = {}
    for bar_index, day in enumerate(calendar):
        for symbol in symbols:
            daily = series[symbol].get(day)
            if daily is None:
                previous = last_close.get(symbol)
                if previous is None:
                    continue
                daily = {
                    "open": previous,
                    "high": previous,
                    "low": previous,
                    "close": previous,
                    "volume": 0,
                }
            last_close[symbol] = daily["close"]
            bars.append(
                {
                    "ticker": symbol,
                    "ts": f"{day.isoformat()}T16:00:00",
                    "session_date": day.isoformat(),
                    "bar_index": bar_index,
                    "open": round(daily["open"], 2),
                    "high": round(daily["high"], 2),
                    "low": round(daily["low"], 2),
                    "close": round(daily["close"], 2),
                    "volume": daily["volume"],
                }
            )

    fetched_at = datetime.now(timezone.utc).isoformat()
    return DailyDataset(
        bars=bars,
        tickers=tuple(symbols),
        fetched_at=fetched_at,
        last_bar_date=calendar[-1].isoformat(),
    )

