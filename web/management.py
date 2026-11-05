"""Read model for the DO research management dashboard."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from digital_oracle.timeline import TimelineStore


SUBJECT_ORDER = ["黄金", "白银", "有色", "半导体", "科创50", "原油", "创新药", "光模块", "美联储"]
RESOLVED_DIRECTIONS = {"strong_bullish", "bullish", "neutral", "mixed", "bearish", "strong_bearish"}


def _direction(report: dict[str, Any], subject: str) -> str:
    judgment = report.get("subject_judgments", {}).get(subject, {})
    return judgment.get("direction") or "unknown"


def _evidence(report: dict[str, Any], subject: str) -> str:
    judgment = report.get("subject_judgments", {}).get(subject, {})
    return judgment.get("evidence") or report.get("summary") or "暂无摘要"


def _dated_reports(reports: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (report for report in reports if report.get("analysis_at")),
        key=lambda report: report["analysis_at"],
    )


def _freshness(analysis_at: str | None, now: datetime) -> str:
    if not analysis_at:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(analysis_at)
        reference = now if now.tzinfo else now.astimezone()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=reference.tzinfo)
        days = (reference - parsed.astimezone(reference.tzinfo)).total_seconds() / 86400
    except (TypeError, ValueError):
        return "unknown"
    if days <= 3:
        return "current"
    if days <= 14:
        return "aging"
    return "stale"


def build_management_summary(
    store: TimelineStore,
    chat_history: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Combine legacy reports, structured trends, and workflow health."""
    now = now or datetime.now().astimezone()
    all_reports = store.list_reports()
    discovered = {subject for report in all_reports for subject in report.get("subjects", [])}
    subjects = [*SUBJECT_ORDER, *sorted(discovered - set(SUBJECT_ORDER))]
    summaries: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []

    for subject in subjects:
        reports = store.list_reports(subject)
        dated = _dated_reports(reports)
        resolved = [report for report in dated if _direction(report, subject) in RESOLVED_DIRECTIONS]
        latest = resolved[-1] if resolved else None
        previous = None
        if latest:
            previous = next(
                (report for report in reversed(resolved[:-1]) if _direction(report, subject) != _direction(latest, subject)),
                None,
            )
        subject_id = store.resolve_subject_id(subject)
        horizons = store.current_trends(subject_id) if subject_id else []
        item = {
            "name": subject,
            "report_count": len(reports),
            "resolved_count": len(resolved),
            "needs_review": sum(report.get("extraction_status") != "confirmed" for report in reports),
            "latest_analysis_at": latest.get("analysis_at") if latest else None,
            "latest_direction": _direction(latest, subject) if latest else "unknown",
            "latest_evidence": _evidence(latest, subject) if latest else "暂无有效判断",
            "previous_direction": _direction(previous, subject) if previous else None,
            "changed_from_at": previous.get("analysis_at") if previous else None,
            "freshness": _freshness(latest.get("analysis_at") if latest else None, now),
            "horizons": horizons,
            "history": [
                {
                    "analysis_at": report["analysis_at"],
                    "direction": _direction(report, subject),
                    "evidence": _evidence(report, subject),
                    "hash": report["hash"],
                    "title": report["title"],
                }
                for report in resolved
            ],
            "timeline_url": f"/timeline?subject={subject}",
        }
        summaries.append(item)
        if latest and previous:
            changes.append({
                "subject": subject,
                "analysis_at": latest["analysis_at"],
                "from_direction": _direction(previous, subject),
                "to_direction": _direction(latest, subject),
                "evidence": _evidence(latest, subject),
                "timeline_url": item["timeline_url"],
            })

    summaries.sort(key=lambda item: item["latest_analysis_at"] or "", reverse=True)
    changes.sort(key=lambda item: item["analysis_at"], reverse=True)
    latest_analysis_at = max((item["latest_analysis_at"] or "" for item in summaries), default="") or None
    latest_chat_at = max((item.get("created_at") or "" for item in chat_history), default="") or None
    automation_health = dict(store.automation_health())
    published_at = automation_health.get("last_published_at")
    if published_at and "Z" not in published_at and "+" not in published_at:
        automation_health["last_published_at"] = published_at.replace(" ", "T") + "Z"

    return {
        "generated_at": now.isoformat(timespec="minutes"),
        "totals": {
            "reports": len(all_reports),
            "subjects": sum(item["report_count"] > 0 for item in summaries),
            "needs_review": store.counts()["needs_review"],
            "chat_analyses": len(chat_history),
            "latest_analysis_at": latest_analysis_at,
            "latest_chat_at": latest_chat_at,
        },
        "automation_health": automation_health,
        "subjects": summaries,
        "recent_changes": changes[:8],
    }
