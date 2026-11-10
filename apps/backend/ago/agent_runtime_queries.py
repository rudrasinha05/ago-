"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class AgentRuntimeQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_ago_governed_tasks_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT action,assignee_id FROM ago_governed_tasks\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def select_ago_employees_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT kind FROM ago_employees\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def insert_ago_agent_runs_03(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_agent_runs\n                   (id,tenant_id,task_id,agent_id,executor_id,status,dna_context)\n                   VALUES (%s,%s,%s,%s,%s,'running',%s::jsonb)",
            parameters,
        )

    def select_ago_agent_runs_04(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,task_id,agent_id,status,result,failure_code,started_at,dna_context\n               FROM ago_agent_runs WHERE tenant_id=%s\n               ORDER BY started_at DESC,id LIMIT %s",
            parameters,
        )

    def update_ago_agent_runs_05(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_agent_runs SET status='completed',result=%s::jsonb,\n                       finished_at=now() WHERE tenant_id=%s AND id=%s\n                       AND status='running'",
            parameters,
        )

    def insert_ago_agent_messages_06(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_agent_messages\n                       (id,tenant_id,run_id,kind,content)\n                       VALUES (%s,%s,%s,'evidence',%s)",
            parameters,
        )

    def update_ago_agent_runs_07(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_agent_runs SET status='failed',\n                       failure_code=%s,finished_at=now()\n                       WHERE tenant_id=%s AND id=%s AND status='running'",
            parameters,
        )

    def select_ago_agent_runs_08(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT r.id,r.task_id FROM ago_agent_runs r\n                   WHERE r.tenant_id=%s AND r.status='running'\n                     AND r.started_at < now() - (%s * interval '1 second')\n                   ORDER BY r.started_at,r.id FOR UPDATE SKIP LOCKED LIMIT 100",
            parameters,
        )

    def update_ago_agent_runs_09(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_agent_runs\n                       SET status='failed',failure_code='worker_timeout',finished_at=now()\n                       WHERE id=%s AND tenant_id=%s AND status='running'",
            parameters,
        )

    def update_ago_governed_tasks_10(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_governed_tasks\n                       SET status='failed',updated_at=now()\n                       WHERE id=%s AND tenant_id=%s AND status='running'",
            parameters,
        )

    def insert_ago_agent_messages_11(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_agent_messages\n                       (id,tenant_id,run_id,kind,content)\n                       VALUES (%s,%s,%s,'evidence',%s)",
            parameters,
        )

    def select_passed_stage_work_13(self, parameters: Any = None) -> Cursor:
        """(tenant_id, intake_id, stage): recorded results of the EARLIER stages of
        this project that completed and passed independent QA, in delivery order."""
        return self.connection.execute("""
            SELECT s.stage,r.result
            FROM ago_founder_intake_stages s
            JOIN ago_founder_intake_stages cur ON cur.tenant_id=s.tenant_id
              AND cur.intake_id=s.intake_id AND cur.stage=%s AND s.position<cur.position
            JOIN ago_plan_steps ps ON ps.tenant_id=s.tenant_id AND ps.plan_id=s.plan_id
              AND ps.id=s.plan_step_id
            JOIN ago_governed_tasks t ON t.tenant_id=ps.tenant_id AND t.id=ps.task_id
              AND t.status='completed'
            JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id AND q.task_id=t.id
              AND q.verdict='pass'
            JOIN ago_agent_runs r ON r.tenant_id=t.tenant_id AND r.task_id=t.id
              AND r.status='completed'
            WHERE s.tenant_id=%s AND s.intake_id=%s
            ORDER BY s.position
        """, parameters)

    def select_ago_founder_project_12(self, parameters: Any = None, *, lock: bool = False) -> Cursor:
        """Lock project ownership through admission, including newly materialized tasks."""
        return self.connection.execute("""
            SELECT i.id,i.title,i.brief,i.founder_id,s.stage,s.deliverable
            FROM ago_founder_intakes i
            JOIN ago_founder_intake_stages s
              ON s.tenant_id=i.tenant_id AND s.intake_id=i.id
            JOIN ago_plan_steps ps
              ON ps.tenant_id=i.tenant_id AND ps.plan_id=i.plan_id
             AND ps.id=s.plan_step_id
            WHERE ps.task_id=%s AND i.tenant_id=%s LIMIT 1
        """ + (" FOR SHARE OF i" if lock else ""), parameters)
