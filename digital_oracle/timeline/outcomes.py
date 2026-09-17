"""Conservative verification of explicit historical thresholds.

This does not calculate prediction accuracy or fetch market data. Callers must
provide a dated, contract-matched observation from a verified source.
"""
from __future__ import annotations


def evaluate_threshold(report: dict, observation: dict, direction: str, level: float) -> dict:
    start = report.get("horizon_start")
    end = report.get("horizon_end")
    observed_at = observation.get("as_of")
    checked_at = observation.get("checked_at")
    if not start or not end or not observed_at or not checked_at or observation.get("value") is None:
        return {"status": "unverifiable", "reason": "预测窗口、核对日期或观察值缺失"}
    if checked_at < end:
        return {"status": "not_due", "reason": "预测窗口尚未结束"}
    if not start <= observed_at <= end:
        return {"status": "incomparable", "reason": "观察值不在预测窗口内"}
    for field in ("instrument", "contract", "unit"):
        if not report.get(field) or not observation.get(field) or report[field] != observation[field]:
            return {"status": "incomparable", "reason": f"{field} 不一致或缺失"}
    if direction not in ("above", "below"):
        return {"status": "unverifiable", "reason": "阈值方向不明确"}
    value = float(observation["value"])
    hit = value > level if direction == "above" else value < level
    return {"status": "triggered" if hit else "not_met_at_observation", "observed": value, "level": level, "as_of": observed_at}
