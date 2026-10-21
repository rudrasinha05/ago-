"""Regression: immutable scoped founder authority AND independent operational review."""
from uuid import uuid4

from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee


def test_two_authority_lanes_respect_requester_identity(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]

    # Old M2 operational work: same requester cannot review themselves,
    # even if the requester happens to be the human founder.
    req = post(client, "/v1/governance/approvals", founder,
               {"action":"internal:brief"})
    path="/v1/governance/approvals/"+req["request_id"]+"/decision"
    post(client,path,founder,{"approve":True,"reason":"Forbidden operational self-review"},expected=403)
    authorized=post(client,path,reviewer,{"approve":True,"reason":"Independent reviewed task scope"})
    assert authorized["status"]=="approved"
    assert str(authorized["reviewer_id"])==info["reviewer_id"]

    # In contrast, a company-founder project plan is a *strategic decision*:
    # the independent reviewer cannot hijack this founder decision.
    dept=department(client,founder)
    employee(client,founder,dept)
    brief=("Build a secured, accessible admission enquiry portal with complete "
           "documentation, QA and verifiable project delivery.")
    project=post(client,"/v1/organization/company/projects/start",founder,
                 {"brief":brief,"operation_key":str(uuid4())})
    assert project["plan_status"]=="draft"
    approval=post(client,"/v1/brain/plans/"+project["plan_id"]+"/submit",founder)
    assert approval["approval_id"]
    strategic="/v1/governance/approvals/"+approval["approval_id"]+"/decision"
    post(client,strategic,reviewer,{"approve":True,"reason":"Reviewer cannot decide founder strategy"},expected=403)
    decided=post(client,strategic,founder,{"approve":True,"reason":"Founder approved scoped project planning"})
    assert decided["status"]=="approved"

    inbox=client.get("/v1/organization/company/approvals",headers=founder)
    assert inbox.status_code==200
    items=inbox.json()
    op=next(x for x in items if x["id"]==req["request_id"])
    st=next(x for x in items if x["id"]==approval["approval_id"])
    assert op["requires_founder_decision"] is False
    assert st["requires_founder_decision"] is True
    assert "Independent" in op["review_routing"]
    assert "Founder only" in st["review_routing"]
