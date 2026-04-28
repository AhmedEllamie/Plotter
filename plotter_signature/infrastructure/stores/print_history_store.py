from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_print_history_db_path() -> Path:
    """Repo root (folder containing `plotter_signature` package) / print_history.sqlite3."""
    # plotter_signature/infrastructure/stores/print_history_store.py -> parents[3] = repo root
    return Path(__file__).resolve().parents[3] / "print_history.sqlite3"


class PrintHistoryStore:
    """Persistent print/bulk job history with 30-day retention."""

    RETENTION_DAYS = 30

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or default_print_history_db_path()
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS print_jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    signature_file_name TEXT,
                    signature_sha256 TEXT,
                    copies_requested INTEGER NOT NULL DEFAULT 1,
                    copies_printed INTEGER,
                    queued_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error_message TEXT,
                    result_json TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_print_jobs_queued_at ON print_jobs(queued_at)")
            conn.commit()

    def _prune_locked(self, conn: sqlite3.Connection) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.RETENTION_DAYS)).isoformat()
        conn.execute("DELETE FROM print_jobs WHERE queued_at < ?", (cutoff,))

    def prune_old(self) -> None:
        with self._lock:
            with self._connect() as conn:
                self._prune_locked(conn)
                conn.commit()

    def insert_queued(
        self,
        *,
        job_type: str,
        signature_file_name: str,
        signature_sha256: str,
        copies_requested: int = 1,
        job_id: UUID | None = None,
    ) -> UUID:
        jid = job_id or uuid4()
        queued_at = _utc_now_iso()
        with self._lock:
            with self._connect() as conn:
                self._prune_locked(conn)
                conn.execute(
                    """
                    INSERT INTO print_jobs (
                        id, job_type, status, signature_file_name, signature_sha256,
                        copies_requested, copies_printed, queued_at, started_at, completed_at,
                        error_message, result_json
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, NULL)
                    """,
                    (
                        str(jid),
                        job_type,
                        "queued",
                        signature_file_name,
                        signature_sha256,
                        copies_requested,
                        queued_at,
                    ),
                )
                conn.commit()
        return jid

    def update_started(self, job_id: UUID) -> None:
        started_at = _utc_now_iso()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE print_jobs SET status = ?, started_at = ? WHERE id = ?",
                    ("started", started_at, str(job_id)),
                )
                conn.commit()

    def update_completed(
        self,
        job_id: UUID,
        *,
        status: str,
        copies_printed: int | None = None,
        error_message: str | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> None:
        completed_at = _utc_now_iso()
        result_blob = json.dumps(result_json, ensure_ascii=True) if result_json is not None else None
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE print_jobs SET
                        status = ?,
                        copies_printed = COALESCE(?, copies_printed),
                        completed_at = ?,
                        error_message = ?,
                        result_json = COALESCE(?, result_json)
                    WHERE id = ?
                    """,
                    (
                        status,
                        copies_printed,
                        completed_at,
                        error_message,
                        result_blob,
                        str(job_id),
                    ),
                )
                conn.commit()

    def list_since(
        self,
        *,
        days: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        days = days if days is not None else self.RETENTION_DAYS
        if days < 1:
            days = 1
        if limit < 1:
            limit = 1
        if limit > 2000:
            limit = 2000
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock:
            with self._connect() as conn:
                self._prune_locked(conn)
                conn.commit()
                cur = conn.execute(
                    """
                    SELECT * FROM print_jobs
                    WHERE queued_at >= ?
                    ORDER BY queued_at DESC
                    LIMIT ?
                    """,
                    (cutoff, limit),
                )
                rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            if d.get("result_json"):
                try:
                    d["result"] = json.loads(str(d["result_json"]))
                except json.JSONDecodeError:
                    d["result"] = None
            else:
                d["result"] = None
            del d["result_json"]
            out.append(d)
        return out
