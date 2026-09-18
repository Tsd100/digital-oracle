"""SQLite index and read-only source import for DO reports."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import re
from pathlib import Path

from .extract import extract_report
from .judgment import subject_judgments

DEFAULT_DB = Path(__file__).resolve().parents[2] / "web" / "timeline.db"
DEFAULT_ARCHIVE = Path(r"D:\坚果云同步\WS\Digital-Oracle-Reports")
SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
 hash TEXT PRIMARY KEY, title TEXT NOT NULL, extracted TEXT NOT NULL, content TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
 source_key TEXT PRIMARY KEY, report_hash TEXT NOT NULL, source_kind TEXT NOT NULL,
 FOREIGN KEY(report_hash) REFERENCES reports(hash)
);
CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(report_hash);
CREATE TABLE IF NOT EXISTS corrections (
 report_hash TEXT NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL,
 changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(report_hash, field)
);
CREATE TABLE IF NOT EXISTS correction_log (
 report_hash TEXT NOT NULL, field TEXT NOT NULL, old_value TEXT, new_value TEXT NOT NULL,
 changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class TimelineStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def add(self, source_key: str, content: str, source_kind: str = "file") -> str:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        parsed = extract_report(content)
        with self.connect() as conn:
            conn.execute("INSERT INTO reports VALUES (?, ?, ?, ?) ON CONFLICT(hash) DO UPDATE SET title=excluded.title, extracted=excluded.extracted, content=excluded.content",
                         (digest, parsed["title"], json.dumps(parsed, ensure_ascii=False), content))
            conn.execute("INSERT INTO sources VALUES (?, ?, ?) ON CONFLICT(source_key) DO UPDATE SET report_hash=excluded.report_hash, source_kind=excluded.source_kind",
                         (source_key, digest, source_kind))
            # A changed source may leave an old orphan; corrections stay tied to the old hash for audit.
            conn.execute("DELETE FROM reports WHERE hash NOT IN (SELECT report_hash FROM sources)")
        return digest

    def correct(self, digest: str, field: str, value):
        allowed = {"analysis_at", "data_as_of", "market_session", "horizon", "subjects", "summary", "main_probability", "extraction_status"}
        if field not in allowed:
            raise ValueError(f"field not correctable: {field}")
        with self.connect() as conn:
            if not conn.execute("SELECT 1 FROM reports WHERE hash=?", (digest,)).fetchone():
                raise KeyError(digest)
            prior = conn.execute("SELECT value FROM corrections WHERE report_hash=? AND field=?", (digest, field)).fetchone()
            encoded = json.dumps(value, ensure_ascii=False)
            conn.execute("INSERT INTO correction_log(report_hash, field, old_value, new_value) VALUES (?, ?, ?, ?)",
                         (digest, field, prior[0] if prior else None, encoded))
            conn.execute("INSERT INTO corrections(report_hash, field, value) VALUES (?, ?, ?) ON CONFLICT(report_hash, field) DO UPDATE SET value=excluded.value, changed_at=CURRENT_TIMESTAMP",
                         (digest, field, encoded))

    def _row(self, conn, row) -> dict:
        item = json.loads(row["extracted"])
        item["hash"] = row["hash"]
        item["sources"] = [r[0] for r in conn.execute("SELECT source_key FROM sources WHERE report_hash=? ORDER BY source_kind, source_key", (row["hash"],))]
        hints = [re.search(r"(20\d{2}-\d{2}-\d{2})[_-](\d{2})-(\d{2})", Path(source).name) for source in item["sources"]]
        item["source_time_hint"] = next((f"{m.group(1)} {m.group(2)}:{m.group(3)}" for m in hints if m), None)
        corrected_fields = set()
        for override in conn.execute("SELECT field, value FROM corrections WHERE report_hash=?", (row["hash"],)):
            item[override["field"]] = json.loads(override["value"])
            corrected_fields.add(override["field"])
        if corrected_fields & {"summary", "subjects"}:
            content = row["content"] if "content" in row.keys() else conn.execute("SELECT content FROM reports WHERE hash=?", (row["hash"],)).fetchone()[0]
            item["subject_judgments"] = subject_judgments(item.get("summary"), item.get("subjects", []), item.get("summary_line"), content)
        return item

    def list_reports(self, subject: str | None = None, limit: int = 1000) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT hash, extracted FROM reports").fetchall()
            items = [self._row(conn, row) for row in rows]
        if subject:
            items = [item for item in items if subject in item.get("subjects", [])]
        items.sort(key=lambda item: (item.get("analysis_at") is None, item.get("analysis_at") or item.get("source_time_hint") or "9999"))
        return items[:limit]

    def get_report(self, digest: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT hash, extracted, content FROM reports WHERE hash=?", (digest,)).fetchone()
            if not row:
                return None
            item = self._row(conn, row)
            item["content"] = row["content"]
            return item

    def counts(self) -> dict:
        with self.connect() as conn:
            rows = conn.execute("SELECT hash, extracted FROM reports").fetchall()
            needs_review = sum(self._row(conn, row)["extraction_status"] != "confirmed" for row in rows)
            return {"reports": len(rows),
                    "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
                    "needs_review": needs_review}


def import_sources(db_path: Path | str = DEFAULT_DB, folders: list[Path] | None = None,
                   web_db: Path | str | None = None) -> dict:
    store = TimelineStore(db_path)
    failures = []
    for folder in folders or []:
        folder = Path(folder)
        if not folder.exists():
            failures.append(f"目录不存在: {folder}")
            continue
        for path in sorted(folder.glob("*.md")):
            try:
                store.add(str(path.resolve()), path.read_text(encoding="utf-8-sig"), "file")
            except (OSError, UnicodeError, ValueError) as exc:
                failures.append(f"{path}: {exc}")
    if web_db and Path(web_db).exists():
        try:
            uri = Path(web_db).resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True) as source:
                for qid, report in source.execute("SELECT id, report FROM history WHERE status='done' AND report IS NOT NULL"):
                    try:
                        store.add(f"web:{qid}", report, "web")
                    except (ValueError, UnicodeError) as exc:
                        failures.append(f"web:{qid}: {exc}")
        except sqlite3.Error as exc:
            failures.append(f"Web 历史读取失败: {exc}")
    return {**store.counts(), "failures": failures}
