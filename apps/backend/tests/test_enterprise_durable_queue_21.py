"""Section 21: durable fair queue never replays governed side effects."""
from datetime import datetime, timedelta, timezone
import time
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


def test_expired_unknown_lease_requires_reconciliation_never_automatic_replay(case):
    """Real PostgreSQL expiry: neither claim API nor direct SQL may replay.

    A subsecond lease is inserted only in the disposable integration DB.
    The normal public claim API enforces 300..3600 second leases.
    """
    client, headers, context = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    worker = employee(client, founder, department(client, founder))
    task = _approved_task(client, founder, reviewer, worker)
    item = _enqueue(client, founder, task, 50)
    db = context["db"]
    with db.transaction():
        db.execute(
            """INSERT INTO ago_oos_queue_events
               (id,tenant_id,queue_id,actor_id,state,sequence,expires_at,explanation)
               VALUES (%s,%s,%s,%s,'leased',1,
                       clock_timestamp()+interval '1 second',%s)""",
            (str(uuid4()), context["tenant"], item["id"],
             context["founder_id"], "Disposable DB: simulate uncertain expiry"),
        )
    time.sleep(1.3)
    queue = client.get(
        "/v1/operations/enterprise/work-queue", headers=founder,
    )
    assert queue.status_code == 200, queue.text
    entry = next(row for row in queue.json() if row["id"] == item["id"])
    assert entry["lease_state"] == "leased"
    assert entry["requires_reconciliation"] is True
    claim = post(client, "/v1/operations/enterprise/work-queue/claim",
                 founder, {"lease_seconds": 600})
    assert claim["queue_id"] is None
    assert claim["reason"] == "no_safe_approved_task"
    with pytest.raises(Exception, match="Existing work lease cannot be stolen or replayed"):
        with db.transaction():
            db.execute(
                """INSERT INTO ago_oos_queue_events
                   (id,tenant_id,queue_id,actor_id,state,sequence,expires_at,explanation)
                   VALUES (%s,%s,%s,%s,'leased',2,
                           clock_timestamp()+interval '10 minutes',%s)""",
                (str(uuid4()), context["tenant"], item["id"],
                 context["founder_id"], "Malicious raw SQL replay attempt"),
            )
    release = f"/v1/operations/enterprise/work-queue/{item['id']}/release"
    post(client, release, founder,
         {"status": "released", "explanation": "Unsafe replay of expired lease"},
         expected=403)
    resolved = post(client, release, founder,
                    {"status": "reconciled",
                     "explanation": "Founder inspected unknown outcome: no retry"})
    assert resolved["state"] == "reconciled"
    assert resolved["replayed"] is False
    after = post(client, "/v1/operations/enterprise/work-queue/claim",
                 founder, {"lease_seconds": 600})
    assert after["queue_id"] is None
    assert after["reason"] == "no_safe_approved_task"


def test_two_project_priority_isolation_in_real_postgres(case):
    """Atomic plan scope: a high-priority unrelated project cannot be claimed."""
    from test_enterprise_capacity_21 import _approved_task
    client,headers,context=case
    founder,reviewer=headers["founder"],headers["reviewer"]
    # Separate real workers/departments: the existing company capacity gate
    # correctly refuses two simultaneous leases of one AI employee.
    # This checks project isolation without weakening that independent gate.
    agent_a=employee(client,founder,department(client,founder))
    agent_b=employee(client,founder,department(client,founder))
    projects=[]
    for name in ("Alpha","Beta"):
        project=post(client,"/v1/organization/company/projects/start",founder,{
            "brief":"Build an auditable "+name+" application with safe validated engineering workflows",
            "operation_key":str(uuid4()),
        })
        approval=post(client,"/v1/brain/plans/"+project["plan_id"]+"/submit",founder)
        post(client,"/v1/governance/approvals/"+approval["approval_id"]+"/decision",
             founder,{"approve":True,"reason":"Approve bounded project plan"})
        post(client,"/v1/brain/plans/"+project["plan_id"]+"/activate",founder)
        projects.append(project)
    task_a=_approved_task(client,founder,reviewer,agent_a)
    task_b=_approved_task(client,founder,reviewer,agent_b)
    for project,task in zip(projects,(task_a,task_b)):
        step=project["stages"][0]["plan_step_id"]
        assert step is not None
        # Disposable test DB only; attach a separately approved task to the
        # persisted discovery plan step for the scoped admission check.
        with context["db"].transaction():
            context["db"].execute(
                """UPDATE ago_plan_steps SET task_id=%s
                   WHERE tenant_id=%s AND id=%s AND plan_id=%s""",
                (task,context["tenant"],step,project["plan_id"]),
            )
    qa=_enqueue(client,founder,task_a,1)
    qb=_enqueue(client,founder,task_b,99)
    path="/v1/operations/enterprise/work-queue"
    scoped=client.get(path,headers=founder,
                      params={"plan_id":projects[0]["plan_id"]})
    assert scoped.status_code==200,scoped.text
    assert [x["id"] for x in scoped.json()]==[qa["id"]]
    assert client.get(path,headers=founder,
                      params={"plan_id":projects[1]["plan_id"]}).json()[0]["id"]==qb["id"]
    first=post(client,path+"/offline-claim",founder,
               {"lease_seconds":600,"plan_id":projects[0]["plan_id"]})
    assert first["queue_id"]==qa["id"]
    assert first["task_id"]==task_a
    second=post(client,path+"/offline-claim",founder,
                {"lease_seconds":600,"plan_id":projects[1]["plan_id"]})
    assert second["queue_id"]==qb["id"]
    assert second["task_id"]==task_b
    empty=post(client,path+"/offline-claim",founder,
               {"lease_seconds":600,"plan_id":str(uuid4())})
    assert empty["queue_id"] is None
    # Reviewer already has operations:read in this tenant; scoped filtering
    # must preserve existing RBAC, not falsely claim Founder-only metadata.
    reviewer_view=client.get(path,headers=reviewer,
                             params={"plan_id":projects[0]["plan_id"]})
    assert reviewer_view.status_code==200,reviewer_view.text
    assert [r["id"] for r in reviewer_view.json()]==[qa["id"]]
    assert client.get(path,params={"plan_id":projects[0]["plan_id"]}).status_code==401
