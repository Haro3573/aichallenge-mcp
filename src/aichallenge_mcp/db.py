from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .models import Competition, utc_now_iso


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS competitions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_run_id INTEGER NOT NULL,
                    FOREIGN KEY(last_run_id) REFERENCES runs(id)
                );

                CREATE TABLE IF NOT EXISTS changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    competition_id TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    before_json TEXT,
                    after_json TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id),
                    FOREIGN KEY(competition_id) REFERENCES competitions(id)
                );
                """
            )

    def start_run(self) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO runs(started_at, status) VALUES (?, ?)",
                (utc_now_iso(), "running"),
            )
            return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        item_count: int = 0,
        error: str | None = None,
    ) -> None:
        with self.connect() as db:
            db.execute(
                """
                UPDATE runs
                SET finished_at = ?, status = ?, item_count = ?, error = ?
                WHERE id = ?
                """,
                (utc_now_iso(), status, item_count, error, run_id),
            )

    def upsert(self, item: Competition, run_id: int) -> str:
        now = utc_now_iso()
        payload = json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True)
        fingerprint = item.fingerprint()

        with self.connect() as db:
            old = db.execute(
                "SELECT * FROM competitions WHERE id = ?", (item.id,)
            ).fetchone()

            if old is None:
                db.execute(
                    """
                    INSERT INTO competitions
                    (id, title, status, payload_json, fingerprint, first_seen_at,
                     last_seen_at, last_run_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (item.id, item.title, item.status, payload, fingerprint, now, now, run_id),
                )
                db.execute(
                    """
                    INSERT INTO changes
                    (run_id, competition_id, change_type, before_json, after_json, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, item.id, "new", None, payload, now),
                )
                return "new"

            change_type = "unchanged"
            if old["fingerprint"] != fingerprint:
                change_type = "changed"
                before = old["payload_json"]
                db.execute(
                    """
                    INSERT INTO changes
                    (run_id, competition_id, change_type, before_json, after_json, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, item.id, change_type, before, payload, now),
                )

            db.execute(
                """
                UPDATE competitions
                SET title = ?, status = ?, payload_json = ?, fingerprint = ?,
                    last_seen_at = ?, last_run_id = ?
                WHERE id = ?
                """,
                (item.title, item.status, payload, fingerprint, now, run_id, item.id),
            )
            return change_type

    def active(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload_json FROM competitions"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        else:
            query += " WHERE status IN ('접수중', '진행중')"
        query += " ORDER BY title COLLATE NOCASE"

        with self.connect() as db:
            rows = db.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = f"%{query.strip()}%"
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT payload_json FROM competitions
                WHERE title LIKE ? OR payload_json LIKE ?
                ORDER BY title COLLATE NOCASE
                """,
                (needle, needle),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def fetch(self, item_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload_json FROM competitions WHERE id = ?", (item_id,)
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def changes_for_run(self, run_id: int) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT change_type, competition_id, before_json, after_json
                FROM changes WHERE run_id = ? ORDER BY id
                """,
                (run_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "change_type": row["change_type"],
                    "competition_id": row["competition_id"],
                    "before": json.loads(row["before_json"])
                    if row["before_json"]
                    else None,
                    "after": json.loads(row["after_json"]),
                }
            )
        return result
