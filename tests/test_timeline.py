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


def test_corrected_summary_updates_subject_direction(tmp_path):
    db = tmp_path / "timeline.db"
    store = TimelineStore(db)
    digest = store.add("gold", "# 黄金走势\n\n## 结论\n> 黄金偏多。")
    store.correct(digest, "summary", "黄金偏空。")
    assert store.list_reports("黄金")[0]["subject_judgments"]["黄金"]["direction"] == "bearish"


def test_new_report_metadata_is_extracted():
    report = "# 黄金走势\n\n分析时间（北京时间）：2026-09-17 14:00；数据截止：2026-09-17 13:55；分析窗口：未来 1—4 周；盘中/收盘：盘中；主题：黄金；标的及合约：GC=F。\n\n## 结论\n> 黄金短线偏多。"
    item = extract_report(report)
    assert item["analysis_at"] == "2026-09-17T14:00+08:00"
    assert "2026-09-17 13:55" in item["data_as_of"]
    assert item["market_session"] == "intraday"


def test_markdown_confirmed_time_and_oil_title_are_recognized():
    report = "# 石油走势：DO 分析\n\n**确认时间：**2026-09-03 14:41（北京时间）\n\n## 结论\n> 石油偏弱，黄金只是对照。"
    item = extract_report(report)
    assert item["analysis_at"] == "2026-09-03T14:41+08:00"
    assert item["subjects"] == ["原油"]


def test_broad_title_does_not_inherit_incidental_asset_from_conclusion():
    report = "# 美伊局势研判\n\n## 结论\n> 黄金和原油可能受到影响。"
    assert extract_report(report)["subjects"] == []


def test_explicit_single_window_is_kept_but_multiple_windows_need_review():
    single = "# 原油走势\n\n确认时间：2026-09-03 14:41\n核心问题：原油近期（1-3个月）的走势。\n\n## 结论\n> 偏弱。"
    mixed = "# 原油走势\n\n确认时间：2026-09-03 14:41\n核心问题：原油近期（1-3个月）的走势。\n\n## 情景概率\n### 未来1-5个交易日\n\n## 结论\n> 偏弱。"
    assert extract_report(single)["horizon"] == "1—3月"
    assert extract_report(mixed)["horizon"] is None
    assert extract_report(mixed)["extraction_status"] == "needs_review"


def test_short_and_swing_windows_are_not_mislabeled_as_one_forecast():
    report = "# 石油走势\n\n确认北京时间：2026-08-24 14:46\n- 短线（1—5个交易日）：偏强。\n- 波段（2—8周）：震荡。\n\n## 结论\n> 中短期偏多。"
    item = extract_report(report)
    assert item["horizon"] is None
    assert item["extraction_status"] == "needs_review"


def test_joint_report_has_separate_direction_without_comparable_probability():
    report = "# 黄金与白银走势\n\n确认时间：2026-08-22 19:29\n\n## 结论\n> 黄金未来1—3个月震荡偏强；白银短线偏弱。"
    item = extract_report(report)
    assert item["subject_judgments"]["黄金"]["direction"] == "bullish"
    assert item["subject_judgments"]["白银"]["direction"] == "bearish"
    assert "黄金" in item["subject_judgments"]["黄金"]["evidence"]
    assert item["extraction_status"] == "needs_review"


def test_mixed_horizons_and_relative_ranking_do_not_force_a_direction():
    mixed = extract_report("# 黄金与白银走势\n\n## 结论\n> 黄金：中期上升趋势尚未破坏，短线进入回撤确认；白银偏多。")
    ranked = extract_report("# 黄金与白银走势\n\n## 结论\n> 黄金最稳、白银最有弹性。组合仍偏多。")
    assert mixed["subject_judgments"]["黄金"]["direction"] == "mixed"
    assert ranked["subject_judgments"]["黄金"]["direction"] == "unknown"
    structure = extract_report("# 黄金与白银走势\n\n## 结论\n> 黄金：中期多头结构仍在，但短线延续弱势。")
    assert structure["subject_judgments"]["黄金"]["direction"] == "mixed"


def test_subject_direction_changes_even_when_probabilities_are_not_comparable():
    first = extract_report("# 黄金与白银走势\n确认时间：2026-08-22 19:29\n\n## 结论\n> 黄金偏强；白银震荡。")
    second = extract_report("# 黄金与白银走势\n确认时间：2026-08-23 19:29\n\n## 结论\n> 黄金短线偏弱；白银震荡。")
    result = compare_subject([first, second], "黄金")
    assert result["pairs"][0]["judgment_change"] == "下调"
    assert result["pairs"][0]["main_probability_delta"] is None


def test_later_asset_bullets_are_read_from_joint_conclusion():
    report = "# 黄金、白银、科创50、有色金属走势\n\n确认时间：2026-09-15 13:42\n\n## 一、结论先行\n- **黄金**：短线偏弱。\n- **白银**：今日反弹尚不足以确认止跌，仍处弱势。\n- **科创50**：今日超跌反弹，不是趋势反转。\n- **有色金属**：板块仍处弱势下行。"
    item = extract_report(report)
    assert item["subject_judgments"]["白银"]["direction"] == "bearish"
    assert item["subject_judgments"]["科创50"]["direction"] == "neutral"
    assert item["subject_judgments"]["有色"]["direction"] == "bearish"
    assert item["subject_judgments"]["有色"]["source_line"] == 9


def test_asset_judgment_heading_uses_following_forecast_paragraph():
    report = "# 黄金与白银走势\n\n## 一句话结论\n黄金：中期偏强，短线回撤。\n\n### 白银判断\n\n**未来1–5个交易日：高位震荡偏弱，未来1–4周仍有中期多头基础。**"
    item = extract_report(report)
    assert item["subject_judgments"]["白银"]["direction"] == "mixed"
    assert "未来1–5个交易日" in item["subject_judgments"]["白银"]["evidence"]


def test_later_forecast_sentence_can_follow_historical_summary():
    report = "# 半导体走势\n\n## 结论\n> 半导体上周经历大幅波动。后续1—3个月更可能进入区间宽幅震荡。"
    item = extract_report(report)
    assert item["subject_judgments"]["半导体"]["direction"] == "neutral"
    assert item["subject_judgments"]["半导体"]["evidence"].startswith("后续")


def test_risk_and_conditional_upgrade_are_not_current_direction():
    silver = extract_report("# 黄金与白银走势\n\n## 结论\n> 黄金偏多；白银弹性较大，但短线回撤风险较高。")
    star = extract_report("# 科创50走势\n\n## 结论\n> 科创50未来1—4周震荡偏弱，只有放量突破才把判断上调为趋势修复。")
    assert silver["subject_judgments"]["白银"]["direction"] == "unknown"
    assert star["subject_judgments"]["科创50"]["direction"] == "bearish"


def test_asset_scenario_fallback_uses_explicit_top_probability_label():
    report = "# 黄金与白银走势\n\n## 概率情景\n### 白银未来1—4周\n| 情景 | 概率 |\n|---|---:|\n| 高位震荡 | 50% |\n| 加速上行 | 30% |\n\n## 结论\n> 黄金偏多；白银弹性更大。"
    item = extract_report(report)
    assert item["subject_judgments"]["白银"]["direction"] == "neutral"
    assert item["subject_judgments"]["白银"]["evidence"] == "白银：高位震荡（主情景 50%）"


def test_tied_scenarios_do_not_force_an_asset_direction():
    report = "# 黄金与白银走势\n\n## 概率情景\n### 白银\n| 情景 | 概率 |\n|---|---:|\n| 震荡偏强 | 50% |\n| 震荡偏弱 | 50% |\n\n## 结论\n> 黄金偏多；白银波动较大。"
    assert extract_report(report)["subject_judgments"]["白银"]["direction"] == "unknown"


def test_fed_report_is_not_labeled_bearish_from_gold_comment():
    report = "# 美联储加息影响\n\n## 结论\n> 高利率维持，未来可能再加息；黄金短线承压。"
    item = extract_report(report)
    assert item["subject_judgments"]["美联储"]["direction"] == "not_applicable"
    assert item["subject_judgments"]["美联储"]["score"] is None


def test_relative_comparison_keeps_full_asset_sentence_without_inheriting_other_asset_direction():
    report = "# 黄金与白银走势\n\n## 结论\n> 黄金偏多；白银绝对趋势仍弱，但比黄金抗跌。"
    silver = extract_report(report)["subject_judgments"]["白银"]
    assert silver["direction"] == "bearish"
    assert "比黄金抗跌" in silver["evidence"]


def test_medium_silver_rally_and_short_term_decline_are_mixed():
    report = "# 黄金与白银走势\n\n## 一句话结论\n**黄金：中期偏强。**\n**白银：中期涨势强于黄金，但短线跌势更深，回撤风险更高。**"
    silver = extract_report(report)["subject_judgments"]["白银"]
    assert silver["direction"] == "mixed"
    assert "中期涨势" in silver["evidence"]
    weaker = extract_report("# 黄金与白银走势\n\n## 一句话结论\n**白银：中期涨势强于黄金，但短线明显更弱、波动更大。**")
    assert weaker["subject_judgments"]["白银"]["direction"] == "mixed"


def test_second_conclusion_quote_can_supply_single_topic_forecast():
    report = "# 半导体走势\n\n## 结论\n> 半导体上周经历拥挤交易踩踏。\n> 本周半导体超跌反弹延续，但上方有套牢盘。"
    item = extract_report(report)
    assert item["subject_judgments"]["半导体"]["direction"] == "neutral"
    assert item["subject_judgments"]["半导体"]["source_line"] == 5


def test_later_short_term_sentence_is_read_when_first_is_historical():
    report = "# 半导体走势\n\n## 结论\n> 半导体设备本周涨幅领先。融资和情绪指标意味着短期震荡不会结束。"
    item = extract_report(report)
    assert item["subject_judgments"]["半导体"]["direction"] == "neutral"
    assert "短期震荡" in item["subject_judgments"]["半导体"]["evidence"]
