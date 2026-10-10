"""M8 department automation materializes governed tasks, never executes them."""

from __future__ import annotations

from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.department_automation_queries import DepartmentAutomationQueries
from ago.governance import ApprovalRepository
from ago.security import Principal
from ago.task_store import TaskStore
from ago.tool_catalog import require_tool_code
from ago.tool_enrollment import ToolEnrollment

TRIGGERS = frozenset(("qa_pass", "knowledge_verified"))


class DepartmentAutomation:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def create(
        self,
        *,
        actor: Principal,
        department_id: str,
        assignee_id: str,
        code: str,
        trigger: str,
    ) -> str:
        for identity in (actor.tenant_id, actor.subject, department_id, assignee_id):
            UUID(identity)
        require_tool_code(code)
        if trigger not in TRIGGERS:
            raise ValueError("Unregistered automation trigger")
        with self.db.transaction():
            self.repositories.resolve(ToolEnrollment).require_active(
                tenant_id=actor.tenant_id,
                code=code,
            )
            employee = (
                self.repositories.resolve(DepartmentAutomationQueries)
                .select_ago_employees_01((actor.tenant_id, assignee_id))
                .fetchone()
            )
            if (
                employee is None
                or employee["kind"] != "ai"
                or str(employee["department_id"]) != department_id
            ):
                raise PermissionError("Automation needs an AI assignee in its department")
            rule_id = str(uuid4())
            self.repositories.resolve(DepartmentAutomationQueries).insert_ago_automation_rules_02(
                (rule_id, actor.tenant_id, actor.subject, department_id, assignee_id, code, trigger)
            )
        return rule_id

    def disable(self, *, tenant_id: str, rule_id: str) -> None:
        UUID(rule_id)
        with self.db.transaction():
            row = (
                self.repositories.resolve(DepartmentAutomationQueries)
                .update_ago_automation_rules_03((tenant_id, rule_id))
                .fetchone()
            )
            if row is None:
                raise PermissionError("Rule not active or not in tenant")

    def _source_exists(
        self,
        *,
        tenant_id: str,
        trigger: str,
        source_id: str,
    ) -> bool:
        if trigger == "qa_pass":
            # Never recursively trigger on work materialized by an automation.
            automation_output = (
                self.repositories.resolve(DepartmentAutomationQueries)
                .select_ago_automation_firings_04((tenant_id, source_id))
                .fetchone()
            )
            if automation_output is not None:
                return False
            result = (
                self.repositories.resolve(DepartmentAutomationQueries)
                .select_ago_governed_tasks_05((tenant_id, source_id))
                .fetchone()
            )
        elif trigger == "knowledge_verified":
            result = (
                self.repositories.resolve(DepartmentAutomationQueries)
                .select_ago_knowledge_nodes_06((tenant_id, source_id))
                .fetchone()
            )
        else:
            raise ValueError("Unsupported event trigger")
        return result is not None

    def fire(
        self,
        *,
        tenant_id: str,
        rule_id: str,
        source_id: str,
    ) -> dict:
        UUID(tenant_id)
        UUID(rule_id)
        UUID(source_id)
        with self.db.transaction():
            rule = (
                self.repositories.resolve(DepartmentAutomationQueries)
                .select_ago_automation_rules_07((tenant_id, rule_id))
                .fetchone()
            )
            if rule is None:
                raise LookupError("Automation rule not found")
            if rule["status"] != "active":
                raise PermissionError("Automation rule is disabled")
            self.repositories.resolve(ToolEnrollment).require_active(
                tenant_id=tenant_id,
                code=rule["tool_code"],
            )
            existing = (
                self.repositories.resolve(DepartmentAutomationQueries)
                .select_ago_automation_firings_08((tenant_id, rule_id, source_id))
                .fetchone()
            )
            if existing:
                return {
                    "id": str(existing["id"]),
                    "task_id": str(existing["task_id"]),
                    "approval_id": str(existing["approval_id"]),
                    "created": False,
                }
            if not self._source_exists(
                tenant_id=tenant_id,
                trigger=rule["trigger_kind"],
                source_id=source_id,
            ):
                raise PermissionError("Verified same-tenant source event required")
            task = self.repositories.resolve(TaskStore).propose(
                tenant_id=tenant_id,
                action=rule["tool_code"],
                assignee_id=str(rule["assignee_id"]),
            )
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=tenant_id,
                action=rule["tool_code"],
                requester_id=str(rule["creator_id"]),
            )
            self.repositories.resolve(TaskStore).request_approval(
                task_id=task.id,
                tenant_id=tenant_id,
                approval_id=approval.request_id,
            )
            firing_id = str(uuid4())
            self.repositories.resolve(DepartmentAutomationQueries).insert_ago_automation_firings_09(
                (firing_id, tenant_id, rule_id, source_id, task.id, approval.request_id)
            )
        return {
            "id": firing_id,
            "task_id": task.id,
            "approval_id": approval.request_id,
            "created": True,
            "execution_permitted": False,
        }

    def scan(self, *, tenant_id: str, limit: int = 25) -> list[dict]:
        """Operator/scheduler invokes explicitly; never dispatches tool runs."""
        if not 1 <= limit <= 100:
            raise ValueError("Automation scan limit must be 1–100")
        rules = (
            self.repositories.resolve(DepartmentAutomationQueries)
            .select_ago_automation_rules_10((tenant_id,))
            .fetchall()
        )
        fired = []
        for rule in rules:
            if len(fired) >= limit:
                break
            if rule["trigger_kind"] == "qa_pass":
                sources = (
                    self.repositories.resolve(DepartmentAutomationQueries)
                    .select_ago_governed_tasks_11((tenant_id, rule["id"], limit - len(fired)))
                    .fetchall()
                )
            else:
                sources = (
                    self.repositories.resolve(DepartmentAutomationQueries)
                    .select_ago_knowledge_nodes_12((tenant_id, rule["id"], limit - len(fired)))
                    .fetchall()
                )
            for source in sources:
                item = self.fire(
                    tenant_id=tenant_id,
                    rule_id=str(rule["id"]),
                    source_id=str(source["source_id"]),
                )
                if item["created"]:
                    fired.append(item)
        return fired

    def list_rules(self, *, tenant_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.repositories.resolve(DepartmentAutomationQueries)
            .select_ago_automation_rules_13((tenant_id,))
            .fetchall()
        ]

    def list_firings(self, *, tenant_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.repositories.resolve(DepartmentAutomationQueries)
            .select_ago_automation_firings_14((tenant_id,))
            .fetchall()
        ]
