import pytest

from digital_oracle.timeline.trends import compare_confidence, compare_direction, compare_probability


@pytest.mark.parametrize(
    ("old", "new", "event"),
    [
        (None, "bullish", "initiated"),
        ("neutral", "bullish", "shifted"),
        ("bullish", "strong_bullish", "strengthened"),
        ("strong_bullish", "bullish", "weakened"),
        ("bullish", "bearish", "reversed"),
        ("bearish", "strong_bearish", "strengthened"),
        ("bullish", "bullish", "continued"),
    ],
)
def test_direction_events(old, new, event):
    assert compare_direction(old, new) == event


def test_confidence_thresholds():
    assert compare_confidence(60, 64) == "stable"
    assert compare_confidence(60, 65) == "strengthened"
    assert compare_confidence(60, 75) == "strongly_strengthened"
    assert compare_confidence(60, 45) == "strongly_weakened"


def test_probability_requires_matching_scenario_and_term():
    old = {"scenario_id": "gold_1m_up", "term": "1m", "probability": 58}
    new = {"scenario_id": "gold_1m_up", "term": "1m", "probability": 63}
    assert compare_probability(old, new) == 5
    assert compare_probability(old, {**new, "scenario_id": "gold_hold_4200"}) is None
    assert compare_probability(old, {**new, "term": "3m"}) is None
