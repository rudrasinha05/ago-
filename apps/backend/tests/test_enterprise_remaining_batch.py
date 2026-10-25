"""Prospective data, durable lifecycle and source-document security acceptance."""

import base64
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ago.enterprise_domains import (
    LIFECYCLE_PHASES,
    calibrate_runtime,
    controlled_assignment,
    forecast_runtime,
    next_lifecycle_phase,
)
from test_enterprise_capacity_21 import _approved_task
from test_enterprise_durable_queue_21 import _enqueue
from test_enterprise_http_21_27 import department, employee
from test_m7_http_postgres import case as case, decide, post

BASE = "/v1/operations/enterprise"


def review(client, founder, reviewer, item):
    approval = post(client, BASE + "/evidence/" + item["id"] + "/approval", founder)
    decide(client, reviewer, approval["approval_id"])
    return post(
        client,
        BASE + "/evidence/" + item["id"] + "/review",
        founder,
        {"approval_id": approval["approval_id"]},
    )


@pytest.mark.parametrize(
    "previous,expected", [(None, "sense"), *zip(LIFECYCLE_PHASES, (*LIFECYCLE_PHASES[1:], "sense"))]
)
def test_durable_phase_sequence(previous, expected):
    assert next_lifecycle_phase(previous) == expected


def test_phase_corruption_is_denied():
    with pytest.raises(ValueError, match="checkpoint"):
        next_lifecycle_phase("promote_permissions")


def test_prospective_seeded_assignment_balanced_and_immutable():
    ids = [str(uuid4()) for _ in range(9)]
    actual = controlled_assignment(ids, "predeclared")
    assert actual == controlled_assignment(list(reversed(ids)), "predeclared")
    assert list(actual.values()).count("baseline") == 5
    with pytest.raises(ValueError, match="Unique"):
        controlled_assignment([ids[0], ids[0]], "seed")
    with pytest.raises(ValueError, match="Unique"):
        controlled_assignment(ids, "")


def test_runtime_metrics_and_unknown_training():
    now = datetime.now(timezone.utc)
    cohort = [
        {
            "id": "future",
            "created_at": now.isoformat(),
            "deadline": (now + timedelta(seconds=15)).isoformat(),
        }
    ]
    forecast = forecast_runtime([{"elapsed_seconds": 10}, {"elapsed_seconds": 20}], cohort)
    actual = calibrate_runtime(forecast, [{"id": "future", "elapsed_seconds": 30}])
    assert actual["mean_absolute_error_seconds"] == 15
    assert actual["empirical_range_coverage"] == 0
    assert actual["deadline_classification_error_rate"] == 1
    assert not actual["accuracy_certified"]
    assert calibrate_runtime(forecast, [])["pending_samples"] == 1
    assert (
        calibrate_runtime(forecast_runtime([], cohort), [{"id": "future", "elapsed_seconds": 30}])[
            "mean_absolute_error_seconds"
        ]
        is None
    )
    with pytest.raises(ValueError, match="same-cohort"):
        calibrate_runtime(forecast, [{"id": "other", "elapsed_seconds": 1}])


def test_full_lifecycle_dispatch_exact_retry_restart_and_sync(case):
    client, headers, _ = case
    f, r = headers["founder"], headers["reviewer"]
    worker = employee(client, f, department(client, f))
    task = _approved_task(client, f, r, worker)
    _enqueue(client, f, task, 30)
    cursor = None
    for phase in LIFECYCLE_PHASES:
        params = {
            "operation_key": "tick-" + phase,
            "expected_event_id": cursor,
            "execute_one": True,
        }
        event = post(client, BASE + "/lifecycle/advance", f, params)
        assert event["payload"]["phase"] == phase
        assert post(client, BASE + "/lifecycle/advance", f, params)["idempotent"]
        post(client, BASE + "/lifecycle/advance", f, {**params, "execute_one": False}, expected=400)
        if phase == "coordinate":
            assert event["payload"]["execution"]["executed"]
        cursor = event["id"]
    checkpoint = client.get(BASE + "/lifecycle", headers=f).json()["checkpoint"]
    assert checkpoint["id"] == cursor and checkpoint["payload"]["sequence"] == 8
    assert client.get(BASE + "/twin/sync", headers=f).json()["snapshot"]
    post(
        client,
        BASE + "/lifecycle/advance",
        f,
        {"operation_key": "stale", "expected_event_id": None},
        expected=400,
    )
    assert (
        post(
            client,
            BASE + "/lifecycle/advance",
            f,
            {"operation_key": "restart", "expected_event_id": cursor},
        )["payload"]["phase"]
        == "sense"
    )
    assert client.get(BASE + "/lifecycle").status_code == 401
    assert len(client.get("/v1/agents/runs", headers=f).json()) == 1


def test_reviewed_prospective_experiment_actual_variant_output_and_later_qa(case):
    client, headers, context = case
    f, r = headers["founder"], headers["reviewer"]
    worker = employee(client, f, department(client, f))
    tasks = [_approved_task(client, f, r, worker) for _ in range(4)]
    params = {
        "task_ids": tasks,
        "seed": "frozen-seed",
        "hypothesis": "Checklist improves independent review.",
        "rollback_plan": "Retain ordinary output; no global policy mutation.",
        "operation_key": "experiment",
    }
    registered = post(client, BASE + "/evolution/register", f, params)
    post(client, "/v1/agents/tasks/" + tasks[0] + "/run", f, expected=403)
    assert post(client, BASE + "/evolution/register", f, params)["idempotent"]
    post(client, BASE + "/evolution/register", f, {**params, "seed": "substituted"}, expected=400)
    review(client, f, r, registered)
    before = post(
        client,
        BASE + "/evolution/registrations/" + registered["id"] + "/measure",
        f,
        {"operation_key": "before"},
    )
    assert before["payload"]["pending_samples"] == 4
    variants = set()
    for task in tasks:
        result = post(client, "/v1/agents/tasks/" + task + "/run", f)["result"]
        variant = result["experiment"]["variant"]
        variants.add(variant)
        assert result["experiment"]["registration_digest"] == registered["digest"]
        assert ("review_checklist" in result) == (variant == "candidate")
        post(
            client,
            "/v1/tasks/" + task + "/review",
            r,
            {"verdict": "pass", "evidence": "Actual isolated packet independently inspected"},
        )
    assert variants == {"baseline", "candidate"}
    after = post(
        client,
        BASE + "/evolution/registrations/" + registered["id"] + "/measure",
        f,
        {"operation_key": "after"},
    )["payload"]
    assert after["complete"] and after["baseline"]["samples"] == after["candidate"]["samples"] == 2
    assert after["pass_rate_delta"] == 0 and not after["policy_promoted"]
    # Agent results are founder-only; evidence keeps only a digest and the
    # experiment metadata the measurement needs.
    outcomes = after["source_outcomes"]
    assert {str(o["id"]) for o in outcomes} == set(tasks)
    assert all("result" not in o and len(o["result_sha256"]) == 64 for o in outcomes)
    assert {o["experiment"]["variant"] for o in outcomes} == {"baseline", "candidate"}
    listed = client.get(BASE + "/evidence?kind=experiment_measurement", headers=f)
    assert listed.status_code == 200 and "review_checklist" not in listed.text
    post(
        client,
        BASE + "/evolution/register",
        f,
        {**params, "operation_key": "retrospective"},
        expected=403,
    )
    with pytest.raises(Exception, match="append-only"):
        with context["db"].transaction():
            context["db"].execute(
                "UPDATE ago_experiment_assignments SET variant='candidate' WHERE tenant_id=%s",
                (context["tenant"],),
            )


def test_experiment_controls_foreign_and_duplicate_enrollment(case):
    client, headers, _ = case
    f, r = headers["founder"], headers["reviewer"]
    worker = employee(client, f, department(client, f))
    tasks = [_approved_task(client, f, r, worker) for _ in range(2)]
    params = {
        "task_ids": tasks,
        "seed": "seed",
        "hypothesis": "Compare packets",
        "rollback_plan": "Retain baseline",
        "operation_key": "exp",
    }
    post(
        client,
        BASE + "/evolution/register",
        f,
        {**params, "task_ids": [tasks[0], str(uuid4())]},
        expected=404,
    )
    post(
        client,
        BASE + "/evolution/register",
        f,
        {**params, "task_ids": [tasks[0], tasks[0]]},
        expected=400,
    )
    post(client, BASE + "/evolution/register", f, params)
    post(
        client, BASE + "/evolution/register", f, {**params, "operation_key": "reuse"}, expected=400
    )


def cost(client, f, key, amount="100", currency="INR"):
    now = datetime.now(timezone.utc)
    return post(
        client,
        BASE + "/costs",
        f,
        {
            "operation_key": key,
            "category": "model",
            "provider": "test-claim",
            "source_ref": "test:" + key,
            "amount": amount,
            "currency": currency,
            "period_start": now.isoformat(),
            "period_end": (now + timedelta(days=1)).isoformat(),
        },
    )["id"]


def document(client, f, identifier, kind, key, raw=None):
    return post(
        client,
        BASE + "/finance/documents",
        f,
        {
            "operation_key": key,
            "cost_id": identifier,
            "document_type": kind,
            "content_base64": base64.b64encode(
                (raw or "Disposable test source " + key).encode()
            ).decode(),
        },
    )


def test_exact_evidence_source_requires_live_founder_even_after_role_revocation(case):
    client, headers, info = case
    founder = headers["founder"]
    identifier = cost(client, founder, "cost")
    item = document(client, founder, identifier, "invoice", "private")
    url = BASE + "/evidence/" + item["id"]
    assert client.get(url, headers=founder).status_code == 200

    # A cached signed session still contains the old Founder role. Give the
    # same user organization:manage through another REAL management role,
    # revoke the database Founder role, and prove the independent live
    # Founder check rejects raw source access. No data is exported.
    db, tenant, founder_id = (
        info["db"], info["tenant"], info["founder_id"]
    )
    db.execute("""
        INSERT INTO ago_role_permissions(tenant_id,role,permission)
        VALUES(%s,'evidence_auditor','organization:manage')
        ON CONFLICT DO NOTHING
    """, (tenant,))
    db.execute("""
        INSERT INTO ago_user_roles(tenant_id,user_id,role)
        VALUES(%s,%s,'evidence_auditor') ON CONFLICT DO NOTHING
    """, (tenant,founder_id))
    db.execute("""
        DELETE FROM ago_user_roles
        WHERE tenant_id=%s AND user_id=%s AND role='founder'
    """, (tenant,founder_id))
    from ago.security import Principal
    from ago.security_controls import SecurityControls
    caller = Principal(founder_id,tenant,("founder",))
    gate = SecurityControls(db)
    assert gate.permitted(caller,"organization:manage",tenant)
    assert not gate.permitted(caller,"approval:founder",tenant)
    assert client.get(url,headers=founder).status_code == 403

    from ago.enterprise_store import EnterpriseOperationsStore
    with pytest.raises(LookupError,match="Evidence not found"):
        EnterpriseOperationsStore(db).evidence_item(
            tenant_id=str(uuid4()), evidence_id=item["id"]
        )


def test_financial_sources_require_independent_review_and_deny_duplicate_bytes(case):
    client, headers, info = case
    f, r = headers["founder"], headers["reviewer"]
    identifier = cost(client, f, "cost")
    invoice = document(client, f, identifier, "invoice", "invoice")
    bank = document(client, f, identifier, "bank", "bank")
    # The bulk evidence list never returns raw document bytes.
    raw_invoice = base64.b64encode(b"Disposable test source invoice").decode()
    listed = client.get(BASE + "/evidence?kind=financial_document", headers=f)
    assert listed.status_code == 200 and raw_invoice not in listed.text
    assert {x["id"] for x in listed.json()} >= {invoice["id"], bank["id"]}
    assert all("content_base64" not in x["payload"] and x["payload"]["content_withheld"]
               for x in listed.json())
    # F3: bulk stays redacted even to the Founder. Exact one-item bytes are
    # privileged and must leave a redacted access audit.
    source_url=BASE+"/evidence/"+invoice["id"]
    exact=client.get(source_url,headers=f)
    assert exact.status_code==200,exact.text
    assert exact.json()["payload"]["content_base64"]==raw_invoice
    assert exact.json()["digest"]==invoice["digest"]
    assert client.get(source_url,headers=r).status_code==403
    assert client.get(BASE+"/evidence/"+str(uuid4()),headers=f).status_code==404
    audit=info["db"].execute("""
        SELECT actor_id,outcome,metadata FROM ago_security_audit
        WHERE tenant_id=%s AND action=%s ORDER BY id DESC LIMIT 1
    """,(info["tenant"],"enterprise:evidence:source_read")).fetchone()
    assert audit and str(audit["actor_id"])==info["founder_id"]
    assert audit["outcome"]=="allowed"
    assert audit["metadata"].get("record_id")==invoice["id"]
    assert raw_invoice not in str(audit["metadata"])
    params = {
        "operation_key": "match",
        "matches": [{"invoice_id": invoice["id"], "bank_id": bank["id"]}],
        "currency": "INR",
        "baseline_revenue": "0",
        "alternative_net": "0",
        "assumptions": "Disposable test records only",
    }
    post(client, BASE + "/finance/reconcile", f, params, expected=403)
    for item in (invoice, bank):
        review(client, f, r, item)
    result = post(client, BASE + "/finance/reconcile", f, params)["payload"]
    assert (
        Decimal(result["observed_cost"]) == 100
        and not result["provider_authenticated"]
        and not result["financial_settlement"]
    )
    assert result["evidence_state"] == "independently_reviewed_document_matches"
    assert post(client, BASE + "/finance/reconcile", f, params)["idempotent"]
    post(
        client,
        BASE + "/finance/reconcile",
        f,
        {**params, "operation_key": "double-charge"},
        expected=400,
    )
    duplicate = document(
        client,
        f,
        cost(client, f, "duplicate-cost"),
        "invoice",
        "duplicate",
        raw="Disposable test source invoice",
    )
    second_bank = document(client, f, duplicate["payload"]["cost"]["id"], "bank", "second-bank")
    for item in (duplicate, second_bank):
        review(client, f, r, item)
    post(
        client,
        BASE + "/finance/reconcile",
        f,
        {
            **params,
            "operation_key": "duplicate-bytes",
            "matches": [{"invoice_id": duplicate["id"], "bank_id": second_bank["id"]}],
        },
        expected=400,
    )
    post(
        client,
        BASE + "/finance/documents",
        f,
        {
            "operation_key": "foreign",
            "cost_id": str(uuid4()),
            "document_type": "invoice",
            "content_base64": "dGVzdA==",
        },
        expected=404,
    )


def test_mismatched_financial_period_amount_and_currency_denied(case):
    client, headers, _ = case
    f, r = headers["founder"], headers["reviewer"]
    a = document(client, f, cost(client, f, "first"), "invoice", "first")
    b = document(client, f, cost(client, f, "other", "200", "USD"), "bank", "other")
    for item in (a, b):
        review(client, f, r, item)
    post(
        client,
        BASE + "/finance/reconcile",
        f,
        {
            "operation_key": "mismatch",
            "matches": [{"invoice_id": a["id"], "bank_id": b["id"]}],
            "currency": "INR",
            "baseline_revenue": "0",
            "alternative_net": "0",
            "assumptions": "Incomparable sources",
        },
        expected=400,
    )


def test_twin_chain_replay_and_retrospective_forecast_denied(case):
    client, headers, _ = case
    f, r = headers["founder"], headers["reviewer"]
    worker = employee(client, f, department(client, f))
    task = _approved_task(client, f, r, worker)
    first = post(client, BASE + "/twin/state", f, {"operation_key": "state-1"})
    post(client, "/v1/agents/tasks/" + task + "/run", f)
    post(
        client,
        "/v1/tasks/" + task + "/review",
        r,
        {"verdict": "pass", "evidence": "Later actual independent QA"},
    )
    assert post(client, BASE + "/twin/state", f, {"operation_key": "state-1"})["idempotent"]
    second = post(client, BASE + "/twin/state", f, {"operation_key": "state-2"})
    assert second["payload"]["previous_snapshot_id"] == first["id"]
    assert second["payload"]["previous_snapshot_digest"] == first["digest"]
    post(
        client,
        BASE + "/twin/forecast",
        f,
        {
            "operation_key": "retro",
            "snapshot_id": first["id"],
            "task_ids": [task],
            "horizon_end": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
        expected=403,
    )
    assert client.get(BASE + "/twin/sync", headers=f).json()["freshness_seconds"] >= 0
    assert client.get(BASE + "/twin/sync").status_code == 401


@pytest.mark.parametrize("expire", [False, True])
def test_opt_in_continuous_worker_signed_phase_cursor_and_expiry(monkeypatch, expire):
    import json
    from ago.local_ops import work_local

    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    calls = []
    checkpoint = None

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == "127.0.0.1" and port == 8000 and timeout == 30

        def request(self, method, path, body, headers):
            self.path = path
            self.body = json.loads(body) if body else None
            calls.append((method, path, self.body, headers))

        def getresponse(self):
            nonlocal checkpoint
            status = 200
            if self.path == "/v1/sessions":
                payload = {"access_token": "memory-only"}
            elif self.path.endswith("/lifecycle"):
                payload = {"checkpoint": checkpoint}
            elif expire and len(calls) == 5:
                status, payload = 401, {}
            else:
                assert self.body["expected_event_id"] == (checkpoint["id"] if checkpoint else None)
                i = sum(x[1].endswith("/advance") for x in calls) - 1
                checkpoint = {
                    "id": str(uuid4()),
                    "payload": {
                        "phase": LIFECYCLE_PHASES[i],
                        "execution": {"executed": True} if i == 4 else None,
                    },
                }
                payload = checkpoint

            class Response:
                def read(self, limit):
                    return json.dumps(payload).encode()

            response = Response()
            response.status = status
            return response

        def close(self):
            pass

    args = {
        "port": 8000,
        "tenant_id": str(uuid4()),
        "email": "local@example.test",
        "password": "test-only",
        "lifecycle": True,
        "connection": Connection,
        "pause": lambda _: None,
    }
    if expire:
        with pytest.raises(RuntimeError, match="Local worker stopped"):
            work_local(**args)
        assert len(calls) == 5
    else:
        result = work_local(**args)
        assert result["completed"] == 1 and result["idle_polls"] == 0
        assert len(calls) == 10
    assert all(x[3].get("Authorization") == "Bearer memory-only" for x in calls[1:])


def test_evolution_audits_actual_reviewed_capacity_promotion_and_restoration(case):
    client, headers, _ = case
    f, r = headers["founder"], headers["reviewer"]
    proposal = post(client, BASE + "/evolution/diagnostics", f, {"operation_key": "quality"})
    assert proposal["payload"]["architecture_measurement"]["passed"]
    review(client, f, r, proposal)
    intents = []
    for value in (2, 3, 2):
        item = post(
            client,
            BASE + "/intents",
            f,
            {
                "operation": "capacity",
                "parameters": {
                    "scope_kind": "company",
                    "scope_id": None,
                    "max_running": value,
                    "rationale": "Explicit independently reviewed control",
                },
            },
        )
        decide(client, r, item["approval_id"])
        post(client, BASE + "/intents/" + item["id"] + "/apply", f)
        intents.append(item["id"])
    params = {
        "proposal_id": proposal["id"],
        "baseline_intent_id": intents[0],
        "candidate_intent_id": intents[1],
        "rollback_intent_id": intents[2],
        "operation_key": "audit",
    }
    result = post(client, BASE + "/evolution/policy-audit", f, params)["payload"]
    assert result["baseline_restored"] and not result["evolution_applied_change"]
    assert len(result["actual_policy_applications"]) == 3
    post(
        client,
        BASE + "/evolution/policy-audit",
        f,
        {**params, "rollback_intent_id": str(uuid4())},
        expected=403,
    )
    post(
        client,
        BASE + "/evolution/policy-audit",
        f,
        {**params, "baseline_intent_id": intents[2], "rollback_intent_id": intents[0]},
        expected=400,
    )


def test_continuous_worker_two_real_signed_api_cycles_sync_and_replay_safety(case):
    import json
    from ago.local_ops import work_local

    client, headers, context = case
    f, r = headers["founder"], headers["reviewer"]
    worker = employee(client, f, department(client, f))
    task = _approved_task(client, f, r, worker)
    _enqueue(client, f, task, 10)

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == "127.0.0.1"

        def request(self, method, path, body, headers):
            self.response = client.request(
                method, path, json=json.loads(body) if body else None, headers=headers
            )

        def getresponse(self):
            actual = self.response

            class Response:
                status = actual.status_code

                def read(self, limit):
                    return actual.content

            return Response()

        def close(self):
            pass

    result = work_local(
        port=8000,
        tenant_id=context["tenant"],
        email="m7founder@example.test",
        password="founder-test-password-123",
        iterations=2,
        connection=Connection,
        pause=lambda _: None,
        lifecycle=True,
    )
    assert result["completed"] == 1 and result["idle_polls"] == 1
    state = client.get(BASE + "/lifecycle", headers=f).json()["checkpoint"]
    assert state["payload"]["sequence"] == 16
    snapshots = client.get(BASE + "/evidence?kind=twin_state", headers=f).json()
    assert (
        len(snapshots) == 2
        and snapshots[0]["payload"]["previous_snapshot_id"] == snapshots[1]["id"]
    )
    assert len(client.get("/v1/agents/runs", headers=f).json()) == 1


def test_lifecycle_coordinate_failure_rolls_back_lease_and_checkpoint(case):
    from ago.enterprise_store import EnterpriseOperationsStore
    from ago.security import Principal

    client, headers, context = case
    f, r = headers["founder"], headers["reviewer"]
    worker = employee(client, f, department(client, f))
    task = _approved_task(client, f, r, worker)
    _enqueue(client, f, task, 20)
    cursor = None
    for i in range(4):
        cursor = post(
            client,
            BASE + "/lifecycle/advance",
            f,
            {"operation_key": "before-" + str(i), "expected_event_id": cursor},
        )["id"]
    store = EnterpriseOperationsStore(context["db"])
    actor = Principal(context["founder_id"], context["tenant"], ("founder",))

    def fail(**kwargs):
        raise RuntimeError("Disposable offline crash before any external effect")

    with pytest.raises(RuntimeError, match="offline crash"):
        store.advance_lifecycle(
            actor=actor,
            operation_key="crash",
            expected_event_id=cursor,
            execute_one=True,
            runner=fail,
        )
    assert client.get(BASE + "/lifecycle", headers=f).json()["checkpoint"]["id"] == cursor
    queue = client.get(BASE + "/work-queue", headers=f).json()
    assert queue[0]["lease_state"] is None
    result = post(
        client,
        BASE + "/lifecycle/advance",
        f,
        {"operation_key": "crash", "expected_event_id": cursor, "execute_one": True},
    )
    assert result["payload"]["execution"]["executed"]


def test_runtime_forecast_deadline_later_qa_and_exact_retry(case):
    from test_enterprise_completion_batch import _finish_reviewed

    client, headers, _ = case
    f, r = headers["founder"], headers["reviewer"]
    worker = employee(client, f, department(client, f))
    _finish_reviewed(client, f, r, worker)
    task = _approved_task(client, f, r, worker)
    now = datetime.now(timezone.utc)
    post(
        client,
        "/v1/operations/calendar",
        f,
        {
            "title": "Observed task deadline",
            "task_id": task,
            "operation_key": "deadline",
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
        },
    )
    snapshot = post(client, BASE + "/twin/state", f, {"operation_key": "runtime-state"})
    params = {
        "operation_key": "runtime-forecast",
        "snapshot_id": snapshot["id"],
        "task_ids": [task],
        "horizon_end": (now + timedelta(days=1)).isoformat(),
    }
    forecast = post(client, BASE + "/twin/forecast", f, params)
    assert forecast["payload"]["runtime"]["training_samples"] == 1
    assert forecast["payload"]["runtime"]["tasks"][0]["deadline"]
    post(client, "/v1/agents/tasks/" + task + "/run", f)
    post(
        client,
        "/v1/tasks/" + task + "/review",
        r,
        {"verdict": "pass", "evidence": "Actual later runtime/deadline QA"},
    )
    assert post(client, BASE + "/twin/forecast", f, params)["idempotent"]
    observed = post(
        client,
        BASE + "/twin/forecasts/" + forecast["id"] + "/calibrate",
        f,
        {"operation_key": "runtime-actual"},
    )["payload"]
    assert observed["runtime"]["observed_samples"] == 1
    assert observed["runtime"]["pending_samples"] == 0
    assert observed["runtime"]["deadline_observed_samples"] == 1
    assert observed["runtime"]["mean_absolute_error_seconds"] is not None
    assert not observed["runtime"]["accuracy_certified"]


def test_continuous_evidence_does_not_hide_pending_financial_review(case):
    client, headers, _ = case
    f = headers["founder"]
    item = document(client, f, cost(client, f, "source"), "invoice", "source-document")
    for i in range(12):
        post(client, BASE + "/twin/state", f, {"operation_key": "capture-" + str(i)})
    dashboard = client.get(BASE + "/evidence", headers=f).json()
    assert sum(x["kind"] == "twin_state" for x in dashboard) == 1
    assert any(x["id"] == item["id"] for x in dashboard)
    assert len(client.get(BASE + "/evidence?kind=twin_state", headers=f).json()) == 12
