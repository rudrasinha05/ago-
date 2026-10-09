"""M5 PostgreSQL virtual-credit ledger invariants."""
import os
from uuid import uuid4

import pytest

from ago.credits import CreditBudget
from ago.simulation import ScenarioSimulator


@pytest.fixture
def case():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("AGO_TEST_POSTGRES_DSN required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant, user = str(uuid4()), str(uuid4())
            db.execute("INSERT INTO ago_tenants(id,name) VALUES (%s,%s)", (tenant, "M5 test"))
            db.execute(
                "INSERT INTO ago_users(id,tenant_id,email,password_hash) VALUES (%s,%s,%s,%s)",
                (user, tenant, "m5@example.test", "test-only"),
            )
            yield db, tenant, user
        finally:
            db.rollback()


def test_idempotent_ledger_and_hard_cap(case):
    db, tenant, user = case
    store = CreditBudget(db)
    store.configure(tenant_id=tenant, ceiling="10")
    args = dict(tenant_id=tenant, actor_id=user, amount="3.5",
                category="agent", operation_key="same")
    first = store.charge(**args)
    replay = store.charge(**args)
    assert first["charged"] and not replay["charged"]
    assert first["id"] == replay["id"]
    assert store.balance(tenant_id=tenant)["remaining"] == "6.5000"
    with pytest.raises(PermissionError):
        store.charge(tenant_id=tenant, actor_id=user, amount="7",
                     category="agent", operation_key="overspend")
    with pytest.raises(PermissionError):
        store.configure(tenant_id=tenant, ceiling="1")


def test_usage_history_is_append_only(case):
    psycopg = pytest.importorskip("psycopg")
    db, tenant, user = case
    store = CreditBudget(db)
    store.configure(tenant_id=tenant, ceiling="5")
    entry = store.charge(tenant_id=tenant, actor_id=user, amount="2",
                         category="audit", operation_key="immutable")
    with pytest.raises(psycopg.errors.RaiseException):
        with db.transaction():
            db.execute("DELETE FROM ago_credit_usage WHERE id=%s", (entry["id"],))


def test_simulation_flags_cost_and_failure_risk():
    result = ScenarioSimulator.estimate(
        planned_actions=10, cost_per_action="2.5",
        available_credits="15", failure_percent=40,
    )
    assert result["simulation_only"] is True
    assert "budget_shortfall" in result["risk_flags"]
    assert "high_failure_rate" in result["risk_flags"]
    with pytest.raises(ValueError):
        ScenarioSimulator.estimate(
            planned_actions=-1, cost_per_action="1", available_credits="2",
        )
