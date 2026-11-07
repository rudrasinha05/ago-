"""Context-owned AI QA persistence queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class AiQaReviewQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_stage_task_01(self, parameters: Any = None) -> Cursor:
        """(stage, tenant_id, project_id, founder_id): the stage's linked task,
        its single agent run and whether any QA review exists; locks the task."""
        return self.connection.execute(
            """SELECT i.title AS project_title,i.brief AS project_brief,
                      s.deliverable,p.status AS plan_status,
                      t.id AS task_id,t.status AS task_status,t.assignee_id,
                      r.status AS run_status,r.agent_id AS run_agent_id,r.result AS run_result,
                      EXISTS (SELECT 1 FROM ago_task_reviews q
                              WHERE q.tenant_id=t.tenant_id AND q.task_id=t.id)
                        AS already_reviewed
               FROM ago_founder_intakes i
               JOIN ago_founder_intake_stages s ON s.tenant_id=i.tenant_id
                AND s.intake_id=i.id AND s.stage=%s
               JOIN ago_plan_steps ps ON ps.tenant_id=s.tenant_id
                AND ps.plan_id=s.plan_id AND ps.id=s.plan_step_id
               JOIN ago_strategy_plans p ON p.tenant_id=ps.tenant_id AND p.id=ps.plan_id
               JOIN ago_governed_tasks t ON t.tenant_id=ps.tenant_id AND t.id=ps.task_id
               LEFT JOIN ago_agent_runs r ON r.tenant_id=t.tenant_id AND r.task_id=t.id
               WHERE i.tenant_id=%s AND i.id=%s AND i.founder_id=%s
               FOR UPDATE OF t""",
            parameters,
        )

    def select_qa_employee_02(self, parameters: Any = None) -> Cursor:
        """(tenant_id, employee_id): identity, kind, role and termination state."""
        return self.connection.execute(
            """SELECT e.id,e.name,e.kind,e.role_title,
                      EXISTS (SELECT 1 FROM ago_personnel_events pe
                              WHERE pe.tenant_id=e.tenant_id AND pe.employee_id=e.id
                                AND pe.change_kind='terminated') AS terminated
               FROM ago_employees e WHERE e.tenant_id=%s AND e.id=%s""",
            parameters,
        )

    def insert_ai_qa_review_03(self, parameters: Any = None) -> Cursor:
        """Append one immutable AI QA receipt."""
        return self.connection.execute(
            """INSERT INTO ago_ai_qa_reviews
               (id,tenant_id,task_id,qa_employee_id,author_id,requested_by,model,
                provider_mode,prompt_sha256,response_sha256,response_text,verdict,
                credit_usage_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'ollama_local',%s,%s,%s,%s,%s)
               RETURNING created_at""",
            parameters,
        )
