from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_paths_follow_environment(monkeypatch, tmp_path):
    from web.config import runtime_paths

    monkeypatch.setenv("DO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DO_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("DO_ARCHIVE_DIR", str(tmp_path / "archive"))
    paths = runtime_paths(ROOT)

    assert paths.timeline_db == tmp_path / "data" / "timeline.db"
    assert paths.chat_db == tmp_path / "data" / "digital_oracle.db"
    assert paths.reports_dir == tmp_path / "reports"
    assert paths.archive_dir == tmp_path / "archive"


def test_docker_package_is_persistent_and_health_checked():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-web.txt").read_text(encoding="utf-8")

    assert "USER app" in dockerfile
    assert "gunicorn" in dockerfile.lower()
    assert "restart: unless-stopped" in compose
    assert "healthcheck:" in compose
    assert "/healthz" in compose
    assert "DO_DATA_DIR" in compose
    assert "./data:/app/data" in compose
    assert "./reports:/app/reports" in compose
    assert "gunicorn==" in requirements
    assert "Flask==" in requirements


def test_question_workspace_has_no_public_cdn_dependency():
    ask = (ROOT / "web" / "templates" / "ask.html").read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net" not in ask
    assert "/static/js/markdown-lite.js" in ask
