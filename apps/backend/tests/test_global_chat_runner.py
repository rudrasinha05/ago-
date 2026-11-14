"""Local Founder chat runner: bounded, browser-independent, no fabricated work.

Unit cases use fake localhost transports; real signed PostgreSQL, model-fencing
and CEO-to-specialist handoffs are covered in test_global_chat_accountability.
"""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest

SCRIPTS=Path(__file__).resolve().parents[3]/"scripts"
sys.path.insert(0,str(SCRIPTS))
spec=spec_from_file_location("ago_global_chat_runner",SCRIPTS/"ago_global_chat_runner.py")
runner=module_from_spec(spec)
spec.loader.exec_module(runner)

CEO=str(uuid4())
WORKER=str(uuid4())
OTHER=str(uuid4())


def msg(mid,*,ceo=CEO,targets=(CEO,),acks=(),state="awaiting_ack"):
    return {"message_id":mid,"accountable_ceo_id":ceo,"state":state,
            "work_items":[{"assignee_id":i,"assignee_name":i[:5],
                           "assignee_kind":"ai",
                           "ack_message_id":mid+100 if i in acks else None}
                          for i in targets]}


def test_bounded_readonly_preview_has_zero_model_calls_and_explicit_confirm():
    calls=[]
    def transport(method,path,body=None):
        calls.append((method,path))
        return {"roles":["founder"]} if path=="/v1/console/me" else [
            msg(15,targets=(CEO,WORKER),acks=(CEO,)),msg(10,state="blocked_no_ceo")]
    result=runner.run_session(transport)
    assert result=={"status":"read_only_preview","pending_ai_replies":1,
                    "replies_recorded":0,"automatic_replay":False,
                    "started_at_boot":False}
    assert all(m=="GET" for m,_ in calls)
    with pytest.raises(PermissionError):
        runner.run_session(transport,apply=True)
    with pytest.raises(PermissionError):
        runner.run_session(transport,confirmation=runner.CONFIRM)
    with pytest.raises(ValueError):
        runner.run_session(transport,interval=0)
    with pytest.raises(PermissionError):
        runner.run_session(lambda *_:{"roles":["reviewer"]})


def test_runner_receives_ceo_reply_then_delegated_worker_no_browser():
    orders=[msg(10,targets=(CEO,))]
    seen=[]
    def transport(method,path,body=None):
        if path=="/v1/console/me":
            return {"roles":["founder"]}
        if method=="GET":
            return orders
        assert path.startswith("/v1/organization/company/chat/orders/10/respond")
        who=body["employee_id"]
        seen.append(who)
        if who==CEO:
            orders[0]=msg(10,targets=(CEO,WORKER),acks=(CEO,))
            return {"status":"responded","ai_acknowledged":True,
                    "delegated_employee_id":WORKER}
        assert who==WORKER
        orders[0]=msg(10,targets=(CEO,WORKER),acks=(CEO,WORKER))
        return {"status":"responded","ai_acknowledged":True}
    report=[]
    done=runner.run_session(transport,apply=True,confirmation=runner.CONFIRM,
                            report=report.append,clock=lambda:1,pause=lambda _:None)
    assert seen==[CEO,WORKER]
    assert done["status"]=="queue_acknowledged_not_executed"
    assert done["replies_recorded"]==2
    assert done["automatic_replay"] is False
    assert done["started_at_boot"] is False
    assert [r["employee_id"] for r in report]==seen


def test_runner_stops_on_revoked_token_without_cached_password_relogin():
    calls=[]
    def request(method,path,body=None):
        calls.append((method,path))
        if path=="/v1/console/me":
            return {"roles":["founder"]}
        if method=="GET":
            return [msg(10)]
        raise runner.SessionExpired()
    result=runner.run_session(request,apply=True,confirmation=runner.CONFIRM,
                              clock=lambda:0,pause=lambda _:None)
    assert result["status"]=="session_expired"
    assert result["replies_recorded"]==0
    assert calls.count(("POST","/v1/organization/company/chat/orders/10/respond"))==1


def test_runner_never_claims_success_after_uncertain_http_answer():
    calls=[]
    def request(method,path,body=None):
        if path=="/v1/console/me":
            return {"roles":["founder"]}
        if method=="GET":
            return [msg(10)]
        calls.append(path)
        raise URLError("Lost POST answer; outcome may be recorded")
    result=runner.run_session(request,apply=True,confirmation=runner.CONFIRM,
                              clock=lambda:1,pause=lambda _:None)
    assert result["status"]=="server_unavailable"
    assert result["replies_recorded"]==0
    assert len(calls)==runner.MAX_LOST_ANSWERS


@pytest.mark.parametrize("result,expected",[
    ({"status":"local_model_disabled"},"founder_needed"),
    ({"status":"retry_limit"},"founder_needed"),
])
def test_worker_honors_model_gate_and_retry_budget(result,expected):
    def request(method,path,body=None):
        if path=="/v1/console/me":
            return {"roles":["founder"]}
        if method=="GET":
            return [msg(10)]
        return result
    outcome=runner.run_session(request,apply=True,confirmation=runner.CONFIRM,
                               clock=lambda:1,pause=lambda _:None)
    assert outcome["status"]==expected
    assert outcome["replies_recorded"]==0


def test_pending_priority_is_oldest_ceo_first_and_skips_human():
    orders=[msg(20,targets=(CEO,WORKER)),msg(10,targets=(CEO,WORKER))]
    orders[-1]["work_items"].append({"assignee_id":OTHER,"assignee_name":"human",
                                      "assignee_kind":"human","ack_message_id":None})
    assert list(runner.next_pending(orders))==[
        (10,CEO),(10,WORKER),(20,CEO),(20,WORKER)]


def test_runner_escalates_missing_ceo_instead_of_saying_orders_finished():
    def transport(method,path,body=None):
        if path=="/v1/console/me":
            return {"roles":["founder"]}
        if method=="GET":
            return [msg(20,state="blocked_no_ceo",targets=())]
        raise AssertionError("No AI model may run without appointed CEO")
    result=runner.run_session(transport,apply=True,confirmation=runner.CONFIRM,
                              clock=lambda:1,pause=lambda _:None)
    assert result["status"]=="founder_needed"
    assert result["blocked_without_ceo"]==1
    assert result["replies_recorded"]==0


@pytest.mark.parametrize("code", [400, 403, 409, 429, 500])
@pytest.mark.parametrize("failing_method", ["GET", "POST"])
def test_explicit_http_failure_is_terminal(code, failing_method):
    calls = []
    def request(method, path, body=None):
        calls.append((method, path))
        if path == "/v1/console/me":
            return {"roles": ["founder"]}
        if method == failing_method:
            raise HTTPError(path, code, "denied", {}, None)
        return [msg(10)]
    with pytest.raises(HTTPError) as failure:
        runner.run_session(request, apply=True, confirmation=runner.CONFIRM,
                           clock=lambda: 0, pause=lambda _: None)
    assert failure.value.code == code
    assert len([m for m, p in calls if m == failing_method and p != "/v1/console/me"]) == 1


@pytest.mark.parametrize("state", ["already_processing", "already_replied"])
def test_stale_queue_cannot_bypass_request_budget(state):
    calls = []
    def request(method, path, body=None):
        if path == "/v1/console/me":
            return {"roles": ["founder"]}
        if method == "GET":
            return [msg(10)]
        calls.append(path)
        assert len(calls) <= 4, "Runner ignored its request budget"
        return {"status": state}
    result = runner.run_session(request, apply=True, confirmation=runner.CONFIRM,
                                max_replies=4, clock=lambda: 0, pause=lambda _: None)
    assert result["status"] == "limit_reached"
    assert result["requests"] == 4
    assert result["replies_recorded"] == 0


def test_queue_priority_does_not_depend_on_inbox_display_order():
    assert list(runner.next_pending([msg(10), msg(30), msg(20)])) == [
        (10, CEO), (20, CEO), (30, CEO)]
