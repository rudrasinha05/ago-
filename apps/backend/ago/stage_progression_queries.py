"""Context-owned stage continuation queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class StageProgressionQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_project_01(self, parameters: Any = None) -> Cursor:
        """(tenant_id, project_id, founder_id): lock the Founder's project and
        read its plan, goal and accountable manager."""
        return self.connection.execute(
            """SELECT i.id,i.title,i.plan_id,p.status AS plan_status,
                      g.status AS goal_status,l.accountable_manager_id,
                      m.name AS manager_name,m.kind AS manager_kind,
                      m.role_title AS manager_role
               FROM ago_founder_intakes i
               JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
               JOIN ago_goals g ON g.tenant_id=p.tenant_id AND g.id=p.goal_id
               JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id
                AND l.intake_id=i.id
               JOIN ago_employees m ON m.tenant_id=l.tenant_id
                AND m.id=l.accountable_manager_id
               WHERE i.tenant_id=%s AND i.id=%s AND i.founder_id=%s
               FOR UPDATE OF i,p""",
            parameters,
        )

    def select_stages_02(self, parameters: Any = None) -> Cursor:
        """(tenant_id, project_id): every stage with its step, task, QA verdict,
        latest run and approved specialist, in delivery order."""
        return self.connection.execute(
            """SELECT s.position,s.stage,s.deliverable,s.plan_step_id,
                      a.assignee_id AS approved_assignee_id,
                      w.name AS approved_assignee_name,
                      ps.task_id,t.status AS task_status,
                      q.verdict AS qa_verdict,
                      r.status AS run_status,r.failure_code,r.result AS run_result,
                      (SELECT count(*) FROM ago_plan_step_task_recoveries v
                       WHERE v.tenant_id=s.tenant_id AND v.plan_step_id=s.plan_step_id
                         AND v.decided_by_employee_id IS NOT NULL) AS ai_recoveries
               FROM ago_founder_intake_stages s
               LEFT JOIN ago_project_stage_delegation_activations a
                 ON a.tenant_id=s.tenant_id AND a.intake_id=s.intake_id AND a.stage=s.stage
               LEFT JOIN ago_employees w ON w.tenant_id=a.tenant_id AND w.id=a.assignee_id
               LEFT JOIN ago_plan_steps ps ON ps.tenant_id=s.tenant_id
                 AND ps.plan_id=s.plan_id AND ps.id=s.plan_step_id
               LEFT JOIN ago_governed_tasks t ON t.tenant_id=ps.tenant_id AND t.id=ps.task_id
               LEFT JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id AND q.task_id=t.id
               LEFT JOIN ago_agent_runs r ON r.tenant_id=t.tenant_id AND r.task_id=t.id
               WHERE s.tenant_id=%s AND s.intake_id=%s
               ORDER BY s.position""",
            parameters,
        )

    def insert_stage_step_03(self, parameters: Any = None) -> Cursor:
        """(id, tenant_id, plan_id, position, assignee_id, depends_on); the
        database guard re-checks QA PASS, position and the approved specialist."""
        return self.connection.execute(
            """INSERT INTO ago_plan_steps
               (id,tenant_id,plan_id,position,action,assignee_id,depends_on)
               VALUES (%s,%s,%s,%s,'internal:brief',%s,%s)""",
            parameters,
        )

    def link_step_task_04(self, parameters: Any = None) -> Cursor:
        """(task_id, tenant_id, plan_step_id)"""
        return self.connection.execute(
            """UPDATE ago_plan_steps SET task_id=%s
               WHERE tenant_id=%s AND id=%s AND task_id IS NULL""",
            parameters,
        )

    def link_stage_step_05(self, parameters: Any = None) -> Cursor:
        """(plan_step_id, tenant_id, project_id, stage); one-time, trigger-guarded."""
        return self.connection.execute(
            """UPDATE ago_founder_intake_stages SET plan_step_id=%s
               WHERE tenant_id=%s AND intake_id=%s AND stage=%s AND plan_step_id IS NULL""",
            parameters,
        )

    def insert_progression_06(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            """INSERT INTO ago_project_stage_progressions
               (tenant_id,intake_id,plan_id,from_stage,to_stage,passed_task_id,
                plan_step_id,task_id,assignee_id,decided_by_employee_id,authorized_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id,created_at""",
            parameters,
        )

    def insert_project_notice_07(self, parameters: Any = None) -> Cursor:
        """(tenant_id, founder_id, author_name, body, employee_id)"""
        return self.connection.execute(
            """INSERT INTO ago_company_chat
               (tenant_id,channel,author_id,author_name,body,kind,employee_id)
               VALUES (%s,'global',%s,%s,%s,'project',%s)""",
            parameters,
        )

    def select_project_of_task_08(self, parameters: Any = None) -> Cursor:
        """(tenant_id, task_id, founder_id): the Founder project whose stage
        step is linked to this task, if any."""
        return self.connection.execute(
            """SELECT i.id AS project_id,s.stage
               FROM ago_plan_steps ps
               JOIN ago_founder_intake_stages s ON s.tenant_id=ps.tenant_id
                AND s.plan_id=ps.plan_id AND s.plan_step_id=ps.id
               JOIN ago_founder_intakes i ON i.tenant_id=s.tenant_id AND i.id=s.intake_id
               WHERE ps.tenant_id=%s AND ps.task_id=%s AND i.founder_id=%s""",
            parameters,
        )

    def select_qa_candidates_09(self, parameters: Any = None) -> Cursor:
        """(project_id, tenant_id): active AI employees, the project's approved
        quality-stage tester first, then by name."""
        return self.connection.execute(
            """SELECT e.id,e.name,e.role_title,
                      EXISTS (SELECT 1 FROM ago_project_stage_delegation_activations a
                              WHERE a.tenant_id=e.tenant_id AND a.intake_id=%s
                                AND a.stage='quality' AND a.assignee_id=e.id)
                        AS project_tester
               FROM ago_employees e
               WHERE e.tenant_id=%s AND e.kind='ai'
                 AND NOT EXISTS (SELECT 1 FROM ago_personnel_events pe
                                 WHERE pe.tenant_id=e.tenant_id AND pe.employee_id=e.id
                                   AND pe.change_kind='terminated')
               ORDER BY project_tester DESC,lower(e.name),e.id""",
            parameters,
        )
