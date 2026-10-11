"""M6 organizational calendar: permissioned, local-only commitments and RSVPs."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.security import Principal


class CalendarStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def schedule(
        self,
        *,
        actor: Principal,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        operation_key: str,
        detail: str = "",
        visibility: str = "tenant",
        employee_ids: list[str] | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
    ) -> str:
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if (
            starts_at.tzinfo is None
            or ends_at.tzinfo is None
            or starts_at.utcoffset() is None
            or ends_at.utcoffset() is None
        ):
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
            self._lock(actor.tenant_id)
            row = self.db.execute(
                """SELECT id,creator_id,title,detail,starts_at,ends_at,
                          visibility,goal_id,task_id
                   FROM ago_calendar_events
                   WHERE tenant_id=%s AND operation_key=%s""",
                (actor.tenant_id, operation_key),
            ).fetchone()
            if row is not None:
                expected = (
                    actor.subject,
                    title.strip(),
                    detail,
                    starts_at,
                    ends_at,
                    visibility,
                    goal_id,
                    task_id,
                )
                actual = (
                    str(row["creator_id"]),
                    row["title"],
                    row["detail"],
                    row["starts_at"],
                    row["ends_at"],
                    row["visibility"],
                    str(row["goal_id"]) if row["goal_id"] else None,
                    str(row["task_id"]) if row["task_id"] else None,
                )
                if expected != actual:
                    raise PermissionError("Calendar idempotency key reused")
                recorded = {
                    str(r["employee_id"])
                    for r in self.db.execute(
                        """SELECT employee_id FROM ago_calendar_attendees
                           WHERE tenant_id=%s AND event_id=%s""",
                        (actor.tenant_id, row["id"]),
                    ).fetchall()
                }
                if recorded != set(attendee_ids):
                    raise PermissionError("Calendar key cannot change attendees")
                return str(row["id"])
            self._check_commitment(actor, starts_at, ends_at, attendee_ids)
            event_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_calendar_events
                   (id,tenant_id,creator_id,title,detail,starts_at,ends_at,
                    visibility,operation_key,goal_id,task_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    event_id,
                    actor.tenant_id,
                    actor.subject,
                    title.strip(),
                    detail,
                    starts_at,
                    ends_at,
                    visibility,
                    operation_key,
                    goal_id,
                    task_id,
                ),
            )
            self._audit(actor, event_id, "scheduled", title.strip())
            for employee_id in attendee_ids:
                self.db.execute(
                    """INSERT INTO ago_calendar_attendees(tenant_id,event_id,employee_id)
                       VALUES (%s,%s,%s)""",
                    (actor.tenant_id, event_id, employee_id),
                )
        return event_id

    def list(self, *, actor: Principal, start: datetime, end: datetime) -> list[dict]:
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
            self._lock(actor.tenant_id)
            event = self.db.execute(
                """SELECT creator_id,status FROM ago_calendar_events
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, event_id),
            ).fetchone()
            if event is None:
                raise LookupError("Event not found")
            if str(event["creator_id"]) != actor.subject or event["status"] != "scheduled":
                raise PermissionError("Only creator may cancel a scheduled event")
            if any(
                x["event_id"] == event_id or event_id in x["depends_on"]
                for x in self._state(actor.tenant_id)["links"]
            ):
                raise PermissionError("Governed event requires independently reviewed rescheduling")
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
            self._lock(actor.tenant_id)
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
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT employee_id,response FROM ago_calendar_attendees
               WHERE tenant_id=%s AND event_id=%s ORDER BY employee_id""",
                (actor.tenant_id, event_id),
            ).fetchall()
        ]

    def _audit(self, actor: Principal, event_id: str, event: str, note: str) -> None:
        self.db.execute(
            """INSERT INTO ago_calendar_audit
               (id,tenant_id,event_id,actor_id,event,note)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (str(uuid4()), actor.tenant_id, event_id, actor.subject, event, note),
        )

    def history(self, *, actor: Principal, event_id: str) -> list[dict]:
        self.attendees(actor=actor, event_id=event_id)
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT actor_id,event,note,occurred_at FROM ago_calendar_audit
               WHERE tenant_id=%s AND event_id=%s
               ORDER BY event_order LIMIT 500""",
                (actor.tenant_id, event_id),
            ).fetchall()
        ]

    def _lock(self, tenant_id: str) -> None:
        if (
            self.db.execute(
                "SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (str(UUID(tenant_id)),)
            ).fetchone()
            is None
        ):
            raise LookupError("Organization not found")

    def _founder(self, actor: Principal) -> None:
        from ago.security_controls import SecurityControls

        if not self.repositories.resolve(SecurityControls).permitted(
            actor, "calendar:write", actor.tenant_id
        ):
            raise PermissionError("Calendar governance permission required")
        if (
            self.db.execute(
                """SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
               JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
               WHERE u.tenant_id=%s AND u.id=%s AND u.active AND e.kind='human' AND r.role='founder'""",
                (actor.tenant_id, actor.subject),
            ).fetchone()
            is None
        ):
            raise PermissionError("Active human founder must author calendar governance")

    def _state(self, tenant_id: str) -> dict:
        from ago.enterprise_domains import CALENDAR_DOMAINS

        rows = self.db.execute(
            """SELECT c.revision,c.created_at,c.result,p.id,p.command,p.specification
               FROM ago_calendar_changes c JOIN ago_calendar_proposals p
               ON p.tenant_id=c.tenant_id AND p.id=c.proposal_id
               WHERE c.tenant_id=%s ORDER BY c.revision LIMIT 10001""",
            (tenant_id,),
        ).fetchall()
        if len(rows) > 10000:
            raise PermissionError(
                "Calendar history exceeds bounded projection; operator review required"
            )
        policies, windows, links, replacements = {}, {}, {}, {}
        for row in rows:
            spec = row["specification"]
            if row["command"] == "policy":
                policies[(spec["scope_kind"], spec["scope_id"])] = {
                    **spec,
                    "revision": row["revision"],
                }
            elif row["command"] == "window":
                windows[str(row["id"])] = {
                    **spec,
                    "id": str(row["id"]),
                    "revision": row["revision"],
                }
            elif row["command"] == "window_cancel":
                windows.pop(spec["window_id"], None)
            elif row["command"] == "event_link":
                links[spec["event_id"]] = spec
            elif row["command"] == "reschedule":
                for move in spec["moves"]:
                    old, new = move["event_id"], move["replacement_id"]
                    replacements[old] = new
                    if old in links:
                        links[new] = {**links.pop(old), "event_id": new}
                    for key, value in list(links.items()):
                        links[key] = {
                            **value,
                            "depends_on": [new if d == old else d for d in value["depends_on"]],
                        }
        return {
            "revision": rows[-1]["revision"] if rows else 0,
            "policies": list(policies.values()),
            "windows": list(windows.values()),
            "links": list(links.values()),
            "replacements": replacements,
            "domains": CALENDAR_DOMAINS,
            "configured": bool(rows),
            "authority_changed": False,
            "history_limit": 10000,
        }

    def governance(self, *, actor: Principal) -> dict:
        state = self._state(actor.tenant_id)
        proposals = self.db.execute(
            """SELECT p.*,a.status,a.reviewer_id,c.revision AS applied_revision
               FROM ago_calendar_proposals p JOIN ago_approval_requests a
                 ON a.tenant_id=p.tenant_id AND a.id=p.approval_id
               LEFT JOIN ago_calendar_changes c ON c.tenant_id=p.tenant_id AND c.proposal_id=p.id
               WHERE p.tenant_id=%s ORDER BY p.created_at DESC,p.id LIMIT 100""",
            (actor.tenant_id,),
        ).fetchall()
        signals = self.db.execute(
            """SELECT id,kind,detail,occurred_at FROM ago_calendar_timing_audit
               WHERE tenant_id=%s ORDER BY occurred_at DESC,id LIMIT 100""",
            (actor.tenant_id,),
        ).fetchall()
        return {
            **state,
            "proposals": [dict(x) for x in proposals],
            "signals": [dict(x) for x in signals],
            "read_limits": {"proposals": 100, "signals": 100},
            "baseline": "UTC continuous availability until reviewed policy; actual task approval is always required",
        }

    def approval_source(self, *, actor: Principal, approval_id: str) -> dict:
        row = self.db.execute(
            "SELECT * FROM ago_calendar_proposals WHERE tenant_id=%s AND approval_id=%s",
            (actor.tenant_id, str(UUID(approval_id))),
        ).fetchone()
        if row is None:
            raise LookupError("Calendar source package not found")
        return dict(row)

    def _entity(self, tenant_id: str, spec: dict) -> None:
        kind = spec.get("scope_kind")
        if kind in ("department", "employee"):
            # Explicit constant SQL; no caller-controlled table/identifier interpolation.
            query = (
                "SELECT id FROM ago_departments WHERE tenant_id=%s AND id=%s"
                if kind == "department"
                else "SELECT id FROM ago_employees WHERE tenant_id=%s AND id=%s"
            )
            if self.db.execute(query, (tenant_id, spec["scope_id"])).fetchone() is None:
                raise PermissionError(
                    "Calendar entity belongs to another organization or is absent"
                )

    def _event(self, actor: Principal, identifier: str) -> dict:
        row = self.db.execute(
            """SELECT id,creator_id,title,detail,starts_at,ends_at,visibility,status,goal_id,task_id
               FROM ago_calendar_events WHERE tenant_id=%s AND id=%s AND visibility='tenant'
                 AND status='scheduled'""",
            (actor.tenant_id, str(UUID(identifier))),
        ).fetchone()
        if row is None:
            raise PermissionError(
                "Governed changes require a scheduled shared event in this organization"
            )
        attendees = self.db.execute(
            "SELECT employee_id FROM ago_calendar_attendees WHERE tenant_id=%s AND event_id=%s ORDER BY employee_id",
            (actor.tenant_id, identifier),
        ).fetchall()
        result = {
            key: (
                value.isoformat()
                if isinstance(value, datetime)
                else str(value)
                if isinstance(value, UUID)
                else value
            )
            for key, value in dict(row).items()
        }
        result["employee_ids"] = [str(a["employee_id"]) for a in attendees]
        return result

    def _command(
        self, actor: Principal, command: str, specification: dict, state: dict
    ) -> tuple[dict, dict]:
        from ago.enterprise_domains import (
            validate_calendar_policy,
            validate_calendar_window,
            calendar_instant,
        )

        if not isinstance(specification, dict):
            raise ValueError("Calendar specification must be an object")
        source = {"revision": state["revision"]}
        if command == "policy":
            spec = validate_calendar_policy(specification)
            self._entity(actor.tenant_id, spec)
            for reviewer in spec["reviewer_ids"] + spec["emergency_reviewer_ids"]:
                if not self._human_available(actor.tenant_id, reviewer, None, state):
                    raise PermissionError(
                        "Calendar reviewers must be active humans with approval authority"
                    )
            source["previous_policy"] = next(
                (
                    p
                    for p in state["policies"]
                    if (p["scope_kind"], p["scope_id"]) == (spec["scope_kind"], spec["scope_id"])
                ),
                None,
            )
        elif command == "window":
            spec = validate_calendar_window(specification)
            self._entity(actor.tenant_id, spec)
            windows = {x["id"]: x for x in state["windows"]}
            for dependency in spec["depends_on"]:
                if dependency not in windows or calendar_instant(
                    windows[dependency]["slots"][-1]["ends_at"]
                ) > calendar_instant(spec["slots"][0]["starts_at"]):
                    raise PermissionError("Calendar handoff must follow an existing dependency")
            if spec["parent_id"]:
                parent = windows.get(spec["parent_id"])
                if parent is None or not all(
                    any(
                        calendar_instant(p["starts_at"])
                        <= calendar_instant(s["starts_at"])
                        < calendar_instant(s["ends_at"])
                        <= calendar_instant(p["ends_at"])
                        for p in parent["slots"]
                    )
                    for s in spec["slots"]
                ):
                    raise PermissionError("Calendar cycle must fit inside its parent horizon")
            source["dependencies"] = [windows[x] for x in spec["depends_on"]]
            source["parent"] = windows.get(spec["parent_id"])
        elif command == "window_cancel":
            if set(specification) != {"window_id"}:
                raise ValueError("Cancellation requires only the window id")
            spec = {"window_id": str(UUID(specification["window_id"]))}
            window = next((w for w in state["windows"] if w["id"] == spec["window_id"]), None)
            if window is None:
                raise PermissionError("Active temporal window required")
            if any(
                spec["window_id"] in w["depends_on"] or w["parent_id"] == spec["window_id"]
                for w in state["windows"]
            ):
                raise PermissionError(
                    "Dependent windows require reviewed cancellation before their parent"
                )
            source["window"] = window
        elif command == "event_link":
            if set(specification) - {"event_id", "depends_on", "goal_id", "task_id"}:
                raise ValueError("Unknown event-link field")
            event_id = str(UUID(specification["event_id"]))
            dependencies = specification.get("depends_on", [])
            if (
                not isinstance(dependencies, list)
                or len(dependencies) > 50
                or len(set(dependencies)) != len(dependencies)
            ):
                raise ValueError("Bounded unique event dependencies required")
            dependencies = [str(UUID(x)) for x in dependencies]
            source["event"] = self._event(actor, event_id)
            source["dependencies"] = [self._event(actor, x) for x in dependencies]
            if any(
                calendar_instant(x["ends_at"]) > calendar_instant(source["event"]["starts_at"])
                for x in source["dependencies"]
            ):
                raise PermissionError("Dependent event must follow its prerequisite")
            edges = {x["event_id"]: x["depends_on"] for x in state["links"]}

            def reaches(current, seen):
                if current == event_id:
                    return True
                if current in seen:
                    return False
                return any(reaches(x, seen | {current}) for x in edges.get(current, []))

            if any(reaches(x, set()) for x in dependencies):
                raise ValueError("Calendar dependencies must be acyclic")
            spec = {
                "event_id": event_id,
                "depends_on": dependencies,
                "goal_id": None,
                "task_id": None,
            }
            for key in ("goal_id", "task_id"):
                if specification.get(key):
                    identifier = str(UUID(specification[key]))
                    query = (
                        "SELECT id FROM ago_goals WHERE tenant_id=%s AND id=%s"
                        if key == "goal_id"
                        else "SELECT id FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s"
                    )
                    if self.db.execute(query, (actor.tenant_id, identifier)).fetchone() is None:
                        raise PermissionError(
                            "Event plan/task link must be within this organization"
                        )
                    spec[key] = identifier
        elif command == "reschedule":
            if set(specification) != {"event_id", "starts_at", "ends_at"}:
                raise ValueError("Reschedule requires event id and exact new boundaries")
            identifier = str(UUID(specification["event_id"]))
            event = self._event(actor, identifier)
            start, end = (
                calendar_instant(specification["starts_at"]),
                calendar_instant(specification["ends_at"]),
            )
            if not start < end <= start + timedelta(days=366):
                raise ValueError("Invalid replacement duration")
            delta = start - calendar_instant(event["starts_at"])
            affected = {identifier}
            changed = True
            while changed:
                changed = False
                for link in state["links"]:
                    if link["event_id"] not in affected and set(link["depends_on"]) & affected:
                        affected.add(link["event_id"])
                        changed = True
                if len(affected) > 100:
                    raise ValueError("Reschedule propagation exceeds 100 events")
            events = [event] + [self._event(actor, x) for x in sorted(affected - {identifier})]
            source["events"] = events
            moves = []
            for old in events:
                new_start = (
                    start if old["id"] == identifier else calendar_instant(old["starts_at"]) + delta
                )
                new_end = (
                    end if old["id"] == identifier else calendar_instant(old["ends_at"]) + delta
                )
                moves.append(
                    {
                        "event_id": old["id"],
                        "replacement_id": str(uuid4()),
                        "starts_at": new_start.isoformat(),
                        "ends_at": new_end.isoformat(),
                    }
                )
            boundaries = {m["event_id"]: m for m in moves}
            for link in state["links"]:
                current = boundaries.get(link["event_id"])
                if current:
                    for dependency in link["depends_on"]:
                        previous = boundaries.get(dependency) or self._event(actor, dependency)
                        if calendar_instant(previous["ends_at"]) > calendar_instant(
                            current["starts_at"]
                        ):
                            raise PermissionError("Reschedule would break dependent handoff")
            spec = {"event_id": identifier, "moves": moves}
            source["deadline_impact"] = [
                {
                    "event_id": m["event_id"],
                    "old_end": e["ends_at"],
                    "new_end": m["ends_at"],
                    "task_id": next(
                        (x.get("task_id") for x in state["links"] if x["event_id"] == e["id"]),
                        e["task_id"],
                    ),
                    "goal_id": e["goal_id"],
                }
                for e, m in zip(events, moves)
            ]
        else:
            raise ValueError("Unknown calendar governance command")
        return spec, source

    def propose_governance(
        self,
        *,
        actor: Principal,
        command: str,
        specification: dict,
        rationale: str,
        operation_key: str,
        base_revision: int,
    ) -> dict:
        from hashlib import sha256
        from json import dumps
        from ago.governance import ApprovalRepository

        self._founder(actor)
        if (
            not isinstance(rationale, str)
            or not 1 <= len(rationale.strip()) <= 6000
            or not 1 <= len(operation_key) <= 160
            or type(base_revision) is not int
            or base_revision < 0
        ):
            raise ValueError(
                "Calendar review needs rationale, operation key and nonnegative revision"
            )
        with self.db.transaction():
            self._lock(actor.tenant_id)
            prior = self.db.execute(
                "SELECT * FROM ago_calendar_proposals WHERE tenant_id=%s AND operation_key=%s",
                (actor.tenant_id, operation_key),
            ).fetchone()
            if prior:
                if (
                    str(prior["actor_id"]),
                    prior["command"],
                    prior["base_revision"],
                    prior["rationale"],
                    prior["source"].get("input"),
                ) != (actor.subject, command, base_revision, rationale.strip(), specification):
                    raise PermissionError("Calendar retry cannot change the reviewed package")
                return dict(prior)
            state = self._state(actor.tenant_id)
            if state["revision"] != base_revision:
                raise PermissionError("Calendar source revision changed; review current state")
            try:
                spec, source = self._command(actor, command, specification, state)
            except (KeyError, TypeError, AttributeError) as exc:
                raise ValueError("Incomplete or malformed calendar specification") from exc
            source["input"] = specification
            digest = sha256(
                dumps(
                    {
                        "command": command,
                        "specification": spec,
                        "source": source,
                        "rationale": rationale.strip(),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            identifier = str(uuid4())
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=actor.tenant_id,
                requester_id=actor.subject,
                action="calendar:review:" + identifier + ":" + digest,
            )
            self.db.execute(
                """INSERT INTO ago_calendar_proposals(id,tenant_id,actor_id,approval_id,operation_key,
                   base_revision,command,specification,source,rationale,digest)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)""",
                (
                    identifier,
                    actor.tenant_id,
                    actor.subject,
                    approval.request_id,
                    operation_key,
                    base_revision,
                    command,
                    dumps(spec, sort_keys=True),
                    dumps(source, sort_keys=True),
                    rationale.strip(),
                    digest,
                ),
            )
            return {
                "id": identifier,
                "approval_id": approval.request_id,
                "base_revision": base_revision,
                "command": command,
                "specification": spec,
                "source": source,
                "digest": digest,
            }

    def apply_governance(self, *, actor: Principal, proposal_id: str) -> dict:
        from json import dumps
        from ago.security_controls import SecurityControls

        self._founder(actor)
        with self.db.transaction():
            self._lock(actor.tenant_id)
            proposal = self.db.execute(
                "SELECT * FROM ago_calendar_proposals WHERE tenant_id=%s AND id=%s",
                (actor.tenant_id, str(UUID(proposal_id))),
            ).fetchone()
            if proposal is None or str(proposal["actor_id"]) != actor.subject:
                raise PermissionError("Original human calendar proposer required")
            prior = self.db.execute(
                "SELECT revision,result FROM ago_calendar_changes WHERE tenant_id=%s AND proposal_id=%s",
                (actor.tenant_id, proposal_id),
            ).fetchone()
            if prior:
                return {
                    "revision": prior["revision"],
                    "result": prior["result"],
                    "idempotent": True,
                }
            state = self._state(actor.tenant_id)
            if proposal["base_revision"] != state["revision"]:
                raise PermissionError("Calendar proposal is stale; new exact review required")
            approval = self.db.execute(
                "SELECT * FROM ago_approval_requests WHERE tenant_id=%s AND id=%s FOR UPDATE",
                (actor.tenant_id, proposal["approval_id"]),
            ).fetchone()
            if (
                approval is None
                or approval["status"] != "approved"
                or approval["action"] != "calendar:review:" + proposal_id + ":" + proposal["digest"]
                or str(approval["requester_id"]) != actor.subject
                or str(approval["reviewer_id"]) == actor.subject
                or not self._human_available(
                    actor.tenant_id, str(approval["reviewer_id"]), None, state
                )
                or not self.repositories.resolve(SecurityControls).permitted(
                    Principal(str(approval["reviewer_id"]), actor.tenant_id, ()),
                    "approval:decide",
                    actor.tenant_id,
                )
            ):
                raise PermissionError("Independent active human exact calendar approval required")
            # Re-read every mutable event/dependency input before application.
            checked, current = self._command(
                actor, proposal["command"], proposal["source"]["input"], state
            )
            original = {k: v for k, v in proposal["source"].items() if k != "input"}
            if current != original:
                raise PermissionError("Calendar source event/dependency changed since review")
            if proposal["command"] != "reschedule" and checked != proposal["specification"]:
                raise PermissionError("Calendar package normalization changed")
            spec = proposal["specification"]
            result = {
                "command": proposal["command"],
                "proposal_id": proposal_id,
                "authority_changed": False,
                "rescheduled": [],
            }
            if proposal["command"] == "reschedule":
                for old, move in zip(proposal["source"]["events"], spec["moves"]):
                    self._check_commitment(
                        actor,
                        datetime.fromisoformat(move["starts_at"]),
                        datetime.fromisoformat(move["ends_at"]),
                        old["employee_ids"],
                        exclude_ids=[m["event_id"] for m in spec["moves"]],
                    )
                for old, move in zip(proposal["source"]["events"], spec["moves"]):
                    self.db.execute(
                        "UPDATE ago_calendar_events SET status='cancelled' WHERE tenant_id=%s AND id=%s AND status='scheduled'",
                        (actor.tenant_id, old["id"]),
                    )
                    self._audit(
                        actor,
                        old["id"],
                        "cancelled",
                        "Reviewed replacement " + move["replacement_id"],
                    )
                    new_id = move["replacement_id"]
                    self.db.execute(
                        """INSERT INTO ago_calendar_events
                        (id,tenant_id,creator_id,title,detail,starts_at,ends_at,visibility,operation_key,goal_id,task_id)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,'tenant',%s,%s,%s)""",
                        (
                            new_id,
                            actor.tenant_id,
                            actor.subject,
                            old["title"],
                            old["detail"],
                            move["starts_at"],
                            move["ends_at"],
                            "reschedule:" + proposal_id + ":" + old["id"],
                            old["goal_id"],
                            old["task_id"],
                        ),
                    )
                    self._audit(actor, new_id, "scheduled", "Reviewed replacement of " + old["id"])
                    for employee_id in old["employee_ids"]:
                        self.db.execute(
                            """INSERT INTO ago_calendar_attendees(tenant_id,event_id,employee_id)
                            VALUES(%s,%s,%s)""",
                            (actor.tenant_id, new_id, employee_id),
                        )
                    result["rescheduled"].append({**move, "previous_id": old["id"]})
            revision = state["revision"] + 1
            self.db.execute(
                """INSERT INTO ago_calendar_changes(id,tenant_id,proposal_id,actor_id,revision,result)
                   VALUES(%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    str(uuid4()),
                    actor.tenant_id,
                    proposal_id,
                    actor.subject,
                    revision,
                    dumps(result, sort_keys=True),
                ),
            )
            self._timing(actor.tenant_id, "applied:" + proposal_id, "governed_change", result)
            return {"revision": revision, "result": result, "idempotent": False}

    def _timing(self, tenant_id: str, operation_key: str, kind: str, detail: dict) -> None:
        from json import dumps

        self.db.execute(
            """INSERT INTO ago_calendar_timing_audit(id,tenant_id,operation_key,kind,detail)
               VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT(tenant_id,operation_key) DO NOTHING""",
            (
                str(uuid4()),
                tenant_id,
                operation_key,
                kind,
                dumps(detail, sort_keys=True, default=str),
            ),
        )

    def _human_available(
        self,
        tenant_id: str,
        identifier: str,
        at: datetime | None,
        state: dict,
        duration_minutes: int = 1,
    ) -> bool:
        from ago.enterprise_domains import calendar_policy_reasons

        cache = state.setdefault("_humans", {})
        if identifier not in cache:
            cache[identifier] = self.db.execute(
                """SELECT e.department_id FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
               JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
               JOIN ago_role_permissions p ON p.tenant_id=r.tenant_id AND p.role=r.role
               WHERE u.tenant_id=%s AND u.id=%s AND u.active AND e.kind='human'
                 AND p.permission='approval:decide' LIMIT 1""",
                (tenant_id, identifier),
            ).fetchone()
        row = cache[identifier]
        if row is None:
            return False
        if at is None:
            return True
        policies = self._applicable(state["policies"], identifier, str(row["department_id"]))
        return not any(
            calendar_policy_reasons(p, at, duration_minutes) for p in policies
        ) and not self._window_reasons(
            state["windows"],
            identifier,
            str(row["department_id"]),
            at,
            duration_minutes,
            human=True,
        )

    @staticmethod
    def _applicable(values: list[dict], employee_id: str, department_id: str) -> list[dict]:
        return [
            x
            for x in values
            if x["scope_kind"] == "company"
            or (x["scope_kind"] == "employee" and x["scope_id"] == employee_id)
            or (x["scope_kind"] == "department" and x["scope_id"] == department_id)
        ]

    def _window_reasons(
        self,
        windows: list[dict],
        employee_id: str,
        department_id: str,
        at: datetime,
        duration: int,
        *,
        human: bool = False,
    ) -> list[str]:
        from ago.enterprise_domains import calendar_instant

        end = at + timedelta(minutes=duration)
        reasons = set()
        scoped = self._applicable(windows, employee_id, department_id)
        for window in scoped:
            if window["kind"] in ("maintenance", "incident", "release_freeze", "quiet"):
                if any(
                    calendar_instant(s["starts_at"]) < end and calendar_instant(s["ends_at"]) > at
                    for s in window["slots"]
                ):
                    reasons.add(window["kind"])
        for kind in ("approval",) if human else ("execution", "budget"):
            applicable = [w for w in scoped if w["kind"] == kind]
            if applicable and not any(
                calendar_instant(s["starts_at"]) <= at < end <= calendar_instant(s["ends_at"])
                for w in applicable
                for s in w["slots"]
            ):
                reasons.add("outside_" + kind + "_window")
        return sorted(reasons)

    def _eligibility(
        self,
        tenant_id: str,
        employee_id: str,
        at: datetime,
        duration_minutes: int,
        state: dict,
        task_id: str | None = None,
    ) -> dict:
        from ago.enterprise_domains import calendar_instant, calendar_policy_reasons

        at = calendar_instant(at)
        if type(duration_minutes) is not int or not 1 <= duration_minutes <= 1440:
            raise ValueError("Reservation duration must be 1 through 1440 minutes")
        workers = state.setdefault("_workers", {})
        if employee_id not in workers:
            workers[employee_id] = self.db.execute(
                "SELECT department_id,kind FROM ago_employees WHERE tenant_id=%s AND id=%s",
                (tenant_id, str(UUID(employee_id))),
            ).fetchone()
        worker = workers[employee_id]
        if worker is None:
            raise PermissionError("Calendar employee not in organization")
        department = str(worker["department_id"])
        policies = self._applicable(state["policies"], employee_id, department)
        reasons = set(
            self._window_reasons(state["windows"], employee_id, department, at, duration_minutes)
        )
        for policy in policies:
            reasons.update(calendar_policy_reasons(policy, at, duration_minutes))
            if policy["require_supervisor"] and not any(
                self._human_available(tenant_id, x, at, state, duration_minutes) for x in policy["reviewer_ids"]
            ):
                reasons.add("human_reviewer_unavailable")
        # Real state remains authoritative; calendar does not wake a sleeping or terminated worker.
        recent_states = state.setdefault("_worker_states", {})
        if employee_id not in recent_states:
            recent_states[employee_id] = self.db.execute(
                """SELECT state FROM ago_worker_state_events WHERE tenant_id=%s AND employee_id=%s
               ORDER BY sequence DESC LIMIT 1""",
                (tenant_id, employee_id),
            ).fetchone()
        latest = recent_states[employee_id]
        if latest and latest["state"] not in ("available", "idle"):
            reasons.add("worker_" + latest["state"])
        mode_cache = state.setdefault("_modes", {})
        for kind, identifier in (
            ("company", None),
            ("department", department),
            ("employee", employee_id),
        ):
            key = (kind, identifier)
            if key not in mode_cache:
                mode_cache[key] = self.db.execute(
                    """SELECT mode,expires_at FROM ago_oos_mode_events
                    WHERE tenant_id=%s AND scope_kind=%s AND scope_id IS NOT DISTINCT FROM %s::uuid
                    ORDER BY sequence DESC LIMIT 1""",
                    (tenant_id, kind, identifier),
                ).fetchone()
            mode = mode_cache[key]
            if mode and (
                mode["mode"] != "active" or mode["expires_at"] and mode["expires_at"] <= at
            ):
                reasons.add("organizational_mode_restricted")
        terminated = state.setdefault("_terminated", {})
        if employee_id not in terminated:
            terminated[employee_id] = (
                self.db.execute(
                    """SELECT 1 FROM ago_personnel_events
                WHERE tenant_id=%s AND employee_id=%s AND change_kind='terminated' LIMIT 1""",
                    (tenant_id, employee_id),
                ).fetchone()
                is not None
            )
        if terminated[employee_id]:
            reasons.add("employee_terminated")
        recent_tasks = state.setdefault("_recent", {})
        if employee_id not in recent_tasks:
            recent_tasks[employee_id] = self.db.execute(
                """SELECT updated_at,status FROM ago_governed_tasks WHERE tenant_id=%s AND assignee_id=%s
               AND status IN ('running','completed','failed') ORDER BY updated_at DESC LIMIT 1""",
                (tenant_id, employee_id),
            ).fetchone()
        recent = recent_tasks[employee_id]
        if worker["kind"] == "ai" and recent:
            for policy in policies:
                if (
                    policy["rest_minutes"]
                    and recent["status"] != "running"
                    and recent["updated_at"] + timedelta(minutes=policy["rest_minutes"]) > at
                ):
                    reasons.add("rest_interval")
                if recent["status"] == "running" and recent["updated_at"] + timedelta(
                    minutes=policy["max_continuous_minutes"]
                ) <= at + timedelta(minutes=duration_minutes):
                    reasons.add("continuous_work_limit")
        if task_id:
            tasks = state.setdefault("_tasks", {})
            if task_id not in tasks:
                tasks[task_id] = self.db.execute(
                    "SELECT assignee_id,status FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s",
                    (tenant_id, str(UUID(task_id))),
                ).fetchone()
            task = tasks[task_id]
            if task is None or str(task["assignee_id"]) != employee_id:
                raise PermissionError("Task must be assigned to this organization employee")
            if task["status"] not in ("proposed", "waiting_approval"):
                reasons.add("task_not_pending")
            linked = [x for x in state["links"] if x.get("task_id") == task_id]
            deadline_cache = state.setdefault("_deadlines", {})
            if task_id not in deadline_cache:
                deadline_cache[task_id] = self.db.execute(
                    """SELECT starts_at,ends_at FROM ago_calendar_events WHERE tenant_id=%s AND task_id=%s
                   AND visibility='tenant' AND status='scheduled' ORDER BY ends_at LIMIT 101""",
                    (tenant_id, task_id),
                ).fetchall()
            deadlines = deadline_cache[task_id]
            linked_cache = state.setdefault("_linked_deadlines", {})
            if task_id not in linked_cache:
                linked_cache[task_id] = []
                for link in linked:
                    row = self.db.execute(
                        """SELECT starts_at,ends_at FROM ago_calendar_events WHERE tenant_id=%s AND id=%s
                       AND visibility='tenant' AND status='scheduled'""",
                        (tenant_id, link["event_id"]),
                    ).fetchone()
                    if row:
                        linked_cache[task_id].append(row)
            deadlines = deadlines + linked_cache[task_id]
            if len(deadlines) > 100:
                reasons.add("task_calendar_truncated")
            for event in deadlines:
                if at < event["starts_at"]:
                    reasons.add("before_task_window")
                if at + timedelta(minutes=duration_minutes) > event["ends_at"]:
                    reasons.add("deadline_window_missed")
        from ago.enterprise_domains import calendar_minutes
        from zoneinfo import ZoneInfo

        support = []
        emergency = []
        for policy in policies:
            if policy["support_start"] is not None:
                local = at.astimezone(ZoneInfo(policy["timezone"]))
                minute = local.hour * 60 + local.minute
                support.append(
                    calendar_minutes(policy["support_start"])
                    <= minute
                    < calendar_minutes(policy["support_end"], end=True)
                    and not calendar_policy_reasons(policy, at, duration_minutes)
                )
            if policy["emergency_reviewer_ids"]:
                emergency.append(
                    any(
                        self._human_available(tenant_id, x, at, state, duration_minutes)
                        for x in policy["emergency_reviewer_ids"]
                    )
                )
        return {
            "eligible": not reasons,
            "reasons": sorted(reasons),
            "at": at,
            "duration_minutes": duration_minutes,
            "calendar_revision": state["revision"],
            "policy_count": len(policies),
            "support_coverage_available": all(support) if support else None,
            "emergency_review_available": all(emergency) if emergency else None,
            "configured": state["configured"],
            "authority_changed": False,
            "approval_still_required": True,
        }

    def eligibility(
        self,
        *,
        actor: Principal,
        employee_id: str,
        at: datetime,
        duration_minutes: int = 1,
        task_id: str | None = None,
        search_days: int = 14,
    ) -> dict:
        from ago.enterprise_domains import calendar_instant

        if type(search_days) is not int or not 0 <= search_days <= 14:
            raise ValueError("Eligibility search is bounded to 14 days")
        state = self._state(actor.tenant_id)
        start = calendar_instant(at)
        result = self._eligibility(
            actor.tenant_id, employee_id, start, duration_minutes, state, task_id
        )
        next_at, attempts = (start if result["eligible"] else None), 0
        # Exact boundary candidates plus minute grid: conservative minute-resolution planning.
        candidates = {start + timedelta(minutes=i) for i in range(1, search_days * 1440 + 1)}
        candidates.update(
            calendar_instant(s[k])
            for w in state["windows"]
            for s in w["slots"]
            for k in ("starts_at", "ends_at")
            if start < calendar_instant(s[k]) <= start + timedelta(days=search_days)
        )
        for candidate in sorted(candidates) if next_at is None else []:
            attempts += 1
            if attempts > 20160:
                break
            if self._eligibility(
                actor.tenant_id, employee_id, candidate, duration_minutes, state, task_id
            )["eligible"]:
                next_at = candidate
                break
        return {
            **result,
            "next_eligible_at": next_at,
            "search_days": search_days,
            "search_resolution_seconds": 60,
            "search_attempts": min(attempts, 20160),
            "search_complete": next_at is not None or attempts <= 20160,
            "search_status": "found"
            if next_at is not None
            else "truncated"
            if attempts > 20160
            else "not_found",
            "retrospective_execution": False,
        }

    def require_execution(self, *, actor: Principal, task_id: str) -> None:
        task = self.db.execute(
            "SELECT assignee_id FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s",
            (actor.tenant_id, str(UUID(task_id))),
        ).fetchone()
        if task is None:
            raise PermissionError("Task not found in organization")
        now = self.db.execute("SELECT clock_timestamp() AS at").fetchone()["at"]
        result = self._eligibility(
            actor.tenant_id, str(task["assignee_id"]), now, 1, self._state(actor.tenant_id), task_id
        )
        if not result["eligible"]:
            self._timing(
                actor.tenant_id,
                "denied:" + str(uuid4()),
                "execution_denied",
                {"task_id": task_id, "actor_id": actor.subject, **result},
            )
            raise PermissionError("Calendar blocks execution: " + ", ".join(result["reasons"]))

    def record_execution(self, *, tenant_id: str, task_id: str, status: str) -> None:
        if status not in ("started", "completed", "failed"):
            raise ValueError("Unknown execution timing status")
        self._timing(
            tenant_id,
            "task:" + task_id + ":" + status,
            "execution_" + status,
            {"task_id": task_id, "status": status, "actual_clock": True},
        )

    def tick(self, *, actor: Principal) -> dict:
        signals = []
        from ago.enterprise_domains import calendar_instant

        with self.db.transaction():
            self._lock(actor.tenant_id)
            state = self._state(actor.tenant_id)
            now = self.db.execute("SELECT clock_timestamp() AS at").fetchone()["at"]
            for window in state["windows"]:
                for slot in window["slots"]:
                    for boundary, key in (("opened", "starts_at"), ("closed", "ends_at")):
                        if calendar_instant(slot[key]) <= now:
                            operation_key = (
                                "cycle:" + window["id"] + ":" + slot["starts_at"] + ":" + boundary
                            )
                            detail = {
                                "window_id": window["id"],
                                "kind": window["kind"],
                                "owner": window["owner"],
                                "boundary": boundary,
                                "due_at": slot[key],
                                "observed_at": now,
                                "scope_kind": window["scope_kind"],
                                "scope_id": window["scope_id"],
                                "review_required": True,
                                "automatic_business_action": False,
                            }
                            self._timing(
                                actor.tenant_id, operation_key, "cycle_" + boundary, detail
                            )
                            signals.append(detail)
            return {
                "observations": signals,
                "observed_at": now,
                "authority_changed": False,
                "notifications_external": False,
                "actions_executed": False,
            }

    def temporal_snapshot(self, *, tenant_id: str) -> dict:
        state = self._state(tenant_id)
        return {
            key: state[key]
            for key in (
                "revision",
                "policies",
                "windows",
                "links",
                "configured",
                "authority_changed",
            )
        }

    def _check_commitment(
        self,
        actor: Principal,
        starts_at: datetime,
        ends_at: datetime,
        employee_ids: list[str],
        *,
        exclude_ids: list[str] | None = None,
    ) -> None:
        from ago.enterprise_domains import calendar_instant, calendar_policy_reasons

        state = self._state(actor.tenant_id)
        participants = list(dict.fromkeys([actor.subject] + employee_ids))
        if self.db.execute(
            """SELECT 1 FROM ago_calendar_events e WHERE e.tenant_id=%s AND e.status='scheduled'
               AND e.starts_at<%s AND e.ends_at>%s AND NOT(e.id=ANY(%s::uuid[]))
               AND (e.creator_id=ANY(%s::uuid[]) OR EXISTS(SELECT 1 FROM ago_calendar_attendees a
                  WHERE a.tenant_id=e.tenant_id AND a.event_id=e.id AND a.response<>'declined'
                    AND a.employee_id=ANY(%s::uuid[]))) LIMIT 1""",
            (actor.tenant_id, ends_at, starts_at, exclude_ids or [], participants, participants),
        ).fetchone():
            raise PermissionError("A participant has another commitment in this time window")
        for identifier in participants:
            worker = self.db.execute(
                "SELECT department_id FROM ago_employees WHERE tenant_id=%s AND id=%s",
                (actor.tenant_id, identifier),
            ).fetchone()
            if worker is None:
                raise PermissionError("Invited employee must belong to this organization")
            policies = self._applicable(state["policies"], identifier, str(worker["department_id"]))
            cursor, end = calendar_instant(starts_at), calendar_instant(ends_at)
            while cursor < end and policies:
                minutes = min(1440, max(1, int((end - cursor).total_seconds() + 59) // 60))
                if any(calendar_policy_reasons(p, cursor, minutes) for p in policies):
                    raise PermissionError(
                        "Commitment conflicts with reviewed availability or quiet hours"
                    )
                cursor += timedelta(minutes=minutes)
