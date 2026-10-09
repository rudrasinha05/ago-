"""M5 policy experiments require independent approval and never apply automatically."""
import os
from uuid import uuid4

import pytest

from ago.experiments import ExperimentStore
from ago.governance import ApprovalRepository
from ago.organization_store import OrganizationStore
from ago.scorecard import Scorecard


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
            db.execute("INSERT INTO ago_tenants(id,name) VALUES (%s,%s)", (tenant, "Evolution test"))
            org = OrganizationStore(db)
            dept = org.add_department(tenant_id=tenant, name="Governance")
            people = [
                org.hire(tenant_id=tenant, department_id=dept.id, name=name, kind="human")
                for name in ("Proposer", "Independent Reviewer")
            ]
            for index, person in enumerate(people):
                db.execute(
                    "INSERT INTO ago_users(id,tenant_id,email,password_hash) VALUES (%s,%s,%s,%s)",
                    (person.id, tenant, f"evo{index}@example.test", "test-only"),
                )
            yield db, tenant, people
        finally:
            db.rollback()


def test_experiment_is_proposal_only(case):
    db, tenant, (author, reviewer) = case
    store = ExperimentStore(db)
    proposal = store.propose(
        tenant_id=tenant, proposer_id=author.id,
        hypothesis="Reduce unnecessary approvals",
        baseline="Approval for every action",
        candidate="Apply lower risk for internal read-only report",
    )
    assert proposal["applied"] is False
    assert store.list(tenant_id=tenant)[0]["approval_status"] == "pending"
    with pytest.raises(PermissionError):
        ApprovalRepository(db).decide(
            request_id=proposal["approval_id"], tenant_id=tenant,
            reviewer_id=author.id, approve=True, reason="Self", authorized=True,
        )
    ApprovalRepository(db).decide(
        request_id=proposal["approval_id"], tenant_id=tenant,
        reviewer_id=reviewer.id, approve=True,
        reason="Independent review", authorized=True,
    )
    assert store.list(tenant_id=tenant)[0]["approval_status"] == "approved"
    assert store.list(tenant_id=str(uuid4())) == []
    score = Scorecard(db).summary(tenant_id=tenant)
    assert score["counts"]["experiments"] == 1
    assert score["virtual_credit_budget"]["remaining"] == "0"
