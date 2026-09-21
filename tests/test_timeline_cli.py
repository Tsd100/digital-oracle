import json

from digital_oracle.timeline.cli import main


def test_cli_publish_returns_duplicate_status(tmp_path, capsys):
    payload = {"schema_version":"1.0","analysis_id":"gold-cli","analysis_at":"2026-09-21T10:00:00+08:00","data_as_of":"2026-09-21T10:00:00+08:00","subjects":[{"subject_id":"gold","subject_name":"黄金","instrument":"XAUUSD","quote_currency":"USD","quote_unit":"oz","horizons":{"short":{"direction":"bullish","confidence":60,"summary":"偏多"}}}]}
    path = tmp_path / "gold.md"
    path.write_text(f"# 黄金\n```do-trend\n{json.dumps(payload, ensure_ascii=False)}\n```\n", encoding="utf-8")
    db = tmp_path / "timeline.db"
    args = ["--db", str(db), "publish", str(path), "--source-kind", "codex"]
    main(args)
    first = json.loads(capsys.readouterr().out)
    main(args)
    second = json.loads(capsys.readouterr().out)
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert "黄金短线" in first["summary"]
