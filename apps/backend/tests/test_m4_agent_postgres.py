"""M4 agent runtime integration against an isolated PostgreSQL database."""
import os
from uuid import uuid4

import pytest

from ago.agent_handlers import BUILTIN_HANDLERS
from ago.agent_runtime import AgentRuntime
from ago.governance import ApprovalRepository
from ago.organization_store import OrganizationStore
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.task_store import TaskStore


@pytest.fixture
def case():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("PostgreSQL required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant = str(uuid4())
            db.execute("INSERT INTO ago_tenants(id,name) VALUES (%s,%s)", (tenant, "M4 agent test"))
            org = OrganizationStore(db)
            dept = org.add_department(tenant_id=tenant, name="Agents")
            user = org.hire(tenant_id=tenant, department_id=dept.id, name="Operator", kind="human")
            reviewer = org.hire(tenant_id=tenant, department_id=dept.id, name="Reviewer", kind="human")
            agent = org.hire(tenant_id=tenant, department_id=dept.id, name="Research AI", kind="ai")
            for n, human in enumerate((user, reviewer)):
                db.execute(
                    "INSERT INTO ago_users(id,tenant_id,email,password_hash) VALUES (%s,%s,%s,%s)",
                    (human.id, tenant, f"agentuser{n}@example.test", "test-only"),
                )
            db.execute(
                "INSERT INTO ago_user_roles(tenant_id,user_id,role) VALUES (%s,%s,'operator')",
                (tenant, user.id),
            )
            SecurityControls(db).grant(tenant, "operator", "task:execute")
            yield db, tenant, user, reviewer, agent
        finally:
            db.rollback()


def approved_task(db, tenant, user, reviewer, agent, action="internal:brief"):
    proposal = ApprovalRepository(db).propose(
        tenant_id=tenant, requester_id=user.id, action=action,
    )
    task = TaskStore(db).propose(tenant_id=tenant, assignee_id=agent.id, action=action)
    TaskStore(db).request_approval(
        task_id=task.id, tenant_id=tenant, approval_id=proposal.request_id,
    )
    ApprovalRepository(db).decide(
        request_id=proposal.request_id, tenant_id=tenant,
        reviewer_id=reviewer.id, approve=True, reason="Validated", authorized=True,
    )
    return task.id


def test_agent_result_and_replay_protection(case):
    db, tenant, user, reviewer, agent = case
    task_id = approved_task(db, tenant, user, reviewer, agent)
    runtime = AgentRuntime(db, handlers=BUILTIN_HANDLERS)
    actor = Principal(user.id, tenant, ("operator",))
    result = runtime.run(task_id=task_id, actor=actor)
    assert result["result"]["requires_human_qa"] is True
    assert len(runtime.list(tenant_id=tenant)) == 1
    with pytest.raises(PermissionError):
        runtime.run(task_id=task_id, actor=actor)
    assert runtime.list(tenant_id=str(uuid4())) == []


def test_unregistered_handler_cannot_claim_task(case):
    db, tenant, user, reviewer, agent = case
    task_id = approved_task(db, tenant, user, reviewer, agent, action="send:money")
    with pytest.raises(PermissionError):
        AgentRuntime(db, handlers=BUILTIN_HANDLERS).run(
            task_id=task_id, actor=Principal(user.id, tenant, ("operator",)),
        )
    assert db.execute(
        "SELECT status FROM ago_governed_tasks WHERE id=%s", (task_id,),
    ).fetchone()["status"] == "waiting_approval"
