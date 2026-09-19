"""SQLite 持久化：保存核验结果与人工复核反馈。"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core.config import settings

_DB_PATH = settings.project_root / "data" / "verifier.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification (
                task_id TEXT PRIMARY KEY,
                created_at TEXT,
                source_text TEXT,
                result_json TEXT,
                mode TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                claim_id TEXT,
                user_verdict TEXT,
                comment TEXT,
                created_at TEXT
            )
            """
        )


def save_verification(task_id: str, source_text: str, result: dict, mode: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO verification(task_id, created_at, source_text, result_json, mode) VALUES(?,?,?,?,?)",
            (task_id, datetime.now().isoformat(timespec="seconds"), source_text,
             json.dumps(result, ensure_ascii=False), mode),
        )


def get_verification(task_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM verification WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        return None
    data = json.loads(row["result_json"])
    data["task_id"] = row["task_id"]
    data["created_at"] = row["created_at"]
    data["mode"] = row["mode"]
    return data


def save_feedback(task_id: str, claim_id: str, user_verdict: str, comment: str) -> dict:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO feedback(task_id, claim_id, user_verdict, comment, created_at) VALUES(?,?,?,?,?)",
            (task_id, claim_id, user_verdict, comment, datetime.now().isoformat(timespec="seconds")),
        )
        row_id = cur.lastrowid
    return {"id": row_id, "task_id": task_id, "claim_id": claim_id, "user_verdict": user_verdict, "comment": comment}


def list_feedback(task_id: str | None = None) -> list[dict]:
    with _conn() as conn:
        if task_id:
            rows = conn.execute("SELECT * FROM feedback WHERE task_id=? ORDER BY id DESC", (task_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM feedback ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]
