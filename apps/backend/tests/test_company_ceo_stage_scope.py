"""CEO may staff the exact already-approved five project stages without repeat Founder votes."""
from uuid import uuid4

from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department


def test_ceo_activates_only_founder_approved_recorded_specialists(case):
    client, headers, info=case
    founder, outsider=headers["founder"],headers["reviewer"]
    dept=department(client,founder)
    names=("CEO","Research Analyst","System Architect","Software Developer",
           "QA Specialist","DevOps Release Specialist")
    people={}
    for name in names:
        person=post(client,"/v1/organization/employees",founder,{
            "department_id":dept,"name":name,"kind":"ai"})
        people[name]=person["id"]
    response=client.put(
        "/v1/organization/company/employees/"+people["CEO"]+"/role",
        headers=founder,json={
            "role_title":"Chief Executive Officer",
            "core_responsibilities":"Delivery leadership for Founder approved project",
            "extra_responsibilities":"No unapproved external tools",
        })
    assert response.status_code==200,response.text
    post(client,"/v1/organization/company/board/appoint",founder,{
        "seat":"Strategy & Vision","employee_id":people["CEO"],
    })
    project=post(client,"/v1/organization/company/projects/start",founder,{
        "brief":"Build secure product with research, architecture, code, QA and release evidence",
        "operation_key":str(uuid4()),
    })
    assert len(project["stages"])==5
    base="/v1/organization/company/projects/"+project["id"]
    post(client,base+"/ceo/reconcile",founder,expected=403)
    plan=post(client,"/v1/brain/plans/"+project["plan_id"]+"/submit",founder)
    decided=post(client,"/v1/governance/approvals/"+plan["approval_id"]+"/decision",
                 founder,{"approve":True,"reason":"Single Founder project authorization"})
    assert decided["status"]=="approved"
    post(client,"/v1/brain/plans/"+project["plan_id"]+"/activate",founder)
    tasks=post(client,"/v1/brain/plans/"+project["plan_id"]+"/materialize",founder)
    task_id=tasks["task_ids"][0]
    post(client,"/v1/console/tasks/"+task_id+"/request-approval",founder)
    post(client,base+"/ceo/reconcile",outsider,expected=403)
    recorded=post(client,base+"/ceo/reconcile",founder)
    assert recorded["ceo_id"]==people["CEO"]
    assert recorded["approved_task_ids"]==[task_id]
    assert recorded["approved_stage_count"]==5
    assert set(recorded["approved_stage_names"])=={
        "discovery","architecture","implementation","quality","release"}
    assert recorded["tasks_executed"]==0
    assert recorded["external_tools_authorized"] is False
    rows=info["db"].execute("""
        SELECT a.stage,a.assignee_id,r.reviewer_id,r.status
        FROM ago_project_stage_delegation_activations a
        JOIN ago_project_stage_delegation_proposals d
          ON d.tenant_id=a.tenant_id AND d.id=a.proposal_id
        JOIN ago_approval_requests r
          ON r.tenant_id=d.tenant_id AND r.id=d.approval_id
        WHERE a.tenant_id=%s AND a.intake_id=%s
    """,(info["tenant"],project["id"])).fetchall()
    assert len(rows)==5
    assert all(str(row["reviewer_id"])==people["CEO"] and
               row["status"]=="approved" for row in rows)
    qa=next(row for row in rows if row["stage"]=="quality")
    implementation=next(row for row in rows if row["stage"]=="implementation")
    assert qa["assignee_id"]!=implementation["assignee_id"]
    again=post(client,base+"/ceo/reconcile",founder)
    assert again["approved_stage_count"]==0
    assert again["verified_task_count"]==0
    assert info["db"].execute("""
        SELECT COUNT(*) AS total FROM ago_project_stage_delegation_activations
        WHERE tenant_id=%s AND intake_id=%s
    """,(info["tenant"],project["id"])).fetchone()["total"]==5
