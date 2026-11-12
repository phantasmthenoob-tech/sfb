"""Runtime configuration for the market simulation backend."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Universe used both for the replay data and for the tradable universe.
DEFAULT_UNIVERSE: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "AMZN",
    "GOOGL",
    "META",
    "AMD",
)

SPEED_OPTIONS: tuple[int, ...] = (1, 5, 10, 30)


def _default_db_path() -> str:
    base = Path(__file__).resolve().parent.parent / "data"
    return str(base / "simulation.db")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """All simulation knobs in one place.

    Money is stored in USD with 2 decimal places. Share quantities are signed
    integers: positive = long, negative = short.
    """

    starting_balance: float = 10_000.0
    db_path: str = field(default_factory=lambda: os.environ.get("DB_PATH", _default_db_path()))

    universe: tuple[str, ...] = DEFAULT_UNIVERSE

    # Simulated transaction costs.
    fee_bps: float = 5.0  # 5 bps = 0.05% of notional, per side
    borrow_rate_annual: float = 0.08  # 8% annualised borrow fee on short market value

    # Risk limits (fractions of current portfolio equity).
    max_position_pct: float = 0.25
    max_short_position_pct: float = 0.20
    max_total_short_pct: float = 0.50
    max_order_notional_pct: float = 0.25

    # Market data. "yahoo" downloads real daily bars from Yahoo Finance and
    # caches them; "synthetic" generates deterministic sample bars (tests).
    data_source: str = field(
        default_factory=lambda: os.environ.get("MARKET_DATA_SOURCE", "yahoo").lower()
    )
    data_refresh_hours: float = field(
        default_factory=lambda: _env_float("MARKET_DATA_REFRESH_HOURS", 24.0)
    )
    history_range: str = field(
        default_factory=lambda: os.environ.get("MARKET_HISTORY_RANGE", "1y")
    )

    # Replay configuration. With real daily bars each bar is one trading day.
    # replay_sessions/bars_per_session only shape the synthetic fallback.
    replay_sessions: int = 10
    bars_per_session: int = 78
    bar_interval_seconds: float = 1.0
    default_speed: int = 5
    agent_decision_every: int = 1
    seed: int = 20260914

    # Live mode: poll real quotes during the US session and let the agents
    # trade against them. One poll acts as one "bar" after which orders fill.
    default_mode: str = field(
        default_factory=lambda: os.environ.get("SIM_MODE", "replay").lower()
    )
    live_poll_seconds: float = field(
        default_factory=lambda: _env_float("LIVE_POLL_SECONDS", 60.0)
    )
    live_decision_seconds: float = field(
        default_factory=lambda: _env_float("LIVE_DECISION_SECONDS", 300.0)
    )
    autostart: bool = field(
        default_factory=lambda: os.environ.get("SIM_AUTOSTART", "1").lower()
        not in ("0", "false", "no")
    )

    def as_public_dict(self) -> dict:
        return {
            "starting_balance": self.starting_balance,
            "universe": list(self.universe),
            "fee_bps": self.fee_bps,
            "borrow_rate_annual": self.borrow_rate_annual,
            "max_position_pct": self.max_position_pct,
            "max_short_position_pct": self.max_short_position_pct,
            "max_total_short_pct": self.max_total_short_pct,
            "max_order_notional_pct": self.max_order_notional_pct,
            "speed_options": list(SPEED_OPTIONS),
            "bar_interval_seconds": self.bar_interval_seconds,
            "data_source": self.data_source,
            "data_refresh_hours": self.data_refresh_hours,
            "history_range": self.history_range,
            "replay_sessions": self.replay_sessions,
            "bars_per_session": self.bars_per_session,
            "default_mode": self.default_mode,
            "live_poll_seconds": self.live_poll_seconds,
            "live_decision_seconds": self.live_decision_seconds,
        }
