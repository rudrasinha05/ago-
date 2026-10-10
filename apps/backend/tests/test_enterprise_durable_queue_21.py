"""Section 21: durable fair queue never replays governed side effects."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from test_enterprise_capacity_21 import _approved_task
from test_enterprise_http_21_27 import department, employee
from test_m7_http_postgres import case as case, post


def _enqueue(client, founder, task_id, priority):
    path = "/v1/operations/enterprise/work-queue"
    payload = {"task_id": task_id, "priority": priority,
               "operation_key": "queue:" + task_id,
               "eligible_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()}
    result = post(client, path, founder, payload)
    assert not result["executed"]
    assert post(client, path, founder, payload)["idempotent"]
    return result


def test_fair_approved_priority_leases_are_durable_without_automatic_execution(case):
    client, headers, context = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    first = employee(client, founder, dept)
    second = employee(client, founder, dept)
    low = _approved_task(client, founder, reviewer, first)
    high = _approved_task(client, founder, reviewer, second)
    low_queue = _enqueue(client, founder, low, 1)
    high_queue = _enqueue(client, founder, high, 99)
    claim_path = "/v1/operations/enterprise/work-queue/claim"
    leased = post(client, claim_path, founder, {"lease_seconds": 600})
    assert leased["queue_id"] == high_queue["id"]
    assert leased["manual_authorized_execution_required"]
    assert leased["executed"] is False
    second_lease = post(client, claim_path, founder, {"lease_seconds": 600})
    assert second_lease["queue_id"] == low_queue["id"]
    assert second_lease["executed"] is False
    view = client.get("/v1/operations/enterprise/work-queue",
                      headers=founder).json()
    assert len(view) == 2
    assert all(row["lease_state"] == "leased" for row in view)
    assert client.get("/v1/operations/enterprise/work-queue").status_code == 401
    with pytest.raises(Exception, match="append-only"):
        with context["db"].transaction():
            context["db"].execute(
                """UPDATE ago_oos_queue_events SET state='released'
                   WHERE tenant_id=%s AND queue_id=%s""",
                (context["tenant"], high_queue["id"]),
            )


def test_released_lease_can_be_reclaimed_but_terminal_reconciliation_cannot(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    worker = employee(client, founder, department(client, founder))
    task = _approved_task(client, founder, reviewer, worker)
    item = _enqueue(client, founder, task, 10)
    claim_path = "/v1/operations/enterprise/work-queue/claim"
    claim = post(client, claim_path, founder, {"lease_seconds": 600})
    assert claim["queue_id"] == item["id"]
    release = f"/v1/operations/enterprise/work-queue/{item['id']}/release"
    post(client, release, founder,
         {"status": "released", "explanation": "No execution attempted"})
    reclaimed = post(client, claim_path, founder, {"lease_seconds": 600})
    assert reclaimed["queue_id"] == item["id"]
    post(client, release, founder,
         {"status": "reconciled", "explanation": "Human reconciled recovery; no replay"})
    remaining = post(client, claim_path, founder, {"lease_seconds": 600})
    assert remaining["queue_id"] is None
    assert remaining["reason"] == "no_safe_approved_task"


def test_unapproved_task_cannot_enter_durable_queue(case):
    client, headers, _ = case
    founder = headers["founder"]
    worker = employee(client, founder, department(client, founder))
    pending = post(client, "/v1/tasks", founder,
                   {"assignee_id": worker, "action": "internal:brief"})
    post(client, "/v1/operations/enterprise/work-queue", founder, {
        "task_id": pending["id"], "operation_key": str(uuid4()),
        "priority": 50, "eligible_at": datetime.now(timezone.utc).isoformat(),
    }, expected=403)
