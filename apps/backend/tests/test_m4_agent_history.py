"""M4 agent run history remains immutable after terminal completion."""
import os
from uuid import uuid4

import pytest

from ago.organization_store import OrganizationStore
from ago.task_store import TaskStore


def test_completed_agent_run_cannot_be_rewritten():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("PostgreSQL required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant, human = str(uuid4()), str(uuid4())
            db.execute("INSERT INTO ago_tenants(id,name) VALUES (%s,%s)", (tenant, "Audit"))
            org = OrganizationStore(db)
            department = org.add_department(tenant_id=tenant, name="Agents")
            ai = org.hire(
                tenant_id=tenant, department_id=department.id,
                name="Agent", kind="ai",
            )
            db.execute(
                "INSERT INTO ago_users(id,tenant_id,email,password_hash) VALUES (%s,%s,%s,%s)",
                (human, tenant, "history@example.test", "test-only"),
            )
            task = TaskStore(db).propose(
                tenant_id=tenant, action="internal:brief", assignee_id=ai.id,
            )
            run_id = str(uuid4())
            db.execute(
                """INSERT INTO ago_agent_runs
                   (id,tenant_id,task_id,agent_id,executor_id,status)
                   VALUES (%s,%s,%s,%s,%s,'running')""",
                (run_id, tenant, task.id, ai.id, human),
            )
            db.execute(
                """UPDATE ago_agent_runs
                   SET status='completed',result='{}'::jsonb,finished_at=now()
                   WHERE id=%s""",
                (run_id,),
            )
            with pytest.raises(psycopg.errors.RaiseException):
                with db.transaction():
                    db.execute(
                        """UPDATE ago_agent_runs
                           SET result='{"tampered":true}'::jsonb WHERE id=%s""",
                        (run_id,),
                    )
        finally:
            db.rollback()
