"""Pure deterministic comparison rules for structured DO trends."""
from __future__ import annotations


DIRECTION_SCORE = {
    "strong_bullish": 2,
    "bullish": 1,
    "neutral": 0,
    "bearish": -1,
    "strong_bearish": -2,
}


def compare_direction(old: str | None, new: str) -> str:
    if old is None:
        return "initiated"
    if old == new:
        return "continued"
    old_score = DIRECTION_SCORE[old]
    new_score = DIRECTION_SCORE[new]
    if old_score * new_score < 0:
        return "reversed"
    if old_score == 0 or new_score == 0:
        return "shifted"
    return "strengthened" if abs(new_score) > abs(old_score) else "weakened"


def compare_confidence(old: int, new: int) -> str:
    delta = new - old
    if abs(delta) < 5:
        return "stable"
    if delta >= 15:
        return "strongly_strengthened"
    if delta <= -15:
        return "strongly_weakened"
    return "strengthened" if delta > 0 else "weakened"


def compare_probability(old: dict, new: dict) -> float | None:
    identity = ("scenario_id", "term")
    if any(old.get(key) != new.get(key) for key in identity):
        return None
    try:
        return float(new["probability"]) - float(old["probability"])
    except (KeyError, TypeError, ValueError):
        return None
