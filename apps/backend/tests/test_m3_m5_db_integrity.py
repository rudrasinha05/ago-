"""PostgreSQL integrity invariants for immutable plans and agent results."""
import os
from uuid import uuid4

import pytest

from ago.goals import GoalStore
from ago.organization_store import OrganizationStore
from ago.plan_store import PlanStore


@pytest.fixture
def prepared():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Database required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant = str(uuid4())
            db.execute("INSERT INTO ago_tenants(id,name) VALUES (%s,%s)", (tenant, "Integrity"))
            org = OrganizationStore(db)
            dept = org.add_department(tenant_id=tenant, name="Proof")
            human = org.hire(
                tenant_id=tenant, department_id=dept.id, name="Human", kind="human",
            )
            ai = org.hire(
                tenant_id=tenant, department_id=dept.id, name="AI", kind="ai",
            )
            db.execute(
                """INSERT INTO ago_users(id,tenant_id,email,password_hash)
                   VALUES (%s,%s,%s,%s)""",
                (human.id, tenant, "integrity@example.test", "test-only"),
            )
            yield db, tenant, human, ai
        finally:
            db.rollback()


def test_submitted_steps_cannot_be_rewritten(prepared):
    psycopg = pytest.importorskip("psycopg")
    db, tenant, human, ai = prepared
    goal = GoalStore(db).create(
        tenant_id=tenant, created_by=human.id, title="Strategic evidence",
    )
    plan = PlanStore(db).create(
        tenant_id=tenant, proposer_id=human.id, goal_id=goal, title="Immutable plan",
    )
    step = PlanStore(db).add_step(
        tenant_id=tenant, plan_id=plan,
        action="internal:brief", assignee_id=ai.id,
    )
    PlanStore(db).submit(tenant_id=tenant, plan_id=plan, requester_id=human.id)
    with pytest.raises(psycopg.errors.RaiseException):
        with db.transaction():
            db.execute(
                "UPDATE ago_plan_steps SET action='different' WHERE id=%s", (step,),
            )
