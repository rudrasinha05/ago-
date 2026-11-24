"""Company Brain skill persistence (SKL-002/003/005); caller owns the transaction."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope

ROLE_NAMES = ("ceo", "cto", "finance", "risk", "quality", "pm", "employee", "qa", "chat")


class BrainSkillStore:
    def __init__(self, connection: DatabaseConnection, *,
                 repositories: RepositoryScope | None = None):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    # -- reading -----------------------------------------------------------
    def approved(self, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.connection.execute(
            """SELECT id,slug,title,domain,roles,stages,keywords,body,source,created_at
               FROM ago_brain_skills WHERE tenant_id=%s AND status='approved'
               ORDER BY created_at""", (tenant_id,)).fetchall()]

    def decisions(self, tenant_id: str, limit: int = 100) -> list[dict]:
        """Every AI-drafted skill with the AI CEO's decision, newest first."""
        return [dict(r) for r in self.connection.execute(
            """SELECT s.id,s.slug,s.title,s.domain,s.topic,s.status,s.review_text,s.body,
                      s.draft_model,s.review_model,s.created_at,
                      d.name AS drafted_by_name,v.name AS reviewed_by_name
               FROM ago_brain_skills s
               JOIN ago_employees d ON d.tenant_id=s.tenant_id AND d.id=s.drafted_by
               JOIN ago_employees v ON v.tenant_id=s.tenant_id AND v.id=s.reviewed_by
               WHERE s.tenant_id=%s ORDER BY s.created_at DESC LIMIT %s""",
            (tenant_id, limit)).fetchall()]

    def retired(self, tenant_id: str) -> frozenset[str]:
        return frozenset(r["skill_ref"] for r in self.connection.execute(
            "SELECT skill_ref FROM ago_brain_skill_retired WHERE tenant_id=%s",
            (tenant_id,)).fetchall())

    def usage(self, tenant_id: str) -> dict[str, dict]:
        """Per skill: tasks it went into, and how many of those passed/failed QA."""
        rows = self.connection.execute(
            """SELECT u.skill_ref,
                      count(DISTINCT u.task_id) AS uses,
                      count(DISTINCT u.task_id) FILTER (WHERE q.verdict='pass') AS passed,
                      count(DISTINCT u.task_id) FILTER (WHERE q.verdict='fail') AS failed
               FROM ago_brain_skill_uses u
               LEFT JOIN ago_task_reviews q ON q.tenant_id=u.tenant_id AND q.task_id=u.task_id
               WHERE u.tenant_id=%s GROUP BY u.skill_ref""", (tenant_id,)).fetchall()
        return {r["skill_ref"]: {"uses": r["uses"], "passed": r["passed"], "failed": r["failed"]}
                for r in rows}

    def open_gaps(self, tenant_id: str, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.connection.execute(
            """SELECT g.id,g.task_id,g.role,g.stage,g.topic,g.created_at,t.action
               FROM ago_brain_skill_gaps g
               JOIN ago_governed_tasks t ON t.tenant_id=g.tenant_id AND t.id=g.task_id
               WHERE g.tenant_id=%s AND g.resolved_skill_id IS NULL
               ORDER BY g.created_at DESC LIMIT %s""", (tenant_id, limit)).fetchall()]

    def gap(self, tenant_id: str, gap_id: str) -> dict | None:
        row = self.connection.execute(
            """SELECT id,topic,role,stage,resolved_skill_id FROM ago_brain_skill_gaps
               WHERE tenant_id=%s AND id=%s FOR UPDATE""", (tenant_id, gap_id)).fetchone()
        return dict(row) if row else None

    def board_seat(self, tenant_id: str, seat: str) -> dict | None:
        """The appointed, active AI employee on a Board seat."""
        row = self.connection.execute(
            """SELECT e.id,e.name FROM ago_company_board_appointments b
               JOIN ago_employees e ON e.tenant_id=b.tenant_id AND e.id=b.employee_id
               WHERE b.tenant_id=%s AND b.seat=%s AND e.kind='ai'""", (tenant_id, seat)).fetchone()
        return dict(row) if row else None

    def slug_taken(self, tenant_id: str, slug: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM ago_brain_skills WHERE tenant_id=%s AND slug=%s AND status='approved'",
            (tenant_id, slug)).fetchone() is not None

    # -- writing -----------------------------------------------------------
    def record_uses(self, tenant_id: str, task_id: str, refs: list[str], role: str,
                    stage: str | None) -> None:
        if role not in ROLE_NAMES:
            return
        for ref in refs:
            self.connection.execute(
                """INSERT INTO ago_brain_skill_uses(tenant_id,task_id,skill_ref,role,stage)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (tenant_id, task_id, ref, role, stage))

    def record_gap(self, tenant_id: str, task_id: str, role: str, stage: str | None,
                   topic: str) -> None:
        topic = " ".join(str(topic).split())[:500]
        if role not in ROLE_NAMES or len(topic) < 3:
            return
        self.connection.execute(
            """INSERT INTO ago_brain_skill_gaps(id,tenant_id,task_id,role,stage,topic)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (str(uuid4()), tenant_id, task_id, role, stage, topic))

    def insert_skill(self, values: dict[str, Any]) -> dict:
        row = self.connection.execute(
            """INSERT INTO ago_brain_skills
                 (id,tenant_id,slug,title,domain,roles,stages,keywords,body,source,topic,
                  status,drafted_by,reviewed_by,draft_model,review_model,review_text,requested_by)
               VALUES (%(id)s,%(tenant_id)s,%(slug)s,%(title)s,%(domain)s,%(roles)s,%(stages)s,
                       %(keywords)s,%(body)s,%(source)s,%(topic)s,%(status)s,%(drafted_by)s,
                       %(reviewed_by)s,%(draft_model)s,%(review_model)s,%(review_text)s,
                       %(requested_by)s)
               RETURNING id,slug,status,created_at""", values).fetchone()
        return dict(row)

    def resolve_gap(self, tenant_id: str, gap_id: str, skill_id: str) -> None:
        self.connection.execute(
            """UPDATE ago_brain_skill_gaps SET resolved_skill_id=%s,resolved_at=clock_timestamp()
               WHERE tenant_id=%s AND id=%s AND resolved_skill_id IS NULL""",
            (skill_id, tenant_id, gap_id))

    def retire(self, tenant_id: str, skill_ref: str, user_id: str) -> None:
        self.connection.execute(
            """INSERT INTO ago_brain_skill_retired(tenant_id,skill_ref,retired_by)
               VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""", (tenant_id, skill_ref, user_id))

    def restore(self, tenant_id: str, skill_ref: str) -> None:
        self.connection.execute(
            "DELETE FROM ago_brain_skill_retired WHERE tenant_id=%s AND skill_ref=%s",
            (tenant_id, skill_ref))
