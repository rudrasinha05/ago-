"""M6 organizational calendar: permissioned, local-only commitments and RSVPs."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from ago.security import Principal


class CalendarStore:
    def __init__(self, db):
        self.db = db

    def schedule(
        self, *, actor: Principal, title: str, starts_at: datetime,
        ends_at: datetime, operation_key: str, detail: str = "",
        visibility: str = "tenant", employee_ids: list[str] | None = None,
        goal_id: str | None = None, task_id: str | None = None,
    ) -> str:
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if (starts_at.tzinfo is None or ends_at.tzinfo is None
                or starts_at.utcoffset() is None or ends_at.utcoffset() is None):
            raise ValueError("Calendar datetimes must include timezone offsets")
        if not starts_at < ends_at <= starts_at + timedelta(days=366):
            raise ValueError("Invalid event duration")
        if not 1 <= len(title.strip()) <= 250 or len(detail) > 6000:
            raise ValueError("Invalid calendar content")
        if not 1 <= len(operation_key) <= 160:
            raise ValueError("Invalid event idempotency key")
        if visibility not in ("private", "tenant"):
            raise ValueError("Invalid visibility")
        attendee_ids = list(dict.fromkeys(employee_ids or []))
        if len(attendee_ids) > 100:
            raise ValueError("Too many attendees")
        for value in attendee_ids + [x for x in (goal_id, task_id) if x]:
            UUID(value)
        with self.db.transaction():
            row = self.db.execute(
                """SELECT id,creator_id,title,detail,starts_at,ends_at,
                          visibility,goal_id,task_id
                   FROM ago_calendar_events
                   WHERE tenant_id=%s AND operation_key=%s""",
                (actor.tenant_id, operation_key),
            ).fetchone()
            if row is not None:
                expected = (actor.subject, title.strip(), detail,
                            starts_at, ends_at, visibility,
                            goal_id, task_id)
                actual = (str(row["creator_id"]), row["title"], row["detail"],
                          row["starts_at"], row["ends_at"], row["visibility"],
                          str(row["goal_id"]) if row["goal_id"] else None,
                          str(row["task_id"]) if row["task_id"] else None)
                if expected != actual:
                    raise PermissionError("Calendar idempotency key reused")
                recorded = {
                    str(r["employee_id"]) for r in self.db.execute(
                        """SELECT employee_id FROM ago_calendar_attendees
                           WHERE tenant_id=%s AND event_id=%s""",
                        (actor.tenant_id, row["id"]),
                    ).fetchall()
                }
                if recorded != set(attendee_ids):
                    raise PermissionError("Calendar key cannot change attendees")
                return str(row["id"])
            event_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_calendar_events
                   (id,tenant_id,creator_id,title,detail,starts_at,ends_at,
                    visibility,operation_key,goal_id,task_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (event_id, actor.tenant_id, actor.subject, title.strip(),
                 detail, starts_at, ends_at, visibility, operation_key,
                 goal_id, task_id),
            )
            self._audit(actor, event_id, 'scheduled', title.strip())
            for employee_id in attendee_ids:
                self.db.execute(
                    """INSERT INTO ago_calendar_attendees(tenant_id,event_id,employee_id)
                       VALUES (%s,%s,%s)""",
                    (actor.tenant_id, event_id, employee_id),
                )
        return event_id

    def list(self, *, actor: Principal, start: datetime,
             end: datetime) -> list[dict]:
        if start.tzinfo is None or end.tzinfo is None or not start < end:
            raise ValueError("Invalid calendar query range")
        if end > start + timedelta(days=366):
            raise ValueError("Calendar query exceeds one year")
        rows = self.db.execute(
            """SELECT e.id,e.title,e.detail,e.starts_at,e.ends_at,
                      e.visibility,e.status,e.goal_id,e.task_id,e.creator_id,
                      EXISTS(
                        SELECT 1 FROM ago_calendar_attendees invited
                        WHERE invited.tenant_id=e.tenant_id
                          AND invited.event_id=e.id AND invited.employee_id=%s
                      ) AS invited
               FROM ago_calendar_events e
               WHERE e.tenant_id=%s AND e.starts_at < %s AND e.ends_at > %s
                 AND (e.visibility='tenant' OR e.creator_id=%s
                   OR EXISTS(
                       SELECT 1 FROM ago_calendar_attendees a
                       WHERE a.tenant_id=e.tenant_id AND a.event_id=e.id
                         AND a.employee_id=%s))
               ORDER BY e.starts_at,e.id LIMIT 500""",
            (actor.subject, actor.tenant_id, end, start, actor.subject, actor.subject),
        ).fetchall()
        return [dict(r) for r in rows]

    def cancel(self, *, actor: Principal, event_id: str) -> None:
        UUID(event_id)
        with self.db.transaction():
            event = self.db.execute(
                """SELECT creator_id,status FROM ago_calendar_events
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, event_id),
            ).fetchone()
            if event is None:
                raise LookupError("Event not found")
            if str(event["creator_id"]) != actor.subject or event["status"] != "scheduled":
                raise PermissionError("Only creator may cancel a scheduled event")
            self.db.execute(
                """UPDATE ago_calendar_events SET status='cancelled'
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, event_id),
            )
            self._audit(actor, event_id, "cancelled", "Creator cancelled event")

    def respond(self, *, actor: Principal, event_id: str, response: str) -> None:
        UUID(event_id)
        if response not in ("accepted", "declined"):
            raise ValueError("Invalid calendar response")
        with self.db.transaction():
            event = self.db.execute(
                """SELECT status FROM ago_calendar_events
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, event_id),
            ).fetchone()
            if event is None or event["status"] != "scheduled":
                raise PermissionError("Event is not scheduled in tenant")
            changed = self.db.execute(
                """UPDATE ago_calendar_attendees SET response=%s
                   WHERE tenant_id=%s AND event_id=%s AND employee_id=%s
                   RETURNING employee_id""",
                (response, actor.tenant_id, event_id, actor.subject),
            ).fetchone()
            if changed is None:
                raise PermissionError("Only invited employee may respond")
            self._audit(actor, event_id, response, "Attendee response")

    def attendees(self, *, actor: Principal, event_id: str) -> list[dict]:
        UUID(event_id)
        visible = self.db.execute(
            """SELECT 1 FROM ago_calendar_events e
               WHERE e.tenant_id=%s AND e.id=%s
                 AND (e.visibility='tenant' OR e.creator_id=%s
                   OR EXISTS(
                     SELECT 1 FROM ago_calendar_attendees a
                     WHERE a.tenant_id=e.tenant_id AND a.event_id=e.id
                       AND a.employee_id=%s))""",
            (actor.tenant_id, event_id, actor.subject, actor.subject),
        ).fetchone()
        if visible is None:
            raise PermissionError("Event not visible")
        return [dict(row) for row in self.db.execute(
            """SELECT employee_id,response FROM ago_calendar_attendees
               WHERE tenant_id=%s AND event_id=%s ORDER BY employee_id""",
            (actor.tenant_id, event_id),
        ).fetchall()]

    def _audit(self, actor: Principal, event_id: str, event: str, note: str) -> None:
        self.db.execute(
            """INSERT INTO ago_calendar_audit
               (id,tenant_id,event_id,actor_id,event,note)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (str(uuid4()), actor.tenant_id, event_id, actor.subject, event, note),
        )

    def history(self, *, actor: Principal, event_id: str) -> list[dict]:
        self.attendees(actor=actor, event_id=event_id)
        return [dict(row) for row in self.db.execute(
            """SELECT actor_id,event,note,occurred_at FROM ago_calendar_audit
               WHERE tenant_id=%s AND event_id=%s
               ORDER BY event_order LIMIT 500""",
            (actor.tenant_id, event_id),
        ).fetchall()]
