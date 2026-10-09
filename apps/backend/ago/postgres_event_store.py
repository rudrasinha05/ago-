"""PostgreSQL transactional outbox/inbox adapter using psycopg 3.

Requires a PostgreSQL database and the SQL migration in deploy/sql/.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from ago.events import Event

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


class PostgresEventStore:
    """Database-backed events. Use one instance per worker, not shared concurrently."""

    def __init__(self, dsn: str):
        if psycopg is None:
            raise RuntimeError("Install ago-backend[postgres] for PostgreSQL support")
        self.connection = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with self.connection.transaction():
            yield self.connection

    def enqueue(self, event: Event, connection: Any | None = None) -> None:
        db = connection or self.connection
        db.execute(
            """INSERT INTO event_outbox
                (id, name, payload, occurred_at, correlation_id, available_at)
                VALUES (%s, %s, %s::jsonb, %s, %s, now())""",
            (event.id, event.name, json.dumps(event.payload),
             event.occurred_at, event.correlation_id),
        )

    def pending(self, limit: int = 100) -> list[Event]:
        """Non-locking inspection. Use claim() for concurrent delivery workers."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        rows = self.connection.execute(
            """SELECT * FROM event_outbox WHERE status='pending'
               AND available_at<=now() ORDER BY available_at, id LIMIT %s""",
            (limit,),
        ).fetchall()
        return [self._event(row) for row in rows]

    @staticmethod
    def _event(row: dict[str, Any]) -> Event:
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return Event(
            id=str(row["id"]), name=row["name"], payload=payload,
            occurred_at=row["occurred_at"], correlation_id=row["correlation_id"]
        )

    def claim(self, worker_id: str, limit: int = 100, lease_seconds: int = 60) -> list[Event]:
        """Atomically lease due events using SKIP LOCKED for multiple workers."""
        if not worker_id or not 1 <= limit <= 1000 or not 1 <= lease_seconds <= 3600:
            raise ValueError("Invalid worker ID, limit or lease duration")
        with self.transaction() as db:
            rows = db.execute(
                """WITH due AS (
                     SELECT id FROM event_outbox
                     WHERE (status='pending' AND available_at<=now())
                        OR (status='leased' AND available_at<=now())
                     ORDER BY available_at, id
                     FOR UPDATE SKIP LOCKED LIMIT %s
                   )
                   UPDATE event_outbox o SET status='leased', lease_owner=%s,
                     available_at=now()+(%s * interval '1 second')
                   FROM due WHERE o.id=due.id RETURNING o.*""",
                (limit, worker_id, lease_seconds),
            ).fetchall()
        return [self._event(row) for row in rows]

    def delivered(self, event_id: str, worker_id: str) -> bool:
        row = self.connection.execute(
            """UPDATE event_outbox SET status='delivered', lease_owner=NULL
               WHERE id=%s AND status='leased' AND lease_owner=%s RETURNING id""",
            (event_id, worker_id),
        ).fetchone()
        return row is not None

    def failed(
        self, event_id: str, worker_id: str, error: str, max_attempts: int = 3
    ) -> bool:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        row = self.connection.execute(
            """UPDATE event_outbox
               SET attempts=attempts+1,
                   status=CASE WHEN attempts+1 >= %s THEN 'dead' ELSE 'pending' END,
                   available_at=now()+(
                       LEAST(60 * POWER(2, LEAST(attempts, 6)), 3600)
                       * interval '1 second'),
                   last_error=%s, lease_owner=NULL
               WHERE id=%s AND status='leased' AND lease_owner=%s RETURNING id""",
            (max_attempts, error[:2000], event_id, worker_id),
        ).fetchone()
        return row is not None

    def handle_once(
        self, consumer: str, event: Event, handler: Callable[[Any, Event], None]
    ) -> bool:
        """Exactly-once for DB writes in the same transaction; not external calls."""
        if not consumer:
            raise ValueError("consumer required")
        with self.transaction() as db:
            inserted = db.execute(
                """INSERT INTO event_inbox (consumer, event_id, handled_at)
                   VALUES (%s, %s, now()) ON CONFLICT DO NOTHING
                   RETURNING event_id""",
                (consumer, event.id),
            ).fetchone()
            if inserted is None:
                return False
            handler(db, event)
        return True

    def close(self) -> None:
        self.connection.close()
