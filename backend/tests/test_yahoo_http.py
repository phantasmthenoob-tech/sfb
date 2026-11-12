"""Yahoo HTTP retry policy: 429/5xx backoff before any cache fallback."""
from __future__ import annotations

import json
import urllib.error

import pytest

from app.market import yahoo_http


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def http_error(code: int, retry_after: float | None = None) -> urllib.error.HTTPError:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return urllib.error.HTTPError("https://query2.finance.yahoo.com", code, "error", headers, None)


@pytest.fixture
def sleeps(monkeypatch):
    recorded: list[float] = []
    monkeypatch.setattr(yahoo_http.time, "sleep", recorded.append)
    return recorded


def fake_urlopen(monkeypatch, outcomes):
    calls: list[object] = []

    def opener(*args, **kwargs):
        calls.append(args)
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(yahoo_http.urllib.request, "urlopen", opener)
    return calls


def test_retries_429_and_5xx_with_exponential_backoff(monkeypatch, sleeps):
    calls = fake_urlopen(
        monkeypatch,
        [http_error(429), http_error(503), FakeResponse({"chart": {"result": [1]}})],
    )

    payload = yahoo_http.request_json("https://query2.finance.yahoo.com/x", timeout=1)

    assert payload == {"chart": {"result": [1]}}
    assert len(calls) == 3
    assert len(sleeps) == 2
    assert 0.5 <= sleeps[0] <= 0.6
    assert 1.0 <= sleeps[1] <= 1.2


def test_retry_after_header_is_honoured(monkeypatch, sleeps):
    fake_urlopen(monkeypatch, [http_error(429, retry_after=4), FakeResponse({"ok": True})])

    yahoo_http.request_json("https://query2.finance.yahoo.com/x", timeout=1)

    assert len(sleeps) == 1
    assert 4.0 <= sleeps[0] <= 4.5


def test_non_retryable_status_fails_immediately(monkeypatch, sleeps):
    calls = fake_urlopen(monkeypatch, [http_error(404)])

    with pytest.raises(urllib.error.HTTPError) as raised:
        yahoo_http.request_json("https://query2.finance.yahoo.com/x", timeout=1)

    assert raised.value.code == 404
    assert len(calls) == 1
    assert sleeps == []


def test_retries_are_bounded_and_raise_the_last_error(monkeypatch, sleeps):
    calls = fake_urlopen(monkeypatch, [http_error(500), http_error(502)])

    with pytest.raises(urllib.error.HTTPError) as raised:
        yahoo_http.request_json(
            "https://query2.finance.yahoo.com/x", timeout=1, attempts=2
        )

    assert raised.value.code == 502
    assert len(calls) == 2
    assert len(sleeps) == 1


def test_backoff_is_capped():
    assert yahoo_http.retry_delay(10, None) <= yahoo_http.DEFAULT_MAX_DELAY + 0.25
    assert yahoo_http.retry_delay(1, "999") <= yahoo_http.DEFAULT_MAX_DELAY + 0.25


def test_both_providers_use_the_shared_retrying_helper():
    from app.market import live_provider, yahoo_provider

    assert yahoo_provider.request_json is yahoo_http.request_json
    assert live_provider.request_json is yahoo_http.request_json
