"""Full local signed-session AGO task -> four bound AI identities -> durable run.

Uses an injected fake *local* provider, not cloud inference or laptop Ollama;
the exact model endpoint is tested separately. PostgreSQL approvals and stored
run evidence are real and isolated to a disposable fixture transaction.
"""
from uuid import uuid4

from ago.credits import CreditBudget
from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, post


BASE="/v1/organization/company"


def test_governed_local_ollama_chain_needs_actual_founder_board_and_qa(case, monkeypatch):
    import ago.model_handlers as model_handlers

    client,headers,info=case
    founder,reviewer=headers["founder"],headers["reviewer"]
    dept=department(client,founder)

    def ai(name):
        return post(client,"/v1/organization/employees",founder,
                    {"department_id":dept,"name":name,"kind":"ai"})["id"]

    ceo=ai("Strategy Agent")
    cto=ai("Technology Agent")
    pm=ai("Delivery Manager")
    worker=ai("Research Worker")
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
    post(client,"/v1/governance/approvals/"+task_approval["request_id"]+"/decision",
         reviewer,{"approve":True,"reason":"Independent scoped task review"})

    CreditBudget(info["db"]).configure(tenant_id=info["tenant"],ceiling="20")
    calls=[]
    class LocalFake:
        def __init__(self,**kwargs):
            assert kwargs["model"]=="qwen2.5:3b"
            assert kwargs["keep_alive"]=="90s"
        def generate(self, prompt):
            calls.append(prompt)
            assert len(prompt)<=4000
            return ("DECISION: verified draft\nDELIVERABLE: internal role note\n"
                    "RISKS: needs QA\nACCEPTANCE: human must review")

    monkeypatch.setenv("AGO_LLM_PROVIDER","ollama_local")
    monkeypatch.setenv("AGO_ENABLE_LOCAL_MODELS","true")
    monkeypatch.setenv("AGO_LOCAL_COMPANY_CHAIN","true")
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

    for seat,identity in (
        ("Strategy & Vision",ceo),
        ("Technology Oversight",cto),
    ):
        post(client,BASE+"/board/appoint",founder,{
            "seat":seat,"employee_id":identity})

    response=post(client,"/v1/agents/tasks/"+task_id+"/run",founder)
    result=response["result"]
    assert result["kind"]=="local_company_governed_handoff"
    assert result["roles_completed"]==4 and len(calls)==4
    assert [r["employee_id"] for r in result["handoffs"]]==[
        ceo,cto,pm,worker]
    assert [r["role"] for r in result["handoffs"]]==[
        "ceo","cto","pm","employee"]
    assert result["requires_human_qa"] is True
    assert result["github_commits_created"] is False
    assert result["external_tools_called"] is False
    assert result["project_released"] is False
    assert all(not x["human_qa_approved"] for x in result["handoffs"])
    saved=info["db"].execute("""
        SELECT result FROM ago_agent_runs WHERE tenant_id=%s AND task_id=%s
    """,(info["tenant"],task_id)).fetchone()
    assert saved["result"]["roles_completed"]==4
    details=client.get(BASE+"/projects/"+project["id"],headers=founder)
    assert details.status_code==200,details.text
    chain=details.json()["stages"][0]["founder_agent_result"]
    assert chain["roles_completed"]==4
    assert chain["handoffs"][0]["employee_id"]==ceo
    post(client,"/v1/agents/tasks/"+task_id+"/run",founder,expected=403)
    assert len(calls)==4  # duplicate runs are forbidden
