from pathlib import Path

from digital_oracle.timeline import TimelineStore, compare_subject, import_sources
from digital_oracle.timeline.extract import extract_report


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "timeline"


def test_import_is_idempotent_and_keeps_duplicate_sources(tmp_path):
    report = "# 有色金属走势\n\n**确认北京时间：2026-08-26 21:18；分析窗口：未来 1—4 周。**\n\n## 4. 结论\n> **偏强，但需确认。**\n"
    first = tmp_path / "local" / "first.md"
    second = tmp_path / "archive" / "second.md"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text(report, encoding="utf-8")
    second.write_text(report, encoding="utf-8")
    db = tmp_path / "timeline.db"
    stats = import_sources(db, [first.parent, second.parent])
    assert stats["sources"] == 2
    assert stats["reports"] == 1
    assert import_sources(db, [first.parent, second.parent])["reports"] == 1
    store = TimelineStore(db)
    rows = store.list_reports("有色")
    assert len(rows) == 1
    assert len(rows[0]["sources"]) == 2


def test_real_nonferrous_reports_keep_unchanged_probability_and_session_difference():
    a = extract_report((FIXTURES / "nonferrous_2026-08-26.md").read_text(encoding="utf-8"))
    b = extract_report((FIXTURES / "nonferrous_2026-08-27.md").read_text(encoding="utf-8"))
    assert a["analysis_at"].startswith("2026-08-26T21:17")
    assert b["market_session"] == "intraday"
    assert a["horizon"] == b["horizon"] == "1—4周"
    result = compare_subject([a, b], "有色")
    assert result["pairs"][0]["main_probability_delta"] == 0
    assert result["pairs"][0]["session_changed"] is True
    assert result["pairs"][0]["judgment_change"] == "上调"


def test_gold_silver_report_is_not_a_single_gold_prediction():
    report = "# 黄金与白银走势\n\n## 结论\n> 黄金偏强，白银震荡。"
    extracted = extract_report(report)
    assert "黄金" in extracted["subjects"]
    assert "白银" in extracted["subjects"]
    assert extracted["extraction_status"] == "needs_review"


def test_unknown_horizon_does_not_compare_probabilities():
    a = {"subjects": ["有色"], "analysis_at": "2026-08-01T10:00+08:00", "horizon": "1—4周", "main_probability": 55, "summary": "偏强", "market_session": "close"}
    b = {"subjects": ["有色"], "analysis_at": "2026-08-02T10:00+08:00", "horizon": "1—3月", "main_probability": 60, "summary": "偏强", "market_session": "close"}
    result = compare_subject([a, b], "有色")
    assert result["pairs"][0]["main_probability_delta"] is None
    assert "预测窗口" in result["pairs"][0]["comparability"]


def test_unknown_time_is_listed_but_not_compared():
    rows = [
        {"subjects": ["黄金"], "analysis_at": "2026-08-01T10:00+08:00", "summary": "偏强"},
        {"subjects": ["黄金"], "analysis_at": None, "summary": "偏空"},
    ]
    result = compare_subject(rows, "黄金")
    assert len(result["reports"]) == 2
    assert result["pairs"] == []


def test_correction_survives_reimport(tmp_path):
    report = tmp_path / "gold.md"
    report.write_text("# 黄金走势\n\n## 结论\n> 偏强。", encoding="utf-8")
    db = tmp_path / "timeline.db"
    import_sources(db, [tmp_path])
    store = TimelineStore(db)
    digest = store.list_reports("黄金")[0]["hash"]
    store.correct(digest, "analysis_at", "2026-08-01T10:00+08:00")
    import_sources(db, [tmp_path])
    assert TimelineStore(db).list_reports("黄金")[0]["analysis_at"] == "2026-08-01T10:00+08:00"


def test_new_report_metadata_is_extracted():
    report = "# 黄金走势\n\n分析时间（北京时间）：2026-09-17 14:00；数据截止：2026-09-17 13:55；分析窗口：未来 1—4 周；盘中/收盘：盘中；主题：黄金；标的及合约：GC=F。\n\n## 结论\n> 黄金短线偏多。"
    item = extract_report(report)
    assert item["analysis_at"] == "2026-09-17T14:00+08:00"
    assert "2026-09-17 13:55" in item["data_as_of"]
    assert item["market_session"] == "intraday"
