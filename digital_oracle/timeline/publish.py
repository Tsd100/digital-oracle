"""Shared idempotent publication pipeline for future DO reports."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .contract import extract_trend_block
from .extract import extract_report
from .store import TimelineStore
from .trends import DIRECTION_SCORE, compare_confidence, compare_direction, compare_levels, compare_probabilities


LABELS = {
    "strong_bullish": "明确看多", "bullish": "偏多", "neutral": "中性/震荡",
    "bearish": "偏空", "strong_bearish": "明确看空", "insufficient": "信息不足",
}
EVENT_LABELS = {
    "initiated": "首次建立", "continued": "延续", "strengthened": "增强",
    "weakened": "减弱", "shifted": "转向", "reversed": "反转",
}
HORIZON_LABELS = {"short": "短线", "swing": "波段", "medium": "中期"}
LEVEL_LABELS = {"support": "支撑位", "resistance": "压力位", "target": "目标位", "invalidation": "失效位"}


@dataclass(frozen=True)
class PublishResult:
    publication_id: int
    duplicate: bool
    updated_tracks: int
    events: tuple[dict, ...]
    summary: str
    errors: tuple[str, ...] = ()


def _summary(events: list[dict]) -> str:
    lines = []
    for event in events:
        prefix = f"{event['subject_name']}{HORIZON_LABELS[event['horizon']]}"
        current = LABELS[event["new_direction"]]
        change = EVENT_LABELS[event["event_type"]]
        details = []
        for probability in event.get("probability_changes", []):
            label = "上涨概率" if str(probability["scenario_id"]).endswith("_up") else f"{probability['scenario_id']} 概率"
            details.append(f"{label} {probability['old']:g}%→{probability['new']:g}%")
        for level in event.get("level_changes", []):
            details.append(f"{LEVEL_LABELS[level['kind']]} {level['old']:g}→{level['new']:g}")
        suffix = f" {'；'.join(details)}。" if details else ""
        lines.append(f"{prefix}：{current}（{change}），连续 {event['streak']} 次。{suffix}")
    return "\n".join(lines)


def publish_report(store: TimelineStore, source_key: str, content: str, source_kind: str = "file") -> PublishResult:
    try:
        contract = extract_trend_block(content)
    except Exception as exc:
        store.record_publication_failure(source_key, source_kind, str(exc))
        raise
    report_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    fingerprint = hashlib.sha256(
        f"{source_kind}\0{contract.analysis_id}\0{contract.data_as_of}\0{report_hash}".encode("utf-8")
    ).hexdigest()
    parsed = extract_report(content)
    structured_horizons = sorted({name for subject in contract.subjects for name in subject.horizons})
    parsed.update({
        "analysis_at": contract.analysis_at,
        "data_as_of": contract.data_as_of,
        "subjects": [subject.subject_name for subject in contract.subjects],
        "horizon": ",".join(structured_horizons) or None,
        "summary": "；".join(
            horizon.summary for subject in contract.subjects for horizon in subject.horizons.values()
        ) or None,
        "extraction_status": "confirmed",
        "structured_trend": True,
    })
    with store.connect() as conn:
        conn.execute("DELETE FROM publication_failures WHERE source_key=?", (source_key,))
        existing = conn.execute("SELECT id FROM publications WHERE fingerprint=?", (fingerprint,)).fetchone()
        if existing:
            events = [dict(row) for row in conn.execute("SELECT * FROM trend_events WHERE publication_id=? ORDER BY id", (existing[0],))]
            for event in events:
                event["probability_changes"] = json.loads(event["probability_changes"])
                event["level_changes"] = json.loads(event["level_changes"])
                event["subject_name"] = next((s.subject_name for s in contract.subjects if s.subject_id == event["subject_id"]), event["subject_id"])
            return PublishResult(existing[0], True, len(events), tuple(events), _summary(events))
        conn.execute(
            "INSERT INTO reports VALUES (?, ?, ?, ?) ON CONFLICT(hash) DO UPDATE SET title=excluded.title, extracted=excluded.extracted, content=excluded.content",
            (report_hash, parsed["title"], json.dumps(parsed, ensure_ascii=False), content),
        )
        conn.execute(
            "INSERT INTO sources VALUES (?, ?, ?) ON CONFLICT(source_key) DO UPDATE SET report_hash=excluded.report_hash, source_kind=excluded.source_kind",
            (source_key, report_hash, source_kind),
        )
        cursor = conn.execute(
            "INSERT INTO publications(fingerprint,analysis_id,analysis_at,data_as_of,source_key,source_kind,report_hash,schema_version) VALUES(?,?,?,?,?,?,?,?)",
            (fingerprint, contract.analysis_id, contract.analysis_at, contract.data_as_of, source_key, source_kind, report_hash, contract.schema_version),
        )
        publication_id = cursor.lastrowid
        events = []
        for subject in contract.subjects:
            for horizon, snapshot in subject.horizons.items():
                conn.execute(
                    "INSERT INTO trend_snapshots(publication_id,subject_id,subject_name,instrument,quote_currency,quote_unit,horizon,direction,confidence,summary,probabilities,levels) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (publication_id, subject.subject_id, subject.subject_name, subject.instrument, subject.quote_currency,
                     subject.quote_unit, horizon, snapshot.direction, snapshot.confidence, snapshot.summary,
                     json.dumps(snapshot.probabilities, ensure_ascii=False), json.dumps(snapshot.levels, ensure_ascii=False)),
                )
                if snapshot.direction == "insufficient":
                    continue
                previous = conn.execute(
                    "SELECT * FROM trend_state WHERE subject_id=? AND instrument=? AND quote_currency=? AND quote_unit=? AND horizon=?",
                    (subject.subject_id, subject.instrument, subject.quote_currency, subject.quote_unit, horizon),
                ).fetchone()
                old_direction = previous["direction"] if previous else None
                event_type = compare_direction(old_direction, snapshot.direction)
                same_side = bool(previous) and (
                    old_direction == snapshot.direction
                    or DIRECTION_SCORE[old_direction] * DIRECTION_SCORE[snapshot.direction] > 0
                )
                streak = previous["streak"] + 1 if same_side else 1
                started_at = previous["started_at"] if previous and streak > 1 else contract.analysis_at
                last_reversal = contract.analysis_at if event_type == "reversed" else (previous["last_reversal_at"] if previous else None)
                confidence_change = compare_confidence(previous["confidence"], snapshot.confidence) if previous else None
                previous_snapshot = None
                if previous:
                    previous_snapshot = conn.execute(
                        "SELECT probabilities, levels FROM trend_snapshots WHERE publication_id=? AND subject_id=? AND instrument=? AND quote_currency=? AND quote_unit=? AND horizon=?",
                        (previous["publication_id"], subject.subject_id, subject.instrument, subject.quote_currency, subject.quote_unit, horizon),
                    ).fetchone()
                probability_changes = compare_probabilities(
                    json.loads(previous_snapshot["probabilities"]) if previous_snapshot else [], list(snapshot.probabilities)
                )
                level_changes = compare_levels(
                    json.loads(previous_snapshot["levels"]) if previous_snapshot else [], list(snapshot.levels)
                )
                event = {
                    "publication_id": publication_id, "subject_id": subject.subject_id, "subject_name": subject.subject_name,
                    "horizon": horizon, "event_type": event_type, "old_direction": old_direction,
                    "new_direction": snapshot.direction, "confidence_change": confidence_change,
                    "old_confidence": previous["confidence"] if previous else None,
                    "new_confidence": snapshot.confidence, "streak": streak,
                    "probability_changes": probability_changes, "level_changes": level_changes,
                }
                event["summary"] = _summary([event])
                conn.execute(
                    "INSERT INTO trend_events(publication_id,subject_id,horizon,event_type,old_direction,new_direction,confidence_change,old_confidence,new_confidence,streak,probability_changes,level_changes,summary) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (publication_id, subject.subject_id, horizon, event_type, old_direction, snapshot.direction,
                     confidence_change, event["old_confidence"], snapshot.confidence, streak,
                     json.dumps(probability_changes, ensure_ascii=False), json.dumps(level_changes, ensure_ascii=False), event["summary"]),
                )
                conn.execute(
                    "INSERT INTO trend_state(subject_id,instrument,quote_currency,quote_unit,horizon,direction,confidence,summary,streak,started_at,last_reversal_at,analysis_at,publication_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(subject_id,instrument,quote_currency,quote_unit,horizon) DO UPDATE SET direction=excluded.direction,confidence=excluded.confidence,summary=excluded.summary,streak=excluded.streak,started_at=excluded.started_at,last_reversal_at=excluded.last_reversal_at,analysis_at=excluded.analysis_at,publication_id=excluded.publication_id",
                    (subject.subject_id, subject.instrument, subject.quote_currency, subject.quote_unit, horizon,
                     snapshot.direction, snapshot.confidence, snapshot.summary, streak, started_at, last_reversal,
                     contract.analysis_at, publication_id),
                )
                events.append(event)
    return PublishResult(publication_id, False, len(events), tuple(events), _summary(events))
