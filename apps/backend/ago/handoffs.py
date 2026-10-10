"""M6 tenant-scoped departmental handoffs. No external action execution."""
from __future__ import annotations

from uuid import UUID, uuid4

from ago.security import Principal
from ago.security_controls import SecurityControls


class HandoffStore:
    def __init__(self, db):
        self.db = db

    def request(
        self, *, actor: Principal, sender_department_id: str,
        receiver_department_id: str, assignee_id: str,
        title: str, brief: str, operation_key: str,
    ) -> str:
        for item in (actor.tenant_id, actor.subject, sender_department_id,
                     receiver_department_id, assignee_id):
            UUID(item)
        if sender_department_id == receiver_department_id:
            raise ValueError("Handoff requires distinct departments")
        if not 1 <= len(title.strip()) <= 250 or not 1 <= len(brief.strip()) <= 6000:
            raise ValueError("Handoff title and brief required")
        if not 1 <= len(operation_key) <= 160:
            raise ValueError("Invalid idempotency key")
        with self.db.transaction():
            existing = self.db.execute(
                """SELECT id,sender_department_id,receiver_department_id,
                          assignee_id,requester_id,title,brief
                   FROM ago_handoffs WHERE tenant_id=%s AND operation_key=%s""",
                (actor.tenant_id, operation_key),
            ).fetchone()
            if existing is not None:
                expected = (sender_department_id, receiver_department_id, assignee_id,
                            actor.subject, title.strip(), brief.strip())
                recorded = (str(existing["sender_department_id"]),
                            str(existing["receiver_department_id"]),
                            str(existing["assignee_id"]), str(existing["requester_id"]),
                            existing["title"], existing["brief"])
                if expected != recorded:
                    raise PermissionError("Idempotency key used for another handoff")
                return str(existing["id"])
            author = self.db.execute(
                """SELECT department_id,kind FROM ago_employees
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, actor.subject),
            ).fetchone()
            target = self.db.execute(
                """SELECT department_id FROM ago_employees
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, assignee_id),
            ).fetchone()
            if (author is None or author["kind"] != "human"
                    or str(author["department_id"]) != sender_department_id):
                raise PermissionError("Human requester must belong to sending department")
            if target is None or str(target["department_id"]) != receiver_department_id:
                raise PermissionError("Assignee must belong to receiving department")
            handoff_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_handoffs
                   (id,tenant_id,requester_id,sender_department_id,
                    receiver_department_id,assignee_id,title,brief,operation_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (handoff_id, actor.tenant_id, actor.subject, sender_department_id,
                 receiver_department_id, assignee_id, title.strip(),
                 brief.strip(), operation_key),
            )
            self._record(actor, handoff_id, "requested", brief.strip())
        return handoff_id

    def _record(self, actor: Principal, handoff_id: str, event: str, note: str) -> None:
        self.db.execute(
            """INSERT INTO ago_handoff_events
               (id,tenant_id,handoff_id,actor_id,event,note)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (str(uuid4()), actor.tenant_id, handoff_id, actor.subject, event, note),
        )

    def transition(
        self, *, actor: Principal, handoff_id: str, decision: str, note: str,
    ) -> dict:
        UUID(handoff_id)
        if decision not in ("accepted", "rejected", "completed"):
            raise ValueError("Invalid handoff transition")
        if not 1 <= len(note.strip()) <= 6000:
            raise ValueError("Transition evidence required")
        with self.db.transaction():
            row = self.db.execute(
                """SELECT status,requester_id,receiver_department_id,receiver_actor_id
                   FROM ago_handoffs WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, handoff_id),
            ).fetchone()
            if row is None:
                raise LookupError("Handoff not found")
            if not SecurityControls(self.db).permitted(
                actor, "operations:respond", actor.tenant_id,
            ):
                raise PermissionError("Receiver authorization required")
            human = self.db.execute(
                """SELECT department_id FROM ago_employees
                   WHERE tenant_id=%s AND id=%s AND kind='human'""",
                (actor.tenant_id, actor.subject),
            ).fetchone()
            if (human is None
                    or str(human["department_id"]) != str(row["receiver_department_id"])
                    or actor.subject == str(row["requester_id"])):
                raise PermissionError("Independent human from receiving department required")
            if decision in ("accepted", "rejected"):
                if row["status"] != "requested":
                    raise PermissionError("Handoff is no longer requested")
                receiver = actor.subject
            else:
                if row["status"] != "accepted" or actor.subject != str(row["receiver_actor_id"]):
                    raise PermissionError("Only accepting human may close accepted handoff")
                receiver = actor.subject
            self.db.execute(
                """UPDATE ago_handoffs SET status=%s,receiver_actor_id=%s,
                   conclusion=%s,updated_at=now()
                   WHERE id=%s AND tenant_id=%s""",
                (decision, receiver, note.strip(), handoff_id, actor.tenant_id),
            )
            self._record(actor, handoff_id, decision, note.strip())
        return {"id": handoff_id, "status": decision}

    def list(self, *, tenant_id: str, department_id: str | None = None) -> list[dict]:
        args = [tenant_id]
        condition = ""
        if department_id is not None:
            UUID(department_id)
            condition = " AND (sender_department_id=%s OR receiver_department_id=%s)"
            args.extend((department_id, department_id))
        rows = self.db.execute(
            """SELECT id,requester_id,sender_department_id,receiver_department_id,
                      assignee_id,title,brief,status,receiver_actor_id,conclusion,created_at
               FROM ago_handoffs WHERE tenant_id=%s""" + condition
            + " ORDER BY created_at DESC,id LIMIT 200",
            tuple(args),
        ).fetchall()
        return [dict(row) for row in rows]

    def history(self, *, tenant_id: str, handoff_id: str) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            """SELECT e.actor_id,e.event,e.note,e.created_at
               FROM ago_handoff_events e JOIN ago_handoffs h
                 ON h.id=e.handoff_id AND h.tenant_id=e.tenant_id
               WHERE e.tenant_id=%s AND e.handoff_id=%s
               ORDER BY e.created_at,e.id""",
            (tenant_id, handoff_id),
        ).fetchall()]
