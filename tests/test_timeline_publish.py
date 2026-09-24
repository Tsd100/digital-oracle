import json

import pytest

from digital_oracle.timeline.contract import ContractError
from digital_oracle.timeline.publish import publish_report
from digital_oracle.timeline.store import TimelineStore


def make_report(direction="bullish", confidence=60, analysis_id="gold-1", analysis_at="2026-09-21T10:00:00+08:00",
                probabilities=None, levels=None):
    payload = {
        "schema_version": "1.0", "analysis_id": analysis_id,
        "analysis_at": analysis_at, "data_as_of": analysis_at,
        "subjects": [{"subject_id": "gold", "subject_name": "黄金", "instrument": "XAUUSD",
                      "quote_currency": "USD", "quote_unit": "oz",
                      "horizons": {"short": {"direction": direction, "confidence": confidence,
                                                "summary": "测试结论",
                                                "probabilities": probabilities or [],
                                                "levels": levels or []}}}],
    }
    return f"# 黄金分析\n\n```do-trend\n{json.dumps(payload, ensure_ascii=False)}\n```\n"


def test_duplicate_publish_is_idempotent(tmp_path):
    store = TimelineStore(tmp_path / "timeline.db")
    report = make_report()
    first = publish_report(store, "codex:gold-1", report, "codex")
    second = publish_report(store, "codex:gold-1", report, "codex")
    assert first.publication_id == second.publication_id
    assert second.duplicate is True
    assert store.automation_health()["publications"] == 1


def test_publication_builds_events_and_current_state(tmp_path):
    store = TimelineStore(tmp_path / "timeline.db")
    first = publish_report(store, "codex:gold-1", make_report(), "codex")
    second = publish_report(store, "codex:gold-2", make_report("strong_bullish", 76, "gold-2", "2026-09-22T10:00:00+08:00"), "codex")
    assert first.events[0]["event_type"] == "initiated"
    assert second.events[0]["event_type"] == "strengthened"
    state = store.current_trends("gold")
    assert state[0]["direction"] == "strong_bullish"
    assert state[0]["streak"] == 2
    assert "明确看多" in second.summary
    legacy_view = store.list_reports("黄金")
    assert legacy_view[-1]["analysis_at"] == "2026-09-22T10:00:00+08:00"
    assert legacy_view[-1]["extraction_status"] == "confirmed"


def test_missing_block_is_reported_without_structured_rows(tmp_path):
    store = TimelineStore(tmp_path / "timeline.db")
    with pytest.raises(ContractError):
        publish_report(store, "codex:bad", "# plain report", "codex")
    assert store.automation_health()["publications"] == 0
    assert store.automation_health()["errors"] == 1


def test_publication_compares_matching_probabilities_and_levels(tmp_path):
    store = TimelineStore(tmp_path / "timeline.db")
    publish_report(
        store, "codex:gold-1",
        make_report(probabilities=[{"scenario_id": "gold_1m_up", "term": "1m", "probability": 58}],
                    levels=[{"kind": "support", "value": 4292}]), "codex",
    )
    result = publish_report(
        store, "codex:gold-2",
        make_report(analysis_id="gold-2", analysis_at="2026-09-22T10:00:00+08:00",
                    probabilities=[{"scenario_id": "gold_1m_up", "term": "1m", "probability": 63}],
                    levels=[{"kind": "support", "value": 4350}]), "codex",
    )
    event = result.events[0]
    assert event["probability_changes"] == [{"scenario_id": "gold_1m_up", "term": "1m", "old": 58, "new": 63, "delta": 5.0}]
    assert event["level_changes"] == [{"kind": "support", "old": 4292, "new": 4350, "delta": 58.0}]
    assert "上涨概率 58%→63%" in result.summary
    assert "支撑位 4292→4350" in result.summary


def test_publication_does_not_compare_changed_scenario(tmp_path):
    store = TimelineStore(tmp_path / "timeline.db")
    publish_report(store, "one", make_report(probabilities=[{"scenario_id": "gold_1m_up", "term": "1m", "probability": 58}]), "codex")
    result = publish_report(store, "two", make_report(analysis_id="gold-2", analysis_at="2026-09-22T10:00:00+08:00",
                                                      probabilities=[{"scenario_id": "gold_hold_4200", "term": "1m", "probability": 80}]), "codex")
    assert result.events[0]["probability_changes"] == []


def test_reusing_source_key_keeps_published_report_for_audit(tmp_path):
    store = TimelineStore(tmp_path / "timeline.db")
    result = publish_report(store, "reports/gold.md", make_report(), "codex")
    store.add("reports/gold.md", "# 新版但尚未结构化的报告\n\n## 结论\n> 震荡。", "file")
    with store.connect() as conn:
        report_hash = conn.execute("SELECT report_hash FROM publications WHERE id=?", (result.publication_id,)).fetchone()[0]
    assert store.get_report(report_hash)["content"].startswith("# 黄金分析")
