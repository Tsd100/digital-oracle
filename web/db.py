"""SQLite database for chat history storage."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "digital_oracle.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id         TEXT PRIMARY KEY,
    question   TEXT NOT NULL,
    report     TEXT,
    status     TEXT NOT NULL DEFAULT 'pending',
    error_msg  TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_created
    ON history(created_at DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def insert_question(question: str, qid: str | None = None) -> str:
    qid = qid or _new_id()
    conn = get_connection()
    now = _now()
    conn.execute(
        "INSERT INTO history (id, question, status, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?)",
        (qid, question, now, now),
    )
    conn.commit()
    conn.close()
    return qid


def update_status(qid: str, status: str, error_msg: str | None = None) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE history SET status = ?, error_msg = ?, updated_at = ? WHERE id = ?",
        (status, error_msg, _now(), qid),
    )
    conn.commit()
    conn.close()


def save_report(qid: str, report: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE history SET report = ?, status = 'done', updated_at = ? WHERE id = ?",
        (report, _now(), qid),
    )
    conn.commit()
    conn.close()


def get_history(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, question, status, created_at FROM history ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_history_item(qid: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM history WHERE id = ?", (qid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_history_item(qid: str) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM history WHERE id = ?", (qid,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted
