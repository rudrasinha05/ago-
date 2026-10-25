"""Approved internal tasks only; real API owns execution permissions."""
import subprocess
import sys
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
    assert module.request_timeout("POST","/v1/agents/tasks/abc/run")==480
    assert module.request_timeout("POST","/v1/console/logout")==15


def test_watch_only_performs_explicitly_confirmed_approved_work_and_never_replays():
    one,two=str(uuid4()),str(uuid4())
    state={"tasks":[{"id":one,"action":"internal:brief","status":"waiting_approval","approval_id":"a"},
                    {"id":two,"action":"internal:brief","status":"waiting_approval","approval_id":"b"}]}
    receipts=[{"id":"a","status":"approved","action":"internal:brief"},
              {"id":"b","status":"pending","action":"internal:brief"}]
    clock=[0.0]
    calls=[]
    def fetch():
        if clock[0]>=20:
            receipts[1]["status"]="approved"
        return state["tasks"],receipts
    def dispatch(task_id):
        calls.append(task_id)
        # Simulate delayed persistence: still waiting on next poll, must not rerun.
        return {"task_id":task_id,"status":"completed"}
    def pause(seconds):
        clock[0]+=seconds
    with pytest.raises(PermissionError):
        module.watch(fetch,dispatch,minutes=1,max_tasks=2,interval=10,confirm="no",clock=lambda:clock[0],pause=pause)
    assert calls==[]
    result=module.watch(fetch,dispatch,minutes=1,max_tasks=2,interval=10,
                        confirm=module.CONFIRM,clock=lambda:clock[0],pause=pause)
    assert result["completed_task_ids"]==[one,two]
    assert calls==[one,two]
    assert result["scheduled_service"] is False


def test_watch_fails_closed_on_unknown_outcome_and_limits():
    task_id=str(uuid4())
    row=[{"id":task_id,"action":"internal:brief","status":"waiting_approval","approval_id":"a"}]
    receipts=[{"id":"a","action":"internal:brief","status":"approved"}]
    calls=[]
    def bad_dispatch(value):
        calls.append(value)
        raise RuntimeError("timeout: outcome uncertain")
    with pytest.raises(RuntimeError):
        module.watch(lambda:(row,receipts),bad_dispatch,minutes=1,max_tasks=2,interval=10,
                     confirm=module.CONFIRM)
    assert calls==[task_id]
    with pytest.raises(ValueError):
        module.watch(lambda:(row,receipts),bad_dispatch,minutes=100,max_tasks=2,interval=10,confirm=module.CONFIRM)


def test_founder_signin_is_interactive_without_cli_secrets_or_persistence():
    from io import BytesIO
    import json
    class Response(BytesIO):
        pass
    recorded=[]
    def opener(request,timeout):
        recorded.append((request.full_url,request.get_method(),json.loads(request.data),timeout))
        return Response(b'{"access_token":"test-local-founder-token"}')
    tenant=str(uuid4())
    token=module.founder_login("http://127.0.0.1:8000",tenant,"founder@example.test","private-pass",opener=opener)
    assert token=="test-local-founder-token"
    assert recorded[0][0]=="http://127.0.0.1:8000/v1/sessions"
    assert recorded[0][1]=="POST" and recorded[0][3]==15
    assert recorded[0][2]["tenant_id"]==tenant
    with pytest.raises(ValueError):
        module.founder_login("http://external.org:8000",tenant,"founder@example.test","private",opener=opener)
    with pytest.raises(ValueError):
        module.founder_login("http://127.0.0.1:8000","not-uuid","founder@example.test","private",opener=opener)


def test_empty_batch_explains_exact_next_step_without_fake_execution():
    result=module.batch([],[],lambda _:None,limit=3,apply=False,confirm=None)
    assert result["eligible_task_ids"]==[]
    assert result["eligibility"]["recorded_tasks"]==0
    assert "First AI employee run" in result["eligibility"]["suggested_next_step"]


def test_batch_diagnostic_distinguishes_pending_and_real_model_tasks():
    p=str(uuid4())
    r=str(uuid4())
    tasks=[
      {"id":p,"action":"internal:brief","status":"proposed"},
      {"id":r,"action":"research:brief","status":"waiting_approval","approval_id":"x"},
    ]
    approvals=[{"id":"x","action":"research:brief","status":"approved"}]
    diagnostic=module.inspection_summary(tasks,approvals)
    assert diagnostic["internal_proposed_needing_request"]==1
    assert diagnostic["research_approved_for_separate_execution"]==1
    tasks[0]["status"]="waiting_approval"
    tasks[0]["approval_id"]="a"
    diagnostic=module.inspection_summary(tasks,approvals)
    assert diagnostic["internal_waiting_for_review"]==1
    approvals.append({"id":"a","action":"internal:brief","status":"approved"})
    diagnostic=module.inspection_summary(tasks,approvals)
    assert diagnostic["internal_eligible_now"]==1
    assert diagnostic["internal_waiting_for_review"]==0


def test_local_batch_refuses_false_success_from_risk_board_veto():
    task_id = str(uuid4())
    rows = [{"id": task_id, "action": "internal:brief",
             "status": "waiting_approval", "approval_id": "reviewed"}]
    approvals = [{"id": "reviewed", "action": "internal:brief", "status": "approved"}]
    attempts = []
    for body in (
        {"task_id": task_id, "status": "completed", "delivery_status": "blocked",
         "result": {"board_blocked": True}},
        {"task_id": task_id, "status": "completed", "delivery_status": "completed",
         "result": {"requires_founder_resolution": True}},
        {"task_id": task_id, "status": "completed", "result": "untrusted malformed payload"},
        {"task_id": task_id, "status": "completed", "delivery_status": "unknown"},
    ):
        def dispatch(tid):
            attempts.append(tid)
            return body
        with pytest.raises(RuntimeError, match="unblocked completed task"):
            module.batch(rows, approvals, dispatch, limit=1, apply=True,
                         confirm=module.CONFIRM)
    assert attempts == [task_id] * 4
    assert module.confirmed_local_delivery(
        {"task_id": task_id, "status": "completed",
         "delivery_status": "completed", "result": {"board_blocked": False}},
        task_id,
    ) is True


def test_local_watch_stops_immediately_on_board_veto_without_replay():
    task_id = str(uuid4())
    rows = [{"id": task_id, "action": "internal:brief",
             "status": "waiting_approval", "approval_id": "reviewed"}]
    approvals = [{"id": "reviewed", "action": "internal:brief", "status": "approved"}]
    attempts = []
    def reject(tid):
        attempts.append(tid)
        return {"task_id": tid, "status": "completed", "delivery_status": "blocked",
                "result": {"kind": "local_company_governed_handoff",
                           "board_blocked": True, "requires_founder_resolution": True}}
    with pytest.raises(RuntimeError, match="Blocked or unknown task outcome"):
        module.watch(lambda: (rows, approvals), reject, minutes=1, max_tasks=2,
                     interval=10, confirm=module.CONFIRM)
    assert attempts == [task_id]


def test_durable_attempt_journal_blocks_cross_session_replay_and_keeps_no_secrets(tmp_path):
    task_id=str(uuid4())
    journal=module.DurableAttemptJournal(tmp_path/"receipts")
    assert not (tmp_path/"receipts").exists()
    assert journal.claim(task_id) is True
    assert journal.claim(task_id) is False
    assert module.DurableAttemptJournal(tmp_path/"receipts").claim(task_id) is False
    records=list((tmp_path/"receipts").glob("*.attempt"))
    assert len(records)==1
    receipt=records[0].read_text()
    assert task_id not in receipt
    assert "Bearer " not in receipt
    assert receipt.startswith("AGO_ATTEMPT_V1 ")
    assert len(records[0].stem)==64


def test_durable_claim_happens_before_post_and_never_retries_unknown(tmp_path):
    task_id=str(uuid4())
    records=[{"id":task_id,"action":"internal:brief",
              "status":"waiting_approval","approval_id":"verified"}]
    approvals=[{"id":"verified","status":"approved","action":"internal:brief"}]
    journal=module.DurableAttemptJournal(tmp_path/"attempts")
    calls=[]
    def unknown(tid):
        calls.append(tid)
        raise TimeoutError("Outcome unknown")
    with pytest.raises(TimeoutError):
        module.batch(records,approvals,unknown,limit=1,apply=True,
                     confirm=module.CONFIRM,claim=journal.claim)
    replay=module.batch(records,approvals,unknown,limit=1,apply=True,
                        confirm=module.CONFIRM,
                        claim=module.DurableAttemptJournal(tmp_path/"attempts").claim)
    assert calls==[task_id]
    assert replay["completed_task_ids"]==[]
    assert replay["skipped_previously_attempted"]==[task_id]


def test_durable_watch_skips_already_attempted_ids_without_faking_delivery(tmp_path):
    task_id=str(uuid4())
    journal=module.DurableAttemptJournal(tmp_path/"attempts")
    assert journal.claim(task_id)
    tasks=[{"id":task_id,"action":"internal:brief","status":"waiting_approval","approval_id":"a"}]
    approvals=[{"id":"a","status":"approved","action":"internal:brief"}]
    clock=[0.0]
    output=module.watch(lambda:(tasks,approvals),lambda _:pytest.fail("Replay attempted"),
                        minutes=1,max_tasks=1,interval=10,confirm=module.CONFIRM,
                        clock=lambda:clock[0],pause=lambda dt:clock.__setitem__(0,clock[0]+dt),
                        claim=journal.claim)
    assert output["task_count"]==0
    assert output["skipped_previously_attempted"]==[task_id]


def test_attempt_journal_refuses_symlink_folder(tmp_path):
    target=tmp_path/"legitimate"
    target.mkdir()
    link=tmp_path/"link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError,NotImplementedError):
        pytest.skip("Filesystem does not permit symlinks")
    with pytest.raises(PermissionError):
        module.DurableAttemptJournal(link).claim(str(uuid4()))


def test_safe_queue_resume_after_actual_separate_python_process_exit(tmp_path):
    """A new OS process cannot replay a previous one-shot dispatch claim."""
    first_task, next_task = str(uuid4()), str(uuid4())
    directory = tmp_path / "owner_attempts"
    program = (
        "import importlib.util,sys;"
        "spec=importlib.util.spec_from_file_location('ago_batch',sys.argv[1]);"
        "module=importlib.util.module_from_spec(spec);"
        "spec.loader.exec_module(module);"
        "print(int(module.DurableAttemptJournal(sys.argv[2]).claim(sys.argv[3])))"
    )
    command = [sys.executable, "-c", program, str(SCRIPT), str(directory), first_task]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    restarted = subprocess.run(command, check=True, capture_output=True, text=True)
    assert first.stdout.strip() == "1"
    assert restarted.stdout.strip() == "0"
    assert len(list(directory.glob("*.attempt"))) == 1
    tasks = [
        {"id":first_task,"action":"internal:brief",
         "status":"waiting_approval","approval_id":"approved"},
        {"id":next_task,"action":"internal:brief",
         "status":"waiting_approval","approval_id":"approved"},
    ]
    approved = [{"id":"approved","action":"internal:brief","status":"approved"}]
    called=[]
    def run(task_id):
        called.append(task_id)
        return {"task_id":task_id,"status":"completed"}
    fresh = module.DurableAttemptJournal(directory)
    result = module.batch(tasks, approved, run, limit=2, apply=True,
                          confirm=module.CONFIRM, claim=fresh.claim)
    assert result["completed_task_ids"] == [next_task]
    assert result["skipped_previously_attempted"] == [first_task]
    assert called == [next_task]


def test_engineering_preflight_blocks_stub_or_untrusted_server_response():
    valid = {
        "kind": "ago_local_engineering_capabilities",
        "engineering_enabled": True,
        "provider_mode": "ollama_local", "required_roles": 7,
        "model_tag": "qwen2.5-coder:1.5b",
        "github_write_authorized": False, "release_ready": False,
    }
    module.require_engineering_capability(valid)
    for key, value in (
        ("engineering_enabled", False),
        ("provider_mode", "paid"), ("required_roles", 4),
        ("model_tag", ""), ("github_write_authorized", True),
        ("release_ready", True),
    ):
        altered = {**valid, key: value}
        with pytest.raises(PermissionError):
            module.require_engineering_capability(altered)
    for fake in (None, {}, [], "enabled", {"kind": "true"}):
        with pytest.raises(PermissionError):
            module.require_engineering_capability(fake)


def test_operator_engineering_preflight_is_before_task_dispatch():
    content = SCRIPT.read_text(encoding="utf-8")
    assert '--require-engineering' in content
    assert 'require_engineering_capability(' in content
    assert content.index('require_engineering_capability(\n                request(') < content.index(
        'dispatch=lambda task_id:request("POST"'
    )


def sample_live_board_payload(task_id):
    roles = ("ceo", "cto", "finance", "risk", "quality", "pm", "employee")
    seats = ("Strategy & Vision", "Technology Oversight", "Finance & Budget",
             "Risk & Compliance", "Quality & Release")
    ids = [str(uuid4()) for _ in roles]
    return {"id": str(uuid4()), "task_id": task_id, "status": "completed",
            "delivery_status": "completed", "result": {
                "kind": "local_company_governed_handoff",
                "task_id": task_id, "project_id": str(uuid4()),
                "provider_mode": "ollama_local", "board_review_mode": "full_five_seat",
                "roles_completed": 7, "roles_expected": 7,
                "board_review_cleared": True, "handoff_complete": True,
                "board_blocked": False, "requires_founder_resolution": False,
                "requires_human_qa": True, "board_recommendations_binding": False,
                "engineering_candidate_status": "syntax_reviewed",
                "engineering_candidate": {"files": []},
                "github_commits_created": False, "project_released": False,
                "external_tools_called": False, "runtime_elapsed_ms": 7000,
                "handoffs": [{"role": role, "employee_id": ids[i],
                              "model_inference_completed": True,
                              "human_qa_approved": False,
                              "elapsed_ms": 1000, "draft": "Sensitive draft"}
                             for i, role in enumerate(roles)],
                "board_recommendations": [{"seat": seat, "employee_id": ids[i],
                                           "recommendation": "approve",
                                           "verifiable_model_output": True,
                                           "binding_authorization": False}
                                          for i, seat in enumerate(seats)],
            }}


def test_real_seven_role_acceptance_redacts_drafts_and_requires_seven_employees():
    task_id = str(uuid4())
    receipt = module.verify_real_board_handoffs(sample_live_board_payload(task_id), task_id)
    assert len(set(receipt["employee_ids"])) == 7
    assert receipt["board_votes"] == ["approve"] * 5
    assert receipt["independent_human_qa"] is False
    assert "Sensitive draft" not in str(receipt)


@pytest.mark.parametrize("reason", [
    "stub", "not_seven", "same_person", "board_veto", "vote_unverified",
    "missing_inference", "fake_qa", "wrong_task", "overrun",
    "missing_candidate", "wrong_role", "fake_github",
])
def test_seven_role_fake_success_is_rejected(reason):
    task_id = str(uuid4())
    outcome = sample_live_board_payload(task_id)
    p = outcome["result"]
    if reason == "stub":
        outcome = {"status": "completed", "task_id": task_id}
    elif reason == "not_seven":
        p["handoffs"].pop()
    elif reason == "same_person":
        p["handoffs"][-1]["employee_id"] = p["handoffs"][0]["employee_id"]
    elif reason == "board_veto":
        p["board_blocked"] = True
    elif reason == "vote_unverified":
        p["board_recommendations"][1]["recommendation"] = "unverified"
    elif reason == "missing_inference":
        p["handoffs"][2]["model_inference_completed"] = False
    elif reason == "fake_qa":
        p["handoffs"][0]["human_qa_approved"] = True
    elif reason == "wrong_task":
        p["task_id"] = str(uuid4())
    elif reason == "overrun":
        p["handoffs"][4]["elapsed_ms"] = 90000
    elif reason == "missing_candidate":
        p["engineering_candidate"] = None
    elif reason == "wrong_role":
        p["handoffs"][0]["role"] = "worker"
    elif reason == "fake_github":
        p["github_commits_created"] = True
    with pytest.raises((RuntimeError, TypeError)):
        module.verify_real_board_handoffs(outcome, task_id)


def test_engineering_dispatch_does_not_accept_stub_completion():
    task = str(uuid4())
    work = [{"id": task, "action": "internal:brief",
             "status": "waiting_approval", "approval_id": "ok"}]
    approvals = [{"id": "ok", "status": "approved", "action": "internal:brief"}]
    with pytest.raises((RuntimeError, TypeError)):
        module.batch(work, approvals,
                     lambda _: {"task_id": task, "status": "completed"},
                     limit=1, apply=True, confirm=module.CONFIRM,
                     require_engineering=True)
    verified = module.batch(work, approvals, lambda _: sample_live_board_payload(task),
                            limit=1, apply=True, confirm=module.CONFIRM,
                            require_engineering=True)
    assert verified["completed_task_ids"] == [task]
    assert len(verified["verified_seven_role_handoffs"]) == 1
