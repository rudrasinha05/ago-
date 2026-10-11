"""Actual local integration, independent evidence and nonfabrication acceptance."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ago.enterprise_domains import calibrate_quality, finance_analysis, forecast_quality
from test_enterprise_capacity_21 import _approved_task
from test_enterprise_durable_queue_21 import _enqueue
from test_enterprise_http_21_27 import department, employee
from test_m7_http_postgres import case as case, decide, post

BASE = "/v1/operations/enterprise"


def _finish_reviewed(client, founder, reviewer, worker):
    task = _approved_task(client, founder, reviewer, worker)
    post(client, "/v1/agents/tasks/"+task+"/run", founder)
    post(client, "/v1/tasks/"+task+"/review", reviewer,
         {"verdict": "pass", "evidence": "Independent review of actual offline result"})
    return task


def test_frozen_cohort_metrics_unknowns_and_foreign_outcomes():
    unknown = forecast_quality([], [{"id": "next"}])
    assert unknown["pass_probability"] is None
    assert calibrate_quality(unknown, [])['calibration_status'] == "awaiting_observations_or_training"
    prediction = forecast_quality(
        [{"status": "completed", "verdict": "pass"}, {"status": "failed", "verdict": "fail"}],
        [{"id": "future"}])
    assert prediction["pass_probability"] == .5
    assert prediction["probability_interval_95"][0] < .5 < prediction["probability_interval_95"][1]
    actual = calibrate_quality(prediction, [{"id": "future", "status": "completed", "verdict": "pass"}])
    assert actual["brier_score"] == .25 and actual["complete"]
    assert actual["calibration_status"] == "held_out_measured" and not actual["accuracy_certified"]
    with pytest.raises(ValueError, match="outside"):
        calibrate_quality(prediction, [{"id": "other"}])
    with pytest.raises(ValueError, match="Duplicate"):
        calibrate_quality(prediction, [{"id": "future"}, {"id": "future"}])


def test_finance_currency_and_operator_verification_boundaries():
    rows = [{"currency": "INR", "category": "model", "observed_amount": "100"},
            {"currency": "INR", "category": "revenue", "observed_amount": "200"}]
    result = finance_analysis(rows, currency="INR", baseline_revenue="50",
                              alternative_net="120", assumptions="Same period; actual claimed sources")
    assert result["incremental_roi_pct"] == "50" and result["opportunity_cost"] == "20"
    assert not result["financial_settlement"]
    assert result["evidence_state"] == "operator_claims_not_provider_authenticated"
    with pytest.raises(ValueError, match="single-currency"):
        finance_analysis([*rows, {"currency": "USD"}], currency="INR",
                         baseline_revenue="0", alternative_net="0", assumptions="Not comparable")


def test_owned_offline_execution_no_replay_and_qa_preserved(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    worker = employee(client, founder, department(client, founder))
    task = _approved_task(client, founder, reviewer, worker)
    item = _enqueue(client, founder, task, 50)
    lease = post(client, BASE+"/work-queue/offline-claim", founder, {"lease_seconds": 600})
    path = BASE+"/work-queue/"+item["id"]+"/run"
    post(client, path, reviewer, {"lease_id": lease["lease_id"]}, expected=403)
    post(client, path, founder, {"lease_id": str(uuid4())}, expected=403)
    result = post(client, path, founder, {"lease_id": lease["lease_id"]})
    assert result["executed"] and result["independent_qa_required"] and not result["external_effects"]
    post(client, path, founder, {"lease_id": lease["lease_id"]}, expected=403)
    assert post(client, BASE+"/work-queue/offline-claim", founder, {"lease_seconds": 600})["queue_id"] is None


def test_capacity_reservations_and_restart_before_execution(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    worker = employee(client, founder, department(client, founder))
    for _ in range(2):
        _enqueue(client, founder, _approved_task(client, founder, reviewer, worker), 20)
    lease = post(client, BASE+"/work-queue/offline-claim", founder, {"lease_seconds": 600})
    assert lease["queue_id"]
    assert post(client, BASE+"/work-queue/offline-claim", founder, {"lease_seconds": 600})["queue_id"] is None
    post(client, BASE+"/work-queue/"+lease["queue_id"]+"/release", founder,
         {"status": "released", "explanation": "Stopped before execution; no side effect"})
    again = post(client, BASE+"/work-queue/offline-claim", founder, {"lease_seconds": 600})
    assert again["queue_id"] == lease["queue_id"] and again["lease_id"] != lease["lease_id"]


def test_exact_intent_survives_reload_and_blocks_substitution_and_self_review(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    params = {"scope_kind": "company", "scope_id": None, "max_running": 3,
              "rationale": "Exact recorded local capacity"}
    request = post(client, BASE+"/intents", founder, {"operation": "capacity", "parameters": params})
    path = BASE+"/intents/"+request["id"]+"/apply"
    post(client, path, founder, expected=403)
    post(client, "/v1/governance/approvals/"+request["approval_id"]+"/decision", founder,
         {"approve": True, "reason": "Forbidden self-review"}, expected=403)
    decide(client, reviewer, request["approval_id"])
    post(client, BASE+"/capacity", founder,
         {**params, "rationale": "Substituted", "approval_id": request["approval_id"]}, expected=403)
    captured = client.get(BASE+"/evidence?kind=intent", headers=reviewer).json()[0]
    assert captured["payload"]["parameters"]["max_running"] == 3
    assert post(client, path, founder)["result"]["max_running"] == 3
    assert post(client, path, founder)["idempotent"]
    post(client, BASE+"/intents", founder, {"operation": "capacity", "parameters": {
        **params, "authorized": True}}, expected=400)


def test_evidence_review_immutability_and_tenant_isolation(case):
    client, headers, context = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    snapshot = post(client, BASE+"/cycle", founder, {"operation_key": "cycle-v1"})
    assert not snapshot["payload"]["authority_changed"]
    request = post(client, BASE+"/evidence/"+snapshot["id"]+"/approval", founder)
    details = client.get(BASE+"/approval-details/"+request["approval_id"], headers=reviewer).json()
    assert details["details"]["digest"] == snapshot["digest"]
    path = BASE+"/evidence/"+snapshot["id"]+"/review"
    post(client, path, founder, {"approval_id": request["approval_id"]}, expected=403)
    decide(client, reviewer, request["approval_id"])
    result = post(client, path, founder, {"approval_id": request["approval_id"]})
    assert result["reviewed"] and not result["authority_granted"] and not result["provider_authenticated"]
    assert client.get(BASE+"/evidence").status_code == 401
    post(client, BASE+"/evidence/"+str(uuid4())+"/approval", founder, expected=404)
    with pytest.raises(Exception, match="append-only"):
        with context["db"].transaction():
            context["db"].execute("UPDATE ago_enterprise_evidence SET digest=%s WHERE id=%s",
                                  ("0"*64, snapshot["id"]))


def test_competence_and_evolution_read_actual_qa_sources(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    worker = employee(client, founder, department(client, founder))
    before = post(client, BASE+"/agents/"+worker+"/assessment", founder, {"operation_key": "before"})["payload"]
    assert before["sample_count"] == 0 and before["knowledge_level"] == "unknown"
    first = _finish_reviewed(client, founder, reviewer, worker)
    second = _finish_reviewed(client, founder, reviewer, worker)
    measured = post(client, BASE+"/agents/"+worker+"/assessment", founder, {"operation_key": "after"})["payload"]
    assert measured["sample_count"] == 2 and not measured["authority_granted"]
    assert measured["action_assessments"]["internal:brief"]["passed"] == 2
    params = {"operation_key": "measured", "baseline_task_ids": [first], "candidate_task_ids": [second],
              "hypothesis": "Compare observed internal QA", "rollback_plan": "Retain original approved workflow"}
    compared = post(client, BASE+"/evolution/experiment", founder, params)["payload"]
    assert compared["pass_rate_delta"] == 0 and not compared["applied"]
    post(client, BASE+"/evolution/experiment", founder, {**params, "candidate_task_ids": [first]}, expected=400)
    diagnostics = post(client, BASE+"/evolution/diagnostics", founder, {"operation_key": "diagnostic"})["payload"]
    assert diagnostics["grouped_observations"]["prompt_or_handler:internal:brief"]["reviewed"] == 2


def test_twin_held_out_outcomes_and_private_calendar_exclusion(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    worker = employee(client, founder, department(client, founder))
    training = _finish_reviewed(client, founder, reviewer, worker)
    future = _approved_task(client, founder, reviewer, worker)
    now = datetime.now(timezone.utc)
    event = post(client, "/v1/operations/calendar", founder, {"title": "Private operator calendar", "visibility": "private",
        "operation_key": str(uuid4()), "starts_at": now.isoformat(), "ends_at": (now+timedelta(hours=1)).isoformat()})
    snapshot = post(client, BASE+"/twin/state", founder, {"operation_key": "state-v1"})
    assert snapshot["payload"]["departments"] and snapshot["payload"]["employees"]
    assert next(x for x in snapshot["payload"]["employees"] if str(x["id"]) == worker)["availability"] == "available"
    assert snapshot["payload"]["source_limits"]["calendar"] == 1000
    assert not any(str(x["id"]) == event["id"] for x in snapshot["payload"]["calendar"])
    params = {"operation_key": "forecast-v1", "snapshot_id": snapshot["id"], "task_ids": [future],
              "horizon_end": (now+timedelta(days=1)).isoformat()}
    forecast = post(client, BASE+"/twin/forecast", founder, params)
    assert forecast["payload"]["training_samples"] == 1
    post(client, BASE+"/twin/forecast", founder, {**params, "task_ids": [training]}, expected=403)
    path = BASE+"/twin/forecasts/"+forecast["id"]+"/calibrate"
    partial = post(client, path, founder, {"operation_key": "partial"})["payload"]
    assert partial["pending_samples"] == 1 and partial["brier_score"] is None
    post(client, "/v1/agents/tasks/"+future+"/run", founder)
    post(client, "/v1/tasks/"+future+"/review", reviewer, {"verdict": "pass", "evidence": "Held out later QA"})
    result = post(client, path, founder, {"operation_key": "actual"})["payload"]
    assert result["complete"] and result["brier_score"] == 0 and not result["accuracy_certified"]
    source = client.get(BASE+"/evidence?kind=twin_state", headers=founder).json()[0]
    assert next(t for t in source["payload"]["tasks"] if t["id"] == future)["status"] == "waiting_approval"


def test_finance_analysis_requires_same_tenant_deduplicated_records(case):
    client, headers, _ = case
    founder = headers["founder"]
    now = datetime.now(timezone.utc)
    ids = []
    for category, amount in (("model", "100"), ("revenue", "200")):
        row = post(client, BASE+"/costs", founder, {"operation_key": category, "category": category,
            "provider": "local-operator", "source_ref": "record:"+category, "amount": amount, "currency": "INR",
            "period_start": now.isoformat(), "period_end": (now+timedelta(days=1)).isoformat()})
        ids.append(row["id"])
    params = {"operation_key": "analysis", "cost_ids": ids, "currency": "INR",
              "baseline_revenue": "50", "alternative_net": "120", "assumptions": "Same observation period"}
    result = post(client, BASE+"/finance/assessment", founder, params)
    assert result["payload"]["incremental_roi_pct"] == "50"
    assert post(client, BASE+"/finance/assessment", founder, params)["idempotent"]
    post(client, BASE+"/finance/assessment", founder, {**params, "cost_ids": [str(uuid4())]}, expected=404)
    post(client, BASE+"/finance/assessment", founder, {**params, "currency": "USD"}, expected=400)


def test_planning_rollup_uses_real_linked_qa_and_preserves_plan(case):
    from test_enterprise_plan_revisions_23 import _create
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    parent = _create(client, founder, reviewer)
    child = _create(client, founder, reviewer, parent=parent["id"], horizon="five_year", budget="100",
                    start=datetime.now(timezone.utc)-timedelta(days=2),
                    end=datetime.now(timezone.utc)+timedelta(days=350))
    worker = employee(client, founder, department(client, founder))
    task = _approved_task(client, founder, reviewer, worker)
    intent = post(client, BASE+"/intents", founder, {"operation":"link",
        "parameters":{"horizon_plan_id":child["id"],"task_id":task,"evidence_ref":"actual:strategic-link"}})
    decide(client, reviewer, intent["approval_id"])
    post(client, BASE+"/intents/"+intent["id"]+"/apply", founder)
    post(client, "/v1/agents/tasks/"+task+"/run", founder)
    post(client, "/v1/tasks/"+task+"/review", reviewer,
         {"verdict":"pass","evidence":"Actual reviewed offline planning task"})
    result = post(client, BASE+"/plans/"+parent["id"]+"/rollup", founder,
                  {"operation_key":str(uuid4())})["payload"]
    assert len(result["hierarchy"]) == 2 and result["qa_passed"] == 1
    assert result["task_lineage"][0]["task_id"] == task
    assert not result["automatically_approved"] and not result["tasks_executed"]
    assert result["proposal"]["base_revision"] == 1
    state=client.get(BASE+"/agents/"+worker+"/state",headers=founder).json()
    assert state["task_assignments"][0]["id"] == task
    assert state["horizon_assignments"][0]["horizon_plan_id"] == child["id"]


def test_local_offline_worker_stops_on_expired_session_and_never_reviews(monkeypatch):
    import json
    from ago.local_ops import work_local
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    requests=[]
    responses=iter([(200,{"access_token":"memory-only"}),
                    (200,{"queue_id":"q","lease_id":"l"}),
                    (200,{"status":"completed"}), (401,{"detail":"Expired"})])
    class Connection:
        def __init__(self,host,port,timeout):
            assert host == "127.0.0.1" and port == 8000 and timeout == 30
        def request(self,method,path,body,headers):
            requests.append((path,json.loads(body),headers))
        def getresponse(self):
            status,payload=next(responses)
            class Response:
                def read(self,limit): return json.dumps(payload).encode()
            result=Response()
            result.status=status
            return result
        def close(self): pass
    with pytest.raises(RuntimeError,match="Local worker stopped"):
        work_local(port=8000,tenant_id=str(uuid4()),email="test@example.test",
                   password="test-only",iterations=2,connection=Connection,pause=lambda _:None)
    assert [r[0].rsplit("/",1)[-1] for r in requests] == ["sessions","offline-claim","run","offline-claim"]
    assert requests[0][2].get("Authorization") is None
    assert all(r[2]["Authorization"] == "Bearer memory-only" for r in requests[1:])


@pytest.mark.parametrize("operation,parameters,target", [
    ("mode", {"target":"paused","expires_at":"2026-10-12T00:00:00Z","rationale":"Reviewed restriction"}, False),
    ("worker", {"state":"available","reason":"Reviewed resume"}, True),
    ("capacity", {"scope_kind":"company","max_running":2,"rationale":"Reviewed limits"}, False),
    ("plan", {"horizon":"lifetime","title":"Reviewed strategy","starts_at":"2026-10-10T00:00:00Z","ends_at":"2027-10-10T00:00:00Z","budget_ceiling":"100","evidence_ref":"actual:strategy"}, False),
    ("budget", {"scope_kind":"company","ceiling":"100","currency":"INR"}, False),
    ("consume", {"department_id":"11111111-1111-4111-8111-111111111111","evidence_ref":"reviewed:reuse"}, True),
    ("retire", {"target_state":"deprecated","reason":"Reviewed successor"}, True),
    ("link", {"horizon_plan_id":"11111111-1111-4111-8111-111111111111","task_id":"22222222-2222-4222-8222-222222222222","evidence_ref":"reviewed:lineage"}, False),
    ("resolve", {"outcome":"resolved","explanation":"Reviewed actual remediation"}, True),
])
def test_typed_saved_intent_whitelist_and_authority_injection(operation,parameters,target):
    from ago.api_operations import EnterpriseActionIntentInput, validate_action_intent
    identifier=str(uuid4()) if target else None
    request=EnterpriseActionIntentInput(operation=operation, parameters=parameters, target_id=identifier)
    action, normalized=validate_action_intent(request)
    assert action.startswith("enterprise:") and "approval_id" not in normalized
    for key in ("authorized", "approval_id", "applied"):
        forged=request.model_copy(update={"parameters":{**parameters,key:True}})
        with pytest.raises(ValueError):
            validate_action_intent(forged)



def test_pending_employee_evidence_can_be_reviewed_after_reload(case):
    client, headers, _ = case
    founder, reviewer=headers["founder"],headers["reviewer"]
    worker=employee(client,founder,department(client,founder))
    request=post(client,BASE+"/agents/"+worker+"/evidence/approval",founder,
        {"kind":"confidence","label":"Reviewed operational confidence","value_int":65,
         "evidence_ref":"actual:independent-observation","note":"Reported confidence remains uncalibrated"})
    rows=client.get(BASE+"/agents/review-intents",headers=reviewer).json()
    assert rows[0]["id"] == request["intent_id"] and rows[0]["value_int"] == 65
    assert rows[0]["applied_at"] is None
    decide(client,reviewer,request["approval_id"])
    post(client,BASE+"/agents/"+worker+"/evidence/"+request["intent_id"]+"/apply",founder,
         {"approval_id":request["approval_id"]})
    rows=client.get(BASE+"/agents/review-intents",headers=founder).json()
    assert rows[0]["applied_at"] and rows[0]["status"] == "approved"
    state=client.get(BASE+"/agents/"+worker+"/state",headers=founder).json()
    assert state["confidence"] == 65 and not state["confidence_calibrated"]
    assert client.get(BASE+"/agents/review-intents").status_code == 401


def test_actual_stored_asset_reuse_and_reviewed_sunset_impact(case):
    import base64
    from hashlib import sha256
    client, headers, _ = case
    founder,reviewer=headers["founder"],headers["reviewer"]
    dept=department(client,founder)
    content=b"Independently reviewed reusable local checklist"
    asset=post(client,BASE+"/marketplace",founder,
        {"department_id":dept,"name":"Actual reusable checklist","kind":"template",
         "version":"1.0.0","license_id":"internal-only","sha256_digest":sha256(content).hexdigest(),
         "manifest":{"dependencies":[]}})["id"]
    path=BASE+"/marketplace/"+asset
    post(client,path+"/payload",founder,{"content_type":"text/plain","content_base64":base64.b64encode(content).decode()})
    request=post(client,path+"/approval",founder)
    review_content=client.get(BASE+"/approval-details/"+request["approval_id"],headers=reviewer).json()
    assert base64.b64decode(review_content["details"]["content_base64"]) == content
    assert review_content["details"]["digest"] == sha256(content).hexdigest()
    assert client.get(BASE+"/approval-details/"+request["approval_id"]).status_code == 401
    decide(client,reviewer,request["approval_id"])
    post(client,path+"/publish",founder)
    assert client.get(path+"/payload",headers=reviewer).status_code == 403
    saved=client.get(path+"/payload",headers=founder).json()
    assert base64.b64decode(saved["content_base64"]) == content
    reuse=post(client,BASE+"/intents",founder,{"operation":"consume","target_id":asset,
        "parameters":{"department_id":dept,"evidence_ref":"actual:reviewed-use"}})
    decide(client,reviewer,reuse["approval_id"])
    post(client,BASE+"/intents/"+reuse["id"]+"/apply",founder)
    impact=client.get(path+"/impact",headers=founder).json()
    assert impact["consumer_departments"][0]["uses"] == 1 and not impact["automatic_migration"]
    sunset=post(client,BASE+"/intents",founder,{"operation":"retire","target_id":asset,
        "parameters":{"target_state":"deprecated","reason":"Reviewed sunset; successor requires reapproval"}})
    decide(client,reviewer,sunset["approval_id"])
    post(client,BASE+"/intents/"+sunset["id"]+"/apply",founder)
    assert client.get(path+"/impact",headers=reviewer).json()["reuse_blocked"]
