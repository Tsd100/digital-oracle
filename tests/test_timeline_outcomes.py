from digital_oracle.timeline.outcomes import evaluate_threshold


def test_threshold_requires_mature_horizon_and_matching_contract():
    report = {"horizon_start": "2026-08-01", "horizon_end": "2026-08-31", "instrument": "GC=F", "contract": "continuous", "unit": "USD/oz"}
    observation = {"as_of": "2026-08-25", "checked_at": "2026-08-25", "instrument": "GC=F", "contract": "continuous", "unit": "USD/oz", "value": 4700}
    assert evaluate_threshold(report, observation, "above", 4660)["status"] == "not_due"
    observation["checked_at"] = "2026-09-01"
    observation["contract"] = "front-month"
    assert evaluate_threshold(report, observation, "above", 4660)["status"] == "incomparable"
    observation["contract"] = "continuous"
    assert evaluate_threshold(report, observation, "above", 4660)["status"] == "triggered"
    observation["as_of"] = "2026-09-01"
    assert evaluate_threshold(report, observation, "above", 4660)["status"] == "incomparable"


def test_missing_horizon_cannot_create_accuracy_claim():
    result = evaluate_threshold({"instrument": "GC=F"}, {"instrument": "GC=F", "value": 4700}, "above", 4660)
    assert result["status"] == "unverifiable"
