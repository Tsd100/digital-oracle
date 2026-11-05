from pathlib import Path

from digital_oracle.timeline import TimelineStore
from digital_oracle.timeline import publish_report
from web.app import create_app
from web.analysis import _SYSTEM_PROMPT


def test_web_analysis_prompt_requires_structured_trend_block():
    assert "```do-trend" in _SYSTEM_PROMPT
    assert '"schema_version": "1.0"' in _SYSTEM_PROMPT
    assert "未分析的周期直接省略" in _SYSTEM_PROMPT


def test_timeline_page_and_api_show_indexed_report(tmp_path, monkeypatch):
    import web.app as web_app
    db = tmp_path / "timeline.db"
    store = TimelineStore(db)
    digest = store.add("archive:test.md", "# 有色走势\n\n**确认北京时间：2026-08-26 21:18；分析窗口：未来 1—4 周。**\n\n## 结论\n> 偏强。")
    monkeypatch.setattr(web_app, "TIMELINE_DB", db, raising=False)
    app = create_app()
    client = app.test_client()
    page = client.get("/timeline")
    assert page.status_code == 200
    assert b'id="trend-cards"' in page.data
    assert b'id="trend-chart"' in page.data
    assert b'id="automation-health"' in page.data
    assert b'id="theme-toggle"' in page.data
    assert b'localStorage.getItem("do-timeline-theme")' in page.data
    assert b'id="overview-title"' in page.data
    assert b'id="report-map-panel"' in page.data
    assert b'id="legacy-chart-anchor"' in page.data
    assert client.get("/").status_code == 200
    assert client.get("/api/history").status_code == 200
    response = client.get("/api/timeline?subject=有色")
    assert response.status_code == 200
    assert response.json["reports"][0]["hash"] == digest
    assert response.json["counts"]["matching_needs_review"] == 0
    assert "有色走势" in client.get(f"/api/timeline/report/{digest}").json["content"]


def test_management_home_replaces_question_console_and_preserves_it_at_ask(tmp_path, monkeypatch):
    import web.app as web_app

    db = tmp_path / "timeline.db"
    TimelineStore(db).add(
        "archive:gold.md",
        "# 黄金走势\n\n确认北京时间：2026-11-02 10:30；分析窗口：未来 1—4 周。\n\n## 结论\n> 偏强。",
    )
    monkeypatch.setattr(web_app, "TIMELINE_DB", db, raising=False)
    client = create_app().test_client()

    home = client.get("/")
    assert home.status_code == 200
    assert b'id="management-overview"' in home.data
    assert b'id="recent-changes"' in home.data
    assert b'id="system-health"' in home.data
    assert b'id="horizon-matrix"' in home.data
    assert b'id="history-matrix"' in home.data
    assert b'id="signal-drawer"' in home.data
    assert b'id="question-form"' not in home.data

    ask = client.get("/ask")
    assert ask.status_code == 200
    assert b'id="question-form"' in ask.data
    assert b'href="/"' in ask.data


def test_management_summary_combines_subject_state_and_health(tmp_path, monkeypatch):
    import web.app as web_app

    db = tmp_path / "timeline.db"
    store = TimelineStore(db)
    store.add(
        "archive:gold-old.md",
        "# 黄金走势\n\n确认北京时间：2026-10-30 10:00；分析窗口：未来 1—4 周。\n\n## 结论\n> 偏弱。",
    )
    store.add(
        "archive:gold-new.md",
        "# 黄金走势\n\n确认北京时间：2026-11-02 10:30；分析窗口：未来 1—4 周。\n\n## 结论\n> 偏强。",
    )
    monkeypatch.setattr(web_app, "TIMELINE_DB", db, raising=False)
    monkeypatch.setattr(
        web_app,
        "get_history",
        lambda limit=50: [{"id": "q1", "question": "黄金走势", "status": "done", "created_at": "2026-11-02T02:30:00Z"}],
    )

    data = create_app().test_client().get("/api/management/summary").get_json()
    gold = next(item for item in data["subjects"] if item["name"] == "黄金")

    assert data["totals"]["reports"] == 2
    assert data["totals"]["chat_analyses"] == 1
    assert data["automation_health"]["errors"] == 0
    assert gold["latest_direction"] == "bullish"
    assert gold["previous_direction"] == "bearish"
    assert gold["latest_analysis_at"].startswith("2026-11-02")
    assert gold["report_count"] == 2
    assert [point["direction"] for point in gold["history"]] == ["bearish", "bullish"]
    assert gold["history"][1]["hash"]
    assert data["recent_changes"][0]["subject"] == "黄金"


def test_health_endpoint_checks_both_databases(tmp_path, monkeypatch):
    import web.app as web_app

    db = tmp_path / "timeline.db"
    monkeypatch.setattr(web_app, "TIMELINE_DB", db, raising=False)
    response = create_app().test_client().get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["timeline_db"] == "ok"
    assert response.get_json()["chat_db"] == "ok"


def test_timeline_counts_are_scoped_to_selected_subject_and_corrections(tmp_path, monkeypatch):
    import web.app as web_app
    db = tmp_path / "timeline.db"
    store = TimelineStore(db)
    pending = store.add("a", "# 原油走势\n\n## 结论\n> 偏弱。")
    store.add("b", "# 黄金走势\n\n## 结论\n> 偏强。")
    monkeypatch.setattr(web_app, "TIMELINE_DB", db, raising=False)
    client = create_app().test_client()
    counts = client.get("/api/timeline?subject=原油").json["counts"]
    assert counts["matching_needs_review"] == 1
    assert counts["needs_review"] == 2
    store.correct(pending, "extraction_status", "confirmed")
    counts = client.get("/api/timeline?subject=原油").json["counts"]
    assert counts["matching_needs_review"] == 0
    assert counts["needs_review"] == 1


def test_timeline_separates_joint_reports_from_single_subject_gaps(tmp_path, monkeypatch):
    import web.app as web_app
    db = tmp_path / "timeline.db"
    store = TimelineStore(db)
    store.add("joint", "# 黄金与白银走势\n\n## 结论\n> 黄金偏强，白银震荡。")
    store.add("gap", "# 黄金走势\n\n## 结论\n> 偏强。")
    store.add("ready", "# 黄金走势\n\n确认北京时间：2026-08-26 21:18；分析窗口：未来 1—4 周。\n\n## 结论\n> 偏强。")
    monkeypatch.setattr(web_app, "TIMELINE_DB", db, raising=False)
    counts = create_app().test_client().get("/api/timeline?subject=黄金").json["counts"]
    assert counts["matching_joint"] == 1
    assert counts["matching_single_needs_review"] == 1
    assert counts["matching_ready"] == 1
    assert counts["matching_needs_review"] == 2


def test_timeline_api_returns_structured_trends(tmp_path, monkeypatch):
    import json
    from web.app import create_app
    import web.app as app_module

    db = tmp_path / "timeline.db"
    monkeypatch.setattr(app_module, "TIMELINE_DB", db)
    payload = {"schema_version":"1.0","analysis_id":"gold-web","analysis_at":"2026-09-21T10:00:00+08:00","data_as_of":"2026-09-21T09:55:00+08:00","subjects":[{"subject_id":"gold","subject_name":"黄金","instrument":"XAUUSD","quote_currency":"USD","quote_unit":"oz","horizons":{"short":{"direction":"bullish","confidence":66,"summary":"短线偏多"}}}]}
    report = f"# 黄金\n```do-trend\n{json.dumps(payload, ensure_ascii=False)}\n```\n"
    publish_report(TimelineStore(db), "web:test", report, "web")
    data = create_app().test_client().get("/api/timeline?subject=黄金").get_json()
    assert data["current_state"][0]["direction"] == "bullish"
    assert data["trend_points"][0]["horizon"] == "short"
    assert data["trend_events"][0]["event_type"] == "initiated"
    assert data["automation_health"]["publications"] == 1
    management = create_app().test_client().get("/api/management/summary").get_json()
    assert management["automation_health"]["last_published_at"].endswith("Z")


def test_web_workflow_auto_publishes_and_returns_change_summary(tmp_path, monkeypatch):
    import json
    import web.app as app_module

    db = tmp_path / "timeline.db"
    payload = {"schema_version":"1.0","analysis_id":"gold-workflow","analysis_at":"2026-09-25T10:00:00+08:00","data_as_of":"2026-09-25T09:55:00+08:00","subjects":[{"subject_id":"gold","subject_name":"黄金","instrument":"XAUUSD","quote_currency":"USD","quote_unit":"oz","horizons":{"short":{"direction":"bullish","confidence":66,"summary":"短线偏多"}}}]}
    report = f"# 黄金\n```do-trend\n{json.dumps(payload, ensure_ascii=False)}\n```\n"
    monkeypatch.setattr(app_module, "TIMELINE_DB", db)
    monkeypatch.setattr(app_module, "run_fetch", lambda question, queue: {"results": {}})
    monkeypatch.setattr(app_module, "generate_report", lambda question, results, queue, model: report)
    monkeypatch.setattr(app_module, "save_report", lambda qid, content: None)
    monkeypatch.setattr(app_module, "update_status", lambda *args: None)
    monkeypatch.setattr(app_module, "_is_llm_configured", lambda: False)
    queue = app_module._create_stream("workflow-test")
    app_module._run_workflow("workflow-test", "黄金走势", "test-model")
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    done = next(message["data"] for message in messages if message["event"] == "done")
    assert done["trend_publication"]["updated_tracks"] == 1
    assert "黄金短线" in done["trend_publication"]["summary"]
    assert TimelineStore(db).automation_health()["publications"] == 1
