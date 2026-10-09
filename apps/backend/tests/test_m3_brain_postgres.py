"""M3 integration: approved strategies, single materialization and QA dependencies."""
import os
from uuid import uuid4

import pytest

from ago.governance import ApprovalRepository
from ago.goals import GoalStore
from ago.organization_store import OrganizationStore
from ago.plan_execution import PlanExecution
from ago.plan_store import PlanStore
from ago.quality import Verdict
from ago.quality_store import QualityStore
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.task_store import TaskStore


@pytest.fixture
def case():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("PostgreSQL test DB required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant = str(uuid4())
            db.execute(
                "INSERT INTO ago_tenants(id,name) VALUES (%s,%s)",
                (tenant, "M3 strategy test"),
            )
            org = OrganizationStore(db)
            department = org.add_department(tenant_id=tenant, name="Strategy")
            author = org.hire(
                tenant_id=tenant, department_id=department.id,
                name="Author", kind="human",
            )
            reviewer = org.hire(
                tenant_id=tenant, department_id=department.id,
                name="Reviewer", kind="human",
            )
            agent = org.hire(
                tenant_id=tenant, department_id=department.id,
                name="Agent", kind="ai",
            )
            security = SecurityControls(db)
            for number, person in enumerate((author, reviewer)):
                db.execute(
                    """INSERT INTO ago_users(id,tenant_id,email,password_hash)
                       VALUES (%s,%s,%s,%s)""",
                    (person.id, tenant, f"m3human{number}@example.test", "test-only"),
                )
                db.execute(
                    """INSERT INTO ago_user_roles(tenant_id,user_id,role)
                       VALUES (%s,%s,'operator')""",
                    (tenant, person.id),
                )
            security.grant(tenant, "operator", "task:execute")
            security.grant(tenant, "operator", "qa:review")
            yield db, tenant, author, reviewer, agent
        finally:
            db.rollback()


def test_strategic_plan_requires_approval_and_step_qa(case):
    db, tenant, author, reviewer, agent = case
    goals = GoalStore(db)
    goal_id = goals.create(
        tenant_id=tenant, created_by=author.id, title="Build department capability",
    )
    plans = PlanStore(db)
    plan_id = plans.create(
        tenant_id=tenant, proposer_id=author.id, goal_id=goal_id, title="Initial roadmap",
    )
    first = plans.add_step(
        tenant_id=tenant, plan_id=plan_id,
        action="internal:first", assignee_id=agent.id,
    )
    plans.add_step(
        tenant_id=tenant, plan_id=plan_id,
        action="internal:second", assignee_id=agent.id, depends_on=first,
    )
    approval_id = plans.submit(
        tenant_id=tenant, plan_id=plan_id, requester_id=author.id,
    )
    execution = PlanExecution(db)
    with pytest.raises(PermissionError):
        execution.activate(tenant_id=tenant, plan_id=plan_id)
    with pytest.raises(PermissionError):
        plans.add_step(
            tenant_id=tenant, plan_id=plan_id,
            action="internal:after-submit", assignee_id=agent.id,
        )
    approvals = ApprovalRepository(db)
    approvals.decide(
        request_id=approval_id, tenant_id=tenant,
        reviewer_id=reviewer.id, approve=True,
        reason="Strategic plan approved", authorized=True,
    )
    execution.activate(tenant_id=tenant, plan_id=plan_id)
    first_task, second_task = execution.materialize(
        tenant_id=tenant, plan_id=plan_id,
    )
    assert [first_task, second_task] == execution.materialize(
        tenant_id=tenant, plan_id=plan_id,
    )
    tasks = TaskStore(db)
    for task_id, action in (
        (first_task, "internal:first"),
        (second_task, "internal:second"),
    ):
        approval = approvals.propose(
            tenant_id=tenant, action=action, requester_id=author.id,
        )
        tasks.request_approval(
            task_id=task_id, tenant_id=tenant,
            approval_id=approval.request_id,
        )
        approvals.decide(
            request_id=approval.request_id, tenant_id=tenant,
            reviewer_id=reviewer.id, approve=True,
            reason="Reviewed action", authorized=True,
        )
    actor = Principal(author.id, tenant, ("operator",))
    with pytest.raises(PermissionError):
        tasks.authorize_and_start(task_id=second_task, principal=actor)
    tasks.authorize_and_start(task_id=first_task, principal=actor)
    tasks.finish(task_id=first_task, tenant_id=tenant, success=True)
    with pytest.raises(PermissionError):
        tasks.authorize_and_start(task_id=second_task, principal=actor)
    QualityStore(db).review(
        task_id=first_task, principal=Principal(reviewer.id, tenant, ("operator",)),
        verdict=Verdict.PASS, evidence="Independent review passed",
    )
    tasks.authorize_and_start(task_id=second_task, principal=actor)


def test_cross_tenant_parent_cannot_be_selected(case):
    db, tenant, author, _, _ = case
    other = str(uuid4())
    db.execute("INSERT INTO ago_tenants(id,name) VALUES (%s,%s)", (other, "Other"))
    parent = GoalStore(db).create(
        tenant_id=tenant, created_by=author.id, title="Private root",
    )
    with pytest.raises(PermissionError):
        GoalStore(db).create(
            tenant_id=other, created_by=author.id,
            title="Invalid child", parent_id=parent,
        )
