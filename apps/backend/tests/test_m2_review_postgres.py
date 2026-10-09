"""M2 PostgreSQL QA and approval tamper-resistance acceptance."""
import os
from uuid import uuid4

import pytest

from ago.governance import ApprovalRepository
from ago.organization_store import OrganizationStore
from ago.quality import Verdict
from ago.quality_store import QualityStore
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.task_store import TaskStore


@pytest.fixture
def db():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Requires AGO_TEST_POSTGRES_DSN")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            yield db
        finally:
            db.rollback()


def setup_tenant(db):
    tenant = str(uuid4())
    db.execute("INSERT INTO ago_tenants(id, name) VALUES (%s, %s)", (tenant, "QA gate test"))
    org = OrganizationStore(db)
    dept = org.add_department(tenant_id=tenant, name="Engineering")
    author = org.hire(tenant_id=tenant, department_id=dept.id, name="Agent", kind="ai")
    human = org.hire(tenant_id=tenant, department_id=dept.id, name="Human", kind="human")
    db.execute(
        "INSERT INTO ago_users(id, tenant_id, email, password_hash) VALUES (%s,%s,%s,%s)",
        (human.id, tenant, "qa@example.test", "test-only-not-authenticating"),
    )
    db.execute(
        "INSERT INTO ago_user_roles(tenant_id,user_id,role) VALUES (%s,%s,%s)",
        (tenant, human.id, "qa"),
    )
    security = SecurityControls(db)
    for permission in ("qa:review", "task:execute", "approval:decide"):
        security.grant(tenant, "qa", permission)
    return tenant, author, human


def test_qa_review_after_completed_task_is_append_only(db):
    psycopg = pytest.importorskip("psycopg")
    tenant, author, human = setup_tenant(db)
    approval = ApprovalRepository(db).propose(
        tenant_id=tenant, action="internal:check", requester_id=author.id,
    )
    task = TaskStore(db).propose(
        tenant_id=tenant, action="internal:check", assignee_id=author.id,
    )
    TaskStore(db).request_approval(
        task_id=task.id, tenant_id=tenant, approval_id=approval.request_id,
    )
    ApprovalRepository(db).decide(
        request_id=approval.request_id, tenant_id=tenant,
        reviewer_id=human.id, approve=True, reason="Approved",
        authorized=True,
    )
    principal = Principal(human.id, tenant, ("qa",))
    TaskStore(db).authorize_and_start(task_id=task.id, principal=principal)
    TaskStore(db).finish(task_id=task.id, tenant_id=tenant, success=True)
    QualityStore(db).review(
        task_id=task.id, principal=principal,
        verdict=Verdict.PASS, evidence="Executed test and reviewed result",
    )
    QualityStore(db).require_pass(task_id=task.id, tenant_id=tenant)
    with pytest.raises(psycopg.errors.RaiseException):
        with db.transaction():
            db.execute(
                "DELETE FROM ago_task_reviews WHERE tenant_id=%s AND task_id=%s",
                (tenant, task.id),
            )
    with pytest.raises(psycopg.errors.RaiseException):
        with db.transaction():
            db.execute(
                "UPDATE ago_approval_audit SET reason='tampered' WHERE request_id=%s",
                (approval.request_id,),
            )


def test_cannot_assign_one_approval_to_two_tasks(db):
    psycopg = pytest.importorskip("psycopg")
    tenant, author, _ = setup_tenant(db)
    approval = ApprovalRepository(db).propose(
        tenant_id=tenant, action="internal:check", requester_id=author.id,
    )
    store = TaskStore(db)
    first = store.propose(tenant_id=tenant, action="internal:check", assignee_id=author.id)
    second = store.propose(tenant_id=tenant, action="internal:check", assignee_id=author.id)
    store.request_approval(
        task_id=first.id, tenant_id=tenant, approval_id=approval.request_id,
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.transaction():
            store.request_approval(
                task_id=second.id, tenant_id=tenant, approval_id=approval.request_id,
            )
