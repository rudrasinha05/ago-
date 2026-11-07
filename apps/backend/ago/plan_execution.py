"""M3: activate approved strategies and materialize steps into governed tasks.

Materializing never authorizes actions. Every task requires a distinct M2 approval.
"""

from __future__ import annotations

from uuid import UUID

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance import ApprovalRepository
from ago.plan_execution_queries import PlanExecutionQueries
from ago.task_store import TaskStore


class PlanExecution:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def activate(self, *, tenant_id: str, plan_id: str) -> None:
        with self.db.transaction():
            plan = (
                self.repositories.resolve(PlanExecutionQueries)
                .select_ago_strategy_plans_01((tenant_id, plan_id))
                .fetchone()
            )
            if plan is None or plan["status"] != "pending_approval":
                raise PermissionError("Plan must await human approval")
            goal = (
                self.repositories.resolve(PlanExecutionQueries)
                .select_ago_goals_02((tenant_id, plan["goal_id"]))
                .fetchone()
            )
            if goal is None or goal["status"] != "active":
                raise PermissionError("Parent goal must still be active")
            self.repositories.resolve(ApprovalRepository).assert_executable(
                request_id=str(plan["approval_id"]),
                tenant_id=tenant_id,
                action=f"brain:activate:{plan_id}",
            )
            self.repositories.resolve(PlanExecutionQueries).update_ago_strategy_plans_03(
                (tenant_id, plan_id)
            )

    def materialize(self, *, tenant_id: str, plan_id: str) -> list[str]:
        with self.db.transaction():
            plan = (
                self.repositories.resolve(PlanExecutionQueries)
                .select_ago_strategy_plans_04((tenant_id, plan_id))
                .fetchone()
            )
            if plan is None or plan["status"] != "active" or plan["goal_status"] != "active":
                raise PermissionError("Only active approved plans may create tasks")
            rows = (
                self.repositories.resolve(PlanExecutionQueries)
                .select_ago_plan_steps_05((tenant_id, plan_id))
                .fetchall()
            )
            created = []
            for step in rows:
                if step["task_id"]:
                    created.append(str(step["task_id"]))
                    continue
                task = self.repositories.resolve(TaskStore).propose(
                    tenant_id=tenant_id,
                    action=step["action"],
                    assignee_id=str(step["assignee_id"]),
                )
                self.repositories.resolve(PlanExecutionQueries).update_ago_plan_steps_06(
                    (task.id, tenant_id, step["id"])
                )
                created.append(task.id)
        return created

    def recover_failed_stage(
        self, *, tenant_id: str, founder_id: str, project_id: str, stage: str,
        failed_task_id: str, reason: str,
    ) -> dict:
        """Founder-authorized recovery of a FAILED project stage task (issue #10).

        Also the rework path after QA (issue #8): a COMPLETED task whose QA
        verdict is FAIL may be recovered the same way, so the stage gets new
        work and a new QA instead of staying stuck.

        Creates a NEW proposed task with the step's own action and assignee,
        records an append-only recovery row and relinks the step. The failed
        task and its run stay immutable evidence; nothing is approved, replayed
        or run. The new task needs its own approval through the existing flow.
        """
        for value in (tenant_id, founder_id, project_id, failed_task_id):
            UUID(value)
        if stage not in ("discovery", "architecture", "implementation", "quality", "release"):
            raise ValueError("Unknown project stage")
        reason = (reason or "").strip()
        if not 1 <= len(reason) <= 500:
            raise ValueError("A recovery reason of 1-500 characters is required")
        queries = self.repositories.resolve(PlanExecutionQueries)
        with self.db.transaction():
            step = queries.select_founder_stage_step_07(
                (stage, tenant_id, project_id, founder_id)
            ).fetchone()
            if step is None:
                raise LookupError("Project stage not found")
            if step["plan_status"] != "active" or step["goal_status"] != "active":
                raise PermissionError("Only an active approved plan and goal may recover a stage task")
            if str(step["task_id"] or "") != failed_task_id:
                raise ValueError("This stage is no longer linked to that task; refresh first")
            task = queries.select_task_for_recovery_08((tenant_id, failed_task_id)).fetchone()
            if task is None:
                raise LookupError("Task not found")
            if task["already_recovered"]:
                raise ValueError("This failed task was already recovered")
            rework = task["status"] == "completed" and bool(task["qa_failed"])
            if (task["status"] != "failed" and not rework) or task["run_active"]:
                raise ValueError(
                    "Only a failed task, or a finished task that failed QA, can be recovered"
                )
            if (task["action"] != step["action"]
                    or str(task["assignee_id"]) != str(step["assignee_id"])):
                raise ValueError("Failed task does not match this plan step")
            created = self.repositories.resolve(TaskStore).propose(
                tenant_id=tenant_id,
                action=step["action"],
                assignee_id=str(step["assignee_id"]),
            )
            record = queries.insert_step_task_recovery_09((
                tenant_id, str(step["plan_id"]), str(step["plan_step_id"]),
                failed_task_id, created.id, founder_id, reason,
            )).fetchone()
            relinked = queries.relink_step_task_10(
                (created.id, tenant_id, str(step["plan_step_id"]), failed_task_id)
            )
            if relinked.rowcount != 1:
                raise ValueError("Stage changed during recovery; refresh first")
        return {
            "kind": "ago_stage_task_recovery_v1",
            "project_id": project_id,
            "stage": stage,
            "failed_task_id": failed_task_id,
            "recovery_task_id": created.id,
            "recovery_task_status": "proposed",
            "recovery_kind": "qa_rework" if rework else "failed_run",
            "recovery_id": int(record["id"]),
            "recorded_at": record["created_at"].isoformat(),
            "approval_required": True,
            "run_started": False,
        }
