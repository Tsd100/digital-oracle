from pathlib import Path

from digital_oracle.timeline import TimelineStore
from digital_oracle.timeline import publish_report
from web.app import create_app


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
    assert client.get("/").status_code == 200
    assert client.get("/api/history").status_code == 200
    response = client.get("/api/timeline?subject=有色")
    assert response.status_code == 200
    assert response.json["reports"][0]["hash"] == digest
    assert response.json["counts"]["matching_needs_review"] == 0
    assert "有色走势" in client.get(f"/api/timeline/report/{digest}").json["content"]


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
