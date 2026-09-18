"""Compare report snapshots without silently changing horizons or scope."""
from __future__ import annotations


def _strength(summary: str | None) -> int | None:
    if not summary:
        return None
    if any(x in summary for x in ("偏空", "转弱", "回撤风险上升")):
        return -1
    if any(x in summary for x in ("短线偏多", "上调为", "突破加速")):
        return 2
    if any(x in summary for x in ("震荡偏强", "偏强", "修复")):
        return 1
    return None


def _scenario_class(report: dict) -> str | None:
    scenarios = report.get("scenarios") or []
    if not scenarios:
        return None
    label = scenarios[0].get("label", "")
    if "震荡" in label and any(x in label for x in ("强", "上")):
        return "偏强震荡"
    return label.strip() or None


def compare_subject(reports: list[dict], subject: str) -> dict:
    rows = [r for r in reports if subject in r.get("subjects", [])]
    rows.sort(key=lambda r: r.get("analysis_at") or "9999")
    dated = [r for r in rows if r.get("analysis_at")]
    pairs = []
    for old, new in zip(dated, dated[1:]):
        reasons = []
        if not old.get("horizon") or old.get("horizon") != new.get("horizon"):
            reasons.append("预测窗口不同或缺失")
        if old.get("scope") and new.get("scope") and old["scope"] != new["scope"]:
            reasons.append("分析范围不同")
        if len(old.get("subjects", [])) != 1 or len(new.get("subjects", [])) != 1:
            reasons.append("联合主题报告，单项结论待核对")
        if old.get("main_probability") is not None and new.get("main_probability") is not None:
            if not _scenario_class(old) or not _scenario_class(new):
                reasons.append("主情景定义待核对")
            elif _scenario_class(old) != _scenario_class(new):
                reasons.append("主情景定义不同")
        comparable = not reasons
        previous, current = old.get("main_probability"), new.get("main_probability")
        delta = current - previous if comparable and previous is not None and current is not None else None
        old_judgment = old.get("subject_judgments", {}).get(subject)
        new_judgment = new.get("subject_judgments", {}).get(subject)
        a = old_judgment.get("score") if old_judgment is not None else _strength(old.get("summary"))
        b = new_judgment.get("score") if new_judgment is not None else _strength(new.get("summary"))
        judgment = "无法判断" if a is None or b is None else "上调" if b > a else "下调" if b < a else "维持"
        pairs.append({
            "old": old, "new": new, "judgment_change": judgment,
            "main_probability_delta": delta, "comparability": "；".join(reasons) if reasons else "可比较",
            "session_changed": old.get("market_session") in ("close", "intraday") and new.get("market_session") in ("close", "intraday") and old.get("market_session") != new.get("market_session"),
        })
    return {"subject": subject, "reports": rows, "pairs": pairs}
