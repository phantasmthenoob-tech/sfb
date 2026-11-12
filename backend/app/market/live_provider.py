"""Live quotes from Yahoo Finance's public chart endpoint.

The same unofficial endpoint that supplies the daily replay also exposes a
one-minute series plus session metadata. During the US session each poll gives
the latest price, the day's open/high/low and the cumulative volume, which is
enough to keep one forming bar per trading day.

Outside the session the latest trade is yesterday's close, so callers must use
``market_open`` rather than assuming every poll is a new price.
"""
from __future__ import annotations

import logging
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from .yahoo_http import HOSTS, request_json

logger = logging.getLogger(__name__)

NEW_YORK = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
MAX_QUOTE_AGE_SECONDS = 30 * 60


class LiveDataError(Exception):
    """Raised when live quotes cannot be fetched or parsed."""


@dataclass(frozen=True)
class LiveQuote:
    ticker: str
    price: float
    previous_close: float | None
    day_open: float | None
    day_high: float | None
    day_low: float | None
    volume: int
    market_time: datetime | None

    def is_fresh(self, now: datetime, max_age: int = MAX_QUOTE_AGE_SECONDS) -> bool:
        if not self.market_time:
            return False
        age = (now - self.market_time).total_seconds()
        return 0 <= age <= max_age


@dataclass(frozen=True)
class LiveSnapshot:
    quotes: dict[str, LiveQuote]
    fetched_at: str
    market_open: bool
    session_date: str | None
    latest_quote_time: datetime | None = None
    errors: dict[str, str] = field(default_factory=dict)


def market_hours_open(now: datetime | None = None) -> bool:
    """True inside the regular US session on a weekday (holidays excluded by staleness)."""
    current = (now or datetime.now(NEW_YORK)).astimezone(NEW_YORK)
    if current.weekday() >= 5:
        return False
    return MARKET_OPEN <= current.time().replace(tzinfo=None) < MARKET_CLOSE


def _request(ticker: str, timeout: float) -> dict:
    errors: list[str] = []
    for host in HOSTS:
        url = (
            f"{host}/v8/finance/chart/{ticker}"
            "?range=1d&interval=1m&includePrePost=false"
        )
        try:
            payload = request_json(url, timeout=timeout)
            if payload.get("chart", {}).get("error"):
                raise LiveDataError(str(payload["chart"]["error"]))
            return payload["chart"]["result"][0]
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            errors.append(f"{host}: {exc}")
            logger.info("Live quote request failed for %s via %s: %s", ticker, host, exc)
    raise LiveDataError(f"{ticker}: " + " | ".join(errors))


def _float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def parse_quote(ticker: str, result: dict) -> LiveQuote:
    """Turn one chart response into a live quote (also used by tests)."""
    meta = result.get("meta") or {}
    stamps = result.get("timestamp") or []
    series = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = series.get("close") or []
    opens = series.get("open") or []
    highs = series.get("high") or []
    lows = series.get("low") or []
    volumes = series.get("volume") or []

    price = _float(meta.get("regularMarketPrice"))
    if price is None:
        for value in reversed(closes):
            price = _float(value)
            if price is not None:
                break
    if price is None:
        raise LiveDataError(f"{ticker}: no live price in response")

    raw_time = meta.get("regularMarketTime")
    market_time = None
    if raw_time:
        market_time = datetime.fromtimestamp(int(raw_time), tz=timezone.utc).astimezone(
            NEW_YORK
        )

    day = market_time.date() if market_time else datetime.now(NEW_YORK).date()
    day_opens: list[float] = []
    day_highs: list[float] = []
    day_lows: list[float] = []
    day_volume = 0
    for index, stamp in enumerate(stamps):
        moment = datetime.fromtimestamp(int(stamp), tz=timezone.utc).astimezone(NEW_YORK)
        if moment.date() != day:
            continue
        day_opens.extend(
            value for value in [_float(opens[index]) if index < len(opens) else None] if value
        )
        day_highs.extend(
            value for value in [_float(highs[index]) if index < len(highs) else None] if value
        )
        day_lows.extend(
            value for value in [_float(lows[index]) if index < len(lows) else None] if value
        )
        volume = volumes[index] if index < len(volumes) else None
        if volume:
            day_volume += int(volume)

    day_open = _float(meta.get("regularMarketOpen")) or (day_opens[0] if day_opens else None)
    day_high = _float(meta.get("regularMarketDayHigh")) or (max(day_highs) if day_highs else None)
    day_low = _float(meta.get("regularMarketDayLow")) or (min(day_lows) if day_lows else None)
    if day_high is not None:
        day_high = max(day_high, price)
    if day_low is not None:
        day_low = min(day_low, price)

    volume = day_volume or int(meta.get("regularMarketVolume") or 0)

    return LiveQuote(
        ticker=ticker.upper(),
        price=round(price, 2),
        previous_close=_float(meta.get("chartPreviousClose")) or _float(meta.get("previousClose")),
        day_open=round(day_open, 2) if day_open else None,
        day_high=round(day_high, 2) if day_high else None,
        day_low=round(day_low, 2) if day_low else None,
        volume=volume,
        market_time=market_time,
    )


def fetch_live_quotes(
    tickers: Iterable[str],
    *,
    timeout: float = 10.0,
    max_workers: int = 4,
    now: datetime | None = None,
) -> LiveSnapshot:
    """Fetch the latest quote for every ticker and decide whether the market is open."""
    symbols = [ticker.upper() for ticker in tickers]
    quotes: dict[str, LiveQuote] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(symbols)))) as pool:
        futures = {pool.submit(_request, symbol, timeout): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                quotes[symbol] = parse_quote(symbol, future.result())
            except Exception as exc:  # noqa: BLE001 - one bad symbol must not stop the poll
                errors[symbol] = str(exc)
                logger.info("Live quote unavailable for %s: %s", symbol, exc)

    if not quotes:
        raise LiveDataError("Yahoo Finance returned no live quotes: " + " | ".join(errors.values()))

    current = (now or datetime.now(NEW_YORK)).astimezone(NEW_YORK)
    latest = max(
        (quote.market_time for quote in quotes.values() if quote.market_time),
        default=None,
    )
    fresh = latest is not None and (
        (current - latest).total_seconds() <= MAX_QUOTE_AGE_SECONDS
        and (current - latest).total_seconds() >= 0
    )
    is_open = market_hours_open(current) and fresh
    session_date = None
    if is_open:
        session_date = current.date().isoformat()
    elif latest is not None:
        session_date = latest.date().isoformat()

    return LiveSnapshot(
        quotes=quotes,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        market_open=is_open,
        session_date=session_date,
        latest_quote_time=latest,
        errors=errors,
    )
