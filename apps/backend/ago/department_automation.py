"""M8 department automation materializes governed tasks, never executes them."""
from __future__ import annotations

from uuid import UUID, uuid4

from ago.governance import ApprovalRepository
from ago.security import Principal
from ago.task_store import TaskStore
from ago.tool_catalog import require_tool_code
from ago.tool_enrollment import ToolEnrollment

TRIGGERS = frozenset(("qa_pass", "knowledge_verified"))


class DepartmentAutomation:
    def __init__(self, db):
        self.db = db

    def create(
        self, *, actor: Principal, department_id: str, assignee_id: str,
        code: str, trigger: str,
    ) -> str:
        for identity in (actor.tenant_id, actor.subject,
                         department_id, assignee_id):
            UUID(identity)
        require_tool_code(code)
        if trigger not in TRIGGERS:
            raise ValueError("Unregistered automation trigger")
        with self.db.transaction():
            ToolEnrollment(self.db).require_active(
                tenant_id=actor.tenant_id, code=code,
            )
            employee = self.db.execute(
                """SELECT kind,department_id FROM ago_employees
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, assignee_id),
            ).fetchone()
            if employee is None or employee["kind"] != "ai" or str(
                employee["department_id"]
            ) != department_id:
                raise PermissionError("Automation needs an AI assignee in its department")
            rule_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_automation_rules
                   (id,tenant_id,creator_id,department_id,assignee_id,
                    tool_code,trigger_kind)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (rule_id, actor.tenant_id, actor.subject,
                 department_id, assignee_id, code, trigger),
            )
        return rule_id

    def disable(self, *, tenant_id: str, rule_id: str) -> None:
        UUID(rule_id)
        with self.db.transaction():
            row = self.db.execute(
                """UPDATE ago_automation_rules SET status='disabled',
                   disabled_at=now()
                   WHERE tenant_id=%s AND id=%s AND status='active'
                   RETURNING id""",
                (tenant_id, rule_id),
            ).fetchone()
            if row is None:
                raise PermissionError("Rule not active or not in tenant")

    def _source_exists(
        self, *, tenant_id: str, trigger: str, source_id: str,
    ) -> bool:
        if trigger == "qa_pass":
            # Never recursively trigger on work materialized by an automation.
            automation_output = self.db.execute(
                """SELECT 1 FROM ago_automation_firings
                   WHERE tenant_id=%s AND task_id=%s""",
                (tenant_id, source_id),
            ).fetchone()
            if automation_output is not None:
                return False
            result = self.db.execute(
                """SELECT 1 FROM ago_governed_tasks t
                   JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id
                     AND q.task_id=t.id
                   WHERE t.tenant_id=%s AND t.id=%s
                     AND t.status='completed' AND q.verdict='pass'""",
                (tenant_id, source_id),
            ).fetchone()
        elif trigger == "knowledge_verified":
            result = self.db.execute(
                """SELECT 1 FROM ago_knowledge_nodes
                   WHERE tenant_id=%s AND id=%s AND status='verified'""",
                (tenant_id, source_id),
            ).fetchone()
        else:
            raise ValueError("Unsupported event trigger")
        return result is not None

    def fire(
        self, *, tenant_id: str, rule_id: str, source_id: str,
    ) -> dict:
        UUID(tenant_id)
        UUID(rule_id)
        UUID(source_id)
        with self.db.transaction():
            rule = self.db.execute(
                """SELECT creator_id,assignee_id,trigger_kind,tool_code,status
                   FROM ago_automation_rules
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (tenant_id, rule_id),
            ).fetchone()
            if rule is None:
                raise LookupError("Automation rule not found")
            if rule["status"] != "active":
                raise PermissionError("Automation rule is disabled")
            ToolEnrollment(self.db).require_active(
                tenant_id=tenant_id, code=rule["tool_code"],
            )
            existing = self.db.execute(
                """SELECT task_id,approval_id,id FROM ago_automation_firings
                   WHERE tenant_id=%s AND rule_id=%s AND source_id=%s""",
                (tenant_id, rule_id, source_id),
            ).fetchone()
            if existing:
                return {
                    "id": str(existing["id"]), "task_id": str(existing["task_id"]),
                    "approval_id": str(existing["approval_id"]), "created": False,
                }
            if not self._source_exists(
                tenant_id=tenant_id, trigger=rule["trigger_kind"],
                source_id=source_id,
            ):
                raise PermissionError("Verified same-tenant source event required")
            task = TaskStore(self.db).propose(
                tenant_id=tenant_id, action=rule["tool_code"],
                assignee_id=str(rule["assignee_id"]),
            )
            approval = ApprovalRepository(self.db).propose(
                tenant_id=tenant_id, action=rule["tool_code"],
                requester_id=str(rule["creator_id"]),
            )
            TaskStore(self.db).request_approval(
                task_id=task.id, tenant_id=tenant_id,
                approval_id=approval.request_id,
            )
            firing_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_automation_firings
                   (id,tenant_id,rule_id,source_id,task_id,approval_id)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (firing_id, tenant_id, rule_id, source_id, task.id,
                 approval.request_id),
            )
        return {
            "id": firing_id, "task_id": task.id,
            "approval_id": approval.request_id, "created": True,
            "execution_permitted": False,
        }

    def scan(self, *, tenant_id: str, limit: int = 25) -> list[dict]:
        """Operator/scheduler invokes explicitly; never dispatches tool runs."""
        if not 1 <= limit <= 100:
            raise ValueError("Automation scan limit must be 1–100")
        rules = self.db.execute(
            """SELECT r.id,r.trigger_kind FROM ago_automation_rules r
               JOIN ago_tool_enrollments e ON e.tenant_id=r.tenant_id
                 AND e.tool_code=r.tool_code AND e.status='active'
               WHERE r.tenant_id=%s AND r.status='active'
               ORDER BY r.created_at,r.id LIMIT 100""",
            (tenant_id,),
        ).fetchall()
        fired = []
        for rule in rules:
            if len(fired) >= limit:
                break
            if rule["trigger_kind"] == "qa_pass":
                sources = self.db.execute(
                    """SELECT DISTINCT t.id AS source_id FROM ago_governed_tasks t
                       JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id
                         AND q.task_id=t.id
                       WHERE t.tenant_id=%s AND t.status='completed'
                         AND q.verdict='pass'
                         AND NOT EXISTS (
                           SELECT 1 FROM ago_automation_firings f
                           WHERE f.tenant_id=t.tenant_id AND
                             (f.task_id=t.id OR
                              (f.rule_id=%s AND f.source_id=t.id)))
                       ORDER BY source_id LIMIT %s""",
                    (tenant_id, rule["id"], limit - len(fired)),
                ).fetchall()
            else:
                sources = self.db.execute(
                    """SELECT k.id AS source_id FROM ago_knowledge_nodes k
                       WHERE k.tenant_id=%s AND k.status='verified'
                         AND NOT EXISTS (
                           SELECT 1 FROM ago_automation_firings f
                           WHERE f.tenant_id=k.tenant_id AND f.rule_id=%s
                             AND f.source_id=k.id)
                       ORDER BY k.id LIMIT %s""",
                    (tenant_id, rule["id"], limit - len(fired)),
                ).fetchall()
            for source in sources:
                item = self.fire(
                    tenant_id=tenant_id, rule_id=str(rule["id"]),
                    source_id=str(source["source_id"]),
                )
                if item["created"]:
                    fired.append(item)
        return fired

    def list_rules(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            """SELECT id,department_id,assignee_id,creator_id,tool_code,
                      trigger_kind,status,created_at
               FROM ago_automation_rules WHERE tenant_id=%s
               ORDER BY created_at,id LIMIT 200""",
            (tenant_id,),
        ).fetchall()]

    def list_firings(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            """SELECT id,rule_id,source_id,task_id,approval_id,created_at
               FROM ago_automation_firings WHERE tenant_id=%s
               ORDER BY created_at,id LIMIT 200""",
            (tenant_id,),
        ).fetchall()]
