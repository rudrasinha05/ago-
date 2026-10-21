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
    rows=[
        {"id":yes,"action":"internal:brief","status":"waiting_approval"},
        {"id":str(uuid4()),"action":"project:plan","status":"waiting_approval"},
        {"id":no,"action":"internal:brief","status":"running"},
        {"id":yes,"action":"internal:brief","status":"waiting_approval"},
    ]
    calls=[]
    def dispatch(task_id):
        calls.append(task_id)
        return {"task_id":task_id,"status":"completed"}
    preview=module.batch(rows,dispatch,limit=10,apply=False,confirm=None)
    assert preview["eligible_task_ids"]==[yes]
    assert preview["completed_task_ids"]==[]
    assert calls==[]
    with pytest.raises(PermissionError):
        module.batch(rows,dispatch,limit=2,apply=True,confirm=None)
    with pytest.raises(ValueError):
        module.batch(rows,dispatch,limit=99,apply=False,confirm=None)
    applied=module.batch(rows,dispatch,limit=2,apply=True,confirm=module.CONFIRM)
    assert applied["completed_task_ids"]==[yes]
    assert calls==[yes]
    assert applied["external_actions_authorized"] is False


def test_dispatch_never_retries_when_handler_rejects_or_result_mismatches():
    task_id=str(uuid4())
    rows=[{"id":task_id,"action":"internal:brief","status":"waiting_approval"}]
    invocations=[]
    def failed(task):
        invocations.append(task)
        raise RuntimeError("Unknown execution outcome")
    with pytest.raises(RuntimeError):
        module.batch(rows,failed,limit=1,apply=True,confirm=module.CONFIRM)
    assert invocations==[task_id]
    with pytest.raises(RuntimeError):
        module.batch(rows,lambda _:{"task_id":str(uuid4()),"status":"completed"},
                     limit=1,apply=True,confirm=module.CONFIRM)
