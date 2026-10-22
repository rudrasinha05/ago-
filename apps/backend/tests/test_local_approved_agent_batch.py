"""Approved internal tasks only; real API owns execution permissions."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest

SCRIPT=Path(__file__).resolve().parents[3]/"scripts"/"local_approved_agent_batch.py"
SPEC=spec_from_file_location("ago_local_approved_batch",SCRIPT)
module=module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_rejects_remote_endpoints_and_malformed_uris():
    for url in ("https://127.0.0.1:8000","http://example.org:8000",
                "http://127.0.0.1:8000/admin","http://user:secret@localhost:8000",
                "http://localhost:8000?access_token=secret",
                "http://127.0.0.1:80"):
        with pytest.raises(ValueError):
            module.local_url(url)
    assert module.local_url("http://127.0.0.1:8000")=="http://127.0.0.1:8000"


def test_no_dispatch_unless_exact_confirmed_founder_batch():
    yes=str(uuid4())
    no=str(uuid4())
    approvals=[{"id":"a","status":"approved","action":"internal:brief"}]
    rows=[
        {"id":yes,"action":"internal:brief","status":"waiting_approval","approval_id":"a"},
        {"id":str(uuid4()),"action":"project:plan","status":"waiting_approval"},
        {"id":no,"action":"internal:brief","status":"running"},
        {"id":yes,"action":"internal:brief","status":"waiting_approval","approval_id":"a"},
    ]
    calls=[]
    def dispatch(task_id):
        calls.append(task_id)
        return {"task_id":task_id,"status":"completed"}
    preview=module.batch(rows,approvals,dispatch,limit=10,apply=False,confirm=None)
    assert preview["eligible_task_ids"]==[yes]
    assert preview["completed_task_ids"]==[]
    assert calls==[]
    with pytest.raises(PermissionError):
        module.batch(rows,approvals,dispatch,limit=2,apply=True,confirm=None)
    with pytest.raises(ValueError):
        module.batch(rows,approvals,dispatch,limit=99,apply=False,confirm=None)
    applied=module.batch(rows,approvals,dispatch,limit=2,apply=True,confirm=module.CONFIRM)
    assert applied["completed_task_ids"]==[yes]
    assert calls==[yes]
    assert applied["external_actions_authorized"] is False


def test_dispatch_never_retries_when_handler_rejects_or_result_mismatches():
    task_id=str(uuid4())
    rows=[{"id":task_id,"action":"internal:brief","status":"waiting_approval","approval_id":"a"}]
    approvals=[{"id":"a","status":"approved","action":"internal:brief"}]
    invocations=[]
    def failed(task):
        invocations.append(task)
        raise RuntimeError("Unknown execution outcome")
    with pytest.raises(RuntimeError):
        module.batch(rows,approvals,failed,limit=1,apply=True,confirm=module.CONFIRM)
    assert invocations==[task_id]
    with pytest.raises(RuntimeError):
        module.batch(rows,approvals,lambda _:{"task_id":str(uuid4()),"status":"completed"},
                     limit=1,apply=True,confirm=module.CONFIRM)


def test_batch_fails_closed_without_matching_independent_approval():
    task_id=str(uuid4())
    rows=[{"id":task_id,"action":"internal:brief","status":"waiting_approval","approval_id":"a"}]
    calls=[]
    def dispatch(task):
        calls.append(task)
        return {"task_id":task,"status":"completed"}
    for approvals in ([],[{"id":"a","status":"pending","action":"internal:brief"}],
                      [{"id":"a","status":"approved","action":"research:brief"}],
                      [{"id":"b","status":"approved","action":"internal:brief"}]):
        result=module.batch(rows,approvals,dispatch,limit=3,apply=True,confirm=module.CONFIRM)
        assert result["eligible_task_ids"]==[]
        assert result["completed_task_ids"]==[]
    assert calls==[]

def test_local_batch_separates_fast_metadata_reads_and_long_bounded_agent_runs():
    assert module.request_timeout("GET","/v1/organization/company/activity")==15
    assert module.request_timeout("GET","/v1/organization/company/approvals")==15
    assert module.request_timeout("POST","/v1/agents/tasks/abc/run")==270
    assert module.request_timeout("POST","/v1/console/logout")==15
