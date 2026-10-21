"""Actual project worker assignment is independently reviewed and audit-visible.

All operations run on disposable local PostgreSQL using authenticated sessions.
A founder's strategic approval cannot substitute for operational QA/review.
"""
from uuid import uuid4
from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee

BASE="/v1/organization/company"


def test_local_project_stage_delegation_is_real_audited_and_requires_two_reviews(case):
    client,headers,info=case
    founder,reviewer=headers["founder"],headers["reviewer"]
    dept=department(client,founder)
    employee(client,founder,dept)  # Real AI discovery agent, seeds a bounded plan step.
    developer=post(client,"/v1/organization/employees",founder,
                   {"department_id":dept,"name":"Backend Engineer","kind":"ai"})["id"]
    project=post(client,BASE+"/projects/start",founder,
                 {"brief":"Build a secure admission workflow with working modules, reviewed CI and documentation",
                  "operation_key":str(uuid4())})
    path=BASE+"/projects/"+project["id"]+"/delegations"
    payload={"stage":"implementation","assignee_id":developer}
    post(client,path,reviewer,payload,expected=403)
    proposal=post(client,path,founder,payload)
    assert proposal["task_executed"] is False
    assert proposal["status"]=="pending_independent_review"
    again=post(client,path,founder,payload)
    assert again["reused"] is True
    assert again["proposal_id"]==proposal["proposal_id"]
    apply=path+"/"+proposal["proposal_id"]+"/activate"
    post(client,apply,founder,{},expected=403)  # Strategy not active
    self_review="/v1/governance/approvals/"+proposal["approval_id"]+"/decision"
    post(client,self_review,founder,{"approve":True,"reason":"No self review"},expected=403)
    decision=post(client,self_review,reviewer,
                  {"approve":True,"reason":"Independent review of implementation team scope"})
    assert decision["status"]=="approved"
    post(client,apply,founder,{},expected=403)  # Approval alone cannot activate a draft strategy

    # Only the founder can authorize original strategy; reviewer cannot hijack it.
    strategy=post(client,"/v1/brain/plans/"+project["plan_id"]+"/submit",founder)
    gate="/v1/governance/approvals/"+strategy["approval_id"]+"/decision"
    post(client,gate,reviewer,{"approve":True,"reason":"Not founder"},expected=403)
    post(client,gate,founder,{"approve":True,"reason":"Approve bounded local project goals"})
    post(client,"/v1/brain/plans/"+project["plan_id"]+"/activate",founder)

    assignment=post(client,apply,founder,{})
    assert assignment["assignee_id"]==developer
    assert assignment["stage"]=="implementation"
    assert assignment["reused"] is False
    assert assignment["task_executed"] is False
    assert post(client,apply,founder,{})["reused"] is True
    post(client,apply,reviewer,{},expected=403)
    queue=client.get(path,headers=founder)
    assert queue.status_code==200,queue.text
    rows=queue.json()
    assert len(rows)==1
    assert rows[0]["approval_status"]=="approved"
    assert rows[0]["worker_name"]=="Backend Engineer"
    assert rows[0]["applied_at"]
    assert info["db"].execute("""
      SELECT COUNT(*) AS total FROM ago_project_stage_delegation_activations
      WHERE tenant_id=%s AND intake_id=%s
    """,(info["tenant"],project["id"])).fetchone()["total"]==1
    # Recorded assignment is not a fake model run, task execution or GitHub commit.
    assert info["db"].execute("""
      SELECT 1 FROM ago_agent_runs WHERE tenant_id=%s
    """,(info["tenant"],)).fetchone() is None


def test_worker_scope_and_project_isolation_are_denied(case):
    client,headers,info=case
    founder=headers["founder"]
    dept=department(client,founder)
    researcher=employee(client,founder,dept)
    project=post(client,BASE+"/projects/start",founder,{
        "brief":"Develop auditable local governance and validated QA control reports",
        "operation_key":str(uuid4())})
    path=BASE+"/projects/"+project["id"]+"/delegations"
    post(client,path,founder,{"stage":"quality","assignee_id":researcher},expected=403)
    post(client,path,founder,{"stage":"implementation","assignee_id":str(uuid4())},
         expected=404)
    post(client,BASE+"/projects/"+str(uuid4())+"/delegations",founder,
         {"stage":"implementation","assignee_id":researcher},expected=404)
    # Reviewer approval power does not confer company-wide read access.
    assert client.get(path,headers=headers["reviewer"]).status_code==403
    assert client.get(path,headers=founder).status_code==200
    assert client.get(path).status_code==401

def test_confidential_registry_denies_unassigned_company_readers(case):
    """Company-level RBAC alone must not reveal founder's confidential projects."""
    client,headers,info=case
    founder,reviewer=headers["founder"],headers["reviewer"]
    project=post(client,BASE+"/projects/start",founder,{
        "brief":"Confidential invention prototype with founder-only business plans and unreleased research",
        "operation_key":str(uuid4())})
    # Reviewer is granted ordinary organization/brain read in this disposable
    # tenant to prove *per-project* access is checked independently.
    for permission in ("organization:read","brain:read"):
        info["db"].execute("""
            INSERT INTO ago_role_permissions(tenant_id,role,permission)
            VALUES (%s,'reviewer',%s) ON CONFLICT DO NOTHING
        """,(info["tenant"],permission))
    registry=client.get(BASE+"/projects",headers=reviewer)
    assert registry.status_code==200,registry.text
    assert all(str(x["id"])!=project["id"] for x in registry.json())
    assert client.get(BASE+"/projects/"+project["id"],headers=reviewer).status_code==404
    assert client.get(BASE+"/projects/"+project["id"]+"/delegations",
                      headers=reviewer).status_code==404
    founder_list=client.get(BASE+"/projects",headers=founder)
    assert any(x["id"]==project["id"] for x in founder_list.json())
    assert client.get(BASE+"/projects/"+project["id"],headers=founder).status_code==200
