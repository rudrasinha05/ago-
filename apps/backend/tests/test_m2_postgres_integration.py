"""M2 integration tests against migrated disposable PostgreSQL database."""
import os
from uuid import uuid4

import pytest

from ago.governance import ApprovalRepository
from ago.memory import MemoryRecord
from ago.organization_store import MemoryStore, OrganizationStore
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.task_store import TaskStore


@pytest.fixture
def db():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("AGO_TEST_POSTGRES_DSN required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        try:
            yield conn
        finally:
            conn.rollback()


def tenant(conn):
    tenant_id = str(uuid4())
    conn.execute("INSERT INTO ago_tenants(id, name) VALUES (%s, %s)", (tenant_id, "M2 test"))
    return tenant_id


def test_organization_and_memory_tenant_isolation(db):
    tenant_a = tenant(db)
    tenant_b = tenant(db)
    store = OrganizationStore(db)
    department = store.add_department(tenant_id=tenant_a, name="Engineering")
    manager = store.hire(
        tenant_id=tenant_a, department_id=department.id, name="Manager", kind="human"
    )
    worker = store.hire(
        tenant_id=tenant_a, department_id=department.id, name="Worker",
        kind="ai", manager_id=manager.id,
    )
    assert worker.id in [
        employee.id for employee in store.list_employees(
            tenant_id=tenant_a, department_id=department.id
        )
    ]
    assert store.list_employees(tenant_id=tenant_b, department_id=department.id) == []
    memory = MemoryRecord.create(
        tenant_id=tenant_a, owner_id=manager.id, content="internal",
    )
    memories = MemoryStore(db)
    memories.save(memory)
    assert memories.get(
        record_id=memory.id, tenant_id=tenant_a, reader_id=manager.id
    ).content == "internal"
    with pytest.raises(PermissionError):
        memories.get(record_id=memory.id, tenant_id=tenant_a, reader_id=worker.id)
    with pytest.raises(LookupError):
        memories.get(record_id=memory.id, tenant_id=tenant_b, reader_id=manager.id)


def test_approved_task_lifecycle_and_audit(db):
    tenant_id = tenant(db)
    org = OrganizationStore(db)
    department = org.add_department(tenant_id=tenant_id, name="Operations")
    requester = org.hire(
        tenant_id=tenant_id, department_id=department.id, name="Agent", kind="ai"
    )
    reviewer = org.hire(
        tenant_id=tenant_id, department_id=department.id, name="Reviewer", kind="human"
    )
    db.execute(
        """INSERT INTO ago_users(id, tenant_id, email, password_hash)
           VALUES (%s, %s, %s, %s)""",
        (reviewer.id, tenant_id, "reviewer@example.test", "test-only-not-authenticating"),
    )
    db.execute(
        "INSERT INTO ago_user_roles(tenant_id, user_id, role) VALUES (%s, %s, %s)",
        (tenant_id, reviewer.id, "operator"),
    )
    security = SecurityControls(db)
    security.grant(tenant_id, "operator", "task:execute")
    principal = Principal(reviewer.id, tenant_id, ("operator",))
    approvals = ApprovalRepository(db)
    proposal = approvals.propose(
        tenant_id=tenant_id, action="deploy:staging", requester_id=requester.id
    )
    tasks = TaskStore(db)
    task = tasks.propose(
        tenant_id=tenant_id, action="deploy:staging", assignee_id=requester.id
    )
    tasks.request_approval(
        task_id=task.id, tenant_id=tenant_id, approval_id=proposal.request_id
    )
    with pytest.raises(PermissionError):
        tasks.authorize_and_start(task_id=task.id, principal=principal)
    approvals.decide(
        request_id=proposal.request_id, tenant_id=tenant_id,
        reviewer_id=reviewer.id, approve=True, reason="Reviewed", authorized=True,
    )
    started = tasks.authorize_and_start(task_id=task.id, principal=principal)
    assert started.status.value == "running"
    tasks.finish(task_id=task.id, tenant_id=tenant_id, success=True)
    with pytest.raises(PermissionError):
        tasks.authorize_and_start(task_id=task.id, principal=principal)
    events = db.execute(
        "SELECT event FROM ago_approval_audit WHERE request_id=%s ORDER BY id",
        (proposal.request_id,),
    ).fetchall()
    assert [row["event"] for row in events] == ["proposed", "approved"]
