from pathlib import Path

from digital_oracle.timeline import TimelineStore
from web.app import create_app


def test_timeline_page_and_api_show_indexed_report(tmp_path, monkeypatch):
    import web.app as web_app
    db = tmp_path / "timeline.db"
    store = TimelineStore(db)
    digest = store.add("archive:test.md", "# 有色走势\n\n**确认北京时间：2026-08-26 21:18；分析窗口：未来 1—4 周。**\n\n## 结论\n> 偏强。")
    monkeypatch.setattr(web_app, "TIMELINE_DB", db, raising=False)
    app = create_app()
    client = app.test_client()
    assert client.get("/timeline").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/api/history").status_code == 200
    response = client.get("/api/timeline?subject=有色")
    assert response.status_code == 200
    assert response.json["reports"][0]["hash"] == digest
    assert "有色走势" in client.get(f"/api/timeline/report/{digest}").json["content"]
