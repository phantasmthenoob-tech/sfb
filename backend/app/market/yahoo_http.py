"""Shared Yahoo Finance HTTP helper with bounded retry/backoff.

The public chart endpoint occasionally answers 429 (rate limit) or a 5xx
(gateway hiccup). Both the daily-history and live-quote providers use this
helper so those responses are retried with exponential backoff and jitter
before the caller falls back to cached data or another host.
"""
from __future__ import annotations

import json
import logging
import random
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

HOSTS = (
    "https://query2.finance.yahoo.com",
    "https://query1.finance.yahoo.com",
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# 429 and transient gateway/server errors are worth retrying; 4xx else is not.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
DEFAULT_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 0.5
DEFAULT_MAX_DELAY = 8.0


def retry_delay(
    attempt: int,
    retry_after: str | None,
    *,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> float:
    """Exponential backoff for the given attempt (1-based), honouring Retry-After."""
    delay = base_delay * (2 ** (attempt - 1))
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except (TypeError, ValueError):
            pass
    delay = min(delay, max_delay)
    return round(delay + random.uniform(0, min(0.25, delay * 0.1)), 3)


def request_json(
    url: str,
    *,
    timeout: float,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> dict:
    """Fetch and decode JSON, retrying 429/5xx with exponential backoff."""
    attempts = max(1, attempts)
    last_error: urllib.error.HTTPError | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_STATUS or attempt == attempts:
                raise
            last_error = exc
            delay = retry_delay(
                attempt,
                exc.headers.get("Retry-After") if exc.headers else None,
                base_delay=base_delay,
                max_delay=max_delay,
            )
            logger.warning(
                "Yahoo returned HTTP %s; retrying in %.2fs (attempt %s/%s)",
                exc.code,
                delay,
                attempt,
                attempts,
            )
            time.sleep(delay)
    # Unreachable: the loop either returns or raises on the final attempt.
    if last_error is not None:
        raise last_error
    raise RuntimeError("Yahoo request failed without an error")
