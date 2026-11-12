"""Helpers for turning raw strategy scores into recorded predictions."""
from __future__ import annotations

from .features import clamp


def direction_for(score: float, threshold: float) -> str:
    if score >= threshold:
        return "UP"
    if score <= -threshold:
        return "DOWN"
    return "FLAT"


def confidence_for(score: float) -> float:
    """Map a signal score to a 0-1 confidence that never claims certainty."""
    return round(clamp(0.5 + abs(score) * 0.45, 0.5, 0.95), 3)
