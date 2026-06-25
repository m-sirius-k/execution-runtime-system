from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "runtime.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS task_spec (
    spec_id TEXT PRIMARY KEY,
    issued_by TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    intent TEXT NOT NULL,
    params_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_token (
    token_id TEXT PRIMARY KEY,
    spec_id TEXT NOT NULL REFERENCES task_spec(spec_id),
    spec_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    used_flag INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS execution_log (
    execution_id TEXT PRIMARY KEY,
    spec_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    result TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS execution_log_no_update
BEFORE UPDATE ON execution_log
BEGIN
    SELECT RAISE(ABORT, 'execution_log is append-only: update forbidden');
END;

CREATE TRIGGER IF NOT EXISTS execution_log_no_delete
BEFORE DELETE ON execution_log
BEGIN
    SELECT RAISE(ABORT, 'execution_log is append-only: delete forbidden');
END;
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level="IMMEDIATE")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def insert_task_spec(spec) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO task_spec (spec_id, issued_by, issued_at, intent, params_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (spec.spec_id, spec.issued_by, spec.issued_at, spec.intent, json.dumps(spec.params)),
        )


def insert_approval_token(token_id: str, spec_id: str, spec_hash: str, signature_hex: str,
                           scope: dict, issued_at: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO approval_token (token_id, spec_id, spec_hash, signature, scope_json, "
            "issued_at, used_flag) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (token_id, spec_id, spec_hash, signature_hex, json.dumps(scope), issued_at),
        )


def get_task_spec(spec_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM task_spec WHERE spec_id = ?", (spec_id,)
        ).fetchone()


def get_approval_token(token_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM approval_token WHERE token_id = ?", (token_id,)
        ).fetchone()


def mark_token_used(token_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE approval_token SET used_flag = 1 WHERE token_id = ?", (token_id,)
        )


def claim_token(token_id: str) -> bool:
    """Atomically marks a token used iff it was not already used.

    Returns True only for the single caller that wins the race; all
    concurrent callers on the same token_id receive False.
    """
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE approval_token SET used_flag = 1 WHERE token_id = ? AND used_flag = 0",
            (token_id,),
        )
        return cursor.rowcount > 0


def append_execution_log(execution_id: str, spec_id: str, token_id: str,
                          result: str, status: str, timestamp: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO execution_log (execution_id, spec_id, token_id, result, status, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (execution_id, spec_id, token_id, result, status, timestamp),
        )
