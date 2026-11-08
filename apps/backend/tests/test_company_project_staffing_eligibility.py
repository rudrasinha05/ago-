"""Read-only real PostgreSQL staffing evidence: active employee vs terminated."""
from uuid import uuid4

from test_enterprise_http_21_27 import department, employee
from test_enterprise_hr_21 import _change
from test_m7_http_postgres import case as case, post

BASE="/v1/organization/company"


def test_staffing_shortlist_excludes_terminated_ai_and_requires_real_approval(case):
    client,headers,info=case
    founder,reviewer=headers["founder"],headers["reviewer"]
    dept=department(client,founder)
    employee(client,founder,dept)  # Actual discovery employee.
    ceo=post(client,"/v1/organization/employees",founder,
             {"department_id":dept,"name":"CEO","kind":"ai"})["id"]
    response=client.put(BASE+"/employees/"+ceo+"/role",headers=founder,json={
        "role_title":"Chief Executive Officer",
        "core_responsibilities":"Govern approved local work",
        "extra_responsibilities":"No unapproved external tools",
    })
    assert response.status_code==200,response.text
    post(client,BASE+"/board/appoint",founder,
         {"seat":"Strategy & Vision","employee_id":ceo})
    project=post(client,BASE+"/projects/start",founder,{
        "brief":"Build a secure admissions reporting API with authenticated data validation",
        "operation_key":str(uuid4()),
    })
    plan=post(client,"/v1/brain/plans/"+project["plan_id"]+"/submit",founder)
    post(client,"/v1/governance/approvals/"+plan["approval_id"]+"/decision",
         founder,{"approve":True,"reason":"Approve bounded company project scope"})
    post(client,"/v1/brain/plans/"+project["plan_id"]+"/activate",founder)
    path=BASE+"/projects/"+project["id"]+"/staffing-proposals"
    assert client.get(path,headers=reviewer).status_code==403
    baseline=client.get(path,headers=founder)
    assert baseline.status_code==200,baseline.text
    stage=next(x for x in baseline.json()["proposals"]
               if x["stage"]=="implementation")
    assert stage["eligible_existing_count"]==0
    worker=post(client,"/v1/organization/employees",founder,{
        "department_id":dept,"name":"Software Developer","kind":"ai"})["id"]
    active=client.get(path,headers=founder)
    assert active.status_code==200,active.text
    stage=next(x for x in active.json()["proposals"]
               if x["stage"]=="implementation")
    assert stage["decision"]=="review_existing_staff"
    assert stage["eligible_existing_count"]==1
    assert stage["eligible_candidates"][0]["employee_id"]==worker
    assert active.json()["personnel_hired"] is False
    assert active.json()["permission_granted"] is False
    assert active.json()["source_sha256"]!=baseline.json()["source_sha256"]
    _change(client,founder,reviewer,"terminated",worker)
    after=client.get(path,headers=founder)
    assert after.status_code==200,after.text
    stage=next(x for x in after.json()["proposals"]
               if x["stage"]=="implementation")
    assert stage["decision"]=="propose_specialist_staffing"
    assert stage["eligible_existing_count"]==0
    assert stage["eligible_candidates"]==[]
    assert after.json()["source_sha256"]==baseline.json()["source_sha256"]
    # Read-only shortlist must not forge a staffing activation or model run.
    db=info["db"]
    assert db.execute("SELECT 1 FROM ago_project_stage_delegation_activations "
                      "WHERE tenant_id=%s AND intake_id=%s",
                      (info["tenant"],project["id"])).fetchone() is None
