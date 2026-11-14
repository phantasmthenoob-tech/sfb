"""Resolve human replay windows against the cached daily timeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

RANGE_OPTIONS: tuple[dict[str, str], ...] = (
    {"id": "1w", "label": "1W", "description": "Last week"},
    {"id": "1m", "label": "1M", "description": "Last month"},
    {"id": "3m", "label": "3M", "description": "Last three months"},
    {"id": "ytd", "label": "YTD", "description": "Year to date"},
    {"id": "1y", "label": "1Y", "description": "Last twelve months"},
    {"id": "5y", "label": "5Y", "description": "Last five years"},
    {"id": "all", "label": "All", "description": "All recorded sessions"},
)
RANGE_IDS = tuple(option["id"] for option in RANGE_OPTIONS)
DEFAULT_RANGE = "all"


@dataclass(frozen=True)
class ReplayRange:
    preset: str
    start_bar: int
    end_bar: int
    start_date: str
    end_date: str

    @property
    def bars(self) -> int:
        return max(0, self.end_bar - self.start_bar + 1)


def range_options() -> list[dict[str, str]]:
    return [dict(option) for option in RANGE_OPTIONS]


def _parse(day: str) -> date:
    return date.fromisoformat(day[:10])


def resolve_replay_range(timeline: list[dict], preset: str | None) -> ReplayRange:
    """Return the bar indices and session dates for a named window.

    The end is always the newest recorded session. Unknown presets fall back to
    the full dataset rather than raising, so an old saved value cannot prevent
    the server from starting.
    """
    if not timeline:
        raise ValueError("Replay timeline is empty")
    selected = preset if preset in RANGE_IDS else DEFAULT_RANGE
    first_date = _parse(timeline[0]["session_date"])
    last_date = _parse(timeline[-1]["session_date"])

    if selected == "all":
        start_date = first_date
        end_date = last_date
    elif selected == "ytd":
        start_date = date(last_date.year, 1, 1)
        end_date = last_date
    else:
        days = {"1w": 7, "1m": 30, "3m": 91, "1y": 365, "5y": 1825}[selected]
        start_date = last_date - timedelta(days=days)
        end_date = last_date

    start_bar = next(
        (
            index
            for index, row in enumerate(timeline)
            if _parse(row["session_date"]) >= start_date
        ),
        len(timeline) - 1,
    )
    end_bar = next(
        (
            index
            for index in range(len(timeline) - 1, -1, -1)
            if _parse(timeline[index]["session_date"]) <= end_date
        ),
        len(timeline) - 1,
    )
    if end_bar < start_bar:
        start_bar = end_bar
    return ReplayRange(
        preset=selected,
        start_bar=start_bar,
        end_bar=end_bar,
        start_date=timeline[start_bar]["session_date"],
        end_date=timeline[end_bar]["session_date"],
    )
