"""SQLite transactional event outbox and consumer inbox for local/single-node use.

A production PostgreSQL adapter and background worker are separate deployment tasks.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from ago.events import Event


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteEventStore:
    def __init__(self, database: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(database), isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS event_outbox (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                correlation_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'delivered', 'dead')),
                attempts INTEGER NOT NULL DEFAULT 0,
                available_at TEXT NOT NULL,
                last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_outbox_pending
                ON event_outbox(status, available_at);
            CREATE TABLE IF NOT EXISTS event_inbox (
                consumer TEXT NOT NULL,
                event_id TEXT NOT NULL,
                handled_at TEXT NOT NULL,
                PRIMARY KEY (consumer, event_id)
            );
        """)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

    def enqueue(self, event: Event, connection: sqlite3.Connection | None = None) -> None:
        db = connection or self.connection
        db.execute(
            """INSERT INTO event_outbox
               (id, name, payload, occurred_at, correlation_id, available_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event.id, event.name, json.dumps(event.payload),
             event.occurred_at.isoformat(), event.correlation_id, _now()),
        )

    def pending(self, limit: int = 100) -> list[Event]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        rows = self.connection.execute(
            """SELECT * FROM event_outbox WHERE status='pending' AND available_at<=?
               ORDER BY available_at, rowid LIMIT ?""",
            (_now(), limit),
        ).fetchall()
        return [
            Event(name=r["name"], payload=json.loads(r["payload"]), id=r["id"],
                  occurred_at=datetime.fromisoformat(r["occurred_at"]),
                  correlation_id=r["correlation_id"])
            for r in rows
        ]

    def delivered(self, event_id: str) -> None:
        self.connection.execute(
            "UPDATE event_outbox SET status='delivered' WHERE id=?", (event_id,)
        )

    def failed(self, event_id: str, error: str, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        row = self.connection.execute(
            "SELECT attempts FROM event_outbox WHERE id=?", (event_id,)
        ).fetchone()
        if row is None:
            raise KeyError(event_id)
        attempts = row["attempts"] + 1
        status = "dead" if attempts >= max_attempts else "pending"
        delay = min(60 * 2 ** (attempts - 1), 3600)
        available = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
        self.connection.execute(
            """UPDATE event_outbox SET attempts=?, status=?, available_at=?, last_error=?
               WHERE id=?""",
            (attempts, status, available, error[:2000], event_id),
        )

    def already_handled(self, consumer: str, event_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM event_inbox WHERE consumer=? AND event_id=?",
            (consumer, event_id),
        ).fetchone()
        return row is not None

    def handle_once(
        self, consumer: str, event: Event, handler: Callable[[sqlite3.Connection, Event], None]
    ) -> bool:
        """Atomically record consumption and handler's writes on this same database."""
        with self.transaction() as connection:
            if self.already_handled(consumer, event.id):
                return False
            handler(connection, event)
            connection.execute(
                "INSERT INTO event_inbox(consumer, event_id, handled_at) VALUES (?, ?, ?)",
                (consumer, event.id, _now()),
            )
        return True

    def close(self) -> None:
        self.connection.close()
