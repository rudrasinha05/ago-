"""Full local signed-session AGO task -> four bound AI identities -> durable run.

Uses an injected fake *local* provider, not cloud inference or laptop Ollama;
the exact model endpoint is tested separately. PostgreSQL approvals and stored
run evidence are real and isolated to a disposable fixture transaction.
"""
import json
from decimal import Decimal
from uuid import uuid4

import pytest

from ago.credits import CreditBudget
from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, post


BASE="/v1/organization/company"


@pytest.mark.parametrize("full_board,deny_risk,engineering", [
    (False,False,False), (True,False,False), (True,True,False),
    (True,False,True),
])
def test_governed_local_ollama_chain_needs_actual_founder_board_and_qa(
    case, monkeypatch, full_board, deny_risk, engineering,
):
    import ago.model_handlers as model_handlers

    client,headers,info=case
    founder=headers["founder"]
    dept=department(client,founder)

    def ai(name, manager=None):
        payload={"department_id":dept,"name":name,"kind":"ai"}
        if manager:
            payload["manager_id"]=manager
        return post(client,"/v1/organization/employees",founder,payload)["id"]

    ceo=ai("Strategy Agent")
    cto=ai("Technology Agent")
    pm=ai("Delivery Manager")
    worker=ai("Research Worker",pm if full_board else None)
    finance=ai("Finance Director") if full_board else None
    risk=ai("Risk Director") if full_board else None
    quality=ai("Quality Director") if full_board else None
    edited=client.put(BASE+"/employees/"+pm+"/role",headers=founder,json={
        "role_title":"Project Manager",
        "core_responsibilities":"Accountable founder scoped software delivery",
        "extra_responsibilities":"Plan bounded local research tasks"})
    assert edited.status_code==200,edited.text

    project=post(client,BASE+"/projects/start",founder,{
        "brief":"Implement a secure localhost scheduling app with human QA and no public data",
        "operation_key":str(uuid4())})
    assert project["accountable_manager_id"]==pm
    assert project["stages"][0]["suggested_assignee_id"]==worker

    plan=post(client,"/v1/brain/plans/"+project["plan_id"]+"/submit",founder)
    post(client,"/v1/governance/approvals/"+plan["approval_id"]+"/decision",
         founder,{"approve":True,"reason":"Founder approves local project scope"})
    post(client,"/v1/brain/plans/"+project["plan_id"]+"/activate",founder)
    activated=post(client,"/v1/brain/plans/"+project["plan_id"]+"/materialize",founder)
    task_id=activated["task_ids"][0]
    task_approval=post(client,"/v1/governance/approvals",founder,
                       {"action":"internal:brief"})
    post(client,"/v1/tasks/"+task_id+"/approval",founder,{
        "approval_id":task_approval["request_id"]})
    # Founder already approved this project's full strategy; CEO must check
    # the task only after its real board seat is installed.

    CreditBudget(info["db"]).configure(tenant_id=info["tenant"],ceiling="20")
    calls=[]
    class LocalFake:
        def __init__(self,**kwargs):
            assert kwargs["model"]=="qwen2.5:3b"
            assert kwargs["keep_alive"]=="90s"
            assert kwargs["max_output_tokens"]==(1024 if engineering else 384)
        def generate(self, prompt):
            calls.append(prompt)
            assert len(prompt)<=4000
            if deny_risk and "ROLE: RISK\n" in prompt:
                return "BOARD_RECOMMENDATION: DENY\nRISKS: Security risk unresolved"
            if engineering and "ROLE: EMPLOYEE\n" in prompt:
                return json.dumps({
                    "files": [
                        {"path":"src/logic.py", "content":"def answer():\n    return 42\n"},
                        {"path":"tests/test_logic.py", "content":
                         "from src.logic import answer\n\ndef test_answer():\n    assert answer()==42\n"},
                    ],
                    "acceptance_checks":["Run isolated pytest after founder source review"],
                })
            return (("BOARD_RECOMMENDATION: APPROVE\n" if "BOARD_ADVISORY:" in prompt else "") +
                    "DECISION: verified draft\nDELIVERABLE: internal role note\n"
                    "RISKS: needs QA\nACCEPTANCE: human must review")

    monkeypatch.setenv("AGO_LLM_PROVIDER","ollama_local")
    monkeypatch.setenv("AGO_ENABLE_LOCAL_MODELS","true")
    monkeypatch.setenv("AGO_LOCAL_COMPANY_CHAIN","true")
    if engineering:
        monkeypatch.setenv("AGO_LOCAL_ENGINEERING_CANDIDATES","true")
    else:
        monkeypatch.delenv("AGO_LOCAL_ENGINEERING_CANDIDATES",raising=False)
    if full_board:
        monkeypatch.setenv("AGO_LOCAL_FULL_BOARD_REVIEW","true")
    else:
        monkeypatch.delenv("AGO_LOCAL_FULL_BOARD_REVIEW",raising=False)
    monkeypatch.setenv("AGO_LLM_MODEL","qwen2.5:3b")
    monkeypatch.setattr(model_handlers,"OllamaLocalTextProvider",LocalFake)

    # Missing board appointments fail BEFORE consuming approved task, credits or
    # model inference; this is a real governed preflight, not a simulated team.
    post(client,"/v1/agents/tasks/"+task_id+"/run",founder,expected=403)
    assert calls==[]
    original=info["db"].execute("""
        SELECT status FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s
    """,(info["tenant"],task_id)).fetchone()
    assert original["status"]=="waiting_approval"
    assert info["db"].execute("""
        SELECT 1 FROM ago_agent_runs WHERE tenant_id=%s AND task_id=%s
    """,(info["tenant"],task_id)).fetchone() is None

    seats = [("Strategy & Vision",ceo),("Technology Oversight",cto)]
    if full_board:
        seats += [
            ("Finance & Budget",finance),
            ("Risk & Compliance",risk),
            ("Quality & Release",quality),
        ]
    for seat,identity in seats:
        post(client,BASE+"/board/appoint",founder,{
            "seat":seat,"employee_id":identity})
    reconciled=post(client,BASE+"/projects/"+project["id"]+"/ceo/reconcile",founder)
    assert task_id in reconciled["approved_task_ids"]
    assert reconciled["ceo_id"]==ceo
    assert reconciled["tasks_executed"]==0

    response=post(client,"/v1/agents/tasks/"+task_id+"/run",founder)
    result=response["result"]
    assert result["kind"]=="local_company_governed_handoff"
    expected_count=4 if deny_risk else (7 if full_board else 4)
    expected_people=(
        [ceo,cto,finance,risk] if deny_risk
        else ([ceo,cto,finance,risk,quality,pm,worker] if full_board
              else [ceo,cto,pm,worker])
    )
    expected_roles=(
        ["ceo","cto","finance","risk"] if deny_risk
        else (["ceo","cto","finance","risk","quality","pm","employee"]
              if full_board else ["ceo","cto","pm","employee"])
    )
    assert result["roles_completed"]==expected_count and len(calls)==expected_count
    # Exactly the calls attempted count against the virtual budget; a Risk
    # veto must not pretend the remaining three employees spent model credits.
    usage=info["db"].execute("""
        SELECT operation_key,amount FROM ago_credit_usage
        WHERE tenant_id=%s AND operation_key LIKE %s
        ORDER BY operation_key
    """,(info["tenant"],f"local-chain:{task_id}:role:%")).fetchall()
    assert len(usage)==expected_count
    assert all(Decimal(u["amount"]) == Decimal("1") for u in usage)
    assert len({u["operation_key"] for u in usage})==expected_count
    assert float(CreditBudget(info["db"]).balance(tenant_id=info["tenant"])["consumed"])==expected_count
    assert result["roles_expected"]==(7 if full_board else 4)
    assert result["handoff_complete"] is not deny_risk
    assert result["board_review_cleared"] is (full_board and not deny_risk)
    assert result["board_blocked"] is deny_risk
    assert [r["employee_id"] for r in result["handoffs"]]==expected_people
    assert [r["role"] for r in result["handoffs"]]==expected_roles
    assert response["delivery_status"]==("blocked" if deny_risk else "completed")
    assert result["requires_human_qa"] is True
    assert result["engineering_candidate_status"]==(
        "syntax_reviewed" if engineering else "not_requested"
    )
    if engineering:
        assert result["engineering_candidate"]["source_parse_passed"] is True
        assert result["engineering_candidate"]["tests_executed"] is False
        assert result["engineering_candidate"]["github_committed"] is False
    assert result["github_commits_created"] is False
    assert result["external_tools_called"] is False
    assert result["project_released"] is False
    assert all(not x["human_qa_approved"] for x in result["handoffs"])
    saved=info["db"].execute("""
        SELECT result FROM ago_agent_runs WHERE tenant_id=%s AND task_id=%s
    """,(info["tenant"],task_id)).fetchone()
    assert saved["result"]["roles_completed"]==expected_count
    if engineering:
        assert saved["result"]["engineering_candidate"]["candidate_sha256"]==(
            result["engineering_candidate"]["candidate_sha256"]
        )
    task_row=info["db"].execute("""
        SELECT status FROM ago_governed_tasks
        WHERE tenant_id=%s AND id=%s
    """,(info["tenant"],task_id)).fetchone()
    assert task_row["status"]==("failed" if deny_risk else "completed")
    report=info["db"].execute("""
        SELECT kind FROM ago_company_reports
        WHERE tenant_id=%s AND task_id=%s
        ORDER BY id DESC LIMIT 1
    """,(info["tenant"],task_id)).fetchone()
    assert report is not None
    assert report["kind"]==("blocker" if deny_risk else "module_complete")
    details=client.get(BASE+"/projects/"+project["id"],headers=founder)
    assert details.status_code==200,details.text
    chain=details.json()["stages"][0]["founder_agent_result"]
    assert chain["roles_completed"]==expected_count
    assert chain["handoffs"][0]["employee_id"]==ceo
    assert chain["board_review_mode"]==(
        "full_five_seat" if full_board else "legacy_two_seat"
    )
    post(client,"/v1/agents/tasks/"+task_id+"/run",founder,expected=403)
    assert len(calls)==expected_count  # duplicate runs are forbidden
