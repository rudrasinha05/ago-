"""Local bounded queue worker, durable no-replay and real PostgreSQL integration."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from test_m7_http_postgres import case as case

DIR=Path(__file__).resolve().parents[3]/"scripts"
sys.path.insert(0,str(DIR))
spec=spec_from_file_location("ago_approved_queue_worker",DIR/"ago_approved_queue_worker.py")
worker=module_from_spec(spec)
spec.loader.exec_module(worker)
from local_approved_agent_batch import DurableAttemptJournal, CONFIRM


def item(**changes):
    return {"id":str(uuid4()),"task_id":str(uuid4()),
            "task_status":"waiting_approval","task_action":"internal:brief",
            "lease_state":None,"requires_reconciliation":False,**changes}


def lease(row):
    return {"queue_id":row["id"],"task_id":row["task_id"],
            "lease_id":str(uuid4()),"executed":False,
            "manual_authorized_execution_required":True,
            "replay_of_side_effects":False}


def receipt(row):
    return {"queue_id":row["id"],"executed":True,"external_effects":False,
            "independent_qa_required":True,
            "run":{"id":str(uuid4()),"task_id":row["task_id"],
                   "status":"completed","delivery_status":"completed"}}


def test_preview_is_read_only_without_journal_or_execution(tmp_path):
    row=item()
    requests=[]
    def request(method,path,body=None):
        requests.append(method)
        if path=="/v1/console/me":return {"roles":["founder"]}
        if path==worker.QUEUE:return [row]
        raise AssertionError(path)
    result=worker.run_session(request)
    assert result["candidate_ids"]==[row["id"]]
    assert result["tasks_executed"]==0
    assert requests==["GET","GET"]
    assert list(tmp_path.iterdir())==[]


def test_founder_explicitly_runs_bounded_two_approved_tasks(tmp_path):
    first,second=item(),item()
    rows=[first,second]
    attempts=[]
    def request(method,path,body=None):
        attempts.append(path)
        if path=="/v1/console/me":return {"roles":["founder"]}
        if path==worker.QUEUE:return rows
        if path==worker.OFFLINE:return lease(rows[0])
        for r in (first,second):
            if path==worker.QUEUE+"/"+r["id"]+"/run":
                rows.remove(r)
                return receipt(r)
        raise AssertionError(path)
    journal=DurableAttemptJournal(tmp_path/"attempts")
    result=worker.run_session(request,apply=True,confirmation=CONFIRM,
                              journal=journal,max_tasks=2)
    assert result["completed_task_ids"]==[first["task_id"],second["task_id"]]
    assert result["automatic_replay"] is False
    assert result["independent_qa_required"] is True
    assert journal.has_claim(first["task_id"]) and journal.has_claim(second["task_id"])
    assert sum(path.endswith("/run") for path in attempts)==2


def test_crash_keeps_durable_attempt_and_does_not_replay_after_restart(tmp_path):
    row=item()
    journal=DurableAttemptJournal(tmp_path/"attempts")
    calls=[]
    def request(method,path,body=None):
        calls.append(path)
        if path=="/v1/console/me":return {"roles":["founder"]}
        if path==worker.QUEUE:return [row]
        if path==worker.OFFLINE:return lease(row)
        if path.endswith("/run"):raise OSError("uncertain transport")
        raise AssertionError(path)
    with pytest.raises(OSError):
        worker.run_session(request,apply=True,confirmation=CONFIRM,journal=journal)
    assert journal.has_claim(row["task_id"])
    again=worker.run_session(request,apply=True,confirmation=CONFIRM,journal=journal)
    assert again["status"]=="reconciliation_required"
    assert calls.count(worker.OFFLINE)==1
    assert calls.count(worker.QUEUE+"/"+row["id"]+"/run")==1


def test_expired_lease_requires_reconcile_but_other_task_can_run(tmp_path):
    expired=item(lease_state="leased",requires_reconciliation=True)
    available=item()
    rows=[expired,available]
    def request(method,path,body=None):
        if path=="/v1/console/me":return {"roles":["founder"]}
        if path==worker.QUEUE:return rows
        if path==worker.OFFLINE:return lease(available)
        if path==worker.QUEUE+"/"+available["id"]+"/run":
            rows.remove(available)
            return receipt(available)
        raise AssertionError(path)
    preview=worker.run_session(request)
    assert preview["reconciliation_ids"]==[expired["id"]]
    result=worker.run_session(request,apply=True,confirmation=CONFIRM,
                              journal=DurableAttemptJournal(tmp_path/"claims"),
                              max_tasks=1)
    assert result["completed_task_ids"]==[available["task_id"]]


def test_untrusted_claim_and_false_success_fail_closed(tmp_path):
    row=item()
    called=[]
    def spoof(method,path,body=None):
        called.append(path)
        if path=="/v1/console/me":return {"roles":["founder"]}
        if path==worker.QUEUE:return [row]
        if path==worker.OFFLINE:return lease(item())
        raise AssertionError("Task run MUST NOT be invoked")
    with pytest.raises(PermissionError):
        worker.run_session(spoof,apply=True,confirmation=CONFIRM,
                           journal=DurableAttemptJournal(tmp_path/"a"))
    assert all(not p.endswith("/run") for p in called)
    assert not worker.verify_run({**receipt(row),"independent_qa_required":False},
                                 row["id"],row["task_id"])


def test_founder_and_bounds_guard_before_network_side_effects(tmp_path):
    calls=[]
    def reviewer(method,path,body=None):
        calls.append(path)
        return {"roles":["reviewer"]}
    with pytest.raises(PermissionError):
        worker.run_session(reviewer,apply=True,confirmation=None,
                           journal=DurableAttemptJournal(tmp_path))
    with pytest.raises(PermissionError):
        worker.run_session(reviewer)
    for opts in ({"minutes":61},{"max_tasks":11},{"interval":1},
                 {"lease_seconds":3600}):
        with pytest.raises(ValueError):
            worker.run_session(reviewer,**opts)
    assert calls==["/v1/console/me"]


def test_actual_postgres_queue_worker_executes_only_one_approved_packet(case,tmp_path):
    from test_enterprise_capacity_21 import _approved_task
    from test_enterprise_durable_queue_21 import _enqueue
    from test_enterprise_http_21_27 import department, employee
    client,headers,info=case
    founder,reviewer=headers["founder"],headers["reviewer"]
    agent=employee(client,founder,department(client,founder))
    task=_approved_task(client,founder,reviewer,agent)
    queued=_enqueue(client,founder,task,50)
    def request(method,path,body=None):
        response=client.request(method,path,headers=founder,json=body)
        assert response.status_code==200,(path,response.status_code,response.text)
        return response.json()
    journal=DurableAttemptJournal(tmp_path/"claims")
    result=worker.run_session(request,apply=True,confirmation=CONFIRM,
                              journal=journal,max_tasks=1)
    assert result["completed_task_ids"]==[task]
    assert result["external_actions_authorized"] is False
    assert journal.has_claim(task)
    record=next(x for x in request("GET",worker.QUEUE) if x["id"]==queued["id"])
    assert record["task_status"]=="completed"
    assert record["lease_state"]=="reconciled"
    row=info["db"].execute(
        "SELECT count(*) AS total FROM ago_agent_runs WHERE tenant_id=%s AND task_id=%s",
        (info["tenant"],task)).fetchone()
    assert row["total"]==1
