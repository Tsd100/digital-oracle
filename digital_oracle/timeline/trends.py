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


def compare_probabilities(old_values: list[dict], new_values: list[dict]) -> list[dict]:
    old_by_key = {(item.get("scenario_id"), item.get("term")): item for item in old_values}
    changes = []
    for new in new_values:
        key = (new.get("scenario_id"), new.get("term"))
        old = old_by_key.get(key)
        if old is None:
            continue
        delta = compare_probability(old, new)
        if delta is None:
            continue
        changes.append({
            "scenario_id": key[0], "term": key[1],
            "old": old["probability"], "new": new["probability"], "delta": delta,
        })
    return changes


def compare_levels(old_values: list[dict], new_values: list[dict]) -> list[dict]:
    old_by_kind = {item.get("kind"): item for item in old_values}
    changes = []
    for new in new_values:
        old = old_by_kind.get(new.get("kind"))
        if old is None:
            continue
        changes.append({
            "kind": new["kind"], "old": old["value"], "new": new["value"],
            "delta": float(new["value"]) - float(old["value"]),
        })
    return changes
