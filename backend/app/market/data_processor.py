"""Small pure helpers for turning bars into display-ready values."""
from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def quote_payload(ticker: str, bar: dict, previous_close: float | None) -> dict:
    """Daily quote: the move is measured from the previous session's close."""
    close = bar["close"]
    reference = previous_close if previous_close else bar["open"]
    change = close - reference if reference else 0.0
    change_pct = (change / reference * 100.0) if reference else 0.0
    return {
        "ticker": ticker,
        "price": close,
        "open": bar["open"],
        "high": bar["high"],
        "low": bar["low"],
        "volume": bar["volume"],
        "previous_close": previous_close,
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "ts": bar["ts"],
    }


def moving_average(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window
